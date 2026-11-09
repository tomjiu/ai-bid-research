"""招投标研究场景的提示词模板模块。

集中管理 LLM 调用所用提示词，保证各分析环节提示词风格统一、
可测试、可复用。
"""

from __future__ import annotations

from typing import Callable, Dict

# 各模板共享的系统角色设定（模块级常量，保持向后兼容）
SYSTEM_ROLE = (
    "你是一位资深的中国招投标市场分析专家，精通政府采购法、招标投标法"
    "及相关行业规范，擅长从招标公告与历史中标数据中提炼关键信息、"
    "评估竞争格局并给出可执行的投标建议。"
)


class PromptTemplates:
    """招投标研究提示词模板集合。

    所有模板均为静态方法，入参为业务数据文本，返回可直接作为
    user 消息内容的完整提示词。
    """

    #: 各模板共享的系统角色设定
    SYSTEM_ROLE = SYSTEM_ROLE

    @staticmethod
    def bid_extraction(bid_text: str) -> str:
        """生成招标信息抽取提示词。

        Args:
            bid_text: 招标公告原文。

        Returns:
            指示模型抽取结构化字段并以 JSON 输出的提示词。
        """
        return f"""请仔细阅读以下招标公告原文，抽取结构化信息。

招标公告原文：
---
{bid_text}
---

请以 JSON 对象输出，包含以下字段：
- project_name: 项目名称
- bid_id: 招标编号
- budget: 预算金额（万元，数字；未提及则为 null）
- publish_date: 公告发布日期（YYYY-MM-DD，无法确定则为 null）
- deadline: 投标截止时间（YYYY-MM-DD HH:MM，无法确定则为 null）
- region: 项目所在地区（省/市）
- purchaser: 采购人名称
- agency: 代理机构名称
- category: 采购类别（货物/服务/工程）
- requirements: 关键资格要求与技术要求要点（字符串数组）

只输出 JSON，不要添加任何解释性文字。"""

    @staticmethod
    def bid_analysis(bid_info: str) -> str:
        """生成单项目投标价值分析提示词。

        Args:
            bid_info: 已抽取的招标项目结构化信息（JSON 文本）。

        Returns:
            指示模型从投标价值角度分析该项目的提示词。
        """
        return f"""请基于以下招标项目结构化信息，从投标方视角进行深度分析。

项目信息：
---
{bid_info}
---

请输出 Markdown 格式的分析报告，包含以下小节：
## 项目概况
## 资格门槛分析
## 技术要求难点
## 竞争格局预判
## 投标建议与风险提示

要求：结论具体、有依据，避免空泛套话；涉及金额与日期时引用原始数据。"""

    @staticmethod
    def competitor_analysis(keyword: str, bid_list: str) -> str:
        """生成竞争态势分析提示词。

        Args:
            keyword: 检索关键词（如行业领域或产品名）。
            bid_list: 近期相关招标/中标项目清单文本。

        Returns:
            指示模型汇总该关键词领域竞争态势的提示词。
        """
        return f"""请基于关键词「{keyword}」近期的招标与中标项目数据，分析该领域的竞争态势。

项目清单：
---
{bid_list}
---

请输出 Markdown 格式的分析报告，包含以下小节：
## 市场热度概览
## 主要采购方与典型项目
## 中标供应商格局
## 常见采购需求与技术趋势
## 对新进入者的建议

要求：基于给定数据展开，不得编造清单之外的项目；数据不足时明确说明。"""

    @staticmethod
    def report_generation(analysis_data: str) -> str:
        """生成研究报告撰写提示词。

        Args:
            analysis_data: 前序分析产出的数据与结论（JSON 或文本）。

        Returns:
            指示模型将分析数据组织为正式研究报告的提示词。
        """
        return f"""请将以下分析数据整理为一篇结构完整的投标研究报告。

分析数据：
---
{analysis_data}
---

要求：
1. 使用 Markdown 格式，报告以二级标题分节；
2. 篇幅 800-1500 字，重点突出、层次清晰；
3. 包含"结论与建议"小节，给出明确、可执行的下一步动作；
4. 数据引用须与分析数据一致，不得新增未经数据支撑的结论。"""

    @staticmethod
    def get_all_templates() -> Dict[str, Callable[..., str]]:
        """返回全部模板的名称到方法的映射。

        Returns:
            字典，键为模板名，值为对应的静态方法，
            可用于运行时枚举或批量校验提示词。
        """
        return {
            "bid_extraction": PromptTemplates.bid_extraction,
            "bid_analysis": PromptTemplates.bid_analysis,
            "competitor_analysis": PromptTemplates.competitor_analysis,
            "report_generation": PromptTemplates.report_generation,
        }
