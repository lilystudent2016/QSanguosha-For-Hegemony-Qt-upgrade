# -*- coding: utf-8 -*-
"""把 patch 片段以 CRLF 追加到目标 .lua 文件末尾（保持项目行尾风格）。
用法: python append_patch.py <target.lua> <patch.lua>
若已包含同一 marker 则不重复追加。"""
import sys, io

target, patch = sys.argv[1], sys.argv[2]
tdata = open(target, "rb").read()
pdata = open(patch, "rb").read()

# 归一化：统一成 LF 再统一转 CRLF
ttext = tdata.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
ptext = pdata.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")

if not ttext.endswith("\n"):
    ttext += "\n"
ptext = ptext.lstrip("\n")

# 幂等：patch 首行非空注释作为指纹
fingerprint = next((l for l in ptext.split("\n") if l.strip()), "")
if fingerprint and fingerprint in ttext:
    print("SKIP  %s (already contains %r)" % (target, fingerprint[:60]))
    sys.exit(0)

new = ttext + "\n" + ptext
if not new.endswith("\n"):
    new += "\n"
open(target, "wb").write(new.replace("\n", "\r\n").encode("utf-8"))
print("APPEND %s  <- %s  (+%d lines)" % (target, patch, ptext.count("\n")))
