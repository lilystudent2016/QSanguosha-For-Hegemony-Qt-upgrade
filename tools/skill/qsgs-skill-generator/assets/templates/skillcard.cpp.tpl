// 技能卡实现骨架
// 落点：src/package/<pkg>.cpp
// 配套：在 .h 中已声明类；在包构造函数里 addMetaObject<{{SkillName}}Card>();

{{SkillName}}Card::{{SkillName}}Card()
{
    // mute = true;   // 不需要播放卡牌语音时打开
}

bool {{SkillName}}Card::targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const
{
    // 常见写法：只允许选一个目标，并附加合法性条件
    return targets.isEmpty() /* && 其它条件，例如 to_select->getHp() > Self->getHp() */;
}

void {{SkillName}}Card::onEffect(const CardEffectStruct &effect) const
{
    Room *room = effect.to->getRoom();

    // 1) 需要玩家选择时，reason 用技能的 objectName()，AI 侧配 sgs.ai_skill_playerchosen.<技能名>
    // ServerPlayer *target = room->askForPlayerChosen(effect.from, candidates, "{{skillname}}", "@{{skillname}}-damage");

    // 2) 产生效果
    // room->damage(DamageStruct("{{skillname}}", effect.from, effect.to));
    // effect.to->drawCards(1);
    // room->loseHp(effect.to);
}

// —— 承载它的技能（出牌阶段限一次、不需弃牌的形态）——
// class {{SkillName}} : public ZeroCardViewAsSkill
// {
// public:
//     {{SkillName}}() : ZeroCardViewAsSkill("{{skillname}}")
//     {
//     }
//
//     virtual bool isEnabledAtPlay(const Player *player) const
//     {
//         return !player->hasUsed("{{SkillName}}Card");
//     }
//
//     virtual const Card *viewAs() const
//     {
//         {{SkillName}}Card *card = new {{SkillName}}Card;
//         card->setShowSkill(objectName());
//         return card;
//     }
// };
