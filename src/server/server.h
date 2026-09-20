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

#ifndef SERVER_H
#define SERVER_H

#include <QObject>
#include <QSet>
#include <QStringList>
#include <QElapsedTimer>

#include "protocol.h"

class Room;
class ClientSocket;
class ServerSocket;
class ServerPlayer;

class Server : public QObject
{
    Q_OBJECT

public:
    friend class BanIpDialog;

    explicit Server(QObject *parent);

    void broadcastSystemMessage(const QString &msg);

    bool listen();
    void daemonize();


    Room *createNewRoom();
    void signupPlayer(ServerPlayer *player);

    // ── [A1 补丁 2026-09-19] 无头自对弈（命令行 -autoplay [N]）──────────
    //  不开监听端口，直接在进程内造「全 bot 房」连跑 N 局，每局 10 席全录像。
    //  日志/录像落盘到工作目录下的 a1_out/（Debug 版无控制台，printf 无效）。
    void autoplay(int games);

private:
    void notifyClient(ClientSocket *socket, QSanProtocol::CommandType command, const QVariant &arg = QVariant());

    void processClientRequest(ClientSocket *socket, const QSanProtocol::Packet &signup);

    void autoplayNextRoom();
    int m_autoplayLeft;
    int m_autoplaySeq;
    QString m_autoplayOut;   // [A1 补丁] 输出根目录（env A1_OUT 可覆盖，多实例隔离用）
    QElapsedTimer m_autoplayRoomT0;
    QElapsedTimer m_autoplayAllT0;

    ServerSocket *server;
    Room *current;
    QSet<Room *> rooms;
    QHash<QString, ServerPlayer *> players;
    QStringList addresses;
    QMultiHash<QString, QString> name2objname;

private slots:
    void processNewConnection(ClientSocket *socket);
    void processRequest(const QByteArray &request);
    void cleanup();
    void gameOver();
    void autoplayGameOver(const QString &winner);   // [A1 补丁]

signals:
    void server_message(const QString &);
    void newPlayer(ServerPlayer *player);
};

#endif // SERVER_H
