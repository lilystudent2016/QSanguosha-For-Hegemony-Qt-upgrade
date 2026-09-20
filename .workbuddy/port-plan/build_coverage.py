#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
移植覆盖矩阵生成器：QSanguosha(老) -> FreeKill(新)

产出：coverage-matrix.csv
列：技能名 / 中文名 / 老项目C++位置 / 老项目AI hook数 / FreeKill实现位置 / 分类 / 备注

分类规则：
  A  两边都有实现 -> 直接用，零工作
  B  两边都有但需核对描述 -> 可能需改参数
  C  仅老项目有，标准形态 -> 按模板新写（主战场）
  D  仅老项目有且形态特殊 -> 需先查 FreeKill 引擎支持
  ?  仅老项目有但未定位到 C++ 实现 -> 待人工判定（多为卡牌名）
"""
import os
import re
import csv
import sys
import json
from collections import defaultdict

QSG = r"C:\Users\Administrator\code\QSanguosha-For-Hegemony-Qt-upgrade"
FK = r"C:\Users\Administrator\code\FreeKill"
OUT_DIR = os.path.join(QSG, ".workbuddy", "port-plan")

# FreeKill 引擎已支持的特殊形态关键词（用于 D 类判定）
FREEKILL_SPECIAL = [
    "lord", "monarch", "junge", "vassal", "kingdom", "convert",
    "formation", "basara", "pindian", "chain", "wake",
]


def read_text(path):
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


# ---------------------------------------------------------------- 老项目扫描

def scan_qsg_lang():
    """
    从 lang/zh_CN/Package/*.lua 抓三类条目，并区分性质：
      - 武将名: ["caocao"] = "曹操"        -> kind=general
      - 技能名: ["jianxiong"] = "奸雄"     且存在 [":jianxiong"] -> kind=skill
      - 卡牌名: ["slash"] = "杀"（无描述或无 C++ 技能类） -> kind=card
    判定依据（与项目现有约定一致）：
      * 同时有 ["K"] 与 [":K"] 才算技能；
      * 有 ["#K"] 的 K 是武将称号，不算；
      * 剩余有中文名的条目若能在 C++ 里找到技能类 -> skill，否则 card/general（后续再细分）。
    """
    out = {}
    lang_dir = os.path.join(QSG, "lang", "zh_CN", "Package")
    for fn in os.listdir(lang_dir):
        if not fn.endswith(".lua"):
            continue
        text = read_text(os.path.join(lang_dir, fn))
        named = {}   # key -> 中文名
        desc = {}    # key -> 描述
        title = set()  # 武将称号键
        for m in re.finditer(r'\["([a-z_0-9]+)"\]\s*=\s*"([^"]*)"', text):
            named.setdefault(m.group(1), m.group(2))
        for m in re.finditer(r'\[":([a-z_0-9]+)"\]\s*=\s*"([^"]*)"', text):
            desc[m.group(1)] = m.group(2)
        for m in re.finditer(r'\["#([a-z_0-9]+)"\]\s*=', text):
            title.add(m.group(1))
        for key, cn in named.items():
            if key in title:
                continue
            out.setdefault(key, {
                "cn": cn, "desc": desc.get(key, ""),
                "lang_file": fn,
                "has_desc": key in desc,
            })
    return out


# C++ 里基类构造的第一个字符串参数就是技能 objectName
# 例：Jianxiong() : MasochismSkill("jianxiong")
#     Tuxi::Tuxi(const QString &owner) : DrawCardsSkill("tuxi" + owner)
CPP_SKILL_CTOR = re.compile(
    r"class\s+([A-Za-z_]\w*)\s*(?::\s*public\s+([A-Za-z_]\w*))?"   # class 声明 + 可选基类
    r".*?"                                                          # 类体开头
    r'([A-Za-z_]\w*Skill|[A-Za-z_]\w*Card)\s*\(\s*"([a-z_0-9]+)"',  # 构造函数：基类("skillname"
    re.S)


def scan_qsg_cpp():
    """
    抓 src/package/*.cpp 里技能 objectName -> 类名/基类/文件/行号。
    以「基类构造的第一个字符串字面量」为准（这是引擎真正注册的名字）。
    同时记录类声明处的基类，供形态判定使用。
    """
    out = {}
    pkg_dir = os.path.join(QSG, "src", "package")
    for fn in sorted(os.listdir(pkg_dir)):
        if not fn.endswith(".cpp"):
            continue
        text = read_text(os.path.join(pkg_dir, fn))
        # 先建立 类名 -> 基类 映射
        bases = {}
        for m in re.finditer(
                r"class\s+([A-Za-z_]\w*)\s*:\s*public\s+([A-Za-z_]\w*)", text):
            cls, base = m.group(1), m.group(2)
            bases.setdefault(cls, base)
        # 再找构造函数里的技能名
        # 形式1: 类内联  Xxx() : BaseSkill("name")
        # 形式2: 类外    Xxx::Xxx(...) : BaseSkill("name")
        ctor = re.compile(
            r'(?:^|[\s;}])(?:([A-Za-z_]\w*)::)?([A-Za-z_]\w*)\s*\([^)]*\)\s*'
            r'(?::[^;{]*?)?\b([A-Za-z_]\w*(?:Skill|Card))\s*\(\s*"([a-z_0-9]+)"')
        for m in ctor.finditer(text):
            outer_cls, inner_cls, base, skill = m.groups()
            cls = outer_cls or inner_cls
            if not base.endswith(("Skill", "Card")):
                continue
            prev = out.get(skill)
            if prev:
                continue  # 同名技能只记第一次（owner 后缀变体会被 lang 单独列出）
            out[skill] = {
                "class": cls,
                "base": bases.get(cls, base),
                "ctor_base": base,
                "file": fn,
                "line": text[:m.start()].count("\n") + 1,
            }
    return out


def scan_qsg_ai():
    """抓 lua/ai/*.lua 里所有 sgs.ai_xxx.<key> 的 hook，统计每个技能有几个。"""
    hooks = defaultdict(list)
    ai_dir = os.path.join(QSG, "lua", "ai")
    pat = re.compile(r"sgs\.(ai_[a-z_]+)\.([A-Za-z_0-9#]+)\s*=")
    for fn in os.listdir(ai_dir):
        if not fn.endswith(".lua"):
            continue
        text = read_text(os.path.join(ai_dir, fn))
        for m in pat.finditer(text):
            kind, key = m.group(1), m.group(2)
            hooks[key].append({
                "kind": kind, "file": fn,
                "line": text[:m.start()].count("\n") + 1,
            })
    return hooks


# ---------------------------------------------------------------- FreeKill 扫描

def scan_fk_skills():
    """抓 packages/*/pkg/skills/*.lua 的技能名、文件、是否有 addAI / addTest。"""
    out = {}
    pkgs_dir = os.path.join(FK, "packages")
    if not os.path.isdir(pkgs_dir):
        return out
    for pkg in os.listdir(pkgs_dir):
        sk_dir = os.path.join(pkgs_dir, pkg, "pkg", "skills")
        if not os.path.isdir(sk_dir):
            # 技能可能直接放在 pkg/ 下
            sk_dir = os.path.join(pkgs_dir, pkg, "pkg")
            if not os.path.isdir(sk_dir):
                continue
        for fn in os.listdir(sk_dir):
            if not fn.endswith(".lua"):
                continue
            path = os.path.join(sk_dir, fn)
            text = read_text(path)
            names = re.findall(r'name\s*=\s*"([a-z_0-9]+)"', text)
            for name in names:
                out[name] = {
                    "pkg": pkg, "file": fn,
                    "has_ai": "addAI" in text,
                    "has_test": "addTest" in text,
                    "path": os.path.relpath(path, FK),
                }
    return out


def scan_fk_generals():
    """抓 FreeKill 各包已注册的武将名（General:new(extension, "xxx", ...)）。"""
    names = set()
    pkgs_dir = os.path.join(FK, "packages")
    if not os.path.isdir(pkgs_dir):
        return names
    for root, _, files in os.walk(pkgs_dir):
        for fn in files:
            if not fn.endswith(".lua"):
                continue
            text = read_text(os.path.join(root, fn))
            for m in re.finditer(r'General:new\([^,]+,\s*"([a-z_0-9]+)"', text):
                names.add(m.group(1))
    return names


# ---------------------------------------------------------------- 主流程

def main():
    if not os.path.isdir(QSG):
        sys.exit(f"老项目路径不存在: {QSG}")
    if not os.path.isdir(FK):
        sys.exit(f"FreeKill 路径不存在: {FK}")

    qsg_lang = scan_qsg_lang()
    qsg_cpp = scan_qsg_cpp()
    qsg_ai = scan_qsg_ai()
    fk_skills = scan_fk_skills()
    fk_generals = scan_fk_generals()

    rows = []
    for name, info in sorted(qsg_lang.items()):
        cn = info["cn"]
        cpp = qsg_cpp.get(name, {})
        fk = fk_skills.get(name)
        hooks = qsg_ai.get(name, [])

        # ---- 先判定这个条目到底是什么 ----
        # 技能的必要条件：有描述 [":x"]，或能在 C++ 里找到技能类，或有 AI hook
        is_skill = bool(info["has_desc"] or cpp or hooks)
        if not is_skill:
            # 没描述、没 C++、没 AI -> 武将名或卡牌名
            # 武将名：常见于 General 文件，且中文名是 2~4 个汉字且不含"杀/闪/桃/锦囊"等牌名特征
            if name in fk_generals:
                kind = "general_both"      # 两边都有这个武将
            elif re.search(r"^(sha|shan|tao|jiu|jink|slash|peach|analeptic|"
                           r"dismantlement|snatch|duel|indulgence|"
                           r"ex_nihilo|amazing_grace|archery_attack|"
                           r"savage_assault|god_salvation|collateral|"
                           r"nullification|lightning|supply_shortage|"
                           r"iron_chain|fire_attack|drowning|burning|"
                           r"known_both|befriend|await|alliance|"
                           r"conquering|consolidate)", name):
                kind = "card"
            else:
                kind = "general_only"      # 疑似武将名（老项目有，FreeKill 无）
            rows.append({
                "技能名": name, "中文名": cn,
                "性质": kind,
                "老项目lang文件": info["lang_file"],
                "老项目C++类": "", "老项目C++基类": "", "老项目C++位置": "",
                "老项目AI hook数": 0, "FreeKill实现": "",
                "FreeKill有AI": "", "FreeKill有测试": "",
                "分类": "—",
                "备注": {"general_both": "武将是两边都有",
                         "general_only": "武将名，老项目有 FreeKill 无",
                         "card": "卡牌名"}[kind],
            })
            continue

        # ---- 是技能，做分类 ----
        if fk:
            cls = "A"
            note = (f"FreeKill 已有；AI:{'有' if fk['has_ai'] else '无'} "
                    f"测试:{'有' if fk['has_test'] else '无'}")
            if info["desc"]:
                note += "；需核对中文描述是否同版本"
            # 老项目有 AI 但 FreeKill 版本没 AI -> 需要补 AI
            if hooks and not fk["has_ai"]:
                cls = "B"
                note = "FreeKill 有技能实现但缺 AI，需把老项目 AI 移植过来"
        elif cpp:
            base = cpp.get("base", "") or cpp.get("ctor_base", "")
            special = any(k in base.lower() for k in FREEKILL_SPECIAL)
            cls = "D" if special else "C"
            note = (f"老项目基类 {base}；"
                    f"{'需先查 FreeKill 引擎是否有对应机制' if special else '需按 FreeKill 模板重写'}")
        elif hooks:
            cls = "C"
            note = f"有 {len(hooks)} 个 AI hook 但 C++ 未定位到；按 AI 反推实现"
        else:
            # 有描述但无 C++ 技能类、无 AI hook：绝大多数是卡牌名（有 [":x"] 描述）
            cls = "card"
            note = "卡牌名（有描述但无技能类），随卡牌一起移植"

        rows.append({
            "技能名": name,
            "中文名": cn,
            "性质": "skill",
            "老项目lang文件": info["lang_file"],
            "老项目C++类": cpp.get("class", ""),
            "老项目C++基类": cpp.get("base", "") or cpp.get("ctor_base", ""),
            "老项目C++位置": (f"src/package/{cpp['file']}:{cpp['line']}"
                            if cpp else ""),
            "老项目AI hook数": len(hooks),
            "FreeKill实现": fk["path"] if fk else "",
            "FreeKill有AI": ("是" if fk and fk["has_ai"] else ("否" if fk else "")),
            "FreeKill有测试": ("是" if fk and fk["has_test"] else ("否" if fk else "")),
            "分类": cls,
            "备注": note,
        })

    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "coverage-matrix.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 统计
    stat = defaultdict(int)
    kind_stat = defaultdict(int)
    skill_rows = []
    for r in rows:
        stat[r["分类"]] += 1
        kind_stat[r["性质"]] += 1
        if r["性质"] == "skill":
            skill_rows.append(r)

    summary = {
        "老项目lang条目总数": len(rows),
        "其中_技能": kind_stat.get("skill", 0),
        "其中_武将名": kind_stat.get("general_both", 0) + kind_stat.get("general_only", 0),
        "其中_卡牌名": kind_stat.get("card", 0),
        "FreeKill技能数": len(fk_skills),
        "FreeKill武将数": len(fk_generals),
        "技能分类_A_两边都有": stat.get("A", 0),
        "技能分类_C_需按模板新写": stat.get("C", 0),
        "技能分类_D_需查引擎支持": stat.get("D", 0),
        "技能分类_未定位": stat.get("?", 0),
        "参与移植的技能总数A+C+D": stat.get("A", 0) + stat.get("C", 0) + stat.get("D", 0),
        "老项目带AI的技能数": sum(1 for r in skill_rows if r["老项目AI hook数"] > 0),
    }

    json_path = os.path.join(OUT_DIR, "coverage-summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ---- 按包分组的工作量估算 ----
    by_lang = defaultdict(lambda: defaultdict(int))
    for r in skill_rows:
        key = r["老项目lang文件"].replace(".lua", "")
        by_lang[key][r["分类"]] += 1

    work_path = os.path.join(OUT_DIR, "workload-by-package.md")
    with open(work_path, "w", encoding="utf-8") as f:
        f.write("# 按包分组的工作量估算\n\n")
        f.write("| 老项目 lang 文件 | 技能总数 | A 直接用 | B 补AI | C 需新写 | D 需查引擎 | 备注 |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        totals = defaultdict(int)
        for key in sorted(by_lang, key=lambda k: -sum(by_lang[k].values())):
            d = by_lang[key]
            total = sum(d.values())
            for k2, v2 in d.items():
                totals[k2] += v2
            totals["total"] += total
            f.write(f"| {key} | {total} | {d.get('A', 0)} | {d.get('B', 0)} "
                    f"| {d.get('C', 0)} | {d.get('D', 0)} | |\n")
        f.write(f"| **合计** | **{totals['total']}** | {totals['A']} | "
                f"{totals['B']} | {totals['C']} | {totals['D']} | |\n")

    print(f"[OK] {work_path}")

    print(f"[OK] {csv_path}")
    print(f"[OK] {json_path}")
    print()
    print("=== 统计 ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
