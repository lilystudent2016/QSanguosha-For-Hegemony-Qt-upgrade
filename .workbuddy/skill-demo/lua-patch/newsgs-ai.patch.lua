--=== newsgs-ai.lua 缺失 AI 补全（qsgs-skill-generator/audit_ai.py 审计） ===
-- 对应 src/package/newsgs.cpp 中 NewSGSPackage（jianggan/yangwan/zhouyi/lvlingqi/
-- nanhualaoxian/ty_duyu/huangquan/panjinshu）缺失的 AI hook。

-- 诱言（杨婉）：回合内因弃置而失去牌后，亮出牌堆顶四张并获得花色不同的牌
-- 期望收益为正（约得3张、弃1张），且每回合限一次，故默认发动
sgs.ai_skill_invoke.youyan = true

-- 追还（杨婉）：选择一至两名角色，赋予“追还（伤害）/（弃牌）”
-- 优先给敌方挂标记（其受伤时反击来源 / 令来源弃牌）
sgs.ai_skill_playerchosen.zhuihuan = function(self, targets, max_num, min_num)
	local targetlist = sgs.QList2Table(targets)
	local result = {}
	self:sort(targetlist, "hp")
	for _, target in ipairs(targetlist) do
		if self:isEnemy(target) and #result < max_num then
			table.insert(result, target)
		end
	end
	if #result == 0 then
		for _, target in ipairs(targetlist) do
			if not self:isFriend(target) and #result < max_num then
				table.insert(result, target)
			end
		end
	end
	return result
end

