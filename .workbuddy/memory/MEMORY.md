# QSanguosha-For-Hegemony-Qt-upgrade 核心开发与 AI 校验备忘

## 1. 架构与运行环境要点
- **跑批工作目录**：实际测试跑批目录为 `build-QSanguosha-Desktop_Qt_5_14_2_MinGW_64_bit-Debug/debug/`（或同等级 Debug 目录）。源码树 `lua/ai/` 更新后，必须同步到部署树下的 `debug/lua/ai/`，否则游戏运行时加载的仍是旧版 AI。
- **Lua 私有拓展语法**：QSanguosha 内置 Lua 5.1 解析器被打上了 `continue` 关键字补丁。离线编译器检查 Lua 语法时，需将 `\bcontinue\b` 预替换为 `do end` 空块，避免误报 syntax error。

## 2. Bot AI 生成与校验规范 (qsgs-skill-generator)
- **键名归一化匹配规则**：
  - `dash_under` (中划线转下划线)：`ai_skill_invoke`, `ai_skill_cardchosen`, `ai_skill_cardschosen`, `ai_skill_askforag`, `ai_skill_playerchosen`
  - `verbatim` (逐字原样保留)：`ai_skill_choice`, `ai_skill_discard`, `ai_skill_exchange`, `ai_skill_suit`
  - `prompt_probe` (冒号前缀截取)：`ai_skill_cardask` (匹配 `prompt:split(":")[1]`)
  - `verbatim_pattern/class`：`ai_skill_use` (如 `"@@skill"`), `ai_skill_use_func` (卡牌类名)
- **C/Lua 跨语言调用反死锁准则**：
  - 在 `ai_skill_invoke` 内调用 `self:isFriend()`、`self:isEnemy()`、`self:getCardsNum()` 等可能穿透回 C++ `relationTo` 并再次触发询问的方法时，**必须**加 `local xxx_invoking = false` 护栏，防止 C 栈溢出 (0xC00000FD 崩溃，家族C)。
- **返回值契约**：
  - `ai_skill_exchange` / `ai_skill_cardschosen` 在无可用牌时必须返回空表 `{}`，严禁返回 `nil`，否则触发 C++ 解包断言崩溃 (家族A)。
