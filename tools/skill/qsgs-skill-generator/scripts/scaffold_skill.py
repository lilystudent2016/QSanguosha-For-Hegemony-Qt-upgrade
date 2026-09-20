#!/usr/bin/env python3
"""根据中文 lang 条目生成技能三件套骨架（C++ / AI / lang）。

用法：
    # 从 lang 文件里取一个技能，生成骨架到 ./qsgs-scaffold/<skill>/
    python scaffold_skill.py lang/zh_CN/Package/StandardWeiGeneral.lua --skill jianxiong

    # 直接从 lang 片段生成
    python scaffold_skill.py --snippet my-skill.lang.lua --out ./out

    # 指定 package（决定 .pro / 注册函数提示）与输出目录
    python scaffold_skill.py <file> --skill xxx --package formation --out ./out

    # 只打印不落盘
    python scaffold_skill.py <file> --skill xxx --print

生成物（放在 --out 目录）：
    <skill>.h         技能卡声明（仅当需要技能卡时生成）
    <skill>.cpp       C++ 技能类骨架
    <skill>.lang.lua  lang 中文条目（规范化后的输入）
    <skill>-ai.lua    AI hook 骨架
    README.md         落点清单 + 待人工补全的 TODO

生成的是**骨架**：结构、事件、频率、hook 组合都已按解析结果填好，
但技能语义（条件判断与结算内容）会留成显式 TODO，需要人工或模型补全。
生成后请用 inspect_skill.py 自检三处是否对齐。

只读输入文件，写出到 --out 目录。
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from parse_lang import analyse, parse_text, read
except ImportError:
    print("错误：需要与 parse_lang.py 放在同一目录", file=sys.stderr)
    raise


def pascal(name):
    """he-xia_pinyin -> HeXiaPinyin"""
    parts = re.split(r"[-_]+", name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


# --------------------------------------------------------------------------
# C++ 骨架
# --------------------------------------------------------------------------

HEADER = """// ============================================================
// 生成物 {skill} —— 由 scaffold_skill.py 自动生成
// objectName: {obj}   中文名: {cn}
// 形态: {form}    建议基类: {base}
// 落点: src/package/<pkg>.cpp{hp}
// ============================================================
"""


def gen_h(s, card):
    return """// ============================================================
// {cn}（{obj}）技能卡声明
// 落点：src/package/<pkg>.h
// 硬性要求：SkillCard 必须声明在 .h，且带 Q_OBJECT + Q_INVOKABLE
//           否则 moc 不生成元对象，运行期 @{card} 解析不到（静默失效）
//           并在包构造函数里 addMetaObject<{card}>();
// ============================================================

class {card} : public SkillCard
{{
    Q_OBJECT

public:
    Q_INVOKABLE {card}();

    virtual bool targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const;
    // TODO: 若描述里还有"额外消耗"（弃牌 / 失去体力），加 extraCost：
    // virtual void extraCost(Room *room, const CardUseStruct &card_use) const;
    virtual void onEffect(const CardEffectStruct &effect) const;
}};
""".format(cn=s["cn_name"] or s["objectName"], obj=s["objectName"], card=card)


CPP_TAIL = """
// ============================================================
// 注册（两处都要）
// ============================================================
// 1) 包构造函数中登记技能卡元对象（仅当有技能卡时）：
//        addMetaObject<{card}>();
// 2) 武将注册函数 / 包构造函数中挂技能：
//        general->addSkill(new {cls});
//    standard 包的注册函数在 standard-wei-generals.cpp 的 StandardPackage::addWeiGenerals() 等；
//    其它包直接在 XxxPackage::XxxPackage() 里建 General 并 addSkill。
// 3) 新增了 .cpp/.h 时，同步加进 QSanguosha.pro 的 SOURCES / HEADERS。
"""


def gen_cpp_trigger(s):
    cls = pascal(s["objectName"])
    events = " << ".join(s["events"]) if s["events"] else "/* TODO: 选事件 */"
    freq = s["frequency"]
    return """// {form}骨架
