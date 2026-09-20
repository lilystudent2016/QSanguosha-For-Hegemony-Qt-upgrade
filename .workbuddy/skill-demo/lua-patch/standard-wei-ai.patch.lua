
--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/standard-wei-generals.cpp 中缺失的 AI hook
--============================================================

-- 刚烈：判定为黑色时弃置伤害来源的一张牌 → 敌方挑价值最高的拆
sgs.ai_skill_cardchosen.ganglie = function(self, who, flags, method, disable_list)
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
