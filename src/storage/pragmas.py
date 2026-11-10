"""SQLite 平台调优面（#601 R42）。

WAL（write-ahead logging）让「一写多读」并发成为可能——研究工作区
的典型负载（pipeline 写 + analyze 读）收益明显。但 WAL **依赖共享
内存机制**，在以下场景会静默失效或直接不可用：

- Windows 网络盘（SMB/CIFS 共享映射盘）；
- 旧式 FAT/exFAT 本地卷；
- 部分容器/虚拟文件系统（overlayfs 某些配置）。

失效时 SQLite 不报错，只是 ``PRAGMA journal_mode=WAL`` 的返回值
停留在 ``delete``。本模块据此做**探测-回退**：能切则切（附
``synchronous=NORMAL``），不能切保持缺省日志模式并如实回报，
绝不让调用方在不知道的情况下以为获得了 WAL 并发。

Linux 本地 ext4/xfs 与 Windows NTFS 本地卷均支持 WAL。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union


def configure_pragmas(conn: sqlite3.Connection) -> dict[str, str]:
    """应用平台安全的 PRAGMA 组合，返回实际生效的 journal 模式等信息。

    Returns:
        ``{"journal_mode": "wal"|"delete"|..., "synchronous": "1"}``，
        以 SQLite 回报的**生效值**为准（而非请求值）。
    """
    applied: dict[str, str] = {}
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    mode = str(row[0]).lower() if row else "unknown"
    applied["journal_mode"] = mode
    if mode == "wal":
        # WAL 下 NORMAL 足够安全（断电最多丢最后一次事务，不损库）
        conn.execute("PRAGMA synchronous=NORMAL")
    else:
        # 回退路径：保持 delete 日志 + FULL 同步（SQLite 缺省，最稳）
        conn.execute("PRAGMA synchronous=FULL")
    sync_row = conn.execute("PRAGMA synchronous").fetchone()
    applied["synchronous"] = str(sync_row[0]) if sync_row else "unknown"
    return applied


def journal_mode_of(db_path: Union[str, Path]) -> str:
    """只读探测一个库文件的当前日志模式（诊断面）。"""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).lower() if row else "unknown"
    finally:
        conn.close()


def wal_available(db_path: Union[str, Path]) -> bool:
    """在目标路径实测 WAL 可用性（不改动既有库——用临时文件）。"""
    probe = Path(str(db_path) + ".wal-probe")
    conn = sqlite3.connect(str(probe))
    try:
        applied = configure_pragmas(conn)
        return applied["journal_mode"] == "wal"
    finally:
        conn.close()
        try:
            probe.unlink()
            Path(str(probe) + "-wal").unlink(missing_ok=True)
            Path(str(probe) + "-shm").unlink(missing_ok=True)
        except OSError:
            pass