class {cls} : public {base}
{{
public:
    {cls}() : {base}("{obj}")
    {{
        events << {events};
        frequency = Skill::{freq};
    }}

    virtual QStringList triggerable(TriggerEvent triggerEvent, Room *room, ServerPlayer *player,
                                    QVariant &data, ServerPlayer * &ask_who) const
    {{
        // TODO: 补发动条件。返回 QStringList(objectName()) 表示可发动，空列表表示不发动。
        //       注意"一名角色"类描述要用 player 判断主体，不要默认成自己。
        if (TriggerSkill::triggerable(player)) {{
            return QStringList();
        }}
        return QStringList();
    }}

    virtual bool cost(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer *) const
    {{
        // TODO: 若有"弃置一张牌 / 失去体力"等消耗，在这里完成，再 return true
        if (player->askForSkillInvoke(this, data)) {{
            room->broadcastSkillInvoke(objectName(), player);
            return true;
        }}
        return false;
    }}

    virtual bool effect(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer *) const
    {{
        // TODO: 补结算内容
        return false;   // 返回 true 会中断后续结算链
    }}
}};
""".format(form=s["form"], cls=cls, base=s["base"], obj=s["objectName"],
           events=events, freq=freq)


def gen_cpp_masochism(s):
    cls = pascal(s["objectName"])
    return """// 受虐技骨架（MasochismSkill）
// 注意：Damaged 事件由基类自动挂载，构造函数里不要写 events <<
class {cls} : public MasochismSkill
{{
public:
    {cls}() : MasochismSkill("{obj}")
    {{
        frequency = Skill::{freq};
    }}

    virtual QStringList triggerable(TriggerEvent, Room *room, ServerPlayer *player,
                                    QVariant &data, ServerPlayer * &) const
    {{
        if (MasochismSkill::triggerable(player)) {{
            DamageStruct damage = data.value<DamageStruct>();
            // TODO: 补发动条件，例如 damage.card != NULL / damage.from != NULL
            return QStringList(objectName());
        }}
        return QStringList();
    }}

    virtual bool cost(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer *) const
    {{
        if (player->askForSkillInvoke(this, data)) {{
            room->broadcastSkillInvoke(objectName(), player);
            return true;
        }}
        return false;
    }}

    // 结算写在 onDamaged，不写 effect
    virtual void onDamaged(ServerPlayer *player, const DamageStruct &damage) const
    {{
        // TODO: 补结算内容
    }}
}};
""".format(cls=cls, obj=s["objectName"], freq=s["frequency"])


def gen_cpp_viewas(s):
    cls = pascal(s["objectName"])
    base = s["base"]
    if base == "OneCardViewAsSkill":
        body = """    {cls}() : OneCardViewAsSkill("{obj}")
    {{
        filter_pattern = /* TODO: 例 ".|black|.|hand" */;
        response_pattern = /* TODO: 仅响应时填 "jink" / "slash" / "nullification" */;
        response_or_use = true;
    }}

    virtual const Card *viewAs(const Card *originalCard) const
    {{
        // TODO: 构造目标牌。下面四步都不能少。
        // Jink *jink = new Jink(originalCard->getSuit(), originalCard->getNumber());
        // jink->setSkillName(objectName());
        // jink->addSubcard(originalCard->getId());
        // jink->setShowSkill(objectName());
        // return jink;
        return NULL;
    }}""".format(cls=cls, obj=s["objectName"])
    elif base == "ZeroCardViewAsSkill":
        card = cls + "Card"
        body = """    {cls}() : ZeroCardViewAsSkill("{obj}")
    {{
    }}

    virtual bool isEnabledAtPlay(const Player *player) const
    {{
        // TODO: 若有"出牌阶段限一次"，加 !player->hasUsed("{card}")
        return false;
    }}

    virtual const Card *viewAs() const
    {{
        {card} *card = new {card};
        card->setShowSkill(objectName());
        return card;
    }}""".format(cls=cls, obj=s["objectName"], card=card)
    else:  # ViewAsSkill
        body = """    {cls}() : ViewAsSkill("{obj}")
    {{
    }}

    virtual bool isEnabledAtPlay(const Player *player) const
    {{
        return false;   // TODO
    }}

    virtual bool viewFilter(const QList<const Card *> &selected, const Card *to_select) const
    {{
        // TODO: 可选牌的范围。selected.isEmpty() 表示只允许选一张
        return selected.isEmpty();
    }}

    virtual const Card *viewAs(const QList<const Card *> &cards) const
    {{
        // TODO: 构造目标牌，别忘了 setShowSkill(objectName())
        return NULL;
    }}""".format(cls=cls, obj=s["objectName"])
    return "// 视为技骨架\nclass {cls} : public {base}\n{{\npublic:\n{body}\n}};\n".format(
        cls=cls, base=base, body=body)


def gen_cpp_modifier(s):
    cls = pascal(s["objectName"])
    base = s["base"]
    sig = {
        "ProhibitSkill": ("isProhibited(const Player *from, const Player *to, const Card *card, "
                          "const QList<const Player *> &others) const",
                          "return false;   // TODO: 返回 true 表示禁止使用"),
        "DistanceSkill": ("getCorrect(const Player *from, const Player *to) const",
                          "return 0;   // TODO: 返回距离修正值，例如 -1"),
        "MaxCardsSkill": ("getExtra(const Player *target) const",
                          "return 0;   // TODO: 手牌上限的额外值"),
        "AttackRangeSkill": ("getExtra(const Player *target, const Player *source) const",
                             "return 0;   // TODO: 攻击范围的额外值"),
        "TargetModSkill": ("getResidueNum(const Player *from, const Card *card) const",
                           "return 0;   // TODO: 额外使用次数（另有 getDistanceLimit / getExtraTargetNum）"),
        "InvaliditySkill": ("isSkillValid(const Player *player, const Skill *skill) const",
                            "return false;   // TODO"),
        "ViewHasSkill": ("ViewHas(const Player *player, const QString &skill_name, const QString &flag) const",
                         "return false;   // TODO"),
    }
    fn, ret = sig.get(base, ("/* TODO: 覆写该基类的纯虚函数 */", "return 0;"))
    return """// 规则修正型骨架（{base}）—— 不产生牌、不主动触发，只改规则数值或合法性
