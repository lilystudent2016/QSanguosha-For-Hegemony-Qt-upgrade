/********************************************************************
    Copyright (c) 2013-2015 - Mogara

    This file is part of QSanguosha-Hegemony.

    This game is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License as
    published by the Free Software Foundation; either version 3.0
    of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    General Public License for more details.

    See the LICENSE file for more details.

    Mogara
    *********************************************************************/

#include "server.h"
#include "nativesocket.h"
#include "clientstruct.h"
#include "json.h"
#include "room.h"
#include "roomthread.h"
#include "serverplayer.h"
#include "settings.h"
#include "engine.h"
#include "scenario.h"
#include "socket.h"

#include <QApplication>
#include <QDir>
#include <QFile>
#include <QDateTime>
#include <QTimer>
// ── [A1 补丁 2026-09-19] meta.json 结构化元数据 ──────────────────────────
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

using namespace QSanProtocol;

Server::Server(QObject *parent)
    : QObject(parent)
{
    server = new NativeServerSocket;
    server->setParent(this);

    //synchronize ServerInfo on the server side to avoid ambiguous usage of Config and ServerInfo
    ServerInfo.parse(Sanguosha->getSetupString());

    current = NULL;

    connect(server, &NativeServerSocket::new_connection, this, &Server::processNewConnection);
    connect(qApp, &QApplication::aboutToQuit, this, &Server::deleteLater);
}

void Server::broadcastSystemMessage(const QString &msg)
{
    JsonArray arg;
    arg << ".";
    arg << msg;

    Packet packet(S_SRC_ROOM | S_TYPE_NOTIFICATION | S_DEST_CLIENT, S_COMMAND_SPEAK);
    packet.setMessageBody(arg);

    foreach(Room *room, rooms)
        room->broadcast(&packet);
}

bool Server::listen()
{
    return server->listen();
}

void Server::daemonize()
{
    server->daemonize();
}

Room *Server::createNewRoom()
{
    Room *new_room = new Room(this, Config.GameMode);
    current = new_room;
    rooms.insert(current);

    connect(current, &Room::room_message, this, &Server::server_message);
    connect(current, &Room::game_over, this, &Server::gameOver);

    return current;
}

void Server::processNewConnection(ClientSocket *socket)
{
    QString address = socket->peerAddress();
    if (Config.ForbidSIMC) {
        if (addresses.contains(address)) {
            socket->disconnectFromHost();
            emit server_message(tr("Forbid the connection of address %1").arg(address));
            return;
        } else {
            addresses.append(address);
        }
    }

    if (Config.value("BannedIP").toStringList().contains(address)) {
        socket->disconnectFromHost();
        emit server_message(tr("Forbid the connection of address %1").arg(address));
        return;
    }

    connect(socket, &ClientSocket::disconnected, this, &Server::cleanup);

    notifyClient(socket, S_COMMAND_CHECK_VERSION, Sanguosha->getVersion());
    notifyClient(socket, S_COMMAND_SETUP, Sanguosha->getSetupString());

    emit server_message(tr("%1 connected").arg(socket->peerName()));

    connect(socket, &ClientSocket::message_got, this, &Server::processRequest);
}

void Server::processRequest(const QByteArray &request)
{
    ClientSocket *socket = qobject_cast<ClientSocket *>(sender());

    Packet packet;
    if (!packet.parse(request)) {
        emit server_message(tr("Invalid message %1 from %2").arg(QString::fromUtf8(request)).arg(socket->peerAddress()));
        return;
    }

    switch (packet.getPacketSource()) {
    case S_SRC_CLIENT:
        processClientRequest(socket, packet);
        break;
    default:
        emit server_message(tr("Packet %1 from an unknown source %2").arg(QString::fromUtf8(request)).arg(socket->peerAddress()));
    }
}

void Server::notifyClient(ClientSocket *socket, CommandType command, const QVariant &arg)
{
    Packet packet(S_SRC_ROOM | S_TYPE_NOTIFICATION | S_DEST_CLIENT, command);
    packet.setMessageBody(arg);
    socket->send(packet.toJson());
}

