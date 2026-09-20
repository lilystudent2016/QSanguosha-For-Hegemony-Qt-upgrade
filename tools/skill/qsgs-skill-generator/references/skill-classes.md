# 技能基类、事件、package 落点

## 一、package ↔ 文件落点对照表

一个技能要落到哪个 C++ / lang / AI 文件，取决于它属于哪个 package。

| package 名（`Package("...")`） | C++ 文件 | lang 文件 | AI 文件 |
|---|---|---|---|
| `standard`（含 test） | `standard-package.cpp`、`standard-wei-generals.cpp`、`standard-shu-generals.cpp`、`standard-wu-generals.cpp`、`standard-qun-generals.cpp` | `StandardGeneralPackage.lua`、`StandardWeiGeneral.lua`、`StandardShuGeneral.lua`、`StandardWuGeneral.lua`、`StandardQunGeneral.lua` | `standard-wei-ai.lua` 等 4 个 + `standard_cards-ai.lua` |
| `standard_cards` | `standard-basics.cpp`、`standard-equips.cpp`、`standard-tricks.cpp` | `StandardPackage.lua` | `standard_cards-ai.lua` |
| `momentum` / `momentum_equip` | `momentum.cpp` | `MomentumPackage.lua` | `momentum-ai.lua` |
| `power` / `power_equip` | `power.cpp` | `PowerPackage.lua` | `power-ai.lua` |
| `lord_ex` / `lord_ex_card` | `lord-ex.cpp` | `LordEXPackage.lua` | `lord_ex-ai.lua` |
| `manoeuvre` / `newsgs` | `newsgs.cpp` | `LordEXPackage.lua`（**注意不是同名文件**） | `manoeuvre-ai.lua`、`newsgs-ai.lua` |
| `MOL` / `overseas` | `mol.cpp` | `LordEXPackage.lua` | `mol-ai.lua`、`overseas-ai.lua` |
| `formation` / `formation_equip` | `formation.cpp` | `FormationPackage.lua` | `formation-ai.lua` |
| `jiange-defense` | `jiange-defense.cpp` | `JiangeDefensePackage.lua` | `jiange-defense-ai.lua` |
| `strategic_advantage` | `strategic-advantage.cpp` | `StrategicAdvantagePackage.lua` | `strategic_advantage-ai.lua` |
| `transformation` / `transformation_equip` | `transformation.cpp` | `TransformationPackage.lua` | `transformation-ai.lua` |

**对照表只是起点，落点一律以 grep 实测为准**（lang 文件名与 package 名并不总是一致，上表已标注两处例外）。确认命令：

```bash
# 已知同 package 里某个兄弟技能，看它的中文在哪个文件
grep -rln '\["<兄弟技能名>"\]' lang/zh_CN/
```

## 二、基类决策表

虚函数签名取自 `src/core/skill.h`。

### 触发型（派生自 `TriggerSkill`）

| 基类 | 语义 | 必须 / 常覆写 |
|---|---|---|
| `TriggerSkill` | 通用时机触发 | `triggerable` / `cost` / `effect`；需要只记录不结算时用 `record` |
| `MasochismSkill` | "当你受到伤害后"专用 | `onDamaged(ServerPlayer *, const DamageStruct &)`（纯虚）；事件自动挂 `Damaged`，**不要手写 events** |
| `PhaseChangeSkill` | 阶段相关 | `onPhaseChange(ServerPlayer *)`（纯虚），返回 true 中断阶段 |
| `DrawCardsSkill` | 改摸牌数 | `getDrawNum(ServerPlayer *, int n)`（纯虚） |
| `GameStartSkill` | 游戏开始时 | `onGameStart(ServerPlayer *)`（纯虚） |
| `DetachEffectSkill` | 技能被移除时的收尾 | `getPileName()` / `onSkillDetached(...)` |
| `WeaponSkill` / `ArmorSkill` / `TreasureSkill` | 装备技能 | `triggerable(const ServerPlayer *)`，需 `frequency = Compulsory` |
| `FakeMoveSkill` | 伪移动（记录牌去向） | 一般直接继承即可 |
| `BattleArraySkill` | 阵法技 | `triggerable(const ServerPlayer *)` + `summonFriends` |
| `ScenarioRule` | 场景规则 | 只在 scenario 里用 |

