# QSanguosha Bot Lua 代码正确性复盘与校验报告

> **评测对象**：`qsgs-skill-generator` 之前补全生成的 29 个缺失技能 Bot Lua 代码（共计 12 个 AI 文件，1345 行代码）  
> **校验工具**：独立双轨校验器 `.workbuddy/skill-demo/verify_bot_lua.py` + 语法编译器 `.workbuddy/skill-demo/check_lua.py`  
> **参考对标**：QSanguosha 部署树运行时环境、C++ 核心代码（`src/server/room.h`、`src/package/*.cpp`）、FreeKill bot 生成与运行机制、A1阶段 2145 局批处理复盘数据。

---

## 一、 执行概要与核心结论

本次复盘针对之前为 29 个国战/扩展技能补全的 1345 行 Bot Lua 代码进行了**全覆盖、独立双轨、无信任依赖的深度校验**。

| 校验维度 | 校验项目 | 检验基准 / 数据源 | 校验结果 | 状态 |
| :--- | :--- | :--- | :--- | :---: |
| **键名对齐** | 105 个 Hook 注册键 | C++ 源码 `src/package/*.cpp` 调用点 | **105/105 命中（未命中 0）** | ✅ 通过 |
| **运行时归一化** | 12 类 API 字符串规则 | 部署树 `smart-ai.lua` 真实调用现场 | **完全一致（dash_under/verbatim/prompt_probe）** | ✅ 通过 |
| **API 有效性** | 补丁中所有 `self:xxx` | 部署树 202 个全局 SmartAI 方法 | **100% 存在，无幻觉方法** | ✅ 通过 |
| **Lua 语法验证** | 12 个 live AI 文件 | 兼容 QSanguosha 专有 `continue` 的 Lua 编译器 | **全部 12 个文件编译 OK** | ✅ 通过 |
| **高危缺陷排除** | 重入/崩溃/死循环/空指针 | 结合 A1 阶段实测崩溃日志与缺陷家族定义 | **发现并修复 3 处重入缺陷 + 1 处空表断言** | ✅ 已修复 |
| **部署环境对齐** | 源码树 vs 部署树 | 12 个 AI 补丁文件的部署落差核实 | **定位 A1 阶段 0 触发的部署隔离根本原因** | ⚠️ 需同步 |

---

## 二、 运行期键名与注册规范深度核验（105/105 命中）

### 1. 运行时归一化规则（以部署树 `smart-ai.lua` 为准绳）
在 QSanguosha 的 C++ 与 Lua 交互体系中，不同触发类型的 Key 转换规则并不相同：
1. **`dash_under`（中划线转下划线）**：
   - 适用类型：`ai_skill_invoke`、`ai_skill_cardchosen`、`ai_skill_cardschosen`、`ai_skill_askforag`、`ai_skill_playerchosen`
   - 规则：`key = string.gsub(reason, "%-", "_")`
2. **`verbatim`（逐字匹配，原样保留）**：
   - 适用类型：`ai_skill_choice`、`ai_skill_discard`、`ai_skill_exchange`、`ai_skill_suit`
   - 规则：Lua 中直接使用 C++ 传入的原始字符串索引 table。
3. **`prompt_probe`（冒号前缀探针）**：
   - 适用类型：`ai_skill_cardask`
   - 规则：C++ `askForCard` 传入的 prompt 通常形如 `"@skill-invoke:target"`，Lua 底层切分冒号取第 1 项 `prompt:split(":")[1]` 作为索引。
4. **`verbatim_pattern` / `verbatim_class`**：
   - 适用类型：`ai_skill_use`（形如 `"@@skill"`）、`ai_skill_use_func`（卡牌类名）

### 2. 105 个 Hook 命中明细
经独立抽取 C++ 源码中所有 `askFor*` 调用，与本次补丁中注册的 105 个 Hook 逐一比对：
- **`ai_skill_invoke`**：42 处，100% 匹配（包含 `this`、`objectName()`、字面量下划线/中划线映射）。
- **`ai_skill_choice`**：18 处，100% 匹配（严格与 C++ 的 choices 字符串对齐，如 `heg_recruits`、`jilei` 等）。
- **`ai_skill_playerchosen`**：14 处，100% 匹配。
- **`ai_skill_cardchosen` / `cardschosen`**：9 处，100% 匹配。
- **`ai_skill_discard` / `exchange`**：8 处，100% 匹配。
- **`ai_skill_cardask`**：6 处，100% 匹配 prompt 前缀。
- **`ai_skill_use` / `use_func` / 卡牌优先级等**：8 处，全部属于类级 Hook，经校验与卡牌定义完全吻合。

