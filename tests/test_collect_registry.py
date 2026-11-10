"""src/collect.sources 读取器注册表测试（#601 R32）。

覆盖研究面扩展点：注册新扩展名后目录源/单文件源自动识别、
覆盖式重注册、非法注册拒绝、受支持扩展名单点派生。
"""

import pytest

from src.collect import (
    SourceError,
    load_records,
    register_source_reader,
    supported_suffixes,
)
from src.collect import sources as sources_mod
from src.collect.sources import resolve_source_files


def _tsv_reader(path):
    """测试用 TSV 读取器（签名同 _read_jsonl_items）。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    items, errors = [], []
    for lineno, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        row = line.split("\t")
        if len(row) != len(header):
            errors.append((lineno, "列数不齐"))
            continue
        items.append(
            (lineno, {k: (v or None) for k, v in zip(header, row)})
        )
    return items, errors


@pytest.fixture
def clean_registry():
    """测试后恢复注册表原状（避免污染其他测试）。"""
    saved = dict(sources_mod._ROW_READERS)
    yield sources_mod
    sources_mod._ROW_READERS.clear()
    sources_mod._ROW_READERS.update(saved)


class TestRegistryDefaults:
    """默认注册面。"""

    def test_default_suffixes_sorted(self):
        """默认受支持扩展名：.json + 内置行式读取器，排序确定性。"""
        assert supported_suffixes() == (".csv", ".json", ".jsonl")

    def test_default_dispatch_unchanged(self, tmp_path):
        """注册表化后默认分发行为不变（CSV 正常装载）。"""
        path = tmp_path / "b.csv"
        path.write_text(
            "bid_id,project_name\nR32-1,某项目\n", encoding="utf-8"
        )
        result = load_records(path)
        assert result.failures == []
        assert result.records[0].bid_id == "R32-1"


class TestRegisterExtension:
    """注册扩展面。"""

    def test_register_new_suffix_directory_pickup(
        self, tmp_path, clean_registry
    ):
        """注册 .tsv 后：目录源自动收集该扩展名并走自定义读取器。"""
        register_source_reader(".tsv", _tsv_reader)
        path = tmp_path / "data.tsv"
        path.write_text(
            "bid_id\tproject_name\nT-1\tTSV 源项目\n", encoding="utf-8"
        )
        result = load_records(tmp_path)
        assert result.failures == []
        assert result.records[0].project_name == "TSV 源项目"
        assert ".tsv" in supported_suffixes()

    def test_register_single_file_dispatch(self, tmp_path, clean_registry):
        """注册 .tsv 后：单文件源直接分发。"""
        register_source_reader(".tsv", _tsv_reader)
        path = tmp_path / "one.tsv"
        path.write_text(
            "bid_id\tproject_name\nT-2\t单文件\n", encoding="utf-8"
        )
        result = load_records(path)
        assert result.records[0].bid_id == "T-2"

    def test_register_uppercase_suffix_normalized(self, clean_registry):
        """扩展名大小写归一：.TSV → .tsv。"""
        register_source_reader(".TSV", _tsv_reader)
        assert ".tsv" in supported_suffixes()

    def test_reregister_overrides_builtin(self, tmp_path, clean_registry):
        """重复注册后注册覆盖前注册（研究脚本可替换内置实现）。"""
        path = tmp_path / "b.csv"
        path.write_text(
            "bid_id,project_name\nO-1,原实现\n", encoding="utf-8"
        )
        marker = []

        def _custom(path):
            marker.append(path.name)
            return [(2, {"bid_id": "O-1", "project_name": "覆盖实现"})], []

        register_source_reader(".csv", _custom)
        result = load_records(path)
        assert result.records[0].project_name == "覆盖实现"
        assert marker == ["b.csv"]

    def test_registered_suffix_in_unknown_error(self, tmp_path, clean_registry):
        """注册 .tsv 后：未知扩展名报错信息包含全部受支持类型。"""
        register_source_reader(".tsv", _tsv_reader)
        path = tmp_path / "data.xlsx"
        path.write_text("x", encoding="utf-8")
        with pytest.raises(SourceError, match=r"\.tsv"):
            resolve_source_files(path)


class TestRegisterValidation:
    """注册入参校验。"""

    def test_suffix_without_dot_rejected(self):
        with pytest.raises(ValueError, match="须以 . 开头"):
            register_source_reader("csv", _tsv_reader)

    def test_non_callable_reader_rejected(self):
        with pytest.raises(ValueError, match="不可调用"):
            register_source_reader(".tsv", "not-a-function")
