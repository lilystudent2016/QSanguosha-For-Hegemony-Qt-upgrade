#!/usr/bin/env python3
"""全项目「技能 → Lua AI」覆盖审计。

判定逻辑（不靠中文猜测，靠 C++ 里实际调用的询问 API 反推）：

    引擎在技能 C++ 里每调用一次 room->askForXxx(...)，就必然要在 Lua AI 里
    提供对应的 sgs.ai_xxx.<reason>，否则 AI（托管玩家）走到这一步只能瞎选或
    卡住。所以：

        扫描技能类体内的 askFor* 调用  →  推导必需的 AI hook  →  查 lua/ai 是否存在

    另外两种形态不经过 askFor，需要单独判定：
        视为技（ViewAsSkill 族）      →  需要 sgs.ai_view_as.<skill>
        技能卡（XxxCard）            →  需要 sgs.ai_skills + sgs.ai_skill_use_func.<CardClassName>
        规则修正技（Distance/MaxCards/AttackRange/Prohibit/TargetMod）
                                      →  引擎直接生效，不需要 AI（但可配意图提示）

用法：
    python audit_ai.py --root <项目根>                # 全量审计，输出汇总 + 缺失清单
    python audit_ai.py --root <项目根> --json         # 机器可读
    python audit_ai.py --root <项目根> --skill jianxiong   # 审计单个技能
    python audit_ai.py --root <项目根> --package standard  # 只审计某个 package

只读操作，不修改任何文件。
"""

import argparse
import json
import os
import re
import sys

# --------------------------------------------------------------------------
# askFor API → (必需的 AI hook, reason 参数下标)
# 下标是该 API 形参里 "reason / skill_name" 的位置（从 0 计）。
# 参考 src/server/room.h 的声明。
# --------------------------------------------------------------------------
ASK_MAP = {
    "askForSkillInvoke": ("ai_skill_invoke", 1),
    "askForChoice": ("ai_skill_choice", 1),
    "askForPlayerChosen": ("ai_skill_playerchosen", 2),
    "askForPlayersChosen": ("ai_skill_playerchosen", 2),
    "askForDiscard": ("ai_skill_discard", 1),
    "askForExchange": ("ai_skill_exchange", 1),
    "askForPindian": ("ai_skill_pindian", 2),
    "askForPindianRace": ("ai_skill_pindian", 2),
    "askForCardChosen": ("ai_skill_cardchosen", 3),
    "askForCardsChosen": ("ai_skill_cardschosen", 3),
    "askForAG": ("ai_skill_askforag", 3),
    "askForMoveCards": ("ai_skill_movecards", 4),
    "askForSuit": ("ai_skill_suit", 1),
    "askForYiji": ("ai_skill_askforyiji", 2),
    "askForCard": ("ai_skill_cardask", 4),
    "askForCardShow": ("ai_skill_cardshow", 0),
    "askForArrangeCards": ("ai_skill_cardchosen", 3),
    "askForGongxin": ("ai_skill_cardchosen", 2),
}

# 这些 askFor 是房间级流程（选将/选国/方向/紫微），不属于某个技能的 AI
ROOM_LEVEL_ASK = {
    "askForGeneral", "askForGeneralShow", "askForKingdom", "askForDirection",
    "askForOrder", "askForLuckCard", "askForSurrender", "askForTriggerOrder",
    "askForNullification", "askForUseCard", "askForUseSlashTo", "askForCardOrUseCard",
    "askForSinglePeach", "askForGuanxing", "askForQiaobian",
    "askForQiaobianTargetsChosen", "askForRende", "askForTransferFieldCard",
    "askForTransferFieldCards",
}

# 规则修正技基类：引擎直接读数值，不需要 AI 决策
# FilterSkill 也归此类：它只是让引擎换个花色/牌名看待某张牌（如红颜），
# 是被动生效的，不存在"AI 要不要用"的决策，因此不需要任何 AI 注册。
RULE_BASES = {
    "DistanceSkill", "MaxCardsSkill", "AttackRangeSkill", "ProhibitSkill",
    "InvaliditySkill", "ViewHasSkill", "TargetModSkill", "AttackRangeSkill",
    "FilterSkill",
}

# 视为技基类（需要 AI 注册才可能被使用）
VIEWAS_BASES = {"ViewAsSkill", "OneCardViewAsSkill", "ZeroCardViewAsSkill"}

# 视为技产生"技能卡"时，AI 需要按卡类名注册 ai_skill_use_func
RESPONSE_PATTERN_RE = re.compile(r'response_pattern\s*=\s*"([^"]+)"')
NEW_CARD_RE = re.compile(r'\bnew\s+([A-Za-z_]\w*Card)\b')

# 缺失 AI 时的严重度分级（依据 smart-ai.lua 里各 hook 的实际兜底行为）
#
# 致命：引擎兜底会让技能彻底失效或做出明显错误的选择
#   ai_skill_invoke   —— 兜底只在 frequency==Frequent 时返回 true，其余返回 nil（=不发动）
#                        ⇒ 非 Frequent 技能若不配，AI 永远不用这个技能
#   ai_skill_choice   —— 兜底优先选 "cancel"/"no"，否则随机 ⇒ 技能可能永远不生效
#   ai_skill_exchange —— 兜底直接返回 {} ⇒ 交易类技能彻底不发动
#   ai_skill_cardask  —— 兜底走通用 response 逻辑，多数技能语境下会出错
# 降级：引擎有可用的通用启发式，技能照常工作，只是选择不够聪明
#   ai_skill_discard / ai_skill_playerchosen / ai_skill_cardchosen /
#   ai_skill_cardschosen / ai_skill_askforag / ai_skill_movecards / ai_skill_suit
FATAL_HOOKS = {
    "ai_skill_invoke", "ai_skill_choice", "ai_skill_exchange", "ai_skill_cardask",
}
DEGRADED_HOOKS = {
    "ai_skill_discard", "ai_skill_playerchosen", "ai_skill_cardchosen",
    "ai_skill_cardschosen", "ai_skill_askforag", "ai_skill_movecards",
    "ai_skill_suit", "ai_skill_cardshow", "ai_skill_pindian", "ai_skill_askforyiji",
}

