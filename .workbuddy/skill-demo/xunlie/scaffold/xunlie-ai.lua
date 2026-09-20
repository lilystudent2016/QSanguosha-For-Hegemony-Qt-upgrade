-- ============================================================
-- 生成物 Xunlie —— 由 scaffold_skill.py 自动生成
-- objectName: xunlie   中文名: 巡猎
-- 落点：lua/ai/<pkg>-ai.lua（往已存在的文件追加；已存在文件不需要登记）
-- hook 全表与签名见 references/ai-hooks.md
-- ============================================================

--巡猎
-- 1) 让 AI 在出牌阶段"想起"这个技能（技能卡 / 视为技必配，否则 AI 永远不会用）
local xunlie_skill = {}
xunlie_skill.name = "xunlie"
table.insert(sgs.ai_skills, xunlie_skill)
xunlie_skill.getTurnUseCard = function(self)
	-- 出牌阶段限一次
	if self.player:hasUsed("XunlieCard") then return end

	-- TODO: 判断是否值得发动（敌方数量、目标是否虚弱、代价是否划得来）
	-- TODO: 构造技能卡字符串（含实体牌）：
	--   return sgs.Card_Parse("@XunlieCard=<card_id>&xunlie")   -- 需要消耗牌时
	--   return sgs.Card_Parse("@XunlieCard=.&xunlie")           -- 不消耗牌时
	return nil
end

-- 2) 技能卡的选目标与结算策略（键是【类名】，不是技能名 —— 高频错误点）
sgs.ai_skill_use_func.XunlieCard = function(card, use, self)
	if #self.enemies == 0 then return end
	-- TODO: 选目标，通过写 use.card 与 use.to 表达决策
	-- use.card = card
	-- if use.to then use.to:append(target) end
end

-- 4) 询问选项（choices = "（把 choices 里的一项原样返回）"）
--    注意：这里的 self.player 是【被询问者】，不一定是技能拥有者
sgs.ai_skill_choice.xunlie = function(self, choices, data)
	-- TODO: 按局势返回选项串
	return choices
end

-- 5) 选目标（reason = "xunlie"）
sgs.ai_skill_playerchosen.xunlie = function(self, targets, max_num, min_num)
	self:sort(self.enemies, "hp")
	for _, p in ipairs(self.enemies) do
		if targets:contains(p) then return p end
	end
end

-- 6) 弃牌选择（reason = "xunlie"）
sgs.ai_skill_discard.xunlie = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByKeepValue(cards, true)
	local result = {}
	for i = 1, math.min(discard_num, #cards) do
		result[#result + 1] = cards[i]:getId()
	end
	return result
end

-- 9) 数值偏好（让 AI 正确评估这张技能卡）
sgs.ai_use_value.XunlieCard = 3.5
sgs.ai_card_intention.XunlieCard = 80
sgs.dynamic_value.damage_card.XunlieCard = true