class {cls} : public {base}
{{
public:
    {cls}() : {base}("{obj}")
    {{
        frequency = Skill::{freq};
    }}

    virtual {fn}
    {{
        {ret}
    }}
}};
""".format(base=base, cls=cls, obj=s["objectName"], freq=s["frequency"], fn=fn, ret=ret)


def gen_cpp(s):
    cls = pascal(s["objectName"])
    card = cls + "Card" if s["needs_skillcard"] else None
    parts = [HEADER.format(skill=cls, obj=s["objectName"], cn=s["cn_name"],
                           form=s["form"], base=s["base"],
                           hp="（另需 .h 声明技能卡）" if card else "")]

    if card:
        parts.append("""// —— 技能卡实现 ——
{card}::{card}()
{{
}}

bool {card}::targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const
{{
    // TODO: 补目标合法性。只选一人时 targets.isEmpty() 必写
    return targets.isEmpty() && to_select != Self;
}}

void {card}::onEffect(const CardEffectStruct &effect) const
{{
    Room *room = effect.from->getRoom();
    // TODO: 补结算。需要询问选项时：
    //   QString choice = room->askForChoice(effect.to, "{obj}", "选项1+选项2", QVariant(), "@{obj}-choose");
    // 需要弃牌时（reason 用 objectName，AI 侧对应 sgs.ai_skill_discard.{obj}）：
    //   room->askForDiscard(effect.to, "{obj}", 1, 1, false, true);
}}
""".format(card=card, obj=s["objectName"]))
    elif s["base"] == "MasochismSkill":
        parts.append(gen_cpp_masochism(s))
    elif s["base"] in ("ViewAsSkill", "OneCardViewAsSkill", "ZeroCardViewAsSkill"):
        parts.append(gen_cpp_viewas(s))
    elif s["base"] in ("ProhibitSkill", "DistanceSkill", "MaxCardsSkill", "AttackRangeSkill",
                       "TargetModSkill", "InvaliditySkill", "ViewHasSkill"):
        parts.append(gen_cpp_modifier(s))
    else:
        parts.append(gen_cpp_trigger(s))

    parts.append(CPP_TAIL.format(card=card or (cls + "Card"), cls=cls))
    tail = "\n// 频率实现提示：%s\n" % s["limit"] if s["limit"] else ""
    return "\n".join(parts) + tail


# --------------------------------------------------------------------------
# AI 骨架
# --------------------------------------------------------------------------

AI_HEAD = """-- ============================================================
-- 生成物 {skill} —— 由 scaffold_skill.py 自动生成
-- objectName: {obj}   中文名: {cn}
-- 落点：lua/ai/<pkg>-ai.lua（往已存在的文件追加；已存在文件不需要登记）
-- hook 全表与签名见 references/ai-hooks.md
-- ============================================================