# 技能基类全集（用于识别 C++ 里哪些类是真技能）
SKILL_BASES = {
    "TriggerSkill", "MasochismSkill", "PhaseChangeSkill", "DrawCardsSkill",
    "GameStartSkill", "ViewAsSkill", "OneCardViewAsSkill", "ZeroCardViewAsSkill",
    "FilterSkill", "DistanceSkill", "MaxCardsSkill", "AttackRangeSkill",
    "ProhibitSkill", "InvaliditySkill", "ViewHasSkill", "TargetModSkill",
    "Skill", "LordSkill", "BattleArraySkill", "ArraySummonCard",
}

# 这些基类的类不是"技能"，不参与 AI 审计：
#   Package  —— 武将包/牌堆包注册类（: Package("lord_ex")），没有 AI 可言
#   Card 系  —— 牌类
#   GameRule —— 规则类
NON_SKILL_BASES = {
    "Package", "CardPack", "GameRule", "Scenario",
    "Card", "BasicCard", "TrickCard", "EquipCard", "Weapon", "Armor",
    "Horse", "Treasure", "DummyCard",
}

# 视为技产生的通用容器卡，不是真正的"技能卡"，不参与技能卡审计
GENERIC_CARDS = {"DummyCard"}

CPP_DIRS = ["src/package"]
# 询问发起方可能不只写在技能包里（如 @@commandefect! 在引擎 serverplayer.cpp 里发起）
QUEST_DIRS = ["src/package", "src/server"]
AI_DIRS = ["lua/ai", "lua"]
LANG_DIRS = ["lang/zh_CN"]


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def iter_files(root, rel_dir, exts=(".cpp", ".h")):
    base = os.path.join(root, rel_dir)
    if not os.path.isdir(base):
        return
    for dirpath, _d, filenames in os.walk(base):
        for fn in filenames:
            if fn.endswith(exts):
                yield os.path.join(dirpath, fn)


def find_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, "QSanguosha.pro")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def strip_comments(text):
    """把 // 与 /* */ 注释换成等长空格，保持行号与列偏移不变。"""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            if j == -1:
                j = n
            out.append(" " * (j - i))
            i = j
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            seg = text[i:j]
            out.append("".join("\n" if ch == "\n" else " " for ch in seg))
            i = j
        elif c == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                if text[j] == "\n":
                    break
                j += 1
            out.append(text[i:j])
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# ① 扫描 C++：技能类、基类、类体
# --------------------------------------------------------------------------

CTOR_RE = re.compile(r'\b([A-Za-z_]\w*)\s*\(\s*\)\s*\n?\s*:\s*([A-Za-z_]\w*)\s*\(\s*"([^"]+)"')


def scan_cpp_skills(root, cpp_dirs=None):
    """返回 {objectName: [record, ...]}。

    一个 objectName 可能对应多个类（连携技 / 复刻技），全部保留。
    """
    result = {}
    seen = set()
    for rel in (cpp_dirs or CPP_DIRS):
        for path in iter_files(root, rel, exts=(".cpp",)):
            text = strip_comments(read(path))
            relpath = os.path.relpath(path, root).replace("\\", "/")
            lines = text.split("\n")

            # 先建立 类名 → 基类 映射（本文件的 .h 里找）
            hpath = os.path.splitext(path)[0] + ".h"
            htext = strip_comments(read(hpath)) if os.path.isfile(hpath) else ""
            class_base = {}
            for m in re.finditer(r'^\s*class\s+(\w+)\s*(?::\s*public\s+([\w:]+))?', htext, re.M):
                class_base[m.group(1)] = (m.group(2) or "").split("::")[-1]
            # 本 .cpp 里内联声明的类
            for m in re.finditer(r'^\s*class\s+(\w+)\s*(?::\s*public\s+([\w:]+))?', text, re.M):
                class_base.setdefault(m.group(1), (m.group(2) or "").split("::")[-1])

            # 形如  ClassName::ClassName() : Base("name")  或  ClassName() : Base("name")（内联类）
            for m in re.finditer(
                    r'\b([A-Za-z_]\w*)\s*::\s*\1\s*\(\s*\)\s*'
                    r'(?:\n\s*)?:\s*([A-Za-z_]\w*)\s*\(\s*"([^"]+)"\s*\)', text):
                cls, base, name = m.group(1), m.group(2), m.group(3)
                line = text.count("\n", 0, m.start()) + 1
                key = (name, cls, relpath)
                if key in seen:
                    continue
                seen.add(key)
                result.setdefault(name, []).append({
                    "class": cls, "base": base, "file": relpath, "line": line,
                    "span": 0, "rule_modifier": base in RULE_BASES,
                    "viewas": base in VIEWAS_BASES,
                })

            # 内联类：class Xxx : public Base { Xxx() : Base("name") {...} };
            for m in re.finditer(
                    r'^\s*class\s+(\w+)\s*:\s*public\s+(\w+)\s*\{', text, re.M):
                cls, base = m.group(1), m.group(2)
                head = text[m.end():m.end() + 900]
                nm = re.search(r'\b' + re.escape(cls) + r'\s*\(\s*\)\s*:\s*\w+\s*\(\s*"([^"]+)"', head)
                if not nm:
                    continue
                name = nm.group(1)
                line = text.count("\n", 0, m.start()) + 1
                key = (name, cls, relpath)
                if key in seen:
                    continue
                seen.add(key)
                result.setdefault(name, []).append({
                    "class": cls, "base": base, "file": relpath, "line": line,
                    "span": 0, "rule_modifier": base in RULE_BASES,
                    "viewas": base in VIEWAS_BASES,
                })

    # 剔除 Package / Card / GameRule 等非技能类（它们没有 AI 可言）
    for name in list(result.keys()):
        result[name] = [r for r in result[name] if r["base"] not in NON_SKILL_BASES]
        if not result[name]:
            del result[name]

    # 计算每个类在源文件里的实现范围，供后续扫描 askFor 使用
    for name, recs in result.items():
        for rec in recs:
            rec["spans"] = class_spans(root, rec)
            body = class_body_text(root, rec)
            rec["body"] = body
            # 响应式视为技的 pattern：response_pattern 字段 + 类体内出现的 "@@xxx" 字面量
            # （如 shensu 的 @@shensu1/2/3 是在 cost() 里传给 askForUseCard 的）
            pats = set(RESPONSE_PATTERN_RE.findall(body))
            pats.update(re.findall(r'"(@@[^"]+)"', body))
            rec["patterns"] = sorted(pats)
            rec["response_pattern"] = rec["patterns"][0] if rec["patterns"] else ""
            rec["produced_cards"] = sorted(
                c for c in set(NEW_CARD_RE.findall(body)) if c not in GENERIC_CARDS)
            # 技能卡自身的实现区间：askFor 常写在 XxxCard::use 里
            card_spans = []
            for card in rec["produced_cards"]:
                card_spans.extend(find_class_spans(root, card))
            rec["card_spans"] = card_spans
    return result


