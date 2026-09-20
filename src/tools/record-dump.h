#ifndef RECORD_DUMP_H
#define RECORD_DUMP_H

// 录像局面导出（无界面）
//
//   用途：把 .qsgs 录像重放一遍，并在**每一个"发给录制者的请求"**出现的时刻，
//         把当时录制者看得见的完整局面导出成一行 JSON（JSON Lines）。
//   为什么不用 GUI：这才是"不靠目视"的关键 —— 输出即文件/标准输出，
//         可以直接喂给 Python 侧做四层自校验（尤其 L2 手牌数周期对账）。
//
//   入口由 main.cpp 的 `-dump` 分支调用（与既有 `-server` 并列）。
//
//   用法：
//     QSanguosha.exe -dump <录像.qsgs> [-o out.jsonl] [-n 每局最多导出N个决策点]
//     不带 -o 则输出到标准输出（可重定向 > out.jsonl）
//
//   返回码：0 成功 / 2 打不开文件 / 3 解压失败 / 4 Client 创建失败

#include <QString>

int runRecordDump(const QString &path, const QString &outPath, int limit);

#endif // RECORD_DUMP_H
