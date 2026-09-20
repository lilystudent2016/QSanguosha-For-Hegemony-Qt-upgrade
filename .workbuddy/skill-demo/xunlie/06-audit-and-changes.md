# Skill 能力审计：中文 lang → C++ + AI

审计对象：`~/.workbuddy/skills/qsgs-skill-generator/`
审计方式：用一段真实格式的 lang 片段实跑全链路（本目录的 `00-input.lang.lua`），
并对照仓库真实技能（jianxiong / luoyi / qingguo / quhu / luoshen / jushou / shangyi / qiangxi）回归。

## 一、三项能力的实现情况

| 能力 | 审计前 | 审计后 | 说明 |
|---|---|---|---|
| ① 解析中文 lang 文件 | ❌ **无实现** | ✅ 已实现 | 新增 `scripts/parse_lang.py` |
| ② 生成对应的 C 代码 | ⚠️ **半实现** | ✅ 已实现 | 新增 `scripts/scaffold_skill.py`；补齐形态覆盖 |
| ③ 生成对应的 Lua 技能 AI | ⚠️ **半实现** | ✅ 已实现 | 同上脚本按形态生成 hook 组合 |

### 审计前的具体缺口

**① 解析 —— 完全缺失。**
原技能只有"写 lang"的规则（第 4 步），没有"读 lang"的能力：
- 没有脚本能从 lang 文件反推技能清单与要素；
- `inspect_skill.py` 必须**先知道技能名**才能检索，不能"给文件推名字"；
- `cn-to-cpp.md` 的措辞映射规则只面向"描述文本"，没有键位语义（`@` / `~` / `xxx:choice` / `#` 各是什么）。

**② 生成 C++ —— 知识与骨架都有，但覆盖面不全且无自动化。**
- 有：26 个基类决策表、事件关键词表、4 个端到端实例、`.pro`/`.h`/注册约定。
- 缺：只有 3 个模板（TriggerSkill / MasochismSkill / SkillCard），
  **没有** ViewAsSkill 族、PhaseChange/DrawCards/GameStart、9 个规则修正型的骨架；
  没有生成脚本，全靠模型照模板手抄。

**③ 生成 AI —— 参考文档最完备，但同样缺生成与分形态模板。**
- 有：`ai-hooks.md` 全表（键 / 签名 / 返回值）+ SmartAI 方法清单 + 一个"所有 hook 堆一起"的通用模板。
- 缺：没有按技能形态分档的 AI 骨架（触发技 / 视为技 / 技能卡各一套）；
  `ai_choicemade_filter` 的询问类型只列了 4 个（实际有 11 个，且**数组 vs 具名键**两种写法混用，写错静默不生效）。

## 二、这轮实跑中发现并修掉的 6 个 bug

| # | 位置 | 问题 | 修法 |
|---|---|---|---|
| 1 | `inspect_skill.py` | **注释被当成真实代码**：模板里 `// addSkill(new Xxx);` 会让"未注册"的技能报成"已注册" | 扫描前按等长空格屏蔽 `//` `/* */` `--` `--[[ ]]`，行号不变；含长度校验防止误吞 |
| 2 | `inspect_skill.py` | 传 Git-Bash 风格 `--root /c/...` 被解释成 `C:\c\...`，不报错，只把三处全报"缺失" | 增加根目录合法性校验 + 明确的报错提示 |
| 3 | `inspect_skill.py` | 不检查技能卡元对象登记，而漏 `addMetaObject` 是典型静默失效 | 新增该检查（已在本轮抓到演示 .cpp 的问题） |
| 4 | `parse_lang.py` | 把「出牌阶段」误判为触发时机 → 形态判成 TriggerSkill | 区分 trigger / active 两类时机 |
| 5 | `parse_lang.py` | `quhu` 因描述含"其对其攻击范围内"被误判成 `AttackRangeSkill` | 规则修正型措辞收紧为"你的攻击范围±N"等指向自身属性的写法 |
| 6 | `parse_lang.py` | `luoyi` 取错主时机（取到"造成伤害时"而非"摸牌阶段结束时"） | 主时机改为取描述中**位置最靠前**者，其余列为"次要时机"并提示拆内部技 |

另外修正了 `references/ai-hooks.md` 里 `ai_choicemade_filter` 的类型清单与结构说明。

## 三、回归结果

解析器在真实技能上的判定（与仓库实际实现一致）：

| 技能 | 判定形态 | 判定基类 | 主时机 |
|---|---|---|---|
| jianxiong 奸雄 | 触发技 | `MasochismSkill` | 受到伤害后 |
| luoyi 裸衣 | 触发技 | `TriggerSkill` | 摸牌阶段结束时（次要时机：造成伤害时 ✅ 提示需拆内部技） |
| qingguo 倾国 | 视为技 | `OneCardViewAsSkill` | — |
| quhu 驱虎 | 主动技 | `ZeroCardViewAsSkill` | 出牌阶段 |
| luoshen 洛神 | 触发技 | `PhaseChangeSkill` | 准备阶段 |
| jushou 据守 | 触发技 | `TriggerSkill` | 结束阶段 |
| shangyi 尚义 | 主动技 | `ZeroCardViewAsSkill` | 出牌阶段 |

自检器在真实仓库上：jianxiong / luoyi / qingguo / quhu / tuxi / ganglie / shangyi / qiangxi 全部通过，未出现新的误报。
全项目 lang 共解析出 **415 个技能**。

## 四、仍然存在的边界（未做的事）

1. **生成的是骨架，不是成品**。结构（事件、频率、hook 组合、基类、`.h`/`.cpp` 归属）由解析结果自动填对，
   但语义——发动条件、结算内容、AI 的价值判断——一律留成显式 `TODO`。
   这部分无法从中文描述机械推导，必须有模型或人工介入。
2. **解析器是关键词规则，不是语义理解**。描述写法超出规则表时（生僻措辞、双重否定、条件嵌套）
   会落到"待定"并提示人工判读，而不是硬猜。这是有意设计。
3. **不编译、不做语义校验**。`inspect_skill.py` 的"三处齐备"只等于拼写与结构对齐。
4. **`assets/templates/` 未补齐**。ViewAsSkill 族与规则修正型的骨架现在由 `scaffold_skill.py` 直接输出，
   模板目录里仍是手写时代的 3 个文件，存在功能重叠。可以后续把模板收敛为"生成器的形态说明"。
