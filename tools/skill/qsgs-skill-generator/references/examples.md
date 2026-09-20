# 端到端实例对照

四个实例覆盖了绝大多数技能形态。写代码前先找到形态最接近的一个，照它的骨架改写。

---

## 例 1：奸雄 —— 受虐技 + 可选（最简单形态）

**中文描述**：当你受到伤害后，你可获得是此伤害的渠道的牌对应的所有实体牌。

**① lang** —— `lang/zh_CN/Package/StandardWeiGeneral.lua`

```lua
["jianxiong"] = "奸雄",
[":jianxiong"] = "当你受到伤害后，你可获得是此伤害的渠道的牌对应的所有实体牌。",
```

**② C++** —— `src/package/standard-wei-generals.cpp`（无需 Q_OBJECT，直接写 .cpp）

```cpp
class Jianxiong : public MasochismSkill
{
public:
    Jianxiong() : MasochismSkill("jianxiong")
    {
        frequency = Frequent;
    }

    virtual QStringList triggerable(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer * &) const
    {
        if (MasochismSkill::triggerable(player)) {
            DamageStruct damage = data.value<DamageStruct>();
            const Card *card = damage.card;
            if (damage.card == NULL)
                return QStringList();

            QList<int> table_cardids = room->getCardIdsOnTable(card);

            return (table_cardids.length() != 0 && card->getSubcards() == table_cardids) ? QStringList(objectName()) : QStringList();
        }
        return QStringList();
    }

    virtual bool cost(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer *) const
    {
        if (player->askForSkillInvoke(this, data)) {
            room->broadcastSkillInvoke(objectName(), player);
            return true;
        }
        return false;
    }

    virtual void onDamaged(ServerPlayer *player, const DamageStruct &damage) const
    {
        player->obtainCard(damage.card);
    }
};
```

**要点**：
- `MasochismSkill` 自动挂 `Damaged`，**构造函数里不写 `events <<`**。
- 受虐技用 `onDamaged` 而非 `effect`。
- 构造函数与类名同名，写成 `Jianxiong() : MasochismSkill("jianxiong")`。

**③ AI** —— `lua/ai/standard-wei-ai.lua`

```lua
--曹操
sgs.ai_skill_invoke.jianxiong = function(self, data)
	if sgs.GetConfig("EnableLordConvertion", true) and self.player:getMark("Global_RoundCount") <= 1
	and not self.player:hasShownGeneral1() and self.player:inHeadSkills("jianxiong") and not self:isWeak() then--君主
		return false
	end
	if not self:willShowForMasochism() then return false end
	if self.get_AOE_subcard then self.get_AOE_subcard = nil return true end
	return not self:needKongcheng(self.player, true)
end
```

---

## 例 2：裸衣 —— 主技能 + 内部触发技 + 回合内标记

**中文描述**：摸牌阶段结束时，你可弃置一张牌▶当你于此回合内因执行【杀】或【决斗】的效果而对一名角色造成伤害时，你令伤害值+1。

这条描述里有两个结算点，所以拆成**两个技能**：`luoyi`（可选，负责弃牌并打标记）+ `#luoyi-damage`（强制内部技，负责加伤害）。

**① lang**

```lua
["luoyi"] = "裸衣",
[":luoyi"] = "摸牌阶段结束时，你可弃置一张牌▶当你于此回合内因执行【杀】或【决斗】的效果而对一名角色造成伤害时，你令伤害值+1。",
["#LuoyiBuff"] = "%from 的“<font color=\"yellow\"><b>裸衣</b></font>”效果被触发，伤害从 %arg 点增加至 %arg2 点",
["@luoyi"] = "是否使用“裸衣”，选择一张牌弃置",
```

**② C++**

