-- ============================================================
-- 技能 AI 骨架
-- 落点：lua/ai/<pkg>-ai.lua（先 grep 确认正确文件；已存在的文件无需登记）
-- hook 全表与签名见 references/ai-hooks.md
-- !! 技能名必须与 C++ 的 objectName() 逐字一致；带 "-" 的键要换成 "_"
-- ============================================================

--{{武将中文名}}

-- 1) 是否发动（可选技必配，否则 AI 永不发动）
sgs.ai_skill_invoke.{{skillname}} = function(self, data)
	if not self:willShowForMasochism() then return false end   -- 国战亮将意愿，按技能性质替换成 Attack / Defence
	return false
end

-- 2) 询问选项（技能里有 askForChoice 时才需要）
sgs.ai_skill_choice.{{skillname}} = function(self, choices, data)
	return choices
end

-- 3) 选目标（技能里有 askForPlayerChosen 时才需要；reason 用技能的 objectName）
sgs.ai_skill_playerchosen.{{skillname}} = function(self, targets, max_num, min_num)
	for _, p in sgs.qlist(targets) do
		if self:isEnemy(p) then return p end
	end
end

-- 4) 选牌（技能里有 askForCardChosen / askForDiscard 时才需要）
sgs.ai_skill_cardchosen.{{skillname}} = function(self, who, flags, method, disable_list)
	local cards = who:getCards(flags)
	if not cards:isEmpty() then return cards:first() end
end

-- 5) 视为技（ViewAsSkill 族必配，否则 AI 不会使用该技能）
-- sgs.ai_view_as.{{skillname}} = function(card, player, card_place)
-- 	local suit = card:getSuitString()
-- 	local number = card:getNumberString()
-- 	local card_id = card:getEffectiveId()
-- 	if card:isBlack() and (card_place == sgs.Player_PlaceHand or player:getHandPile():contains(card_id)) then
-- 		return ("jink:{{skillname}}[%s:%s]=%d&{{skillname}}"):format(suit, number, card_id)
-- 	end
-- end

-- 6) 出牌阶段主动使用（技能卡 / 视为技需要 AI 主动想起时）
-- local {{skillname}}_skill = {}
-- {{skillname}}_skill.name = "{{skillname}}"
-- table.insert(sgs.ai_skills, {{skillname}}_skill)
-- {{skillname}}_skill.getTurnUseCard = function(self, has_no_card)
-- 	if self.player:hasUsed("{{SkillName}}Card") then return end
-- 	return sgs.Card_Parse("@{{SkillName}}Card=.&{{skillname}}")
-- end

-- 7) 技能卡的选目标与结算策略（键为 SkillCard 的类名）
-- sgs.ai_skill_use_func.{{SkillName}}Card = function(QHCard, use, self)
-- 	if #self.enemies == 0 then return end
-- 	use.card = QHCard
-- 	if use.to then use.to:append(self.enemies[1]) end
-- end

-- 8) 数值偏好（按需）
-- sgs.ai_use_priority.{{SkillName}}Card = 9.2
-- sgs.{{general}}_keep_value = { Peach = 6, Jink = 5.2, Slash = 5.4 }
-- sgs.{{general}}_suit_value = { heart = 6.7, spade = 5 }
-- sgs.{{skillname}}_keep_value = { Slash = 5.4 }
