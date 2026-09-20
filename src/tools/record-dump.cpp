// record-dump.cpp —— 把 .qsgs 录像重放成「决策点 + 当时局面」的 JSON Lines
//
// 设计要点（与 Python 侧状态机互补）：
//   1. **复用真实客户端逻辑**：把录像里的广播报文逐条投给 Client::processServerPacket，
//      状态由 ClientPlayer/Player 自己累积 —— 不重新实现一遍状态语义。
//   2. **可见性天然正确**：录像本身就是"按录制者视野过滤后的报文流"，
//      所以重放出来的局面就是录制者当时真实看到的（他人暗手牌只有数量）。
//   3. **瞬时、无等待**：**不调用 Client 的启动函数**（那会 start() Replayer 线程按时间播放），
//      而是自己按行同步投喂 —— 一局几百毫秒跑完。
//   4. marks 是 Player 的 protected 成员，外部取不到整表；
//      标记由 Python 侧状态机直接读 SET_MARK/SET_INT_MARK/SET_STRING_MARK 报文获得，
//      本工具只导出公开可读字段（血量/手牌/装备/判定区/武将/明置/势力/阶段…）。

#include "record-dump.h"

#include <QByteArray>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMetaObject>
#include <QVariant>
#include <cstdio>
#include <cstdlib>

#include "card.h"
#include "client.h"
#include "clientplayer.h"
#include "engine.h"
#include "player.h"
#include "protocol.h"
#include "settings.h"

// ── 把 QVariant（报文 body）递归转成一行可读文本，避免依赖未知的 JSON 工具函数 ──
static QString bodyToString(const QVariant &v, int depth = 0)
{
    if (depth > 8) return QString("...");
    if (v.userType() == QMetaType::QString) return QString("\"%1\"").arg(v.toString());
    if (v.userType() == QMetaType::Bool) return v.toBool() ? "true" : "false";
    if (v.userType() == QMetaType::Int || v.userType() == QMetaType::LongLong
        || v.userType() == QMetaType::UInt)
        return QString::number(v.toLongLong());
    if (v.userType() == QMetaType::Double) return QString::number(v.toDouble());
    if (v.canConvert<QVariantList>()) {
        const QVariantList list = v.toList();
        QStringList parts;
        foreach (const QVariant &item, list) parts << bodyToString(item, depth + 1);
        return "[" + parts.join(",") + "]";
    }
    if (v.canConvert<QVariantMap>()) {
        const QVariantMap map = v.toMap();
        QStringList parts;
        for (QVariantMap::const_iterator it = map.constBegin(); it != map.constEnd(); ++it)
            parts << QString("\"%1\":%2").arg(it.key()).arg(bodyToString(it.value(), depth + 1));
        return "{" + parts.join(",") + "}";
    }
    return QString("\"%1\"").arg(v.toString());
}

static QJsonObject cardJson(const Card *card)
{
    QJsonObject o;
    if (card == NULL) return o;
    o["id"] = card->getId();
    o["name"] = card->getName();
    o["suit"] = card->getSuitString();
    o["num"] = card->getNumberString();
    o["type"] = card->getType();
    if (card->isVirtualCard()) {
        const QString skill = card->getSkillName();
        if (!skill.isEmpty()) o["skill"] = skill;   // 技能转化出的虚拟牌（@技能名）
        o["virtual"] = true;
    }
    return o;
}

static QJsonArray cardsJson(const QList<const Card *> &cards)
{
    QJsonArray arr;
    foreach (const Card *c, cards) arr.append(cardJson(c));
    return arr;
}

