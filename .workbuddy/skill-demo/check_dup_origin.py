"""对比 HEAD 与当前工作区：我们新增的 hook 是否覆盖了原有 AI 逻辑。

用法：
  python check_dup_origin.py --root <repo>
输出：
  - 每个被改动的 live AI 文件中，哪些 hook 键在 HEAD 已存在、现在又多了一份（= 覆盖）
  - 哪些是全新键（正常补全）
"""
import argparse
import os
import re
import subprocess
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


def registrations(text):
    out = []
    for rx in REG_RES:
        for m in rx.finditer(text):
            if m.group(1) in HOOK_TABLES:
                out.append((m.group(1), m.group(2)))
    for m in re.finditer(r'(\w+)\.name\s*=\s*"([^"]+)"', text):
        out.append(("ai_skills", m.group(2)))
    return out


def git_show(root, path):
    r = subprocess.run(["git", "show", "HEAD:%s" % path], cwd=root,
                       capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    live_dir = os.path.join(root, "lua", "ai")

    override, fresh, gone = [], [], []
    for fn in sorted(os.listdir(live_dir)):
        if not fn.endswith(".lua"):
            continue
        cur = open(os.path.join(live_dir, fn), "rb").read().decode("utf-8", "replace")
        head = git_show(root, "lua/ai/%s" % fn)
        if head is None:
            continue
        c_cur = defaultdict(int)
        c_head = defaultdict(int)
        for h, k in registrations(cur):
            c_cur[(h, k)] += 1
        for h, k in registrations(head):
            c_head[(h, k)] += 1
        for key, n in c_cur.items():
            hn = c_head.get(key, 0)
            if hn > 0 and n > hn:
                override.append((fn, key[0], key[1], hn, n))
            elif hn == 0:
                fresh.append((fn, key[0], key[1], n))
        for key, n in c_head.items():
            if key not in c_cur:
                gone.append((fn, key[0], key[1]))

    print("【新增（HEAD 无，本次补全）】%d 条" % len(fresh))
    for f in fresh:
        print("   + %-26s %s.%s  x%d" % (f[0], f[1], f[2], f[3]))
    print()
    print("【覆盖（HEAD 已有，本次又加了一份 ⇒ 原逻辑被替换）】%d 条" % len(override))
    for f in override:
        print("   ! %-26s %s.%s  HEAD=%d 现在=%d" % (f[0], f[1], f[2], f[3], f[4]))
    print()
    print("【丢失（HEAD 有，当前没有）】%d 条" % len(gone))
    for f in gone:
        print("   - %-26s %s.%s" % (f[0], f[1], f[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
