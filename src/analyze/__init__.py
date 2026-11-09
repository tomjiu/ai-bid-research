"""研究分析面（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

对入库的招标记录做描述性分析：预算分布、区域分布、时间趋势、
关键词频次、竞争密度——产出「分析数据集」供报告生成消费。
"""

from src.analyze.dataset import AnalysisDataset, load_dataset

__all__ = [
    "AnalysisDataset",
    "load_dataset",
]