// selfId: 录制者本人 id —— 用于**可见性掩码**（见下）
static QJsonObject playerJson(const ClientPlayer *p, const QString &selfId)
{
    QJsonObject o;
    if (p == NULL) return o;
    o["id"] = p->objectName();
    o["seat"] = p->getSeat();
    o["alive"] = p->isAlive();
    QJsonArray hp; hp.append(p->getHp()); hp.append(p->getMaxHp());
    o["hp"] = hp;
    o["hand_n"] = p->getHandcardNum();
    QJsonArray shown; shown.append(p->hasShownGeneral1()); shown.append(p->hasShownGeneral2());
    o["shown"] = shown;                    // 明置标记（国战核心）
    o["general"] = p->getGeneralName();    // 显示名：未明置时为 anjiang/空（已正确实现可见性）
    o["general2"] = p->getGeneral2Name();
    // ── ★ 可见性掩码（2026-09-18 实测后加）────────────────────────────────
    // 背景：`ServerPlayer::setActualGeneral1Name/2Name` 用的是 **doBroadcastNotify**（广播给所有人），
    //       且服务端会 broadcastProperty 广播真实 kingdom ⇒ **客户端其实知道所有人的真武将与真势力**。
    //       实测：全暗置对手的快照里 95% 的 actual*、96% 的 kingdom 有值 —— 这正是老项目
    //       bot "偷看势力"缺陷的数据根源（不是算出来的，是数据里就给了）。
    // 规则：非本人一律不给 actual*；非本人且**未明置**则不给 kingdom（暗将无势力，规则如此）。
    //       `general`/`general2` 的显示名已天然正确（暗置时为 anjiang），信息不丢。
    //       另外**不导出 `role`**：那是老项目把势力映射成身份字符串的内部编码（GetMappedRole），
    //       既非框架中立、又正是"偷看"的直接机制。
    const bool isSelf = (!selfId.isEmpty() && p->objectName() == selfId);
    if (isSelf) {
        o["kingdom"] = p->getKingdom();
        o["actual1"] = p->getActualGeneral1Name();
        o["actual2"] = p->getActualGeneral2Name();
    } else {
        const bool anyShown = p->hasShownGeneral1() || p->hasShownGeneral2();
        o["kingdom"] = anyShown ? p->getKingdom() : QString();
        o["actual1"] = QString();
        o["actual2"] = QString();
    }
    o["phase"] = p->getPhaseString();
    o["chained"] = p->isChained();
    o["faceup"] = p->faceUp();
    o["turn"] = p->getMark("Global_TurnCount");
    o["equips"] = cardsJson(p->getEquips());
    o["judging"] = cardsJson(p->getJudgingArea());
    // 手牌明细：只有"自己 + 已公开"的牌才在 known_cards 里 —— 可见性天然正确
    o["hand"] = cardsJson(p->getHandcards());
    return o;
}

// ── 读 .qsgs：'\0' + uint32BE(解压后长度) + zlib + UTF-8 文本 ──
static QByteArray readQsgs(const QString &path, bool *ok)
{
    *ok = false;
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) return QByteArray();
    const QByteArray raw = f.readAll();
    f.close();
    if (raw.isEmpty() || raw.at(0) != '\0') return QByteArray();
    // qUncompress 期望「4 字节大端长度 + zlib 流」，正好等于本格式去掉首字节后的部分
    const QByteArray text = qUncompress(raw.mid(1));
    if (text.isEmpty()) return QByteArray();
    *ok = true;
    return text;
}


