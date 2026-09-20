// ============================================================
// 巡猎（xunlie）技能卡声明
// 落点：src/package/<pkg>.h
// 硬性要求：SkillCard 必须声明在 .h，且带 Q_OBJECT + Q_INVOKABLE
//           否则 moc 不生成元对象，运行期 @XunlieCard 解析不到（静默失效）
//           并在包构造函数里 addMetaObject<XunlieCard>();
// ============================================================

class XunlieCard : public SkillCard
{
    Q_OBJECT

public:
    Q_INVOKABLE XunlieCard();

    virtual bool targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const;
    // TODO: 若描述里还有"额外消耗"（弃牌 / 失去体力），加 extraCost：
    // virtual void extraCost(Room *room, const CardUseStruct &card_use) const;
    virtual void onEffect(const CardEffectStruct &effect) const;
};
