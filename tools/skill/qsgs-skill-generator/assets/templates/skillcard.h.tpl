// 技能卡骨架 —— 必须先声明在 .h 里
// 落点：src/package/<pkg>.h
// 硬性要求：Q_OBJECT + Q_INVOKABLE 构造函数，否则 moc 不生成元对象，运行期解析不到该技能卡
// 同时在包的构造函数里登记：addMetaObject<{{SkillName}}Card>();

class {{SkillName}}Card : public SkillCard
{
    Q_OBJECT

public:
    Q_INVOKABLE {{SkillName}}Card();

    // 目标合法性：return true 表示可把 to_select 选为目标
    virtual bool targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const;

    // 结算
    virtual void onEffect(const CardEffectStruct &effect) const;

    // 按需：额外消耗（例如弃牌、失去体力）
    // virtual void extraCost(Room *room, const CardUseStruct &card_use) const;

    // 按需：实际使用时的一次性结算（区别：use 在选完目标后、onEffect 在每个目标上各来一次）
    // virtual void use(Room *room, ServerPlayer *source, QList<ServerPlayer *> &targets) const;
};
