
--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/standard-equips.cpp 中缺失的 AI hook
--============================================================

-- 双股剑：目标须弃置一张手牌，否则使用者摸一张牌
-- 作为目标：手牌充裕且丢得起时主动弃牌，阻止对方摸牌
sgs.ai_skill_discard.DoubleSword = function(self, discard_num, min_num, optional, include_equip)
	if self.player:getHandcardNum() <= 1 then return {} end
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByKeepValue(cards)
	if self:getKeepValue(cards[1]) >= 4.1 then return {} end
	return { cards[1]:getEffectiveId() }
end

-- 寒冰剑：造成伤害时可改为弃置目标两张牌（此处挑要弃的那一张）
-- 敌方挑价值最高的拆，友方挑价值最低的拆
sgs.ai_skill_cardchosen.IceSword = function(self, who, flags, method, disable_list)
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

-- 麒麟弓：弃置目标的一匹马，优先废掉其防御马，其次进攻马
sgs.ai_skill_choice.KylinBow = function(self, choices, data)
	if string.find(choices, "dhorse", 1, true) then return "dhorse" end
	if string.find(choices, "ohorse", 1, true) then return "ohorse" end
	return "shorse"
end
