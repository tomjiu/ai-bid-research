#!/usr/bin/env python3
"""ai-bid-research —— AI 驱动的招投标研究工具（命令行入口）。

非生产链路——仅供研究，与 Rust bid 链路的边界见 docs/PYTHON-BOUNDARY.md。

用法示例::

    # 从本地源采集公告（JSON/JSONL 文件或目录）→ 规范化 → 去重 → 入库
    python main.py collect --source announcements/ --dry-run
    python main.py collect --source announcements/ --db data/bids.db

    # 结构化抽取：公告原文 → LLM → 合并入库（失败自动登记 pending 可重试）
    python main.py extract --source announcements/ --db data/bids.db
    python main.py extract --retry --db data/bids.db    # 重试此前失败的公告

    # 领域数据分析（离线纯数据报告：预算/区域/趋势/关键词/密度）
    python main.py analyze --db data/bids.db --keyword 智慧城市 --days 90 --html

    # 研究管道全链：采集→抽取→分析→报告一条命令（增量模式只读新文件）
    python main.py pipeline --source announcements/ --db data/bids.db --incremental --html

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
from typing import Any, Optional, Sequence

from src.collect import dedupe_records, load_records
from src.collect.sources import SourceError
from src.llm.prompts import PromptTemplates
from src.platform import configure_console_safe, write_text_lf
from src.report.generator import ReportGenerator
from src.storage.database import _BID_COLUMNS, BidDatabase

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
            "公告源路径：.json/.jsonl/.csv 文件，或包含它们的目录"
            "（目录源按文件名排序装载）"
        ),
    )
    collect.add_argument(
        "--recursive",
        action="store_true",
        help=(
            "目录源深度遍历子目录（含符号链接环防护与"
            " Windows 大小写路径去重）"
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
        help="公告结构化抽取：原文 → LLM → 合并入库（失败进 pending 待重试）",
    )
    extract.add_argument(
        "--source",
        type=Path,
        default=None,
        help=(
            "公告源路径（.json/.jsonl 文件或目录）：装载→去重→抽取→入库；"
            "不指定时须 --retry"
        ),
    )
    extract.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"目标数据库路径（默认 {DEFAULT_DB_PATH}）",
    )
    extract.add_argument(
        "--no-llm",
        action="store_true",
        help="离线模式：不调 LLM，结构化源直通入库（无 API key 时自动降级）",
    )
    extract.add_argument(
        "--retry",
        action="store_true",
        help="重试 pending 面的待处理公告（需 API key；不处理新源）",
    )
    extract.add_argument(
        "--limit",
        type=int,
        default=None,
        help="重试条数上限（--retry 模式）",
    )
    extract.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：遇到坏文件/坏记录即中止（默认登记后继续）",
    )

    # analyze 子命令（#601 批次 C：分析面）
    analyze = sub.add_parser(
        "analyze",
        help="领域数据分析：预算/区域/趋势/关键词/密度 → 纯数据报告（离线）",
    )
    analyze.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"研究工作区数据库（默认 {DEFAULT_DB_PATH}）",
    )
    analyze.add_argument(
        "--keyword",
        default=None,
        help="领域关键词过滤（与 db --query 同口径；缺省 = 全量）",
    )
    analyze.add_argument(
        "--days",
        type=int,
        default=None,
        help="时间窗口（天；缺省 = 不限）",
    )
    analyze.add_argument(
        "--html",
        action="store_true",
        help="报告落盘后同时导出 HTML",
    )
    analyze.add_argument(
        "--compare",
        default=None,
        help="领域对照模式：逗号分隔 ≥2 个关键词（如 --compare 智慧城市,政务云）",
    )
    analyze.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/reports"),
        help="报告输出目录（默认 output/reports）",
    )

    # pipeline 子命令（#601 批次 D：全链编排）
    pipeline = sub.add_parser(
        "pipeline",
        help=(
            "研究管道全链：采集→抽取→分析→报告一条命令"
            "（每阶段状态可见，失败降级不静默）"
        ),
    )
    pipeline.add_argument(
        "--source",
        type=Path,
        default=None,
        help="公告源路径；缺省时只分析既有库（跳过采集/抽取）",
    )
    pipeline.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"研究工作区数据库（默认 {DEFAULT_DB_PATH}）",
    )
    pipeline.add_argument(
        "--keyword",
        default=None,
        help="分析/报告关键词口径",
    )
    pipeline.add_argument(
        "--days",
        type=int,
        default=None,
        help="分析/报告时间窗口（天）",
    )
    pipeline.add_argument(
        "--incremental",
        action="store_true",
        help="增量模式：只读上次成功运行后的新文件（水位见 pipeline_runs）",
    )
    pipeline.add_argument(
        "--no-llm",
        action="store_true",
        help="离线模式：跳过 LLM 抽取阶段",
    )
    pipeline.add_argument(
        "--html",
        action="store_true",
        help="报告落盘后同时导出 HTML",
    )
    pipeline.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/reports"),
        help="报告输出目录（默认 output/reports）",
    )

    # db 子命令
    db = sub.add_parser(
        "db", help="招标信息数据库管理（导入/查询/统计/导出）"
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
    db.add_argument(
        "--export",
        choices=("csv", "json"),
        help="导出项目记录为研究快照（配合 --query/--days 过滤、--out 落盘）",
    )
    db.add_argument(
        "--out",
        type=Path,
        default=None,
        help="导出目标文件（缺省输出到 stdout；CSV 落盘用 utf-8-sig）",
    )
    db.add_argument(
        "--limit",
        type=int,
        default=None,
        help="导出条数上限（配合 --export；缺省导出全部命中）",
    )
    db.add_argument(
        "--pending",
        action="store_true",
        help="列出 pending 面待处理公告（LLM 失败/拒收的降级队列）",
    )
    db.add_argument(
        "--pending-stats",
        action="store_true",
        help="pending 面统计（按状态/原因分组）",
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
        loaded = load_records(
            args.source,
            skip_invalid=not args.strict,
            recursive=getattr(args, "recursive", False),
        )
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

    # 健全性告警面（R33）——告警不拒收，逐条可见供复核
    warned = [r for r in deduped.unique if r.warnings]
    if warned:
        print(f"健全性告警：{len(warned)} 条（不拒收，供复核）")
        for record in warned[:5]:
            print(f"  ⚠ {record.bid_id}: {'; '.join(record.warnings)}")
        if len(warned) > 5:
            print(f"  … 另有 {len(warned) - 5} 条见记录 warnings")

    if args.dry_run:
        print("演练模式：未写库（--dry-run）")
        return 0

    with BidDatabase(args.db) as db:
        saved = db.import_bids([r.to_bid_row() for r in deduped.unique])
    print(f"已入库 {saved} 条 → {args.db}")
    return 0


def _build_llm_client_or_none() -> Optional[Any]:
    """构造 LLM 客户端；无环境 key 时返回 None（降级为离线直通）。

    Returns:
        LLM 客户端；或 None（未检测到 DEEPSEEK_API_KEY/OPENAI_API_KEY）。
    """
    import os

    from src.llm.client import LLMClient

    if not (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print(
            "警告：未检测到 DEEPSEEK_API_KEY/OPENAI_API_KEY——"
            "降级为离线直通模式（等价 --no-llm）"
        )
        return None
    return LLMClient()


def run_extract(args: argparse.Namespace) -> int:
    """执行 extract 子命令：装载→去重→抽取→合并入库（失败进 pending）。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码（0 正常；2 源不可读/--retry 无 key）。
    """
    from src.extract import (
        REASON_LLM_ERROR,
        REASON_REJECTED,
        STATUS_REJECTED,
        AnnouncementExtractor,
        park_record_failure,
    )

    # --retry 模式：重试 pending 面（需真实 API key）
    if args.retry:
        client = _build_llm_client_or_none()
        if client is None:
            print("错误：--retry 需要真实 LLM（设 DEEPSEEK_API_KEY）", file=sys.stderr)
            return 2
        report = asyncio.run(
            _retry_with_client(args.db, client, args.limit)
        )
        print(
            f"重试完成：尝试 {report.attempted} 条，"
            f"resolved {report.resolved} 条，"
            f"仍待处理 {report.still_pending} 条，"
            f"载荷损坏 {report.skipped_rebuild} 条"
        )
        for detail in report.details:
            print(f"  · {detail['fingerprint']}: {detail['result']}")
        return 0

    # 抽取模式：装载→去重→抽取→入库
    if args.source is None:
        print("错误：需要 --source 或 --retry", file=sys.stderr)
        return 2
    try:
        loaded = load_records(args.source, skip_invalid=not args.strict)
    except (SourceError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    deduped = dedupe_records(loaded.records)
    print(f"源装载：读取 {loaded.files_read} 个文件，"
          f"成功 {len(loaded.records)} 条，失败 {len(loaded.failures)} 条；"
          f"去重后待抽取 {len(deduped.unique)} 条")

    client = None if args.no_llm else _build_llm_client_or_none()
    extractor = AnnouncementExtractor(client)
    batch = asyncio.run(extractor.extract_batch(deduped.unique))

    llm_count = sum(1 for o in batch.outcomes if o.used_llm)
    print(f"抽取完成：LLM {llm_count} 条 / 直通 "
          f"{len(batch.outcomes) - llm_count} 条 / 失败 {len(batch.failures)} 条")

    record_map = {r.bid_id: r for r in deduped.unique}
    parked = 0
    with BidDatabase(args.db) as db:
        # 逐条按 bid_id 映射入库（抽取失败的记录不在 outcomes 里，
        # 不能与源记录按位置配对——失败面走下方 pending 登记）
        from src.extract import (
            STATUS_STORED,
            BatchStoreResult,
            apply_extraction,
        )

        store_result = BatchStoreResult()
        for outcome in batch.outcomes:
            record = record_map.get(outcome.bid_id)
            if record is None:
                continue
            store_result.outcomes.append(
                apply_extraction(db, outcome, record.to_bid_row())
            )
        stored_count = sum(
            1 for o in store_result.outcomes if o.status == STATUS_STORED
        )
        rejected_count = len(store_result.outcomes) - stored_count
        # LLM 失败 → pending（原文随载荷保留，可 --retry）
        for failure in batch.failures:
            record = record_map.get(failure["bid_id"])
            if record is not None:
                park_record_failure(
                    db,
                    record,
                    REASON_LLM_ERROR,
                    raw_text=(
                        record.extras.get("content")
                        or record.extras.get("公告原文")
                    ),
                    error=failure["error"],
                )
                parked += 1
        # 校验拒收 → pending（防御面：不静默丢）
        for outcome in store_result.outcomes:
            if outcome.status == STATUS_REJECTED and outcome.bid_id:
                record = record_map.get(outcome.bid_id)
                if record is not None:
                    park_record_failure(
                        db,
                        record,
                        REASON_REJECTED,
                        raw_text=(
                            record.extras.get("content")
                            or record.extras.get("公告原文")
                        ),
                        error="缺必填字段: " + ",".join(outcome.missing_required),
                        hit_rate=outcome.hit_rate,
                    )
                    parked += 1
        pending = db.pending_stats()

    print(f"入库：成功 {stored_count} 条 / 拒收 "
          f"{rejected_count} 条；本次登记 pending {parked} 条")
    print(f"pending 面：待处理 {pending['pending']} 条"
          f"（按原因：{pending['by_reason'] or '无'}）")
    return 0


async def _retry_with_client(db_path, client, limit):
    """重试 pending 面并在结束时关闭客户端。"""
    from src.extract import AnnouncementExtractor, retry_pending

    try:
        with BidDatabase(db_path) as db:
            return retry_pending(db, AnnouncementExtractor(client), limit=limit)
    finally:
        await client.close()


def run_analyze(args: argparse.Namespace) -> int:
    """执行 analyze 子命令：数据集 → 分析面 → 纯数据报告。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码（0 正常——空数据集也 0，报告会如实说明缺口）。
    """
    from src.analyze import (
        build_analysis_payload,
        build_comparison_payload,
        load_dataset,
    )

    if args.compare:
        keywords = [k for k in args.compare.split(",") if k.strip()]
        try:
            comparison = build_comparison_payload(
                args.db, keywords, days=args.days
            )
        except ValueError as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 2
        generator = ReportGenerator(output_dir=args.output_dir)
        report_path = generator.generate_comparison_report(comparison)
        print(f"对照报告已生成: {report_path}")
        if args.html:
            print(f"HTML 已导出: {generator.export_html(report_path)}")
        return 0

    dataset = load_dataset(
        args.db, keyword=args.keyword, days=args.days
    )
    payload = build_analysis_payload(
        dataset, keyword=args.keyword, days=args.days
    )

    scope = f"「{args.keyword}」" if args.keyword else "全量"
    print(f"分析数据集：{scope} {len(dataset)} 条记录"
          f"（完整度 {payload['complete_rate'] and round(payload['complete_rate'] * 100, 1) or 0}%）")
    if not dataset.is_empty:
        budget = payload["budget"]
        density = payload["density"]
        print(f"预算：中位 {budget['median'] and round(budget['median'], 1)} 万元，"
              f"均值 {budget['mean'] and round(budget['mean'], 1)} 万元"
              f"（有效 {budget['count']} 条）")
        print(f"密度：{density['density_level']}"
              f"（{density['monthly_rate'] and round(density['monthly_rate'], 1)} 条/月，"
              f"定标率 {density['award_rate'] and round(density['award_rate'] * 100, 1) or 0}%）")

    generator = ReportGenerator(output_dir=args.output_dir)
    report_path = generator.generate_analysis_report(payload)
    print(f"报告已生成: {report_path}")
    if args.html:
        html_path = generator.export_html(report_path)
        print(f"HTML 已导出: {html_path}")
    return 0


def run_pipeline(args: argparse.Namespace) -> int:
    """执行 pipeline 子命令：全链编排 + 阶段报告。

    Args:
        args: 已解析的命令行参数。

    Returns:
        进程退出码（0 正常；2 源不可读——起步硬错）。
    """
    from src.extract import AnnouncementExtractor
    from src.pipeline import ResearchPipeline

    extractor = None
    if args.source is not None and not args.no_llm:
        client = _build_llm_client_or_none()
        if client is not None:
            extractor = AnnouncementExtractor(client)

    pipeline = ResearchPipeline(
        args.db, extractor=extractor, output_dir=args.output_dir
    )
    try:
        result = pipeline.run(
            args.source,
            keyword=args.keyword,
            days=args.days,
            html=args.html,
            incremental=args.incremental,
        )
    except SourceError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    for stage in result.stages:
        detail = stage.detail
        if stage.status == "skipped":
            # 任何阶段的跳过都有 reason（不静默——空转也要说清楚为什么）
            line = f"跳过：{detail.get('reason', '（无原因记录）')}"
        elif stage.name == "collect":
            line = (
                f"读取 {detail['files_read']} 文件，装载 {detail['loaded']} 条"
                f"（新 {detail['new']} / 更新 {detail['updated']}），"
                f"去重 {detail['deduped']}，失败 {len(stage.failures)}"
            )
        elif stage.name == "extract":
            line = (
                f"抽取 {detail['extracted']} 条"
                f"（入库 {detail['stored']} / LLM 失败 {detail['llm_failures']}"
                f" → pending {detail['parked']}）"
            )
        elif stage.name == "analyze":
            rate = detail.get("complete_rate")
            rate_txt = f"，完整度 {round(rate * 100, 1)}%" if rate else ""
            line = f"{detail['records']} 条记录{rate_txt}"
        else:  # report
            line = f"报告 → {detail['path']}"
        print(f"[{stage.name}] {stage.status}: {line}")
        for failure in stage.failures:
            print(f"  ✗ {failure['origin']}: {failure['error']}")

    if result.report_path is not None:
        print(f"\n报告已生成: {result.report_path}")
        if args.html and result.payload and result.payload.get("_html_path"):
            print(f"HTML 已导出: {result.payload['_html_path']}")
    if result.run_id is not None:
        print(f"运行已登记：run #{result.run_id}（pipeline_runs 台账）")
    return 0


def _export_bids(db: BidDatabase, args: argparse.Namespace) -> int:
    """导出项目记录为研究快照（CSV/JSON，#601 R34）。

    Args:
        db: 已打开的数据库。
        args: 命令行参数（--export/--out/--limit/--query/--days）。

    Returns:
        进程退出码（0 正常；2 目标路径不可写）。
    """
    import csv as csv_mod

    keyword = args.query
    days = args.days
    total = db.count_bids(keyword=keyword, days=days)
    limit = args.limit if args.limit is not None else max(total, 1)
    rows = db.query_bids(keyword=keyword, days=days, limit=limit)

    # 只导业务列（id/created_at 是库内账面，不入研究快照）
    columns = list(_BID_COLUMNS)
    out_path = args.out

    if args.export == "csv":

        def _render(fh) -> None:
            writer = csv_mod.DictWriter(
                fh, fieldnames=columns, extrasaction="ignore"
            )
            writer.writeheader()
            for row in rows:
                item = {key: row.get(key) for key in columns}
                if isinstance(item.get("requirements"), list):
                    item["requirements"] = ";".join(item["requirements"])
                writer.writerow(item)

        if out_path is not None:
            try:
                with open(
                    out_path, "w", encoding="utf-8-sig", newline=""
                ) as fh:
                    _render(fh)
            except OSError as exc:
                print(f"错误：导出文件不可写: {exc}", file=sys.stderr)
                return 2
            print(
                f"已导出 {len(rows)} 条 → {out_path}（CSV，utf-8-sig）",
                file=sys.stderr,
            )
        else:
            _render(sys.stdout)
        return 0

    # JSON 快照：requirements 保持列表形态（下游机器可读）
    snapshot = [{key: row.get(key) for key in columns} for row in rows]
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if out_path is not None:
        try:
            write_text_lf(out_path, payload + "\n")
        except OSError as exc:
            print(f"错误：导出文件不可写: {exc}", file=sys.stderr)
            return 2
        print(f"已导出 {len(rows)} 条 → {out_path}（JSON）", file=sys.stderr)
    else:
        print(payload)
    return 0


def run_db(args: argparse.Namespace) -> int:
    """执行 db 子命令：导入/查询/统计/导出。

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
        if args.export:
            return _export_bids(db, args)

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

        if args.pending:
            rows = db.list_pending(limit=50)
            print(f"pending 面待处理 {len(rows)} 条（最近 50 条）：")
            for row in rows:
                print(
                    f"  [{row['reason']}] {row['bid_id'] or '（缺编号）'}"
                    f" · 指纹 {row['fingerprint']}"
                    f" · 原文 {'有' if row.get('raw_text') else '无'}"
                    f" · {row.get('error') or '原因见 reason'}"
                )

        if args.pending_stats:
            pending = db.pending_stats()
            print(
                f"pending 统计：共 {pending['total']} 条"
                f"（待处理 {pending['pending']} / "
                f"已解决 {pending['resolved']} / 跳过 {pending['skipped']}）"
            )
            if pending["by_reason"]:
                for reason, count in pending["by_reason"].items():
                    print(f"  · {reason}: {count}")

        if args.stats or (
            args.import_file is None
            and not args.query
            and not args.pending
            and not args.pending_stats
        ):
            stats = db.stats()
            runs = db.pipeline_runs_list(limit=1)
            line = (
                f"数据库统计：共 {stats['total']} 条项目，"
                f"其中 {stats['awarded']} 条已定中标人"
            )
            if runs:
                run = runs[0]
                line += (
                    f"｜最近管道运行 #{run['id']}（{run['status']}，"
                    f"{run['started_at']}）"
                )
            print(line)
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
    # R40：控制台加固先于一切输出——Windows GBK/ascii 代码页打印
    # 报告符号（█▏）不再崩溃，坏字符降级为 ?
    for action in configure_console_safe():
        logging.getLogger(__name__).debug("console hardened: %s", action)

    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "report":
        return asyncio.run(run_report(args))
    if args.command == "collect":
        return run_collect(args)
    if args.command == "extract":
        return run_extract(args)
    if args.command == "analyze":
        return run_analyze(args)
    if args.command == "pipeline":
        return run_pipeline(args)
    if args.command == "db":
        return run_db(args)
    if args.command == "templates":
        return run_templates()
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
