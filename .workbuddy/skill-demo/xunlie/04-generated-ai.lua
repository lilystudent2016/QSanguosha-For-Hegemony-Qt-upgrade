-- ============================================================
-- 生成物 ③：技能 AI
-- 落点：lua/ai/<pkg>-ai.lua（往已存在的文件里追加，不需要在 smart-ai.lua 登记）
-- 键名一律用技能 objectName。本技能无连字符，无需归一化。
-- ============================================================

--巡猎（示例武将）

-- 1) 让 AI 在出牌阶段"想起"这张技能卡
--    技能卡不配这一段，AI 永远不会主动发动 —— 这是技能卡最常见的"AI 不会用"根因
local xunlie_skill = {}
xunlie_skill.name = "xunlie"
table.insert(sgs.ai_skills, xunlie_skill)
xunlie_skill.getTurnUseCard = function(self)
	if self.player:hasUsed("XunlieCard") then return end          -- 出牌阶段限一次
	if not self:willShowForAttack() then return end               -- 国战亮将意愿
	if #self.enemies == 0 then return end

	-- 先挑出可以弃置的牌（被"鸡肋"之类封印的牌不能作消耗），弃最不值钱的那张
	local usable = {}
	for _, card in ipairs(sgs.QList2Table(self.player:getHandcards())) do
		if not self.player:isJilei(card) then usable[#usable + 1] = card end
	end
	if #usable == 0 then return end
	self:sortByKeepValue(usable, true)

	return sgs.Card_Parse("@XunlieCard=" .. tostring(usable[1]:getId()) .. "&xunlie")
end

-- 2) 选目标
--    键是【技能卡类名 XunlieCard】，不是技能名 —— 这是第二个高频错误点
sgs.ai_skill_use_func.XunlieCard = function(xunlie_card, use, self)
	self:sort(self.enemies, "hp")
	for _, enemy in ipairs(self.enemies) do
		if self:isWeak(enemy)
		and not self:cantbeHurt(enemy)
		and self:damageIsEffective(enemy)
		and not self:needDamagedEffects(enemy, self.player)
		and not self:needToLoseHp(enemy) then
			use.card = xunlie_card
			if use.to then use.to:append(enemy) end
			return
		end
	end
end

-- 3) 被询问者的选择（reason = "xunlie"，choices = "discard+damage"）
--    注意：这里的 self.player 是【被询问的目标】，不是技能拥有者
sgs.ai_skill_choice.xunlie = function(self, choices, data)
	local hand = self.player:getHandcardNum()
	if hand == 0 then return "damage" end                         -- 无牌可弃，只能吃伤害
	if self.player:getHp() <= 1 then return "discard" end         -- 只剩 1 血，不能再挨打
	return hand > 2 and "discard" or "damage"                     -- 牌多弃牌，牌少硬吃
end

-- 4) 被询问者的弃牌选择（reason 同样是技能 objectName）
sgs.ai_skill_discard.xunlie = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByKeepValue(cards, true)
	local result = {}
	for i = 1, math.min(discard_num, #cards) do
		result[#result + 1] = cards[i]:getId()
	end
	return result
end

-- 5) 数值偏好：让 AI 正确评估这张技能卡
sgs.ai_use_value.XunlieCard = 3.5
sgs.ai_card_intention.XunlieCard = 80
sgs.dynamic_value.damage_card.XunlieCard = true