void Server::processClientRequest(ClientSocket *socket, const Packet &signup)
{
    disconnect(socket, &ClientSocket::message_got, this, &Server::processRequest);

    if (signup.getCommandType() != S_COMMAND_SIGNUP) {
        emit server_message(tr("Invalid signup string: %1").arg(signup.toString()));
        notifyClient(socket, S_COMMAND_WARN, "INVALID_FORMAT");
        socket->disconnectFromHost();
        return;
    }

    JsonArray body = signup.getMessageBody().value<JsonArray>();
    bool is_reconnection = body[0].toBool();
    QString screen_name = body[1].toString();
    QString avatar = body[2].toString();

    if (is_reconnection) {
        foreach (const QString &objname, name2objname.values(screen_name)) {
            ServerPlayer *player = players.value(objname);
            if (player && player->getState() == "offline" && !player->getRoom()->isFinished()) {
                player->getRoom()->reconnect(player, socket);
                return;
            }
        }
    }

    if (current == NULL || current->isFull() || current->isFinished())
        createNewRoom();

    ServerPlayer *player = current->addSocket(socket);
    current->signup(player, screen_name, avatar, false);
    emit newPlayer(player);

    if (current->getPlayers().length() == 1 && current->getScenario() && current->getScenario()->objectName() == "jiange_defense") {
        for (int i = 0; i < 4; ++i)
            current->addRobotCommand(player, QVariant());
    }
}

void Server::cleanup()
{
    ClientSocket *socket = qobject_cast<ClientSocket *>(sender());
    if (Config.ForbidSIMC)
        addresses.removeOne(socket->peerAddress());
    socket->deleteLater();
}

void Server::signupPlayer(ServerPlayer *player)
{
    name2objname.insert(player->screenName(), player->objectName());
    players.insert(player->objectName(), player);
}

// ══════════════ [A1 补丁 2026-09-19] 无头自对弈（命令行 -autoplay [N]）══════════════
// 目的：在**一个进程内**连跑 N 局「全 10 席都是 bot」的国战对局；每局把 10 个座位
//       各自可见的全过程录成 .qsgs（a1_out/gNNN/<座位名>.qsgs），供 A1/A3 数据管线用。
// 为什么必须走 C++ 而不是外部 socket 脚本：ServerPlayer::getAI() 对 state=="online"
//       一律返回 NULL（serverplayer.cpp:1294）⇒ 任何 SIGNUP 进来的连接都会让服务端
//       反过来 doRequest 等它回话（Config.OperationNoLimit=true 时是无限等待），
//       于是「至少有一个座位是人」⇒ 拿不到全 bot 对局。
//       （外部驱动的实测与踩坑见 qsgs_record_tools/A1-headless自对弈方案.md §6）
// 注意：Debug 版是 GUI 子系统程序、无控制台 ⇒ printf 无输出，所有进度只能写文件。
static QFile *s_a1Log = NULL;
static QFile *s_a1QtLog = NULL;

// ── [A1 补丁 2026-09-19] 输出目录可配（多实例并行的前提）──────────────
// 默认 a1_out/；环境变量 A1_OUT 可覆盖。★ 并行跑时必须各自指定：局号从 1 重数，
// 同目录下两个进程都写 a1_out/g001/<座位>.qsgs ⇒ 直接互相覆盖、静默丢样本。
static QString a1OutDir()
{
    const QByteArray env = qgetenv("A1_OUT");
    return env.isEmpty() ? QString("a1_out") : QString::fromLocal8Bit(env);
}

static void a1Log(const QString &line)
{
    if (s_a1Log == NULL) return;
    s_a1Log->write((QDateTime::currentDateTime().toString("HH:mm:ss.zzz ") + line + "\n").toUtf8());
    s_a1Log->flush();
}

