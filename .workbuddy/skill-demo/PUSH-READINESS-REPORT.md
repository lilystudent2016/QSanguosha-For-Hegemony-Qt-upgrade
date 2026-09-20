# 推送前检查报告 · 2026-09-20（第二轮）

> 范围：① 再次校验已生成 Bot Lua 代码的正确性；② 盘点本仓库中自动生成/修改的资料，判定隐私风险与保留/忽略；③ 梳理推送到 `origin/newai` 的可行性。
> **本报告只做检查与建议，未执行任何 push / commit / 分支切换。**

---

## 一、再次校验：已生成 Bot Lua 代码正确性

本轮在上一轮基础上新增了 **3 项独立检查**（补丁合并性、HEAD 回归对比、全量语法编译），工具与结果如下。

| # | 检查项 | 工具 | 结果 | 判定 |
|---|---|---|---|---|
| 1 | 语法编译（QSanguosha 私有 `continue` 已做 `do end` 等价替换） | `check_lua.py` | **22/22 个 `lua/ai/*.lua` 全部 OK** | ✅ |
| 2 | 键名 ↔ C++ `askFor*` 调用点对齐 | `verify_bot_lua.py` | **注册 105 · 命中 105 · 未命中 0** | ✅ |
| 3 | `self:xxx` API 是否存在于部署树 SmartAI（202 个方法） | `verify_bot_lua.py` | **可疑调用 0** | ✅ |
| 4 | **【新增】补丁是否完整合并进 live 树** | `check_patch_merge.py` | **105/105 已合并，0 未合并** | ✅ |
| 5 | **【新增】相对 HEAD 是否覆盖/丢失原有 AI** | `check_dup_origin.py` | **新增 105 · 覆盖 0 · 丢失 0** | ✅ 纯增量 |
| 6 | 家族 C（C 栈重入） | `verify_bot_lua.py` | **3 条全部 `severity=OK`（护栏已生效）** | ✅ |
| 7 | 家族 A / NIL 告警复核 | 人工逐条 + C++ 调用点取证 | **14 条全部为误报（见下）** | ✅ |

### 1.1 四条已修复缺陷的状态确认（文件:行）

| 编号 | 位置 | 内容 | 当前状态 |
|---|---|---|---|
| R1 | `lua/ai/mol-ai.lua:445-454` | `juzhan` 重入护栏 `local juzhan_invoking` | ✅ 已生效 |
| R2 | `lua/ai/mol-ai.lua:626-646` | `xiaoqi` 重入护栏 `local xiaoqi_invoking` | ✅ 已生效 |
| R3 | `lua/ai/lord_ex-ai.lua:3097-3108` | `wuyan` 重入护栏 `local wuyan_invoking` | ✅ 已生效 |
| R4 | `lua/ai/mol-ai.lua`（`biaozhao_give`） | `return nil` → `return {}` | ✅ 已生效 |

补丁源 `.workbuddy/skill-demo/lua-patch/*.patch.lua` 与 live 树内容一致（第 4 项检查已验证）。

### 1.2 家族 A / NIL 14 条告警逐条取证（结论：全部误报）

| 补丁位置 | 告警内容 | 取证 | 结论 |
|---|---|---|---|
| `jiange-defense-ai.patch.lua:48` | exchange 返空表 + `cards[1]` | `jiange-defense.cpp:2214` 有 `!target->isNude()` 守卫 | 安全 |
| `mol-ai.patch.lua:225` | 同上（`biaozhao_give`） | `mol.cpp:2833` `source->isNude()` + `2836` `cards.isEmpty()` 双重守卫 | 安全（另已加 R4 防御） |
| `mol-ai.patch.lua:10` | `cards[1]` | `askForAG` 的 `card_ids` 由引擎保证非空 | 安全 |
| `mol-ai.patch.lua:212` | `cards[1]/[2]` | 同行上方 `#cards < 2 then return {}` | 安全 |
| `mol-ai.patch.lua:294` | `cards[1]/[2]` | 上方 `if #cards < 2 then return "."` | 安全 |
| `momentum-ai.patch.lua:10` | `cand[1]` | 上方 `if #cand == 0 then return "."` | 安全 |
| `standard_cards-ai.patch.lua:9` | `cards[1]` | 上方 `getHandcardNum() <= 1 then return {}` | 安全 |
| `lord_ex-ai.patch.lua:161` | `cand[1]` | 上方 `#cand == 0 then return "."` | 安全 |
| `manoeuvre-ai.patch.lua:35` | `data:toPlayer()` 未判 nil | **第 38 行已有 `if not target then`** | 安全（检测正则未覆盖 `if not x`） |

