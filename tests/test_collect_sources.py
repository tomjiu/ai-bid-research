"""src/collect.sources 模块单元测试（#601 批次 A 第 2 轮）。

覆盖 JSON 数组/单对象/JSONL 三形态、目录源确定性、坏数据不静默
（失败逐条登记）与严格模式。
"""

import json

import pytest

from src.collect import (
    AnnouncementRecord,
    LoadResult,
    SourceError,
    load_records,
)


def _bid(bid_id: str, name: str = "某项目") -> dict:
    """构造最小合法公告载荷。"""
    return {"bid_id": bid_id, "project_name": name}


def _write(path, payload) -> None:
    """写 JSON/JSONL 文件（payload 为列表且后缀 jsonl 时行式写）。"""
    if path.suffix == ".jsonl" and isinstance(payload, list):
        path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in payload)
            + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )


# ----------------------------------------------------------------------
# 文件源三形态
# ----------------------------------------------------------------------

class TestFileForms:
    """单文件源三形态。"""

    def test_json_array(self, tmp_path):
        """JSON 数组：每元素一条记录。"""
        path = tmp_path / "bids.json"
        _write(path, [_bid("A-1"), _bid("A-2"), _bid("A-3")])
        result = load_records(path)
        assert [r.bid_id for r in result.records] == ["A-1", "A-2", "A-3"]
        assert result.failures == []
        assert result.files_read == 1

    def test_json_single_object(self, tmp_path):
        """单 JSON 对象：产出一条记录。"""
        path = tmp_path / "one.json"
        _write(path, {**_bid("S-1"), "region": "浙江"})
        result = load_records(path)
        assert len(result.records) == 1
        assert result.records[0].region == "浙江"

    def test_jsonl_lines_with_blanks(self, tmp_path):
        """JSONL：逐行解析，空行容忍。"""
        path = tmp_path / "bids.jsonl"
        path.write_text(
            json.dumps(_bid("L-1"), ensure_ascii=False)
            + "\n\n"
            + json.dumps(_bid("L-2"), ensure_ascii=False)
            + "\n\n",
            encoding="utf-8",
        )
        result = load_records(path)
        assert [r.bid_id for r in result.records] == ["L-1", "L-2"]

    def test_json_array_with_non_dict_item_fails_file(self, tmp_path):
        """JSON 数组含非对象元素 → 整文件失败（不产出半批）。"""
        path = tmp_path / "bad-array.json"
        path.write_text('["x", {"bid_id": "B-1"}]', encoding="utf-8")
        result = load_records(path)
        assert result.records == []
        assert len(result.failures) == 1
        assert "非对象元素" in result.failures[0]["error"]

    def test_jsonl_bad_line_fails_only_line(self, tmp_path):
        """JSONL 坏行只登记该行，其余行照常装载。"""
        path = tmp_path / "mixed.jsonl"
        path.write_text(
            json.dumps(_bid("G-1"), ensure_ascii=False)
            + "\n{broken json\n"
            + json.dumps(_bid("G-2"), ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        result = load_records(path)
        assert [r.bid_id for r in result.records] == ["G-1", "G-2"]
        assert len(result.failures) == 1
        assert result.failures[0]["origin"] == "mixed.jsonl:2"

    def test_jsonl_non_dict_line_fails_line(self, tmp_path):
        """JSONL 行是合法 JSON 但非对象（如字符串）→ 该行失败。"""
        path = tmp_path / "str.jsonl"
        path.write_text('"just a string"\n', encoding="utf-8")
        result = load_records(path)
        assert result.records == []
        assert "不是 JSON 对象" in result.failures[0]["error"]


# ----------------------------------------------------------------------
# 目录源
# ----------------------------------------------------------------------

class TestDirectorySource:
    """目录源收集面。"""

    def test_directory_sorted_deterministic(self, tmp_path):
        """目录源收集 json+jsonl，按文件名排序（确定性）。"""
        _write(tmp_path / "b.json", [_bid("D-2")])
        _write(tmp_path / "c.jsonl", [_bid("D-3")])
        _write(tmp_path / "a.json", [_bid("D-1")])
        result = load_records(tmp_path)
        assert [r.bid_id for r in result.records] == ["D-1", "D-2", "D-3"]
        assert result.files_read == 3

    def test_directory_ignores_other_suffixes(self, tmp_path):
        """非 json/jsonl 文件（txt/md）不被读取。"""
        _write(tmp_path / "keep.json", [_bid("K-1")])
        (tmp_path / "notes.txt").write_text("原始公告文本", encoding="utf-8")
        (tmp_path / "README.md").write_text("说明", encoding="utf-8")
        result = load_records(tmp_path)
        assert [r.bid_id for r in result.records] == ["K-1"]
        assert result.files_read == 1

    def test_directory_without_sources_raises(self, tmp_path):
        """目录内无受支持源文件 → SourceError（R32 起动态列举类型）。"""
        (tmp_path / "only.txt").write_text("x", encoding="utf-8")
        with pytest.raises(SourceError, match="目录内无"):
            load_records(tmp_path)

    def test_missing_path_raises(self, tmp_path):
        """路径不存在 → SourceError。"""
        with pytest.raises(SourceError, match="不存在"):
            load_records(tmp_path / "nope.json")

    def test_unsupported_suffix_raises(self, tmp_path):
        """文件扩展名不支持 → SourceError。"""
        path = tmp_path / "raw.txt"
        path.write_text("x", encoding="utf-8")
        with pytest.raises(SourceError, match="不支持的源文件类型"):
            load_records(path)


# ----------------------------------------------------------------------
# 失败语义：skip_invalid 双模式
# ----------------------------------------------------------------------

class TestFailureSemantics:
    """坏数据不静默——登记 or 抛错。"""

    def test_skip_invalid_collects_failures(self, tmp_path):
        """默认模式：坏文件/坏记录登记后继续，好数据不丢。"""
        _write(tmp_path / "good.json", [_bid("OK-1")])
        (tmp_path / "broken.json").write_text("{broken", encoding="utf-8")
        _write(tmp_path / "noreq.json", [{"bid_id": ""}])  # 缺项目名
        result = load_records(tmp_path)
        assert [r.bid_id for r in result.records] == ["OK-1"]
        assert len(result.failures) == 2
        origins = {f["origin"] for f in result.failures}
        assert origins == {"broken.json", "noreq.json"}
        assert result.total == 3

    def test_strict_mode_raises_first_failure(self, tmp_path):
        """严格模式：JSONL 坏行（真实语法错误）即抛。"""
        path = tmp_path / "broken.jsonl"
        path.write_text("{broken\n", encoding="utf-8")
        with pytest.raises(ValueError, match="第 1 行"):
            load_records(path, skip_invalid=False)

    def test_strict_mode_non_dict_line_raises(self, tmp_path):
        """严格模式：行是合法 JSON 但非对象 → 抛。"""
        path = tmp_path / "str.jsonl"
        path.write_text('"just a string"\n', encoding="utf-8")
        with pytest.raises(ValueError, match="不是 JSON 对象"):
            load_records(path, skip_invalid=False)

    def test_strict_mode_json_file_raises(self, tmp_path):
        """严格模式：.json 文件语法错直接抛 ValueError（含原异常上下文）。"""
        (tmp_path / "bad.json").write_text("{broken", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON 语法错误"):
            load_records(tmp_path, skip_invalid=False)

    def test_load_result_dataclass_defaults(self):
        """LoadResult 默认值与 total 统计。"""
        result = LoadResult()
        assert result.records == []
        assert result.failures == []
        assert result.total == 0
        result.add_failure("x.json", "boom")
        assert result.total == 1

    def test_records_are_normalized(self, tmp_path):
        """装载产出已是规范化记录（别名/金额已归一）。"""
        _write(
            tmp_path / "s.json",
            [{"招标编号": "N-1", "项目名称": "某项目", "预算金额": "1.2亿"}],
        )
        result = load_records(tmp_path)
        record = result.records[0]
        assert isinstance(record, AnnouncementRecord)
        assert record.budget == 12000.0
        assert record.fingerprint()
