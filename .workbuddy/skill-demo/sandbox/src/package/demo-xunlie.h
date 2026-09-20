// ============================================================
// 生成物 ②-a：技能卡声明
// 落点：src/package/<pkg>.h
// 硬性要求：技能卡必须声明在 .h，且带 Q_OBJECT + Q_INVOKABLE，
//           否则 moc 不生成元对象，运行期 @XunlieCard 解析不到（静默失效）
// ============================================================

class XunlieCard : public SkillCard
{
    Q_OBJECT

public:
    Q_INVOKABLE XunlieCard();

    // 目标合法性：只选一名其他角色
    virtual bool targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const;

    // "你可弃置一张牌" —— 消耗在 extraCost 里完成
    virtual void extraCost(Room *room, const CardUseStruct &card_use) const;

    // "令一名其他角色选择一项……" —— 分叉结算
    virtual void onEffect(const CardEffectStruct &effect) const;
};