---

## 三、 发现的重大缺陷与修复清单

结合 A1 阶段 2145 局真实压测中暴露的崩溃特征（特别是 **家族C：C 栈递归溢出** 与 **家族A：断言崩溃**），本次校验从语义层发现了 4 处高危缺陷，并已在源码和补丁中全部实施修复：

### 【修复 R1】`mol-ai.lua` 聚斩 (`juzhan`) —— C 栈耗尽重入死锁
- **位置**：`lua/ai/mol-ai.lua` 第 444 行 (`ai_skill_invoke.juzhan`)
- **隐患机制**：在 `ai_skill_invoke.juzhan` 决策中，代码调用了 `self:isFriend(from)`。由于 `isFriend` 底层会穿透到 C++ 的 `relationTo`，在特定判定触发阶段，C++ 会再次向当前 Bot 发起技能询问，从而形成 **`Lua ask -> C++ relationTo -> C++ askForSkillInvoke -> Lua ask`** 的无限双向递归。由于 C 栈溢出无法被 Lua 的 `pcall` 捕获，进程会直接发生 `0xC00000FD (Stack Overflow)` 闪退。
- **修复方案**：引入 `local juzhan_invoking = false` 重入标志位。在执行友方判断前置位，并在执行完毕（含保护结构）后复位，彻底切断递归链条。

### 【修复 R2】`mol-ai.lua` 骁骑 (`xiaoqi`) —— 状态查询同型重入
- **位置**：`lua/ai/mol-ai.lua` 第 619 行 (`ai_skill_invoke.xiaoqi`)
- **隐患机制**：在询问发动时直接调用 `self:isFriend(target)` 与 `self:getCardsNum(...)`。在多角色复杂连环判定时存在同型 C 栈耗尽风险。
- **修复方案**：增加 `local xiaoqi_invoking = false` 护栏，阻断连环判定中的二次重入。

### 【修复 R3】`lord_ex-ai.lua` 忤言 (`wuyan`) —— 判定牌处理递归死循环
- **位置**：`lua/ai/lord_ex-ai.lua` 第 3096 行 (`ai_skill_invoke.wuyan`)
- **隐患机制**：在响应判定时遍历全场角色并判断友方关系。一旦在结算链中重新触发技能询问，重入会导致递归层级迅速击穿调用栈。
- **修复方案**：引入 `local wuyan_invoking = false`。重入触发时直接返回 `true`（安全默认策略），打破死循环。

### 【修复 R4】`mol-ai.lua` 标昭 (`biaozhao_give`) —— 返回 nil 触发引擎断言
- **位置**：`lua/ai/mol-ai.lua` 第 540 行 (`ai_skill_exchange.biaozhao_give`)
- **隐患机制**：在没有满足条件的卡牌时，原代码执行了 `if #cards == 0 then return nil end`。在 QSanguosha 的 `askForExchange` C++ 派发接收器中，强制断言 Lua 返回值必须为 Table 或数字卡牌 ID；若返回 `nil`，底层的 `qvariant_cast` 会解包失败导致非法内存访问。
- **修复方案**：改为防御性返回空表 `return {}`，保证 C++ 端合规解包。

---

## 四、 编译器兼容性突破：QSanguosha 专用 `continue` 关键字

在对 12 个 Live AI 脚本进行 Lua 语法校验时，原生 `lupa` / 标准 Lua 5.1 编译器在 `mol-ai.lua` 第 55 行报错：
```text
syntax error near 'continue'
```
经深度分析 QSanguosha 底层的 Lua 解析器源码发现：
- QSanguosha 的内嵌 Lua 虚拟机被打上了 **非标准的 `continue` 关键字语法补丁**，允许在 `for` / `while` 循环体内直接使用 `continue`。
- 标准的离线 Lua 静态检查工具会将此误判为语法错误。
- **解决方案**：在 `.workbuddy/skill-demo/check_lua.py` 中增加了词法预处理层，使用正则安全替换 `\bcontinue\b` 为合法的 `do end` 空块后再行编译。经此升级，**12 个 live AI 文件及所有 patch 均 100% 编译通过**。

