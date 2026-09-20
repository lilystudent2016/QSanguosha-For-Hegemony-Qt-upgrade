#!/usr/bin/env python3
"""lang/zh_CN 技能条目解析器（中文 lang 文件 → 技能要素表）。

用法：
    # 解析单个 lang 文件，列出其中所有技能及其要素
    python parse_lang.py lang/zh_CN/Package/StandardWeiGeneral.lua

    # 只看某个技能
    python parse_lang.py <file> --skill jianxiong

    # 直接解析一段 lang 片段（不必是合法 lua 表）
    python parse_lang.py --snippet my-skill.lang.lua

    # 列出整个项目 lang 里的全部技能名
    python parse_lang.py --root <项目根> --list

    # 机器可读
    python parse_lang.py <file> --json

解析结果可直接交给 scaffold_skill.py 生成三件套骨架。

只读操作，不修改任何文件。
"""

import argparse
import json
import os
import re
import sys

# --------------------------------------------------------------------------
# 中文措辞 → 技能要素 的规则表（依据 references/cn-to-cpp.md）
# --------------------------------------------------------------------------

# 触发时机关键词 → (TriggerEvent 列表, 建议基类, 类别)
# 类别：trigger = 由时机触发；active = 主动使用（不挂事件）
# 顺序敏感：更具体的时机放前面；命中即停止。
TIMING_RULES = [
    (r"受到伤害后", ["Damaged"], "MasochismSkill", "trigger"),
    (r"造成伤害后", ["Damage"], None, "trigger"),
    (r"即将造成伤害|造成伤害时|伤害结算开始时", ["DamageCaused"], None, "trigger"),
    (r"进入濒死状态", ["Dying"], None, "trigger"),
    (r"死亡后", ["DeathFinished"], None, "trigger"),
    (r"摸牌阶段结束时", ["EventPhaseEnd", "Player::Draw"], None, "trigger"),
    (r"摸牌阶段", ["EventPhaseStart", "Player::Draw"], "DrawCardsSkill", "trigger"),
    (r"准备阶段|回合开始阶段", ["EventPhaseStart", "Player::Start"], "PhaseChangeSkill", "trigger"),
    (r"回合开始时|回合一号位置", ["TurnStart"], "PhaseChangeSkill", "trigger"),
    (r"结束阶段", ["EventPhaseStart", "Player::Finish"], None, "trigger"),
    (r"出牌阶段结束时", ["EventPhaseEnd", "Player::Play"], None, "trigger"),
    (r"出牌阶段开始时", ["EventPhaseStart", "Player::Play"], None, "trigger"),
    (r"出牌阶段", [], None, "active"),
    (r"弃牌阶段结束时", ["EventPhaseEnd", "Player::Discard"], None, "trigger"),
    (r"弃牌阶段", ["EventPhaseStart", "Player::Discard"], None, "trigger"),
    (r"判定阶段", ["EventPhaseStart", "Player::Judge"], None, "trigger"),
    (r"回合结束时", ["EventPhaseStart", "Player::NotActive"], None, "trigger"),
    (r"回合结束后", ["EventPhaseEnd", "Player::NotActive"], None, "trigger"),
    (r"判定牌生效前|判定前", ["AskForRetrial"], None, "trigger"),
    (r"判定结果确定后", ["FinishRetrial"], None, "trigger"),
    (r"拼点时", ["PindianVerifying"], None, "trigger"),
    (r"拼点后", ["Pindian"], None, "trigger"),
    (r"使用牌时", ["PreCardUsed"], None, "trigger"),
    (r"指定目标后", ["TargetChosen"], None, "trigger"),
    (r"结算完成后", ["CardFinished"], None, "trigger"),
    (r"响应后", ["CardResponded"], None, "trigger"),
    (r"游戏开始时", ["GameStart"], "GameStartSkill", "trigger"),
    (r"体力值变化|失去体力时|回复体力时", ["PreHpLost"], None, "trigger"),
    (r"手牌上限", ["MaxHpChanged"], "MaxCardsSkill", "trigger"),
    (r"翻面", ["TurnedOver"], None, "trigger"),
]