--{cn}
"""


def gen_ai(s):
    name = s["objectName"]
    cls = pascal(name)
    card = cls + "Card"
    out = [AI_HEAD.format(skill=cls, obj=name, cn=s["cn_name"] or name)]
    hooks = [h for h, _ in s["ai_hooks"]]

    need_use = any("getTurnUseCard" in h for h in hooks)
    if need_use:
        out.append("""-- 1) 让 AI 在出牌阶段"想起"这个技能（技能卡 / 视为技必配，否则 AI 永远不会用）
local {low}_skill = {{}}
{low}_skill.name = "{obj}"
table.insert(sgs.ai_skills, {low}_skill)
{low}_skill.getTurnUseCard = function(self)
{guard}
	-- TODO: 判断是否值得发动（敌方数量、目标是否虚弱、代价是否划得来）
	-- TODO: 构造技能卡字符串（含实体牌）：
	--   return sgs.Card_Parse("@{card}=<card_id>&{obj}")   -- 需要消耗牌时
	--   return sgs.Card_Parse("@{card}=.&{obj}")           -- 不消耗牌时
	return nil
end

""".format(low=name.replace("-", "_"), obj=name, card=card,
           guard=("\t-- 出牌阶段限一次\n\tif self.player:hasUsed(\"%s\") then return end\n" % card)
                 if "限一次" in (s["limit"] or "") else ""))
        out.append("""-- 2) 技能卡的选目标与结算策略（键是【类名】，不是技能名 —— 高频错误点）
sgs.ai_skill_use_func.{card} = function(card, use, self)
	if #self.enemies == 0 then return end
	-- TODO: 选目标，通过写 use.card 与 use.to 表达决策
	-- use.card = card
	-- if use.to then use.to:append(target) end
end

""".format(card=card))

    if "sgs.ai_skill_invoke.%s" % name in hooks:
        out.append("""-- 3) 是否发动（可选技必配，否则 AI 永不发动）
sgs.ai_skill_invoke.{obj} = function(self, data)
	-- TODO: 国战常先判断亮将意愿：self:willShowForMasochism() / willShowForAttack() / willShowForDefence()
	return true
end

""".format(obj=name))

    if "sgs.ai_skill_choice.%s" % name in hooks:
        opts = "、".join(s["choices"]) or "（把 choices 里的一项原样返回）"
        out.append("""-- 4) 询问选项（choices = "{choices}"）
--    注意：这里的 self.player 是【被询问者】，不一定是技能拥有者
sgs.ai_skill_choice.{obj} = function(self, choices, data)
	-- TODO: 按局势返回选项串
	return choices
end

""".format(obj=name, choices=opts))

    if "sgs.ai_skill_playerchosen.%s" % name in hooks:
        out.append("""-- 5) 选目标（reason = "{obj}"）
sgs.ai_skill_playerchosen.{obj} = function(self, targets, max_num, min_num)
	self:sort(self.enemies, "hp")
	for _, p in ipairs(self.enemies) do
		if targets:contains(p) then return p end
	end
