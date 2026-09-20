
--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/momentum.cpp 中缺失的 AI hook
--============================================================

-- 锋矢：被【杀】指定为目标时，须弃置一张装备（否则随机弃）
-- 主动交出最不心疼的一张装备，规避随机弃置
sgs.ai_skill_cardask["@fengshi-discard"] = function(self, data, pattern, target, target2)
	local cand = {}
	for _, c in ipairs(sgs.QList2Table(self.player:getEquips())) do
		if self.player:canDiscard(self.player, c:getEffectiveId()) then
			table.insert(cand, c)
		end
	end
	if #cand == 0 then return "." end
	self:sortByKeepValue(cand)
	return "$" .. cand[1]:getEffectiveId()
end

-- 焚鸣：对所有处于横置状态的角色各弃置一张牌
-- 敌方拆其价值最高的牌，友方拆其价值最低的牌
sgs.ai_skill_cardchosen.fenming = function(self, who, flags, method, disable_list)
	local function usable(c)
		return c and not table.contains(disable_list, c:getId())
	end
	local cards = sgs.QList2Table(who:getCards(flags))
	if self:isFriend(who) then
		self:sortByKeepValue(cards)
	else
		self:sortByUseValue(cards)
	end
	for _, c in ipairs(cards) do
		if usable(c) then return c:getId() end
	end
	return -1
end

-- 横征：获得每名其他角色区域里的一张牌
-- 友方：优先拿走其判定区里的负面牌（变相帮忙）；敌方：拿走其价值最高的牌
sgs.ai_skill_cardchosen.hengzheng = function(self, who, flags, method, disable_list)
	local function usable(c)
		return c and not table.contains(disable_list, c:getId())
	end
	local cards = sgs.QList2Table(who:getCards(flags))
	if self:isFriend(who) then
		local harmful = { Indulgence = true, SupplyShortage = true, Lightning = true }
		for _, c in ipairs(cards) do
			if usable(c) and harmful[c:getClassName()] then return c:getId() end
		end
		self:sortByKeepValue(cards)
		for _, c in ipairs(cards) do
			if usable(c) then return c:getId() end
		end
	else
		self:sortByUseValue(cards)
		for _, c in ipairs(cards) do
			if usable(c) and not c:isKindOf("Lightning") then return c:getId() end
		end
		for _, c in ipairs(cards) do
			if usable(c) then return c:getId() end
		end
	end
	return -1
end
