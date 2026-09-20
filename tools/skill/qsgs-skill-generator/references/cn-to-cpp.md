# 中文技能文案 → 技能要素 拆解规则

本文件是第 1 步的依据。目标是把一段中文技能描述拆成一组**可机械映射到代码**的要素。

## 一、拆解产出表

对每条技能，先填出这张表再写代码：

| 字段 | 取值 |
|---|---|
| objectName | 小写拼音 |
| 触发时机 | 见下第二节 |
| 触发主体 | 自己 / 一名角色 / 其他角色 / 全场 |
| 可选性 | 可选 / 强制（锁定技） |
| 频率 | 无限制 / 每回合限一次 / 每阶段限一次 / 每局限一次（限定技）/ 觉醒技 |
| 目标 | 无 / 一名其他角色 / 至多 N 名 / 由玩家指定 |
| 牌操作 | 无 / 弃置 / 选择 / 交给 / 获得 / 视为使用 |
| 效果 | 伤害 / 回复 / 摸牌 / 弃牌 / 获得牌 / 判定 / 拼点 / 改判 / 标记 |
| 特殊形态 | 视为技 / 技能卡 / 纯规则修正 / 内部触发技（`#`） |

## 二、触发时机关键词 → TriggerEvent

事件枚举在 `src/core/structs.h`。按中文措辞对照：

| 中文措辞 | TriggerEvent | 备注 |
|---|---|---|
| 当你受到伤害后 | `Damaged` | 用 `MasochismSkill`，事件由基类自动挂，不要手写 |
| 当你造成伤害后 | `Damage` | |
| 一名角色受到伤害后 | `Damaged` | 用 `TriggerSkill`，`triggerable` 里自行判断主体 |
| 你即将造成伤害时 | `DamageCaused` | 改伤害数值用这个（见 `LuoyiDamage`） |
| 伤害结算开始时 | `DamageForseen` | |
| 你进入濒死状态时 | `Dying` | 也有 `QuitDying` |
| 一名角色死亡后 | `Death` / `DeathFinished` | `Death` 早于死亡结算，`DeathFinished` 在其后 |
| 摸牌阶段 | `EventPhaseStart` + `Player::Draw` | 或改摸牌数用 `DrawCardsSkill` |
| 摸牌阶段结束时 | `EventPhaseEnd` + `Player::Draw` | 见 `Luoyi` |
| 出牌阶段开始时 | `EventPhaseStart` + `Player::Play` | |
| 出牌阶段结束时 | `EventPhaseEnd` + `Player::Play` | |
| 弃牌阶段结束时 | `EventPhaseEnd` + `Player::Discard` | |
| 回合开始时 | `TurnStart` | |
| 回合结束时 | `EventPhaseStart` + `Player::NotActive` | 本项目惯例，见 `Luoyi::record` |
| 回合结束后 | `EventPhaseEnd` + `Player::NotActive` | |
| 判定牌生效前 | `AskForRetrial` | 改判类技能 |
| 判定结果确定后 | `FinishRetrial` / `FinishJudge` | |
| 拼点时 | `PindianVerifying` | 比点前改判用 |
| 拼点结束后 | `Pindian` | |
| 一名角色使用牌时 | `PreCardUsed` / `CardUsed` | `Pre` 早于结算 |
| 一张牌指定目标后 | `TargetChosen` / `TargetConfirmed` | |
| 一张牌结算完成后 | `CardFinished` | |
| 一名角色响应后 | `CardResponded` | |
| 游戏开始时 | `GameStart` | 用 `GameStartSkill` |
| 你翻面/横置/移出游戏状态改变时 | `TurnedOver` / `ChainStateChanged` / `RemoveStateChanged` | |
| 一名角色获得/失去技能时 | `EventAcquireSkill` / `EventLoseSkill` | |
| 一名角色的体力值变化时 | `HpChanged` / `PreHpLost` / `PreHpRecover` | |
| 一名角色的手牌上限变化时 | `MaxHpChanged` | |
| 牌移动时 | `BeforeCardsMove` / `CardsMoveOneTime` | 干涉移动用 `BeforeCardsMove` |
| 确认伤害数值与属性时 | `ConfirmDamage` | |

**同时挂多个事件**是常态：写 `events << A << B << C;`，在 `triggerable` 里用 `if (triggerEvent == A)` 分支，见 `Luoyi`。

## 三、措辞 → 可选性 / 频率

