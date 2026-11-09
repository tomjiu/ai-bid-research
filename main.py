#!/usr/bin/env python3
"""ai-bid-research —— AI 驱动的招投标研究工具（命令行入口）。

非生产链路——仅供研究，与 Rust bid 链路的边界见 docs/PYTHON-BOUNDARY.md。

用法示例::

    # 导入项目清单到 SQLite（单个对象或对象数组）
    python main.py db --import bids.json

    # 查询与统计
    python main.py db --query 智慧城市 --days 30
    python main.py db --stats

    # 生成关键词竞争态势报告（自动接入 data/bids.db）并同时导出 HTML
    python main.py report --keyword 智慧城市 --days 30 --html

    # 生成单项目报告（分析数据来自 JSON 文件，或来自数据库）
    python main.py report --bid-id ZJ-2026-001 --input analysis.json
    python main.py report --bid-id ZJ-2026-001

    # 查看可用提示词模板
    python main.py templates
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

from src.llm.prompts import PromptTemplates
from src.report.generator import ReportGenerator
from src.storage.database import BidDatabase

logger = logging.getLogger("ai-bid-research")

#: 默认数据库路径（存在时 report 子命令自动接入）
DEFAULT_DB_PATH = Path("data/bids.db")


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        配置好的 ArgumentParser 实例。
    """
    parser = argparse.ArgumentParser(
        prog="ai-bid-research",
        description="AI 驱动的招投标研究工具：LLM 分析 + 报告生成",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="输出调试日志"
    )
    sub = parser.add_subparsers(dest="command", help="可用子命令")

    # report 子命令
    report = sub.add_parser(
        "report", help="生成投标研究报告（Markdown，可选导出 HTML）"
    )
    report.add_argument(
        "--bid-id",
        help="招标项目编号；与 --input 配合生成单项目投标分析报告",
    )
    report.add_argument(
        "--input",
        type=Path,
        help="单项目分析数据 JSON 文件路径（--bid-id 模式必填）",
    )
    report.add_argument(
        "--keyword",
        help="竞争态势检索关键词；生成近 N 天竞争态势报告",
    )
    report.add_argument(
        "--days",
        type=int,
        default=7,
        help="竞争态势回溯天数（默认 7）",
    )
    report.add_argument(
        "--html",
        action="store_true",
        help="报告生成后同时导出 HTML 版本",
    )
    report.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/reports"),
        help="报告输出目录（默认 output/reports）",
    )
    report.add_argument(
        "--db",
        type=Path,
        default=None,
        help=(
            "招标信息 SQLite 数据库路径；不指定时若默认路径"
            f" {DEFAULT_DB_PATH} 存在则自动接入"
        ),
    )

    # db 子命令
    db = sub.add_parser(
        "db", help="招标信息数据库管理（导入/统计）"
    )
    db.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"数据库路径（默认 {DEFAULT_DB_PATH}）",
    )
    db.add_argument(
        "--import",
        dest="import_file",
        type=Path,
        help="导入 JSON 项目清单（单个对象或对象数组）",
    )
    db.add_argument(
        "--stats", action="store_true", help="输出数据库统计概览"
    )
    db.add_argument(
        "--query",
        help="按关键词查询项目记录（可选，配合 --days）",
    )
    db.add_argument(
        "--days", type=int, default=None, help="查询回溯天数（配合 --query）"
    )

    # templates 子命令
    sub.add_parser(
        "templates", help="列出可用的提示词模板"
    )

    return parser


def _open_database(
    db_arg: Optional[Path], *, required: bool = False
) -> Optional[BidDatabase]:
    """打开数据库连接，处理默认路径探测。

    Args:
        db_arg: 命令行指定的数据库路径；``None`` 时探测默认路径。
        required: 为 ``True`` 时路径不存在即报错退出。

    Returns:
        数据库实例；未指定且默认路径不存在时返回 ``None``。
    """
    path = db_arg or (DEFAULT_DB_PATH if DEFAULT_DB_PATH.exists() else None)
    if path is None:
        if required:
            print("错误：数据库不存在，请先通过 db --import 导入数据", file=sys.stderr)
            raise SystemExit(2)
        return None
    return BidDatabase(path)


