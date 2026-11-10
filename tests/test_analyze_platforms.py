"""src/analyze.platforms 平台来源测试（#601 R98）。

覆盖域名归一（scheme 补齐/www 剥离/子域保留/大小写）、非 URL
不猜数、聚合口径（预算有值样本/最近发布日）、排序确定性、
跨平台转发信号（簇成员平台跨度判定）、二十一节渲染。
"""

from src.analyze import AnalysisDataset
from src.analyze.duplicates import find_duplicate_clusters
from src.analyze.platforms import (
    normalize_platform,
    platform_source_distribution,
)


def _rows(*rows):
    return [dict(r) for r in rows]


class TestNormalizePlatform:
    def test_scheme_variants_same_site(self):
        """http/https/无 scheme、www 与否——同一站点归一。"""
        assert (
            normalize_platform("https://www.ccgp.gov.cn/a")
            == normalize_platform("http://ccgp.gov.cn/b")
            == normalize_platform("www.ccgp.gov.cn/c")
            == "ccgp.gov.cn"
        )

    def test_case_and_whitespace(self):
        assert normalize_platform("  HTTPS://GGZY.Jiangsu.GOV.CN/x ") == (
            "ggzy.jiangsu.gov.cn"
        )

    def test_subdomain_preserved(self):
        """其余子域保留（不同入口不合并）。"""
        assert normalize_platform("https://zfcg.czt.zj.gov.cn/a") == (
            "zfcg.czt.zj.gov.cn"
        )

    def test_invalid_inputs_none(self):
        """空/None/纯路径/纯中文/无点内网名 → None（不猜数）。"""
        for bad in (
            None,
            "",
            "   ",
            "/only/path",
            "不是网址",
            "http://intranet/x",  # 无点内网名（urlparse 能解析但非域名形态）
        ):
            assert normalize_platform(bad) is None


class TestPlatformDistribution:
    def test_aggregation_fields(self):
        ds = AnalysisDataset(
            records=_rows(
                {
                    "project_name": "A",
                    "source_url": "https://www.ccgp.gov.cn/a",
                    "budget": 100.0,
                    "publish_date": "2026-01-05",
                },
                {
                    "project_name": "B",
                    "source_url": "ccgp.gov.cn/b",  # 裸域名
                    "budget": 300.0,
                    "publish_date": "2026-03-10",
                },
                {
                    "project_name": "C",
                    "source_url": "https://ggzy.jiangsu.gov.cn/c",
                    "budget": 50.0,
                    "publish_date": "2026-02-01",
                },
                {"project_name": "D", "source_url": None},
                {"project_name": "E", "source_url": ""},
            )
        )
        result = platform_source_distribution(ds)
        assert result["sample_count"] == 3
        assert result["missing_count"] == 2
        assert result["distinct_count"] == 2
        # 计数降序：ccgp.gov.cn=2 > ggzy.jiangsu.gov.cn=1
        top = result["platforms"][0]
        assert top["platform"] == "ccgp.gov.cn"
        assert top["count"] == 2
        assert top["budget_total"] == 400.0
        assert top["budget_mean"] == 200.0
        assert top["budget_sample_count"] == 2
        assert top["latest_date"] == "2026-03-10"

    def test_missing_budget_not_folded(self):
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "A", "source_url": "https://p.example/x"},
                {"project_name": "B", "source_url": "https://p.example/y"},
            )
        )
        entry = platform_source_distribution(ds)["platforms"][0]
        assert entry["budget_total"] is None
        assert entry["budget_sample_count"] == 0
        assert entry["latest_date"] is None

    def test_sorting_deterministic(self):
        """计数降序，并列按域名——确定性。"""
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "A", "source_url": "https://b.example/x"},
                {"project_name": "B", "source_url": "https://a.example/y"},
            )
        )
        names = [
            e["platform"] for e in platform_source_distribution(ds)["platforms"]
        ]
        assert names == ["a.example", "b.example"]

    def test_top_n_limit_distinct_full(self):
        ds = AnalysisDataset(
            records=_rows(
                *(
                    {"project_name": f"P{i}", "source_url": f"https://s{i}.example/x"}
                    for i in range(6)
                )
            )
        )
        result = platform_source_distribution(ds, top_n=3)
        assert len(result["platforms"]) == 3
        assert result["distinct_count"] == 6

    def test_empty_dataset(self):
        result = platform_source_distribution(AnalysisDataset(records=[]))
        assert result["sample_count"] == 0
        assert result["multi_platform"] == {
            "clusters": 0,
            "records": 0,
            "examples": [],
        }