| 中文措辞 | frequency | cost() 写法 |
|---|---|---|
| 你可以…… / 你可…… | `Skill::NotFrequent`（默认） | 需要 `askForSkillInvoke` |
| 你须…… / 锁定技 | `Skill::Compulsory` | 不做询问，直接 true |
| 限定技：每局限一次 | `Skill::Limited` | 需要询问 |
| 觉醒技 | `Skill::Wake` | 有觉醒条件判断 |
| 每回合限一次 | `Skill::Limited` 或自管 mark | 见下 |

**"每回合限一次"的两种实现**：项目里用 `Skill::Limited` 由框架管；但很多武将技用 `player->hasUsed("XxxCard")`（技能卡）或自管 mark（`room->addPlayerMark(player, "##skillname")`）来限制。选哪种取决于是否跨玩家、是否要重置——**优先照抄同 package 内语义最接近的现有技能**。

**"每阶段限一次"** 一律自管 mark，并在下一回合（`EventPhaseStart` + `NotActive`）清零。

## 四、跨时点的"回合内持续"效果

描述形如"当你于此回合内……则……"时：

1. 在发动时 `room->addPlayerMark(player, "##skillname");`（`##` 前缀是私有标记，不进客户端 UI）
2. 效果由另一个 `#` 前缀的内部触发技负责（如 `#luoyi-damage`），其 `triggerable` 检查 `player->getMark("##luoyi") > 0`
3. 在 `record()` 里，`triggerEvent == EventPhaseStart && player->getPhase() == Player::NotActive` 时把标记归零

完整实例见 `references/examples.md` 的裸衣。

## 五、"视为技"的识别

| 中文措辞 | 基类 | 关键成员 |
|---|---|---|
| 你可以将一张<颜色/花色>牌当【X】使用或打出 | `OneCardViewAsSkill` | `filter_pattern`、`response_pattern`、`response_or_use`、`viewAs(const Card *)` |
| 你可以将任意张牌当【X】使用 | `ViewAsSkill` | `viewFilter(selected, to_select)`、`viewAs(cards)` |
| 出牌阶段限一次，你可以……视为使用一张【X】（不带牌） | `ZeroCardViewAsSkill` | `isEnabledAtPlay`、`viewAs()` |
| ……视为使用一张【X】，且需指定目标 | 上述之一 + `SkillCard` | 见第六节 |

在 `viewAs` 里构造牌时**三件事都不能少**：

```cpp
Jink *jink = new Jink(originalCard->getSuit(), originalCard->getNumber());
jink->setSkillName(objectName());
jink->addSubcard(originalCard->getId());
jink->setShowSkill(objectName());
return jink;
```

## 六、技能卡（SkillCard）

中文描述里出现"你可以对一名角色……"并且需要选目标、或效果无法用一把牌表达时，用 `SkillCard`：

- 声明在 `.h`，`Q_OBJECT` + `Q_INVOKABLE XxxCard();`
- 覆写 `targetFilter(targets, to_select, Self)` 表达目标合法性
- 覆写 `onEffect(const CardEffectStruct &effect)` 写结算
- 需要额外消耗时覆写 `extraCost(room, card_use)`
- 承载它的技能是 `ViewAsSkill` / `ZeroCardViewAsSkill`，`viewAs` 里 `new XxxCard`、`card->setShowSkill(objectName())`
- AI 侧用 `sgs.Card_Parse("@XxxCard=.&skillname")` 构造

实例：`Qiangxi`+`QiangxiCard`、`Quhu`+`QuhuCard`（`references/examples.md`）。

## 七、易错点

- **"一名角色"不要直接当成 `self.player`**，要在 `triggerable` 里用 `player` 判断是谁。
- **`effect()` 返回 `true` 会中断结算链**，除非确实要阻止后续（如 `LuoyiDamage` 里改完伤害仍需 `return false`）。
- **数值改动的时机**：改伤害值必须在 `DamageCaused`/`ConfirmDamage`，改完要 `data = QVariant::fromValue(damage);` 写回，否则不生效。
- **`askForSkillInvoke(this, data)` 的第二个参数**是可选的 `QVariant` 上下文，有就用（AI 的 `ai_skill_invoke` 会收到它）。
- **`broadcastSkillInvoke(objectName(), player)`** 放在玩家确认发动之后，用于播放语音（语音在 `lang/zh_CN/Audio/<Package>Lines.lua` 里以 `$skillname1` 定义）。