async def run_report(args: argparse.Namespace) -> int:
    """执行 report 子命令。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码。
    """
    db = _open_database(getattr(args, "db", None))
    generator = ReportGenerator(output_dir=args.output_dir, db=db)

    if args.keyword:
        report_path = await generator.generate_competition_report(
            args.keyword, days=args.days
        )
    elif args.bid_id:
        if args.input is not None:
            if not args.input.is_file():
                print(f"错误：分析数据文件不存在: {args.input}", file=sys.stderr)
                return 2
            try:
                analysis_data = json.loads(
                    args.input.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError as exc:
                print(f"错误：分析数据 JSON 解析失败: {exc}", file=sys.stderr)
                return 2
        else:
            # 无 --input：尝试从数据库取数
            if db is None:
                print(
                    "错误：--bid-id 需要 --input 指定分析数据，"
                    "或通过 --db 接入数据库",
                    file=sys.stderr,
                )
                return 2
            if db.get_bid(args.bid_id) is None:
                print(
                    f"错误：数据库中不存在招标编号: {args.bid_id}",
                    file=sys.stderr,
                )
                return 2
            analysis_data = None
        report_path = await generator.generate_bid_report(
            args.bid_id, analysis_data
        )
    else:
        print(
            "错误：请指定 --keyword 或 --bid-id", file=sys.stderr
        )
        return 2

    print(f"报告已生成: {report_path}")
    if args.html:
        html_path = generator.export_html(report_path)
        print(f"HTML 已导出: {html_path}")
    if db is not None:
        db.close()
    return 0


def run_db(args: argparse.Namespace) -> int:
    """执行 db 子命令：导入/查询/统计。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码。
    """
    db_path: Path = args.db
    creating = args.import_file is not None
    if not creating and not db_path.exists():
        print(f"错误：数据库不存在: {db_path}", file=sys.stderr)
        return 2

    with BidDatabase(db_path) as db:
        if args.import_file is not None:
            if not args.import_file.is_file():
                print(
                    f"错误：导入文件不存在: {args.import_file}", file=sys.stderr
                )
                return 2
            try:
                payload = json.loads(
                    args.import_file.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError as exc:
                print(f"错误：导入 JSON 解析失败: {exc}", file=sys.stderr)
                return 2
            bids = payload if isinstance(payload, list) else [payload]
            saved = db.import_bids(bids)
            print(f"已导入 {saved} 条项目记录 → {db_path}")

        if args.query:
            rows = db.query_bids(keyword=args.query, days=args.days)
            print(f"关键词「{args.query}」命中 {len(rows)} 条：")
            for row in rows:
                print(
                    f"  {row['publish_date'] or '????-??-??'} "
                    f"{row['bid_id']} {row['project_name']}"
                    f"（预算 {row['budget'] if row['budget'] is not None else '未知'}，"
                    f"中标人：{row['winner'] or '未开标'}）"
                )

        if args.stats or (args.import_file is None and not args.query):
            stats = db.stats()
            print(
                f"数据库统计：共 {stats['total']} 条项目，"
                f"其中 {stats['awarded']} 条已定中标人"
            )
    return 0


def run_templates() -> int:
    """执行 templates 子命令，打印模板清单。

    Returns:
        进程退出码（恒为 0）。
    """
    descriptions = {
        "bid_extraction": "从招标公告原文抽取结构化信息（JSON）",
        "bid_analysis": "单项目投标价值分析（Markdown 报告）",
        "competitor_analysis": "关键词领域竞争态势分析",
        "report_generation": "将分析数据整理为正式研究报告",
    }
    print("可用提示词模板：")
    for name, template in PromptTemplates.get_all_templates().items():
        print(f"  {name:<22} {descriptions.get(name, '')}")
        _ = template  # 模板函数本身通过 PromptTemplates.<name>() 调用
    print("\n调用方式：from src.llm.prompts import PromptTemplates")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """命令行入口。

    Args:
        argv: 命令行参数；缺省时读取 ``sys.argv[1:]``。

    Returns:
        进程退出码。
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "report":
        return asyncio.run(run_report(args))
    if args.command == "db":
        return run_db(args)
    if args.command == "templates":
        return run_templates()
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
