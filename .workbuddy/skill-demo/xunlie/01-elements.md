# 第 1 步产物：中文文案 → 技能要素表

输入：`00-input.lang.lua` 的 `[":xunlie"]` 描述文本
依据：`references/cn-to-cpp.md` 第一至六节

| 字段 | 判定 | 依据（描述中的原话） |
|---|---|---|
| objectName | `xunlie` | lang 键 `["xunlie"]` |
| 形态 | **技能卡（SkillCard）** + 承载它的视为技 | "令一名其他角色选择一项……" 需选目标 + 结算复杂，一把牌表达不了 → 第六节 |
| 承载基类 | `ViewAsSkill` | 消耗"一张牌"且该牌进入弃牌堆，需 `viewFilter`/`viewAs` 参与选牌 |
| 触发时机 | 主动（出牌阶段） | 无"当……时/后"→ 不是 TriggerSkill 族 |
| 可选性 | 可选 | "你可弃置……" → 需 `askForSkillInvoke` 语义（视为技由框架询问） |
| 频率 | 出牌阶段限一次 → `!player->hasUsed("XunlieCard")` | "出牌阶段限一次"，且限制以技能卡为单位 |
| 触发主体 | 自己 | —— |
| 目标 | 一名其他角色 | `targetFilter`：`targets.isEmpty() && to_select != Self` |
| 牌操作 | 弃置一张牌（自己 → 弃牌堆） | "你可弃置一张牌" → `extraCost` + `SkillCard::extraCost` |
| 效果 | 分叉：目标弃置一张牌 / 受到 1 点普通伤害 | "选择一项" → `room->askForChoice` |
| 询问方 | **目标**（不是技能拥有者） | "令一名其他角色选择一项" → `askForChoice(effect.to, ...)` |
| 跨时点状态 | 无 | 描述里没有"于此回合内"类措辞 → 不需要 `##` 标记与 `record()` 归零 |

## 事件挂载

无。本技能不是触发技，`Xunlie` 是视为技、`XunlieCard` 是技能卡，都不写 `events <<`。

## 频率核实

"出牌阶段限一次" + 有技能卡 → 走 `player->hasUsed("XunlieCard")`（`cn-to-cpp.md` 第三节列出的两种实现中的前者）。
理由：限制的粒度是"这张技能卡",不是"这个技能名"；仓库同形态对照物 `Qiangxi`（强袭）、`Shangyi`（尚义）都这么做。

## 对照物

| 本技能要素 | 仓库内同形态技能 | 照抄点 |
|---|---|---|
| 出牌阶段限一次 + 一张牌作消耗 + SkillCard | `Qiangxi`（强袭） | `ViewAsSkill` 的 `viewFilter`/`viewAs`/`isEnabledAtPlay` 三件套、`SkillCard::extraCost` 收尾 |
| 技能卡选目标 + `extraCost` + `askForChoice` | `Shangyi`（尚义） | 技能卡声明进 `.h`、`addMetaObject` 登记、`askForChoice` 的 prompt 写法 |

## 需要 AI 覆盖的 hook（推导自第 5 步规则）

| hook | 为什么需要 |
|---|---|
| `sgs.ai_skills` + `getTurnUseCard` | 技能卡必须让 AI 在出牌阶段"想起"它，否则永不使用 |
| `sgs.ai_skill_use_func.XunlieCard` | 键是**类名**；负责选目标、构造 `use.card` |
| `sgs.ai_skill_choice.xunlie` | 技能里有 `askForChoice(reason="xunlie")` |
| `sgs.ai_skill_discard.xunlie` | 技能里有 `askForDiscard(reason="xunlie")` |
| `sgs.ai_use_value` / `ai_card_intention` / `dynamic_value` | 让 AI 正确评估这张技能卡的价值与敌对度 |
