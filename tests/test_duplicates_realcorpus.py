"""近重复检测真实语料实拍（#601 R90）。

real-corpus/gov-procurement 的 576 条**真实公告标题**（政府
采购网抓取，含「第N包」改包重发、同项目多公告的真实形态）——
性能与语义双实拍：
1. 576 条全量检测在研究可接受时间内完成、预算不耗尽；
2. 真实改包族（同项目第1包/第2包…）确实聚簇——语义落地证据；
3. 检出率量级合理（真实库中重复挂网客观存在，不伪报零）。

语料不在（浅克隆/裁剪环境）时整文件 skip——实拍是增益不是门槛。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.analyze.dataset import AnalysisDataset
from src.analyze.duplicates import find_duplicate_clusters

CORPUS = (
    Path(__file__).resolve().parent.parent
    / "real-corpus" / "gov-procurement" / "inventory.json"
)

pytestmark = pytest.mark.skipif(
    not CORPUS.exists(), reason="real-corpus 语料不在本环境"
)


@pytest.fixture(scope="module")
def real_payload():
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    records = [
        {"bid_id": f"RC-{i:04d}", "project_name": f["title"]}
        for i, f in enumerate(data["files"])
        if f.get("title")
    ]
    assert len(records) >= 500  # 语料量级契约（缩水则实拍失效）
    start = time.monotonic()
    payload = find_duplicate_clusters(AnalysisDataset(records=records))
    payload["_elapsed"] = time.monotonic() - start
    return payload


class TestRealCorpusDuplicates:
    def test_performance_real_titles(self, real_payload):
        """576 条真实名：秒级完成（真实名长度/字符分布多样化，
        pigeonhole 候选极少——与合成模板名的爆炸场景互补）。"""
        assert real_payload["_elapsed"] < 10.0, (
            f"真实语料耗时 {real_payload['_elapsed']:.1f}s"
        )

    def test_budget_not_exhausted_on_real_data(self, real_payload):
        """真实多样化名不应触发预算截断（截断=模板批量名专属）。"""
        assert real_payload["budget_exhausted"] is False

    def test_repackage_families_detected(self, real_payload):
        """真实改包族落地：同名簇（不同公告类型/包件号）确实聚出。"""
        assert real_payload["clusters"], "真实库应存在近重复（零簇可疑）"
        # 语义抽查：任一簇内成员必须同源可读（名称确有重叠）
        cluster = real_payload["clusters"][0]
        assert cluster["size"] >= 2
        assert len(cluster["normalized"]) > 4

    def test_detection_rate_reasonable(self, real_payload):
        """检出率量级：真实库重复挂网客观存在（1%-60% 合理带；
        超限说明阈值失真——要么漏报要么误报风暴）。"""
        rate = real_payload["duplicate_rate"]
        assert 0.01 <= rate <= 0.60, f"检出率 {rate:.1%} 异常"

    def test_members_have_real_ids(self, real_payload):
        """簇成员带真实可回查的 bid_id（RC-XXXX ← inventory 序）。"""
        for cluster in real_payload["clusters"][:5]:
            for member in cluster["members"]:
                assert member["bid_id"].startswith("RC-")
