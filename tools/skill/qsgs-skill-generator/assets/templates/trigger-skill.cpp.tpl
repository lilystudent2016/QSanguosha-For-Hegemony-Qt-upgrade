// 触发型技能骨架（TriggerSkill）
// 落点：src/package/<pkg>.cpp（无需 Q_OBJECT 直接写 .cpp；跨 package 复用时才提到 .h）
// 占位符：{{SkillName}} 类名（大驼峰）、{{skillname}} objectName（小写拼音）、{{#skillname-inner}} 内部技名

class {{SkillName}} : public TriggerSkill
{
public:
    {{SkillName}}() : TriggerSkill("{{skillname}}")
    {
        // 按 references/cn-to-cpp.md 的"触发时机关键词表"选事件，可挂多个
        events << /* EVENT_1 */ << /* EVENT_2 */;
        frequency = Skill::NotFrequent;   // 可选技保持 NotFrequent；锁定技改 Compulsory
    }

    // 可选：只做记录、不做结算时用 record（例如回合切换时清空私有标记）
    virtual void record(TriggerEvent triggerEvent, Room *room, ServerPlayer *player, QVariant &) const
    {
        if (triggerEvent == EventPhaseStart && player->getPhase() == Player::NotActive) {
            QList<ServerPlayer *> allplayers = room->getAlivePlayers();
            foreach (ServerPlayer *p, allplayers) {
                room->setPlayerMark(p, "##{{skillname}}", 0);
            }
        }
    }

    virtual QStringList triggerable(TriggerEvent triggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer * &ask_who) const
    {
        if (triggerEvent == /* EVENT_1 */) {
            if (TriggerSkill::triggerable(player) /* && 其它合法性条件 */)
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

    virtual bool effect(TriggerEvent, Room *room, ServerPlayer *player, QVariant &data, ServerPlayer *) const
    {
        // 结算写在这里
        return false;   // 返回 true 会中断后续结算链
    }
};

// —— 注册（写进所属的 addXxxGenerals() 或 Package 构造函数）——
// general->addSkill(new {{SkillName}});
