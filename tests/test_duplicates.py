"""近重复公告检测测试（#601 R79）。

直击三种真实形态：改包重发 / 多平台转发 / 标题微调（全半角、标点）。
性能纪律单列：2000 条唯一名必须在研究可接受时间内完成。
"""

from __future__ import annotations

import time

from src.analyze.dataset import AnalysisDataset
from src.analyze.duplicates import (
    charset_distance_bound,
    find_duplicate_clusters,
    is_similar,
    levenshtein,
    levenshtein_within,
    normalize_name,
    render_duplicates_markdown,
)


def _ds(*names):
    return AnalysisDataset(
        records=[
            {"bid_id": f"B-{i:03d}", "project_name": n}
            for i, n in enumerate(names)
        ]
    )


class TestNormalizeName:
    def test_punct_and_space_stripped(self):
        assert normalize_name("智慧城市，一期 建设") == "智慧城市一期建设"

    def test_fullwidth_to_halfwidth(self):
        # 全角字母/数字/括号 → 半角小写
        assert normalize_name("ＡＢＣ（２０２６）") == "abc2026"

    def test_chinese_difference_preserved(self):
        # 归一是保守的——「一期」「二期」必须仍不同
        assert normalize_name("智慧城市一期") != normalize_name("智慧城市二期")

    def test_empty_and_non_string(self):
        assert normalize_name("") == ""
        assert normalize_name(None) == ""
        assert normalize_name("   ") == ""

    def test_decoration_words_kept(self):
        # 不删词只删噪：地区前缀保留（删了会误合并不同区项目）
        assert normalize_name("北京市智慧交通项目") == "北京市智慧交通项目"


class TestLevenshtein:
    def test_classic(self):
        assert levenshtein("kitten", "sitting") == 3
        assert levenshtein("", "abc") == 3
        assert levenshtein("abc", "") == 3
        assert levenshtein("flaw", "lawn") == 2

    def test_chinese(self):
        assert levenshtein("智慧城市", "智慧城管") == 1

    def test_equal_is_zero_shortcut(self):
        assert levenshtein("同名字符串", "同名字符串") == 0


class TestIsSimilar:
    def test_exact_normalized_match(self):
        assert is_similar("智慧城市一期", "智慧城市一期")

    def test_repackage_suffix_hits(self):
        # 改包重发：加「（二次）」——归一删标点后差 2 字 → 8 字名容忍 0 步？
        # 8 字 * 0.12 = 0.96 → tol=0 → 不同。这正是比例自适应语义：
        # 短名不容忍编辑。用 20 字名验证容忍。
        a = "某某市智慧城市建设项目一期工程总承包"
        b = "某某市智慧城市建设项目一期工程总承包二次"
        assert is_similar(normalize_name(a), normalize_name(b))

    def test_length_prefilter_rejects(self):
        # 长度差远超容忍比例——O(1) 否决（不同编辑距离也判否）
        assert not is_similar("智慧城市", "智慧城市建设项目一期工程总承包施工")

    def test_charset_bound_prefilter_rejects(self):
        # 字符组成完全不同——可证明下界否决（避免进编辑距离）
        assert not is_similar("aaaaaaaaaa", "bbbbbbbbbb")

    def test_charset_bound_math(self):
        # 下界 ≥ max(独有字符数)——替换一次消两侧各一个
        sa, sb = frozenset("智慧城市采购"), frozenset("智慧城管采购")
        # 各自独有 1 字 → 下界 1
        assert charset_distance_bound(sa, sb) == 1
        assert charset_distance_bound(frozenset("abc"), frozenset("abc")) == 0

    def test_banded_dp_matches_full(self):
        # 带限早停版与完整版判定一致（等价性契约）
        cases = [
            ("kitten", "sitting", 3),
            ("kitten", "sitting", 2),
            ("智慧城市一期工程总承包", "智慧城市一期工程总承包二次", 2),
            ("智慧城市", "智慧城管", 0),
            ("abc", "abd", 1),
            ("", "ab", 1),
        ]
        for a, b, tol in cases:
            assert levenshtein_within(a, b, tol) == (
                levenshtein(a, b) <= tol
            ), f"{a!r} vs {b!r} @tol={tol} 不一致"

    def test_short_names_no_tolerance(self):
        # 短名（tol=0）下任何差异都不算重复——防误合并
        assert not is_similar("abc", "abd")


