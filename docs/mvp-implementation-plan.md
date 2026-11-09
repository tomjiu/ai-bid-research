# 最小可行版本（MVP）实施顺序与验收标准（mvp-implementation-plan）

> 前提：本阶段已完成审计与设计（`research/` + `docs/` 共 8 份文档）。本计划给出从 0 到 MVP 的实施顺序、每步验收标准，以及"招标文件导入 → 最终审校导出"的可执行流程串讲。
> 约束：**不修改文档内核内部实现**（M0 定义契约 + stub，M5 才接真实内核）；不实现范围外功能；复用代码只取许可证干净部分（`repository-matrix.md` §3 白名单）。

## 0. 范围界定

**做（MVP）**：招标文件导入与解析（完整性对账）→ 六类条款抽取（覆盖率对账）→ 证据库三通道检索 → 合规矩阵 + 三道人审门 → 规则推导目录 → 单章任务化生成（引用回查）→ 规则注册表审校 + 修订循环 → 内核导出（含暗标模式）→ 全程事件溯源与断点恢复。
**不做（明确排除）**：标书查重、商机发现、多租户/权限体系、Dify 导入、移动端、自动投标决策、历史标书库训练。

## 1. 端到端可执行流程串讲（从导入到最终审校）

| 步 | 动作（工具） | 状态 | 产物/守卫 |
|----|-------------|------|----------|
| 1 | create_bid_project | CREATED | project_id（external_ref 幂等） |
| 2 | import_tender_files（main→attachment） | FILES_IMPORTING→PARSED | chunk 清单；**完整性对账**（Σchar≥98%）不过即 PARSE_FAILED |
| 3 | extract_requirements | →REQUIREMENTS_READY | REQ-ID（内容哈希稳定）；六类封闭枚举；coverage 报告；NO_REJECTION_CLAUSE 守卫 |
| 4 | （服务端）构建合规矩阵 + search_evidence 三通道 + attach_evidence | →MATRIX_READY | CMP（decided_by 留痕）；过期/冲突证据默认不可用 |
| 5 | 人审门① record_review_decision(matrix_approval) | →MATRIX_APPROVED | blocking 项必须决策或 waiver |
| 6 | （服务端）规则推导目录（format 条款 + 招标规定目录优先） | →OUTLINE_DRAFTED | SEC 树 + requirement_ids 映射 |
| 7 | 人审门② record_review_decision(outline_approval) | →OUTLINE_APPROVED | 目录覆盖全部 REQ 或给出未响应清单 |
| 8 | draft_response_section × N（并行队列） | →SECTIONS_IN_PROGRESS→SECTIONS_DRAFTED | 单章：服务端上下文包→生成→**引用回查**→内核块 CAS 写入；EVIDENCE_MISSING→该章 blocked |
| 9 | validate_bid_document（规则注册表 + 模型复核） | →VALIDATED | FIND 报告；blocking=0 才可过 |
| 10 | create_revision_task + draft_response_section(revise) 循环 | （回 SECTIONS_IN_PROGRESS）| 修订两轮熔断→人工 |
| 11 | 人审门③ record_review_decision(pre_export_confirm) | →READY_FOR_EXPORT | 快照 CAS 集绑定 |
| 12 | export_bid_document（内核适配器；暗标强制） | →EXPORTING→EXPORTED | artifact + checksum；门禁后任何变更→SNAPSHOT_STALE |
| 任意 | get_bid_project_state（恢复入口） | 任意 | allowed_next_tools 引导；补遗→失效传播→仅受影响章节重做 |

## 2. 里程碑与验收标准（串行推进，M3 起可部分并行）

### M0 地基（≈1 周）
**内容**：领域模型持久化（`bid-domain-model.md` 全部实体）+ 状态机 + 事件存储（append-only）+ 幂等键表 + MCP server 骨架（12 工具：状态校验与错误包先行，业务可返回 UNIMPLEMENTED_INTERNAL）+ 文档内核适配器 stub（8 操作内存实现）+ CI（含 license-check、token 泄漏扫描）。
**验收**：①状态机全转换路径单测 100%（含非法转换拒绝）；②每个 MCP 工具一个契约测试（无 LLM）全绿；③stub 内核契约测试全绿 + KERNEL_INCOMPATIBLE 演练；④幂等键 24h 去重行为测试；⑤仓库准入扫描（防 S-5 数据入库）。