### 1.3 一个仍需知悉的运行期风险（非代码缺陷）

部署落差依旧存在：源码树 `lua/ai/` 12 个文件与跑批实际加载的 `build-QSanguosha-Desktop_Qt_5_14_2_MinGW_64_bit-Debug/debug/lua/ai/` **全部 DIFF**。
跑批前需执行 `.workbuddy/skill-demo/sync_to_deploy.py`（会自动备份原文件到 `lua_ai_backup_prepatch/`）。

---

## 二、资料盘点：隐私 / 保留 / 忽略

### 2.1 隐私扫描（脚本 `scan_privacy_assets.py`，覆盖 .workbuddy 全部 71 个文本文件 + skill 目录 13 个文件）

| 敏感项 | 命中数 | 说明 |
|---|---|---|
| 硬编码口令 / 密钥 / token / PAT / 私钥 | **0** | 无 |
| 邮箱地址 | **0** | 无 |
| Bearer 令牌 / OpenAI 密钥 | **0** | 无 |
| IPv4 地址 | 0（仓库）/ 2（skill，均为 `0.0.0.0` 绑定地址） | 无风险 |
| **Windows 绝对路径（`C:\Users\Administrator\...`）** | **仓库 35 处 + skill 3 处** | ⚠️ 唯一需处理项：泄露本机账号名 `Administrator` 与目录布局 |

**结论：无密钥、无口令、无邮箱、无令牌类敏感信息。** 唯一"半隐私"是本机绝对路径中的用户名 `Administrator`（通用名，风险低；若介意可做脱敏替换）。

### 2.2 分类清单

#### ✅ 关键、建议保留并入库

| 路径 | 说明 |
|---|---|
| `lua/ai/*.lua`（12 个改动文件） | **核心交付**：105 个 AI hook 补全 + 4 处缺陷修复 |
| `src/tools/record-dump.{cpp,h}` | 录像局面导出工具（AI 训练数据采集基础设施，当前未跟踪） |
| `src/server/*`、`src/core/player.cpp`、`src/main.cpp` 等 C++ 改动 | A1 跑批插桩与崩溃修复 |
| `.workbuddy/skill-demo/lua-patch/*.patch.lua`（11 个） | 生成源，便于追溯与复查 |
| `.workbuddy/skill-demo/*.py`（8 个校验/修复脚本） | 可复用工具链 |
| `.workbuddy/skill-demo/AI-BOT-CORRECTNESS-REPORT.md`、`AI-补全报告.md` | 结论性文档 |
| `.workbuddy/memory/*.md` | 项目长期记忆（含规范约定） |

#### ❌ 建议忽略（不入库）

| 路径 | 原因 |
|---|---|
| `QSanguosha.pro.user` | Qt Creator 本机配置，含绝对路径/环境 UUID |
| `sanguosha.qm` | lrelease 生成的二进制翻译产物 |
| `lua/ai/overseas-ai.lua.a1bak-20260920` | 临时备份 |
| `swig/sanguosha_wrap.cxx` | **SWIG 自动生成，3.2 MB / 103,308 行**；HEAD 中是 0 字节占位，入库会塞入 10 万行生成码 |
| `.workbuddy/skill-demo/audit/*`（`audit.json` 602 KB、`audit-after.json` 584 KB、`missing-context.txt` 133 KB 等） | 中间日志/大 JSON，可再生 |
| `.workbuddy/skill-demo/*.bak`（manoeuvre/newsgs 备份） | 中间备份 |
| `.../freekill-skill-generator/.cache/corpus.json` | **5.69 MB 缓存**，若复制 skill 进仓库必须排除 |

#### ⚠️ 建议脱敏后保留

