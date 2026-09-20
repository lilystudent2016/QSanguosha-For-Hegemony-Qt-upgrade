
--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/transformation.cpp 中缺失的 AI hook
--============================================================

-- 旋略：失去装备区的牌后，可弃置一名其他角色的一张牌
-- 与 playerchosen 的选择保持一致：敌方挑价值最高的拆
sgs.ai_skill_cardchosen.xuanlue = function(self, who, flags, method, disable_list)
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

-- 制蛮（含 zhiman-second 收尾）：获得目标装备区/判定区的一张牌
-- 友方：优先拿走其判定区的负面牌；敌方：拿走其价值最高的牌
sgs.ai_skill_cardchosen.zhiman = function(self, who, flags, method, disable_list)
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
	else
		self:sortByUseValue(cards)
	end
	for _, c in ipairs(cards) do
		if usable(c) then return c:getId() end
	end
	return -1
end

-- 智愚：展示同色手牌后，伤害来源须弃置一张手牌
sgs.ai_skill_discard.zhiyu = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByKeepValue(cards)
	local to_discard = {}
	for i = 1, math.min(discard_num, #cards) do
		table.insert(to_discard, cards[i]:getEffectiveId())
	end
	return to_discard
end