end

""".format(obj=name))

    if "sgs.ai_skill_discard.%s" % name in hooks:
        out.append("""-- 6) 弃牌选择（reason = "{obj}"）
sgs.ai_skill_discard.{obj} = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByKeepValue(cards, true)
	local result = {{}}
	for i = 1, math.min(discard_num, #cards) do
		result[#result + 1] = cards[i]:getId()
	end
	return result
end

""".format(obj=name))

    if "sgs.ai_skill_pindian.%s" % name in hooks:
        out.append("""-- 7) 拼点出牌（reason = "{obj}"）
sgs.ai_skill_pindian.{obj} = function(self, minusecard, self_player, requestor, maxcard, mincard)
	return self:getMaxCard()
end

""".format(obj=name))

    if "sgs.ai_view_as.%s" % name in hooks:
        out.append("""-- 8) 视为技：判定某张牌能否被转化（不配这段，视为技完全不会被 AI 使用）
sgs.ai_view_as.{obj} = function(card, player, card_place)
	local suit = card:getSuitString()
	local number = card:getNumberString()
	local card_id = card:getEffectiveId()
	-- TODO: 补可转化条件
	if card_place == sgs.Player_PlaceHand then
		return ("<目标牌类名小写>:{obj}[%s:%s]=%d&{obj}"):format(suit, number, card_id)
	end
end

""".format(obj=name))

    if need_use:
        out.append("""-- 9) 数值偏好（让 AI 正确评估这张技能卡）