`TriggerSkill` 的三个核心方法（签名完全一致，注意都有 `ask_who`）：

```cpp
virtual QStringList triggerable(TriggerEvent, Room *, ServerPlayer *player, QVariant &data, ServerPlayer * &ask_who) const;
virtual bool cost(TriggerEvent, Room *, ServerPlayer *player, QVariant &data, ServerPlayer *ask_who = NULL) const;
virtual bool effect(TriggerEvent, Room *, ServerPlayer *player, QVariant &data, ServerPlayer *ask_who = NULL) const;
```

返回值语义：
- `triggerable` → 非空 `QStringList(objectName())` 表示"可发动"，空列表表示"不发动"
- `cost` → true 表示玩家选择发动、继续走 `effect`；false 表示放弃
- `effect` → **返回 false 表示继续后续结算；返回 true 表示中断结算链**（如跳过阶段）。默认写 `return false`

### 视为技型

| 基类 | 语义 | 必须覆写 |
|---|---|---|
| `ViewAsSkill` | 任意张牌当作某牌 | `viewFilter(selected, to_select)`、`viewAs(cards)` |
| `OneCardViewAsSkill` | 一张符合条件的牌当作某牌 | `viewAs(const Card *originalCard)`；用 `filter_pattern` / `response_pattern` / `response_or_use` 声明 |
| `ZeroCardViewAsSkill` | 不用牌直接产生（配技能卡） | `viewAs()`；遍历 `isEnabledAtPlay` |
| `FilterSkill` | 把牌"视为"另一张固定牌（如八阵） | `viewFilter(to_select, player)` |
| `ArraySummonSkill` | 阵法召唤 | `isEnabledAtPlay` |

- `filter_pattern` 用项目的 ExpPattern 语法：`".|black|.|hand"`（任意黑色手牌）、`".|.|.|hand,equip"` 等。
- `response_pattern` 声明它能响应什么（`"jink"`、`"slash"`、`"nullification"`）。
- `response_or_use` = true 表示既可响应该牌也可主动使用。

### 规则修正型

| 基类 | 语义 | 必须覆写 |
|---|---|---|
| `ProhibitSkill` | 禁止使用某牌 | `isProhibited(from, to, card, others)` |
| `DistanceSkill` | 改计算距离 | `getCorrect(from, to)` |
| `MaxCardsSkill` | 改手牌上限 | `getExtra` / `getFixed` |
| `TargetModSkill` | 改使用次数 / 距离限制 / 目标数 | `getPattern`、`getResidueNum`、`getDistanceLimit`、`getExtraTargetNum` |
| `SlashNoDistanceLimitSkill` | 【杀】无距离限制 | 继承即可，`getDistanceLimit` 已实现 |
| `FixCardSkill` | 固定牌的处理方式 | `isCardFixed(...)` |
| `ViewHasSkill` | 视同拥有某技能 | `ViewHas(player, skill_name, flag)` |
| `AttackRangeSkill` | 改攻击范围 | `getExtra` / `getFixed` |
| `InvaliditySkill` | 技能无效化 | `isSkillValid(player, skill)` |

### 技能卡

`SkillCard` 派生自 `Card`，**必须声明在 `.h`**：

```cpp
class XxxCard : public SkillCard
{
    Q_OBJECT
public:
    Q_INVOKABLE XxxCard();
    virtual bool targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const;
    virtual void onEffect(const CardEffectStruct &effect) const;
    virtual void extraCost(Room *room, const CardUseStruct &card_use) const;   // 按需
};
```

