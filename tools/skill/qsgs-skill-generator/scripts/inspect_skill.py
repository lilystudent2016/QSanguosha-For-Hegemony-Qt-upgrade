#!/usr/bin/env python3
"""三国杀技能三件套自检工具。

用法：
    python inspect_skill.py <skillname> [--package <pkg>] [--root <dir>] [--json]

检查一个技能是否在三处都齐备：
  ① lang/zh_CN  的中文名与描述条目
  ② src/package 的 C++ 技能类与 addSkill 注册
  ③ lua/ai      的技能 AI hook

同时报告重名冲突与常见错误（连字符技能名的 AI 键、缺少 ai_skill_invoke、
技能卡漏登记 addMetaObject 等）。

扫描前会先把注释屏蔽掉（用等长空格替换，行号保持不变），
避免模板里 `// general->addSkill(new Xxx);` 这类注释被误判为真实注册。

只读操作，不修改任何文件。
"""

import argparse
import json
import os
import re
import sys

LANG_DIR = os.path.join("lang", "zh_CN")
CPP_DIR = os.path.join("src", "package")
AI_DIRS = [os.path.join("lua", "ai"), os.path.join("extensions", "ai")]

SKILL_BASES = [
    "TriggerSkill", "MasochismSkill", "PhaseChangeSkill", "DrawCardsSkill",
    "GameStartSkill", "DetachEffectSkill", "WeaponSkill", "ArmorSkill",
    "TreasureSkill", "FakeMoveSkill", "BattleArraySkill", "ScenarioRule",
    "ViewAsSkill", "OneCardViewAsSkill", "ZeroCardViewAsSkill", "FilterSkill",
    "ArraySummonSkill", "ProhibitSkill", "DistanceSkill", "MaxCardsSkill",
    "TargetModSkill", "SlashNoDistanceLimitSkill", "InvaliditySkill",
    "AttackRangeSkill", "FixCardSkill", "ViewHasSkill", "Skill",
]

# 根目录合法的最小标志：以下子目录至少存在一个
ROOT_MARKERS = [LANG_DIR, CPP_DIR, os.path.join("lua", "ai")]


# --------------------------------------------------------------------------
# 注释屏蔽：把注释内容换成等长空格，行号与字符串字面量都保持不变
# --------------------------------------------------------------------------

def mask_cpp_comments(text):
    out = []
    i, n = 0, len(text)
    state = None          # None | line | block | str | char
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state is None:
            if c == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 2
            elif c == "/" and nxt == "*":
                state = "block"
                out.append("  ")
                i += 2
            elif c == '"':
                state = "str"
                out.append(c)
                i += 1
            elif c == "'":
                state = "char"
                out.append(c)
                i += 1
            else:
                out.append(c)
                i += 1
        elif state == "line":
            out.append("\n" if c == "\n" else " ")
            if c == "\n":
                state = None
            i += 1
        elif state == "block":
            if c == "*" and nxt == "/":
                state = None
                out.append("  ")
                i += 2
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
        else:  # str / char
            if c == "\\" and nxt:
                out.append(c + nxt)
                i += 2
            elif (state == "str" and c == '"') or (state == "char" and c == "'"):
                state = None
                out.append(c)
                i += 1
            else:
                out.append(c)
                i += 1
    return "".join(out)


def mask_lua_comments(text):
    out = []
    i, n = 0, len(text)
    state = None          # None | line | lblock | str | char
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state is None:
            if c == "-" and nxt == "-":
                if text[i + 2:i + 4] == "[[":
                    state = "lblock"
                    out.append("    ")
                    i += 4
                else:
                    state = "line"
                    out.append("  ")
                    i += 2
            elif c == "[" and nxt == "[":
                j = text.find("]]", i + 2)
                if j == -1:
                    out.append(text[i:])
                    break
                out.append(text[i:j + 2])
                i = j + 2
            elif c == '"':
                state = "str"
                out.append(c)
                i += 1
            elif c == "'":
                state = "char"
                out.append(c)
                i += 1
            else:
                out.append(c)
                i += 1
        elif state == "line":
            out.append("\n" if c == "\n" else " ")
            if c == "\n":
                state = None
            i += 1
        elif state == "lblock":
            if text[i:i + 2] == "]]":
                state = None
                out.append("  ")
                i += 2
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
        else:  # str / char
            if c == "\\" and nxt:
                out.append(c + nxt)
                i += 2
            elif (state == "str" and c == '"') or (state == "char" and c == "'"):
                state = None
                out.append(c)
                i += 1
            else:
                out.append(c)
                i += 1
    return "".join(out)