### M1 解析与条款（≈1.5 周）
**内容**：import_tender_files 真实现（pdfium/MinerU 经独立解析服务；结构化分块；完整性对账）+ extract_requirements（双通道互验 + 覆盖率对账 + REQ-ID 内容哈希）+ needs_OCR 子任务位。
**复用**：power_grid 的 MinerU 接线与 >200 页拆分（MIT）；RudyJunyu 解析数据结构仅 clean-room 借鉴。
**验收**：合成语料 T1：总体条款召回 ≥95%，**否决项召回 100%（硬门）**；T2：人为截断的文件必须被 PARSE_INTEGRITY_FAILED 拒绝；重跑同文件 REQ-ID 零漂移；needs_OCR 文件阻止 extract。

### M2 证据与矩阵（≈1 周）
**内容**：证据库 schema + 摄取管道（含 valid_until 解析）+ search_evidence 三通道（向量 + FTS/trgm + 结构化字段过滤）+ 合规矩阵构建 + attach_evidence（引文校验）+ 矩阵门。
**复用**：ai_bidding `hybrid_search` + reranker + 001 SQL（MIT）。
**验收**：T3 针检索：编号/型号/金额区间/日期四类 needle 查询精确命中率 ≥90%；过期证据默认不返回且自动置 blocking；服务端阻断测试（无 waiver 时矩阵门拒绝放行）；证据冲突用例两个 EVL 均不可用。

### M3 章节生成（≈1.5 周）
**内容**：目录推导（format 条款规则 + 规定目录优先）+ SectionTask 引擎（attempts/熔断/上下文包持久化）+ draft_response_section（生成→引用回查→内核 CAS 写入）+ 断点续跑。
**复用**：ai_bidding `tender_format_parser` 确定性格式链 + `context_builder` 五域上下文（MIT）。
**验收**：T5 断点恢复：在 6 个状态边界 + 2 个随机点强杀进程，恢复后状态一致、无重复工作、无条款丢失；引用回查：植入无证据断言必须被 CITATION_MISMATCH 拦截；单章 token 预算上限断言（T9）。

### M4 审校与修订（≈1 周）
**内容**：规则注册表 ≥10 条（AMOUNT/QANTITY/CERT_VALIDITY/DATE_LOGIC/SIGNATURE_PAGE/BLIND_BID_STRIP/PLACEHOLDER/WORD_COUNT/TOC/REJECTION_COVERAGE/FORMAT）+ validate_bid_document + 修订循环 + bid-review 子技能。
**复用**：OpenBidKit 64 规则与查重思路、RudyJunyu 34 检查项——**全部 clean-room 重写**（AGPL/无许可证）。
**验收**：T6 缺陷种子：确定性规则检出率 100%（每规则至少 1 正 1 反用例）；模型复核对 seeded 语义缺陷检出 ≥80%；两轮修订收敛测试；ATTEMPTS_EXCEEDED 熔断生效。

### M5 导出与端到端（≈1 周）
**内容**：适配器接真实文档内核（契约 M0 已冻结，版本协商）+ export_bid_document（含 blind_mode 强制、precheck 快照）+ 端到端联调 + 成本报表（model_run 汇总）。
**复用**：power_grid `md_to_word` 公文参数（MIT）供内核侧模板参考；Get00 TOC 域思路（Apache）。
**验收**：T7 端到端：合成招标文件 → EXPORTED 产物 docx 校验（目录/页眉/暗标剥离抽检）；门禁后修改→SNAPSHOT_STALE 拒绝导出；T10 Skill 演练：全新会话凭 Skill 从断点恢复完成导出，0 非法工具调用。

## 3. 里程碑 × 风险对照（risk-register 前置）

| 里程碑 | 必须闭环的风险 |
|--------|---------------|
| M0 | P-3（复用许可证）、S-5（数据入库扫描）、P-4（状态机漂移） |
| M1 | S-1（截断丢失）、P-1（否决项召回） |
| M2 | S-2（阻断可绕过）、P-2（证据幻觉的基础设施） |
| M3 | S-4（恢复假/默认关）、S-7（静默降级）、P-10（token 失控） |
| M4 | P-7（确定性规则缺失）、P-2（引用回查闭环） |
| M5 | P-6（内核契约漂移）、暗标事故（BLIND_MODE_REQUIRED） |

## 4. 复用执行纪律（每里程碑 PR 门禁）

1. 引入任何第三方代码前查 `repository-matrix.md` §3/§6：仅 MIT/Apache-2.0 可代码级复用，AGPL/无许可证一律 clean-room。
2. 96syh 系代码：替换 PyMuPDF 后才可引入；LingYan 系代码：仅取 HEAD。
3. license-check 进 CI：依赖树 AGPL/无许可证包直接红。
4. 每次复用在 PR 描述登记：来源仓库、文件、许可证、改造点（可审计追溯）。
