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

#if defined(WIN32) && !defined(GPP) && !defined(QT_NO_DEBUG) && !defined(WINRT)
#include <vld/vld.h>
#endif

#include <QFile>
#include <QCoreApplication>
#include <QApplication>
#include <QTranslator>
#include <QDateTime>
#include <QSplashScreen>
#include <QMessageBox>

#include "server.h"
#include "settings.h"
#include "engine.h"
#include "mainwindow.h"
#include "audio.h"
#include "stylehelper.h"
#include "tools/record-dump.h"

#ifndef WINDOWS
#include <QDir>
#endif

#ifdef USE_BREAKPAD
#include <client/windows/handler/exception_handler.h>
#include <QProcess>

using namespace google_breakpad;

static bool callback(const wchar_t *, const wchar_t *id, void *, EXCEPTION_POINTERS *, MDRawAssertionInfo *, bool succeeded)
{
    if (succeeded && QFile::exists("QSanSMTPClient.exe")) {
        char ID[16000];
        memset(ID, 0, sizeof(ID));
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4996)
#endif
        wcstombs(ID, id, wcslen(id));
#ifdef _MSC_VER
#pragma warning(pop)
#endif
        QProcess *process = new QProcess(qApp);
        QStringList args;
        args << QString(ID) + ".dmp";
        process->start("QSanSMTPClient", args);
    }
    return succeeded;
}
#endif

