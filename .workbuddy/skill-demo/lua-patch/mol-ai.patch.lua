
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