def _brace_span(text, decl_match):
    """从 class 声明处起，按大括号配对取类体字符区间 (start_offset, end_offset)。"""
    brace = text.find("{", decl_match.end())
    if brace == -1:
        return None
    depth, i, n = 0, brace, len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return (decl_match.start(), i + 1)
        i += 1
    return None


CLASS_DECL_RE = re.compile(r'^\s*class\s+(\w+)\s*(?::\s*public\s+([\w:]+))?', re.M)


def class_spans(root, rec):
    """返回该技能类在源码里占用的区间列表 [(file, start_line, end_line), ...]。

    本项目绝大多数技能类是在 .cpp 里**内联定义**的：
        class Jianxiong : public MasochismSkill { ... };
    少数类声明在 .h、方法在 .cpp 里以 `Cls::method` 外联实现。两种都覆盖。
    """
    out = []
    cls = rec["class"]
    pat = re.compile(r'^\s*class\s+' + re.escape(cls) + r'\b', re.M)

    for rel in (rec["file"], os.path.splitext(rec["file"])[0] + ".h"):
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        text = strip_comments(read(path))
        lines = text.split("\n")
        found_inline = False
        for m in pat.finditer(text):
            span = _brace_span(text, m)
            if not span:
                continue
            found_inline = True
            s = text.count("\n", 0, span[0]) + 1
            e = text.count("\n", 0, span[1]) + 1
            out.append((rel, s, e))

        # 只有在 .cpp 里没找到内联类体时，才认为方法是以 Cls::method 外联实现的。
        # 否则 hits 会命中类体内部的方法名，把后面无关的类一并圈进来。
        if found_inline:
            continue

        qual = re.compile(r'^\s*(?:[\w:*&<>\[\]\s]+?\s+)?' + re.escape(cls) + r'\s*::')
        hits = [i for i, ln in enumerate(lines) if qual.search(ln)]
        if hits:
            i = hits[-1]
            depth = None
            while i < len(lines):
                ln = lines[i]
                if depth is None and "{" in ln:
                    depth = 0
                if depth is not None:
                    depth += ln.count("{") - ln.count("}")
                    if depth <= 0:
                        break
                i += 1
            out.append((rel, hits[0] + 1, min(i + 1, len(lines))))
    return out


def class_body_text(root, rec):
    """返回该技能类体的源码文本（多段则拼接），用于提取视为技特征。"""
    out = []
    for rel, s, e in rec.get("spans") or []:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        lines = strip_comments(read(path)).split("\n")
        out.append("\n".join(lines[max(0, s - 1):e]))
    return "\n".join(out)


_TEXT_CACHE = {}


def _cached_text(path):
    if path not in _TEXT_CACHE:
        _TEXT_CACHE[path] = strip_comments(read(path)) if os.path.isfile(path) else ""
    return _TEXT_CACHE[path]


def find_class_spans(root, cls, cpp_dirs=None):
    """查找任意类（尤其是技能卡类）的全部实现区间。

    技能卡的关键逻辑常常写在 `void XxxCard::use(...)` 这类**外联方法**里
    （如 JianyanCard::use 里的 askForChoice/askForPlayerChosen），
    只看技能类体是扫不到的，所以这里把所有 `Cls::method` 方法体都取出来。
    """
    out = []
    for rel in (cpp_dirs or CPP_DIRS):
        for path in iter_files(root, rel, exts=(".cpp",)):
            relpath = os.path.relpath(path, root).replace("\\", "/")
            text = _cached_text(path)
            if cls not in text:
                continue
            # ① 内联类体：class Xxx : public Base { ... };
            inline = re.compile(r'^\s*class\s+' + re.escape(cls) + r'\s*(?::|\{)', re.M)
            found = False
            for m in inline.finditer(text):
                span = _brace_span(text, m)
                if span:
                    found = True
                    s = text.count("\n", 0, span[0]) + 1
                    e = text.count("\n", 0, span[1]) + 1
                    out.append((relpath, s, e))
            if found:
                continue
            # ② 外联方法：Type Cls::method(...) { ... }
            qual = re.compile(r'^[^\n;{}]*?\b' + re.escape(cls) + r'\s*::\s*\w+\s*\(', re.M)
            for m in qual.finditer(text):
                span = _brace_span(text, m)
                if span:
                    s = text.count("\n", 0, span[0]) + 1
                    e = text.count("\n", 0, span[1]) + 1
                    out.append((relpath, s, e))
    return out