def mask(text, kind):
    """按语言屏蔽注释。若屏蔽结果异常（吞掉了大半内容）则回退原文，避免误报缺失。"""
    masked = mask_cpp_comments(text) if kind == "cpp" else mask_lua_comments(text)
    if len(masked) != len(text) or len(masked.strip()) < len(text.strip()) * 0.4:
        return text
    return masked


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------

def find_root(start, explicit=None):
    if explicit:
        return os.path.abspath(os.path.normpath(explicit))
    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, "QSanguosha.pro")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def iter_files(root, *rel_dirs, exts=(".lua", ".cpp", ".h")):
    for rel in rel_dirs:
        base = os.path.join(root, rel)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for fn in filenames:
                if fn.endswith(exts):
                    yield os.path.join(dirpath, fn)


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def lineno(text, pos):
    return text.count("\n", 0, pos) + 1


def relpath(root, path):
    return os.path.relpath(path, root).replace("\\", "/")


# --------------------------------------------------------------------------
# ① lang
# --------------------------------------------------------------------------

def scan_lang(root, name):
    """返回 (命中列表, 问题列表)。命中项含文件、类型(name/desc/prompt/notice)。"""
    hits = []
    problems = []
    pat_name = re.compile(r'\[\s*"' + re.escape(name) + r'"\s*\]')
    pat_desc = re.compile(r'\[\s*":' + re.escape(name) + r'"\s*\]')
    pat_prompt = re.compile(r'\[\s*"@' + re.escape(name) + r'(?:-[a-z0-9_-]+)?"\s*\]')
    pat_notice = re.compile(r'\[\s*"~' + re.escape(name) + r'"\s*\]')

    for path in iter_files(root, LANG_DIR, exts=(".lua",)):
        raw = read(path)
        text = mask(raw, "lua")
        rel = relpath(root, path)
        for kind, pat in (("name", pat_name), ("desc", pat_desc),
                          ("prompt", pat_prompt), ("notice", pat_notice)):
            for m in pat.finditer(text):
                tail = text[m.end():text.find("\n", m.end())]
                hits.append({
                    "file": rel, "line": lineno(text, m.start()), "kind": kind,
                    "text": tail.lstrip(" =").strip().strip(",").strip(),
                })

    kinds = [h["kind"] for h in hits]
    if "name" not in kinds:
        problems.append("lang 缺少技能名条目 [\"%s\"]" % name)
    if "desc" not in kinds:
        problems.append("lang 缺少技能描述条目 [\":%s\"]" % name)
    if kinds.count("name") > 1:
        files = sorted({h["file"] for h in hits if h["kind"] == "name"})
        problems.append("lang 技能名重复定义，出现在：%s" % ", ".join(files))
    return hits, problems


# --------------------------------------------------------------------------
# ② C++
# --------------------------------------------------------------------------

