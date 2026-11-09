"""研究分析面（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

对入库的招标记录做描述性分析：预算分布、区域分布、时间趋势、
关键词频次、竞争密度——产出「分析数据集」供报告生成消费。
"""

from src.analyze.dataset import AnalysisDataset, load_dataset
from src.analyze.buyers import buyer_profiles
from src.analyze.density import competition_density
from src.analyze.keywords import common_bigrams, keyword_frequency
from src.analyze.compare import (
    build_comparison_payload,
    render_comparison_markdown,
)
from src.analyze.quality import field_quality
from src.analyze.report_data import build_analysis_payload, render_analysis_markdown
from src.analyze.stats import (
    budget_summary,
    date_range,
    monthly_trend,
    region_distribution,
)

__all__ = [
    "AnalysisDataset",
    "load_dataset",
    "budget_summary",
    "date_range",
    "monthly_trend",
    "region_distribution",
    "keyword_frequency",
    "common_bigrams",
    "competition_density",
    "buyer_profiles",
    "build_analysis_payload",
    "render_analysis_markdown",
    "field_quality",
    "build_comparison_payload",
    "render_comparison_markdown",
]
