"""招标信息 SQLite 存储层。

提供招标/中标项目记录的持久化与按关键词、时间窗口的查询能力。
"""

from src.storage.database import BidDatabase

__all__ = ["BidDatabase"]
