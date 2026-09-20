import sys, re, lupa

def check_file(path):
    with open(path, 'rb') as f:
        content = f.read().decode('utf-8', errors='replace')
    # 本项目 QSanguosha Lua 引擎支持 continue 扩展关键字，
    # 但 lupa (标准 Lua) 不支持。为校验语法正确性，将独立的 continue 替换为 do end
    sanitized = re.sub(r'\bcontinue\b', 'do end', content)
    rt = lupa.LuaRuntime()
    rt.compile(sanitized)

ok = True
for path in sys.argv[1:]:
    try:
        check_file(path)
        print("OK   ", path)
    except Exception as e:
        ok = False
        print("FAIL ", path, "->", e)

sys.exit(0 if ok else 1)