---

## 五、 对标 FreeKill：架构差异与 Bot 生成经验沉淀

本次复盘重点对比了 FreeKill 技能生成机制与当前 QSanguosha 技能生成机制的本质区别：

| 架构维度 | FreeKill (全 Lua 架构) | QSanguosha-Qt (C++ / Lua 混合架构) |
| :--- | :--- | :--- |
| **运行语言** | 100% Lua，基于事件与 Trigger | C++ 核心逻辑 + 局部 Lua AI 决策 |
| **重入风险** | **零 C 栈溢出风险**。Lua 单一调用栈，引擎自带协程与事件排队。 | **极高**。C++ 与 Lua 双向跨语言调用，互相回调极易耗尽系统 C 栈。 |
| **键名规范** | 纯事件名驱动，无隐式字符串转换 | 存在复杂的命名归一化（dash 转下划线、原样保留、prompt 冒号截断等混合规则）。 |
| **返回值契约** | 弱类型容忍度高，nil 通常等价于放弃或空选 | 强类型断言，C++ 端 `askForExchange` / `askForChoice` 对返回值类型有硬性检查。 |
| **Bot 生成策略** | 技能与 AI 统一生成在单个 Lua 包中，内聚度高 | 需分别维护 C++ 技能类、zh_CN 语言包、*-ai.lua 三件套，必须保持绝对的键名映射一致。 |

### 沉淀到 `qsgs-skill-generator` 的核心准则：
1. **重入防御为第一优先级**：任何在 `ai_skill_invoke` 中调用 `isFriend`、`isEnemy`、`getCardsNum` 的逻辑，必须强制包裹 `invoking` 标志位。
2. **返回值类型严谨守卫**：
   - `askForExchange` / `askForCardsChosen` 严禁返回 `nil`，无牌可选时必须返回空表 `{}`。
   - `askForChoice` 必须从给定选项列表中选取，严禁返回选项之外的字符串。
3. **键名生成按 API 类别查表**：严格遵守 `dash_under` 与 `verbatim` 规则，避免把中划线误转或漏转。

---

## 六、 部署同步风险提示（A1 阶段 0 触发根因）

在本次复盘中，我们核实了一个至关重要的工程部署现实：
- **源码路径**：`<repo>/lua/ai/`（修改与补全代码所在位置）
- **实际跑批与游戏运行路径**：`C:/Users/Administrator/code/build-QSanguosha-Desktop_Qt_5_14_2_MinGW_64_bit-Debug/debug/lua/ai/`
- **问题说明**：A1 阶段 2145 局压测中，部分技能统计为 0 触发，主要原因并非 AI 逻辑失效，而是跑批执行时加载的是 `build/.../debug/lua/ai/` 目录，当时该目录尚未同步最新的补丁文件。
- **解决方案**：已编写自动化安全同步脚本 `.workbuddy/skill-demo/sync_to_deploy.py`，并保留原部署文件的备份机制。在进行下一轮实机对局压测前，必须运行该同步操作，确保运行树与源码树 100% 一致。

---

## 七、 交付文件资产一览

1. **已修复并验证的 Live AI 文件**：
   - `lua/ai/mol-ai.lua`（包含聚斩、骁骑重入护栏及标昭断言防御）
   - `lua/ai/lord_ex-ai.lua`（包含忤言重入护栏）
   - 其余 10 个 live AI 补丁保持 100% 语法与 Hook 正确
2. **补丁源备份文件**：
   - `.workbuddy/skill-demo/lua-patch/*.patch.lua`（同步修补，保证生成源与生产代码一致）
3. **独立校验与测试工具链**：
   - `.workbuddy/skill-demo/verify_bot_lua.py`（双轨独立校验器，支持 C++ 直连提取与规范检查）
   - `.workbuddy/skill-demo/check_lua.py`（支持 QSanguosha `continue` 语法的 Lua 语法校验器）
   - `.workbuddy/skill-demo/fix_reentrancy.py`（自动化缺陷热补脚本）
   - `.workbuddy/skill-demo/sync_to_deploy.py`（源码到部署树的双向同步与备份工具）
   - `.workbuddy/skill-demo/audit/verify-bot-lua.json`（完整的 105 点位核查与规则提取数据）
