"""R41 跨平台文件锁测试——Linux 真实 flock + Windows 分支注入替身。"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

from src.locking import (
    LockTimeoutError,
    file_lock,
    lock_sidecar,
    run_exclusive,
)


class TestPosixRealLock:
    """真实 flock 语义（Linux 沙箱）——互斥与释放。"""

    def test_second_lock_blocks_until_release(self, tmp_path):
        lock = tmp_path / "a.lock"
        with file_lock(lock, timeout=3.0):
            held = []

            def grab():
                try:
                    with file_lock(lock, timeout=0.2):
                        held.append("acquired")
                except LockTimeoutError:
                    held.append("timeout")

            t = threading.Thread(target=grab)
            t.start()
            t.join()
            assert held == ["timeout"]
        # 释放后可立即复得
        with file_lock(lock, timeout=1.0):
            pass

    def test_timeout_error_carries_path(self, tmp_path):
        lock = tmp_path / "b.lock"
        with file_lock(lock):
            with pytest.raises(LockTimeoutError) as ei:
                with file_lock(lock, timeout=0.1):
                    pass
        assert ei.value.path == lock
        assert ei.value.timeout == 0.1

    def test_run_exclusive_returns_fn_result(self, tmp_path):
        target = tmp_path / "c.db"
        assert run_exclusive(target, lambda: 42) == 42

    def test_sidecar_naming(self, tmp_path):
        assert lock_sidecar(tmp_path / "bids.db") == tmp_path / "bids.db.lock"

    def test_lock_dir_autocreate(self, tmp_path):
        lock = tmp_path / "deep" / "nested" / "x.lock"
        with file_lock(lock, timeout=1.0):
            assert lock.exists()

    def test_reentrant_same_thread_blocks_and_times_out(self, tmp_path):
        # flock 同进程同 fd 可重入，但不同 fd（两次 open）仍互斥
        lock = tmp_path / "d.lock"
        with file_lock(lock, timeout=1.0):
            with pytest.raises(LockTimeoutError):
                with file_lock(lock, timeout=0.1):
                    pass


class _FakeMsvcrt:
    """msvcrt 替身：字节范围锁语义——任一持有者在场，他人 NBLCK 即失败。"""

    LK_NBLCK = 2
    LK_UNLCK = 8

    def __init__(self):
        self.locked_fds: set[int] = set()
        self.calls: list[tuple[int, int]] = []

    def locking(self, fd, mode, nbytes):
        import errno

        self.calls.append((fd, mode))
        if mode == self.LK_NBLCK:
            if self.locked_fds and fd not in self.locked_fds:
                raise OSError(errno.EACCES, "locked by another process")
            self.locked_fds.add(fd)
        else:
            self.locked_fds.discard(fd)


class TestWindowsBranch:
    """sys.platform=win32 + 注入 msvcrt 替身，验证分支接线。"""

    def test_windows_acquire_release_flow(self, tmp_path, monkeypatch):
        fake = _FakeMsvcrt()
        monkeypatch.setitem(sys.modules, "msvcrt", fake)
        monkeypatch.setattr(sys, "platform", "win32")
        lock = tmp_path / "w.lock"
        with file_lock(lock, timeout=1.0):
            assert any(m == _FakeMsvcrt.LK_NBLCK for _, m in fake.calls)
        assert any(m == _FakeMsvcrt.LK_UNLCK for _, m in fake.calls)

    def test_windows_contention_times_out(self, tmp_path, monkeypatch):
        fake = _FakeMsvcrt()
        monkeypatch.setitem(sys.modules, "msvcrt", fake)
        monkeypatch.setattr(sys, "platform", "win32")
        lock = tmp_path / "w2.lock"
        with file_lock(lock, timeout=1.0):
            with pytest.raises(LockTimeoutError):
                with file_lock(lock, timeout=0.15):
                    pass

    def test_windows_release_failure_swallowed(self, tmp_path, monkeypatch):
        class _BrokenUnlock:
            LK_NBLCK = 2
            LK_UNLCK = 8

            def locking(self, fd, mode, nbytes):
                import errno

                if mode == self.LK_NBLCK:
                    return
                raise OSError(errno.EPERM, "unlock denied")

        monkeypatch.setitem(sys.modules, "msvcrt", _BrokenUnlock())
        monkeypatch.setattr(sys, "platform", "win32")
        # 释放失败不得掩盖主体逻辑（也不能让 with 卡死）
        with file_lock(tmp_path / "w3.lock", timeout=0.5):
            pass

    def test_poll_interval_allows_retry_then_success(self, tmp_path, monkeypatch):
        fake = _FakeMsvcrt()
        monkeypatch.setitem(sys.modules, "msvcrt", fake)
        monkeypatch.setattr(sys, "platform", "win32")
        lock = tmp_path / "w4.lock"

        # 第 1 次 NBLCK 失败，第 2 次成功——验证轮询而非一次判死
        real_locking = fake.locking
        state = {"n": 0}

        def flaky(fd, mode, nbytes):
            if mode == _FakeMsvcrt.LK_NBLCK and state["n"] == 0:
                import errno

                state["n"] += 1
                # 模拟他人持有后立刻放手
                fake.locked_fds.discard(fd)
                raise OSError(errno.EACCES, "transient")
            return real_locking(fd, mode, nbytes)

        fake.locking = flaky
        with file_lock(lock, timeout=2.0):
            assert state["n"] == 1
