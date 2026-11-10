"""跨平台进程级文件锁（#601 R41）。

场景：研究工作区是多终端共用的（一个终端跑 ``pipeline``、另一个跑
``db export``），SQLite 同文件并发写会触发 ``database is locked``。
本模块提供**咨询锁**（advisory lock）：同机多进程互斥，语义在
Linux（``fcntl.flock``）与 Windows（``msvcrt.locking``）上一致：

- 非阻塞抢占 + 轮询重试，超时抛 :class:`LockTimeoutError`；
- 锁文件本身 ``a+b`` 创建，不覆盖既有内容；
- 跨平台实现差异收敛在 ``_acquire`` / ``_release`` 两私有函数，
  公共语义（超时/清理/异常路径）单平台即可全测。

Windows ``msvcrt.locking`` 只锁从当前位置起的 N 字节，故先
``seek(0)`` 再锁 1 字节——与 POSIX 全文件锁在「单写者」用途上
等价（本仓库锁文件不含数据）。
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator

#: 轮询间隔（秒）——Windows 无 flock 的阻塞模式，只能自旋
_POLL_INTERVAL = 0.05


class LockTimeoutError(RuntimeError):
    """在超时窗口内未能取得文件锁。"""

    def __init__(self, path: Path, timeout: float):
        self.path = path
        self.timeout = timeout
        super().__init__(f"文件锁获取超时（{timeout:.1f}s）：{path}")


def _acquire_posix(fh: IO[bytes]) -> None:
    """Linux/macOS：flock 非阻塞抢占，失败抛 OSError。"""
    import fcntl

    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_posix(fh: IO[bytes]) -> None:
    import fcntl

    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _acquire_windows(fh: IO[bytes]) -> None:
    """Windows：msvcrt 锁文件首字节，失败抛 OSError。"""
    import msvcrt

    fh.seek(0)
    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)


def _release_windows(fh: IO[bytes]) -> None:
    import msvcrt

    fh.seek(0)
    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


def _is_windows() -> bool:
    return sys.platform == "win32"


@contextmanager
def file_lock(path: Path | str, timeout: float = 5.0) -> Iterator[IO[bytes]]:
    """跨平台文件锁上下文。

    Args:
        path: 锁文件路径（惯例：目标文件名 + ``.lock``）。
        timeout: 最长等待秒数；超时抛 :class:`LockTimeoutError`。

    Yields:
        已取得锁的文件句柄（调用方一般忽略，仅用作作用域标记）。

    用法::

        with file_lock(db_path.with_suffix(".db.lock")):
            db = BidDatabase(db_path)  # 临界区
    """
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+b")
    acquire = _acquire_windows if _is_windows() else _acquire_posix
    release = _release_windows if _is_windows() else _release_posix
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                acquire(fh)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(lock_path, timeout) from None
                time.sleep(_POLL_INTERVAL)
        yield fh
    finally:
        try:
            release(fh)
        except (OSError, ValueError):
            # 句柄已被关闭/锁已失效——释放失败不掩盖主体异常
            pass
        if not fh.closed:
            fh.close()


def lock_sidecar(target: Path | str) -> Path:
    """目标文件的锁伴生路径（``data/bids.db`` → ``data/bids.db.lock``）。"""
    return Path(str(target) + ".lock")


def run_exclusive(target: Path | str, fn, timeout: float = 5.0):
    """在目标文件的排它锁内执行 ``fn()`` 并返回其结果。

    供 storage 层复用：调用方无需感知锁文件细节。
    """
    with file_lock(lock_sidecar(target), timeout=timeout):
        return fn()
