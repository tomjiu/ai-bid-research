"""投标研究报告生成器（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

基于 LLM 分析产出生成 Markdown 研究报告，并支持导出为带样式的
独立 HTML 文件。
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from src.llm.client import LLMClient
from src.llm.prompts import PromptTemplates
from src.platform import ensure_writable_path, sanitize_filename, write_text_lf

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查期导入，避免运行时强耦合
    from src.storage.database import BidDatabase

logger = logging.getLogger(__name__)

# 文件名中的非法字符清理
_UNSAFE_FILENAME_RE = re.compile(r"[^\w\-]+")

# Markdown 表格分隔行（如 |---|---| 或 | :---: | ---: |）
_TABLE_SEPARATOR_RE = re.compile(
    r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$"
)


class ReportGenerator:
    """基于 LLM 的投标研究报告生成器。

    可选接入 :class:`~src.storage.database.BidDatabase` 作为数据源，
    使竞争态势报告基于真实项目清单、单项目报告支持按编号自动取数。

    Attributes:
        llm: LLM 客户端实例。
        output_dir: 报告输出目录。
        db: 可选的招标信息数据库。
    """

    #: 导出 HTML 时的页面模板（{title}/{generated_at}/{body} 为占位符）
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
      "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    line-height: 1.8;
    color: #1f2937;
    background: #f9fafb;
    margin: 0;
    padding: 2rem 1rem;
  }}
  .container {{
    max-width: 860px;
    margin: 0 auto;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 2.5rem 3rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  }}
  .meta {{
    color: #6b7280;
    font-size: 0.875rem;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 0.75rem;
    margin-bottom: 1.5rem;
  }}
  h1 {{ font-size: 1.75rem; border-bottom: 2px solid #2563eb; padding-bottom: 0.5rem; }}
  h2 {{ font-size: 1.35rem; margin-top: 2rem; color: #1e40af; }}
  h3 {{ font-size: 1.1rem; margin-top: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.95rem; }}
  th, td {{ border: 1px solid #d1d5db; padding: 0.5rem 0.75rem; text-align: left; }}
  th {{ background: #eff6ff; }}
  code {{ background: #f3f4f6; border-radius: 4px; padding: 0.1rem 0.35rem; }}
  pre {{ background: #f3f4f6; border-radius: 6px; padding: 1rem; overflow-x: auto; }}
  blockquote {{ border-left: 4px solid #93c5fd; margin: 1rem 0; padding: 0.25rem 1rem; color: #374151; background: #eff6ff; }}
</style>
</head>
<body>
<div class="container">
  <div class="meta">生成时间：{generated_at} · ai-bid-research</div>
{body}
</div>
</body>
</html>
"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        output_dir: Union[str, Path] = "output/reports",
        db: Optional["BidDatabase"] = None,
    ) -> None:
        """初始化报告生成器。

        Args:
            llm_client: LLM 客户端；缺省时新建默认 :class:`LLMClient`。
            output_dir: 报告输出目录，不存在时自动创建。
            db: 可选的招标信息数据库；接入后报告将基于库内真实数据。
        """
        self.llm = llm_client or LLMClient()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db = db

    # ------------------------------------------------------------------
    # 报告生成
    # ------------------------------------------------------------------

    async def generate_bid_report(
        self, bid_id: str, analysis_data: Optional[Dict[str, Any]] = None
    ) -> Path:
        """生成单个招标项目的投标分析报告。

        Args:
            bid_id: 招标项目编号（用于报告标识与文件名前缀）。
            analysis_data: 该项目的结构化分析数据；为 ``None`` 且已
                接入数据库时按 ``bid_id`` 自动取数。

        Returns:
            已保存的 Markdown 报告文件路径。

        Raises:
            ValueError: 既无 ``analysis_data`` 也未接入数据库时。
            LookupError: 数据库中不存在该编号时。
        """
        if analysis_data is None:
            if self.db is None:
                raise ValueError(
                    "analysis_data 为空且未接入数据库，无法生成报告"
                )
            analysis_data = self.db.get_bid(bid_id)  # type: ignore[union-attr]
            if analysis_data is None:
                raise LookupError(f"数据库中不存在招标编号: {bid_id}")
        prompt = PromptTemplates.report_generation(
            json.dumps(analysis_data, ensure_ascii=False, indent=2)
        )
        content = await self.llm.chat(
            [
                {"role": "system", "content": PromptTemplates.SYSTEM_ROLE},
                {"role": "user", "content": prompt},
            ]
        )

        project_name = str(analysis_data.get("project_name") or bid_id)
        report = (
            f"# 投标分析报告：{project_name}\n\n"
            f"- 招标编号：{bid_id}\n"
            f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "---\n\n"
            f"{content}\n"
        )
        return self._save_report(report, prefix=f"bid_{bid_id}")

    async def generate_competition_report(
        self, keyword: str, days: int = 7
    ) -> Path:
        """生成指定关键词近期项目的竞争态势报告。

        接入数据库时基于库内真实项目清单；未接入时退化为占位提示，
        由模型基于通用行业知识作答。

        Args:
            keyword: 检索关键词（行业领域或产品名）。
            days: 回溯天数，用于限定竞争数据的时间窗口。

        Returns:
            已保存的 Markdown 报告文件路径。
        """
        data_source = "通用行业知识（未接入本地数据库）"
        if self.db is not None:
            bid_rows = self.db.query_bids(keyword=keyword, days=days)  # type: ignore[union-attr]
            data_source = f"本地数据库 {len(bid_rows)} 条项目记录"
            # #601 批次 F：LLM 叙述以计算统计为锚（防模型数字幻觉）——
            # 先给已算好的事实块，再给清单；叙述不得与事实块冲突。
            bid_list = self._grounding_block(keyword, days) or ""
            if bid_rows:
                bid_list += "\n" + "\n".join(
                    f"- {row.get('publish_date') or '日期未知'} | "
                    f"{row.get('project_name')}（编号 {row.get('bid_id')}，"
                    f"预算 {row.get('budget') if row.get('budget') is not None else '未知'}，"
                    f"地区 {row.get('region') or '未知'}，"
                    f"中标人：{row.get('winner') or '未开标'}）"
                    for row in bid_rows
                )
            else:
                bid_list = (
                    f"数据库中关键词「{keyword}」近 {days} 天无记录，"
                    "请基于行业通用情况作答并明确说明数据缺口。"
                )
        else:
            bid_list = f"（关键词「{keyword}」近 {days} 天的招标与中标项目清单）"

        prompt = PromptTemplates.competitor_analysis(
            keyword=keyword, bid_list=bid_list
        )
        content = await self.llm.chat(
            [
                {"role": "system", "content": PromptTemplates.SYSTEM_ROLE},
                {"role": "user", "content": prompt},
            ]
        )

        report = (
            f"# 竞争态势报告：{keyword}\n\n"
            f"- 统计窗口：近 {days} 天\n"
            f"- 数据来源：{data_source}\n"
            f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "---\n\n"
            f"{content}\n"
        )
        return self._save_report(report, prefix=f"competition_{keyword}")

    def _grounding_block(self, keyword: str, days: int) -> str:
        """构造 LLM 叙述的统计锚定块（#601 批次 F）。

        用批次 C 的分析面（预算分位/密度/定标率）产出「已计算事实」，
        叙述面声明这些数字为权威——模型只需解读，不需要自算
        （自算正是数字幻觉的来源）。

        Args:
            keyword: 检索关键词。
            days: 时间窗口。

        Returns:
            统计事实文本块；数据库无记录时为空串。
        """
        from src.analyze import build_analysis_payload, load_dataset

        assert self.db is not None  # 调用方已判
        dataset = load_dataset(self.db, keyword=keyword, days=days)
        if dataset.is_empty:
            return ""
        payload = build_analysis_payload(dataset, keyword=keyword, days=days)
        budget = payload["budget"]
        density = payload["density"]

        def _num(value):
            return f"{value:,.1f}" if isinstance(value, (int, float)) else "——"

        lines = [
            "【已计算统计事实——以下数字为权威，叙述不得与之冲突】",
            f"- 样本：{payload['record_count']} 条记录"
            f"（数据完整度 {round((payload['complete_rate'] or 0) * 100, 1)}%）",
            f"- 预算（万元）：中位 {_num(budget['median'])}，"
            f"均值 {_num(budget['mean'])}，"
            f"P25/P75 = {_num(budget['p25'])}/{_num(budget['p75'])}",
            f"- 发布密度：{density['monthly_rate'] and round(density['monthly_rate'], 1)} 条/月"
            f"（层级 {density['density_level']}）",
            f"- 定标率：{density['award_rate'] and round(density['award_rate'] * 100, 1)}%",
        ]
        top_regions = list(payload["region"].items())[:3]
        if top_regions:
            region_txt = "、".join(f"{name} {count} 条" for name, count in top_regions)
            lines.append(f"- 区域 Top3：{region_txt}")
        return "\n".join(lines)

    def generate_comparison_report(
        self, comparison_payload: Dict[str, Any]
    ) -> Path:
        """保存领域对照报告（#601 批次 F——离线，不走 LLM）。

        Args:
            comparison_payload: ``build_comparison_payload`` 产物。

        Returns:
            已保存的 Markdown 报告文件路径。
        """
        from src.analyze.compare import render_comparison_markdown

        keywords = comparison_payload.get("keywords") or ["对照"]
        content = render_comparison_markdown(comparison_payload)
        prefix = "compare_" + "_vs_".join(keywords)
        return self._save_report(content, prefix=prefix)

    def generate_analysis_report(
        self, analysis_payload: Dict[str, Any]
    ) -> Path:
        """保存纯数据分析报告（#601 批次 C——离线、不走 LLM）。

        与 :meth:`generate_competition_report`（LLM 叙述报告）互补：
        本方法只渲染已组装的分析 payload，可离线复现。

        Args:
            analysis_payload: ``build_analysis_payload`` 产物。

        Returns:
            已保存的 Markdown 报告文件路径。
        """
        from src.analyze.report_data import render_analysis_markdown

        keyword = analysis_payload.get("keyword")
        content = render_analysis_markdown(analysis_payload)
        prefix = f"analysis_{keyword}" if keyword else "analysis_all"
        return self._save_report(content, prefix=prefix)

    # ------------------------------------------------------------------
    # 导出与保存
    # ------------------------------------------------------------------

    def export_html(self, markdown_path: Union[str, Path]) -> Path:
        """将 Markdown 报告导出为带样式的独立 HTML 文件。

        Args:
            markdown_path: Markdown 报告文件路径。

        Returns:
            导出的 HTML 文件路径（与源文件同目录同名，后缀 ``.html``）。

        Raises:
            FileNotFoundError: 源 Markdown 文件不存在时。
        """
        source = Path(markdown_path)
        if not source.is_file():
            raise FileNotFoundError(f"Markdown 报告不存在: {source}")

        markdown_text = source.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else source.stem

        html_content = self.HTML_TEMPLATE.format(
            title=html.escape(title),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            body=self.markdown_to_html(markdown_text),
        )
        target = source.with_suffix(".html")
        ensure_writable_path(target)
        write_text_lf(target, html_content)
        logger.info("HTML 报告已导出: %s", target)
        return target

    def _save_report(self, content: str, prefix: str) -> Path:
        """将报告内容保存为时间戳命名的 Markdown 文件。

        Args:
            content: 报告 Markdown 文本。
            prefix: 文件名前缀（非法字符会被替换为下划线）。

        Returns:
            保存的文件路径，形如 ``<prefix>_<YYYYMMDD_HHMMSS>.md``。
        """
        # R46：平台清洗面（非法字符/保留名/尾点）——\w 类正则不拦
        # Windows 保留名与尾点空格，统一走 sanitize_filename
        safe_prefix = sanitize_filename(prefix) or "report"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"{safe_prefix}_{timestamp}.md"
        ensure_writable_path(path)
        write_text_lf(path, content)
        logger.info("报告已保存: %s", path)
        return path

    # ------------------------------------------------------------------
    # Markdown → HTML 转换（轻量实现，覆盖报告常用语法）
    # ------------------------------------------------------------------

    @staticmethod
    def markdown_to_html(markdown_text: str) -> str:
        """将报告使用的 Markdown 子集转换为 HTML。

        支持语法：标题（``#``~``####``）、无序/有序列表、表格、粗体、
        行内代码、代码块、引用块、水平线与段落。

        Args:
            markdown_text: Markdown 文本。

        Returns:
            HTML 片段字符串（不含 ``<html>`` 外壳）。
        """
        lines = markdown_text.splitlines()
        blocks: list[str] = []
        buffer: list[str] = []
        list_type: str | None = None  # "ul" | "ol" | "quote" | "pre" | "table"

        def flush() -> None:
            nonlocal buffer, list_type
            if not buffer and list_type is None:
                return
            text = "\n".join(buffer)
            if list_type == "ul":
                items = "".join(
                    f"<li>{ReportGenerator._render_inline(item)}</li>"
                    for item in buffer
                )
                blocks.append(f"<ul>{items}</ul>")
            elif list_type == "ol":
                items = "".join(
                    f"<li>{ReportGenerator._render_inline(item)}</li>"
                    for item in buffer
                )
                blocks.append(f"<ol>{items}</ol>")
            elif list_type == "quote":
                quote = "<br>".join(
                    ReportGenerator._render_inline(line) for line in buffer
                )
                blocks.append(f"<blockquote>{quote}</blockquote>")
            elif list_type == "pre":
                blocks.append(f"<pre><code>{html.escape(text)}</code></pre>")
            elif list_type == "table":
                blocks.append(ReportGenerator._render_table(buffer))
            elif buffer:
                blocks.append(f"<p>{ReportGenerator._render_inline(text)}</p>")
            buffer = []
            list_type = None

        for raw_line in lines:
            line = raw_line.rstrip()

            # 代码块围栏
            if line.startswith("```"):
                if list_type == "pre":
                    flush()
                else:
                    flush()
                    list_type = "pre"
                continue

            if list_type == "pre":
                buffer.append(raw_line)
                continue

            stripped = line.strip()

            # 空行
            if not stripped:
                flush()
                continue

            # 标题
            heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
            if heading:
                flush()
                level = len(heading.group(1))
                blocks.append(
                    f"<h{level}>{ReportGenerator._render_inline(heading.group(2))}</h{level}>"
                )
                continue

            # 水平线
            if re.match(r"^-{3,}$", stripped):
                flush()
                blocks.append("<hr>")
                continue

            # 无序列表
            bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
            if bullet:
                if list_type != "ul":
                    flush()
                    list_type = "ul"
                buffer.append(bullet.group(1))
                continue

            # 有序列表
            ordered = re.match(r"^\d+[.、)]\s+(.*)$", stripped)
            if ordered:
                if list_type != "ol":
                    flush()
                    list_type = "ol"
                buffer.append(ordered.group(1))
                continue

            # 引用块
            if stripped.startswith(">"):
                quote_text = stripped.lstrip(">").strip()
                if list_type != "quote":
                    flush()
                    list_type = "quote"
                buffer.append(quote_text)
                continue

            # 表格行（以 | 开头；分隔行 |---|---| 跳过不存）
            if stripped.startswith("|"):
                if list_type != "table":
                    flush()
                    list_type = "table"
                if buffer and _TABLE_SEPARATOR_RE.match(stripped):
                    continue
                buffer.append(stripped)
                continue

            # 普通段落行
            flush()
            buffer.append(stripped)

        flush()
        return "\n".join(blocks)

    @staticmethod
    def _render_table(rows: list[str]) -> str:
        """将 Markdown 表格行渲染为 HTML ``<table>``。

        首行为表头，其余为数据行；分隔行已在上游被跳过。

        Args:
            rows: 以 ``|`` 分隔的原始表格行列表。

        Returns:
            完整 ``<table>`` HTML 片段。
        """

        def split_cells(line: str) -> list[str]:
            return [cell.strip() for cell in line.strip().strip("|").split("|")]

        header = split_cells(rows[0])
        body_rows = [split_cells(row) for row in rows[1:]]
        thead = "<thead><tr>" + "".join(
            f"<th>{ReportGenerator._render_inline(cell)}</th>" for cell in header
        ) + "</tr></thead>"
        tbody = "".join(
            "<tr>"
            + "".join(
                f"<td>{ReportGenerator._render_inline(cell)}</td>"
                for cell in cells
            )
            + "</tr>"
            for cells in body_rows
        )
        return f"<table>{thead}<tbody>{tbody}</tbody></table>"

    @staticmethod
    def _render_inline(text: str) -> str:
        """渲染行内 Markdown 语法（转义、粗体、行内代码）。

        Args:
            text: 单行文本。

        Returns:
            HTML 片段字符串。
        """
        escaped = html.escape(text)
        # 行内代码先处理，避免内部粗体被二次替换
        escaped = re.sub(
            r"`([^`]+)`",
            lambda m: f"<code>{m.group(1)}</code>",
            escaped,
        )
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        return escaped