-- 追还：为选中的角色选择适用效果
sgs.ai_skill_choice.zhuihuan = function(self, choices, data)
	choices = choices:split("+")
	local target = data:toPlayer()
	if target and self:isFriend(target) then
		-- 友方挂“弃牌”：其受伤时能让伤害来源弃两张牌，收益更稳
		if table.contains(choices, "discard") then return "discard" end
	end
	-- 敌方挂“伤害”：其受伤时会对来源反击1点伤害
	if table.contains(choices, "damage") then return "damage" end
	return choices[math.random(1, #choices)]
end

-- 追还（效果）：令伤害来源弃置两张牌
sgs.ai_skill_discard.zhuihuan_discard = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getCards(include_equip and "he" or "h"))
	self:sortByKeepValue(cards)
	local result = {}
	for _, c in ipairs(cards) do
		if #result < discard_num then table.insert(result, c:getId()) end
	end
	return result
end

-- 倾势（杜预）：对本次牌的目标之一造成1点伤害
sgs.ai_skill_playerchosen.qingshi = function(self, targets)
	local targetlist = sgs.QList2Table(targets)
	if #targetlist == 0 then return nil end
	self:sort(targetlist, "hp")
	for _, target in ipairs(targetlist) do
		if self:isEnemy(target) and self:damageIsEffective(target) then
			return target
		end
	end
	for _, target in ipairs(targetlist) do
		if not self:isFriend(target) and self:damageIsEffective(target) then
			return target
		end
	end
	return targetlist[1]
end

-- 途绝（黄权）：将全部牌交给一名其他角色，随后回复X点体力并摸X张牌
-- 交给体力最高、最可能站住的友方
sgs.ai_skill_playerchosen.tujue = function(self, targets)
	local targetlist = sgs.QList2Table(targets)
	if #targetlist == 0 then return nil end
	self:sort(targetlist, "hp", true)
	for _, target in ipairs(targetlist) do
		if self:isFriend(target) then return target end
	end
	for _, target in ipairs(targetlist) do
		if not self:isEnemy(target) then return target end
	end
	return targetlist[1]
end

-- 谏国（杜预）：选择一项令目标执行
-- 目标由 ai_skill_use_func.JianguoCard 记录在 self.jianguo_target 上
sgs.ai_skill_choice.jianguo = function(self, choices, data)
	choices = choices:split("+")
	local target = self.jianguo_target
	self.jianguo_target = nil
	if target then
		local h = target:getHandcardNum()
		if self:isEnemy(target) then
			-- 敌方手牌多时“摸一张再弃一半”，净减其手牌
			if h >= 3 and table.contains(choices, "d1tx") then return "d1tx" end
			if table.contains(choices, "t1dx") then return "t1dx" end
		elseif self:isFriend(target) then
			-- 友方手牌少时先摸一张再弃半张，相当于过牌
			if h <= 2 and table.contains(choices, "d1tx") then return "d1tx" end
			if table.contains(choices, "t1dx") then return "t1dx" end
		end
	end
	if table.contains(choices, "d1tx") then return "d1tx" end
	return choices[math.random(1, #choices)]
end

-- 谏国：目标弃置手牌（弃一半或弃一张），弃最不值的
sgs.ai_skill_discard.jianguo = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getCards("h"))
	self:sortByKeepValue(cards)
	local result = {}
	for _, c in ipairs(cards) do
		if #result < discard_num then table.insert(result, c:getId()) end
	end
	return result
end

-- 谏国：技能卡可用性 + 目标选择
local jianguo_skill = {}
jianguo_skill.name = "jianguo"
table.insert(sgs.ai_skills, jianguo_skill)
jianguo_skill.getTurnUseCard = function(self)
	if self.player:hasUsed("JianguoCard") then return end
	if #self.enemies == 0 and #self.friends_noself == 0 then return end
	return sgs.Card_Parse("@JianguoCard=.&jianguo")
end

sgs.ai_skill_use_func.JianguoCard = function(card, use, self)
	local target
	local enemies = {}
	for _, p in ipairs(self.enemies) do enemies[#enemies + 1] = p end
	self:sort(enemies, "handcard")
	if #enemies > 0 then target = enemies[1] end
	if not target then
		self:sort(self.friends_noself, "handcard", true)
		if #self.friends_noself > 0 then target = self.friends_noself[1] end
	end
	if target then
		self.jianguo_target = target
		use.card = card
		if use.to then use.to:append(target) end
	end
end

sgs.ai_use_priority.JianguoCard = 3.5

-- 劝谏（黄权）：令一名同势力角色选择是否执行军令，不执行则其下次受伤+1
-- 技能卡可用性 + 目标选择
local quanjian_skill = {}
quanjian_skill.name = "quanjian"
table.insert(sgs.ai_skills, quanjian_skill)
quanjian_skill.getTurnUseCard = function(self)
	if self.player:hasUsed("QuanjianCard") then return end
	if #self.friends == 0 then return end
	return sgs.Card_Parse("@QuanjianCard=.&quanjian")
end

sgs.ai_skill_use_func.QuanjianCard = function(card, use, self)
	local target
	self:sort(self.friends, "hp", true)
	for _, f in ipairs(self.friends) do
		if self.player:isFriendWith(f) then
			target = f
			break
		end
	end
	if target then
		use.card = card
		if use.to then use.to:append(target) end
	end
end

sgs.ai_use_priority.QuanjianCard = 3

-- 织纴（潘谨淑）：使用第一张红色非转化牌时选择“卜算”或“弃置女性角色的装备”
sgs.ai_skill_choice.zhiren = function(self, choices, data)
	choices = choices:split("+")
	-- 卜算（控制牌堆顶）收益稳定，优先选择
	if table.contains(choices, "busuan") then return "busuan" end
	if table.contains(choices, "discard") then return "discard" end
	return "cancel"
end

-- 织纴：选择一名有装备的女性角色，拆其装备（优先敌方且装备价值高者）
sgs.ai_skill_playerchosen.zhiren = function(self, targets)
	local targetlist = sgs.QList2Table(targets)
	if #targetlist == 0 then return nil end
	local function equipv(p)
		local v = 0
		for _, c in sgs.qlist(p:getEquips()) do
			v = v + self:getUseValue(c)
		end
		return v
	end
	table.sort(targetlist, function(a, b) return equipv(a) > equipv(b) end)
	for _, target in ipairs(targetlist) do
		if self:isEnemy(target) then return target end
	end
	for _, target in ipairs(targetlist) do
		if not self:isFriend(target) then return target end
	end
	return targetlist[1]
end

-- 织纴：选择弃置的装备牌
sgs.ai_skill_cardchosen.zhiren = function(self, who, flags, method, disable_list)
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
