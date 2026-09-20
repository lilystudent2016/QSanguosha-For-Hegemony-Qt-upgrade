# -*- coding: utf-8 -*-
"""
修复校验器发现的真实缺陷（对 活文件 与 补丁源 双写）：
  R1 mol:   ai_skill_invoke.juzhan  加重入护栏（isFriend 经 C++ 可再入，jilei 同型）
  R2 mol:   ai_skill_invoke.xiaoqi  加重入护栏（isFriend/getCardsNum 同上）
  R3 lord_ex: ai_skill_invoke.wuyan 加重入护栏（isFriend 同上）
  R4 mol:   biaozhao_give 空牌分支 return nil -> return {}（worker 契约只接受 number/table）
CRLF 保持：读写按 LF 归一化比对，写出统一 CRLF。
"""
import io
import sys

ROOT = "C:/Users/Administrator/code/QSanguosha-For-Hegemony-Qt-upgrade"
PAIRS = [
    # (文件相对路径们：同一份替换要写到的每个拷贝)
    (ROOT + "/lua/ai/mol-ai.lua", ROOT + "/.workbuddy/skill-demo/lua-patch/mol-ai.patch.lua"),
    (ROOT + "/lua/ai/lord_ex-ai.lua", ROOT + "/.workbuddy/skill-demo/lua-patch/lord_ex-ai.patch.lua"),
]

# ---- R1 juzhan ----
R1_OLD = """sgs.ai_skill_invoke.juzhan = function(self, data)
\tlocal from = data:toPlayer()
\tif not from then return false end
\treturn not self:isFriend(from)
end"""
R1_NEW = """-- 重入护栏：isFriend 可经 C++ 回调再次触发技能询问而回到本函数（jilei 同型，A1 家族C）
local juzhan_invoking = false
sgs.ai_skill_invoke.juzhan = function(self, data)
\tif juzhan_invoking then return false end
\tjuzhan_invoking = true
\tlocal from = data:toPlayer()
\tlocal ret = false
\tif from then ret = not self:isFriend(from) end
\tjuzhan_invoking = false
\treturn ret
end"""

# ---- R2 xiaoqi ----
R2_OLD = """sgs.ai_skill_invoke.xiaoqi = function(self, data)
\tlocal use = data:toCardUse()
\tif not use or not use.to then return false end
\tlocal target
\tfor _, p in sgs.qlist(use.to) do
\t\tif not self:isFriend(p) then
\t\t\ttarget = p
\t\t\tbreak
\t\tend
\tend
\tif not target then return false end
\treturn self:getCardsNum("Slash") >= target:getCardsNum("Slash") or target:getHandcardNum() <= 1
end"""
R2_NEW = """-- 重入护栏：isFriend/getCardsNum 可经 C++ 回调再次触发技能询问而回到本函数（jilei 同型，A1 家族C）
local xiaoqi_invoking = false
sgs.ai_skill_invoke.xiaoqi = function(self, data)
\tif xiaoqi_invoking then return false end
\txiaoqi_invoking = true
\tlocal ret = false
\tlocal use = data:toCardUse()
\tif use and use.to then
\t\tlocal target
\t\tfor _, p in sgs.qlist(use.to) do
\t\t\tif not self:isFriend(p) then
\t\t\t\ttarget = p
\t\t\t\tbreak
\t\t\tend
\t\tend
\t\tif target then
\t\t\tret = self:getCardsNum("Slash") >= target:getCardsNum("Slash") or target:getHandcardNum() <= 1
\t\tend
\tend
\txiaoqi_invoking = false
\treturn ret
end"""

# ---- R3 wuyan ----
R3_OLD = """sgs.ai_skill_invoke.wuyan = function(self, data)
\tlocal damage = data and data:toDamage() or nil
\tif damage and damage.from and damage.from:objectName() == self.player:objectName() then
\t\treturn damage.to and self:isFriend(damage.to) or false
\tend
\treturn true
end"""
R3_NEW = """-- 重入护栏：isFriend 可经 C++ 回调再次触发技能询问而回到本函数（jilei 同型，A1 家族C）
local wuyan_invoking = false
sgs.ai_skill_invoke.wuyan = function(self, data)
\tif wuyan_invoking then return true end
\twuyan_invoking = true
\tlocal ret = true
\tlocal damage = data and data:toDamage() or nil
\tif damage and damage.from and damage.from:objectName() == self.player:objectName() then
\t\tret = damage.to and self:isFriend(damage.to) or false
\tend
\twuyan_invoking = false
\treturn ret
end"""

# ---- R4 biaozhao_give ----
R4_OLD = """sgs.ai_skill_exchange.biaozhao_give = function(self, pattern, max_num, min_num, expand_pile)
\tlocal cards = sgs.QList2Table(self.player:getCards("he"))
\tif #cards == 0 then return nil end"""
R4_NEW = """sgs.ai_skill_exchange.biaozhao_give = function(self, pattern, max_num, min_num, expand_pile)
\tlocal cards = sgs.QList2Table(self.player:getCards("he"))
\tif #cards == 0 then return {} end"""


def load(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def save(path, text):
    with open(path, "wb") as f:
        f.write(text.replace("\n", "\r\n").encode("utf-8"))


def apply_rules(path, rules):
    t = load(path)
    applied = []
    for rid, old, new in rules:
        if new in t:
            applied.append((rid, "already"))
            continue
        if old in t:
            t = t.replace(old, new, 1)
            applied.append((rid, "patched"))
        else:
            applied.append((rid, "NOT FOUND"))
    save(path, t)
    return applied


def main():
    mol_rules = [("R1", R1_OLD, R1_NEW), ("R2", R2_OLD, R2_NEW), ("R4", R4_OLD, R4_NEW)]
    lord_rules = [("R3", R3_OLD, R3_NEW)]
    jobs = [
        ("lua/ai/mol-ai.lua", mol_rules),
        (".workbuddy/skill-demo/lua-patch/mol-ai.patch.lua", mol_rules),
        ("lua/ai/lord_ex-ai.lua", lord_rules),
        (".workbuddy/skill-demo/lua-patch/lord_ex-ai.patch.lua", lord_rules),
    ]
    ok = True
    for rel, rules in jobs:
        for st, aid in apply_rules(ROOT + "/" + rel, rules):
            print("%-58s %s %s" % (rel, aid, st))
            if st == "NOT FOUND":
                ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
