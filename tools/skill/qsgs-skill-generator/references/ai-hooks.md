# Lua AI hook 全表

所有 hook 都是往 `sgs` 表上挂的名字。分发逻辑在 `lua/ai/smart-ai.lua`（下文行号以本仓库当前版本为准）。

## 一、核心分发（写 AI 必读）

| hook | 分发位置 | 键 | 函数签名 | 返回 |
|---|---|---|---|---|
| `sgs.ai_skill_invoke` | `SmartAI:askForSkillInvoke` L2671 | **技能 objectName** | `(self, data)` | `true` 发动 / `false` 放弃；也可直接赋 `true`/`false` 常量 |
| `sgs.ai_skill_choice` | `SmartAI:askForChoice` L2697 | **技能 objectName** | `(self, choices, data)` | 选项字符串；也可直接赋常量字符串 |
| `sgs.ai_skill_exchange` | `SmartAI:askForExchange` L2715 | `reason` | `(self, pattern, max_num, min_num, expand_pile)` | 数字或数字表 |
| `sgs.ai_skill_discard` | `SmartAI:askForDiscard` L2733 | `reason` | `(self, discard_num, min_num, optional, include_equip)` | 牌 id 或 id 表 |
| `sgs.ai_skill_movecards` | `SmartAI:askForMoveCards` L2826 | `reason` | `(self, upcards, downcards, min_num, max_num)` | `(top, down)` 两张表 |
| `sgs.ai_skill_cardchosen` | `SmartAI:askForCardChosen` L3187 | `reason` | `(self, who, flags, method, disable_list)` | 牌 id 或 Card |
| `sgs.ai_skill_cardask` | `SmartAI:askForCard` L3463 | **prompt 的 `:` 前第一段** | `(self, data, pattern, target, target2, arg, arg2)` | 卡牌字符串；返回 `"."` 表示拒绝 |
| `sgs.ai_skill_askforag` | `SmartAI:askForAG` L3522 | `reason` | `(self, card_ids)` | 牌 id |
| `sgs.ai_skill_pindian` | `SmartAI:askForPindian` L4023 | `reason` | `(minusecard, self, requestor, maxcard, mincard)` | 牌 |
| `sgs.ai_skill_playerchosen` | `SmartAI:askForPlayersChosen` L4060 | `reason` | `(self, targets, max_num, min_num)` | ServerPlayer / ClientPlayer / 表 |
| `sgs.ai_skill_suit` | `SmartAI:askForSuit` L2665 | `reason` | `(self)` | 0–3 的数字 |
| `sgs.ai_need_damaged` | L1401、L4467 | **技能 objectName** | `(self, from, to)` | bool，表示"我乐意承受这份伤害" |

### 键名归一化（关键坑）

- `askForSkillInvoke`：查表前会把技能名里的 `-` 全部替换为 `_`（L2672）。所以技能 `xxx-yyy` 的 AI 写成 `sgs.ai_skill_invoke.xxx_yyy`。
- `askForCardChosen` / `askForAG` / `askForPlayersChosen`：同样把 `reason` 里的 `-` 替换为 `_`。
- `ai_skill_invoke` 如果**既不是函数也不是布尔**，会退回：`Frequent` 技能返回 true，其余返回 nil（=不发动）。所以可选技不写 AI = 永远不发动。

## 二、主动使用（出牌阶段）

