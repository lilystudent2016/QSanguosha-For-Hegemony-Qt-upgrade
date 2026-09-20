// 受虐技骨架（MasochismSkill）—— 专用于"当你受到伤害后……"
// 注意：Damaged 事件由基类自动挂载，构造函数里不要写 events <<
// 落点：src/package/<pkg>.cpp

class {{SkillName}} : public MasochismSkill
{
public:
    {{SkillName}}() : MasochismSkill("{{skillname}}")
    {
        frequency = Skill::NotFrequent;   // 默认 NotFrequent（可选）；Frequent 表示可反复发动
    }

    virtual QStringList triggerable(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer * &) const
    {
        if (MasochismSkill::triggerable(player)) {
            DamageStruct damage = data.value<DamageStruct>();
            // 检查发动条件，例如 damage.card != NULL / damage.from != NULL
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
        // 例：player->obtainCard(damage.card);
    }
};

// —— 注册 ——
// general->addSkill(new {{SkillName}});

// —— 需要被多个 package 复用时的写法 ——
// .h 中：
//   class {{SkillName}} : public MasochismSkill
//   {
//   public:
//       explicit {{SkillName}}(const QString &owner = QString());   // 复用必须给默认值
//       virtual QStringList triggerable(TriggerEvent, Room *, ServerPlayer *, QVariant &, ServerPlayer * &) const;
//       virtual bool cost(TriggerEvent, Room *, ServerPlayer *, QVariant &, ServerPlayer * = NULL) const;
//       virtual void onDamaged(ServerPlayer *, const DamageStruct &) const;
//   };
// .cpp 中：
//   {{SkillName}}::{{SkillName}}(const QString &owner) : MasochismSkill("{{skillname}}" + owner) {}
// 注册：
//   a->addSkill(new {{SkillName}});            // 唯一使用
//   b->addSkill(new {{SkillName}}("b"));        // 共享时按 owner 后缀命名，例如 "mashu_machao"
