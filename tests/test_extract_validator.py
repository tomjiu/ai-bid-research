"""src/extract.validator 模块单元测试（#601 批次 B 第 6 轮）。"""

import pytest

from src.extract import (
    REQUIRED_FIELDS,
    RECOMMENDED_FIELDS,
    validate_fields,
)


def _complete_fields() -> dict:
    """构造 12 字段全满的字段集。"""
    return {
        "bid_id": "V-1",
        "project_name": "智慧城市项目",
        "region": "浙江省 杭州市",
        "budget": 350.0,
        "publish_date": "2026-11-01",
        "deadline": "2026-11-20",
        "category": "服务",
        "purchaser": "某大数据局",
        "agency": "某代理",
        "winner": None,
        "source_url": "https://example.com/1",
        "requirements": ["ISO9001"],
    }


class TestValidateFields:
    """校验器行为面。"""

    def test_complete_fields_valid(self):
        """12 字段全满：valid + 命中率 11/12（winner 未开标为 None）。"""
        result = validate_fields(_complete_fields())
        assert result.valid is True
        assert result.missing_required == []
        assert result.hit_rate == pytest.approx(11 / 12)
        assert "winner" not in result.filled_fields
        assert len(result.filled_fields) == 11

    @pytest.mark.parametrize(
        "missing", ["bid_id", "project_name"]
    )
    def test_missing_required_invalid(self, missing):
        """缺任一必填字段 → invalid（拒收入库面）。"""
        fields = _complete_fields()
        fields[missing] = None
        result = validate_fields(fields)
        assert result.valid is False
        assert result.missing_required == [missing]

    def test_blank_string_counts_as_missing(self):
        """空白字符串视同缺失（不是「已填」）。"""
        fields = _complete_fields()
        fields["project_name"] = "   "
        result = validate_fields(fields)
        assert result.valid is False
        assert "project_name" in result.missing_required

    def test_missing_recommended_still_valid(self):
        """推荐字段缺失不拒收（公告可不写预算），仅进告警清单。"""
        fields = _complete_fields()
        fields["budget"] = None
        fields["publish_date"] = None
        result = validate_fields(fields)
        assert result.valid is True
        assert "budget" in result.missing_recommended
        assert "publish_date" in result.missing_recommended

    def test_empty_requirements_counts_as_missing(self):
        """空列表视同缺失（资格要求没抽到）。"""
        fields = _complete_fields()
        fields["requirements"] = []
        result = validate_fields(fields)
        assert "requirements" in result.missing_recommended

    def test_sparse_record_low_hit_rate(self):
        """稀疏记录（只有 bid_id+项目名）→ 命中率 2/12，valid。"""
        result = validate_fields(
            {"bid_id": "S-1", "project_name": "稀疏项目"}
        )
        assert result.valid is True
        assert result.hit_rate == pytest.approx(2 / 12)
        assert len(result.missing_recommended) == len(RECOMMENDED_FIELDS)

    def test_empty_fields_invalid(self):
        """全空字段 → invalid + 命中率 0。"""
        result = validate_fields({})
        assert result.valid is False
        assert set(result.missing_required) == set(REQUIRED_FIELDS)
        assert result.hit_rate == 0.0

    def test_zero_budget_is_filled(self):
        """预算 0 元是「已填」（合法值），不是缺失。"""
        fields = _complete_fields()
        fields["budget"] = 0.0
        result = validate_fields(fields)
        assert "budget" in result.filled_fields
        assert "budget" not in result.missing_recommended

    def test_constant_contracts(self):
        """契约常量：必填=2、推荐=5、合计口径与研究面一致。"""
        assert set(REQUIRED_FIELDS) == {"bid_id", "project_name"}
        assert len(RECOMMENDED_FIELDS) == 5
        assert set(REQUIRED_FIELDS).isdisjoint(RECOMMENDED_FIELDS)
