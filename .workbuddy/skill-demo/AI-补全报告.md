# 缺失 Lua 格式 AI —— 补全清单与验证报告

> 审计脚本：`~/.workbuddy/skills/qsgs-skill-generator/scripts/audit_ai.py`  
> 审计范围：全项目 lang/zh_CN/Package/*.lua 声明 + src/package/*.cpp 技能实现  
> 生成时间：2026-09-14

## 一、审计结论（补充前 → 补充后）

| 指标 | 补充前 | 补充后 |
|---|---|---|
| 已具备全部必需 AI hook | 417 | **497** |
| 致命缺失 FATAL（AI 永不发动 / 乱选 / 无法响应） | 29 | **0** |
| 降级缺失 DEGRADED（能用但选择不聪明） | 51 | **0** |
| 不可用 UNUSABLE（视为技/技能卡想不起来用） | — | **0** |
| 涉及技能数 / 缺失 hook 数 | 80 / 108 | **0 / 0** |

补充前共 **80 项技能、108 个 AI hook** 缺失；本次已全部补齐，重跑审计后缺失归零。

## 二、逐项清单（技能 → 缺失 hook → 补全位置）

### src/package/formation.cpp（2 技能 / 2 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `huyuan` | DEGRADED | `ai_skill_cardchosen.huyuan` | `lua/ai/formation-ai.lua:835` |
| `tiaoxin` | DEGRADED | `ai_skill_cardchosen.tiaoxin` | `lua/ai/formation-ai.lua:854` |

### src/package/jiange-defense.cpp（11 技能 / 11 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `jgbenlei` | DEGRADED | `ai_skill_playerchosen.jgbenlei` | `lua/ai/jiange-defense-ai.lua:535` |
| `jgfengjian` | FATAL | `ai_skill_invoke.jgfengjian` | `lua/ai/jiange-defense-ai.lua:515` |
| `jghuchen` | FATAL | `ai_skill_invoke.jghuchen` | `lua/ai/jiange-defense-ai.lua:516` |
| `jgjiaoxie` | FATAL | `ai_skill_exchange.jgjiaoxie_give` | `lua/ai/jiange-defense-ai.lua:556` |
| `jgnailuo` | FATAL | `ai_skill_invoke.jgnailuo` | `lua/ai/jiange-defense-ai.lua:524` |
| `jgqinzhen` | FATAL | `ai_skill_invoke.jgqinzhen` | `lua/ai/jiange-defense-ai.lua:517` |
| `jgshuailing` | FATAL | `ai_skill_invoke.jgshuailing` | `lua/ai/jiange-defense-ai.lua:518` |
| `jgtanshi` | DEGRADED | `ai_skill_discard.jgtanshi_discard` | `lua/ai/jiange-defense-ai.lua:545` |
| `jgtianjiang` | FATAL | `ai_skill_invoke.jgtianjiang` | `lua/ai/jiange-defense-ai.lua:519` |
| `jgxiaorui` | FATAL | `ai_skill_invoke.jgxiaorui` | `lua/ai/jiange-defense-ai.lua:520` |
| `jgzhenxi` | FATAL | `ai_skill_invoke.jgzhenxi` | `lua/ai/jiange-defense-ai.lua:521` |

### src/package/lord-ex.cpp（16 技能 / 22 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `#bushi-compulsory` | DEGRADED | `ai_skill_discard.bushi_discard` | `lua/ai/lord_ex-ai.lua:2913` |
| `#jinxian-compulsory` | FATAL | `ai_skill_choice.jinxian_hide` | `lua/ai/lord_ex-ai.lua:2921` |
| `#jinxian-compulsory` | FATAL | `ai_skill_discard.jinxian_discard` | `lua/ai/lord_ex-ai.lua:2927` |
| `#liangfan-effect` | DEGRADED | `ai_skill_cardchosen.liangfan` | `lua/ai/lord_ex-ai.lua:2934` |
| `#lianpian-other` | DEGRADED | `ai_skill_cardchosen.lianpian` | `lua/ai/lord_ex-ai.lua:2941` |
| `#lixia-other` | DEGRADED | `ai_skill_cardchosen.lixia` | `lua/ai/lord_ex-ai.lua:2948` |
| `#lixia-other` | DEGRADED | `ai_skill_discard.lixia_discard` | `lua/ai/lord_ex-ai.lua:2952` |
| `#xiongnve-effect` | DEGRADED | `ai_skill_cardchosen.xiongnve` | `lua/ai/lord_ex-ai.lua:2959` |
| `#zhidao-damage` | DEGRADED | `ai_skill_cardchosen.zhidao` | `lua/ai/lord_ex-ai.lua:2966` |
| `baolie` | DEGRADED | `ai_skill_cardchosen.baolie` | `lua/ai/lord_ex-ai.lua:2973` |
| `jianyan` | FATAL | `ai_skill_choice.jianyan` | `lua/ai/lord_ex-ai.lua:2980` |
| `jianyan` | FATAL | `ai_skill_playerchosen.jianyan` | `lua/ai/lord_ex-ai.lua:2987` |
| `jianyan` | FATAL | `观望可用性(jianyan)` | `lua/ai/lord_ex-ai.lua:3004` |
| `jianyan` | FATAL | `技能卡.JianyanCard` | `lua/ai/lord_ex-ai.lua:3011` |
| `jinfa` | DEGRADED | `ai_skill_cardchosen.jinfa` | `lua/ai/lord_ex-ai.lua:3018` |
| `jujian` | UNUSABLE | `技能卡.JujianCard` | `lua/ai/lord_ex-ai.lua:3025` |
| `shicai` | DEGRADED | `ai_skill_discard.shicai_discard` | `lua/ai/lord_ex-ai.lua:3048` |
| `suzhi` | DEGRADED | `ai_skill_cardchosen.suzhi` | `lua/ai/lord_ex-ai.lua:3055` |
| `tongling` | DEGRADED | `ai_skill_playerchosen.tongling` | `lua/ai/lord_ex-ai.lua:3062` |
| `tongling_usecard` | UNUSABLE | `观望可用性(tongling_usecard)` | `lua/ai/lord_ex-ai.lua:3069` |
| `tongling_usecard` | UNUSABLE | `技能卡.TonglingCard` | `lua/ai/lord_ex-ai.lua:3069` |
| `wuyan` | FATAL | `ai_skill_invoke.wuyan` | `lua/ai/lord_ex-ai.lua:3096` |

### src/package/mol.cpp（17 技能 / 30 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `#danshou-effect` | FATAL | `ai_skill_choice.danshou` | `lua/ai/mol-ai.lua:498` |
| `#kenshang-effect` | FATAL | `ai_skill_invoke._kenshang` | `lua/ai/mol-ai.lua:515` |
| `#kenshang-effect` | FATAL | `ai_skill_choice.kenshang` | `lua/ai/mol-ai.lua:518` |
| `#moukui-effect` | DEGRADED | `ai_skill_cardchosen.moukui` | `lua/ai/mol-ai.lua:341` |
| `#yinbingx-compulsory` | DEGRADED | `ai_skill_askforag.yinbingx` | `lua/ai/mol-ai.lua:330` |
| `biaozhao` | FATAL | `ai_skill_exchange.biaozhao_give` | `lua/ai/mol-ai.lua:540` |
| `biaozhao` | FATAL | `观望可用性(biaozhao)` | `lua/ai/mol-ai.lua:548` |
| `biaozhao` | FATAL | `技能卡.BiaozhaoCard` | `lua/ai/mol-ai.lua:555` |
| `danshou` | FATAL | `ai_skill_invoke.danshou` | `lua/ai/mol-ai.lua:488` |
| `jinqu` | FATAL | `ai_skill_invoke.jinqu` | `lua/ai/mol-ai.lua:426` |
| `jinqu` | FATAL | `ai_skill_discard.jinqu` | `lua/ai/mol-ai.lua:432` |
| `jinwu` | FATAL | `ai_skill_invoke.jinwu` | `lua/ai/mol-ai.lua:376` |
| `jinwu` | FATAL | `ai_skill_playerchosen.jinwu_slash` | `lua/ai/mol-ai.lua:379` |
| `juzhan` | FATAL | `ai_skill_invoke.juzhan` | `lua/ai/mol-ai.lua:444` |
| `juzhan` | FATAL | `ai_skill_playerchosen.juzhan` | `lua/ai/mol-ai.lua:452` |
| `juzhan` | FATAL | `ai_skill_choice.juzhan` | `lua/ai/mol-ai.lua:464` |
| `juzhan` | FATAL | `ai_skill_cardchosen.juzhan` | `lua/ai/mol-ai.lua:471` |
| `kanji` | UNUSABLE | `观望可用性(kanji)` | `lua/ai/mol-ai.lua:588` |
| `kanji` | UNUSABLE | `技能卡.KanjiCard` | `lua/ai/mol-ai.lua:603` |
| `kenshang` | UNUSABLE | `观望可用性(kenshang)` | `lua/ai/mol-ai.lua:527` |
| `moukui` | DEGRADED | `ai_skill_cardchosen.moukui` | `lua/ai/mol-ai.lua:341` |
| `qianzheng` | FATAL | `ai_skill_cardask.@qianzheng-cost` | `lua/ai/mol-ai.lua:609` |
| `qianzheng` | FATAL | `观望可用性(qianzheng)` | `lua/ai/mol-ai.lua:609` |
| `qizhi` | DEGRADED | `ai_skill_playerchosen.qizhi` | `lua/ai/mol-ai.lua:398` |
| `qizhi` | DEGRADED | `ai_skill_cardchosen.qizhi` | `lua/ai/mol-ai.lua:408` |
| `xiaoqi` | FATAL | `ai_skill_invoke.xiaoqi` | `lua/ai/mol-ai.lua:619` |
| `xiaoqi` | FATAL | `观望可用性(xiaoqi)` | `lua/ai/mol-ai.lua:619` |
| `zhenxi` | DEGRADED | `ai_skill_cardchosen.zhenxi` | `lua/ai/mol-ai.lua:358` |
| `zhuke` | FATAL | `ai_skill_invoke.zhuke` | `lua/ai/mol-ai.lua:384` |
| `zhuke` | FATAL | `ai_skill_playerchosen.zhuke` | `lua/ai/mol-ai.lua:387` |

### src/package/momentum.cpp（3 技能 / 3 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `fengshi` | FATAL | `ai_skill_cardask.@fengshi-discard` | `lua/ai/momentum-ai.lua:696` |
| `fenming` | DEGRADED | `ai_skill_cardchosen.fenming` | `lua/ai/momentum-ai.lua:710` |
| `hengzheng` | DEGRADED | `ai_skill_cardchosen.hengzheng` | `lua/ai/momentum-ai.lua:728` |

### src/package/newsgs.cpp（21 技能 / 30 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `#mingfa-effect` | DEGRADED | `ai_skill_cardchosen.mingfa` | `lua/ai/manoeuvre-ai.lua:1354` |
| `#zhuihuan-effect` | DEGRADED | `ai_skill_discard.zhuihuan_discard` | `lua/ai/newsgs-ai.lua:787` |
| `anyong` | DEGRADED | `ai_skill_discard.anyong_discard` | `lua/ai/manoeuvre-ai.lua:1332` |
| `daoshu` | DEGRADED | `ai_skill_cardchosen.daoshu` | `lua/ai/manoeuvre-ai.lua:1288` |
| `deshao` | DEGRADED | `ai_skill_cardchosen.deshao` | `lua/ai/manoeuvre-ai.lua:1270` |
| `fenglve` | DEGRADED | `ai_skill_cardschosen.fenglve` | `lua/ai/manoeuvre-ai.lua:1246` |
| `fenglvezongheng` | DEGRADED | `ai_skill_cardchosen.fenglve` | `lua/ai/manoeuvre-ai.lua:1257` |
| `gongxiu` | DEGRADED | `ai_skill_discard.gongxiu_throw` | `lua/ai/manoeuvre-ai.lua:1343` |
| `jianguo` | FATAL | `ai_skill_choice.jianguo` | `lua/ai/newsgs-ai.lua:832` |
| `jianguo` | FATAL | `ai_skill_discard.jianguo` | `lua/ai/newsgs-ai.lua:853` |
| `jianguo` | FATAL | `观望可用性(jianguo)` | `lua/ai/newsgs-ai.lua:865` |
| `jianguo` | FATAL | `技能卡.JianguoCard` | `lua/ai/newsgs-ai.lua:873` |
| `lundao` | DEGRADED | `ai_skill_cardchosen.lundao` | `lua/ai/manoeuvre-ai.lua:1315` |
| `qiao` | DEGRADED | `ai_skill_cardchosen.qiao` | `lua/ai/manoeuvre-ai.lua:1127` |
| `qiao` | DEGRADED | `ai_skill_discard.qiao_discard` | `lua/ai/manoeuvre-ai.lua:1144` |
| `qingshi` | DEGRADED | `ai_skill_playerchosen.qingshi` | `lua/ai/newsgs-ai.lua:798` |
| `quanjian` | UNUSABLE | `观望可用性(quanjian)` | `lua/ai/newsgs-ai.lua:895` |
| `quanjian` | UNUSABLE | `技能卡.QuanjianCard` | `lua/ai/newsgs-ai.lua:903` |
| `shejian` | FATAL | `ai_skill_choice.shejian` | `lua/ai/manoeuvre-ai.lua:1155` |
| `shejian` | FATAL | `ai_skill_cardschosen.shejian` | `lua/ai/manoeuvre-ai.lua:1173` |
| `tujue` | DEGRADED | `ai_skill_playerchosen.tujue` | `lua/ai/newsgs-ai.lua:817` |
| `weimeng` | DEGRADED | `ai_skill_cardschosen.weimeng` | `lua/ai/manoeuvre-ai.lua:1205` |
| `weimengzongheng` | DEGRADED | `ai_skill_cardchosen.weimeng` | `lua/ai/manoeuvre-ai.lua:1229` |
| `youyan` | FATAL | `ai_skill_invoke.youyan` | `lua/ai/newsgs-ai.lua:750` |
| `yusui` | DEGRADED | `ai_skill_discard.yusui_discard` | `lua/ai/manoeuvre-ai.lua:1193` |
| `zhiren` | FATAL | `ai_skill_choice.zhiren` | `lua/ai/newsgs-ai.lua:921` |
| `zhiren` | FATAL | `ai_skill_playerchosen.zhiren` | `lua/ai/newsgs-ai.lua:930` |
| `zhiren` | FATAL | `ai_skill_cardchosen.zhiren` | `lua/ai/newsgs-ai.lua:951` |
| `zhuihuan` | FATAL | `ai_skill_playerchosen.zhuihuan` | `lua/ai/newsgs-ai.lua:754` |
| `zhuihuan` | FATAL | `ai_skill_choice.zhuihuan` | `lua/ai/newsgs-ai.lua:774` |

### src/package/standard-equips.cpp（3 技能 / 3 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `DoubleSword` | DEGRADED | `ai_skill_discard.DoubleSword` | `lua/ai/standard_cards-ai.lua:3815` |
| `IceSword` | DEGRADED | `ai_skill_cardchosen.IceSword` | `lua/ai/standard_cards-ai.lua:3825` |
| `KylinBow` | FATAL | `ai_skill_choice.KylinBow` | `lua/ai/standard_cards-ai.lua:3842` |

### src/package/standard-qun-generals.cpp（2 技能 / 2 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `#kuangfu-effect` | DEGRADED | `ai_skill_discard.kuangfu_discard` | `lua/ai/standard-qun-ai.lua:1509` |
| `sijian` | DEGRADED | `ai_skill_cardchosen.sijian` | `lua/ai/standard-qun-ai.lua:1492` |

### src/package/standard-shu-generals.cpp（1 技能 / 1 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `lieren` | DEGRADED | `ai_skill_cardchosen.lieren` | `lua/ai/standard-shu-ai.lua:1231` |

### src/package/standard-wei-generals.cpp（1 技能 / 1 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `ganglie` | DEGRADED | `ai_skill_cardchosen.ganglie` | `lua/ai/standard-wei-ai.lua:1851` |

### src/package/transformation.cpp（3 技能 / 3 hook）

| 技能 | 补全前级别 | 补全的 AI hook | 写入位置 |
|---|---|---|---|
| `xuanlue` | DEGRADED | `ai_skill_cardchosen.xuanlue` | `lua/ai/transformation-ai.lua:2497` |
| `zhiman-second` | DEGRADED | `ai_skill_cardchosen.zhiman` | `lua/ai/transformation-ai.lua:2515` |
| `zhiyu` | DEGRADED | `ai_skill_discard.zhiyu` | `lua/ai/transformation-ai.lua:2536` |

**合计 108 个 hook。**

## 三、级别含义

- **FATAL**：`ai_skill_invoke`（非 Frequent 时引擎兜底返回 nil，AI **永不发动**该技能）、`ai_skill_choice`（兜底优先选 cancel/no 或随机）、`ai_skill_exchange`、`ai_skill_cardask`。
- **DEGRADED**：`ai_skill_discard` / `ai_skill_playerchosen` / `ai_skill_cardchosen` / `ai_skill_cardschosen` / `ai_skill_askforag` 有通用启发式兜底，技能能用但选牌/选人不聪明。
- **UNUSABLE**：视为技或技能卡没有任何注册路径（`ai_skills` / `ai_skill_use["@@x"]` / `ai_view_as` / `ai_cardsview` / `ai_skill_use_func.<Card>`），AI 想不起来使用。

## 四、补全原则

1. **键名严格对齐运行期**：`ai_skill_invoke/choice/playerchosen/discard/cardchosen/cardschosen/askforag` 的键取 C++ `askForXXX` 的 reason；内部技的 reason 会经 `string.gsub(reason, "%-", "_")` 归一化（如 `#mingfa-effect` → `mingfa`）。
2. **`ai_skill_cardask` 键取 prompt 首段**（`:` 之前），而非技能名。
3. **排序语义**（`smart-ai.lua`）：`sortByUseValue(cards)` 默认**降序**（先取价值最高）；`sortByUseValue(cards, true)` 升序；`sortByKeepValue(cards)` 默认**升序**（先取最不值钱）；`sort(players, "hp")` 默认升序（先取血最少）。
4. **敌我分治**：拆/偷敌方 → 取价值最高（先 armor/weapon 等关键牌）；拆/弃友方 → 取保留价值最低。
5. **逻辑与 C++ 保持一致**：补全内容逐条对照 C++ 触发条件与结算分支（例如“摸一张再弃一半”vs“弃一张再摸一半”的收益差、`MethodGet` 取牌 vs `MethodDiscard` 弃牌）。

## 五、需注意的边界情况

- `src/package/mol.cpp` 的 `kenshang` / `#kenshang-effect` 为**未接线代码**：C++ 中没有任何 `addSkill` 指向它，lang 也无对应条目。本次仍按其设计意图补齐了 AI，并在 `lua/ai/mol-ai.lua` 内注明，若日后正式接入可直接生效。
- 未修改任何 C++ 与 lang 文件，仅新增 `lua/ai/*.lua` 中的 AI 定义；所有写入均保持项目 **CRLF** 行尾。
