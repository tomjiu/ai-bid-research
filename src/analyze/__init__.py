"""分析面（#601 批次 C）——数据集加载与统计。

非生产链路——仅供研究，与 Rust bid 链路的边界见 docs/PYTHON-BOUNDARY.md。
分析面纯标准库实现（无 LLM/网络依赖）——离线可测，
统计口径在 docstring 中逐项声明（研究结论须可复算）。
"""

from src.analyze.dataset import BidDataset, load_dataset

__all__ = ["BidDataset", "load_dataset"]