```cpp
class Luoyi : public TriggerSkill
{
public:
    Luoyi() : TriggerSkill("luoyi")
    {
        events << EventPhaseEnd << PreCardUsed << EventPhaseStart;
    }

    // 回合切换时清空私有标记
    virtual void record(TriggerEvent triggerEvent, Room *room, ServerPlayer *player, QVariant &) const
    {
        if (triggerEvent == EventPhaseStart) {
            if (player->getPhase() == Player::NotActive) {
                QList<ServerPlayer *> allplayers = room->getAlivePlayers();
                foreach (ServerPlayer *p, allplayers) {
                    room->setPlayerMark(p, "##luoyi", 0);
                }
            }
        }
    }

    virtual QStringList triggerable(TriggerEvent triggerEvent, Room *, ServerPlayer *player, QVariant &, ServerPlayer * &) const
    {
        if (triggerEvent == EventPhaseEnd) {
            if (TriggerSkill::triggerable(player) && player->getPhase() == Player::Draw && !player->isNude())
                return QStringList(objectName());
        }
        return QStringList();
    }

    virtual bool cost(TriggerEvent, Room *room, ServerPlayer *player, QVariant &, ServerPlayer *) const
    {
        // 注意：本技的"弃牌"由 cost 内部直接完成，而不是通过参数返回给框架
        if (room->askForDiscard(player, objectName(), 1, 1, true, true, "@luoyi", true)) {
            room->broadcastSkillInvoke(objectName(), player);
            return true;
        }
        return false;
    }

    virtual bool effect(TriggerEvent, Room *room, ServerPlayer *player, QVariant &, ServerPlayer *) const
    {
        room->addPlayerMark(player, "##luoyi");
        return false;
    }
};

class LuoyiDamage : public TriggerSkill
{
public:
    LuoyiDamage() : TriggerSkill("#luoyi-damage")
    {
        events << DamageCaused;
        frequency = Skill::Compulsory;
    }

    virtual QStringList triggerable(TriggerEvent, Room *, ServerPlayer *player, QVariant &data, ServerPlayer * &) const
    {
        if (player != NULL && player->isAlive() && player->getMark("##luoyi") > 0) {
            DamageStruct damage = data.value<DamageStruct>();
            if (damage.card != NULL && (damage.card->isKindOf("Slash") || damage.card->isKindOf("Duel"))
                    && !damage.chain && !damage.transfer) {
                return QStringList(objectName());
            }
        }
        return QStringList();
    }

    virtual bool effect(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer *) const
    {
        DamageStruct damage = data.value<DamageStruct>();
        LogMessage log;
        log.type = "#LuoyiBuff";
        log.from = player;
        log.to << damage.to;
        log.arg = QString::number(damage.damage);
        log.arg2 = QString::number(++damage.damage);
        room->sendLog(log);

        data = QVariant::fromValue(damage);   // 必须写回，否则数值不生效

        return false;
    }
};
```

注册：

```cpp
xuchu->addSkill(new Luoyi);
xuchu->addSkill(new LuoyiDamage);
```

**要点**：
- `#` 前缀名 `#luoyi-damage` 不出现在武将牌上；`objectName()` 返回的正是这个带 `#` 的字符串。
- 改伤害数值后**必须** `data = QVariant::fromValue(damage);`。
- 回合内有效状态用 `##` 私有标记 + `record()` 里归零。

**③ AI** —— `lua/ai/standard-wei-ai.lua`

```lua
sgs.ai_skill_discard.luoyi = function(self, discard_num, min_num, optional, include_equip)
	if self.player:isSkipped(sgs.Player_Play) then return {} end
	-- ……（按敌方血量、手上杀/决斗数量判断裸衣是否划算，完整实现见仓库）
		--self:speak("luoyi")
		return self:askForDiscard("dummy_reason", discard_num, min_num, false, true)
	end
	return {}
end

function sgs.ai_cardneed.luoyi(to, card, self)
	return to:getCards("h"):length() < 2 and card:isKindOf("Slash")   -- 示意，实际见仓库
end

sgs.luoyi_keep_value = {
	Peach           = 6,
	Analeptic       = 5.8,
	Jink            = 5.2,
	Duel            = 5.5,
	FireSlash       = 5.6,
	Slash           = 5.4,
}
```

**要点**：`cost()` 里自己调 `askForDiscard` 时，AI 走的是 `sgs.ai_skill_discard[reason]`，`reason` 就是 `objectName()` → `luoyi`。

---

## 例 3：倾国 —— 一张牌视为技

**中文描述**：你可将一张黑色手牌当【闪】使用或打出。

**① lang**

```lua
["qingguo"] = "倾国",
[":qingguo"] = "你可将一张黑色手牌当【闪】使用或打出。",
```

**② C++**

```cpp
class Qingguo : public OneCardViewAsSkill
{
public:
    Qingguo() : OneCardViewAsSkill("qingguo")
    {
        filter_pattern = ".|black|.|hand";
        response_pattern = "jink";
        response_or_use = true;
    }

    virtual const Card *viewAs(const Card *originalCard) const
    {
        Jink *jink = new Jink(originalCard->getSuit(), originalCard->getNumber());
        jink->setSkillName(objectName());
        jink->addSubcard(originalCard->getId());
        jink->setShowSkill(objectName());
        return jink;
    }
};
```

**要点**：`OneCardViewAsSkill` 不用写 `viewFilter`；用 `filter_pattern` 声明可选的牌。`viewAs` 里四步（构造牌 → `setSkillName` → `addSubcard` → `setShowSkill`）都不能省。

**③ AI**

```lua
sgs.ai_view_as.qingguo = function(card, player, card_place)
	local suit = card:getSuitString()
	local number = card:getNumberString()
	local card_id = card:getEffectiveId()
	if card:isBlack() and (card_place == sgs.Player_PlaceHand or player:getHandPile():contains(card_id)) then
		return ("jink:qingguo[%s:%s]=%d&qingguo"):format(suit, number, card_id)
	end
end

function sgs.ai_cardneed.qingguo(to, card)
	return to:getCards("h"):length() < 2 and card:isBlack()
end

sgs.qingguo_suit_value = {
	spade = 4.1,
	club = 4.2
}

sgs.ai_suit_priority.qingguo = "diamond|heart|club|spade"
```

**要点**：返回字符串的格式是 `"卡牌类名小写:技能名[花色:点数]=牌id&技能名"`。**AI 不写 `ai_view_as`，技能就完全不会被 AI 使用**——这是视为技最常见的"AI 不会用"根因。

