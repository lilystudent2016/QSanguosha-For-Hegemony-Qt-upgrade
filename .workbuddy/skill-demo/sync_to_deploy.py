import os
import shutil
import hashlib

SRC_DIR = r"C:\Users\Administrator\code\QSanguosha-For-Hegemony-Qt-upgrade\lua\ai"
DEP_DIRS = [
    r"C:\Users\Administrator\code\build-QSanguosha-Desktop_Qt_5_14_2_MinGW_64_bit-Debug\debug\lua\ai",
    r"C:\Users\Administrator\code\QSanguosha-For-Hegemony-Qt-upgrade\build-QSanguosha-Desktop_Qt_5_15_2_MSVC2019_64bit-Debug\debug\lua\ai"
]

def sha256(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def sync_to(dep_dir):
    if not os.path.isdir(dep_dir):
        print(f"[SKIP] Deploy dir not found: {dep_dir}")
        return
    bak_dir = os.path.join(os.path.dirname(dep_dir), "lua_ai_backup_prepatch")
    os.makedirs(bak_dir, exist_ok=True)
    synced = []
    for fn in sorted(os.listdir(SRC_DIR)):
        if not fn.endswith(".lua"):
            continue
        src_f = os.path.join(SRC_DIR, fn)
        dep_f = os.path.join(dep_dir, fn)
        if not os.path.exists(dep_f):
            continue
        h_src = sha256(src_f)
        h_dep = sha256(dep_f)
        if h_src != h_dep:
            bak_f = os.path.join(bak_dir, fn)
            if not os.path.exists(bak_f):
                shutil.copy2(dep_f, bak_f)
            shutil.copy2(src_f, dep_f)
            synced.append(fn)
    print(f"[OK] Synced {len(synced)} files to {dep_dir}")

def main():
    for d in DEP_DIRS:
        sync_to(d)

if __name__ == "__main__":
    main()
