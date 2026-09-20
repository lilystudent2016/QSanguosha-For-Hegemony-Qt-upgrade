-- ============================================================
-- 生成物 Jianxiong —— 由 scaffold_skill.py 自动生成
-- objectName: jianxiong   中文名: 奸雄
-- 落点：lua/ai/<pkg>-ai.lua（往已存在的文件追加；已存在文件不需要登记）
-- hook 全表与签名见 references/ai-hooks.md
-- ============================================================

--奸雄
-- 3) 是否发动（可选技必配，否则 AI 永不发动）
sgs.ai_skill_invoke.jianxiong = function(self, data)
	-- TODO: 国战常先判断亮将意愿：self:willShowForMasochism() / willShowForAttack() / willShowForDefence()
	return true
end