# 视为技识别
VIEWAS_RULES = [
    (r"一张.{0,6}牌当【", "OneCardViewAsSkill",
     "一对一转化 → OneCardViewAsSkill + filter_pattern"),
    (r"任意张.{0,6}牌当【|将.{0,4}张牌当【", "ViewAsSkill",
     "多对一转化 → ViewAsSkill + viewFilter/viewAs"),
    (r"视为使用一张【|视为使用【", "ZeroCardViewAsSkill",
     "不消耗牌 → ZeroCardViewAsSkill（需选目标时配 SkillCard）"),
]

# 规则修正型识别（措辞必须指向技能拥有者自身的属性，避免把"其对其攻击范围内"这类
# 目标筛选条件误判成规则修正技）
MODIFIER_RULES = [
    (r"不能使用|不能打出|无法使用|禁止使用", "ProhibitSkill", "isProhibited"),
    (r"计算与其他角色的距离|至其他角色的距离|距离[-＋+]\d", "DistanceSkill", "getCorrect"),
    (r"你的手牌上限|手牌上限[+＋-]\d", "MaxCardsSkill", "getExtra / getFixed"),
    (r"你的攻击范围[+＋-]|攻击范围[+＋-]\d", "AttackRangeSkill", "getExtra / getFixed"),
    (r"多使用一张|使用次数上限|无距离限制", "TargetModSkill", "getResidueNum / getDistanceLimit"),
    (r"技能无效|技能失效", "InvaliditySkill", "isSkillValid"),
    (r"视为拥有技能", "ViewHasSkill", "ViewHas"),
]