def scan_cpp(root, name):
    """返回 (命中列表, 注册列表, 软提示列表, 问题列表)。"""
    hits = []
    problems = []
    notes = []
    ctor_pat = re.compile(r'(\w+Skill)\(\s*"' + re.escape(name) + r'"')
    class_pat = re.compile(r'^\s*class\s+(\w+)\s*:\s*public\s+(\w+)')
    card_pat = re.compile(r'new\s+(\w+Card)\b')

    cpp_files = list(iter_files(root, CPP_DIR, exts=(".cpp", ".h")))
    all_src = list(iter_files(root, "src", exts=(".cpp", ".h")))

    for path in cpp_files:
        text = mask(read(path), "cpp")
        rel = relpath(root, path)
        lines = text.splitlines()
        for m in ctor_pat.finditer(text):
            line = lineno(text, m.start())
            cls, base = None, m.group(1)      # 基类可由构造函数调用的基类名直接得到

            # 类名：优先从 ClassName::ClassName(...) 限定名取（构造函数写在 .cpp、类声明在 .h 的常见形态）
            cur = lines[line - 1].strip() if line - 1 < len(lines) else ""
            qualified = re.match(r'(\w+)::(\w+)\s*\(', cur)
            if qualified and qualified.group(1) == qualified.group(2):
                cls = qualified.group(1)
            else:
                for i in range(line - 1, max(-1, line - 200), -1):
                    cm = class_pat.match(lines[i] if i < len(lines) else "")
                    if cm:
                        cls, base = cm.group(1), cm.group(2)
                        break

            hits.append({"file": rel, "line": line, "class": cls, "base": base})
            if base and base not in SKILL_BASES:
                problems.append("%s:%d 类 %s 的基类 %s 不在已知技能基类列表中，请核对"
                                % (rel, line, cls, base))

    if not hits:
        problems.append("C++ 中未找到 Skill(\"%s\") 构造" % name)

    classes = {h["class"] for h in hits if h["class"]}

    # 全 src/ 扫描注册与技能卡元对象登记（已在 mask 阶段剔除注释）
    src_texts = []
    registered = []
    metaobjects = set()
    cards_used = set()
    addskill_pat = re.compile(r'addSkill\s*\(\s*new\s+(\w+)')
    addplain_pat = re.compile(r'(?:skills\s*<<|<<)\s*new\s+(\w+)')
    addmeta_pat = re.compile(r'addMetaObject\s*<\s*(\w+)\s*>')

    for path in all_src:
        text = mask(read(path), "cpp")
        src_texts.append(text)
        rel = relpath(root, path)
        for m in addskill_pat.finditer(text):
            if m.group(1) in classes:
                registered.append({"file": rel, "line": lineno(text, m.start()),
                                   "class": m.group(1)})
        for m in addplain_pat.finditer(text):
            if m.group(1) in classes:
                registered.append({"file": rel, "line": lineno(text, m.start()),
                                   "class": m.group(1), "form": "skills <<"})
        for m in addmeta_pat.finditer(text):
            metaobjects.add(m.group(1))
        if rel.startswith("src/package/"):
            for m in card_pat.finditer(text):
                cards_used.add(m.group(1))

    if hits and not registered:
        problems.append("C++ 中定义了技能类但未在包中注册（缺 addSkill(new X) 或 skills << new X）")

    # 技能卡元对象登记：用到 new XxxCard 却没 addMetaObject<XxxCard>()，运行期会静默解析失败。
    # 只对本技能相关的卡报警（类名包含本技能类名），避免牵连同文件里其它包的技能卡。
    if classes:
        for card in sorted(cards_used):
            if card in metaobjects:
                continue
            if any(c and c in card for c in classes):
                problems.append("技能卡 %s 未登记元对象（缺 addMetaObject<%s>()），运行期 @%s 会解析失败"
                                % (card, card, card))

    return hits, registered, notes, problems


def scan_pro(root, cpp_hits):
    """检查命中的 .cpp/.h 是否登记进 QSanguosha.pro 的 SOURCES/HEADERS。"""
    problems = []
    pro = os.path.join(root, "QSanguosha.pro")
    if not os.path.isfile(pro):
        return problems
    text = mask(read(pro), "cpp")
    for h in cpp_hits:
        if h["file"] not in text:
            problems.append("%s 未登记进 QSanguosha.pro" % h["file"])
    return problems


# --------------------------------------------------------------------------
# ③ AI
# --------------------------------------------------------------------------

def build_ai_aliases(name, cpp_hits):
    """AI 侧可能用多种键引用同一技能，逐一列出。

    - 大多数 hook 的键就是技能 objectName（连字符归一化为下划线）
    - sgs.ai_skill_use_func 的键是 SkillCard 的类名（如 QuhuCard）
    - sgs.ai_skill_use 的键是 "@@xxx" 形式的 pattern
    """
    normalized = name.replace("-", "_")
    aliases = {name, normalized}
    for h in cpp_hits:
        cls = h.get("class")
        if cls:
            aliases.add(cls)
            aliases.add(cls + "Card")
    return sorted(aliases)