---

## 例 4：驱虎 —— 技能卡 + owner 无关的零牌视为技

**中文描述**：出牌阶段限一次，你可与一名体力值大于你的角色拼点。若你：赢，其对其攻击范围内你选择的一名角色造成1点普通伤害；未赢，其对你造成1点普通伤害。

**① lang**

```lua
["quhu"] = "驱虎",
[":quhu"] = "出牌阶段限一次，你可与一名体力值大于你的角色拼点。若你：赢，其对其攻击范围内你选择的一名角色造成1点普通伤害；未赢，其对你造成1点普通伤害。",
["@quhu-damage"] = "请选择 %src 攻击范围内的一名角色",
```

**② C++** —— 技能卡声明在 `.h`

```cpp
// standard-wei-generals.h
class QuhuCard : public SkillCard
{
    Q_OBJECT

public:
    Q_INVOKABLE QuhuCard();
    virtual bool targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const;
    virtual void onEffect(const CardEffectStruct &effect) const;
};
```

```cpp
// standard-wei-generals.cpp
QuhuCard::QuhuCard()
{
}

bool QuhuCard::targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const
{
    return targets.isEmpty() && to_select->getHp() > Self->getHp() && Self->canPindianTo(to_select);
}

void QuhuCard::onEffect(const CardEffectStruct &effect) const
{
    if (effect.from->canPindianTo(effect.to)) {
        bool success = effect.from->pindian(effect.to, "quhu");
        Room *room = effect.to->getRoom();
        if (success) {
            QList<ServerPlayer *> players = room->getOtherPlayers(effect.to), wolves;
            foreach (ServerPlayer *player, players) {
                if (effect.to->inMyAttackRange(player))
                    wolves << player;
            }

            if (wolves.isEmpty()) {
                LogMessage log;
                log.type = "#QuhuNoWolf";
                log.from = effect.from;
                log.to << effect.to;
                room->sendLog(log);
                return;
            }

            ServerPlayer *wolf = room->askForPlayerChosen(effect.from, wolves, "quhu", QString("@quhu-damage:%1").arg(effect.to->objectName()));
            room->damage(DamageStruct("quhu", effect.to, wolf));
        } else {
            room->damage(DamageStruct("quhu", effect.to, effect.from));
        }
    }
}

class Quhu : public ZeroCardViewAsSkill
{
public:
    Quhu() : ZeroCardViewAsSkill("quhu")
    {
    }

    virtual bool isEnabledAtPlay(const Player *player) const
    {
        return !player->hasUsed("QuhuCard") && !player->isKongcheng();
    }

    virtual const Card *viewAs() const
    {
        QuhuCard *card = new QuhuCard;
        card->setShowSkill(objectName());
        return card;
    }
};
```

注册（技能卡必须登记元对象）：

```cpp
// StandardPackage 构造函数中
addMetaObject<QuhuCard>();
// addWeiGenerals() 中
xunyu->addSkill(new Quhu);
```

**要点**：
- 技能卡**必须**在 `.h` 里带 `Q_OBJECT` + `Q_INVOKABLE`，否则运行期解析不到。
- 通过 `player->hasUsed("QuhuCard")` 实现"出牌阶段限一次"，因为限制以牌为单位。
- `askForPlayerChosen(..., "quhu", ...)` 的第二参是 reason，AI 侧对应 `sgs.ai_skill_playerchosen.quhu`。

**③ AI**

```lua
local quhu_skill = {}
quhu_skill.name = "quhu"
table.insert(sgs.ai_skills, quhu_skill)
quhu_skill.getTurnUseCard = function(self)
	if self:willShowForAttack() and not self.player:hasUsed("QuhuCard") and not self.player:isKongcheng() then
		return sgs.Card_Parse("@QuhuCard=.&quhu")
	end
end

sgs.ai_skill_use_func.QuhuCard = function(QHCard, use, self)
	if #self.enemies == 0 then return end
	local max_card = self:getMaxNumberCard()
	local max_point = max_card:getNumber()
	-- ……（比较点数、选择敌方、设置 use.card / use.to，完整实现见仓库）
end
```

**要点**：
- `sgs.ai_skills` 的条目让 AI 在出牌阶段"想起"这个技能。
- `sgs.ai_skill_use_func` 的键是**类名** `QuhuCard`（C++ 技能卡走 `card:getClassName()`；Lua 技能卡走 `"#" .. card:objectName()`）。
- 决策通过写 `use.card` 与 `use.to`（一个 SPlayerList）表达。

---

## 形态速查

| 描述形态 | 照抄哪个例子 |
|---|---|
| 当你受到伤害后，你可…… | 例 1 奸雄 |
| 某阶段结束时你可……，且效果持续到回合结束 | 例 2 裸衣（主技 + `#` 内部技） |
| 你可将一张 XX 牌当【X】使用或打出 | 例 3 倾国 |
| 出牌阶段限一次，你可……（需选目标 / 复杂结算） | 例 4 驱虎 |
| 改距离 / 改手牌上限 / 禁止用牌 | 见 `skill-classes.md` 的规则修正型，直接实现对应纯虚函数即可 |