sgs.ai_use_value.{card} = 3.5
sgs.ai_card_intention.{card} = 80
sgs.dynamic_value.damage_card.{card} = true
""".format(card=card))

    if len(out) == 1:
        out.append("-- 解析结果里没有推导出必须的 AI hook，请人工确认该技能是否需要 AI 决策。\n")
    return "".join(out)


# --------------------------------------------------------------------------

def gen_lang(s):
    lines = ['\t["%s"] = "%s",' % (s["objectName"], s["cn_name"] or "TODO 中文技能名"),
             '\t[":%s"] = "%s",' % (s["objectName"], s["desc"] or "TODO 技能描述")]
    for v in s["extra_keys"].get("@", []):
        lines.append('\t["@%s"] = "%s",' % (s["objectName"], v))
    for v in s["extra_keys"].get("~", []):
        lines.append('\t["~%s"] = "%s",' % (s["objectName"], v))
    if s["choices"]:
        lines.append("")
        lines.append("\t-- 选项标签（由 [\"%s:xxx\"] 这种键提供）" % s["objectName"])
        for k, v in s["choices"].items():
            lines.append('\t["%s:%s"] = "%s",' % (s["objectName"], k, v))
    return "return {\n" + "\n".join(lines) + "\n}\n"


def gen_readme(s, files):
    cls = pascal(s["objectName"])
    card = cls + "Card" if s["needs_skillcard"] else None
    out = ["# %s（`%s`）生成说明" % (s["cn_name"] or "未命名", s["objectName"]), ""]
    out.append("> 自动解析结果。骨架里的结构已按描述填好，**语义部分留成 TODO**。")
    out.append("")
    out.append("| 要素 | 判定 |")
    out.append("|---|---|")
    out.append("| 形态 | %s |" % s["form"])
    out.append("| 建议基类 | `%s` |" % s["base"])
    out.append("| 可选性 | %s |" % ("可选" if s["optional"] else "强制/锁定"))
    out.append("| 频率 | `Skill::%s` |" % s["frequency"])
    out.append("| 事件 | `%s` |" % (" << ".join(s["events"]) or "—"))
    out.append("| 需技能卡 | %s |" % ("是（`%s`）" % card if card else "否"))
    out.append("")
    out.append("## 生成的文件与落点")
    out.append("")
    for f, where in files:
        out.append("- `%s` → %s" % (f, where))
    out.append("")
    out.append("## 还要做的事")
    out.append("")
    todos = [
        "把 C++ 粘进 `src/package/<pkg>.cpp`，技能卡类粘进 `.h`（如有）",
        "在包构造函数里 `addMetaObject<%s>();`（如有技能卡）" % (card or "XxxCard"),
        "在武将注册函数里 `addSkill(new %s);`" % cls,
        "把 lang 条目追加到 `lang/zh_CN/Package/<LangFile>.lua`（落点先 grep 兄弟技能确认）",
        "把 AI 追加到 `lua/ai/<pkg>-ai.lua`",
        "新增文件时补进 `QSanguosha.pro` 的 SOURCES / HEADERS",
        "补全所有 TODO 注释处的语义判断",
        "跑 `python scripts/inspect_skill.py %s` 自检三处是否对齐" % s["objectName"],
    ]
    for t in todos:
        out.append("- [ ] %s" % t)
    if s["notes"]:
        out.append("")
        out.append("## 解析器给的额外提示")
        out.append("")
        for n in s["notes"]:
            out.append("- %s" % n)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="根据中文 lang 条目生成技能三件套骨架")
    ap.add_argument("file", nargs="?", help="lang 文件路径")
    ap.add_argument("--snippet", help="lang 片段文件")
    ap.add_argument("--skill", help="技能 objectName（文件里有多个技能时必填）")
    ap.add_argument("--package", help="所属 package（仅用于提示）", default="<pkg>")
    ap.add_argument("--out", help="输出目录", default=None)
    ap.add_argument("--print", dest="to_stdout", action="store_true", help="只打印不落盘")
    args = ap.parse_args()

    target = args.snippet or args.file
    if not target:
        ap.print_help()
        return 2
    if not os.path.isfile(target):
        print("错误：文件不存在 %s" % target, file=sys.stderr)
        return 2

    text = read(target)
    if text.startswith("\ufeff"):
        text = text[1:]
    skills, _ = parse_text(text)
    if not skills:
        print("错误：没解析到技能。判定条件是同时存在 [\"K\"] 与 [\":K\"]（或 [\"@K\"]/[\"~K\"]）", file=sys.stderr)
        return 1

    if args.skill:
        if args.skill not in skills:
            print("错误：没有技能 \"%s\"；该文件里有：%s" % (args.skill, ", ".join(sorted(skills))),
                  file=sys.stderr)
            return 1
        picked = {args.skill: skills[args.skill]}
    else:
        if len(skills) > 1:
            print("错误：文件里有 %d 个技能，请用 --skill 指定：%s"
                  % (len(skills), ", ".join(sorted(skills))), file=sys.stderr)
            return 1
        picked = skills

    name, s = list(picked.items())[0]
    cls = pascal(name)
    card = cls + "Card" if s["needs_skillcard"] else None
    pkg = args.package

    files = []
    if card:
        files.append(("%s.h" % name, "src/package/%s.h（技能卡声明）" % pkg))
    files.append(("%s.cpp" % name, "src/package/%s.cpp（技能类）" % pkg))
    files.append(("%s.lang.lua" % name, "lang/zh_CN/Package/<LangFile>.lua 的条目内容"))
    files.append(("%s-ai.lua" % name, "lua/ai/%s-ai.lua（AI hook）" % pkg))

    built = [
        (name + ".h", gen_h(s, card)) if card else None,
        (name + ".cpp", gen_cpp(s)),
        (name + ".lang.lua", gen_lang(s)),
        (name + "-ai.lua", gen_ai(s)),
        ("README.md", gen_readme(s, files)),
    ]
    built = [b for b in built if b]

    if args.to_stdout:
        for fn, content in built:
            print("=" * 70)
            print("## %s" % fn)
            print("=" * 70)
            print(content)
        return 0

    outdir = args.out or os.path.join(os.getcwd(), "qsgs-scaffold", name)
    os.makedirs(outdir, exist_ok=True)
    for fn, content in built:
        with open(os.path.join(outdir, fn), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    print("已生成到 %s：" % outdir)
    for fn, _ in built:
        print("    %s" % fn)
    print()
    print("下一步：按 README.md 的清单补 TODO，然后用 inspect_skill.py 自检。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
