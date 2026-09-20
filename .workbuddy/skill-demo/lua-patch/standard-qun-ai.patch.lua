
--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/standard-qun-generals.cpp 中缺失的 AI hook
--============================================================

-- 死谏：可弃置一名其他角色的一张牌 → 敌方挑价值最高的拆
sgs.ai_skill_cardchosen.sijian = function(self, who, flags, method, disable_list)
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

-- 狂斧结算后若无伤害，潘凤须弃置两张手牌
sgs.ai_skill_discard.kuangfu_discard = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByKeepValue(cards)
	local to_discard = {}
	for i = 1, math.min(discard_num, #cards) do
		table.insert(to_discard, cards[i]:getEffectiveId())
	end
	return to_discard
end