并在包的构造函数里登记元对象（否则 `@XxxCard` 无法解析）：

```cpp
addMetaObject<XxxCard>();
```

## 三、共享技能的 owner 后缀模式

同一个技能被多名武将复用时，项目惯例是**给技能名加 owner 后缀**，lang 里为每个实例单独起名：

```cpp
// .h
class Mashu : public DistanceSkill
{
public:
    explicit Mashu(const QString &);          // 不写默认值：强制调用方传 owner
    virtual int getCorrect(const Player *from, const Player *) const;
};

// .cpp
Mashu::Mashu(const QString &owner) : DistanceSkill("mashu_" + owner) {}

// 注册
machao->addSkill(new Mashu("machao"));
```

```lua
-- lang/zh_CN/Package/StandardShuGeneral.lua
["mashu_machao"] = "马术",
[":mashu_machao"] = "锁定技，你计算与其他角色的距离-1。",
```

对比：只被一名武将使用、但需要跨 .cpp 复用类的（如 `Fankui`），用 `explicit Xxx(const QString &owner = QString())` 给默认值，构造函数里 `MasochismSkill("fankui" + owner)`。

## 四、事件挂载与频率

```cpp
Xxx() : TriggerSkill("xxx")
{
    events << EventPhaseStart << EventPhaseEnd << PreCardUsed;   // 按需
    frequency = Skill::NotFrequent;                              // 见下表
}
```

| Frequency | 含义 | 对应中文 |
|---|---|---|
| `Frequent`（默认不写则 `NotFrequent`） | 可反复发动 | —— |
| `NotFrequent` | 需要每次询问（可选技默认值） | "你可以……" |
| `Compulsory` | 强制发动，不做询问 | 锁定技、"你须……" |
| `Limited` | 限定技 | "限定技"、"每局限一次" |
| `Wake` | 觉醒技 | "觉醒技" |

`frequency` 必须在**构造函数**里赋值；它是AI 默认行为的兜底依据（`ai_skill_invoke` 缺失时，`Frequent` 恒真、其余随机），所以可选技一定要写 AI。

## 五、注册与登记

1. **武将技能** —— 在所属注册函数里加行：
   ```cpp
   General *caocao = new General(this, "caocao", "wei");   // 已有武将则复用变量
   caocao->addSkill(new Jianxiong);
   ```
   standard 包的注册函数在 `standard-wei-generals.cpp` 的 `StandardPackage::addWeiGenerals()` 等；其它包直接在 `XxxPackage::XxxPackage()` 构造函数里建 `General`。
   新建整名武将时用 `new General(this, "englishname", "kingdom", hp, male, ...)`，kingdom 取 `wei` / `shu` / `wu` / `qun` / `god`。

2. **非武将技能**（全局技、装备技、内部技） —— 在包构造函数里 `skills << new Xxx;`。

3. **技能卡** —— `addMetaObject<XxxCard>();`。

4. **新文件** —— 若新增了 `.cpp` / `.h`，必须加进 `QSanguosha.pro` 的 `SOURCES` / `HEADERS`，否则不参与编译。

5. **整包注册** —— 新增包时在文件末尾 `ADD_PACKAGE(Xxx);`。

## 六、AI 脚本的加载

`lua/ai/*.lua` 由 `lua/ai/smart-ai.lua` 末尾按顺序 `dofile` 载入。已存在的文件不需要额外登记，直接往对应文件里追加即可。

载入顺序中 `standard_cards-ai.lua`、`maneuvering-ai.lua` 早于各国武将 AI，所以在它们里面定义的函数与表在下游文件中可直接使用。

只有 **新增 AI 文件**（而不是往已有文件追加）时才需要改动 smart-ai.lua：在末尾的 `dofile` 列表里加一行。扩展包（`extensions/ai/`）有独立的自动扫描逻辑，不走这条。