ASK_CALL_RE = re.compile(r'\b(askFor[A-Za-z]+)\s*\(')


def split_args(text, lparen_idx):
    """从 '(' 处切出参数列表，返回参数原文列表（已做字符串保护）。"""
    depth, i, n = 0, lparen_idx, len(text)
    args, cur = [], []
    while i < n:
        c = text[i]
        if c == '(':
            depth += 1
            if depth == 1:
                i += 1
                continue
        elif c == ')':
            depth -= 1
            if depth == 0:
                args.append("".join(cur))
                return args
        elif c == ',' and depth == 1:
            args.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    args.append("".join(cur))
    return args


STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')

# askForCard 的 AI 键不是技能名，而是 prompt 串的第一段（":" 之前）。
# SmartAI:askForCard(pattern, prompt, data) 内部：
#     local parsedPrompt = prompt:split(":")
#     local callback = sgs.ai_skill_cardask[parsedPrompt[1]]
# 证据（C++ prompt ↔ 既有 Lua 注册键）：
#     "@fengshi-discard:" + name        ↔ sgs.ai_skill_cardask["@fengshi-discard"]
#     "double-sword-card:" + name       ↔ sgs.ai_skill_cardask["double-sword-card"]
#     "@@chaosselect!" / "@chaos-select"↔ sgs.ai_skill_cardask["@chaos-select"]
#     "@@midao" / prompt_list "@midao-card" ↔ sgs.ai_skill_cardask["@midao-card"]
# prompt 为变量时，退化为在类体里找 `QString prompt = "..."` / `prompt_list << "..."`。
_PROMPT_VAR_RE = re.compile(
    r'\b(?:prompt|prompt_list|cost_prompt|str)\b\s*(?:=|\+=|<<)\s*"((?:[^"\\]|\\.)*)"')


def prompt_key(first_literal):
    """把 prompt 字面量归一成 ai_skill_cardask 的键（取首个 ":" 之前的段）。"""
    if first_literal:
        return first_literal.split(":")[0]
    return None


def cardask_key_from_args(args, seg):
    """askForCard 的真实 AI 键：优先 prompt 形参里的字面量，其次类体里的 prompt 变量。"""
    if len(args) > 2:
        sm = STR_RE.search(args[2])
        if sm:
            k = prompt_key(sm.group(1))
            if k:
                return k
    m = _PROMPT_VAR_RE.search(seg)
    if m:
        return prompt_key(m.group(1))
    return None


def scan_asks_in_span(root, rec):
    """扫描类体内所有 askFor 调用，返回 [(api, reason, file, line), ...]。

    同时扫描该技能产生的技能卡类体（card_spans），因为 askFor 常常写在
    `XxxCard::use()` 里，只扫技能类体会漏掉这些 AI 需求。
    """
    out = []
    for rel, s, e in list(rec.get("spans") or []) + list(rec.get("card_spans") or []):
        path = os.path.join(root, rel)
        text = strip_comments(read(path))
        lines = text.split("\n")
        if s < 1 or e < s or e > len(lines):
            continue
        seg_start = sum(len(l) + 1 for l in lines[:s - 1])
        seg_end = sum(len(l) + 1 for l in lines[:e])
        seg = text[seg_start:seg_end]

        for m in ASK_CALL_RE.finditer(seg):
            api = m.group(1)
            if api in ROOM_LEVEL_ASK or api not in ASK_MAP:
                continue
            args = split_args(seg, m.end() - 1)
            idx = ASK_MAP[api][1]

            # 两种调用形式并存：
            #   player->askForSkillInvoke("name")            → 技能名在 idx 0
            #   player->askForSkillInvoke("name", "reason")  → 技能名仍在 idx 0
            #   room->askForSkillInvoke(player, "name", data)→ 技能名在 idx 1
            # 先试 idx 0（出现概率更高、且是唯一带引号参数的场景），再试 idx 1。
            probed = [0, idx] if api == "askForSkillInvoke" else [idx]

            reason = None
            for i in probed:
                if i >= len(args):
                    continue
                a = args[i]
                if "objectName()" in a:
                    reason = None          # 运行期等于技能名
                    break
                sm = STR_RE.search(a)
                if sm and sm.group(1) and not sm.group(1).startswith("@"):
                    reason = sm.group(1)
                    break

            lineno = s + seg.count("\n", 0, m.start())
            key_override = cardask_key_from_args(args, seg) if api == "askForCard" else None
            out.append((api, reason, rel, lineno, key_override))
    return out