def analyse(name, cn_name, desc, extra_keys=None, choices=None):
    """把一条技能的中文描述拆成要素表。返回 dict。"""
    desc = desc or ""
    notes = []
    extra_keys = extra_keys or {}
    choices = choices or {}

    # —— 频率与可选性 ——
    if re.search(r"锁定技", desc):
        frequency, optional = "Compulsory", False
    elif re.search(r"限定技|每局限一次", desc):
        frequency, optional = "Limited", True
    elif re.search(r"觉醒技", desc):
        frequency, optional = "Wake", True
    elif re.search(r"你须|必须", desc):
        frequency, optional = "Compulsory", False
    else:
        frequency, optional = "NotFrequent", bool(re.search(r"你可|你可以", desc))

    limit_note = None
    if re.search(r"每回合限一次", desc):
        limit_note = "每回合限一次 → 优先照抄同 package 现有技能（Skill::Limited 或自管 mark）"
    elif re.search(r"每阶段限一次", desc):
        limit_note = "每阶段限一次 → 自管 mark（##name），并在下一回合 NotActive 时清零"
    elif re.search(r"出牌阶段限一次", desc):
        limit_note = "出牌阶段限一次 → 技能卡形态用 !player->hasUsed(\"XxxCard\")；非技能卡用 Skill::Limited"

    # —— 触发时机 ——
    # 取"在描述里出现位置最靠前"的那个时机作为主时机（描述的习惯写法是先写时机），
    # 其余时机列出来提示可能需要拆成 `#` 前缀内部触发技。
    matched = []
    for pat, evts, base, kind in TIMING_RULES:
        m = re.search(pat, desc)
        if m:
            matched.append((m.start(), m.group(0), evts, base, kind))
    matched.sort(key=lambda x: x[0])

    events, timing_base, timing_hits, active = [], None, [], False
    extra_timings = []
    if matched:
        _pos, kw, evts, base, kind = matched[0]
        timing_hits.append(kw)
        if kind == "active":
            active = True
        else:
            events.extend(evts)
            timing_base = base
        for _p, kw2, evts2, _b2, kind2 in matched[1:]:
            if kw2 != kw and evts2 != events:
                extra_timings.append((kw2, evts2 if kind2 != "active" else ["（主动使用）"]))

    # —— 形态判定（优先级：规则修正 > 视为技 > 触发技 > 主动技） ——
    form, base, form_note = None, None, None
    for pat, cls, note in MODIFIER_RULES:
        if re.search(pat, desc):
            form, base, form_note = "规则修正", cls, note
            break
    if form is None:
        for pat, cls, note in VIEWAS_RULES:
            if re.search(pat, desc):
                form, base, form_note = "视为技", cls, note
                break
    if form is None and (events or timing_base):
        form = "触发技"
        base = timing_base or "TriggerSkill"
        form_note = "由时机触发 → %s" % base
    if form is None and active:
        form = "主动技"
        if re.search(r"弃置一张|弃置两张|弃一张|弃两张|失去\d*点体力|弃置.{0,4}牌", desc):
            base = "ViewAsSkill"
            form_note = "出牌阶段（主动）且需自选牌 / 失去体力作消耗 → ViewAsSkill（配 SkillCard 承载结算）"
        else:
            base = "ZeroCardViewAsSkill"
            form_note = "出牌阶段（主动）且不消耗牌 → ZeroCardViewAsSkill（配 SkillCard 承载结算）"
    if form is None:
        form = "待定"
        base = "TriggerSkill"
        form_note = "未匹配到明确的时机与形态关键词 → 需人工判读"

    # —— 技能卡判定 ——
    needs_skillcard = bool(re.search(r"选择一名其他角色|令一名其他角色|指定一名角色|选择一名角色", desc))
    if needs_skillcard and form == "视为技":
        form_note += "；需选目标 → 配 SkillCard（声明进 .h + addMetaObject）"
    elif needs_skillcard and form in ("主动技", "触发技"):
        form_note += "；需选目标且结算复杂 → 考虑 SkillCard"

    # —— 效果与牌操作 ——
    effects = []
    for pat, label in [(r"造成.{0,10}伤害", "伤害"), (r"回复体力|回复\d+点体力", "回复"),
                       (r"摸.{0,6}张牌", "摸牌"), (r"弃置|弃掉", "弃牌"),
                       (r"获得.{0,8}牌|交给", "获得/给牌"), (r"判定", "判定"),
                       (r"拼点", "拼点"), (r"改判", "改判"), (r"标记", "标记"),
                       (r"发动.{0,8}技能|视为拥有", "技能操作"), (r"翻面", "翻面")]:
        if re.search(pat, desc):
            effects.append(label)

    # —— 跨时点状态 ——
    cross_turn = bool(re.search(r"于此回合内|本回合内|回合结束前|直到回合结束", desc))
    inner_split = desc.count("▶") > 0 or bool(re.search(r"然后|其后", desc))
    if inner_split:
        notes.append("描述里出现 ▶ / 然后，可能含两个结算点 → 考虑拆成主技能 + `#` 前缀内部触发技")
    if extra_timings:
        notes.append("描述里还出现第二个时机：%s（事件 %s）→ 很可能需要拆成主技能 + `#` 前缀内部触发技"
                     % ("、".join(k for k, _ in extra_timings), " << ".join(extra_timings[0][1])))
    if cross_turn:
        notes.append("含「回合内持续」效果 → 用 room->addPlayerMark(player, \"##%s\") + record() 里归零" % name)
    if re.search(r"选择一项|选择：|任选一项", desc):
        notes.append("含「选择一项」 → 需要 askForChoice，AI 配 sgs.ai_skill_choice.%s" % name)
    if re.search(r"不能|禁止", desc) and form != "规则修正":
        notes.append("描述含「不能/禁止」，确认是否其实是 ProhibitSkill 形态")

    # —— AI hook 建议 ——
    ai_hooks = []
    # ai_skill_invoke 只在"由 cost() 里 askForSkillInvoke 询问"的形态下有意义：
    # 触发技与部分规则修正技。视为技 / 主动技（技能卡）走 getTurnUseCard，不经过这里。
    if optional and form in ("触发技", "规则修正"):
        ai_hooks.append(("sgs.ai_skill_invoke.%s" % name, "可选技必配，否则 AI 永不发动"))
    if re.search(r"选择一项|选择：", desc):
        ai_hooks.append(("sgs.ai_skill_choice.%s" % name, "askForChoice 的 reason 键"))
    if re.search(r"选择一名其他角色|令一名其他角色", desc):
        ai_hooks.append(("sgs.ai_skill_playerchosen.%s" % name, "askForPlayerChosen 的 reason 键"))
    if re.search(r"弃置", desc):
        ai_hooks.append(("sgs.ai_skill_discard.%s" % name, "askForDiscard 的 reason 键"))
    if re.search(r"拼点", desc):
        ai_hooks.append(("sgs.ai_skill_pindian.%s" % name, "askForPindian 的 reason 键"))
    if form == "视为技":
        ai_hooks.append(("sgs.ai_view_as.%s" % name, "视为技必配，否则 AI 完全不会用"))
    if needs_skillcard or form == "视为技":
        card = name[:1].upper() + name[1:] + "Card" if name else "XxxCard"
        ai_hooks.append(("sgs.ai_skills + getTurnUseCard", "让 AI 在出牌阶段想起使用"))
        ai_hooks.append(("sgs.ai_skill_use_func.%s" % card, "键是**类名**，不是技能名"))
        ai_hooks.append(("sgs.ai_use_value.%s" % card, "让 AI 正确评估价值"))

    return {
        "objectName": name,
        "cn_name": cn_name,
        "desc": desc,
        "extra_keys": extra_keys,
        "choices": choices,
        "optional": optional,
        "frequency": frequency,
        "limit": limit_note,
        "timing": timing_hits,
        "extra_timings": extra_timings,
        "events": events,
        "form": form,
        "base": base,
        "form_note": form_note,
        "needs_skillcard": needs_skillcard,
        "effects": effects,
        "cross_turn": cross_turn,
        "inner_split": inner_split,
        "ai_hooks": ai_hooks,
        "notes": notes,
    }


