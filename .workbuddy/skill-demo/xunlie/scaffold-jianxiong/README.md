# 奸雄（`jianxiong`）生成说明

> 自动解析结果。骨架里的结构已按描述填好，**语义部分留成 TODO**。

| 要素 | 判定 |
|---|---|
| 形态 | 触发技 |
| 建议基类 | `MasochismSkill` |
| 可选性 | 可选 |
| 频率 | `Skill::NotFrequent` |
| 事件 | `Damaged` |
| 需技能卡 | 否 |

## 生成的文件与落点

- `jianxiong.cpp` → src/package/standard.cpp（技能类）
- `jianxiong.lang.lua` → lang/zh_CN/Package/<LangFile>.lua 的条目内容
- `jianxiong-ai.lua` → lua/ai/standard-ai.lua（AI hook）

## 还要做的事

- [ ] 把 C++ 粘进 `src/package/<pkg>.cpp`，技能卡类粘进 `.h`（如有）
- [ ] 在包构造函数里 `addMetaObject<XxxCard>();`（如有技能卡）
- [ ] 在武将注册函数里 `addSkill(new Jianxiong);`
- [ ] 把 lang 条目追加到 `lang/zh_CN/Package/<LangFile>.lua`（落点先 grep 兄弟技能确认）
- [ ] 把 AI 追加到 `lua/ai/<pkg>-ai.lua`
- [ ] 新增文件时补进 `QSanguosha.pro` 的 SOURCES / HEADERS
- [ ] 补全所有 TODO 注释处的语义判断
- [ ] 跑 `python scripts/inspect_skill.py jianxiong` 自检三处是否对齐
