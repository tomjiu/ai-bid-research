"""响应窗口期分析（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R95：公告发布日 → 投标截止日的**响应窗口**——采购人给投标人
留了多少准备时间。全部为**描述性统计**（分位数为最近邻秩位
口径，同 ``stats._nearest_rank``——不引第三方库）：

- 日期缺失/不可解析的记录不参与分布（``missing_count`` 如实
  携带，缺失不折零）；
- 截止早于发布（窗口 < 0）是**数据问题**而非业务信号——计入
  ``invalid_count`` 不进分布（揭示归十七节语义审计，本节不
  重复挂账）；
- 「短窗」（< ``SHORT_WINDOW_DAYS`` 日）是**供人工复核的研究
  提示，不是违规认定**：公开招标法定最短 20 日的起算点是
  「招标文件开始发出之日」（招标投标法第二十四条），公告
  发布日通常晚于或等于该日——本节以发布日近似，**偏短估计**。
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.analyze.dataset import AnalysisDataset

#: 短窗提示线（日）。研究经验口径：公开招标法定最短 20 日
#: （起算点为招标文件发出日——本节以公告发布日近似，见模块
#: docstring；竞争性磋商/询价等方式法定期限更短，故本线只作
#: 复核提示不作合规判定）。
SHORT_WINDOW_DAYS = 20


def _parse_date(value: Any) -> Optional[datetime]:
    """解析 YYYY-MM-DD 日期；失败返回 None（口径同 dataset._parse_date）。"""
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _nearest_rank(sorted_values: List[float], q: float) -> Optional[float]:
    """最近邻秩位分位（q∈(0,1]）；空序列返回 None（口径同 stats）。"""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(q * len(sorted_values)))
    return sorted_values[rank - 1]


def response_windows(
    dataset: AnalysisDataset,
    *,
    short_window_days: int = SHORT_WINDOW_DAYS,
    top_n: int = 5,
) -> Dict[str, Any]:
    """响应窗口分布（发布日→截止日，天）。

    Args:
        dataset: 分析数据集。
        short_window_days: 短窗提示线（日，严格小于才计短窗）。
        top_n: 短窗示例清单条数上限。

    Returns:
        JSON 可序列化的分布字典：

        - ``sample_count`` / ``missing_count`` / ``invalid_count``：
          有效样本 / 缺任一日期 / 截止早于发布（倒挂）——三数
          之和为总记录数（口径可核对）；
        - ``median_days`` / ``p25_days`` / ``p75_days`` /
          ``min_days`` / ``max_days``：分布统计（无有效样本时
          为 ``None``，不猜数）；
        - ``short_window_days``：提示线原样携带（口径可追溯）；
        - ``short_window_count`` / ``short_window_rate``：短窗
          条数与占比（占比 = 短窗 / 有效样本；无样本为 ``None``）；
        - ``short_window_examples``：最紧迫短窗 Top N（窗口升序、
          并列按项目名——确定性），每项含项目名/窗口天数/
          区域/发布日/截止日。
    """
    windows: List[int] = []
    missing = 0
    invalid = 0
    short_examples: List[Dict[str, Any]] = []

    for record in dataset.records:
        publish = _parse_date(record.get("publish_date"))
        deadline = _parse_date(record.get("deadline"))
        if publish is None or deadline is None:
            missing += 1
            continue  # 缺日期不猜数
        window_days = (deadline - publish).days
        if window_days < 0:
            invalid += 1
            continue  # 倒挂是数据问题（十七节揭示），不进分布
        windows.append(window_days)
        if window_days < short_window_days:
            short_examples.append(
                {
                    "project_name": str(record.get("project_name") or "").strip(),
                    "window_days": window_days,
                    "region": str(record.get("region") or "").strip() or None,
                    "publish_date": str(record.get("publish_date") or "")[:10],
                    "deadline": str(record.get("deadline") or "")[:10],
                }
            )

    windows.sort()
    sample_count = len(windows)
    short_count = len(short_examples)
    short_examples.sort(
        key=lambda item: (item["window_days"], item["project_name"])
    )

    return {
        "sample_count": sample_count,
        "missing_count": missing,
        "invalid_count": invalid,
        "median_days": _nearest_rank(windows, 0.50),
        "p25_days": _nearest_rank(windows, 0.25),
        "p75_days": _nearest_rank(windows, 0.75),
        "min_days": windows[0] if windows else None,
        "max_days": windows[-1] if windows else None,
        "short_window_days": short_window_days,
        "short_window_count": short_count,
        "short_window_rate": (
            short_count / sample_count if sample_count else None
        ),
        "short_window_examples": short_examples[:top_n],
    }