# --------------------------------------------------------------------------
# lang 文件解析
# --------------------------------------------------------------------------

# ["key"] = "value"   或   ["key"] = [[long]]
ENTRY_RE = re.compile(
    r'\[\s*"([^"]+)"\s*\]\s*=\s*(?:"((?:[^"\\]|\\.)*)"|\[\[(.*?)\]\]|([^,\n]+))',
    re.S)


def unescape(s):
    return s.replace('\\"', '"').replace("\\n", "\n") if s else s


def parse_text(text):
    """解析一段 lang 内容，返回 {skillname: analyse(...)} 与全部条目。"""
    entries = []          # (key, value, line)
    for m in ENTRY_RE.finditer(text):
        key = m.group(1)
        val = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
        entries.append({
            "key": key,
            "value": unescape(val) if val is not None else "",
            "line": text.count("\n", 0, m.start()) + 1,
        })

    by_key = {}
    for e in entries:
        by_key.setdefault(e["key"], e)

    # 技能判定：存在描述键 [":K"] 或询问键 ["@K"] / 指引键 ["~K"] 的 K 才算技能
    names = []
    for key in by_key:
        if key.startswith(("#", "@", "~", ":", "$")) or ":" in key:
            continue
        if (":" + key) in by_key or ("@" + key) in by_key or ("~" + key) in by_key:
            names.append(key)

    skills = {}
    for name in sorted(names):
        desc_entry = by_key.get(":" + name)
        extra = {}
        for e in entries:
            k = e["key"]
            if k == "@" + name or k.startswith("@" + name + "-"):
                extra.setdefault("@", []).append(e["value"])
            elif k == "~" + name:
                extra.setdefault("~", []).append(e["value"])
            elif k.startswith("#") and k.endswith("Buff"):
                extra.setdefault("#", []).append(e["value"])
        choices = {e["key"].split(":", 1)[1]: e["value"]
                   for e in entries if e["key"].startswith(name + ":")}
        cn_entry = by_key.get(name)
        skills[name] = analyse(
            name,
            cn_entry["value"] if cn_entry else "",
            desc_entry["value"] if desc_entry else "",
            extra_keys=extra,
            choices=choices,
        )
        skills[name]["line"] = desc_entry["line"] if desc_entry else (
            cn_entry["line"] if cn_entry else None)
    return skills, entries