// ── [A1 补丁 2026-09-19] Qt 日志落盘：Debug 版崩溃可见性 ──────────────────
// 为什么必需：Debug 版是 GUI 子系统程序、无控制台，Q_ASSERT/qFatal/qWarning 的
//   默认输出全进 stderr 而**无处可看**（此前三个断言崩溃只能靠 gdb 现场抓）。
//   装本处理器后，Qt 的全部消息（含 `ASSERT: ... in file room.cpp, line NNNN`
//   这一行就是崩溃定因）写进 <A1_OUT>/qt.log ⇒ 崩溃可离线复盘。
// 附带收益：qWarning 里本就夹着 bot 的内部推理（势力评估 / gP: / 明置目标），
//   落盘后 A3 插桩几乎免改 C++。
static void a1MessageHandler(QtMsgType type, const QMessageLogContext &, const QString &msg)
{
    if (s_a1QtLog == NULL) return;
    const char *lv = "INFO";
    switch (type) {
    case QtDebugMsg:    lv = "DBG "; break;
    case QtInfoMsg:     lv = "INFO"; break;
    case QtWarningMsg:  lv = "WARN"; break;
    case QtCriticalMsg: lv = "CRIT"; break;
    case QtFatalMsg:    lv = "FATL"; break;
    }
    s_a1QtLog->write((QDateTime::currentDateTime().toString("HH:mm:ss.zzz ") + lv + " " + msg + "\n").toUtf8());
    s_a1QtLog->flush();
}

void Server::autoplay(int games)
{
    const QString outDir = a1OutDir();
    QDir().mkpath(outDir);

    // 先把 Qt 消息处理器挂上：从这一刻起的日志（含断言失败现场）全部落盘
    s_a1QtLog = new QFile(outDir + "/qt.log");
    if (s_a1QtLog->open(QIODevice::WriteOnly | QIODevice::Append))
        qInstallMessageHandler(a1MessageHandler);
    else {
        delete s_a1QtLog;
        s_a1QtLog = NULL;
    }

    s_a1Log = new QFile(outDir + "/autoplay.log");
    if (!s_a1Log->open(QIODevice::WriteOnly | QIODevice::Append)) {
        delete s_a1Log;
        s_a1Log = NULL;
    }

    m_autoplayOut = outDir;
    m_autoplayLeft = games;
    m_autoplaySeq = 0;
    m_autoplayAllT0.start();
    a1Log(QString("=== A1 无头自对弈开始：计划 %1 局；GameMode=%2；PlayerCount=%3；AIDelay(Origin)=%4；out=%5 ===")
          .arg(games).arg(Config.GameMode)
          .arg(Sanguosha->getPlayerCount(Config.GameMode))
          .arg(Config.OriginAIDelay).arg(outDir));
    autoplayNextRoom();
}

void Server::autoplayNextRoom()
{
    Room *room = createNewRoom();
    connect(room, &Room::game_over, this, &Server::autoplayGameOver);

    ++m_autoplaySeq;
    m_autoplayRoomT0.start();
    room->autoplayFillRobots();
    a1Log(QString("[局 %1] 满员 %2 席（全 bot），对局已启动")
          .arg(m_autoplaySeq).arg(room->getPlayers().length()));
}