def scan_ask_patterns(root, cpp_dirs=None):
    """全项目扫描 askForCard / askForUseCard / askForUseSlashTo，建立
    response_pattern → 实际需要的 AI 键 的映射。

    用于判定"响应式视为技"（如 @@chaosselect! / @@zhengbigive! / @@qianzheng）是否可用：
    这些技能自身没有 response 请求代码，请求写在别的技能类（src/package）甚至引擎里
    （src/server/serverplayer.cpp 的 @@commandefect!），只有顺着 pattern 找到发起方，
    才能知道真正要注册的键（prompt 首段 或 pattern 本身）。
    """
    out = {}
    for rel in (cpp_dirs or QUEST_DIRS):
        for path in iter_files(root, rel, exts=(".cpp",)):
            text = strip_comments(read(path))
            relpath = os.path.relpath(path, root).replace("\\", "/")
            for m in ASK_CALL_RE.finditer(text):
                api = m.group(1)
                if api not in ("askForCard", "askForUseCard", "askForUseSlashTo"):
                    continue
                args = split_args(text, m.end() - 1)
                pat = None
                if len(args) > 1:
                    sm = STR_RE.search(args[1])
                    if sm and sm.group(1).startswith("@@"):
                        pat = sm.group(1)
                if not pat:
                    continue
                if api == "askForUseCard":
                    # askForUseCard 走 ai_skill_use[pattern]，不需要 prompt
                    key = None
                else:
                    key = cardask_key_from_args(args, text)
                lineno = text.count("\n", 0, m.start()) + 1
                out.setdefault(pat, []).append(
                    {"api": api, "prompt_key": key, "file": relpath, "line": lineno})
    return out


# --------------------------------------------------------------------------
# ② 扫描 Lua AI
# --------------------------------------------------------------------------

# sgs.ai_xxx.key = ...     sgs.ai_xxx["key"] = ...     sgs.ai_xxx[expr] = ...
# 以及 function sgs.ai_xxx.key(...) / function sgs.ai_xxx["key"](...)
AI_KEY_RE = re.compile(
    r'(?:(?:function\s+)?sgs\.(ai_[a-z_]+)\s*'
    r'(?:\.\s*([A-Za-z0-9_\-]+)|\[\s*"([^"]+)"\s*\]|\[\s*([^\]\n]+?)\s*\])\s*'
    r'(?:=|\(|\{))')
# table.insert(sgs.ai_skills, xxx_skill)
AI_SKILLS_INSERT_RE = re.compile(r'table\.insert\s*\(\s*sgs\.ai_skills\s*,\s*([A-Za-z_]\w*)\s*\)')
# xxx_skill.name = "skillname"
TBL_NAME_RE = re.compile(r'\b([A-Za-z_]\w*)\.name\s*=\s*"([^"]+)"')


def scan_ai(root, ai_dirs=None):
    """返回 {hook: {key: (file, line)}}。

    识别本项目全部 AI 注册写法：
        ① sgs.ai_xxx.key = ...
        ② sgs.ai_xxx["key"] = ...
        ③ sgs.ai_xxx[expr] = ...        （动态键，收录为 <dynamic:expr>）
        ④ function sgs.ai_xxx.key(...)  （函数式注册）
        ⑤ local t = {}; t.name = "skill"; table.insert(sgs.ai_skills, t)
           → 归一化为 sgs.ai_skills.<skill>
    """
    hooks = {}
    for rel in (ai_dirs or AI_DIRS):
        for path in iter_files(root, rel, exts=(".lua",)):
            lov = strip_lua_comments(read(path))
            relpath = os.path.relpath(path, root).replace("\\", "/")

            for m in AI_KEY_RE.finditer(lov):
                hook = m.group(1)
                if m.group(2) is not None:
                    key = m.group(2)
                elif m.group(3) is not None:
                    key = m.group(3)
                else:
                    key = "<dynamic:%s>" % m.group(4).strip()
                line = lov.count("\n", 0, m.start()) + 1
                hooks.setdefault(hook, {})
                hooks[hook].setdefault(key, (relpath, line))

            # ④ ai_skills 的 (变量 → 技能名) 注册
            inserted = set(AI_SKILLS_INSERT_RE.findall(lov))
            if inserted:
                for m in TBL_NAME_RE.finditer(lov):
                    var, name = m.group(1), m.group(2)
                    if var not in inserted:
                        continue
                    line = lov.count("\n", 0, m.start()) + 1
                    hooks.setdefault("ai_skills", {})
                    hooks["ai_skills"].setdefault(name, (relpath, line))
    return hooks


def strip_lua_comments(text):
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "-" and i + 1 < n and text[i + 1] == "-":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif c == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            out.append(text[i:j])
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# ③ 扫描 lang
# --------------------------------------------------------------------------

LANG_ENTRY_RE = re.compile(
    r'\[\s*"([^"]+)"\s*\]\s*=\s*(?:"((?:[^"\\]|\\.)*)"|\[\[(.*?)\]\]|([^,\n]+))', re.S)


def scan_lang(root, lang_dirs=None):
    """返回 {skillname: {'cn_name':..., 'desc':..., 'file':..., 'line':...}}"""
    skills = {}
    entries_all = {}
    for rel in (lang_dirs or LANG_DIRS):
        for path in iter_files(root, rel, exts=(".lua",)):
            text = read(path)
            if text.startswith("\ufeff"):
                text = text[1:]
            relpath = os.path.relpath(path, root).replace("\\", "/")
            by_key = {}
            for m in LANG_ENTRY_RE.finditer(text):
                key = m.group(1)
                val = m.group(2) if m.group(2) is not None else (
                    m.group(3) if m.group(3) is not None else m.group(4))
                line = text.count("\n", 0, m.start()) + 1
                by_key.setdefault(key, {"value": (val or "").replace('\\"', '"'),
                                        "line": line, "file": relpath})
            entries_all.update(by_key)
            for key, info in by_key.items():
                if key.startswith((":", "@", "~", "#", "$")) or ":" in key:
                    continue
                if (":" + key) not in by_key:
                    continue
                skills.setdefault(key, {
                    "cn_name": info["value"],
                    "desc": by_key[":" + key]["value"],
                    "file": by_key[":" + key]["file"],
                    "line": by_key[":" + key]["line"],
                })
    return skills, entries_all


# --------------------------------------------------------------------------
# ④ 交叉核对
# --------------------------------------------------------------------------

def _norm_key(k):
    """去掉 AI 键常见的前缀装饰（@ 询问串、@@ 自主决策）。"""
    k = k.lstrip("@")
    return k