// ── 已知的「客户端防御缺口」过滤器 ──────────────────────────────────────────
// 旧项目客户端里有若干 handler 只做了不充分的长度校验，越界访问 QList::at：
//     Client::mirrorGuanxingStep()  →  if (arg.size() >= 3) { ... arg.at(8) }
// Release 版（QList::at 无断言）= 静默越界读、能跑；Debug 版 = ASSERT → fail-fast。
// ⚠️ 这是**游戏项目自身的潜伏 bug**，按约定不由我改；这里只在工具侧跳过并计数，
//    跳过不丢信息：观星的真实结果由随后的 LOSE_CARD/GET_CARD 广播表达。
static bool bodyTooShort(const QSanProtocol::Packet &packet, const char **why)
{
    const QVariantList body = packet.getMessageBody().toList();
    const int size = body.size();
    const int cmd = (int)packet.getCommandType();

    // ── 镜像步骤报文（观星 / 移牌）：长度要求**按步序**而定，不能按整条命令一刀切 ──
    //   GuanxingStep: S_GUANXING_START=0 / S_GUANXING_MOVE=1 / S_GUANXING_FINISH=2
    //     mirrorGuanxingStep : START 读 at(0..3) → 需 >=4；MOVE 读 at(0..2) → >=3；FINISH → >=1
    //     mirrorMoveCardsStep: START 读 at(0..8) → 需 >=9；MOVE → >=3；FINISH → >=1
    //   ⚠️ 历史教训：早先按整条命令要求 >=9，结果**误杀了大量本来就安全的 MOVE/FINISH 步**
    //   （实测抽样 300 局误杀 2,020 条 ≈ 6.7 条/局）。那些报文只 emit UI 信号、不改任何状态，
    //   但会让 oracle 的重放保真度下降、并让 `skipped` 统计失去意义。
    //   游戏侧已修（START 处改为 >=4 / >=9），这里仍按步序精确校验作第二道防线。
    if (cmd == (int)QSanProtocol::S_COMMAND_MIRROR_GUANXING_STEP ||
        cmd == (int)QSanProtocol::S_COMMAND_MIRROR_MOVECARDS_STEP) {
        if (size < 1) {
            *why = "镜像步骤报文无 body";
            return true;
        }
        const int step = body.at(0).toInt();
        int need = 1;                                   // S_GUANXING_FINISH
        if (step == (int)QSanProtocol::S_GUANXING_START)
            need = (cmd == (int)QSanProtocol::S_COMMAND_MIRROR_GUANXING_STEP) ? 4 : 9;
        else if (step == (int)QSanProtocol::S_GUANXING_MOVE)
            need = 3;
        if (size < need) {
            *why = "镜像步骤报文按步序长度不足";
            return true;
        }
    }

    // ── 引擎不认识的武将 ────────────────────────────────────────────────
    // 录像来自"启用了额外扩展包的房间"（如 asus 服务器的 jiange-defense / test /
    // zzhead / lord_ex_card），本地引擎没有那些武将 ⇒ Sanguosha->getGeneral() 返回 NULL。
    // 而 Player::setActualGeneral1Name / setGeneralName 里有 Q_ASSERT(... != NULL)
    // ⇒ Debug 版断言 fail-fast（Release 版静默）。跳过并计数（无法设置即无信息可设）。
    if (cmd == (int)QSanProtocol::S_COMMAND_SET_ACTULGENERAL && size >= 2) {
        const QString g = body.at(1).toString();
        if (!g.isEmpty() && Sanguosha->getGeneral(g) == NULL) {
            *why = "引擎不认识该武将（录像房间启用了额外扩展包）";
            return true;
        }
    }
    if (cmd == (int)QSanProtocol::S_COMMAND_SET_PROPERTY && size >= 3) {
        const QString prop = body.at(1).toString();
        if (prop == "general" || prop == "general2" || prop == "deputy_general") {
            const QString g = body.at(2).toString();
            if (!g.isEmpty() && g != "anjiang" && Sanguosha->getGeneral(g) == NULL) {
                *why = "引擎不认识该武将（SET_PROPERTY）";
                return true;
            }
        }
    }
    return false;
}

