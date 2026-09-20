# lang/zh_CN 键位规范（解析与书写共用）

本文件是 `scripts/parse_lang.py` 的解析依据，也是第 4 步写 lang 条目的格式依据。
键位前缀是**全仓库统计确认**的，不是推测。

## 一、文件与结构

- 位置：`lang/zh_CN/Package/<LangFile>.lua`；语音在 `lang/zh_CN/Audio/<Package>Lines.lua`。
- 结构：`return { ... }` 的 Lua 表，逗号分隔。文件内按势力分段（`-- 魏势力`），段内按武将分组。
- **lang 文件名与 package 名并不总一致**（`newsgs.cpp`、`mol.cpp` 的中文都在 `LordEXPackage.lua`）。
  落点一律 `grep -rln '\["<兄弟技能名>"\]' lang/zh_CN/` 实测，不要凭名字猜。

## 二、键位前缀全表

| 键形式 | 含义 | 必填 |
|---|---|---|
| `["<武将名>"]` | 武将中文名 | 新增武将时 |
| `["#<武将名>"]` | 武将称号（如 `["#caocao"] = "魏武帝"`） | 新增武将时 |
| `["illustrator:<武将名>"]` | 画师 | 否 |
| `["<技能名>"]` | **技能中文名** | ✅ |
| `[":<技能名>"]` | **技能描述文本** | ✅ |
| `["@<技能名>"]` | 是否发动的询问提示 | 可选 |
| `["@<技能名>-<后缀>"]` | 技能内某一步的询问提示（如 `@quhu-damage`） | 可选 |
| `["~<技能名>"]` | 操作指引（如"选择一张手牌→点击确定"） | 可选 |
| `["<技能名>:<choice>"]` | `askForChoice` 的选项标签（如 `["shangyi:hidden_general"] = "观看武将"`） | 有 askForChoice 时 |
| `["#<XxxBuff>"]` | 日志文案，配 `LogMessage.type = "#XxxBuff"` | 有日志时 |
| `["$<技能名><n>"]` | 技能语音第 n 句，放 `Audio/*Lines.lua` | 否 |

## 三、技能的判定规则（parse_lang.py 用的就是这条）

一个键 `K` 被认定为**技能**，当且仅当：

```
存在 [":K"]（描述键）   或   存在 ["@K"] / ["~K"]（询问/指引键）
```

即 `["K"]` 单独存在时不作为技能。这条规则同时排除了三类干扰：

- `["$xxx1"]` 语音键、`["#caocao"]` 称号键、`["illustrator:xxx"]` 画师键 —— 前缀不在判定集合内
- `["shangyi:hidden_general"]` 选项键 —— 含冒号，被跳过
- 只有名字没有描述的历史残留 —— 没有 `[":K"]` 就不算

## 四、描述文风约定（写条目的第 4 步遵循）

| 记号 | 含义 |
|---|---|
| `▶` | "然后 / 其后结算"，衔接两个结算步骤。**出现即提示可能含两个结算点**，常需拆成主技能 + `#` 前缀内部技 |
| `→` | "选择操作"，用于 `~技能名` 的操作指引 |
| `【】` | 标牌名，如【杀】【闪】【决斗】 |
| `X` / `Y` | 变量 |
| `%from` `%to` `%src` `%dest` `%arg` `%arg2` | 日志占位符，配 `LogMessage` 使用 |
| `锁定技` / `限定技` / `觉醒技` | 写在描述开头，直接决定 `frequency` |

措辞与代码的对应：

| 措辞 | 含义 |
|---|---|
| 你可以…… / 你可…… | 可选，需要询问 |
| 你须…… / 锁定技 | 强制，不询问 |
| 每局限一次 / 限定技 | `Skill::Limited` |
| 出牌阶段限一次 | 技能卡形态用 `!player->hasUsed("XxxCard")`；非技能卡用 `Skill::Limited` |
| 每回合 / 每阶段限一次 | 多数自管标记，**优先照抄同 package 语义最近的现有技能** |

## 五、解析命令

```bash
# 解析单个文件里所有技能
python scripts/parse_lang.py lang/zh_CN/Package/StandardWeiGeneral.lua

# 只看某个技能
python scripts/parse_lang.py lang/zh_CN/Package/StandardWeiGeneral.lua --skill jianxiong

# 解析一段 lang 片段（不必是合法 Lua 表）
python scripts/parse_lang.py --snippet my-skill.lang.lua

# 全项目技能清单
python scripts/parse_lang.py --root . --list

# 机器可读
python scripts/parse_lang.py <file> --json
```

输出的是**技能要素表**：形态、建议基类、可选性、频率、事件、效果、需不需要技能卡、
以及该技能需要的 `sgs.ai_*` hook 组合。可直接喂给 `scripts/scaffold_skill.py` 生成骨架。

## 六、注意

- 判断不了的时候宁可不判：解析器把形态不明的技能标成"待定"，并提示需人工判读，而不是硬猜一个基类。
- 主时机取"在描述里出现位置最靠前"的那个；描述里出现第二个时机时会单独列出，
  这通常正是需要拆内部触发技的地方（如裸衣：主时机"摸牌阶段结束时"、次要时机"造成伤害时"）。
