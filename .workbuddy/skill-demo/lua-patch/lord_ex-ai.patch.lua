
--============================================================
-- 以下由 qsgs-skill-generator/audit_ai.py 审计后补全
-- 对应 src/package/lord-ex.cpp 中缺失的 AI hook
--============================================================

-- 通用：按“弃置/获得”语境挑一张牌。
--   获得类（MethodGet）→ 敌方挑价值最高的拿；
--   弃置类（MethodDiscard）→ 敌方挑价值最高的拆、友方挑价值最低的丢。
local function lordex_pick_card(self, who, flags, method, disable_list)
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

-- 通用：从自己这里弃置若干张牌，丢最不心疼的
local function lordex_discard(self, discard_num, include_equip)
	local flag = include_equip and "he" or "h"
	local cards = sgs.QList2Table(self.player:getCards(flag))
	self:sortByKeepValue(cards)
	local to_discard = {}
	for i = 1, math.min(discard_num, #cards) do
		table.insert(to_discard, cards[i]:getEffectiveId())
	end
	return to_discard
end

-- ---------- 步骘 义舍（bushi） ----------

-- ③准备阶段弃置 X 张牌（X=存活数-体力-2），X 由引擎算出后传入 discard_num
sgs.ai_skill_discard.bushi_discard = function(self, discard_num, min_num, optional, include_equip)
	return lordex_discard(self, discard_num, include_equip)
end

-- ---------- 晋势力 进贤（jinxian） ----------

-- 明置后，距离<2 的已明置角色须暗置一张武将牌。
-- 被暗置会失去该武将技能，优先暗置副将（主将通常承载主将技/核心技）
sgs.ai_skill_choice.jinxian_hide = function(self, choices, data)
	if string.find(choices, "deputy", 1, true) then return "deputy" end
	if string.find(choices, "head", 1, true) then return "head" end
	return "cancel"
end

sgs.ai_skill_discard.jinxian_discard = function(self, discard_num, min_num, optional, include_equip)
	return lordex_discard(self, discard_num, include_equip)
end

-- ---------- 凉凡 量函（liangfan） ----------

-- “函”造成的伤害结算后，可获得该角色一张牌
sgs.ai_skill_cardchosen.liangfan = function(self, who, flags, method, disable_list)
	return lordex_pick_card(self, who, flags, method, disable_list)
end

-- ---------- 连翩（lianpian） ----------

-- #lianpian-other：对方选择弃置你一张牌时，由对方指定弃哪张
sgs.ai_skill_cardchosen.lianpian = function(self, who, flags, method, disable_list)
	return lordex_pick_card(self, who, flags, method, disable_list)
end

-- ---------- 郦食其 礼下（lixia） ----------

-- 弃置其装备区里的一张牌作为触发代价
sgs.ai_skill_cardchosen.lixia = function(self, who, flags, method, disable_list)
	return lordex_pick_card(self, who, flags, method, disable_list)
end

sgs.ai_skill_discard.lixia_discard = function(self, discard_num, min_num, optional, include_equip)
	return lordex_discard(self, discard_num, include_equip)
end

-- ---------- 匈奴 雄略（xiongnve） ----------

-- 对“戮”同势力角色造成伤害后，获得其一张牌
sgs.ai_skill_cardchosen.xiongnve = function(self, who, flags, method, disable_list)
	return lordex_pick_card(self, who, flags, method, disable_list)
end

-- ---------- 指道（zhidao） ----------

-- 对其造成伤害后获得其区域里的一张牌（手牌/装备/判定区）
sgs.ai_skill_cardchosen.zhidao = function(self, who, flags, method, disable_list)
	return lordex_pick_card(self, who, flags, method, disable_list)
end

-- ---------- 爆烈（baolie） ----------

-- 攻击范围内有你且与你势力不同的角色若未对（包括你在内的角色）出【杀】，你弃其一张牌
sgs.ai_skill_cardchosen.baolie = function(self, who, flags, method, disable_list)
	return lordex_pick_card(self, who, flags, method, disable_list)
end

-- ---------- 建言（jianyan） ----------

-- 选择亮出牌堆顶的牌之类别/颜色：危急时优先基本牌（桃/杀），否则优先锦囊
sgs.ai_skill_choice.jianyan = function(self, choices, data)
	if self:isWeak() and string.find(choices, "basic", 1, true) then return "basic" end
	if string.find(choices, "trick", 1, true) then return "trick" end
	return (choices:split("+"))[1]
end

-- 令一名男性角色获得亮出的牌；牌足够好就自己留下，否则给手牌最少的队友
sgs.ai_skill_playerchosen.jianyan = function(self, targets)
	local list = sgs.QList2Table(targets)
	local card_id = self.player:getMark("jianyan")
	local card = (card_id and card_id > 0) and sgs.Sanguosha:getCard(card_id) or nil
	if card and self:getUseValue(card) >= 6 then
		for _, p in ipairs(list) do
			if p:objectName() == self.player:objectName() then return p end
		end
	end
	self:sort(list, "handcard")
	for _, p in ipairs(list) do
		if self:isFriend(p) then return p end
	end
	return list[1]
end

local jianyan_skill = {}
jianyan_skill.name = "jianyan"
table.insert(sgs.ai_skills, jianyan_skill)
jianyan_skill.getTurnUseCard = function(self)
	if self.player:hasUsed("JianyanCard") then return end
	return sgs.Card_Parse("@JianyanCard=.&jianyan")
end

sgs.ai_skill_use_func.JianyanCard = function(card, use, self)
	use.card = card
end

-- ---------- 矜伐（jinfa） ----------

-- 目标选择“令你获得其一张牌”时，由你指定要获得哪一张
sgs.ai_skill_cardchosen.jinfa = function(self, who, flags, method, disable_list)
	return lordex_pick_card(self, who, flags, method, disable_list)
end

-- ---------- 举荐（jujian） ----------

-- 结束阶段弃置一张非基本牌，令一名同势力其他角色变更（双方可能各摸两张）
sgs.ai_skill_use["@@jujian"] = function(self, prompt, method)
	local cand = {}
	for _, c in ipairs(sgs.QList2Table(self.player:getHandcards())) do
		if c:getTypeId() ~= sgs.Card_TypeBasic then
			table.insert(cand, c)
		end
	end
	if #cand == 0 then return "." end
	local friends = {}
	for _, p in sgs.qlist(self.room:getAlivePlayers()) do
		if p:objectName() ~= self.player:objectName() and self:isFriend(p)
				and p:getMark("jujiantransformUsed") == 0 then
			table.insert(friends, p)
		end
	end
	if #friends == 0 then return "." end
	self:sort(friends, "hp")
	self:sortByKeepValue(cand)
	return "@JujianCard=" .. cand[1]:getEffectiveId() .. "&jujian->" .. friends[1]:objectName()
end

-- ---------- 恃才（shicai） ----------

sgs.ai_skill_discard.shicai_discard = function(self, discard_num, min_num, optional, include_equip)
	return lordex_discard(self, discard_num, include_equip)
end

-- ---------- 夙智（suzhi） ----------

-- ③其他角色的牌于你回合内被弃置后，你获得其一张牌
sgs.ai_skill_cardchosen.suzhi = function(self, who, flags, method, disable_list)
	return lordex_pick_card(self, who, flags, method, disable_list)
end

-- ---------- 统率（tongling） ----------

-- 选一名同势力角色 B 接牌；B 手牌越多越有能力出牌，故按手牌降序取首个
sgs.ai_skill_playerchosen.tongling = function(self, targets)
	local list = sgs.QList2Table(targets)
	self:sort(list, "handcard", true)
	return list[1]
end

-- B 用一张手牌当自身使用；优先用【杀】痛击敌方（不可指定 tongling_usetarget）
sgs.ai_skill_use["@@tongling_usecard"] = function(self, prompt, method)
	local seg = prompt:split(":")
	local victim_name = seg[3]
	local victim
	for _, p in sgs.qlist(self.room:getAlivePlayers()) do
		if p:objectName() == victim_name then victim = p break end
	end
	local cards = sgs.QList2Table(self.player:getHandcards())
	self:sortByUseValue(cards)
	for _, c in ipairs(cards) do
		if c:isKindOf("Slash") and c:isAvailable(self.player) then
			for _, p in sgs.qlist(self.room:getAlivePlayers()) do
				if p:objectName() ~= self.player:objectName()
						and (not victim or p:objectName() ~= victim:objectName())
						and self:isEnemy(p) and not self:slashProhibit(c, p) then
					return "@TonglingCard=" .. c:getEffectiveId() .. "&tongling_usecard->" .. p:objectName()
				end
			end
		end
	end
	return "."
end

-- ---------- 无焰（wuyan） ----------

-- 锁定技：防止渠道为锦囊的伤害。
-- 自己在用锦囊打敌方时，宁可放弃该技能（免得替对手挡伤）；其余情况一律发动
-- 重入护栏：isFriend 可经 C++ 回调再次触发技能询问而回到本函数（jilei 同型，A1 家族C）
local wuyan_invoking = false
sgs.ai_skill_invoke.wuyan = function(self, data)
	if wuyan_invoking then return true end
	wuyan_invoking = true
	local ret = true
	local damage = data and data:toDamage() or nil
	if damage and damage.from and damage.from:objectName() == self.player:objectName() then
		ret = damage.to and self:isFriend(damage.to) or false
	end
	wuyan_invoking = false
	return ret
end