int runRecordDump(const QString &path, const QString &outPath, int limit)
{
    if (path.isEmpty()) {
        fprintf(stderr, "用法: QSanguosha.exe -dump <录像.qsgs> [-o out.jsonl] [-n N]\n");
        return 2;
    }

    bool ok = false;
    const QByteArray text = readQsgs(path, &ok);
    if (!ok) {
        fprintf(stderr, "[dump] 解压失败（不是 .qsgs 或文件损坏）: %s\n", qPrintable(path));
        return 3;
    }

    // 构造 Client 但不启动：filename 非空 ⇒ replayer 非空 ⇒
    //   processServerPacket 走"回放语义"（忽略请求，只更新状态），且不会尝试连接服务器。
    setvbuf(stderr, NULL, _IONBF, 0);   // 无缓冲：崩溃时也能看到最后一条进度
    Client *client = new Client(NULL, path);
    if (client == NULL) return 4;
    fprintf(stderr, "[dump] 开始重放: %s\n", qPrintable(path));

    // 输出：文件或标准输出
    FILE *out = stdout;
    if (!outPath.isEmpty()) {
        out = fopen(qPrintable(outPath), "wb");
        if (out == NULL) {
            fprintf(stderr, "[dump] 无法写入: %s\n", qPrintable(outPath));
            return 2;
        }
    }

    const QList<QByteArray> lines = text.split('\n');
    int n_total = 0, n_fed = 0, n_dec = 0, n_parse_fail = 0, n_skipped = 0;
    QString selfId;

    for (int i = 0; i < lines.size(); ++i) {
        const QByteArray line = lines.at(i).trimmed();
        if (line.isEmpty()) continue;
        const int sp = line.indexOf(' ');
        if (sp <= 0) continue;
        bool okMs = false;
        const qint64 ms = line.left(sp).toLongLong(&okMs);
        if (!okMs) continue;
        const QByteArray raw = line.mid(sp + 1);
        if (raw.isEmpty()) continue;
        ++n_total;

        QSanProtocol::Packet packet;
        if (!packet.parse(raw)) { ++n_parse_fail; continue; }

        // 追踪"我是谁"：服务端发给本机的 SET_PROPERTY MG_SELF objectName
        if (packet.getCommandType() == QSanProtocol::S_COMMAND_SET_PROPERTY) {
            const QVariantList body = packet.getMessageBody().toList();
            if (body.size() >= 3 && body.at(0).toString() == "MG_SELF"
                && body.at(1).toString() == "objectName")
                selfId = body.at(2).toString();
        }

        const bool isRequest =
            (packet.getPacketType() == QSanProtocol::S_TYPE_REQUEST);

        if (isRequest) {
            QJsonObject snap;
            snap["t_ms"] = ms;
            snap["cmd"] = (int)packet.getCommandType();     // 序号交给 Python 侧映射成命令名
            snap["body"] = bodyToString(packet.getMessageBody());
            snap["self"] = selfId;
            snap["line_no"] = i;
            QJsonArray players;
            foreach (const ClientPlayer *p, client->getPlayers()) players.append(playerJson(p, selfId));
            snap["players"] = players;
            const QByteArray js = QJsonDocument(snap).toJson(QJsonDocument::Compact) + "\n";
            fwrite(js.constData(), 1, js.size(), out);
            ++n_dec;
            if (limit > 0 && n_dec >= limit) break;
        }

        // 跳过会触发客户端已知防御缺口的报文（记录并计数）
        const char *why = NULL;
        // 设 QSGS_DUMP_NO_GUARD=1 可关闭守卫表（用于验证游戏侧修复是否生效）
        if (getenv("QSGS_DUMP_NO_GUARD") == NULL && bodyTooShort(packet, &why)) {
            ++n_skipped;
            if (n_skipped <= 5)
                fprintf(stderr, "[dump] 跳过过短报文 line=%d cmd=%d size=%d —— %s\n",
                        i, (int)packet.getCommandType(),
                        packet.getMessageBody().toList().size(), why);
            continue;
        }

        if (getenv("QSGS_DUMP_TRACE") != NULL)
            fprintf(stderr, "[trace] line=%d ms=%lld cmd=%d desc=%d len=%d\n",
                    i, (long long)ms, (int)packet.getCommandType(),
                    (int)packet.getPacketDescription(), raw.size());

        // 投喂给客户端累积状态（请求在回放语义下会被 ignore，与真实回放一致）
        QMetaObject::invokeMethod(client, "processServerPacket",
                                  Qt::DirectConnection, Q_ARG(QByteArray, raw));
        ++n_fed;
    }

    fprintf(stderr, "[dump] 完成：报文 %d（投喂 %d，解析失败 %d，跳过 %d），导出决策点 %d\n",
            n_total, n_fed, n_parse_fail, n_skipped, n_dec);
    // 一行摘要给机器读。★ 必须写进**与决策点相同的输出流**：
    // 原来只 printf 到 stdout，用 -o 落盘时摘要就丢了（单文件无法自校验）。
    {
        char sbuf[1024];
        const int slen = snprintf(sbuf, sizeof(sbuf),
            "{\"_summary\":{\"file\":\"%s\",\"records\":%d,\"decision_points\":%d,"
            "\"parse_fail\":%d,\"skipped\":%d}}\n",
            qPrintable(QFileInfo(path).fileName()), n_total, n_dec, n_parse_fail, n_skipped);
        if (out != NULL && out != stdout) {
            fwrite(sbuf, 1, slen, out);
            fclose(out);
        } else {
            fwrite(sbuf, 1, slen, stdout);
            fflush(stdout);
        }
    }
    return 0;
}