| hook | 用途 | 签名 |
|---|---|---|
| `sgs.ai_skills`（数组） | 让 AI 主动想起"使用"某技能。元素形如 `{name = "quhu", getTurnUseCard = function(self, has_no_card) ... end}` | 用 `table.insert(sgs.ai_skills, t)` 追加；`getTurnUseCard` 返回用 `sgs.Card_Parse("@QuhuCard=.&quhu")` 构造的卡，不需要时返回 nil |
| `sgs.ai_skill_use_func` | **技能卡**的具体使用策略 | 键为 SkillCard 的**类名**（`QuhuCard`）；`(QHCard, use, self)`，通过设置 `use.card` 与 `use.to` 表达决策 |
| `sgs.ai_skill_use` | 按 `@@pattern` 分发的通用使用策略 | 键为 `"@@xxx"`；`(self, prompt, method)`，返回卡牌字符串。也支持 `"@@xxx1"`、`"@@xxx2"` 这种多分支命名 |
| `sgs.ai_view_as` | **视为技**：判定一张牌能否被当作用某技能转化 | 键为技能名；`(card, player, card_place, class_name)`，返回 `"jink:qingguo[suit:number]=id&qingguo"` 形式字符串或 nil |
| `sgs.ai_use_priority` | 卡牌使用优先级（越大越优先） | `sgs.ai_use_priority[ClassName] = 9.2` |
| `sgs.ai_use_value` | 卡牌使用价值 | `sgs.ai_use_value[ClassName] = 10` |
| `sgs.ai_cardneed` | 判断队友是否需要某张牌（用于给牌策略） | 键为技能名；`(friend, card, self)` → bool |
| `sgs.ai_card_intention` | 对目标造成的"意图值"（正值=敌对行为） | 键为卡牌类名；`(to, level)` 或数字 |
| `sgs.ai_playerchosen_intention` | 选人行为的意图值 | `sgs.ai_playerchosen_intention[reason] = number 或 function(from, to, level)` |
| `sgs.ai_choicemade_filter` | 对某类询问的**已做出的选择**做修正（不是替玩家选，而是选完后补记状态，常用于把"看过的手牌/武将"记下来） | 两级键：`sgs.ai_choicemade_filter.<询问类型>.<键>`，签名 `(self, player, promptlist)` |

`ai_choicemade_filter` 的完整询问类型（`smart-ai.lua` L84–L96 的表定义，写错类型等于不生效）：

| 询问类型 | 分发方式 | 第二级键 |
|---|---|---|
| `cardUsed` | `ipairs` 遍历数组，**用 `table.insert` 追加** | 无（数组元素） |
| `cardResponded` | 按键索引，index=3 | 牌名 / `general` |
| `skillInvoke` | 按键索引，index=2 | 技能名 / `general` |
| `skillChoice` | 按键索引，index=2 | 技能名 / `general` |
| `cardChosen` | 按键索引，index=2 | 技能名 / `general` |
| `playerChosen` | 按键索引，index=2 | 技能名 / `general` |
| `pindian` | 按键索引，index=2 | 技能名 / `general` |
| `Nullification` | 按键索引，index=2 | 牌名 / `general` |
| `Yiji` | 按键索引，index=2 | 技能名 / `general` |
| `viewCards` | 按键索引，index=2 | 技能名 / `general` |
| `guanxingViewCards` | 按键索引，index=2 | 技能名 / `general` |

注意两点：
- `cardUsed` 是**数组**（`table.insert(sgs.ai_choicemade_filter.cardUsed, fn)`），其余是**具名键**（`sgs.ai_choicemade_filter.skillChoice.xxx = fn`）。混用会静默不生效。
- 分发时 `callbacktable[key] or callbacktable.general` → 写不下具体技能名时可以挂在 `general` 上兜底。
- 实际仓库里 `skillChoice` 用了 6 次、`cardChosen` 7 次，是仅次于两者的高频类型；文档旧版只列了 `cardChosen`/`playerChosen`/`Nullification`/`general`，已补全。

## 三、数值配置表

| 表 | 键 | 说明 |
|---|---|---|
| `sgs.ai_keep_value` | 卡牌类名 | 全局留牌价值 |
| `sgs.<general>_keep_value` | 卡牌类名 | 某武将的留牌价值覆盖，如 `sgs.zhangfei_keep_value.Slash = 5.4` |
| `sgs.<general>_suit_value` | `heart`/`spade`/`club`/`diamond` | 某武将对花色的偏好 |
| `sgs.ai_suit_priority` | 技能名 | 字符串，如 `"diamond|heart|club|spade"` |
| `sgs.ai_weapon_value` / `sgs.ai_armor_value` / `sgs.ai_defense_value` | 卡牌类名 | 装备价值 |
| `sgs.dynamic_value.<类别>` | 卡牌类名 = true | 类别：`damage_card`、`control_usecard`、`control_card`、`lucky_chance`、`benefit` |
| `sgs.ai_slash_prohibit` | 卡牌类名 | `(self, card, enemy)` → bool，阻止对该敌人出杀 |

