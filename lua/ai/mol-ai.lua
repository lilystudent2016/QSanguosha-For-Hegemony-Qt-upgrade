--[[********************************************************************
	Copyright (c) 2013-2015 Mogara

  This file is part of QSanguosha-Hegemony.

  This game is free software; you can redistribute it and/or
  modify it under the terms of the GNU General Public License as
  published by the Free Software Foundation; either version 3.0
  of the License, or (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.

  See the LICENSE file for more details.

  Mogara
*********************************************************************]]
--移动版专属

--杜预
sgs.ai_skill_invoke.wuku = true

local miewu_skill = {}
miewu_skill.name = "miewu"
table.insert(sgs.ai_skills, miewu_skill)
miewu_skill.getTurnUseCard = function(self)
	if self.player:getMark("#wuku") == 0 or self.player:hasFlag("MiewuUsed") or self.player:isNude() then
        return
    end
    local cards = sgs.QList2Table(self.player:getCards("he"))
    self:sortByUseValue(cards, true)
    local subcard = cards[1]:getEffectiveId()
    local str = "@MiewuCard=" .. subcard .. ":"
    local card_name

--[[{联军盛宴,火烧连营,桃园结义,南蛮入侵,万箭齐发,
	远交近攻,无中生有,决斗,顺手牵羊,过河拆桥,水淹七军,
	铁索连环,以逸待劳,五谷丰登,勠力同心,调虎离山,敕令,
	借刀杀人,知己知彼,火攻,挟天子以令诸侯}
]]--按锦囊价值排序
	local trickcards = {"alliance_feast","burning_camps","god_salvation","savage_assault","archery_attack",--群体锦囊
	"befriend_attacking","ex_nihilo","duel","snatch","dismantlement","drowning",--单体锦囊
	"iron_chain","await_exhausted","amazing_grace","fight_together","lure_tiger","imperial_order",--几乎不会用到的群体锦囊
	"collateral","known_both","fire_attack","threaten_emperor"}--几乎不会用到的单体锦囊
    local delaycards = {"indulgence","supply_shortage","lightning"}--延时锦囊：乐不思蜀，兵粮寸断，闪电
    local basiccards = {"slash","fire_slash","thunder_slash","peach","analeptic"}--基本牌：普杀，火杀，雷杀，桃，酒

    local can_use = {}
    local value = self:getUseValue(cards[1])
    for _, trick in ipairs(trickcards) do
        local clonecard = sgs.cloneCard(trick)
		local fixed_cards = {"ex_nihilo","threaten_emperor","await_exhausted"}
		if self.player:hasShownSkill("weimu") and cards[1]:isBlack() and table.contains(fixed_cards, trick) then continue end--贾诩不开黑无中
        if self:getUseValue(clonecard) > value then
            clonecard:addSubcard(subcard)
            clonecard:setCanRecast(false)
            local dummyuse = { isDummy = true }
            self:useCardByClassName(clonecard, dummyuse)
            if dummyuse.card then
                table.insert(can_use, trick)
            end
        end
    end
    for _, dtrick in ipairs(delaycards) do
        local clonecard = sgs.cloneCard(dtrick)
        if self:getUseValue(clonecard) > value then
            clonecard:addSubcard(subcard)
            clonecard:setCanRecast(false)
            local dummyuse = { isDummy = true }
            self:useCardByClassName(clonecard, dummyuse)
            if dummyuse.card then
                table.insert(can_use, dtrick)
            end
        end
    end
    for _, basic in ipairs(basiccards) do
        local clonecard = sgs.cloneCard(basic)
        if self:getUseValue(clonecard) > value then
            clonecard:addSubcard(subcard)
            clonecard:setCanRecast(false)
            local dummyuse = { isDummy = true }
            self:useCardByClassName(clonecard, dummyuse)
            if dummyuse.card then
                table.insert(can_use, basic)
            end
        end
    end

    if #can_use > 0 then
		local floors_index = math.random(1, #can_use)--随机一张牌当彩蛋
		if #can_use > 6 then
			floors_index = math.random(1, math.floor((#can_use)/2))
		end
		card_name = can_use[floors_index]
		sgs.ai_use_priority.MiewuCard = math.max(4, self:getDynamicUsePriority(sgs.cloneCard(card_name)))--4是否合适
        return sgs.Card_Parse(str .. card_name)
    end
end

sgs.ai_skill_use_func.MiewuCard = function(card, use, self)
	local userstring = card:toString()--card:getUserString()
	userstring = (userstring:split(":"))[3]
	local miewucard = sgs.cloneCard(userstring)
    miewucard:addSubcard(card:getSubcards():first())
    miewucard:setCanRecast(false)
    if self.player:isCardLimited(miewucard, sgs.Card_MethodUse) then
        return
    end
	self:useCardByClassName(miewucard, use)--确保能使用
	if use.card then
		Global_room:writeToConsole("灭吴卡使用:"..userstring)
		use.card = card
	end
end

function sgs.ai_cardsview.miewu(self, class_name, player, cards)
	if not player:hasShownSkill("miewu") then return end
	if player:getMark("#wuku") == 0 or player:hasFlag("MiewuUsed") or player:isNude() or player:isRemoved() then
        return
    end
    if sgs.Sanguosha:getCurrentCardUseReason() ~= sgs.CardUseStruct_CARD_USE_REASON_RESPONSE_USE
    and sgs.Sanguosha:getCurrentCardUseReason() ~= sgs.CardUseStruct_CARD_USE_REASON_RESPONSE then
        if player:getPhase() == sgs.Player_Play then
			return--为简化仅考虑响应时，实际上加强了ai
		end
    end
	if class_name == "Peach" or class_name == "Analeptic"
    or class_name == "Slash" or class_name == "Jink" or class_name == "Nullification" then
        if not cards then
			cards = {}
			for _, c in sgs.qlist(player:getCards("he")) do
				if sgs.cardIsVisible(c, player, self.player) and c:isKindOf(class_name) then
                else
                    table.insert(cards, c)
                end
			end
			for _, id in sgs.qlist(player:getHandPile()) do
				local c = sgs.Sanguosha:getCard(id)
				if sgs.cardIsVisible(c, player, self.player) and c:isKindOf(class_name) then
                else
                    table.insert(cards, c)
                end
			end
		else--防止AI用天兵灭吴……
			local self_cards = {}
			for _, c in ipairs(cards) do
				local card_place = self.room:getCardPlace(c:getEffectiveId())
				if (card_place ~= sgs.Player_PlaceSpecial or player:getHandPile():contains(c:getEffectiveId())) then
					table.insert(self_cards, c)
				end
			end
			cards = self_cards
		end
        if #cards < 1 then return {} end
		--只有一个灭吴并且持牌充裕时,考虑保留
		if player:getMark("#wuku") == 1 and player:getCardCount(true) > 1 and (class_name == "Slash" or class_name == "Jink") then
			for _, c in ipairs(cards) do
				if c:isKindOf(class_name) then
					return {}
				end
			end
			--其他情况,尽量使用
		end
        --[[if player:getPhase() <= sgs.Player_Play then
            sgs.ais[player:objectName()]:sortByUseValue(cards, true)
        else

        end]]
        sgs.ais[player:objectName()]:sortByKeepValue(cards)

        local className2objectName = { Peach = "peach", Analeptic = "analeptic",
                     Slash = "slash", Jink = "jink", Nullification = "heg_nullification" }--优先国无懈
		local object_name = className2objectName[class_name]
        if class_name == "Slash" then
            local slash = {"slash","fire_slash","thunder_slash"}--随机属性杀
            object_name = slash[math.random(1, #slash)]
        end
        local clonecard = sgs.cloneCard(object_name)

        local function count_value(acard)
        --由于getUseValue会调用getCardsNum，会再次进入视为卡函数导致死循环。身份蛊惑在smart-ai里单独处理
        --[[if player:getPhase() <= sgs.Player_Play then
                return sgs.ais[player:objectName()]:getUseValue(acard)
            else

            end]]
            return sgs.ais[player:objectName()]:getKeepValue(acard)
        end

        local value = count_value(clonecard)
		local nullification_indulgence = (player:getPhase() == sgs.Player_Judge and not player:isSkipped(sgs.Player_Judge) and not player:isSkipped(sgs.Player_Play)
			and class_name == "Nullification" and player:containsTrick("indulgence") and (player:getHandcardNum() > 3 or player:getHandcardNum() > player:getHp() - 1))
        ----可闪的酒杀应该闪而非保留桃(需要当前杀的data)
		for _, c in ipairs(cards) do--未考虑留桃留无懈等
            local card_value = count_value(c)
			if card_value < value or nullification_indulgence or(card_value <= 4.1 and player:getCardCount(true) == 1) then
                Global_room:writeToConsole("灭吴卡打出:"..object_name)
                return "@MiewuCard=" .. c:getEffectiveId() .. ":" .. object_name
            end
        end
	end
end

sgs.ai_view_as.miewu = function(card, player, card_place)--只为无懈自己的乐,因为ai_cardsview触发频率不够,经常2灭吴被乐弃一把高质量牌
	if not player:hasShownSkill("miewu") then return end
	if player:getMark("#wuku") == 0 or player:hasFlag("MiewuUsed") or player:isNude() or player:isRemoved() then
        return
    end
    if sgs.Sanguosha:getCurrentCardUseReason() ~= sgs.CardUseStruct_CARD_USE_REASON_RESPONSE_USE
    and sgs.Sanguosha:getCurrentCardUseReason() ~= sgs.CardUseStruct_CARD_USE_REASON_RESPONSE then
        if player:getPhase() == sgs.Player_Play then
			return--为简化仅考虑响应时，实际上加强了ai
		end
    end
	local nullification_indulgence = (player:getPhase() == sgs.Player_Judge and not player:isSkipped(sgs.Player_Judge) and not player:isSkipped(sgs.Player_Play)
		and player:containsTrick("indulgence") and (player:getHandcardNum() > 3 or player:getHandcardNum() > player:getHp() - 1))
	if not nullification_indulgence then return end
	local suit = card:getSuitString()
	local number = card:getNumberString()
	local card_id = card:getEffectiveId()
	if (card_place ~= sgs.Player_PlaceSpecial or player:getHandPile():contains(card_id)) then
		if not card:isKindOf("Nullification") then
			return ("nullification:miewu[%s:%s]=%d%s"):format(suit, number, card_id, "&miewu")
		end
	end
end

function sgs.ai_cardneed.miewu(to, card, self)
	return to:isNude() and to:getMark("#wuku") > 0
end

--李丰
sgs.ai_skill_invoke.tunchu = function(self, data)
	if not (self:willShowForAttack() or self:willShowForDefence()) then return false end
	local target = 0
	local goodtarget = 0
	local slashnum = 0
	local needburst = 0

	for _, slash in ipairs(self:getCards("Slash")) do
		for _,enemy in ipairs(self.enemies) do
			if self:slashIsEffective(slash, enemy) then
				slashnum = slashnum + 1
				break
			end
		end
	end

	for _,enemy in ipairs(self.enemies) do
		for _, slash in ipairs(self:getCards("Slash")) do
			if not self:slashProhibit(slash, enemy) and self:slashIsEffective(slash, enemy) and sgs.isGoodTarget(enemy, self.enemies, self) then
				goodtarget = goodtarget + 1
				break
			end
		end
	end

	for _,enemy in ipairs(self.enemies) do
		if self.player:canSlash(enemy) then
			target = target + 1
			break
		end
	end

	if slashnum > 1 or (slashnum > 0 and goodtarget > 0) then needburst = 1 end
	self:sort(self.enemies,"defenseSlash")
	local can_save_card_num = self.player:getMaxCards() - self.player:getHandcardNum()
	if target == 0 or can_save_card_num > 1 or self.player:isSkipped(sgs.Player_Play) then return true end
	--if self:needBear() then return true end

	for _,enemy in ipairs(self.enemies) do
		local def = sgs.getDefense(enemy)
		local slash = sgs.Sanguosha:cloneCard("slash", sgs.Card_NoSuit, 0)
		local eff = self:slashIsEffective(slash, enemy) and sgs.isGoodTarget(enemy, self.enemies, self)

		if self:slashProhibit(slash, enemy) then
		elseif eff and def < 8 and needburst > 0 then return false
		end
	end
	return true
end

sgs.ai_skill_exchange.tunchu_push = function(self, pattern, max_num, min_num, expand_pile)
	local cards = self.player:getCards("h")
	cards = sgs.QList2Table(cards)
	self:sortByUseValue(cards,true)
	--self:sortByKeepValue(cards)
	local to_push = {}
	for _, c in ipairs(cards) do
		table.insert(to_push, c:getEffectiveId())
		if #to_push >= max_num then break end
	end
	return to_push
end

sgs.ai_skill_exchange.shuliang = function(self, pattern, max_num, min_num, expand_pile)
	--local target = self.room:getCurrent()
	local cards = self.player:getPile("food")
	return {cards[1]:getEffectiveId()}
end	

--凌操
sgs.ai_skill_invoke.dujin = function(self, data)
	if #self.friends_noself == 0 then return true end
	if sgs.GetConfig("RewardTheFirstShowingPlayer", true) then
		local reward = true
		for _, p in sgs.qlist(self.room:getAlivePlayers()) do
			if p:hasShownOneGeneral() then
				reward = false
				break
			end
		end
		if reward then return true end
	end
	if math.ceil(self.player:getEquips():length() / 2) > 0 then
		return true
	end
	return false
end

--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/mol.cpp 中缺失的 AI hook
--============================================================

-- 引兵：受到【杀】/【决斗】伤害后，将一张“帻”置入弃牌堆
-- 从武将牌上的“帻”里挑最不值得保留的一张
sgs.ai_skill_askforag.yinbingx = function(self, card_ids)
	local cards = {}
	for _, id in ipairs(card_ids) do
		table.insert(cards, sgs.Sanguosha:getCard(id))
	end
	self:sortByKeepValue(cards)
	return cards[1]:getEffectiveId()
end

-- 谋溃：弃置此【杀】目标（或反过来被其弃置）的一张牌
-- 弃的总是对方（self.player 的对立面），敌方拆其价值最高的牌
sgs.ai_skill_cardchosen.moukui = function(self, who, flags, method, disable_list)
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

-- 震袭：当【杀】指定目标后，弃置目标一张牌
sgs.ai_skill_cardchosen.zhenxi = function(self, who, flags, method, disable_list)
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

-- 矜武：出牌阶段开始时选择是否执行军令。
-- 选“否”会立刻结束出牌阶段，因此只要有可【杀】目标就发动
sgs.ai_skill_invoke.jinwu = true

-- 矜武：军令结算后使用一张无实体牌的普【杀】，选最合适的【杀】目标
sgs.ai_skill_playerchosen.jinwu_slash = function(self, targets)
	return sgs.ai_skill_playerchosen.zero_card_as_slash(self, targets)
end

-- 筑科①：当你选择执行军令后，可自行选择军令（优于系统随机指定）
sgs.ai_skill_invoke.zhuke = true

-- 筑科②③：翻面/横置后，令一名同势力角色回复1点体力，优先选伤得最重的队友
sgs.ai_skill_playerchosen.zhuke = function(self, targets)
	local list = sgs.QList2Table(targets)
	self:sort(list, "hp")
	for _, p in ipairs(list) do
		if self:isFriend(p) and p:getLostHp() > 0 then return p end
	end
	return list[1]
end

-- 奇制：弃置一名不为此牌目标的角色的一张牌，令其摸一张牌
-- 优先挑敌方（敌方只能被弃手牌），挑手牌最少的敌方更易命中关键牌
sgs.ai_skill_playerchosen.qizhi = function(self, targets)
	local list = sgs.QList2Table(targets)
	self:sort(list, "handcard")
	for _, p in ipairs(list) do
		if self:isEnemy(p) then return p end
	end
	return nil
end

-- 奇制：弃置其一张牌（敌方为手牌，友方为手牌或装备）
sgs.ai_skill_cardchosen.qizhi = function(self, who, flags, method, disable_list)
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

-- 进趋：结束阶段摸两张牌，然后将手牌弃至 X 张（X=本回合发动“奇制”的次数）
-- 只有原本手牌不超过 X 时才是净赚，否则等于把好牌换成两张
sgs.ai_skill_invoke.jinqu = function(self, data)
	local x = self.player:getMark("#qizhi-turn")
	if x <= 0 then return false end
	return self.player:getHandcardNum() <= x
end

sgs.ai_skill_discard.jinqu = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByKeepValue(cards)
	local to_discard = {}
	for i = 1, math.min(discard_num, #cards) do
		table.insert(to_discard, cards[i]:getEffectiveId())
	end
	return to_discard
end

-- 拒战（偶数次）：与【杀】使用者各摸一张牌，并可暗置其一张武将牌
-- 暗置会使其失去该武将技能，只对敌方有利；对友方则放弃
-- 重入护栏：isFriend 可经 C++ 回调再次触发技能询问而回到本函数（jilei 同型，A1 家族C）
local juzhan_invoking = false
sgs.ai_skill_invoke.juzhan = function(self, data)
	if juzhan_invoking then return false end
	juzhan_invoking = true
	local from = data:toPlayer()
	local ret = false
	if from then ret = not self:isFriend(from) end
	juzhan_invoking = false
	return ret
end

-- 拒战（奇数次）：获得【杀】目标的一张牌，之后本回合不能对其使用牌
-- 优先挑打不到的敌方（避免自废攻势），其次挑敌方
sgs.ai_skill_playerchosen.juzhan = function(self, targets)
	local list = sgs.QList2Table(targets)
	for _, p in ipairs(list) do
		if self:isEnemy(p) and not self.player:inMyAttackRange(p) then return p end
	end
	for _, p in ipairs(list) do
		if self:isEnemy(p) then return p end
	end
	return list[1]
end

-- 拒战：暗置其一张武将牌，主将通常承载主公技/核心技，优先暗置主将
sgs.ai_skill_choice.juzhan = function(self, choices, data)
	if string.find(choices, "head", 1, true) then return "head" end
	if string.find(choices, "deputy", 1, true) then return "deputy" end
	return "cancel"
end

-- 拒战：获得其一张牌 → 敌方挑价值最高的拿
sgs.ai_skill_cardchosen.juzhan = function(self, who, flags, method, disable_list)
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

-- 胆守：弃置区域内所有牌换本回合连续的摸牌。牌太少不值得清空，故要求至少3张
sgs.ai_skill_invoke.danshou = function(self, data)
	local n = 0
	for _, c in ipairs(sgs.QList2Table(self.player:getCards("hej"))) do
		if not self.player:isJilei(c) then n = n + 1 end
	end
	return n >= 3
end

-- 胆守：选择立即摸 X 张，或让本回合以此法摸牌时多摸一张
-- X 未满4时继续加码（攒到一次摸4张可换取1点伤害），满4后立刻摸
sgs.ai_skill_choice.danshou = function(self, choices, data)
	if string.find(choices, "exdraw", 1, true) then
		local x = self.player:getMark("#danshou-turn")
		if x < 4 then return "exdraw" end
		return "draw"
	end
	if string.find(choices, "yes", 1, true) and not string.find(choices, "exdraw", 1, true) then
		local to = data and data:toPlayer() or nil
		if to and not self:isFriend(to) then return "yes" end
		return "no"
	end
	return "draw"
end

-- 肯伤：#kenshang-effect 的重定向（把近处目标换成远处目标）
-- 注：kenshang/#kenshang-effect 在本仓库未被任何武将 addSkill（也无 lang 条目），
--     属未接线的死代码；此处按技能设计意图补齐，保证一旦接线 AI 即可用。
sgs.ai_skill_invoke._kenshang = true

-- 肯伤：本次【杀】伤害打满时，须弃置自身一个技能，优先舍弃“马术”这类次要技能
sgs.ai_skill_choice.kenshang = function(self, choices, data)
	for _, name in ipairs(choices:split("+")) do
		if string.find(name, "mashu", 1, true) then return name end
	end
	local list = choices:split("+")
	return list[1]
end

-- 肯伤：视为技（任意张手牌当【杀】），响应【杀】时给出一组可用牌
sgs.ai_cardsview.kenshang = function(self, class_name, player, cards)
	if class_name ~= "Slash" then return end
	if not cards then
		cards = sgs.QList2Table(player:getCards("h"))
	end
	if #cards < 2 then return {} end
	self:sortByKeepValue(cards)
	local id1 = cards[1]:getEffectiveId()
	local id2 = cards[2]:getEffectiveId()
	return { ("slash:kenshang[to_be_decided:0]=%d+%d&kenshang"):format(id1, id2) }
end

-- 表召：交给一名角色一张牌（另选一名角色作为【知己知彼】目标）
sgs.ai_skill_exchange.biaozhao_give = function(self, pattern, max_num, min_num, expand_pile)
	local cards = sgs.QList2Table(self.player:getCards("he"))
	if #cards == 0 then return {} end
	self:sortByKeepValue(cards)
	return cards[1]:getEffectiveId()
end

local biaozhao_skill = {}
biaozhao_skill.name = "biaozhao"
table.insert(sgs.ai_skills, biaozhao_skill)
biaozhao_skill.getTurnUseCard = function(self)
	if self.player:hasUsed("BiaozhaoCard") then return end
	return sgs.Card_Parse("@BiaozhaoCard=.&biaozhao")
end

sgs.ai_skill_use_func.BiaozhaoCard = function(card, use, self)
	local enemies, friends = {}, {}
	for _, p in sgs.qlist(self.room:getAlivePlayers()) do
		if p:objectName() ~= self.player:objectName() then
			if self:isEnemy(p) then
				table.insert(enemies, p)
			elseif self:isFriend(p) then
				table.insert(friends, p)
			end
		end
	end
	self:sort(enemies, "handcard", true)
	self:sort(friends, "hp")
	local known_both = sgs.cloneCard("known_both")
	for _, e in ipairs(enemies) do
		if not self.player:isProhibited(e, known_both) then
			for _, f in ipairs(friends) do
				if not e:isFriendWith(f) then
					use.card = card
					if use.to then
						use.to:append(e)
						use.to:append(f)
					end
					return
				end
			end
		end
	end
end

-- 勘集：出牌阶段展示所有手牌，花色全不同则摸两张
-- 只有在手牌本身就满足“花色互不相同”时才发动（否则纯亏信息）
local kanji_skill = {}
kanji_skill.name = "kanji"
table.insert(sgs.ai_skills, kanji_skill)
kanji_skill.getTurnUseCard = function(self)
	if self.player:hasUsed("KanjiCard") then return end
	local cards = sgs.QList2Table(self.player:getHandcards())
	if #cards < 2 then return end
	local suits = {}
	for _, c in ipairs(cards) do
		local s = c:getSuitString()
		if suits[s] then return end
		suits[s] = true
	end
	return sgs.Card_Parse("@KanjiCard=.&kanji")
end

sgs.ai_skill_use_func.KanjiCard = function(card, use, self)
	use.card = card
end

-- 愆正：成为其它角色【杀】/普通锦囊的目标后，重铸两张牌
-- 交出手上最没用的两张，牌不够或没舍得丢的就放弃
sgs.ai_skill_cardask["@qianzheng-cost"] = function(self, data, pattern, target, target2)
	local cards = sgs.QList2Table(self.player:getHandcards())
	if #cards < 2 then return "." end
	self:sortByKeepValue(cards)
	if self:getKeepValue(cards[1]) >= 4.1 then return "." end
	return "$" .. cards[1]:getEffectiveId() .. "+" .. cards[2]:getEffectiveId()
end

-- 骁骑：使用【杀】指定目标时，可改为【决斗】并在决斗中额外打出【杀】
-- 【决斗】不能被【闪】响应；我方【杀】储备不落下风（或目标手牌见底）时发动
-- 重入护栏：isFriend/getCardsNum 可经 C++ 回调再次触发技能询问而回到本函数（jilei 同型，A1 家族C）
local xiaoqi_invoking = false
sgs.ai_skill_invoke.xiaoqi = function(self, data)
	if xiaoqi_invoking then return false end
	xiaoqi_invoking = true
	local ret = false
	local use = data:toCardUse()
	if use and use.to then
		local target
		for _, p in sgs.qlist(use.to) do
			if not self:isFriend(p) then
				target = p
				break
			end
		end
		if target then
			ret = self:getCardsNum("Slash") >= target:getCardsNum("Slash") or target:getHandcardNum() <= 1
		end
	end
	xiaoqi_invoking = false
	return ret
end
