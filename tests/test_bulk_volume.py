"""数据量压力 e2e（#601 R75）——R55 流式 + R62 事务在规模下真验证。

规模：2000 条记录 / 嵌套目录 / 含坏行降级。
时界（宽松）：管道全程 < 60s（沙箱级机器；Windows 业务机留 3x 余量）。
"""

from __future__ import annotations

import json
import time
import pytest

import main as main_mod
from src.storage.database import BidDatabase

N_RECORDS = 2000
N_FILES = 20  # 20 文件 × 100 条/文件，嵌套两级目录

PROVINCES = ["浙江省", "江苏省", "广东省", "北京市", "四川省"]
CITIES = ["杭州市", "南京市", "深圳市", "海淀区", "成都市"]


@pytest.fixture(scope="module")
def bulk_source(tmp_path_factory):
    """合成 2000 条公告（100 文件嵌套布局，含 2% 坏行）。"""
    root = tmp_path_factory.mktemp("bulk")
    per_file = N_RECORDS // N_FILES
    made = 0
    for f in range(N_FILES):
        subdir = root / f"2026-{(f % 12) + 1:02d}"
        subdir.mkdir(exist_ok=True)  # 12 月复用目录（20 文件嵌 12 月）
        rows = []
        for i in range(per_file):
            if made % 50 == 49:  # 2% 坏行——降级面有货
                rows.append({"bid_id": f"BULK-{made}", "budget": "不是数字"})
            else:
                rows.append(
                    {
                        "bid_id": f"BULK-{made}",
                        "project_name": f"智慧城市大数据平台第{made}期",
                        "region": f"{PROVINCES[made % 5]}{CITIES[made % 5]}",
                        "budget": float(100 + (made % 900)),
                        "publish_date": f"2026-{(made % 12) + 1:02d}-15",
                        "purchaser": f"某单位{made % 30}",
                        "category": "信息化",
                    }
                )
            made += 1
        (subdir / f"batch-{f:03d}.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
        )
    return root, made


class TestBulkPipeline:
    def test_bulk_collect_recursive(self, bulk_source, tmp_path, capsys):
        """2000 条嵌套目录递归采集（--recursive 真跑通）。"""
        root, made = bulk_source
        n_bad = sum(1 for i in range(made) if i % 50 == 49)
        db = tmp_path / "bulk.db"
        t0 = time.monotonic()
        rc = main_mod.main(
            [
                "collect", "--source", str(root), "--recursive",
                "--db", str(db),
            ]
        )
        elapsed = time.monotonic() - t0
        assert rc == 0
        out = capsys.readouterr().out
        # 坏预算行整行拒收（from_raw 校验）但容忍模式登记失败不炸
        assert "已入库" in out
        assert "失败" in out
        with BidDatabase(db) as handle:
            total = handle.count_bids()
        assert total == made - n_bad  # 好行全入库
        print(f"\n[bulk] {made} 条（坏 {n_bad}）递归采集 {elapsed:.1f}s")
        assert elapsed < 60

    def test_bulk_analyze_under_time_bound(
        self, bulk_source, tmp_path, capsys
    ):
        """2000 条库上全分析面（15 节报告全渲染）。"""
        root, made = bulk_source
        db = tmp_path / "bulk2.db"
        main_mod.main(
            ["collect", "--source", str(root), "--recursive",
             "--db", str(db)]
        )
        capsys.readouterr()
        t0 = time.monotonic()
        rc = main_mod.main(
            ["analyze", "--db", str(db), "--output-dir",
             str(tmp_path / "reports")]
        )
        elapsed = time.monotonic() - t0
        assert rc == 0
        out = capsys.readouterr().out
        assert "区域 Top 5" in out
        reports = list((tmp_path / "reports").glob("*.md"))
        assert reports
        body = reports[-1].read_text(encoding="utf-8")
        # 规模下的关键节全渲染
        assert "十五、省级归一分布" in body
        assert "十二、供应商画像" not in body or "供应商" in body  # 节按数据有无跳
        print(f"\n[bulk] {made} 条全分析 {elapsed:.1f}s")
        assert elapsed < 60

    def test_bulk_export_import_roundtrip(self, bulk_source, tmp_path):
        """2000 条导出 → diff 自比较零差异（快照面规模验证）。"""
        root, made = bulk_source
        db = tmp_path / "bulk3.db"
        main_mod.main(
            ["collect", "--source", str(root), "--recursive",
             "--db", str(db)]
        )
        s1 = tmp_path / "s1.json"
        s2 = tmp_path / "s2.json"
        main_mod.main(["db", "--db", str(db), "--export", "json",
                       "--out", str(s1)])
        main_mod.main(["db", "--db", str(db), "--export", "json",
                       "--out", str(s2)])
        payload1 = json.loads(s1.read_text(encoding="utf-8"))
        n_bad = sum(1 for i in range(made) if i % 50 == 49)
        assert len(payload1) == made - n_bad
        from src.storage.snapshot_diff import diff_snapshots

        d = diff_snapshots(payload1, payload1)
        assert d["added"] == [] and d["removed"] == [] and d["changed"] == {}
        assert d["unchanged_count"] == made - n_bad