报告与脚本中的 `C:\Users\Administrator\code\...` → 可替换为相对路径或 `<repo-root>`（共约 35 处，可脚本批量替换）。

---

## 三、Git 现状与推送风险（**重要**）

| 项 | 值 |
|---|---|
| 当前本地分支 | **`Qt5.14`** |
| 远程 | `origin → https://github.com/lilystudent2016/QSanguosha-For-Hegemony-Qt-upgrade.git` |
| 远程已有分支 | `master`、`Qt5.14`、`Qt5.15`、`newai`（HEAD 指向 `Qt5.15`） |
| `origin/newai` vs 当前 HEAD | **领先 34 个提交 / 落后 9 个提交**（`git rev-list --left-right --count`） |
| 两分支差异规模 | **约 987 个文件**（含大量 `audio/*`、`image/*` 二进制、`lang/zh_CN/**`、`src/package/**`、`swig/*`） |

### ⚠️ 风险提示

1. **直接 `git push origin Qt5.14:newai` 会被拒绝（non-fast-forward）**，强行 `--force` 会**丢弃 `origin/newai` 上独有的 34 个提交**，其中包括大量美术/音频/lang/包代码改动，且不可逆。
2. `origin/newai` 上还有一份 `.qoder/repowiki/**`（约 243 个中文 wiki 文档），force push 会一并抹掉。
3. 工作区中 `swig/sanguosha_wrap.cxx` 若被提交，会一次性写入 **103,308 行 / 3.2 MB** 的生成代码。

### 可选方案（需你定夺）

| 方案 | 做法 | 风险 |
|---|---|---|
| **A（推荐）** 新开分支推送 | `git checkout -b newai-ai-20260920` → 只提交 AI 相关改动 → `git push -u origin newai-ai-20260920` | 零风险，不动 `newai` |
| **B** 合并到 newai | 本地 `git checkout newai`（跟踪 origin/newai）→ `git merge Qt5.14` → 解冲突 → 普通 push | 冲突多（987 文件），需逐个裁定 |
| **C** 强推覆盖 newai | `git push -f origin Qt5.14:newai` | ⛔ 丢弃 34 个提交，不可逆，**不推荐** |

---

## 四、关于"大模型生成的 skill 能否推送到 GitHub"

- skill 实际存放在 **`C:\Users\Administrator\.workbuddy\skills\qsgs-skill-generator\`**（用户级目录，**不在本仓库内**，因此不会随本次提交走）。
- 体积约 **225 KB / 13 个文件**（`SKILL.md` 24 KB + `references/` 7 篇 + `scripts/` 4 个 + `assets/templates/` 6 个），**无密钥/邮箱/令牌**，可安全公开。
- 若要推送，需先**复制进仓库**（建议放 `tools/skill/qsgs-skill-generator/` 或 `.workbuddy/skills/qsgs-skill-generator/`），复制时务必排除：
  - `freekill-skill-generator/.cache/corpus.json`（5.69 MB）
  - skill 内 3 处 `C:\Users\Administrator\...` 路径（可先脱敏）
- **注意**：`references/ruleset-baseline.md` 指向本地规则知识库 `C:\Users\Administrator\code\code_sgs\`（仓库根有 `CC BY-NC-ND 4.0` 声明）。若其中含官方规则集**大段原文摘录**，公开再分发前请确认不违反 NC/ND 条款；稳妥做法是只保留"索引 + 用法说明"，把原文摘录删除。

---

## 五、建议增补的 `.gitignore`（待你确认后再写入）

```gitignore
tools/swig/                    # 已有

# --- 本机 / 构建产物 ---
*.pro.user*
*.qm
debug/
build-*/
*.a1bak-*

# --- 自动生成的大型包装代码 ---
swig/sanguosha_wrap.cxx

# --- 工作区中间产物（如需保留文档请勿加这一行）---
# .workbuddy/**/audit/
# .workbuddy/**/*.bak
```

---

## 六、待你确认的 3 件事

1. **推送方式**：A 新分支 / B 合并进 newai / C 强推覆盖？
2. **自动生成资料是否入库**：`.workbuddy/` 全量入库 / 只入库文档与脚本（排除 audit 大 JSON）/ 完全不入库？
3. **skill 是否复制进仓库一并推送**？