def _key_equiv(a, b):
    """AI 注册键与期望键是否等价。

    允许的宽松匹配：
        guicai  ≡  @guicai  ≡  @guicai-card  ≡  guicai-card
    但要求超出部分以分隔符开头（- _ : .）或非常短，避免 gu 命中 guicai。
    """
    a, b = _norm_key(a), _norm_key(b)
    if a == b:
        return True
    long_, short = (a, b) if len(a) >= len(b) else (b, a)
    if not long_.startswith(short):
        return False
    rest = long_[len(short):]
    return rest[:1] in ("-", "_", ":", ".")


def key_hit(table, candidates):
    """在 hook 表里查找候选键，返回 (key, file, line) 或 None。"""
    if not table:
        return None
    cands = []
    for c in candidates:
        if not c:
            continue
        cands.extend([c, "@" + c, "@@" + c])
    for cand in cands:
        if not cand:
            continue
        if cand in table:
            return (cand,) + tuple(table[cand])
        for k, v in table.items():
            if k.startswith("<dynamic:"):
                continue
            if _key_equiv(k, cand):
                return (k,) + tuple(v)
    return None


def audit_skill(name, cpp_recs, lang_info, hooks, ask_patterns=None):
    """对单个 objectName 判定。返回 dict。"""
    ask_patterns = ask_patterns or {}
    verdicts = []
    need = []
    have = []
    missing = []

    is_internal = name.startswith("#")
    rule_mod = bool(cpp_recs) and all(r["rule_modifier"] for r in cpp_recs)
    viewas = any(r["viewas"] for r in cpp_recs)
    # 视为技产生的"技能卡"：取 viewAs() 里 new 出来的卡类名（如 JianyanCard / TonglingCard）
    cards = sorted({c for r in cpp_recs for c in (r.get("produced_cards") or [])})
    # 响应式视为技的 pattern（如 @@chaosselect! / @@zhengbigive! / @@shensu1）
    patterns = sorted({p for r in cpp_recs for p in (r.get("patterns") or [])})

    # ---------------- 1) askFor 推导 ----------------
    asks = []
    for rec in cpp_recs:
        for api, reason, f, lineno, key_override in scan_asks_in_span(rec["_root"], rec):
            asks.append((api, reason, f, lineno, key_override))

    freq = next((r["frequency"] for r in cpp_recs if r.get("frequency")), None)

    seen = set()
    for api, reason, f, ln, key_override in asks:
        hook = ASK_MAP[api][0]
        # 引擎侧统一做 string.gsub(reason, "%-", "_") 归一化，
        # 所以 `askForChoice(player, objectName())` 在内部技上得到的键是
        # "#guowu_effect" 而不是 "guowu"；下划线化后再查表才与运行期一致。
        raw_key = key_override or reason or name
        key = raw_key.replace("-", "_") if hook != "ai_skill_cardask" else raw_key
        entry = "%s.%s" % (hook, key)
        if entry in seen:
            continue
        seen.add(entry)

        # Frequent 技能的 askForSkillInvoke 有引擎兜底（直接返回 true），不算缺失
        if hook == "ai_skill_invoke" and freq == "Frequent":
            continue

        need.append(entry)
        cands = [key, raw_key, name, name.replace("-", "_")]
        # 内部技（#aaa-bbb）有时把 AI 键挂在主技能 aaa 上，作为兜底候选
        if reason is None or key_override is None:
            cands.append(name.lstrip("#").split("-")[0])
        cands.append(reason)
        hit = key_hit(hooks.get(hook), cands)
        if hit:
            have.append("%s -> %s:%d" % (entry, hit[1], hit[2]))
        else:
            sev = "FATAL" if hook in FATAL_HOOKS else (
                "DEGRADED" if hook in DEGRADED_HOOKS else "UNKNOWN")
            extra = ""
            if hook == "ai_skill_invoke":
                extra = "（频率 %s，引擎兜底不会发动）" % (freq or "NotFrequent")
            if hook == "ai_skill_cardask":
                extra = "（键取自 askForCard 的 prompt 首段）"
            missing.append((entry, "%s:%d 调用了 %s(\"%s\")%s"
                            % (f, ln, api, key_override or reason or "", extra), sev))

    # ---------------- 2) 视为技 / 主动技的可用性 ----------------
    # 本项目里"技能可用性"的注册路径有六条，命中任意一条即可：
    #   ① sgs.ai_skills 里 .name = "<name>" 的条目    —— 出牌阶段主动使用
    #   ② sgs.ai_skill_use["@@<name>"]               —— 由 skills 触发的自主决策
    #   ③ sgs.ai_skill_use["<response_pattern>"]     —— 响应式视为技（如 @@JadeSeal! / @@shensu1）
    #   ④ sgs.ai_view_as.<name>                      —— 一对一转化的响应
    #   ⑤ sgs.ai_cardsview / ai_skill_cardask        —— 询问响应牌
    #   ⑥ 产生的技能卡已配 ai_skill_use_func          —— 变相说明技能能被用出去
    # 注意：响应式视为技的 pattern 常常带后缀（!、数字、下划线），必须按 C++ 里的
    #       response_pattern 原文去查，不能只按技能名查，否则会误报"不可用"。
    # 响应式视为技：把 response_pattern 映射成"真正要注册的键"。
    #   askForCard(pattern, prompt)      → ai_skill_cardask[prompt 首段]
    #   askForUseCard(pattern, prompt)   → ai_skill_use[pattern]
    resp_keys = []          # [(hook, key), ...]
    for pat in patterns:
        resp_keys.append(("ai_skill_use", pat))
        for info in ask_patterns.get(pat, []):
            if info["api"] == "askForUseCard":
                resp_keys.append(("ai_skill_use", pat))
            elif info["prompt_key"]:
                resp_keys.append(("ai_skill_cardask", info["prompt_key"]))
            else:
                resp_keys.append(("ai_skill_cardask", pat))

    def resp_hit():
        for hook, key in resp_keys:
            h = key_hit(hooks.get(hook), [key])
            if h:
                return h
        return None

    if viewas and not is_internal:
        entry = "观望可用性(%s)" % name
        need.append(entry)
        hit = (key_hit(hooks.get("ai_skills"), [name])
               or key_hit(hooks.get("ai_skill_use"), ["@@" + name])
               or key_hit(hooks.get("ai_view_as"), [name])
               or key_hit(hooks.get("ai_cardsview"), [name])
               or key_hit(hooks.get("ai_cardsview_priority"), [name])
               or key_hit(hooks.get("ai_skill_cardask"), ["@" + name, name])
               or key_hit(hooks.get("ai_skill_invoke"), [name]))
        if not hit:
            for pat in patterns:
                hit = (key_hit(hooks.get("ai_skill_use"), [pat])
                       or key_hit(hooks.get("ai_skill_cardask"), [pat])
                       or key_hit(hooks.get("ai_view_as"), [pat.lstrip("@")]))
                if hit:
                    break
        if not hit:
            hit = resp_hit()
        if not hit:
            for card in cards:
                hit = key_hit(hooks.get("ai_skill_use_func"), [card])
                if hit:
                    break
        if hit:
            have.append("%s -> %s:%d" % (entry, hit[1], hit[2]))
        else:
            pat_hint = ("，response_pattern=%s" % "|".join(patterns)) if patterns else ""
            missing.append((entry, "视为技（%s）没有任何一条可用性注册路径"
                                   "（ai_skills / ai_skill_use[\"@@%s\"] / ai_view_as / ai_cardsview）%s"
                            % ("/".join(sorted({r["base"] for r in cpp_recs})), name, pat_hint),
                            "UNUSABLE"))

    # ---------------- 3) 技能卡 ----------------
    for card in cards:
        entry = "技能卡.%s" % card
        hit = (key_hit(hooks.get("ai_skill_use_func"), [card, name])
               or key_hit(hooks.get("ai_skills"), [name, card])
               or key_hit(hooks.get("ai_skill_use"), ["@@" + name])
               or key_hit(hooks.get("ai_skill_cardask"), ["@" + name, "@" + card, name]))
        if not hit:
            for pat in patterns:
                hit = (key_hit(hooks.get("ai_skill_use"), [pat])
                       or key_hit(hooks.get("ai_skill_cardask"), [pat]))
                if hit:
                    break
        if not hit:
            hit = resp_hit()
        if hit:
            have.append("%s -> %s:%d" % (entry, hit[1], hit[2]))
        else:
            missing.append((entry,
                            "技能卡类 %s 未配 ai_skill_use_func（键须为类名），"
                            "技能也未在 sgs.ai_skills / ai_skill_use[\"@@%s\"] 登记，"
                            "AI 不会主动使用该技能" % (card, name), "UNUSABLE"))

    # ---------------- 4) 定性 ----------------
    if rule_mod:
        verdicts.append(("info", "规则修正技（%s）：引擎直接读取数值，不需要 AI 决策"
                         % "/".join(sorted({r["base"] for r in cpp_recs}))))
    if is_internal:
        verdicts.append(("info", "内部技（# 前缀）：由其它技能或引擎触发"))

    sev_rank = {"FATAL": 3, "DEGRADED": 2, "UNUSABLE": 2, "UNKNOWN": 1}
    has_fatal = any(m[2] == "FATAL" for m in missing)
    has_other = any(m[2] != "FATAL" for m in missing)
    level = "OK"
    if rule_mod and missing:
        level = "PARTIAL"
    elif has_fatal:
        level = "FATAL_MISSING"
    elif has_other:
        level = "DEGRADED_MISSING"

    return {
        "skill": name,
        "cn_name": (lang_info or {}).get("cn_name", ""),
        "desc": (lang_info or {}).get("desc", ""),
        "lang_file": (lang_info or {}).get("file", ""),
        "lang_line": (lang_info or {}).get("line"),
        "frequency": freq,
        "cpp": [{"class": r["class"], "base": r["base"], "file": r["file"], "line": r["line"]}
                for r in cpp_recs],
        "in_lang": bool(lang_info),
        "internal": is_internal,
        "rule_modifier": rule_mod,
        "viewas": viewas,
        "skill_cards": cards,
        "asks": [{"api": a, "reason": r, "file": f, "line": l,
                  "ai_key": k} for a, r, f, l, k in asks],
        "need": sorted(set(need)),
        "have": have,
        "missing": [{"hook": h, "why": w, "severity": sev} for h, w, sev in missing],
        "verdicts": verdicts,
        "level": level,
        "max_severity": max((m[2] for m in missing), key=lambda s: sev_rank.get(s, 0),
                            default="OK"),
    }


