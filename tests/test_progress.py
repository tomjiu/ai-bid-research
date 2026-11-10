"""进度指示面测试（#601 R68）。"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from src.extract import AnnouncementExtractor
from src.llm.client import LLMClient
from src.progress import ProgressPrinter


class _TtyStream:
    def __init__(self):
        self.chunks: list[str] = []
        self._tty = True

    def isatty(self) -> bool:
        return self._tty

    def write(self, text):
        self.chunks.append(text)

    def flush(self):
        pass

    @property
    def text(self):
        return "".join(self.chunks)


class TestProgressPrinter:
    def test_tty_inline_updates(self):
        stream = _TtyStream()
        p = ProgressPrinter(total=3, label="抽取", stream=stream)
        p.step(1, "B-1")
        p.step(2, "B-2")
        p.step(3, "B-3")
        p.finish(summary="完成")
        text = stream.text
        assert "\r抽取中 1/3 · B-1" in text
        assert "\r抽取中 2/3 · B-2" in text
        assert text.endswith("完成\n")

    def test_non_tty_silent(self):
        stream = _TtyStream()
        stream._tty = False
        p = ProgressPrinter(total=5, label="抽取", stream=stream)
        for i in range(1, 6):
            p.step(i, f"B-{i}")
        p.finish(summary="完成 5 条")
        assert stream.text == ""  # 非 tty 零输出（摘要由调用方管）

    def test_quarter_logging_non_tty(self, caplog):
        stream = _TtyStream()
        stream._tty = False
        p = ProgressPrinter(total=8, label="抽取", stream=stream)
        with caplog.at_level(logging.DEBUG, logger="ai-bid-research.progress"):
            for i in range(1, 9):
                p.step(i)
        # 每 25% 一条 DEBUG（1/4 → i=3 时刻等）——至少两条
        debug_lines = [
            r for r in caplog.records if r.levelno == logging.DEBUG
        ]
        assert len(debug_lines) >= 2

    def test_zero_total_disabled(self):
        stream = _TtyStream()
        p = ProgressPrinter(total=0, label="抽取", stream=stream)
        p.step(1)
        p.finish(summary="空")
        assert stream.text == ""

    def test_no_steps_finish_silent(self):
        stream = _TtyStream()
        p = ProgressPrinter(total=10, label="抽取", stream=stream)
        p.finish(summary="未开始")
        assert stream.text == ""

    def test_closed_stream_does_not_crash(self):
        class _Closed:
            def isatty(self):
                return True

            def write(self, text):
                raise ValueError("I/O operation on closed file")

            def flush(self):
                raise ValueError("closed")

        p = ProgressPrinter(total=2, label="抽取", stream=_Closed())
        p.step(1, "B-1")  # 不抛——展示层绝不反噬主流程
        p.finish()


class TestExtractorProgressCallback:
    @pytest.mark.asyncio
    async def test_callback_fires_per_record(self):
        from src.collect.records import AnnouncementRecord

        client = LLMClient(api_key="k")
        client.chat_json = AsyncMock(
            return_value={"bid_id": "placeholder"}
        )
        extractor = AnnouncementExtractor(client)
        records = [
            AnnouncementRecord.from_raw(
                {"bid_id": f"E-{i}", "project_name": f"项目{i}",
                 "content": "预算 100万元"}
            )
            for i in range(3)
        ]
        seen: list[tuple[int, int, str]] = []
        result = await extractor.extract_batch(
            records, progress=lambda cur, total, bid: seen.append(
                (cur, total, bid)
            )
        )
        assert len(result.outcomes) == 3
        assert seen == [
            (1, 3, "E-0"),
            (2, 3, "E-1"),
            (3, 3, "E-2"),
        ]

    @pytest.mark.asyncio
    async def test_broken_callback_does_not_break_batch(self):
        """进度回调抛异常——批处理继续（展示层隔离）。"""
        from src.collect.records import AnnouncementRecord

        client = LLMClient(api_key="k")
        client.chat_json = AsyncMock(
            return_value={"bid_id": "placeholder"}
        )
        extractor = AnnouncementExtractor(client)
        records = [
            AnnouncementRecord.from_raw(
                {"bid_id": "X-1", "project_name": "项目", "content": "文"}
            )
        ]

        def bad_callback(cur, total, bid):
            raise RuntimeError("进度面崩溃")

        result = await extractor.extract_batch(
            records, progress=bad_callback
        )
        assert len(result.outcomes) == 1

    @pytest.mark.asyncio
    async def test_progress_on_failure_record_too(self):
        """失败条目也推进进度（current 连续不跳号）。"""
        from src.collect.records import AnnouncementRecord

        client = LLMClient(api_key="k")
        client.chat_json = AsyncMock(side_effect=RuntimeError("断"))
        extractor = AnnouncementExtractor(client)
        records = [
            AnnouncementRecord.from_raw(
                {"bid_id": "F-1", "project_name": "项目", "content": "文"}
            ),
            AnnouncementRecord.from_raw(
                {"bid_id": "F-2", "project_name": "项目", "content": "文"}
            ),
        ]
        seen: list[int] = []
        await extractor.extract_batch(
            records, progress=lambda cur, total, bid: seen.append(cur)
        )
        assert seen == [1, 2]


class TestCliWiring:
    def test_extract_no_llm_still_fine_with_progress(self, tmp_path, capsys):
        """--no-llm 直通模式 + 零进度输出（非 tty）不炸、结果正确。"""
        import json as _json

        import main as main_mod

        src = tmp_path / "s.jsonl"
        src.write_text(
            _json.dumps(
                {"bid_id": "W-1", "project_name": "直通项目"},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        rc = main_mod.main(
            [
                "extract", "--source", str(src),
                "--db", str(tmp_path / "w.db"),
                "--no-llm",
            ]
        )
        assert rc == 0
        assert "抽取完成" in capsys.readouterr().out
