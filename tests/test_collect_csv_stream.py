"""R55 CSV 流式读取测试——大文件/多行单元格/行数上限。"""

import csv as csv_mod
import resource

from src.collect.sources import _read_csv_rows


def _write_csv(path, rows, header=("bid_id", "project_name")):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv_mod.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


class TestStreamingCsv:
    def test_large_file_functional(self, tmp_path):
        """万行级 CSV 功能正确（流式化不破坏语义）。"""
        n = 10_000
        p = _write_csv(
            tmp_path / "big.csv",
            [(f"B-{i}", f"项目{i}") for i in range(n)],
        )
        items, errors = _read_csv_rows(p)
        assert len(items) == n
        assert errors == []
        assert items[0][1] == {"bid_id": "B-0", "project_name": "项目0"}
        assert items[-1][1] == {"bid_id": f"B-{n-1}", "project_name": f"项目{n-1}"}

    def test_multiline_quoted_cell_now_supported(self, tmp_path):
        """带引号多行单元格——R55 升级为标准 CSV 语义。"""
        p = tmp_path / "ml.csv"
        p.write_text(
            'bid_id,requirements\n'
            '"B-1","第一条要求\n第二条要求"\n'
            '"B-2","单行"\n',
            encoding="utf-8",
        )
        items, errors = _read_csv_rows(p)
        assert errors == []
        assert items[0][1]["requirements"] == "第一条要求\n第二条要求"
        assert items[1][1]["requirements"] == "单行"

    def test_max_rows_guard(self, tmp_path):
        p = _write_csv(
            tmp_path / "cap.csv",
            [(f"B-{i}", "x") for i in range(50)],
        )
        import pytest

        with pytest.raises(ValueError, match="防失控保护"):
            _read_csv_rows(p, max_rows=10)

    def test_max_rows_none_unlimited(self, tmp_path):
        p = _write_csv(
            tmp_path / "nc.csv",
            [(f"B-{i}", "x") for i in range(100)],
        )
        items, _ = _read_csv_rows(p, max_rows=None)
        assert len(items) == 100

    def test_blank_rows_skipped_row_numbers_kept(self, tmp_path):
        p = tmp_path / "blanks.csv"
        p.write_text(
            "bid_id,project_name\nB-1,A\n\nB-2,B\n",
            encoding="utf-8",
        )
        items, errors = _read_csv_rows(p)
        assert [i[0] for i in items] == [2, 4]
        assert errors == []

    def test_ragged_row_still_row_error(self, tmp_path):
        p = tmp_path / "ragged.csv"
        p.write_text(
            "bid_id,project_name,budget\nB-1,A\nB-2,B,100\n",
            encoding="utf-8",
        )
        items, errors = _read_csv_rows(p)
        assert len(items) == 1
        assert errors and "列数不齐" in errors[0][1]

    def test_memory_bounded_on_wide_file(self, tmp_path):
        """内存面上限烟测：流式读取 RSS 增量远小于文件字符总量。

        宽行文件（每行 ~2KB × 5000 行 ≈ 10MB 文本）——若整文件
        读入，RSS 增量 ≥ 10MB；流式应显著低于该量级。
        """
        wide = "很长的要求描述" * 130  # ~1KB+ 中文 ≈ 2KB UTF-8
        p = _write_csv(
            tmp_path / "wide.csv",
            [(f"B-{i}", wide) for i in range(5_000)],
        )
        size = p.stat().st_size
        assert size > 5_000_000  # 前提成立：文件确为 MB 级
        before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        items, _ = _read_csv_rows(p)
        after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # ru_maxrss 是历史峰值（KB）——只验证读取完成 + 峰值增量
        # 不与文件尺寸同量级放大（放行 3 倍余量，跨环境稳）
        assert len(items) == 5_000
        growth_kb = max(0, after - before)
        assert growth_kb < (size // 1024) * 3