class TestMultiPlatformSignal:
    def _dup_ds(self):
        """三平台转发的同名族 + 单平台同名族。"""
        return AnalysisDataset(
            records=_rows(
                {
                    "project_name": "某所运维服务项目",
                    "source_url": "https://www.ccgp.gov.cn/a1",
                },
                {
                    "project_name": "某所运维服务项目",
                    "source_url": "https://ggzy.jiangsu.gov.cn/a2",
                },
                {
                    "project_name": "某所运维服务项目",
                    "source_url": "https://www.qianlima.com/a3",
                },
                {
                    "project_name": "单平台族",
                    "source_url": "https://www.ccgp.gov.cn/b1",
                },
                {
                    "project_name": "单平台族",
                    "source_url": "https://ccgp.gov.cn/b2",  # 同平台不同写法
                },
            )
        )

    def test_multi_platform_clusters_detected(self):
        ds = self._dup_ds()
        clusters = find_duplicate_clusters(ds)
        result = platform_source_distribution(ds, duplicate_clusters=clusters)
        multi = result["multi_platform"]
        assert multi["clusters"] == 1
        assert multi["records"] == 3
        example = multi["examples"][0]
        assert example["size"] == 3
        assert example["platforms"] == [
            "ccgp.gov.cn",
            "ggzy.jiangsu.gov.cn",
            "qianlima.com",
        ]

    def test_single_platform_cluster_not_counted(self):
        """同平台簇（即使 www 与否不同写法）不算跨平台。"""
        ds = self._dup_ds()
        clusters = find_duplicate_clusters(ds)
        result = platform_source_distribution(ds, duplicate_clusters=clusters)
        # 单平台族（ccgp 两条）成簇但平台只有 1 个
        multi = result["multi_platform"]
        assert multi["clusters"] == 1  # 只有三平台族
        assert "单平台族" not in str(multi)

    def test_members_without_url_ignored(self):
        """簇内缺 URL 成员不参与判定——其余成员仍够 2 平台则算。"""
        ds = AnalysisDataset(
            records=_rows(
                {
                    "project_name": "转发族",
                    "source_url": "https://a.example/x",
                },
                {"project_name": "转发族", "source_url": None},
                {
                    "project_name": "转发族",
                    "source_url": "https://b.example/y",
                },
            )
        )
        clusters = find_duplicate_clusters(ds)
        multi = platform_source_distribution(
            ds, duplicate_clusters=clusters
        )["multi_platform"]
        assert multi["clusters"] == 1

    def test_all_members_without_url_not_counted(self):
        """全簇无 URL：无法判定平台跨度——不算跨平台（不猜数）。"""
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "无URL族", "source_url": None},
                {"project_name": "无URL族", "source_url": ""},
            )
        )
        clusters = find_duplicate_clusters(ds)
        multi = platform_source_distribution(
            ds, duplicate_clusters=clusters
        )["multi_platform"]
        assert multi["clusters"] == 0

    def test_no_clusters_passed_empty_signal(self):
        ds = self._dup_ds()
        result = platform_source_distribution(ds)  # 不传簇
        assert result["multi_platform"] == {
            "clusters": 0,
            "records": 0,
            "examples": [],
        }

    def test_json_serializable(self):
        import json

        ds = self._dup_ds()
        clusters = find_duplicate_clusters(ds)
        text = json.dumps(
            platform_source_distribution(ds, duplicate_clusters=clusters),
            ensure_ascii=False,
        )
        assert "ccgp.gov.cn" in text


class TestPlatformSectionRender:
    """二十一节渲染（payload→Markdown 全链）。"""

    def test_section_rendered_with_data(self):
        ds = AnalysisDataset(
            records=_rows(
                {
                    "project_name": "智慧水务平台",
                    "source_url": "https://www.ccgp.gov.cn/a",
                    "budget": 120.0,
                    "region": "江苏",
                    "publish_date": "2026-03-01",
                    "deadline": "2026-03-21",
                    "category": "服务",
                },
                {
                    "project_name": "智慧水务平台",  # 同名 → 成簇 + 跨平台
                    "source_url": "https://ggzy.jiangsu.gov.cn/b",
                    "budget": 120.0,
                    "region": "江苏",
                    "publish_date": "2026-03-02",
                },
            )
        )
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "## 二十一、平台来源分布" in md
        assert "ccgp.gov.cn" in md
        assert "跨平台转发信号" in md
        assert "ggzy.jiangsu.gov.cn" in md
        assert "[二十一、平台来源分布" in md  # 目录可导航

    def test_section_skipped_without_url(self):
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        ds = AnalysisDataset(
            records=_rows({"project_name": "A", "budget": 5.0})
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "二十一、平台来源分布" not in md
