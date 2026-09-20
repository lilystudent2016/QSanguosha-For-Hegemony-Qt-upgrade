// ============================================================
// 生成物 Xunlie —— 由 scaffold_skill.py 自动生成
// objectName: xunlie   中文名: 巡猎
// 形态: 主动技    建议基类: ViewAsSkill
// 落点: src/package/<pkg>.cpp（另需 .h 声明技能卡）
// ============================================================

// —— 技能卡实现 ——
XunlieCard::XunlieCard()
{
}

bool XunlieCard::targetFilter(const QList<const Player *> &targets, const Player *to_select, const Player *Self) const
{
    // TODO: 补目标合法性。只选一人时 targets.isEmpty() 必写
    return targets.isEmpty() && to_select != Self;
}

void XunlieCard::onEffect(const CardEffectStruct &effect) const
{
    Room *room = effect.from->getRoom();
    // TODO: 补结算。需要询问选项时：
    //   QString choice = room->askForChoice(effect.to, "xunlie", "选项1+选项2", QVariant(), "@xunlie-choose");
    // 需要弃牌时（reason 用 objectName，AI 侧对应 sgs.ai_skill_discard.xunlie）：
    //   room->askForDiscard(effect.to, "xunlie", 1, 1, false, true);
}


// ============================================================
// 注册（两处都要）
// ============================================================
// 1) 包构造函数中登记技能卡元对象（仅当有技能卡时）：
//        addMetaObject<XunlieCard>();
// 2) 武将注册函数 / 包构造函数中挂技能：
//        general->addSkill(new Xunlie);
//    standard 包的注册函数在 standard-wei-generals.cpp 的 StandardPackage::addWeiGenerals() 等；
//    其它包直接在 XxxPackage::XxxPackage() 里建 General 并 addSkill。
// 3) 新增了 .cpp/.h 时，同步加进 QSanguosha.pro 的 SOURCES / HEADERS。

// 频率实现提示：出牌阶段限一次 → 技能卡形态用 !player->hasUsed("XxxCard")；非技能卡用 Skill::Limited