def scan_ai(root, name, aliases):
    """返回 (命中列表, 问题列表, 软提示列表)。命中项含文件、行号、hook 名。"""
    hits = []
    problems = []
    notes = []
    normalized = name.replace("-", "_")

    key_alt = "|".join(re.escape(a) for a in aliases)
    pat = re.compile(r'sgs\.(ai_[a-z_]+)\.(' + key_alt + r')\s*=')
    pat_use = re.compile(r'sgs\.ai_skill_use\[\s*"@@(?:' + key_alt + r')\d*"')
    pat_skills = re.compile(r'\.name\s*=\s*"' + re.escape(name) + r'"')

    for rel_dir in AI_DIRS:
        for path in iter_files(root, rel_dir, exts=(".lua",)):
            text = mask(read(path), "lua")
            rel = relpath(root, path)
            for m in pat.finditer(text):
                hook = m.group(1)
                if m.group(2) != normalized and m.group(2) != name:
                    hook += "(key=%s)" % m.group(2)
                hits.append({"file": rel, "line": lineno(text, m.start()), "hook": hook})
            for m in pat_use.finditer(text):
                hits.append({"file": rel, "line": lineno(text, m.start()),
                             "hook": "ai_skill_use[@@]"})
            for m in pat_skills.finditer(text):
                hits.append({"file": rel, "line": lineno(text, m.start()),
                             "hook": "ai_skills(name=)"})

    raw_hooks = {h["hook"] for h in hits}
    hooks = {h.split("(")[0] for h in raw_hooks}

    if not hits:
        problems.append("AI 中未找到任何与 \"%s\" 相关的 hook（技能将完全不被 AI 使用）" % name)
    else:
        if "ai_skills" in hooks and not ({"ai_skill_use_func", "ai_skill_use"} & hooks):
            problems.append("配了 sgs.ai_skills 但没有 sgs.ai_skill_use_func / ai_skill_use，技能卡不会真正被使用")
        if not ({"ai_skill_invoke", "ai_view_as", "ai_skills", "ai_need_damaged",
                 "ai_skill_discard", "ai_skill_cardask", "ai_skill_choice"} & hooks):
            notes.append("AI 未提供 ai_skill_invoke / ai_view_as；若该技能是可选技，AI 会永不发动（由 cost() 自管询问的技可忽略）")
        if hooks <= {"ai_chat", "ai_chat_func"}:
            notes.append("只找到聊天相关 hook，没有决策 hook，请确认技能 AI 是否遗漏")
    if name != normalized and hits:
        problems.append("技能名含连字符；已按归一化键 \"%s\" 一并检索，AI 侧必须写下划线形式" % normalized)
    return hits, problems, notes


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="三国杀技能三件套自检")
    ap.add_argument("skillname", help="技能 objectName，例如 jianxiong")
    ap.add_argument("--package", help="所属 package（仅用于提示，不参与检索）", default=None)
    ap.add_argument("--root", help="项目根目录（含 QSanguosha.pro），默认向上查找", default=None)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    root = find_root(os.getcwd(), args.root)
    if not root:
        print("错误：未找到 QSanguosha.pro，请用 --root 指定项目根目录", file=sys.stderr)
        return 2
    if not any(os.path.isdir(os.path.join(root, m)) for m in ROOT_MARKERS):
        print("错误：根目录 %s 下既没有 %s，也没有 %s，不像是本项目的根；"
              "若是从 Git Bash 传入路径，请改用 Windows 形式（C:/... 而非 /c/...）"
              % (root, LANG_DIR, CPP_DIR), file=sys.stderr)
        return 2

    name = args.skillname.strip()
    lang_hits, lang_problems = scan_lang(root, name)
    cpp_hits, cpp_reg, cpp_notes, cpp_problems = scan_cpp(root, name)
    pro_problems = scan_pro(root, cpp_hits)
    aliases = build_ai_aliases(name, cpp_hits)
    ai_hits, ai_problems, notes = scan_ai(root, name, aliases)

    problems = lang_problems + cpp_problems + pro_problems + ai_problems
    notes = cpp_notes + notes
    if "-" in name:
        notes.append("技能名含连字符，通常是内部规则技 / 触发技（如 global-maxcards、xxx-viewhas）；"
                     "此类技能一般不需要 lang 条目，请人工确认后再按缺失处理")
    ok = not problems

    if args.json:
        print(json.dumps({
            "root": root, "skill": name, "package": args.package,
            "ai_keys": aliases,
            "lang": lang_hits, "cpp": cpp_hits, "registered": cpp_reg,
            "ai": ai_hits, "problems": problems, "notes": notes, "ok": ok,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    print("项目根：%s" % root)
    print("技能名：%s%s" % (name, ("（package: %s）" % args.package) if args.package else ""))
    print()

    def section(title, items, fmt, empty_msg):
        print("── %s ──" % title)
        if not items:
            print("   （无）%s" % empty_msg)
        else:
            for it in items:
                print("   " + fmt(it))
        print()

    section("① 中文条目 lang/zh_CN", lang_hits,
            lambda h: "%-6s %s:%s  %s" % (h["kind"], h["file"], h["line"], h["text"][:70]),
            "—— 缺失")
    section("② C++ 技能类 src/package", cpp_hits,
            lambda h: "%-14s %s:%s  基类 %s" % (h["class"] or "?", h["file"], h["line"], h["base"]),
            "—— 缺失")
    section("② 注册位置", cpp_reg,
            lambda h: "%s:%s  %s" % (h["file"], h["line"], h["class"]),
            "—— 缺失")
    section("③ 技能 AI lua/ai", ai_hits,
            lambda h: "%-28s %s:%s" % (h["hook"], h["file"], h["line"]),
            "—— 缺失")

    print("── 结论 ──")
    if ok:
        print("   三处齐备，未发现硬性问题。")
    else:
        for p in problems:
            print("   [!] " + p)
    for n in notes:
        print("   [~] " + n)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