def run_audit(root, only_skill=None, only_package=None):
    cpp = scan_cpp_skills(root)
    lang, _entries = scan_lang(root)
    hooks = scan_ai(root)
    ask_patterns = scan_ask_patterns(root)

    # 把 root / 技能名塞进 rec，供 class_spans / scan_asks 使用
    for name, recs in cpp.items():
        for rec in recs:
            rec["_root"] = root
            rec["_name"] = name
    for name, recs in cpp.items():
        for rec in recs:
            rec["frequency"] = detect_frequency(root, rec)

    results = []
    for name in sorted(cpp):
        if only_skill and name != only_skill:
            continue
        if only_package:
            allowed = any(only_package in r["file"] for r in cpp[name])
            if not allowed:
                continue
        results.append(audit_skill(name, cpp[name], lang.get(name), hooks, ask_patterns))

    lang_only = sorted(set(lang) - set(cpp))
    return results, lang, cpp, hooks, lang_only


FREQ_RE = re.compile(r':\s*([A-Za-z_]\w*)\s*\(\s*"([^"]+)"\s*(?:,\s*Skill::(\w+))?')


def detect_frequency(root, rec):
    """取技能频率。

    本项目有两种写法，都要认：
        frequency = Compulsory;              （裸赋值，最常见）
        : Skill(name, Skill::Compulsory)     （构造参数）
    同时要避免把 `TriggerSkill::triggerable` 这类方法名误当成频率。
    """
    path = os.path.join(root, rec["file"])
    text = strip_comments(read(path))
    lines = text.split("\n")
    segs = []
    for _rel, s, e in rec.get("spans") or []:
        segs.append("\n".join(lines[max(0, s - 1):e]))
    seg = "\n".join(segs)

    m = re.search(r'(?<![A-Za-z_.])frequency\s*=\s*(\w+)', seg)
    if m and m.group(1) in ("Frequent", "NotFrequent", "Compulsory", "Limited", "Wake"):
        return m.group(1)

    m = re.search(r'(?<![A-Za-z_])Skill::(Frequent|NotFrequent|Compulsory|Limited|Wake)\b', seg)
    if m:
        return m.group(1)
    return None


