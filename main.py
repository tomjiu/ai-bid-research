#!/usr/bin/env python3
"""ai-bid-research —— AI 驱动的招投标研究工具（命令行入口）。

用法示例::

    # 生成单个招标项目的投标分析报告（分析数据来自 JSON 文件）
    python main.py report --bid-id ZJ-2026-001 --input analysis.json

    # 生成关键词竞争态势报告，并同时导出 HTML
    python main.py report --keyword 智慧城市 --days 30 --html

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

from src.llm.client import LLMClient
from src.llm.prompts import PromptTemplates
from src.report.generator import ReportGenerator

logger = logging.getLogger("ai-bid-research")


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

    # templates 子命令
    sub.add_parser(
        "templates", help="列出可用的提示词模板"
    )

    return parser


async def run_report(args: argparse.Namespace) -> int:
    """执行 report 子命令。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码。
    """
    generator = ReportGenerator(output_dir=args.output_dir)

    if args.keyword:
        report_path = await generator.generate_competition_report(
            args.keyword, days=args.days
        )
    elif args.bid_id:
        if args.input is None:
            print(
                "错误：--bid-id 模式需要 --input 指定分析数据 JSON 文件",
                file=sys.stderr,
            )
            return 2
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
        report_path = await generator.generate_bid_report(
            args.bid_id, analysis_data
        )
    else:
        print(
            "错误：请指定 --keyword 或 --bid-id + --input", file=sys.stderr
        )
        return 2

    print(f"报告已生成: {report_path}")
    if args.html:
        html_path = generator.export_html(report_path)
        print(f"HTML 已导出: {html_path}")
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
    if args.command == "templates":
        return run_templates()
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
