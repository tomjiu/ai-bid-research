"""src/collect.sources CSV 读取器测试（#601 R31）。

覆盖 CSV 三约定：表头别名归一（复用 ``from_raw``）、空白单元格→None、
行级失败粒度（坏行不殃及好行）；以及文件级失败（空文件/仅表头/解码失败）、
目录混合源、增量水位与严格模式。
"""

import os

import pytest

from src.collect import SourceError, load_records
from src.collect.sources import resolve_source_files


def _write(path, text, encoding="utf-8"):
    path.write_text(text, encoding=encoding)


# ----------------------------------------------------------------------
# 表头归一与单元格口径
# ----------------------------------------------------------------------

class TestCsvHeaders:
    """表头映射与单元格语义。"""

    def test_canonical_headers(self, tmp_path):
        """规范名表头：字段直通，金额/日期归一。"""
        path = tmp_path / "bids.csv"
        _write(
            path,
            "bid_id,project_name,region,budget,publish_date\n"
            "A-1,某智慧城市项目,浙江,350.5,2026-01-15\n"
            "A-2,某政务云项目,江苏,1.2亿,2026/2/3\n",
        )
        result = load_records(path)
        assert result.failures == []
        assert len(result.records) == 2
        first, second = result.records
        assert first.budget == 350.5
        assert first.publish_date == "2026-01-15"
        assert second.budget == 12000.0  # 1.2亿 → 万元
        assert second.publish_date == "2026-02-03"

    def test_alias_headers_normalized(self, tmp_path):
        """中文别名表头：与 JSON 源同一归一口径。"""
        path = tmp_path / "alias.csv"
        _write(
            path,
            "招标编号,项目名称,预算金额,发布日期,采购人\n"
            "B-1,某数据中台项目,350万,2026年1月5日,某大数据局\n",
        )
        result = load_records(path)
        assert result.failures == []
        record = result.records[0]
        assert record.bid_id == "B-1"
        assert record.budget == 350.0
        assert record.publish_date == "2026-01-05"
        assert record.purchaser == "某大数据局"

    def test_blank_cells_become_none(self, tmp_path):
        """空白单元格 → None（缺失与显式留空同口径，无告警）。"""
        path = tmp_path / "blank.csv"
        _write(
            path,
            "bid_id,project_name,region,budget,deadline\n"
            "C-1,某项目,,,\n",
        )
        result = load_records(path)
        assert result.failures == []
        record = result.records[0]
        assert record.region is None
        assert record.budget is None
        assert record.deadline is None
        assert record.warnings == []

    def test_bom_tolerated(self, tmp_path):
        """UTF-8 BOM（Excel 导出常见）：表头首列不被 BOM 污染。"""
        path = tmp_path / "bom.csv"
        _write(
            path,
            "招标编号,项目名称\nD-1,某项目\n",
            encoding="utf-8-sig",
        )
        result = load_records(path)
        assert result.failures == []
        assert result.records[0].bid_id == "D-1"

    def test_quoted_comma_cell(self, tmp_path):
        """带引号单元格内的逗号：按单字段解析。"""
        path = tmp_path / "quoted.csv"
        _write(
            path,
            'bid_id,project_name,region\nE-1,"项目,二期",浙江\n',
        )
        result = load_records(path)
        assert result.failures == []
        assert result.records[0].project_name == "项目,二期"


# ----------------------------------------------------------------------
# 失败粒度
# ----------------------------------------------------------------------

