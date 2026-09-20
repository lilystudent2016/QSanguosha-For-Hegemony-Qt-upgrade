// ============================================================
// 生成物 ②-b：技能卡实现 + 承载它的视为技 + 注册
// 落点：src/package/<pkg>.cpp
// 形态对照物：Qiangxi（强袭，出牌阶段限一次 + 一张牌作消耗 + SkillCard）
// ============================================================

XunlieCard::XunlieCard()
{
}

bool XunlieCard::targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const
{
    return targets.isEmpty() && to_select != Self;
}

void XunlieCard::extraCost(Room *room, const CardUseStruct &card_use) const
{
    // "你可弃置一张牌"：消耗的牌已作为 subcard 挂在技能卡上，
    // 交给基类移入弃牌堆即可（SkillCard::extraCost 内部走 willThrow + moveCardTo）
    SkillCard::extraCost(room, card_use);
}

void XunlieCard::onEffect(const CardEffectStruct &effect) const
{
    Room *room = effect.from->getRoom();

    // 询问方是【目标】而非技能拥有者：描述为"令一名其他角色选择一项"
    // 第 3 个参数是 choice 串，AI 侧对应 sgs.ai_skill_choice.xunlie
    // 第 4 个参数把伤害来源带给 AI，便于其判断该不该吃伤害
    QString choice = room->askForChoice(effect.to, "xunlie", "discard+damage",
                                        QVariant::fromValue(effect.from),
                                        "@xunlie-choose::" + effect.from->objectName());

    if (choice == "damage")
        room->damage(DamageStruct("xunlie", effect.from, effect.to));
    else
        // reason 用技能 objectName，AI 侧对应 sgs.ai_skill_discard.xunlie
        room->askForDiscard(effect.to, "xunlie", 1, 1, false, true);
}

// —— 承载技能卡的视为技 ——
// 用 ViewAsSkill 而不是 ZeroCardViewAsSkill：本技能需要玩家自选一张牌作消耗
class Xunlie : public ViewAsSkill
{
public:
    Xunlie() : ViewAsSkill("xunlie")
    {
    }

    // "出牌阶段限一次"：限制粒度是技能卡
    virtual bool isEnabledAtPlay(const Player *player) const
    {
        return !player->hasUsed("XunlieCard");
    }

    virtual bool viewFilter(const QList<const Card *> &selected, const Card *to_select) const
    {
        return selected.isEmpty() && !Self->isJilei(to_select);
    }

    virtual const Card *viewAs(const QList<const Card *> &cards) const
    {
        if (cards.length() != 1)
            return NULL;

        XunlieCard *card = new XunlieCard;
        card->addSubcards(cards);
        card->setShowSkill(objectName());   // 少了这句则发动时不显示技能名、AI 也认不出
        return card;
    }
};

// ============================================================
// 注册（两处都要）
// ============================================================
// 1) 包构造函数中登记技能卡元对象：
//        addMetaObject<XunlieCard>();
//    没有这一步，运行期 @XunlieCard 无法解析，技能卡永远构造不出来。
//
// 2) 武将注册函数中挂技能：
//        general->addSkill(new Xunlie);
//
// 真实项目里这两行分别写进 XxxPackage::XxxPackage() 与 addXxxGenerals()。
// 下面是沙箱占位函数，两行都是**真实调用**（不是注释），以便自检脚本能识别；
// 若把它们写成注释，自检会正确地报告"未注册"。
void DemoRegister(General *general, Package *package)
{
    package->addMetaObject<XunlieCard>();
    general->addSkill(new Xunlie);
}