int main(int argc, char *argv[])
{
    bool noGui = argc > 1 && strcmp(argv[1], "-server") == 0;
    // 录像局面导出模式：仍然用 QApplication（Client 依赖 QtGui），但不建任何窗口、不显示 splash
    bool dumpMode = argc > 1 && strcmp(argv[1], "-dump") == 0;

    if (noGui)
        new QCoreApplication(argc, argv);
    else
        new QApplication(argc, argv);

#if defined(Q_OS_MAC) || defined(Q_OS_ANDROID)
#define showSplashMessage(message)
#define SPLASH_DISABLED
#else
    QSplashScreen *splash = NULL;
    if (!noGui && !dumpMode) {
        QPixmap raraLogo;
        QDate currentDate = QDate::currentDate();
        if (currentDate.month() == 11 && currentDate.day() == 30)
            raraLogo.load("image/system/developers/logo_rara.png");
        else
            raraLogo.load("image/system/developers/logo.png");

        splash = new QSplashScreen(raraLogo);
        splash->show();
        qApp->processEvents();
    }
#define showSplashMessage(message) \
    if (splash == NULL) {\
        puts(message.toUtf8().constData());\
        } else {\
        splash->showMessage(message, Qt::AlignBottom | Qt::AlignHCenter, Qt::cyan);\
        qApp->processEvents();\
        }
#endif

#ifdef USE_BREAKPAD
    showSplashMessage(QSplashScreen::tr("Loading BreakPad..."));
    ExceptionHandler eh(L"./dmp", NULL, callback, NULL, ExceptionHandler::HANDLER_ALL);
#endif

#if defined(Q_OS_MAC) && defined(QT_NO_DEBUG)
    showSplashMessage(QSplashScreen::tr("Setting game path..."));
    QDir::setCurrent(qApp->applicationDirPath());
#endif

#ifdef Q_OS_LINUX
    showSplashMessage(QSplashScreen::tr("Checking game path..."));
    QDir dir(QString("lua"));
    if (dir.exists() && (dir.exists(QString("config.lua")))) {
        // things look good and use current dir
    } else {
        showSplashMessage(QSplashScreen::tr("Setting game path..."));
#ifndef Q_OS_ANDROID
        QDir::setCurrent(qApp->applicationFilePath().replace("games", "share"));
#else
        bool found = false;
        QDir storageDir("/storage");
        QStringList sdcards = storageDir.entryList(QDir::Dirs | QDir::NoDotAndDotDot);
        foreach (const QString &sdcard, sdcards) {
            QDir root(QString("/storage/%1/Android/data/org.qsgsrara.qsanguosha").arg(sdcard));
            if (root.exists("lua/config.lua")) {
                QDir::setCurrent(root.absolutePath());
                found = true;
                break;
            }
        }
        if (!found) {
            QDir root("/sdcard/Android/data/org.qsgsrara.qsanguosha");
            if (root.exists("lua/config.lua")) {
                QDir::setCurrent(root.absolutePath());
                found = true;
            }
        }


        if (!found) {
            QString m = QObject::tr("Game data not found, please download QSanguosha-For-Hegemony PC version, and put the files and folders into /sdcard/Android/data/org.qsgsrara.qsanguosha");
            if (!noGui)
                QMessageBox::critical(NULL, QObject::tr("Error"), m);
            else
                puts(m.toLatin1().constData());

            return -2;
        }
#endif
    }
#endif

    // initialize random seed for later use
    // ── [A1 补丁 2026-09-20] A1_SEED 环境变量优先，★ 必须在**进程最早期**播种 ──
    //   原因（A/B 实测暴露）：机器人填充 / 武将分配等 qrand 调用发生在
    //   RoomThread::run() 之前；若这里仍用时间种子（进程启动时刻），那批调用
    //   就会两侧分叉，之后再固定种子也救不回来 —— 表现为「同 A1_SEED 仍得到
    //   不同武将与座次」。未设 A1_SEED 时行为与原来完全一致。
    {
        bool a1SeedOk = false;
        const uint a1Seed = QString::fromLocal8Bit(qgetenv("A1_SEED")).toUInt(&a1SeedOk);
        qsrand(a1SeedOk ? a1Seed : (uint)QTime(0, 0, 0).secsTo(QTime::currentTime()));
    }

    // load the main translation file first for we need to translate messages of splash.
    QTranslator translator;
    translator.load("sanguosha.qm");
    qApp->installTranslator(&translator);

    showSplashMessage(QSplashScreen::tr("Loading translation..."));
    QTranslator qt_translator;
    qt_translator.load("qt_zh_CN.qm");
    qApp->installTranslator(&qt_translator);

    showSplashMessage(QSplashScreen::tr("Initializing game engine..."));
    new Settings;
    Sanguosha = new Engine;

    showSplashMessage(QSplashScreen::tr("Loading user's configurations..."));
    Config.init();
    if (!noGui) {
        QFont f = Config.AppFont;
#ifdef Q_OS_ANDROID
        f.setPointSize(12);
#endif
        qApp->setFont(f);
    }

    if (qApp->arguments().contains("-server")) {
        Server *server = new Server(qApp);

        // ── [A1 补丁 2026-09-19] 无头自对弈 ──────────────────────────────
        //    QSanguosha.exe -server -autoplay [N]
        //     不开监听端口；在进程内直接连跑 N 局「全 10 席都是 bot」的国战，
        //     每局 10 席各自录像到工作目录 a1_out/(gNNN/<座位>.qsgs)，进度写
        //     a1_out/autoplay.log。用于 A1 的训练数据生成。
        if (qApp->arguments().contains("-autoplay")) {
            const QStringList args = qApp->arguments();
            const int idx = args.indexOf("-autoplay");
            int games = 1;
            if (idx + 1 < args.size()) {
                bool ok = false;
                const int v = args.at(idx + 1).toInt(&ok);
                if (ok && v > 0)
                    games = v;
            }
            server->autoplay(games);
            return qApp->exec();
        }

        printf("Server is starting on port %u\n", Config.ServerPort);

        if (server->listen())
            printf("Starting successfully\n");
        else
            printf("Starting failed!\n");

        return qApp->exec();
    }

    // ── 录像局面导出：QSanguosha.exe -dump <录像.qsgs> [-o out.jsonl] [-n N] ──
    //    不需要服务器、不建窗口，输出 JSON Lines（stdout 或 -o 文件）。
    if (dumpMode) {
        const QStringList args = qApp->arguments();
        const int i = args.indexOf("-dump");
        const QString rec = (i >= 0 && i + 1 < args.size()) ? args.at(i + 1) : QString();
        QString outPath;
        if (args.contains("-o")) outPath = args.at(args.indexOf("-o") + 1);
        int limit = 0;
        if (args.contains("-n")) limit = args.at(args.indexOf("-n") + 1).toInt();
        return runRecordDump(rec, outPath, limit);
    }

    showSplashMessage(QSplashScreen::tr("Loading style sheet..."));
    QFile file("style-sheet/sanguosha.qss");
    QString styleSheet;
    if (file.open(QIODevice::ReadOnly)) {
        QTextStream stream(&file);
        styleSheet = stream.readAll();
    }

#ifdef Q_OS_WIN
    QFile winFile("style-sheet/windows-extra.qss");
    if (winFile.open(QIODevice::ReadOnly)) {
        QTextStream winStream(&winFile);
        styleSheet += winStream.readAll();
    }
#endif

    qApp->setStyleSheet(styleSheet + StyleHelper::styleSheetOfTooltip());

#ifdef AUDIO_SUPPORT
    showSplashMessage(QSplashScreen::tr("Initializing audio module..."));
    Audio::init();
#else
    if (!noGui)
        QMessageBox::warning(NULL, QMessageBox::tr("Warning"), QMessageBox::tr("Audio support is disabled when compiled"));
#endif

    showSplashMessage(QSplashScreen::tr("Loading main window..."));
    MainWindow main_window;

    Sanguosha->setParent(&main_window);
    main_window.show();
#ifndef SPLASH_DISABLED
    if (splash != NULL) {
        splash->finish(&main_window);
        delete splash;
    }
#endif

    foreach (const QString &_arg, qApp->arguments()) {
        QString arg = _arg;
        if (arg.startsWith("-connect:")) {
            arg.remove("-connect:");
            Config.HostAddress = arg;
            Config.setValue("HostAddress", arg);

            main_window.startConnection();
            break;
        }
    }

    return qApp->exec();
}
