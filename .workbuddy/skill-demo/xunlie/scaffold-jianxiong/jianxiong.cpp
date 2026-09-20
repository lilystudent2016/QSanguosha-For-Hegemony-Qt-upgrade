// ============================================================
// 生成物 Jianxiong —— 由 scaffold_skill.py 自动生成
// objectName: jianxiong   中文名: 奸雄
// 形态: 触发技    建议基类: MasochismSkill
// 落点: src/package/<pkg>.cpp
// ============================================================

// 受虐技骨架（MasochismSkill）
// 注意：Damaged 事件由基类自动挂载，构造函数里不要写 events <<
class Jianxiong : public MasochismSkill
{
public:
    Jianxiong() : MasochismSkill("jianxiong")
    {
        frequency = Skill::NotFrequent;
    }

    virtual QStringList triggerable(TriggerEvent, Room *room, ServerPlayer *player,
                                    QVariant &data, ServerPlayer * &) const
    {
        if (MasochismSkill::triggerable(player)) {
            DamageStruct damage = data.value<DamageStruct>();
            // TODO: 补发动条件，例如 damage.card != NULL / damage.from != NULL
            return QStringList(objectName());
        }
        return QStringList();
    }

    virtual bool cost(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer *) const
    {
        if (player->askForSkillInvoke(this, data)) {
            room->broadcastSkillInvoke(objectName(), player);
            return true;
        }
        return false;
    }

    // 结算写在 onDamaged，不写 effect
    virtual void onDamaged(ServerPlayer *player, const DamageStruct &damage) const
    {
        // TODO: 补结算内容
    }
};


// ============================================================
// 注册（两处都要）
// ============================================================
// 1) 包构造函数中登记技能卡元对象（仅当有技能卡时）：
//        addMetaObject<JianxiongCard>();
// 2) 武将注册函数 / 包构造函数中挂技能：
//        general->addSkill(new Jianxiong);
//    standard 包的注册函数在 standard-wei-generals.cpp 的 StandardPackage::addWeiGenerals() 等；
//    其它包直接在 XxxPackage::XxxPackage() 里建 General 并 addSkill。
// 3) 新增了 .cpp/.h 时，同步加进 QSanguosha.pro 的 SOURCES / HEADERS。
