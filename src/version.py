"""版本面（#601 R66）——单一权威版本号。

语义化版本：研究工具面（PYTHON-BOUNDARY 非生产链路）。
"""

__version__ = "0.2.0"


def version_banner() -> str:
    """人读版本横幅（--version 输出）。

    附带运行环境（Python/平台）——用户报障时一字不漏贴横幅
    即可定位环境面。
    """
    import platform
    import sys

    return (
        f"ai-bid-research {__version__}"
        f"（python {sys.version.split()[0]},"
        f" {platform.system().lower()}/{sys.platform}）"
    )
