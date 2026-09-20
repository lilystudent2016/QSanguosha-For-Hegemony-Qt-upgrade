"""仓库隐私/资产盘点：扫描自动生成资料中的敏感信息，并分类（保留 / 忽略 / 需脱敏）。

用法：
  python scan_privacy_assets.py --root <repo> [--out <file>]
"""
import argparse
import os
import re
from collections import defaultdict

TEXT_EXT = {".md", ".txt", ".py", ".lua", ".json", ".yaml", ".yml", ".pro",
            ".cpp", ".h", ".cxx", ".ts", ".ini", ".cfg", ".sh", ".bat", ".ps1"}

SECRET_PATTERNS = [
    ("硬编码口令/密钥", re.compile(
        r'(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|'
        r'private[_-]?key|client[_-]?secret)\b\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]{6,})')),
    ("GitHub PAT", re.compile(r'\bghp_[A-Za-z0-9]{20,}\b')),
    ("OpenAI 风格密钥", re.compile(r'\bsk-[A-Za-z0-9]{20,}\b')),
    ("Bearer 令牌", re.compile(r'Bearer\s+[A-Za-z0-9\-\._]{16,}')),
    ("邮箱地址", re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b')),
    ("Windows 用户目录绝对路径", re.compile(r'[A-Za-z]:\\+Users\\+([^\\\s"\'）)]+)')),
    ("IPv4 地址", re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')),
    ("私钥文件标记", re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
]

SKIP_DIRS = {".git", "node_modules", "audio", "image", "font", "diy",
             "skins", "hero-skin", "lib", "include"}


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--targets", nargs="*", default=None,
                    help="限定扫描的相对路径（默认扫 .workbuddy + 未跟踪/改动文件）")
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    if args.targets:
        files = []
        for t in args.targets:
            p = os.path.join(root, t)
            if os.path.isdir(p):
                files += list(iter_files(p))
            elif os.path.isfile(p):
                files.append(p)
    else:
        files = list(iter_files(os.path.join(root, ".workbuddy")))

    hits = defaultdict(list)
    scanned = 0
    for p in files:
        ext = os.path.splitext(p)[1].lower()
        if ext not in TEXT_EXT:
            continue
        try:
            raw = open(p, "rb").read()
        except Exception:
            continue
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("utf-8", errors="replace")
        scanned += 1
        rel = os.path.relpath(p, root)
        for name, rx in SECRET_PATTERNS:
            for m in rx.finditer(text):
                line = text[:m.start()].count("\n") + 1
                snippet = m.group(0)
                if len(snippet) > 80:
                    snippet = snippet[:80] + "..."
                hits[name].append("%s:%d  %s" % (rel, line, snippet))

    lines = []
    lines.append("扫描文件数：%d" % scanned)
    lines.append("")
    for name, _ in SECRET_PATTERNS:
        items = hits.get(name, [])
        lines.append("【%s】%d 处" % (name, len(items)))
        for it in items[:40]:
            lines.append("   " + it)
        if len(items) > 40:
            lines.append("   ...（另有 %d 处）" % (len(items) - 40))
        lines.append("")

    out = "\n".join(lines)
    print(out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)


if __name__ == "__main__":
    main()
