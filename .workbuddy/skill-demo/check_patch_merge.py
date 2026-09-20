"""校验补丁是否已完整合并进 live 树（防止 patch 与 live 漂移）。

用法：
  python check_patch_merge.py --root <repo>
输出：每个补丁文件里注册的所有 hook 键，是否都能在 lua/ai/<同名 live>.lua 中找到；
      同时报告 live 文件中是否存在重复注册（同一键被定义两次 = 后写覆盖前写）。
"""
import argparse
import os
import re
from collections import defaultdict

HOOK_TABLES = {
    "ai_skill_invoke", "ai_skill_choice", "ai_skill_discard", "ai_skill_exchange",
    "ai_skill_cardchosen", "ai_skill_cardschosen", "ai_skill_askforag",
    "ai_skill_playerchosen", "ai_skill_cardask", "ai_skill_suit",
    "ai_skill_use", "ai_skill_use_func", "ai_skills", "ai_cardsview",
    "ai_view_as", "ai_card_intention", "ai_cardneed", "ai_use_priority",
}

REG_RES = [
    re.compile(r"sgs\.(\w+)\.([\w#@_\-]+)\s*="),
    re.compile(r'sgs\.(\w+)\[\s*"([^"]+)"\s*\]\s*='),
]


def read(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def registrations(text, fname):
    out = []
    for rx in REG_RES:
        for m in rx.finditer(text):
            hook, key = m.group(1), m.group(2)
            if hook in HOOK_TABLES:
                out.append((hook, key, text[:m.start()].count("\n") + 1))
    for m in re.finditer(r'(\w+)\.name\s*=\s*"([^"]+)"', text):
        out.append(("ai_skills", m.group(2), text[:m.start()].count("\n") + 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    root = args.root.replace("\\", "/").rstrip("/")
    patch_dir = os.path.join(root, ".workbuddy/skill-demo/lua-patch")
    live_dir = os.path.join(root, "lua/ai")

    total = 0
    problems = []
    for pf in sorted(os.listdir(patch_dir)):
        if not pf.endswith(".patch.lua"):
            continue
        live_name = pf.replace(".patch.lua", ".lua")
        live_path = os.path.join(live_dir, live_name)
        ptxt = read(os.path.join(patch_dir, pf))
        regs = registrations(ptxt, pf)
        if not os.path.exists(live_path):
            problems.append("[缺失] %s 无对应 live 文件 %s" % (pf, live_name))
            continue
        ltxt = read(live_path)
        for hook, key, ln in regs:
            total += 1
            if hook == "ai_skills":
                # ai_skills 走 table.insert(sgs.ai_skills, x)，键体现在 x.name = "key"
                pats = [r'\.name\s*=\s*"%s"' % re.escape(key)]
            else:
                pats = [r"sgs\.%s\.%s\s*=" % (hook, re.escape(key)),
                        r'sgs\.%s\[\s*"%s"\s*\]\s*=' % (hook, re.escape(key))]
            if not any(re.search(p, ltxt) for p in pats):
                problems.append("[未合并] %s:%d  %s.%s  在 %s 中不存在"
                                % (pf, ln, hook, key, live_name))

    # live 树重复注册检查
    dup = []
    for fn in sorted(os.listdir(live_dir)):
        if not fn.endswith(".lua"):
            continue
        txt = read(os.path.join(live_dir, fn))
        seen = defaultdict(int)
        for hook, key, ln in registrations(txt, fn):
            seen[(hook, key)] += 1
        for (hook, key), n in seen.items():
            if n > 1:
                dup.append("[重复] %s  %s.%s  定义 %d 次（后者覆盖前者）" % (fn, hook, key, n))

    print("补丁注册点合计：%d" % total)
    print("未合并/缺失问题：%d" % len(problems))
    for p in problems:
        print("  " + p)
    print("live 树重复注册：%d" % len(dup))
    for d in dup:
        print("  " + d)
    return 1 if (problems or dup) else 0


if __name__ == "__main__":
    raise SystemExit(main())
