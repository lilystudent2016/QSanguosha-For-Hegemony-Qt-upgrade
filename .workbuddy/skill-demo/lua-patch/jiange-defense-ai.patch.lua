
--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/jiange-defense.cpp 中缺失的 AI hook
--============================================================

sgs.ai_skill_invoke.jgfengjian = true
sgs.ai_skill_invoke.jghuchen = true
sgs.ai_skill_invoke.jgqinzhen = true
sgs.ai_skill_invoke.jgshuailing = true
sgs.ai_skill_invoke.jgtianjiang = true
sgs.ai_skill_invoke.jgxiaorui = true
sgs.ai_skill_invoke.jgzhenxi = true

-- 奈落：翻面换全体敌方弃光装备，敌方装备总数>=2 或自身已背面时发动
function sgs.ai_skill_invoke.jgnailuo(self, data)
	local n = 0
	for _, enemy in ipairs(self.enemies) do
		if not self.player:isFriendWith(enemy) then
			n = n + enemy:getCards("e"):length()
		end
	end
	return n >= 2 or not self.player:faceUp()
end

-- 奔雷：对一名敌方器械造成2点雷电伤害，选最脆的敌人
sgs.ai_skill_playerchosen.jgbenlei = function(self, targets)
	local targetlist = sgs.QList2Table(targets)
	self:sort(targetlist, "hp")
	for _, p in ipairs(targetlist) do
		if self:isEnemy(p) then return p end
	end
	return targetlist[1]
end

-- 贪食：锁定弃一张手牌，弃最没价值的
sgs.ai_skill_discard.jgtanshi_discard = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByKeepValue(cards)
	local to_discard = {}
	for i = 1, math.min(discard_num, #cards) do
		table.insert(to_discard, cards[i]:getEffectiveId())
	end
	return to_discard
end

-- 缴械：被迫交给对方一张牌，交最没价值的
sgs.ai_skill_exchange.jgjiaoxie_give = function(self, pattern, max_num, min_num, expand_pile)
	local cards = sgs.QList2Table(self.player:getCards("he"))
	self:sortByKeepValue(cards)
	return cards[1]:getEffectiveId()
end