def render_md(skills):
    out = []
    for name, s in skills.items():
        out.append("### %s —— %s" % (s["cn_name"] or "(无名)", name))
        if s.get("line"):
            out.append("")
            out.append("描述（第 %d 行）：%s" % (s["line"], s["desc"]))
        out.append("")
        out.append("| 要素 | 判定 |")
        out.append("|---|---|")
        out.append("| objectName | `%s` |" % name)
        out.append("| 形态 | %s |" % s["form"])
        out.append("| 建议基类 | `%s` |" % s["base"])
        out.append("| 可选性 | %s |" % ("可选（需 askForSkillInvoke）" if s["optional"] else "强制 / 锁定"))
        out.append("| 频率 | `Skill::%s` |" % s["frequency"])
        if s["timing"]:
            out.append("| 时机措辞 | %s |" % "、".join(s["timing"]))
        if s["events"]:
            out.append("| 事件 | `%s` |" % " << ".join(s["events"]))
        out.append("| 效果 | %s |" % ("、".join(s["effects"]) or "—"))
        out.append("| 需技能卡 | %s |" % ("是" if s["needs_skillcard"] else "否"))
        out.append("")
        out.append("形态说明：%s" % s["form_note"])
        if s["limit"]:
            out.append("")
            out.append("频率实现：%s" % s["limit"])
        if s["choices"]:
            out.append("")
            out.append("选项串（`[" + name + ":xxx]`）：%s" % "、".join(s["choices"]))
        if s["ai_hooks"]:
            out.append("")
            out.append("需要的 AI hook：")
            out.append("")
            out.append("| hook | 说明 |")
            out.append("|---|---|")
            for h, why in s["ai_hooks"]:
                out.append("| `%s` | %s |" % (h, why))
        if s["notes"]:
            out.append("")
            out.append("注意：")
            for n in s["notes"]:
                out.append("- %s" % n)
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def collect_files(root, target=None):
    if target:
        return [target]
    files = []
    base = os.path.join(root, "lang", "zh_CN")
    for dirpath, _d, filenames in os.walk(base):
        for fn in filenames:
            if fn.endswith(".lua"):
                files.append(os.path.join(dirpath, fn))
    return sorted(files)


def find_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, "QSanguosha.pro")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser(description="lang/zh_CN 技能条目解析器")
    ap.add_argument("file", nargs="?", help="lang 文件路径")
    ap.add_argument("--snippet", help="lang 片段文件（无需是合法 lua 表）")
    ap.add_argument("--skill", help="只输出该技能")
    ap.add_argument("--root", help="项目根（用于 --list 与路径解析）", default=None)
    ap.add_argument("--list", action="store_true", help="列出全部技能名")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    target = args.snippet or args.file
    if not target and not args.list:
        ap.print_help()
        return 2

    root = args.root or find_root(os.getcwd())

    if args.list:
        if not root:
            print("错误：未找到项目根，请用 --root 指定", file=sys.stderr)
            return 2
        total = 0
        for f in collect_files(root):
            skills, _ = parse_text(read(f))
            if not skills:
                continue
            rel = os.path.relpath(f, root).replace("\\", "/")
            print("%s  (%d)" % (rel, len(skills)))
            for name in skills:
                print("    %-28s %s" % (name, skills[name]["cn_name"]))
            total += len(skills)
        print()
        print("合计 %d 个技能" % total)
        return 0

    if not os.path.isfile(target):
        print("错误：文件不存在 %s" % target, file=sys.stderr)
        return 2

    text = read(target)
    if text.startswith("\ufeff"):
        text = text[1:]
    skills, entries = parse_text(text)

    if args.skill:
        if args.skill not in skills:
            print("错误：在 %s 里没有解析到技能 \"%s\"" % (target, args.skill), file=sys.stderr)
            cand = ", ".join(sorted(skills)[:20]) or "（无）"
            print("该文件解析到的技能：%s" % cand, file=sys.stderr)
            return 1
        skills = {args.skill: skills[args.skill]}

    if args.json:
        print(json.dumps({
            "file": os.path.abspath(target),
            "skill_count": len(skills),
            "entry_count": len(entries),
            "skills": skills,
        }, ensure_ascii=False, indent=2))
        return 0

    print("文件：%s" % os.path.abspath(target))
    print("解析到 %d 个技能，%d 条 lang 条目" % (len(skills), len(entries)))
    print()
    if not skills:
        print("（没有识别到技能条目：技能的判定条件是同时存在 [\"K\"] 与 [\":K\"]，或 [\"@K\"]/[\"~K\"]）")
        return 0
    print(render_md(skills))
    return 0


if __name__ == "__main__":
    sys.exit(main())