def render(results, lang_only):
    ok = [r for r in results if r["level"] == "OK"]
    fatal = [r for r in results if r["level"] == "FATAL_MISSING"]
    degrad = [r for r in results if r["level"] == "DEGRADED_MISSING"]
    partial = [r for r in results if r["level"] == "PARTIAL"]

    out = []
    out.append("=" * 78)
    out.append("技能 → Lua AI 覆盖审计")
    out.append("=" * 78)
    out.append("")
    out.append("扫描到 C++ 技能类 %d 个（按 objectName 去重）" % len(results))
    out.append("  ✅ 已具备全部必需 AI hook            %d" % len(ok))
    out.append("  ❌ 致命缺失（AI 永不发动 / 乱选）     %d" % len(fatal))
    out.append("  ⚠️  降级缺失（能用但选择不聪明）       %d" % len(degrad))
    out.append("  ➖ 规则修正技的零星缺失               %d" % len(partial))
    out.append("  ℹ️  lang 有条目但 C++ 未找到实现       %d" % len(lang_only))
    out.append("")
    out.append("严重度依据 smart-ai.lua 的实际兜底行为：")
    out.append("  致命 = ai_skill_invoke（非 Frequent 时兜底返回 nil，AI 永不发动）")
    out.append("         ai_skill_choice（兜底优先选 cancel/no，或随机）")
    out.append("         ai_skill_exchange / ai_skill_cardask")
    out.append("  降级 = ai_skill_discard / playerchosen / cardchosen 等有通用启发式兜底")
    out.append("  不可用 = 视为技/技能卡没有任何注册路径，AI 想不起来用")
    out.append("")

    def section(title, note, items):
        if not items:
            return
        out.append("-" * 78)
        out.append(title)
        if note:
            out.append(note)
        out.append("-" * 78)
        for r in items:
            out.append("")
            out.append("### %s  %s" % (r["skill"], r["cn_name"]))
            if r["desc"]:
                out.append("    中文：%s" % r["desc"][:110].replace("\n", " "))
            for c in r["cpp"]:
                out.append("    C++：%-22s (%s:%d)" % (c["base"], c["file"], c["line"]))
            for a in r["asks"]:
                out.append("    调用：%s(\"%s\")  @ %s:%d"
                           % (a["api"], a["reason"], a["file"], a["line"]))
            for m in r["missing"]:
                out.append("    [缺 %s] %s" % (m["severity"], m["hook"]))
                out.append("              %s" % m["why"])
            for h in r["have"]:
                out.append("    [有] %s" % h)
        out.append("")

    section("【① 致命缺失 —— 技能会完全不被 AI 使用，或做出明显错误的选择】",
            "建议优先补齐。", fatal)
    section("【② 降级缺失 —— 技能能用，但 AI 的选择不够聪明】",
            "引擎有通用兜底，可按需补齐。", degrad)

    if partial:
        out.append("-" * 78)
        out.append("【③ 规则修正技的零星缺失（引擎直接生效，影响很小）】")
        out.append("-" * 78)
        for r in partial:
            out.append("  %-24s %s" % (r["skill"], ", ".join(m["hook"] for m in r["missing"])))
        out.append("")

    if lang_only:
        out.append("-" * 78)
        out.append("【④ lang 有条目但 C++ 未找到实现（可能是卡牌/装备名，非技能）】")
        out.append("-" * 78)
        for i in range(0, len(lang_only), 4):
            out.append("  " + "".join("%-22s" % x for x in lang_only[i:i + 4]))
        out.append("")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="技能 → Lua AI 覆盖审计")
    ap.add_argument("--root", default=None)
    ap.add_argument("--skill")
    ap.add_argument("--package")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    root = args.root or find_root(os.getcwd())
    if not root or not os.path.isfile(os.path.join(root, "QSanguosha.pro")):
        print("错误：未找到项目根（需含 QSanguosha.pro），请用 --root 指定", file=sys.stderr)
        return 2

    results, lang, cpp, hooks, lang_only = run_audit(root, args.skill, args.package)

    if args.json:
        payload = json.dumps({
            "root": root,
            "skills_scanned": len(results),
            "lang_only": lang_only,
            "results": results,
        }, ensure_ascii=False, indent=2)
    else:
        payload = render(results, lang_only)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print("已写入 %s" % args.out)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
