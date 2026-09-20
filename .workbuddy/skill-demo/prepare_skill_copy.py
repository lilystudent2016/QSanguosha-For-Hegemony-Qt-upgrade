"""把用户级 skill 复制进仓库并做路径脱敏，便于随代码一起推送。

- 源：C:\\Users\\Administrator\\.workbuddy\\skills\\qsgs-skill-generator
- 目标：<repo>/tools/skill/qsgs-skill-generator
- 排除：.cache/ 之类的大缓存
- 脱敏：本机绝对路径 -> 占位符
"""
import os
import shutil

SRC = r"C:\Users\Administrator\.workbuddy\skills\qsgs-skill-generator"
DST = r"C:\Users\Administrator\code\QSanguosha-For-Hegemony-Qt-upgrade\tools\skill\qsgs-skill-generator"

REPL = [
    (r"C:\Users\Administrator\code\QSanguosha-For-Hegemony-Qt-upgrade", "<repo-root>"),
    (r"C:\Users\Administrator\code\code_sgs", "<ruleset-kb>"),
    (r"C:/Users/Administrator/code/QSanguosha-For-Hegemony-Qt-upgrade", "<repo-root>"),
    (r"C:/Users/Administrator/code/code_sgs", "<ruleset-kb>"),
    (r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe", "<python>"),
    (r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe", "<python>"),
    (r"C:\Users\Administrator\.workbuddy\skills\qsgs-skill-generator", "<skill-dir>"),
]

SKIP_DIRS = {".cache", "__pycache__"}


def main():
    if os.path.exists(DST):
        shutil.rmtree(DST)
    n = 0
    for dirpath, dirnames, filenames in os.walk(SRC):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, SRC)
        outdir = DST if rel == "." else os.path.join(DST, rel)
        os.makedirs(outdir, exist_ok=True)
        for fn in filenames:
            srcf = os.path.join(dirpath, fn)
            dstf = os.path.join(outdir, fn)
            with open(srcf, "rb") as f:
                raw = f.read()
            try:
                text = raw.decode("utf-8")
                for a, b in REPL:
                    text = text.replace(a, b)
                with open(dstf, "w", encoding="utf-8", newline="") as f:
                    f.write(text)
            except UnicodeDecodeError:
                shutil.copy2(srcf, dstf)
            n += 1
    print("copied %d files -> %s" % (n, DST))

    # 顺带把仓库内我生成的报告里的本机绝对路径脱敏
    repo = r"C:\Users\Administrator\code\QSanguosha-For-Hegemony-Qt-upgrade"
    wb = os.path.join(repo, ".workbuddy")
    m = 0
    for dirpath, dirnames, filenames in os.walk(wb):
        for fn in filenames:
            if not fn.lower().endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            with open(p, "rb") as f:
                text = f.read().decode("utf-8", errors="replace")
            new = text.replace(repo, "<repo>").replace(repo.replace("\\", "/"), "<repo>")
            if new != text:
                with open(p, "w", encoding="utf-8", newline="") as f:
                    f.write(new)
                m += 1
    print("desensitized %d markdown files" % m)


if __name__ == "__main__":
    main()