void Server::autoplayGameOver(const QString &winner)
{
    Room *room = qobject_cast<Room *>(sender());
    const double secs = m_autoplayRoomT0.elapsed() / 1000.0;

    if (room != NULL) {
        // game_over 是在 RoomThread 里 emit 的，此刻线程仍在收尾
        // （后面还要 doBroadcastNotify(S_COMMAND_GAME_OVER) 再 throw GameFinished）
        // ⇒ 先等线程真正退出：录像才完整，读房间状态也才线程安全。
        RoomThread *rt = room->getThread();
        if (rt != NULL && rt->isRunning())
            rt->wait(30000);

        QStringList seats;
        foreach (ServerPlayer *p, room->getPlayers()) {
            seats << QString("%1=%2/%3+%4").arg(p->objectName()).arg(p->getRole())
                     .arg(p->getActualGeneral1Name()).arg(p->getActualGeneral2Name());
        }

        const QString dir = QString("%1/g%2").arg(m_autoplayOut).arg(m_autoplaySeq, 3, 10, QChar('0'));
        QDir().mkpath(dir);
        int saved = 0;
        foreach (ServerPlayer *p, room->getPlayers()) {
            if (!p->objectName().isEmpty()) {
                p->saveRecord(dir + "/" + p->objectName() + ".qsgs");
                ++saved;
            }
        }

        // ── [A1 补丁 2026-09-19] 结构化对局元数据（meta.json）──────────────
        // 为什么需要：autoplay.log 是给人看的；打标/切分需要机读，且**必须**知道
        //   每个座位的胜负。国战胜负是「势力制」⇒ 一局里胜方视角有**多人**
        //   （其他势力全灭时该势力存活者全体获胜），实测每局胜方视角 2~4 席 /
        //   10 席，即 20%~40%。旧录像库 98.4% 是胜方视角（人只上传赢的那局），
        //   R7 的阻塞点①「无败方对照组」正好由这里的败方视角补上。
        // ⇒ 一份 meta.json = 事后按「胜方视角 / 败方视角」任意切分的唯一依据，
        //   也是 watchdog 判定「本局是否跑完」的完成标记（最后才写）。
        {
            const QStringList winners = winner.split("+", QString::SkipEmptyParts);
            QJsonObject meta;
            meta["game"] = m_autoplaySeq;
            meta["dir"] = QDir(dir).dirName();
            meta["winner"] = winner;
            meta["seconds"] = secs;
            meta["player_count"] = room->getPlayers().length();
            meta["saved_records"] = saved;
            QJsonArray seat_arr;
            foreach (ServerPlayer *p, room->getPlayers()) {
                QJsonObject s;
                s["name"] = p->objectName();          // 录像文件名 <name>.qsgs
                s["seat_role"] = p->getRole();        // 国战内部 role（势力经 GetMappedRole 映射）
                s["kingdom"] = HegemonyMode::GetMappedKingdom(p->getRole());
                s["general1"] = p->getActualGeneral1Name();
                s["general2"] = p->getActualGeneral2Name();
                s["alive"] = p->isAlive();
                s["is_winner"] = winners.contains(p->objectName());
                seat_arr.append(s);
            }
            meta["seats"] = seat_arr;

            QFile mf(dir + "/meta.json");
            if (mf.open(QIODevice::WriteOnly | QIODevice::Truncate))
                mf.write(QJsonDocument(meta).toJson(QJsonDocument::Indented));
            else
                a1Log(QString("[局 %1] ⚠ meta.json 写入失败：%2").arg(m_autoplaySeq).arg(mf.errorString()));
        }

        a1Log(QString("[局 %1] 结束 winner=%2 本局 %3s；座位 %4；录像 %5 份 → %6")
              .arg(m_autoplaySeq).arg(winner.isEmpty() ? QString("(空)") : winner)
              .arg(secs, 0, 'f', 1).arg(seats.join(" ")).arg(saved).arg(dir));

        rooms.remove(room);
        current = NULL;
        room->deleteLater();
    } else {
        a1Log(QString("[局 %1] 结束 winner=%2 本局 %3s（sender 不是 Room）")
              .arg(m_autoplaySeq).arg(winner).arg(secs, 0, 'f', 1));
    }

    if (--m_autoplayLeft > 0) {
        QTimer::singleShot(200, this, &Server::autoplayNextRoom);
    } else {
        const double total = m_autoplayAllT0.elapsed() / 1000.0;
        a1Log(QString("=== A1 无头自对弈全部结束：%1 局 / 总 %2s / 平均 %3s 每局 ===")
              .arg(m_autoplaySeq).arg(total, 0, 'f', 1)
              .arg(m_autoplaySeq > 0 ? total / m_autoplaySeq : 0.0, 0, 'f', 1));
        if (s_a1Log != NULL) {
            s_a1Log->close();
        }
        qApp->quit();
    }
}

void Server::gameOver()
{
    Room *room = qobject_cast<Room *>(sender());
    rooms.remove(room);

    foreach(ServerPlayer *player, room->findChildren<ServerPlayer *>())
    {
        name2objname.remove(player->screenName(), player->objectName());
        players.remove(player->objectName());
    }
}
