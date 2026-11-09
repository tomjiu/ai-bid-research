#!/usr/bin/env python3
"""ai-bid-research —— AI 驱动的招投标研究工具（命令行入口）。

非生产链路——仅供研究，与 Rust bid 链路的边界见 docs/PYTHON-BOUNDARY.md。

用法示例::

    # 从本地源采集公告（JSON/JSONL 文件或目录）→ 规范化 → 去重 → 入库
    python main.py collect --source announcements/ --dry-run
    python main.py collect --source announcements/ --db data/bids.db

    # 公告原文抽取（.txt 文件/目录 → raw 暂存 → 规则/LLM 抽取 → 入库）
    python main.py extract --source raw-announcements/ --mode rule
    python main.py extract --source notices/ --mode api --dry-run
    python main.py extract --mode api --limit 20   # 只重试库内 pending

    # 数据分析（五维统计 → 离线 Markdown 报告，可选 HTML）
    python main.py analyze --db data/bids.db
    python main.py analyze --db data/bids.db --keyword 智慧城市 --days 90 --html

    # 研究管道：采集→抽取→分析→报告一条命令
    python main.py pipeline --announcements ann/ --raw-texts raw/ --db data/bids.db
    python main.py pipeline --announcements ann/ --dry-run   # 全链预演零副作用

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
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from src.analyze import (
    compute_stats,
    format_stats_markdown,
    load_dataset,
    save_analysis_report,
)
from src.collect import dedupe_records, load_records
from src.collect.sources import SourceError
from src.extract import (
    RuleExtractor,
    load_raw_texts,
    run_extraction,
)
from src.extract.runner import resolve_raw_files
from src.llm.client import LLMClient
from src.llm.prompts import PromptTemplates
from src.pipeline.runner import Pipeline
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

    # collect 子命令（#601 批次 A：采集面）
    collect = sub.add_parser(
        "collect",
        help="从本地源采集公告（JSON/JSONL）→ 规范化 → 去重 → 入库",
    )
    collect.add_argument(
        "--source",
        type=Path,
        required=True,
        help=(
            "公告源路径：.json/.jsonl 文件，或包含它们的目录"
            "（目录源按文件名排序装载）"
        ),
    )
    collect.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"目标数据库路径（默认 {DEFAULT_DB_PATH}）",
    )
    collect.add_argument(
        "--dry-run",
        action="store_true",
        help="演练模式：装载+去重+打印报告，但不写库",
    )
    collect.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：遇到坏文件/坏记录即中止（默认登记后继续）",
    )

    # extract 子命令（#601 批次 B：抽取面）
    extract = sub.add_parser(
        "extract",
        help="公告原文抽取（.txt → raw 暂存 → 规则/LLM → 入库）",
    )
    extract.add_argument(
        "--source",
        type=Path,
        default=None,
        help=(
            "公告原文源：.txt 文件或目录（缺省时只处理库内 pending，"
            "适用于失败件重试）"
        ),
    )
    extract.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"目标数据库路径（默认 {DEFAULT_DB_PATH}）",
    )
    extract.add_argument(
        "--mode",
        choices=("rule", "api"),
        default="rule",
        help=(
            "抽取引擎：rule 离线正则基线（默认，无网络依赖）；"
            "api 走 LLM（需 DEEPSEEK_API_KEY/OPENAI_API_KEY）"
        ),
    )
    extract.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多处理条数（缺省全部 pending）",
    )
    extract.add_argument(
        "--dry-run",
        action="store_true",
        help="演练模式：装载+抽取+打印报告，但不写库不改状态",
    )

    # analyze 子命令（#601 批次 C：分析面）
    analyze = sub.add_parser(
        "analyze",
        help="五维统计分析（金额/区域/趋势/关键词/竞争）→ 离线 Markdown 报告",
    )
    analyze.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"数据源数据库路径（默认 {DEFAULT_DB_PATH}）",
    )
    analyze.add_argument(
        "--keyword",
        default=None,
        help="项目名/编号过滤（可选）",
    )
    analyze.add_argument(
        "--days",
        type=int,
        default=None,
        help="只统计近 N 天发布的记录（可选）",
    )
    analyze.add_argument(
        "--region",
        default=None,
        help="地区子串过滤（可选，如 杭州）",
    )
    analyze.add_argument(
        "--title",
        default="招标数据分析报告",
        help="报告标题",
    )
    analyze.add_argument(
        "--html",
        action="store_true",
        help="同时导出 HTML 版本",
    )
    analyze.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/reports"),
        help=f"报告输出目录（默认 output/reports）",
    )

    # pipeline 子命令（#601 批次 D：管道整合）
    pipeline = sub.add_parser(
        "pipeline",
        help="研究管道：采集→抽取→分析→报告一条命令",
    )
    pipeline.add_argument(
        "--announcements",
        type=Path,
        default=None,
        help="结构化公告源：.json/.jsonl 文件或目录（collect 阶段）",
    )
    pipeline.add_argument(
        "--raw-texts",
        type=Path,
        default=None,
        help="公告原文源：.txt 文件或目录（extract 阶段）",
    )
    pipeline.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"研究工作区数据库路径（默认 {DEFAULT_DB_PATH}）",
    )
    pipeline.add_argument(
        "--keyword",
        default=None,
        help="analyze 数据集过滤：项目名/编号关键词",
    )
    pipeline.add_argument(
        "--days",
        type=int,
        default=None,
        help="analyze 数据集过滤：只统计近 N 天发布",
    )
    pipeline.add_argument(
        "--region",
        default=None,
        help="analyze 数据集过滤：地区子串",
    )
    pipeline.add_argument(
        "--title",
        default="招标数据分析报告",
        help="报告标题",
    )
    pipeline.add_argument(
        "--html",
        action="store_true",
        help="报告同时导出 HTML",
    )
    pipeline.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/reports"),
        help="报告输出目录（默认 output/reports）",
    )
    pipeline.add_argument(
        "--dry-run",
        action="store_true",
        help="全链预演：各阶段只统计将做什么，零副作用",
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


def run_collect(args: argparse.Namespace) -> int:
    """执行 collect 子命令：装载 → 去重 → 入库。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码（0 正常；2 源不可读/严格模式下遇到坏数据）。
    """
    try:
        loaded = load_records(args.source, skip_invalid=not args.strict)
    except (SourceError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    deduped = dedupe_records(loaded.records)

    print(f"源装载：读取 {loaded.files_read} 个文件，"
          f"成功 {len(loaded.records)} 条，失败 {len(loaded.failures)} 条")
    for failure in loaded.failures:
        print(f"  ✗ {failure['origin']}: {failure['error']}")
    print(f"去重：去除 {deduped.removed} 条重复"
          f"（bid_id {deduped.by_bid_id} / 链接 {deduped.by_source_url}"
          f" / 指纹 {deduped.by_fingerprint}），"
          f"待入库 {len(deduped.unique)} 条")
    for dup in deduped.duplicates:
        print(f"  ≈ {dup['bid_id']} 与 {dup['duplicate_of']} 同件（{dup['reason']}）")

    if args.dry_run:
        print("演练模式：未写库（--dry-run）")
        return 0

    with BidDatabase(args.db) as db:
        saved = db.import_bids([r.to_bid_row() for r in deduped.unique])
    print(f"已入库 {saved} 条 → {args.db}")
    return 0


async def run_extract(args: argparse.Namespace) -> int:
    """执行 extract 子命令：原文装载 → 抽取 → 入库/降级。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码（0 正常含失败件降级——它们保持 pending 等重试；
        2 源不可读 / api 模式缺密钥）。
    """
    if args.mode == "api" and not _has_api_key():
        print(
            "错误：api 模式需要 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量",
            file=sys.stderr,
        )
        return 2

    with BidDatabase(args.db) as db:
        if args.source is not None:
            try:
                resolve_raw_files(args.source)
            except SourceError as exc:
                print(f"错误：{exc}", file=sys.stderr)
                return 2
            load_stats = load_raw_texts(args.source, db)
            print(
                f"原文装载：读取 {load_stats.files_read} 个文件，"
                f"新入 {load_stats.saved} 条，"
                f"重复跳过 {load_stats.duplicates} 条"
            )
            for failure in load_stats.failures:
                print(f"  ✗ {failure['origin']}: {failure['error']}")

        if args.mode == "api":
            extractor = _build_llm_extractor()
            if extractor is None:
                print(
                    "错误：api 模式需要 DEEPSEEK_API_KEY 或 OPENAI_API_KEY",
                    file=sys.stderr,
                )
                return 2
        else:
            extractor = RuleExtractor()

        def _print_outcome(item: dict, outcome) -> None:
            if outcome.ok:
                print(
                    f"  ✓ {item['source']} → {outcome.record.bid_id}"
                    f"（{len(outcome.payload_fields)} 字段）"
                )
            else:
                print(f"  ✗ {item['source']}: {outcome.error}")

        stats = await run_extraction(
            db,
            extractor,
            limit=args.limit,
            dry_run=args.dry_run,
            on_outcome=_print_outcome,
        )

        mode_label = "规则基线" if stats.mode == "rule" else "LLM"
        print(
            f"抽取完成（{mode_label}）：处理 {stats.processed} 条，"
            f"成功 {stats.extracted} 条，失败 {stats.failed} 条"
            f"（失败件保持 pending 可重试）"
        )
        raw_stats = db.raw_stats()
        print(
            f"raw 暂存面：共 {raw_stats['total']} 条，"
            f"待抽取 {raw_stats['pending']} 条，"
            f"已抽取 {raw_stats['extracted']} 条"
        )
        if args.dry_run:
            print("演练模式：未写库（--dry-run）")
    return 0


def _has_api_key() -> bool:
    """判断环境是否配了任一 LLM 密钥（api 模式门）。"""
    return bool(
        os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    )


def _build_llm_extractor():
    """构建 LLM 抽取引擎（密钥缺失时返回 None）。"""
    if not _has_api_key():
        return None
    from src.extract import LLMExtractor

    return LLMExtractor(LLMClient())


def run_analyze(args: argparse.Namespace) -> int:
    """执行 analyze 子命令：数据集 → 五维统计 → 离线 Markdown 报告。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码（0 正常；2 数据库不存在/空数据集）。
    """
    db_path: Path = args.db
    if not db_path.exists():
        print(f"错误：数据库不存在: {db_path}", file=sys.stderr)
        return 2

    from src.report.generator import ReportGenerator

    with BidDatabase(db_path) as db:
        ds = load_dataset(
            db, keyword=args.keyword, days=args.days, region=args.region
        )
        if ds.total == 0:
            print(
                "错误：过滤后数据集为空——无样本可统计"
                "（检查 --keyword/--days/--region 或先导入数据）",
                file=sys.stderr,
            )
            return 2
        stats = compute_stats(ds)

    filters = []
    if args.keyword:
        filters.append(f"关键词「{args.keyword}」")
    if args.days:
        filters.append(f"近 {args.days} 天")
    if args.region:
        filters.append(f"地区含「{args.region}」")
    filter_note = f"，过滤条件：{' + '.join(filters)}" if filters else ""
    print(
        f"数据集：{ds.total} 条项目（其中已定标 {ds.awarded} 条）{filter_note}"
    )

    markdown = format_stats_markdown(stats, title=args.title)
    generator = ReportGenerator(
        output_dir=args.output_dir, llm_client=None
    )
    result = save_analysis_report(
        generator, markdown, prefix="analysis", html=args.html
    )
    print(f"分析报告已生成: {result['markdown']}")
    if result["html"]:
        print(f"HTML 已导出: {result['html']}")
    return 0


def run_pipeline(args: argparse.Namespace) -> int:
    """执行 pipeline 子命令：四阶段研究管道。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码（0 全部阶段成功；1 存在失败阶段；2 数据库不存在）。
    """
    db_path: Path = args.db
    if not db_path.exists() and not (
        args.announcements or args.raw_texts or args.dry_run
    ):
        # 无源输入且库不存在——不可能产出任何数据
        print(
            f"错误：数据库不存在且未指定任何源: {db_path}",
            file=sys.stderr,
        )
        return 2

    with BidDatabase(db_path) as db:
        pipeline = Pipeline(db, output_dir=args.output_dir)
        run = pipeline.run(
            announcements=args.announcements,
            raw_texts=args.raw_texts,
            keyword=args.keyword,
            days=args.days,
            region=args.region,
            title=args.title,
            html=args.html,
            dry_run=args.dry_run,
        )

    print(run.format_summary())
    for stage in run.stages:
        summary = stage.summary
        if stage.name == "collect":
            print(
                f"    collect：读取 {summary.get('files_read', 0)} 文件，"
                f"新增 {summary.get('new', 0)}，"
                f"更新 {summary.get('update', 0)}，"
                f"重复跳过 {summary.get('skip_duplicate', 0)}"
            )
        elif stage.name == "extract":
            print(
                f"    extract：读取 {summary.get('files_read', 0)} 文件，"
                f"新入 {summary.get('saved', 0)}，"
                f"处理 {summary.get('processed', 0)}，"
                f"成功 {summary.get('extracted', 0)}，"
                f"失败 {summary.get('failed', 0)}（保持 pending 可重试）"
            )
        elif stage.name == "analyze":
            if stage.ok:
                print(
                    f"    analyze：数据集 {summary.get('total', 0)} 条"
                    f"（已定标 {summary.get('awarded', 0)}）"
                )
        elif stage.name == "report":
            if stage.ok and summary.get("markdown"):
                print(f"    report：{summary['markdown']}")
                if summary.get("html"):
                    print(f"    report HTML：{summary['html']}")
    return 0 if run.all_ok else 1


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

    try:
        if args.command == "report":
            return asyncio.run(run_report(args))
        if args.command == "collect":
            return run_collect(args)
        if args.command == "extract":
            return asyncio.run(run_extract(args))
        if args.command == "analyze":
            return run_analyze(args)
        if args.command == "pipeline":
            return run_pipeline(args)
        if args.command == "db":
            return run_db(args)
        if args.command == "templates":
            return run_templates()
    except BrokenPipeError:
        # 管道下游提前关闭（grep -q / head）——输出已送达，正常退出
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