## 四、SmartAI 常用方法（第 5 步写 AI 时直接调用）

关系判断：
- `self:isFriend(p)` / `self:isEnemy(p)` / `self:isFriend(a, b)` —— 判断友方/敌方
- `self:getFriends(p)` / `self:getEnemies(p)` —— 返回玩家表
- `self.friends` / `self.enemies` —— 当前 AI 的友/敌列表

排序：
- `self:sort(players, key, inverse)`，key ∈ `hp` / `handcard` / `value` / `defense` / `threat`
- `self:sortByKeepValue(cards, inverse, kept)` / `sortByUseValue` / `sortByUsePriority` / `sortByDynamicUsePriority`

取数：
- `self:getCardsNum(class_name[, player[, flag[, selfonly]]])` —— flag 为 `h`/`e`/`j` 组合
- `self:getCardId(class_name[, player])` / `self:getCard` / `self:getCards`
- `self:getMaxCard([player])` / `self:getMaxNumberCard()` / `self:getMinNumberCard()`
- `self:hasSuit("spade|club"[, include_equip[, player]])` / `self:getSuitNum(...)`
- `sgs.QList2Table(qlist)` / `sgs.qlist(list)` —— QList 与 Lua 表互转

技能判断：
- `self:hasSkill("name")` / `self:hasShownSkill("name")` / `self:hasSkills("a|b")`
- `self.player:hasSkill(...)` / `hasShownSkill(...)` / `getVisibleSkillList(true)`
- `self.player:hasUsed("XxxCard")` —— 判断本回合是否已用过某技能卡
- `self.player:getMark("##name")` / `getMark("name")`

局势与伤害：
- `self:isWeak([player])` —— 是否虚弱
- `self:getOverflow([player])` —— 手牌超额
- `self:damageIsEffective([player[, nature[, source]]])`
- `self:needToLoseHp()` / `self:needDamagedEffects(from, to)`
- `self:willShowForMasochism()` / `self:willShowForAttack()` / `self:willShowForDefence()` —— 国战模式的"亮将"意愿，受虐/攻击/防御类技能 AI 常先判断它
- `self:needKongcheng(player, true)` / `self:doNotDiscard(player)` / `self:needToThrowArmor(player)`
- `self:slashProhibit(card, enemy)` / `self:slashIsEffective(card, enemy)` / `self:slashIsAvailable([player])`
- `self:getExpansionPileCards()` 等牌堆操作请就近参考同文件已有写法

## 五、AI 文件写法约定

- 文件顶部保留项目版权注释块，再写 `--魏标准版` 这类分组注释和 `--曹操` 这种武将名注释，便于检索。
- 一个技能的 AI 键名必须与 C++ 的 `objectName()` 完全一致。
- 同一文件内同名 hook 后写会覆盖前写（Lua 表赋值语义），**改已有技能时先 grep 确认没有第二处定义**。
- 建议顺序：先 `ai_skill_invoke`，再 `ai_skill_choice`，再选牌/选人，最后 `ai_skills` / `ai_skill_use_func`。
- AI 里不要直接读客户端 UI 状态；只用 `self`、`self.player`、`self.room`、`sgs.*`。

## 六、注意：`extension-doc/` 中的文档有滞后

`extension-doc/12-SmartAI.lua` 是历史文档，其中提到的 `sgs.ai_chaofeng`（嘲讽值表）在当前代码中**已不存在**，`SmartAI:sort` 的 `chaofeng` 关键字也只剩空壳分支。写 AI 时以**实际 `lua/ai/smart-ai.lua` 与本文件为准**，遇到文档与代码冲突一律信代码。
