
--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/formation.cpp 中缺失的 AI hook
--============================================================

-- 护援：结束阶段曹洪弃置所选角色装备区/判定区里的一张牌
--   对友方：优先拆掉乐不思蜀 / 兵粮寸断 / 闪电等负面判定牌
--   对敌方：拆掉其价值最高的装备或判定牌
sgs.ai_skill_cardchosen.huyuan = function(self, who, flags, method, disable_list)
	local cards = sgs.QList2Table(who:getCards(flags))
	local function usable(c)
		return c and not table.contains(disable_list, c:getId())
	end
	if self:isFriend(who) then
		local harmful = { Indulgence = true, SupplyShortage = true, Lightning = true }
		for _, c in ipairs(cards) do
			if usable(c) and harmful[c:getClassName()] then return c:getId() end
		end
	end
	self:sortByUseValue(cards)
	for _, c in ipairs(cards) do
		if usable(c) then return c:getId() end
	end
	return -1
end

-- 挑衅：目标未对你出杀，则你弃置其一张牌（手牌或装备）
sgs.ai_skill_cardchosen.tiaoxin = function(self, who, flags, method, disable_list)
	local function usable(c)
		return c and not table.contains(disable_list, c:getId())
	end
	-- 敌方手牌已见底时，优先拆掉其装备，废掉其攻击/防御手段
	if self:isEnemy(who) and who:getHandcardNum() <= 1 then
		for _, c in ipairs(sgs.QList2Table(who:getEquips())) do
			if usable(c) then return c:getId() end
		end
	end
	local cards = sgs.QList2Table(who:getCards(flags))
	self:sortByUseValue(cards)
	for _, c in ipairs(cards) do
		if usable(c) then return c:getId() end
	end
	return -1
end