class TestCsvFailures:
    """行级/文件级失败语义。"""

    def test_row_level_failure_origin(self, tmp_path):
        """列数不齐的坏行：登记行级失败，好行不受殃及。"""
        path = tmp_path / "rows.csv"
        _write(
            path,
            "bid_id,project_name\n"
            "F-1,好行一\n"
            "F-2\n"
            "F-3,好行三\n",
        )
        result = load_records(path)
        assert [r.bid_id for r in result.records] == ["F-1", "F-3"]
        assert len(result.failures) == 1
        assert result.failures[0]["origin"] == "rows.csv:3"
        assert "列数不齐" in result.failures[0]["error"]

    def test_missing_required_field_row(self, tmp_path):
        """必填列空缺的行：RecordValidationError 登记为行级失败。"""
        path = tmp_path / "missing.csv"
        _write(
            path,
            "招标编号,项目名称\n,缺编号的项目\nG-1,正常项目\n",
        )
        result = load_records(path)
        assert [r.bid_id for r in result.records] == ["G-1"]
        assert len(result.failures) == 1
        assert result.failures[0]["origin"] == "missing.csv:2"

    def test_empty_file_is_file_level_failure(self, tmp_path):
        """空文件：文件级失败（口径同 JSONL 零非空行）。"""
        path = tmp_path / "empty.csv"
        _write(path, "")
        result = load_records(path)
        assert result.records == []
        assert len(result.failures) == 1
        assert result.failures[0]["origin"] == "empty.csv"

    def test_header_only_is_file_level_failure(self, tmp_path):
        """仅表头零数据行：文件级失败（大概率截断/损坏）。"""
        path = tmp_path / "header.csv"
        _write(path, "bid_id,project_name\n")
        result = load_records(path)
        assert result.records == []
        assert len(result.failures) == 1
        assert "零数据行" in result.failures[0]["error"]

    def test_bad_encoding_is_file_level_failure(self, tmp_path):
        """非 UTF-8 编码：解码失败登记为文件级失败。"""
        path = tmp_path / "gbk.csv"
        path.write_bytes("招标编号,项目名称\nH-1,某项目\n".encode("gbk"))
        result = load_records(path)
        assert result.records == []
        assert len(result.failures) == 1
        assert "解码失败" in result.failures[0]["error"]

    def test_strict_mode_raises(self, tmp_path):
        """严格模式：第一个坏行即抛（origin 携带行号）。"""
        path = tmp_path / "strict.csv"
        _write(path, "bid_id,project_name\nI-1,好行\nI-2\n")
        with pytest.raises(ValueError, match="strict.csv:3"):
            load_records(path, skip_invalid=False)


# ----------------------------------------------------------------------
# 源解析与水位
# ----------------------------------------------------------------------

class TestCsvSourceResolution:
    """目录源 / 扩展名分发 / 增量水位。"""

    def test_directory_mixed_sources(self, tmp_path):
        """混合目录：json + jsonl + csv 全部装载，文件名序确定性。"""
        _write(
            tmp_path / "a.json",
            '[{"bid_id": "J-1", "project_name": "json 源"}]',
        )
        _write(
            tmp_path / "b.jsonl",
            '{"bid_id": "J-2", "project_name": "jsonl 源"}\n',
        )
        _write(
            tmp_path / "c.csv",
            "bid_id,project_name\nJ-3,csv 源\n",
        )
        result = load_records(tmp_path)
        assert result.failures == []
        assert result.files_read == 3
        assert [r.bid_id for r in result.records] == ["J-1", "J-2", "J-3"]

    def test_since_watermark_skips_old_csv(self, tmp_path):
        """增量水位：mtime 早于水位的 CSV 不读（空结果非错误）。"""
        path = tmp_path / "old.csv"
        _write(path, "bid_id,project_name\nK-1,旧文件\n")
        old = 1_000_000.0
        os.utime(path, (old, old))
        result = load_records(path, since=old + 1000)
        assert result.records == []
        assert result.failures == []
        assert result.files_read == 0

    def test_unknown_suffix_error_mentions_csv(self, tmp_path):
        """未知扩展名报错信息含全部受支持类型。"""
        path = tmp_path / "data.xlsx"
        _write(path, "whatever")
        with pytest.raises(SourceError, match=r"\.csv"):
            resolve_source_files(path)
