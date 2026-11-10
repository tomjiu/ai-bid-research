"""pending 队列优先级测试（#601 R61）。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.extract import AnnouncementExtractor
from src.extract.pending import park_raw_failure
from src.llm.client import LLMClient
from src.storage.database import BidDatabase


def _park(db, name, *, reason, hit_rate=None, bid_prefix="P"):
    park_raw_failure(
        db,
        raw_text=f"{name} 的公告原文",
        reason=reason,
        error="记录的失败原因",
        bid_id=(f"{bid_prefix}-{name}" if bid_prefix else None),
        hit_rate=hit_rate,
    )


class TestListPendingPriority:
    def test_priority_order_llm_error_first_then_hit_rate(self):
        db = BidDatabase(":memory:")
        try:
            _park(db, "a", reason="rejected", hit_rate=0.9)   # 结构性拒收
            _park(db, "b", reason="llm_error", hit_rate=0.4)  # 瞬态·低质
            _park(db, "c", reason="llm_error", hit_rate=0.8)  # 瞬态·高质
            _park(db, "d", reason="llm_error")                # 瞬态·无 hit_rate
            fifo = [r["bid_id"] for r in db.list_pending(limit=10)]
            assert fifo == ["P-a", "P-b", "P-c", "P-d"]  # 登记序不变
            prio = [
                r["bid_id"]
                for r in db.list_pending(limit=10, order="priority")
            ]
            # llm_error 优先；组内 hit_rate 降序 NULL 末；同位保登记序
            assert prio == ["P-c", "P-b", "P-d", "P-a"]
        finally:
            db.close()

    def test_fifo_default_unchanged(self):
        """缺省 order 参数 = fifo（历史行为零扰动）。"""
        db = BidDatabase(":memory:")
        try:
            _park(db, "x", reason="rejected")
            _park(db, "y", reason="llm_error", hit_rate=0.9)
            rows = db.list_pending(limit=10)
            assert [r["bid_id"] for r in rows] == ["P-x", "P-y"]
        finally:
            db.close()


class TestRetryPriority:
    def test_retry_priority_end_to_end(self, tmp_path):
        """纯原文流（无 bid_id）——重试走 chat_json，可捕获消费序。"""
        from src.extract.pending import retry_pending

        db = BidDatabase(tmp_path / "rp.db")
        try:
            # 不带 bid_id：raw 流（重试面真实走 LLM 的路径）
            _park(db, "a", reason="rejected", hit_rate=0.9, bid_prefix=None)
            _park(db, "b", reason="llm_error", hit_rate=0.4, bid_prefix=None)
            _park(db, "c", reason="llm_error", hit_rate=0.8, bid_prefix=None)
            _park(db, "d", reason="llm_error", bid_prefix=None)
        finally:
            db.close()

        # 捕获每次重试的提示词（内嵌原文——可反推消费顺序）
        calls: list[str] = []

        async def fail_and_capture(messages):
            calls.append(messages[-1]["content"])
            raise RuntimeError("仍失败")

        client = LLMClient(api_key="k")
        client.chat_json = AsyncMock(side_effect=fail_and_capture)
        extractor = AnnouncementExtractor(client)
        db2 = BidDatabase(tmp_path / "rp.db")
        try:
            report = retry_pending(db2, extractor, limit=2)
            assert report.attempted == 2
            # 优先序前二被消费：c（llm_error, hit 0.8）先于
            # b（llm_error, hit 0.4）；a（rejected）/d（无 hit）未动
            assert len(calls) == 2
            assert "c 的公告原文" in calls[0]
            assert "b 的公告原文" in calls[1]
            # 四条都还在 pending（重试失败不消失）——error 已刷新
            assert len(db2.list_pending(limit=10)) == 4
        finally:
            db2.close()


class TestCliPriority:
    def test_cli_pending_priority_flag(self, tmp_path, capsys):
        import main as main_mod

        db = BidDatabase(tmp_path / "cp.db")
        try:
            _park(db, "a", reason="rejected")
            _park(db, "b", reason="llm_error", hit_rate=0.8)
        finally:
            db.close()
        rc = main_mod.main(
            ["db", "--db", str(tmp_path / "cp.db"),
             "--pending", "--priority"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "重试价值优先序" in out
        assert out.index("P-b") < out.index("P-a")  # llm_error 先展示

    def test_cli_pending_default_fifo(self, tmp_path, capsys):
        import main as main_mod

        db = BidDatabase(tmp_path / "cf.db")
        try:
            _park(db, "a", reason="rejected")
            _park(db, "b", reason="llm_error")
        finally:
            db.close()
        rc = main_mod.main(
            ["db", "--db", str(tmp_path / "cf.db"), "--pending"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "登记序" in out
        assert out.index("P-a") < out.index("P-b")