class TestFindDuplicateClusters:
    def test_empty_and_single(self):
        assert find_duplicate_clusters(AnalysisDataset())["clusters"] == []
        assert find_duplicate_clusters(_ds("唯一"))["clusters"] == []

    def test_repackage_cluster(self):
        payload = find_duplicate_clusters(
            _ds(
                "某某市智慧城市建设项目一期工程总承包",
                "某某市智慧城市建设项目一期工程总承包（二次）",
                "完全无关的另一个项目",
            )
        )
        assert len(payload["clusters"]) == 1
        assert payload["clusters"][0]["size"] == 2
        assert payload["records_in_clusters"] == 2
        assert payload["duplicate_rate"] == 2 / 3

    def test_multi_platform_same_name(self):
        # 多平台转发：不同 bid_id、同名 → 一簇
        payload = find_duplicate_clusters(
            _ds("某某区数据中心采购", "某某区数据中心采购", "其他项目A")
        )
        assert len(payload["clusters"]) == 1
        assert {m["bid_id"] for m in payload["clusters"][0]["members"]} == {
            "B-000",
            "B-001",
        }

    def test_transitive_closure(self):
        # A≈B、B≈C ⇒ {A,B,C}（传递闭包——并查集语义）
        base = "某某市新型基础设施建设项目工程"
        payload = find_duplicate_clusters(
            _ds(
                base,
                base + "二次",
                base + "三次",
            )
        )
        assert len(payload["clusters"]) == 1
        assert payload["clusters"][0]["size"] == 3

    def test_phase_names_form_family(self):
        # 语义边界如实记录：一期 vs 二期只差 1 字——与「加（二次）」
        # 同为 1-2 步编辑，按定义就是近重复。采购研究中它们本是
        # 同项目的不同阶段，聚为族正是研究者需要看到的信号。
        payload = find_duplicate_clusters(
            _ds("某某市智慧城市建设项目一期", "某某市智慧城市建设项目二期")
        )
        assert len(payload["clusters"]) == 1
        assert payload["clusters"][0]["size"] == 2

    def test_unrelated_projects_never_merge(self):
        # 防误合并底线：完全无关的项目绝不聚簇
        payload = find_duplicate_clusters(
            _ds("某某市智慧城市建设项目一期", "某某区农田水利灌溉工程")
        )
        assert payload["clusters"] == []

    def test_sorted_by_size_desc(self):
        payload = find_duplicate_clusters(
            _ds(
                "某某市新型基础设施建设项目工程",  # 簇1 ×3
                "某某市新型基础设施建设项目工程二次",
                "某某市新型基础设施建设项目工程三次",
                "某某区数据中心采购",  # 簇2 ×2
                "某某区数据中心采购（重新招标）",
                "独立项目不参与聚类",
            )
        )
        sizes = [c["size"] for c in payload["clusters"]]
        assert sizes == sorted(sizes, reverse=True)
        assert sizes[0] == 3

    def test_empty_names_excluded(self):
        payload = find_duplicate_clusters(_ds("", None, "正常项目"))
        assert payload["clusters"] == []

    def test_budget_exhausted_is_honest(self, monkeypatch):
        import src.analyze.duplicates as dup

        # 预算归零：任何 ≥2 成员的块桶都爆炸 → 跳桶 + 诚实标注
        monkeypatch.setattr(dup, "_MAX_PAIR_BUDGET", 0)
        payload = find_duplicate_clusters(
            _ds("某某市第1号办公设备采购", "某某市第2号办公设备采购")
        )
        assert payload["budget_exhausted"] is True


class TestRenderMarkdown:
    def test_no_duplicates_copy(self):
        md = render_duplicates_markdown(
            {"total": 5, "clusters": [], "budget_exhausted": False}
        )
        assert "未检出近重复" in md

    def test_cluster_table(self):
        md = render_duplicates_markdown(
            {
                "total": 3,
                "clusters": [
                    {
                        "size": 2,
                        "normalized": "某某区数据中心采购",
                        "members": [
                            {"bid_id": "A", "project_name": "x"},
                            {"bid_id": "B", "project_name": "x"},
                        ],
                    }
                ],
                "records_in_clusters": 2,
                "duplicate_rate": 2 / 3,
                "budget_exhausted": False,
            }
        )
        assert "近重复公告检测" in md
        assert "66.7%" in md
        assert "| 2 |" in md

    def test_budget_warning_shown(self):
        md = render_duplicates_markdown(
            {
                "total": 3,
                "clusters": [],
                "records_in_clusters": 0,
                "duplicate_rate": 0.0,
                "budget_exhausted": True,
            }
        )
        assert "预算耗尽" in md


class TestPerformanceContract:
    def test_batch_template_names_hit_budget_fast(self):
        # 2000 条同模板批量采购名（招投标真实形态：中段全同、编号
        # 互异）——块桶爆炸 → 预算截断，秒级返回 + 诚实标注，
        # 绝不无限精算（旧滑窗实现在此场景 200 万对全进 DP）。
        names = [
            f"某某市第{i}号办公设备批量采购项目{i:04d}"
            for i in range(2000)
        ]
        start = time.monotonic()
        payload = find_duplicate_clusters(_ds(*names))
        elapsed = time.monotonic() - start
        assert elapsed < 10.0, f"模板名场景耗时 {elapsed:.1f}s——预算未生效"
        assert payload["budget_exhausted"] is True  # 不装完成

    def test_diverse_names_complete_detection_fast(self):
        # 多样化真实名（互异词表组合）+ 5 对显式改包重发：
        # 候选极少 → 全量精算 → 完备检出，秒级，预算不耗尽
        regions = ["京津冀", "长三角", "珠三角", "成渝地区", "江淮地带"]
        domains = [
            "智慧交通枢纽", "绿色数据中心", "政务云平台", "雪亮工程",
            "城市大脑运营", "应急指挥调度", "智慧水务监测", "综合管廊",
        ]
        nouns = ["建设", "总承包", "施工", "监理", "勘察设计"]
        suffixes = ["一期", "二期", "三期", "四期", "五期"]
        names = []
        for r in regions:
            for d in domains:
                for n in nouns:
                    for s in suffixes:
                        names.append(f"{r}{d}{n}{s}")
        # 1000 条互异组合名
        assert len(names) == 1000
        # 插入 5 对显式改包重发（尾部加「二次」）
        repackage = [name + "（二次）" for name in names[:5]]
        all_names = names + repackage
        start = time.monotonic()
        payload = find_duplicate_clusters(_ds(*all_names))
        elapsed = time.monotonic() - start
        assert elapsed < 10.0, f"多样化场景耗时 {elapsed:.1f}s"
        assert payload["budget_exhausted"] is False
        # 完备性：5 对改包重发必须全部检出（漏检 = 块分块错误）
        assert payload["records_in_clusters"] >= 10
        assert len(payload["clusters"]) >= 5
