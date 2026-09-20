# 巡猎（`xunlie`）生成说明

> 自动解析结果。骨架里的结构已按描述填好，**语义部分留成 TODO**。

| 要素 | 判定 |
|---|---|
| 形态 | 主动技 |
| 建议基类 | `ViewAsSkill` |
| 可选性 | 可选 |
| 频率 | `Skill::NotFrequent` |
| 事件 | `—` |
| 需技能卡 | 是（`XunlieCard`） |

## 生成的文件与落点

- `xunlie.h` → src/package/demo.h（技能卡声明）
- `xunlie.cpp` → src/package/demo.cpp（技能类）
- `xunlie.lang.lua` → lang/zh_CN/Package/<LangFile>.lua 的条目内容
- `xunlie-ai.lua` → lua/ai/demo-ai.lua（AI hook）

## 还要做的事

- [ ] 把 C++ 粘进 `src/package/<pkg>.cpp`，技能卡类粘进 `.h`（如有）
- [ ] 在包构造函数里 `addMetaObject<XunlieCard>();`（如有技能卡）
- [ ] 在武将注册函数里 `addSkill(new Xunlie);`
- [ ] 把 lang 条目追加到 `lang/zh_CN/Package/<LangFile>.lua`（落点先 grep 兄弟技能确认）
- [ ] 把 AI 追加到 `lua/ai/<pkg>-ai.lua`
- [ ] 新增文件时补进 `QSanguosha.pro` 的 SOURCES / HEADERS
- [ ] 补全所有 TODO 注释处的语义判断
- [ ] 跑 `python scripts/inspect_skill.py xunlie` 自检三处是否对齐

## 解析器给的额外提示

- 描述里出现 ▶ / 然后，可能含两个结算点 → 考虑拆成主技能 + `#` 前缀内部触发技
- 含「选择一项」 → 需要 askForChoice，AI 配 sgs.ai_skill_choice.xunlie
