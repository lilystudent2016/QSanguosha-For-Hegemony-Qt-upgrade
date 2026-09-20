# -*- coding: utf-8 -*-
"""
独立校验：qsgs-skill-generator 生成的 bot(AI) Lua 代码是否正确。

与 audit_ai.py 走**不同通道**：不依赖它的 ASK_MAP/span 归属，而是
  ① 从「运行期实际加载的」部署树 smart-ai.lua 反推每个 hook 的查表键归一化规则；
  ② 直接扫 C++ 的 askForXXX 调用点，按 hook 特异性规则算出**运行期真实键**；
  ③ 与补丁(.patch.lua)里注册的键逐一对齐；
  ④ 对补丁代码做「已知故障家族」静态扫描（A/B/C + nil 安全 + API 存在性）。

用法:
  python verify_bot_lua.py --root <项目根> [--deploy <部署 debug 目录>] [--json out.json]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------- 常量

# 补丁文件 -> 目标 AI 文件（部署清单）
PATCH_FILES = [
    "jiange-defense-ai.patch.lua", "formation-ai.patch.lua", "momentum-ai.patch.lua",
    "standard_cards-ai.patch.lua", "standard-qun-ai.patch.lua", "standard-shu-ai.patch.lua",
    "standard-wei-ai.patch.lua", "transformation-ai.patch.lua", "mol-ai.patch.lua",
    "lord_ex-ai.patch.lua", "manoeuvre-ai.patch.lua", "newsgs-ai.patch.lua",
]

# C++ askForXXX -> (hook 表, reason 参数下标)
#   下标从 0 计，已逐一对照 src/server/room.h 真实签名：
#     askForSkillInvoke(player, skill_name, data, notify)        -> 1
#     askForChoice(player, skill_name, choices, data, prompt)    -> 1
#     askForDiscard(target, reason, discard_num, min_num, ...)   -> 1
#     askForExchange(player, reason, exchange_num, ...)          -> 1
#     askForCardChosen(player, who, flags, reason, method)       -> 3
#     askForCardsChosen(player, who, flags, reason, min, max, m) -> 3
#     askForAG(player, card_ids, refusable, reason)              -> 3
#     askForPlayerChosen(player, targets, reason, skill, opt)    -> 2
#     askForCard(player, pattern, prompt, data, method)          -> 2 (prompt 首段)
ASK_API = {
    "askForSkillInvoke":     ("ai_skill_invoke",     1),
    "askForChoice":          ("ai_skill_choice",     1),
    "askForExchange":        ("ai_skill_exchange",   1),
    "askForDiscard":         ("ai_skill_discard",    1),
    "askForCardChosen":      ("ai_skill_cardchosen", 3),
    "askForCardsChosen":     ("ai_skill_cardschosen", 3),
    "askForAG":              ("ai_skill_askforag",   3),
    "askForPlayerChosen":    ("ai_skill_playerchosen", 2),
    "askForPlayersChosen":   ("ai_skill_playerchosen", 2),
    "askForCard":            ("ai_skill_cardask",    "prompt"),
    "askForUseCard":         ("ai_skill_use",        "pattern"),
    "askForSuit":            ("ai_skill_suit",       1),
}

# 不经 askFor 查表、以「C++ 类/技能卡存在性」核对的 hook
CLASS_BACKED_HOOKS = {"ai_skills", "ai_skill_use_func", "ai_use_priority",
                      "ai_cardsview", "ai_view_as", "ai_card_intention", "ai_cardneed"}

# 「AI 侧可用性/技能卡」相关（audit_ai.py 的 观望可用性 / 技能卡）
AUX_HOOKS = ("ai_skills", "ai_skill_use_func", "ai_view_as", "ai_cardsview",
             "ai_skill_cardask", "ai_skill_use", "ai_skill_invoke")

# 期望：各 askFor 对应的 AI 能力；缺失严重度沿用 audit_ai.py 的口径
FATAL_HOOKS = {"ai_skill_invoke", "ai_skill_choice", "ai_skill_exchange", "ai_skill_cardask"}

# ---------------------------------------------------------------- 工具

def read(path, binary=False):
    with open(path, "rb" if binary else "r", encoding=None if binary else "utf-8",
              errors=None if binary else "replace") as f:
        return f.read()


def split_args(s):
    """按顶层逗号切分实参（跳过括号/引号内的逗号）。"""
    args, depth, cur, quote = [], 0, [], None
    i = 0
    while i < len(s):
        ch = s[i]
        if quote:
            cur.append(ch)
            if ch == "\\":
                if i + 1 < len(s):
                    cur.append(s[i + 1]); i += 2; continue
            elif ch == quote:
                quote = None
        else:
            if ch in "\"'":
                quote = ch; cur.append(ch)
            elif ch in "([{":
                depth += 1; cur.append(ch)
            elif ch in ")]}":
                depth -= 1; cur.append(ch)
            elif ch == "," and depth == 0:
                args.append("".join(cur).strip()); cur = []
            else:
                cur.append(ch)
        i += 1
    if cur:
        args.append("".join(cur).strip())
    return args


def call_args(text, open_paren_idx):
    """从 '(' 开始取到配对 ')'，返回实参列表与结束下标。"""
    depth, i, quote = 0, open_paren_idx, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2; continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return split_args(text[open_paren_idx + 1:i]), i
        i += 1
    return None, len(text)


# ------------------------------------------------- ① 运行期归一化规则

def probe_normalization(smart_ai_text):
    """按部署树 smart-ai.lua 的真实代码判定每个 hook 的键归一化规则。"""
    hooks = ["ai_skill_invoke", "ai_skill_choice", "ai_skill_exchange", "ai_skill_discard",
             "ai_skill_cardchosen", "ai_skill_cardschosen", "ai_skill_cardask",
             "ai_skill_askforag", "ai_skill_playerchosen", "ai_skill_suit",
             "ai_skill_use", "ai_skill_use_func"]
    rules, evidence = {}, {}
    for h in hooks:
        # 找 hook 的查表行
        for m in re.finditer(r"sgs\.%s\[([^\]]*)\]" % re.escape(h), smart_ai_text):
            idx_expr = m.group(1)
            line_no = smart_ai_text[:m.start()].count("\n") + 1
            if h == "ai_skill_cardask":
                rules[h] = "prompt_probe"
                evidence[h] = "L%d: %s" % (line_no, idx_expr)
                break
            if h == "ai_skill_use_func":
                rules[h] = "verbatim_class"
                evidence[h] = "L%d: %s" % (line_no, idx_expr)
                break
            if h == "ai_skill_use":
                rules[h] = "verbatim_pattern"
                evidence[h] = "L%d: %s" % (line_no, idx_expr)
                break
            # 判定是否归一化：①下标表达式本身即 gsub(...)；
            # ②同函数内 idx 变量由 gsub 赋值而来
            varname = idx_expr.strip()
            norm = bool(re.search(r'gsub\s*\([^)]*"%-"[^)]*"_"', varname))
            if not norm:
                fstart = smart_ai_text.rfind("\nfunction ", 0, m.start())
                fstmt = smart_ai_text[fstart:m.start()]
                for g in re.finditer(
                        r'(\w+)\s*=\s*string\.gsub\(\s*(\w+)\s*,\s*"%?-"%?\s*,\s*"_"\s*\)', fstmt):
                    if g.group(1) == varname or g.group(2) == varname:
                        norm = True
            rules[h] = "dash_under" if norm else "verbatim"
            evidence[h] = "L%d: %s  (%s)" % (line_no, idx_expr, "归一化" if norm else "原样")
            break
        else:
            rules[h] = "unknown"
            evidence[h] = "未找到 sgs.%s[ 查表行" % h
    return rules, evidence


# ------------------------------------------------- ② C++ askFor 扫描

CLASS_RE = re.compile(r"^class\s+(\w+)\s*:\s*public\s+(\w+)\s*$", re.M)


def class_ctor_name(text, cls):
    """取 cls 构造函数初始化列表里基类 ctor 的名字串（支持多行/带参 ctor）。"""
    for m in re.finditer(r"\b%s\s*\(" % re.escape(cls), text):
        args, end = call_args(text, m.end() - 1)
        if args is None:
            continue
        tail = text[end:end + 240]
        cm = re.search(r":\s*\w+\s*(?:<[^>]*>)?\s*\(\s*\"([^\"]+)\"", tail)
        if cm:
            return cm.group(1)
    return None


def scan_cpp(path):
    """返回 [(skill_name, cls, api, reason_expr, lineno)]。"""
    text = read(path)
    # 类 -> 技能名
    classes = []
    for m in CLASS_RE.finditer(text):
        cls = m.group(1)
        classes.append((m.start(), cls, class_ctor_name(text, cls)))
    classes.sort()

    def owner(pos):
        cur = None
        for start, cls, name in classes:
            if start <= pos:
                cur = (cls, name)
            else:
                break
        return cur or (None, None)

    out = []
    for m in re.finditer(r"\b(askFor\w+)\s*\(", text):
        api = m.group(1)
        if api not in ASK_API:
            continue
        args, _ = call_args(text, m.end() - 1)
        if args is None:
            continue
        cls, skill = owner(m.start())
        lineno = text[:m.start()].count("\n") + 1
        spec = ASK_API[api][1]
        if isinstance(spec, int):
            # askForSkillInvoke 有三种形态：
            #   room->askForSkillInvoke(player, "x", data)        -> args[1]
            #   player->askForSkillInvoke(this[, data])           -> args[0]
            #   player->askForSkillInvoke("_kenshang", "prompt")  -> args[0]
            if api == "askForSkillInvoke" and args and (
                    args[0].strip() == "this" or args[0].lstrip().startswith('"')):
                expr = args[0]
            else:
                expr = args[spec] if len(args) > spec else ""
        elif spec == "prompt":
            expr = args[2] if len(args) > 2 else ""   # askForCard 的 prompt
        else:
            expr = args[1] if len(args) > 1 else ""   # pattern
        out.append((skill, cls, api, expr, lineno))
    return out


def resolve_reason(expr, cls, skill):
    """把 reason 表达式化归为「字面量」「objectName」「动态」三类。"""
    expr = (expr or "").strip()
    if expr in ("objectName()", "Skill::objectName()", "this"):
        return ("objectName", skill)
    m = re.fullmatch(r'QString\("([^"]*)"\)', expr)
    if m:
        return ("literal", m.group(1))
    m = re.fullmatch(r'"((?:[^"\\]|\\.)*)"', expr)
    if m:
        return ("literal", m.group(1))
    if expr.startswith('"'):
        m = re.match(r'"((?:[^"\\]|\\.)*)"', expr)
        if m:
            return ("literal", m.group(1))
    return ("dynamic", expr)


# ------------------------------------------------- ③ 补丁注册键提取

HOOK_TABLES = ("ai_skill_invoke", "ai_skill_choice", "ai_skill_exchange", "ai_skill_discard",
               "ai_skill_cardchosen", "ai_skill_cardschosen", "ai_skill_askforag",
               "ai_skill_playerchosen", "ai_skill_cardask", "ai_skill_use",
               "ai_skill_use_func", "ai_view_as", "ai_cardsview", "ai_skill_suit",
               "ai_use_priority", "ai_card_intention", "ai_cardneed")


def scan_registrations(text, fname):
    """提取 sgs.<hook>.<key> = ... 与 sgs.<hook>["<key>"] = ... 以及 ai_skills 的 name。"""
    regs = []
    for m in re.finditer(r"sgs\.(\w+)\.([\w#@_\-]+)\s*=", text):
        hook, key = m.group(1), m.group(2)
        if hook in HOOK_TABLES:
            regs.append((hook, key, fname, text[:m.start()].count("\n") + 1))
    for m in re.finditer(r'sgs\.(\w+)\[\s*"([^"]+)"\s*\]\s*=', text):
        hook, key = m.group(1), m.group(2)
        if hook in HOOK_TABLES:
            regs.append((hook, key, fname, text[:m.start()].count("\n") + 1))
    # ai_skills 条目
    for m in re.finditer(r'(\w+)\.name\s*=\s*"([^"]+)"', text):
        regs.append(("ai_skills", m.group(2), fname, text[:m.start()].count("\n") + 1))
    return regs


# ------------------------------------------------- ④ 故障家族扫描

def split_blocks(text):
    """把补丁按顶层 `sgs.x.y = function(` / `function sgs.x.y(` / `local x = {}` 切块。"""
    lines = text.split("\n")
    starts = []
    for i, ln in enumerate(lines):
        if (re.match(r"^\s*(sgs\.\w+[\.\[]\S*\s*=|function sgs\.\w+|local \w+\s*=\s*\{\})", ln)
                and not ln.lstrip().startswith("--")):
            starts.append(i)
    starts.append(len(lines))
    blocks = []
    for a, b in zip(starts, starts[1:]):
        head = lines[a].strip()
        blocks.append((a + 1, head, "\n".join(lines[a:b])))
    return blocks


# 会经 C++ 回调、可能再次触发 askForSkillInvoke 的重入敏感方法
REENTRANT_METHODS = [
    "isFriend", "isEnemy", "getFriends", "getEnemies", "isFriendWith",
    "objectiveLevel", "getCardsNum", "askForCardChosen", "findPlayerToDiscard",
    "needToThrowArmor", "willShowFor", "getDangerousCard", "getCardNeedPlayer",
]

# 空壳牌预检（家族B 判据）：cloneCard 带 3 参 = (name, suit, number) 无子牌
EMPTY_SHELL_RE = re.compile(r"cloneCard\(\s*\"[^\"]+\"\s*,\s*[^,)]+,\s*[^,)]+\)")

NIL_RISKY = [
    (re.compile(r"\[\s*1\s*\]\s*:"), "对排序结果直接取 [1]（空表则 nil 索引）"),
    (re.compile(r":split\(\s*\"[^\"]*\"\s*\)\s*\["), "split 结果直接下标（空串会产出空串元素）"),
    (re.compile(r"tonumber\(([^)]*)\)(?!\s*\)\s*then)"), "tonumber 结果未判 nil 即用"),
]


def scan_blocks(blocks, fname):
    findings = []
    for lineno, head, body in blocks:
        # 家族C：invoke 里调用重入敏感方法且无护栏
        if re.search(r"ai_skill_invoke", head) and "function" in head:
            hit = [m for m in REENTRANT_METHODS if re.search(r"self:%s\s*\(" % m, body)]
            if hit:
                guarded = ("invoking" in body) or ("reentr" in body.lower()) or ("_busy" in body)
                findings.append(dict(file=fname, line=lineno, head=head.strip(),
                                     family="C", severity="HIGH" if not guarded else "OK",
                                     detail="ai_skill_invoke 内调用 %s%s" % (
                                         ",".join(sorted(set(hit))),
                                         "（已有护栏）" if guarded else "（无护栏，与 jilei 同型：可耗尽 C 栈）")))
        # 家族B：空壳 cloneCard 预检
        for m in EMPTY_SHELL_RE.finditer(body):
            findings.append(dict(file=fname, line=lineno, head=head.strip(), family="B",
                                 severity="WARN",
                                 detail="空壳牌预检 %s（房间对 SkillCard 按子牌判限牌 ⇒ 可能不收敛）" % m.group(0)))
        # 家族A：exchange 返回可能为空的表
        if "ai_skill_exchange" in head:
            findings.append(dict(file=fname, line=lineno, head=head.strip(), family="A",
                                 severity="WARN",
                                 detail="askForExchange worker：返回表可能为空 ⇒ 调用方若不守卫会 AV（家族A 根因）"))
        # nil 安全
        for rx, why in NIL_RISKY:
            for _ in rx.finditer(body):
                findings.append(dict(file=fname, line=lineno, head=head.strip(), family="NIL",
                                     severity="WARN", detail=why))
                break
        # data:toXXX() 未判 nil
        for m in re.finditer(r"local\s+(\w+)\s*=\s*data:to(\w+)\(\)", body):
            var = m.group(1)
            if not re.search(r"if\s+%s\b|%s\s*~=\s*nil|%s\s+and\b" % (var, var, var), body):
                findings.append(dict(file=fname, line=lineno, head=head.strip(), family="NIL",
                                     severity="WARN",
                                     detail="%s = data:to%s() 未判 nil 即用" % (var, m.group(2))))
        # getCard / Sanguosha:getCard 结果未判
        for m in re.finditer(r"local\s+(\w+)\s*=\s*sgs\.Sanguosha:getCard\(([^)]*)\)", body):
            var = m.group(1)
            if not re.search(r"if\s+%s\b|%s\s*~=\s*nil" % (var, var), body):
                findings.append(dict(file=fname, line=lineno, head=head.strip(), family="NIL",
                                     severity="WARN",
                                     detail="%s = getCard(%s) 未判 nil（F3 同类：getCard 收非法 id 会报错）"
                                            % (var, m.group(2))))
    return findings


# ------------------------------------------------- ⑤ API 存在性

def smartai_methods(*texts):
    """SmartAI 方法集合：smart-ai.lua + 所有会被 smart-ai.lua dofile 的 *-ai.lua。"""
    methods = set()
    for text in texts:
        methods |= set(re.findall(r"^function\s+SmartAI:(\w+)", text, re.M))
    return methods


def scan_api_usage(blocks, methods, fname):
    """检查补丁里 self:xxx( 是否为已定义的 SmartAI 方法。"""
    bad = []
    for lineno, head, body in blocks:
        for m in re.finditer(r"self:(\w+)\s*\(", body):
            name = m.group(1)
            if name not in methods:
                bad.append(dict(file=fname, line=lineno, head=head.strip(),
                                detail="self:%s(...) 在部署树 smart-ai.lua 中不存在" % name))
    return bad


# ------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--deploy", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    root = args.root.replace("\\", "/").rstrip("/")
    deploy = (args.deploy or
              "C:/Users/Administrator/code/build-QSanguosha-Desktop_Qt_5_14_2_MinGW_64_bit-Debug/debug")
    deploy = deploy.replace("\\", "/").rstrip("/")

    patch_dir = os.path.join(root, ".workbuddy/skill-demo/lua-patch")
    src_ai = os.path.join(root, "lua/ai")
    dep_ai = os.path.join(deploy, "lua/ai")
    pkg_dir = os.path.join(root, "src/package")

    report = {}

    # ---- ① 归一化规则
    sm_path = os.path.join(dep_ai, "smart-ai.lua")
    sm_text = read(sm_path)
    rules, evidence = probe_normalization(sm_text)
    report["normalization"] = {"rules": rules, "evidence": evidence}

    methods = smartai_methods(*[read(os.path.join(dep_ai, fn))
                                for fn in sorted(os.listdir(dep_ai))
                                if fn.endswith(".lua")])
    report["smartai_method_count"] = len(methods)

    # ---- ② 部署落差
    deploy_gap = []
    for pf in PATCH_FILES:
        target = pf.replace(".patch.lua", ".lua")
        s, d = os.path.join(src_ai, target), os.path.join(dep_ai, target)
        if not os.path.exists(d):
            deploy_gap.append({"file": target, "status": "MISSING"})
            continue
        sb, db = read(s, True), read(d, True)
        deploy_gap.append({"file": target, "status": "SAME" if sb == db else "DIFF",
                           "src_bytes": len(sb), "dep_bytes": len(db)})
    report["deploy_gap"] = deploy_gap

    # ---- ③ C++ askFor 全集（运行期真实键）
    asks = []
    cpp_classes, cpp_strings = set(), set()
    for fn in sorted(os.listdir(pkg_dir)):
        if fn.endswith(".cpp"):
            ptxt = read(os.path.join(pkg_dir, fn))
            cpp_classes |= set(re.findall(r"\bclass\s+(\w+)", ptxt))
            cpp_strings |= set(re.findall(r'"([A-Za-z0-9_#\-]+)"', ptxt))
            for skill, cls, api, expr, lineno in scan_cpp(os.path.join(pkg_dir, fn)):
                kind, val = resolve_reason(expr, cls, skill)
                hook, spec = ASK_API[api]
                if hook == "ai_skill_use":
                    key = val if kind == "literal" else "<dynamic:%s>" % val
                elif kind == "literal":
                    key = val
                elif kind == "objectName":
                    key = val or "?"       # 类归属（ctor 名字串）解析出的技能名
                else:
                    key = "<dynamic:%s>" % val
                if hook == "ai_skill_cardask" and kind == "literal":
                    key = key.split(":", 1)[0]   # cardask 键 = prompt 首段
                norm = rules.get(hook, "unknown")
                rk = key
                if norm == "dash_under":
                    rk = key.replace("-", "_")
                asks.append(dict(file="src/package/" + fn, skill=skill, cls=cls, api=api,
                                 hook=hook, reason=key, kind=kind, runtime_key=rk,
                                 lineno=lineno, norm=norm))
    report["ask_count"] = len(asks)

    # ---- ④ 注册键（补丁）
    regs = []
    blocks_all = {}
    for pf in PATCH_FILES:
        p = os.path.join(patch_dir, pf)
        if not os.path.exists(p):
            continue
        t = read(p)
        regs += scan_registrations(t, pf)
        blocks_all[pf] = split_blocks(t)
    report["registration_count"] = len(regs)

    # 注册键 -> 是否被某个 ask 命中（按运行期归一化后比对）
    ask_index = defaultdict(list)
    for a in asks:
        ask_index[(a["hook"], a["runtime_key"])].append(a)
    matched, unmatched = [], []
    for hook, key, pf, ln in regs:
        k = key
        if rules.get(hook) == "dash_under":
            k = key.replace("-", "_")
        if hook in CLASS_BACKED_HOOKS:
            # 技能卡/视为技：以 C++ 类名或 ctor 名字串核对
            why = []
            if key in cpp_classes:
                why.append("class %s" % key)
            if key in cpp_strings or key.replace("_", "-") in cpp_strings:
                why.append("ctor/string \"%s\"" % key)
            rec = dict(hook=hook, key=key, runtime_key=k, file=pf, line=ln, hits=why)
            (matched if why else unmatched).append(rec)
            continue
        hits = ask_index.get((hook, k), [])
        rec = dict(hook=hook, key=key, runtime_key=k, file=pf, line=ln,
                   hits=["%s:%d(%s)" % (h["file"].split("/")[-1], h["lineno"], h["skill"]) for h in hits[:3]])
        (matched if hits else unmatched).append(rec)
    report["matched"] = matched
    report["unmatched"] = unmatched

    # ---- ⑤ 故障家族 + API
    fam, bad_api = [], []
    for pf, blocks in blocks_all.items():
        fam += scan_blocks(blocks, pf)
        bad_api += scan_api_usage(blocks, methods, pf)
    report["findings"] = fam
    report["bad_api"] = bad_api

    # ---- 输出
    print("=" * 78)
    print("① 运行期键归一化规则（来自部署树 smart-ai.lua 真实代码）")
    print("=" * 78)
    for h in sorted(rules):
        print("  %-24s %-14s %s" % (h, rules[h], evidence[h]))
    print()
    print("=" * 78)
    print("② 部署落差：源树 vs 跑批实际加载的部署树")
    print("=" * 78)
    same = sum(1 for g in deploy_gap if g["status"] == "SAME")
    print("  相同 %d / 不同 %d / 缺失 %d  (共 %d)"
          % (same, sum(1 for g in deploy_gap if g["status"] == "DIFF"),
             sum(1 for g in deploy_gap if g["status"] == "MISSING"), len(deploy_gap)))
    for g in deploy_gap:
        print("   %-28s %-8s src=%-8s dep=%s" % (g["file"], g["status"],
                                                 g.get("src_bytes"), g.get("dep_bytes")))
    print()
    print("=" * 78)
    print("③ 注册键 ↔ C++ askFor 对齐（运行期真实键）")
    print("=" * 78)
    print("  注册 %d 个 | 命中 %d | 未命中 %d" % (len(regs), len(matched), len(unmatched)))
    if unmatched:
        print("  --- 未命中（注册了但没有任何 askFor 会查它）---")
        for r in unmatched:
            print("   %-22s %-40s %s:%d" % (r["hook"], r["key"], r["file"], r["line"]))
    print()
    print("=" * 78)
    print("④ 故障家族扫描（补丁 1345 行）")
    print("=" * 78)
    by = defaultdict(list)
    for f in fam:
        by[f["family"]].append(f)
    for k in sorted(by):
        print("  家族%s: %d 条" % (k, len(by[k])))
    for f in fam:
        if f["severity"] != "OK":
            print("   [%s/%s] %s:%d  %s" % (f["family"], f["severity"], f["file"], f["line"], f["detail"]))
    print()
    print("=" * 78)
    print("⑤ API 存在性（self:xxx 对照部署树 SmartAI）")
    print("=" * 78)
    print("  可疑调用 %d 处" % len(bad_api))
    for b in bad_api:
        print("   %s:%d %s" % (b["file"], b["line"], b["detail"]))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print("\n[JSON] -> %s" % args.json)


if __name__ == "__main__":
    main()
