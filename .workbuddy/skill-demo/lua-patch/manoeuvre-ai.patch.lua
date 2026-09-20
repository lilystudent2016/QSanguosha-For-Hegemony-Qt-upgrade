--=== manoeuvre-ai.lua 缺失 AI 补全（qsgs-skill-generator/audit_ai.py 审计） ===
-- 对应 src/package/newsgs.cpp 中 ManoeuvrePackage（huaxin/yanghu/zongyux/dengzhi/
-- luyusheng/fengxi/miheng/xunchen）缺失的 AI hook，键名与 C++ askFor* 的 reason 一一对应。

-- 气傲（宗预）：成为牌的目标后可弃置使用者一张牌，随后自己弃一张
-- 使用者按触发条件必为非同势力，拆其价值最高的一张
sgs.ai_skill_cardchosen.qiao = function(self, who, flags, method, disable_list)
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

-- 气傲：自己弃置一张牌（含装备），弃最不值得保留的
sgs.ai_skill_discard.qiao_discard = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getCards(include_equip and "he" or "h"))
	self:sortByKeepValue(cards)
	local result = {}
	for _, c in ipairs(cards) do
		if #result < discard_num then table.insert(result, c:getId()) end
	end
	return result
end

-- 舌剑（祢衡）：弃光手牌后选择“对使用者造成1点伤害”或“弃其X张牌”
sgs.ai_skill_choice.shejian = function(self, choices, data)
	choices = choices:split("+")
	local target = data:toPlayer()
	if not target then return choices[math.random(1, #choices)] end
	if self:isFriend(target) then
		-- 对友方：能拆牌就拆牌（弃其废牌），否则放弃伤害
		if table.contains(choices, "discard") then return "discard" end
		return "damage"
	end
	if table.contains(choices, "damage") and self:damageIsEffective(target)
	and (self:isWeak(target) or target:getHp() <= 1) then
		return "damage"
	end
	if table.contains(choices, "discard") then return "discard" end
	return choices[math.random(1, #choices)]
end

-- 舌剑：从使用者区域弃置X张牌（X=自己刚弃置的手牌数），拆其关键牌
sgs.ai_skill_cardschosen.shejian = function(self, who, flags, min_num, max_num, method)
	local cards = sgs.QList2Table(who:getCards(flags))
	if #cards == 0 then return {} end
	if self:isFriend(who) then
		self:sortByKeepValue(cards)
	else
		self:sortByUseValue(cards)
	end
	local result = {}
	for _, c in ipairs(cards) do
		if #result < math.max(min_num, 1) and #result < max_num then
			table.insert(result, c:getId())
		else
			break
		end
	end
	return result
end

-- 玉碎（冯熙）：令黑色牌使用者弃置体力上限张手牌（弃最不值的）
sgs.ai_skill_discard.yusui_discard = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getCards(include_equip and "he" or "h"))
	self:sortByKeepValue(cards)
	local result = {}
	for _, c in ipairs(cards) do
		if #result < discard_num then table.insert(result, c:getId()) end
	end
	return result
end

-- 危盟（邓芝）：获得目标至多X张手牌，再把等量的牌交给其
-- 敌方尽量多拿其好牌；友方只拿最少张（随后交回一张有用的牌）
sgs.ai_skill_cardschosen.weimeng = function(self, who, flags, min_num, max_num, method)
	local cards = sgs.QList2Table(who:getCards(flags))
	if #cards == 0 then return {} end
	local result = {}
	if self:isFriend(who) then
		self:sortByKeepValue(cards)
		local want = math.min(math.max(min_num, 1), #cards)
		for _, c in ipairs(cards) do
			if #result < want then table.insert(result, c:getId()) else break end
		end
	else
		self:sortByUseValue(cards)
		-- 拿多少就得还多少，不能超过自己可交出的牌数
		local afford = self.player:getCardCount(true)
		local want = math.min(math.max(min_num, max_num), #cards, afford)
		want = math.max(want, 1)
		for _, c in ipairs(cards) do
			if #result < want then table.insert(result, c:getId()) else break end
		end
	end
	return result
end

-- 危盟（纵横）：获得目标一张手牌
sgs.ai_skill_cardchosen.weimeng = function(self, who, flags, method, disable_list)
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

-- 锋略（荀谌）：输的一方从自己的“手/装/判”区交出牌，交最不值的
sgs.ai_skill_cardschosen.fenglve = function(self, who, flags, min_num, max_num, method)
	local cards = sgs.QList2Table(who:getCards(flags))
	self:sortByKeepValue(cards)
	local result = {}
	for _, c in ipairs(cards) do
		if #result < max_num then table.insert(result, c:getId()) else break end
	end
	return result
end

-- 锋略（纵横）：交出一张自己区域里的牌，同样取最不值的
sgs.ai_skill_cardchosen.fenglve = function(self, who, flags, method, disable_list)
	local function usable(c)
		return c and not table.contains(disable_list, c:getId())
	end
	local cards = sgs.QList2Table(who:getCards(flags))
	self:sortByKeepValue(cards)
	for _, c in ipairs(cards) do
		if usable(c) then return c:getId() end
	end
	return -1
end

-- 德劭（羊祜）：弃置黑色牌使用者一张牌
sgs.ai_skill_cardchosen.deshao = function(self, who, flags, method, disable_list)
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

-- 盗书（蒋干）：获得目标一张手牌
-- 若已知（或预测）的花色与某张手牌一致，则优先拿它，从而触发盗书伤害
sgs.ai_skill_cardchosen.daoshu = function(self, who, flags, method, disable_list)
	local function usable(c)
		return c and not table.contains(disable_list, c:getId())
	end
	local cards = sgs.QList2Table(who:getCards(flags))
	if not self:isFriend(who) and self.daoshu_suit then
		-- 顺序与 Card::Suit 枚举一致：Spade=0 Club=1 Heart=2 Diamond=3
		local suits = {"spade", "club", "heart", "diamond"}
		local want = suits[self.daoshu_suit + 1]
		if want then
			for _, c in ipairs(cards) do
				if usable(c) and c:getSuitString() == want then return c:getId() end
			end
		end
	end
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

-- 论道（南华老仙）：受伤后，来源手牌多于你→弃其一张牌
sgs.ai_skill_cardchosen.lundao = function(self, who, flags, method, disable_list)
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

-- 暗涌（荀谌）：伤害值翻倍后自己弃两张手牌
sgs.ai_skill_discard.anyong_discard = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getCards(include_equip and "he" or "h"))
	self:sortByKeepValue(cards)
	local result = {}
	for _, c in ipairs(cards) do
		if #result < discard_num then table.insert(result, c:getId()) end
	end
	return result
end

-- 共修（南华老仙）：被选中的角色弃置一张牌（含装备）
sgs.ai_skill_discard.gongxiu_throw = function(self, discard_num, min_num, optional, include_equip)
	local cards = sgs.QList2Table(self.player:getCards(include_equip and "he" or "h"))
	self:sortByKeepValue(cards)
	local result = {}
	for _, c in ipairs(cards) do
		if #result < discard_num then table.insert(result, c:getId()) end
	end
	return result
end

-- 明伐（羊祜）：目标手牌少于你时，对其造成伤害并获其一张手牌
sgs.ai_skill_cardchosen.mingfa = function(self, who, flags, method, disable_list)
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
