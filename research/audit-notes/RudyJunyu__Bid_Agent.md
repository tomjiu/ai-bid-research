# RudyJunyu/Bid_Agent 源码审计报告

审计方式：只读静态审计（未安装依赖、未运行仓库代码、未调用 LLM API）。git log/ls-files + 全量源码阅读 + 只读 sqlite3 检查误提交二进制。浅克隆 depth 20。

## 1. 基本信息

- **LICENSE：无**。`git ls-files` 无 LICENSE 文件。法律含义：默认全版权保留（《著作权法》第 10 条 + 伯尔尼公约），任何代码、提示词文本、正则规则表的复制/修改/再分发均需作者书面授权，否则有侵权风险。GitHub 无 License 时按"All rights reserved"处理。
- **主要语言/规模**：Python 后端 23 个 .py（核心管线约 8,900 行：bid_database 2807、bid_parser_api 1819、bid_document_parser 1379、bid_analysis_prompts 827、bid_vector_store 784、bid_structured_extraction 502、bid_analysis_service 506、content_review_agent 400、bid_rule_extractor 387、bid_section_retriever 386 等）+ Electron 前端（renderer.js 3573、main.js 233）。git 跟踪 47 个文件，size-pack 24.43 MiB，其中 **.chroma 二进制 ≈22.9MB + 迁移 zip 13.3MB（均误提交，见风险清单）**，真实代码体积很小。
- **顶层结构**：根目录平铺约 20 个管线模块（解析→抽取→审查→生成全在一个目录）；`electron_client/`（Electron 桌面壳，自动拉起 FastAPI）；`scripts/`（start.ps1、export_db_schema_excel.py）；`docs/招投标智能体数据库表结构.xlsx`（真实存在，4 个 worksheet，由脚本从实际 SQLite 导出）；`DATABASE_SCHEMA_DESIGN.md`（684 行表设计文档）；`思路.md`（作者的技术路径自述）；`plan_and_solve_agent_migration_20260612_165408.zip`（误提交迁移包）。
- **提交历史**：浅克隆 20 条，2026-06-03（Refresh Bid Agent project）→ 2026-06-14（Merge remote master），11 天密集开发后停更。关键提交：`81043eb` 优化结构化提取层流程（06-09）、`681715e` 片段清洗结构化进 SQLite/Chroma（06-09）、`b1701c4/cab7c79` README 大改（06-13/14）。
- **测试：无**（glob `**/test*` 零结果）。README"后续计划"自认"增加自动化测试和发布流程"。
- **第三方依赖**（requirements.txt 22 包）：fastapi/uvicorn、openai、python-dotenv、requests、pydantic、numpy<2、opencv-python<4.12、pdfplumber、**pymupdf（AGPL-3.0 许可证注意点）**、pymupdf4llm、docling、pypdf、docx2python、python-docx、openpyxl、pillow、rapidocr-onnxruntime、pytesseract、chromadb、sentence-transformers、python-multipart。electron devDeps：electron ^31 + electron-builder ^24。**SerpApi_search_tool.py `from serpapi import Client` 但 requirements 未声明 serpapi 包**（该文件为孤儿模块，无任何 import 引用，不影响主链）。无 AGPL 级传染风险组件进入主链调用路径，但 pymupdf 在 requirements 中（pymupdf4llm 的本地依赖），若复用其 PDF 路线需注意 AGPL。

## 2. 能力清单（核心）

### a. 招标文件解析 — **IMPLEMENTED**（本仓库最强环节，与初筛结论一致）
入口：`parse_bid_document()`（bid_document_parser.py L54）→ `parse_document_to_markdown()`（L85）→ `split_bid_markdown_sections()`（L475）→ `enrich_sections_with_metadata()`（L553）。
- 支持 10 种解析方式（bid_parse_strategy.py `PARSE_METHODS_LABELS` L13-24）：MinerU vlm/pipeline/html/parallel_pages（云端 API，MinerU_pdf_parse_tool.py L18 `https://mineru.net/api/v4`，支持后缀含 .html）、本地 pdfplumber/pymupdf4llm/docling、docx2python(+image_ocr)。
- PDF 预检分流：`inspect_document_profile` → `classify_pdf_profile`（bid_parse_strategy.py L226-263）将 PDF 分为 scanned_pdf/mixed_pdf/simple_text_pdf/native_text_pdf 四类，`simple_text_pdf` 要求 ≤20 页、每页 ≥300 字符、无图无表才走 pdfplumber；扫描件/混排走 MinerU；大 PDF（≥30 页）走 `mineru_parallel_pages`（pypdf 按页段切分并发提交后按页序合并，bid_document_parser.py L224-325）。
- 中间数据结构（核心可借鉴资产）：
```python
class BidDocumentSection(BaseModel):          # bid_document_parser.py L18
    index: int; title: str; level: int
    content: str    # 不含标题行正文
    markdown: str   # 标题+正文 Markdown
    metadata: dict  # title_path[]、tables[]、images[]、page_start/end
```
  表格结构化（L586-668）：`_parse_markdown_table` 产出 `{headers, rows, row_cell_header_maps[], row_count, markdown}`，含类合并单元格行填充 `_expand_merged_like_table_row`（左填充+上行填充）与 `_build_cell_header_map`（表头→单元格值映射）。
  DOCX 图片结构化（L898-1038）：`{index, source, location_type(paragraph|table_cell), paragraph_index, table_index, nearby_text, ocr_text, visual_guess, vlm_status:"pending_external_vlm"}`；`_guess_visual_content_type`（L1062）用正则把图片猜成"疑似公章/印章/签字/架构图"——签章线索为关键词级，非视觉检测。
- 章节切分：`_detect_heading`（L1351）识别 Markdown 标题 + 4 种中文编号模式（第X章/一、/1.1/（一）），构建 title_path 栈；无标题时全文兜底为单节；pdfplumber/pymupdf 每页输出 `## 第 N 页` 标题 → 每页一个 section。
- 扫描件：OCR 由 MinerU 云端承担（本地 rapidocr/pytesseract 仅用于 DOCX 内嵌图片，bid_document_parser.py L1093-1124）。HTML：仅能走 MinerU 云端（本地方法不含 HTML）。
- 局限：`_guess_page_number`（L683）靠正则找"第N页"，MinerU 路线大多 page_start=None；DOCX 兜底解析 `_extract_docx_table_lines`（L1127）把表格拍平为 `cell | cell` 文本行，不生成标准 Markdown 表格。

### b. 条款/要求提取 — **PARTIAL**（五模块有实现，六类口径不齐）
入口：`analyze_bid_document`（bid_analysis_service.py L238）与 `_analyze_sections`（bid_parser_api.py L645）。
- 全局上下文两阶段抽取（见 Q2 详述）：第一阶段 `extract_rule_global_context`（bid_rule_extractor.py L126）纯正则产出 project_profile(16 字段)+section_tree+extraction_meta{method:"rule_regex_first_pass", profile_completeness, needs_llm_completion}；第二阶段仅在 `needs_llm_global_completion()`（L219）为真时调用 `GLOBAL_CONTEXT_SYSTEM_PROMPT`（bid_analysis_prompts.py L551，JSON 结构含 section_index/title/level/title_path/start_position/end_position/module_hint/summary）。
- 四模块专项并发：商务（V2 固定 5 张表格模板，bid_analysis_prompts.py L332-399）、技术、资格+废标（3 张表：资格性审查/符合性审查/废标项，L78-103）、评分（商务评分/技术评分，明确不输出价格评分 L131）。全部携带 `SPECIALIST_CONTEXT_RULES`（L607）："不得修改 project_profile 基本信息，只能从指定候选章节提取"。
- 默认 Markdown 快速输出（`BID_FAST_MARKDOWN_EXTRACTION=true` 且 `BID_STRUCTURED_OUTPUT_ENABLED=false` 双开关，bid_structured_extraction.py L21-34）；JSON Schema 模式（5 个 schema，含 review_findings）强制每条带 source_chunk_id/source_text/source_heading/evidence_snippet（L301 SOURCE_REQUIRED），enum 归一化：风险等级 高/中/低/未明确、废标法律性质 资格性/符合性/响应性/其他、评分类型 商务/技术/价格/其他。
- 格式要求类条款：仅散落在商务/资格模块内，无独立"格式要求"分类 → 六类中"格式要求"缺失、"否决项"不独立（挂在资格模块）。
- 资格/废标全覆盖机制：轻量模型逐章预筛 `PREFILTER_SYSTEM_PROMPT`（bid_qualification_prefilter.py L16-39，分类 qualification|compliance|rejection|both|none + confidence 阈值 0.45），先规则召回再切 4500 字符窗口，命中片段合成"预筛章节"并入精提取上下文；失败自动回退规则召回（bid_analysis_service.py L109-117）。

### c. 原文位置溯源 — **PARTIAL**
- 结构化模式：schema 强制 source_chunk_id（候选章节打包时注入 `【source_chunk_id】S{index}` 标记，bid_structured_extraction.py L69-91），入库时写入各表 chunk_id/source_text 列（bid_database.py L1445 等）。
- 默认 Markdown 模式：无 chunk id，入库 source_text 取 LLM 原文摘录或表格行拼接；qualification_requirements 表虽有 source_page_start/end 列（L189-190），`_insert_qualification_and_rejection_structured`（L1486）**并未写入页码** → 页码溯源实际不可用；页码仅 document_sections/chunks 有 page_start/page_end（且多为 None）。
- content_review 的 `_evidence_snippets`（content_review_agent.py L301）给出 ±46 字符原文证据片段——这是默认模式下唯一稳定溯源。

### d. 企业资料检索/证据 — **PARTIAL（弱）**
- 知识库 8 类（KNOWLEDGE_TYPES，bid_database.py L19-28：公司/资质/人员/财务/业绩/案例/历史标书/方案素材），存于通用表 knowledge_entries；companies 等 6 张专用企业表**建了表但没有任何 API 写入**（grep 无 insert into companies）。
- 检索：`list_knowledge_entries`（L488）仅 6 字段 `LIKE %q%`；**无语义召回**（knowledge_entries 不进 Chroma，Chroma 只索引招标文件 document_chunks）、无编号/型号/金额/日期精确匹配字段索引。
- 企业知识→生成链：bid_section_writer 的 context 只含项目侧抽取表（bid_section_writer.py L97-122），**不含任何企业知识库数据** → "证据支撑生成"未打通。

### e. 响应矩阵/合规矩阵 — **MISSING**
全仓库无 requirement×response 覆盖关系、无偏离表/响应表生成（grep response/compliance matrix 无实现；README"后续计划"承认"增加废标项检查和响应完整性检查"）。最近似的只有 content_review 的模块级覆盖率（不是逐条要求映射）和 outline 的"评分响应索引建议"静态清单。

### f. 目录生成与分章节生成 — **IMPLEMENTED（基础版）**
- 目录：`generate_bid_outline`（bid_outline_generator.py L11）——**纯规则模板**（固定四册结构 + 资格/商务/技术/评分/废标风险分组目录 + 暗标特别提醒 L221-230），不是 LLM 生成；`_writing_requirement_chunks`（L233）用正则从 chunks 抽"投标文件组成/编制/格式/密封"线索。
- 分章节：`generate_bid_section_draft`（bid_section_writer.py L13）按单章调用 LLM（system 提示 L72-79：不得编造证书编号/金额/人员姓名，缺料用【待补充】占位，暗标章节避免可识别信息），失败回落 `build_local_section_draft`（L125）本地响应表模板；可单章重复生成（前端重调 API）。API：GET `/projects/{id}/bid-outline`、POST `/projects/{id}/bid-section-draft`（bid_parser_api.py L926/941）。
- 生成任务不持久：bid_generation_tasks 表只有 DDL（bid_database.py L426），无任何 insert（grep 仅 schema + 导出脚本描述）。

### g. 审校/校验 — **PARTIAL**
- 确定性检查：content_review_agent.py `MODULES` 5 模块共 **34 个检查项**（project_overview 10、business 8、technical 6、qualification 5、scoring 5），每项 (名称, 提取侧正则, 原文侧正则, severity high/medium/low)；状态四分：通过 / 原文存在但提取缺失 / 提取有内容但原文未命中 / 原文未直接命中（L204-223）；溯源评分 `_grounding_ratio`（L316）：从提取文本抽 ≤24 个术语（表格单元格或"键：值"值域，剔除 GENERIC_CELLS 与空白标记），10 字符分段 ≥45% 命中即算有据；模块分 = 55*覆盖率 + 30*溯源率 + 15*非空 − 12*高风险 − 6*中风险（L241-250），资格与评分模块权重 1.2（L268）。
- LLM 检查：POST `/bid-documents/content-review`（bid_parser_api.py L1191）手动触发，可选大模型深度审查（提示词 L597-634：复核结论/高风险问题表/需人工核对表/补充建议），失败保留正则报告。
- **无报价/工期/数量/资质有效期/签章/暗标专项确定性检查**——暗标仅有 profile 布尔位（正则判断）+ 目录提醒 + section_writer 提示语；签章仅有 DOCX 图片 visual_guess 关键词猜测。审查不能阻断任何流程（见 Q5）。

### h. 导出 — **PARTIAL**
- 前端汇总导出：renderer.js 三段式"标书生成工作台"（目录→逐章→汇总），`assembleGenerationDraft()` 拼接章节，`exportText` → `Blob` + `link.download`（renderer.js L3549-3553）导出 Markdown/txt 初稿。
- **无 docx/pdf 导出、无格式模板套版、无暗标格式处理**（README 后续计划自认"增加 Word/PDF 导出能力、模板套版能力"）。scripts/export_db_schema_excel.py 只导数据库 schema 到 xlsx，与标书导出无关。

### i. 状态持久化与恢复 — **PARTIAL**
- 已持久化：SQLite `data/bid_agent.db`（bid_database.py L16 DB_PATH），23 张表 + FTS5 虚拟表（document_chunks_fts，L127，tokenize=unicode61）；每次分析 `save_analysis_result`（L769）新建 project_id/document_id，链式写入 sections→chunks→profile→五模块表→review_findings→extraction_runs→Chroma 索引（chunk_embeddings 记录 SQLite chunk_id↔Chroma vector_id 映射，L292-300）。记录级 `confirmed_status`（未确认/已确认）+ `update_record_confirmed_status` API（人工确认位）。
- 未持久化：生成环节（章节草稿只在前端 JS 对象 generationSectionDrafts，renderer.js L1548，刷新即失）；**无中断恢复/断点续跑**——再次解析同文件会生成全新 project_id，无 upsert/去重（无 file_hash）；extraction_runs 只在成功落库时写一条"成功"，无进行中状态机。

### j. 失败处理 — **PARTIAL**
- 多层降级链完整：structured JSON 失败→追加"只能输出 JSON"重试一次→整体回退 Markdown 批量（bid_analysis_service.py L320-396）；模块输出空→`_apply_local_module_fallbacks` 展示本地召回候选片段+“请人工核对”（L158-235）；think_many 失败→逐个 think（L423-430）；预筛失败→回退规则召回（L109-117）；Chroma/embedding 不可用→回退 SQLite FTS5→再回退计数计分（bid_vector_store.py L337-400）；LLM 不可用→本地模板草稿。
- **无重试/退避机制**：LLM_Invoke（llm_client.py）无 retry；预筛批处理 `return_exceptions=True` 静默吞错。人工兜底 = 前端编辑 Markdown 后 POST analyze-content 重跑（L1175）。

### k. 日志与可观测性 — **PARTIAL**
- 后端 print（`_safe_print` 打印模型调用与流式输出到 stdout），启动脚本写 logs/backend.out.log/err.log；SSE 接口把 stage/status/field_done 事件流给前端（bid_parser_api.py L1318+）。无结构化日志、trace id、指标、LLM 调用审计表（extraction_runs 有 llm_vendor/model 列但 save_analysis_result 未填，L859-875 只写 run_type/status）。

### l. 测试 — **MISSING**（0 个测试文件）

### m. Skill 文件 — **MISSING**（无 SKILL.md / .agents/ / .claude/ 任何技能文件）

### n. Dify DSL — **MISSING**（全仓库无 .yaml/.yml 工作流文件；grep app:/nodes:/edges: 无 Dify 特征）

### o. MCP Server — **MISSING**（无 fastmcp/modelcontextprotocol 任何引用；对外仅 FastAPI REST + SSE）

### p. LLM 调用方式 — **IMPLEMENTED**
- llm_client.py `LLM_Invoke`：OpenAI SDK 同步/异步/流式/JSON Schema response_format（`_json_schema_response_format` L232，strict:true），并发 `think_many` + `asyncio.Semaphore(LLM_MAX_CONCURRENCY=2)`；深度思考仅对 qwen/deepseek-r1 注入 `enable_thinking` extra_body + system 追加思考指令（L201-229）。
- 单 vendor：SiliconFlow（llm_model_config.py L12 `https://api.siliconflow.cn/v1`），11 个前端模型名→API id 映射；默认 Qwen/Qwen3-8B 轻量模型；预筛模型独立配置 BID_QUAL_PREFILTER_MODEL_ID。
- 提示词位置：bid_analysis_prompts.py（5 模块系统提示 + 全局上下文 + 专项约束）、bid_qualification_prefilter.py L16、bid_image_analysis.py L221-247（图片 AI 备注）、bid_parser_api.py L597（深度审查）、bid_section_writer.py L63-94（章节草稿）、plan_and_solve_agent.py（与主链无关的通用 Plan-and-Solve 演示）。

## 3. README 声明核对

| README 声称 | 判定 | 证据 |
|---|---|---|
| 支持 PDF/Word/图片/HTML 解析 | 已验证（HTML 有保留） | bid_parse_strategy.py L13-24、MinerU_pdf_parse_tool.py SUPPORTED_DOCUMENT_SUFFIXES 含 .html；本地方法不含 HTML，HTML 仅依赖 MinerU 云端 |
| PDF 类型识别（原生/扫描/混排）+ 两层智能解析 | 已验证 | bid_parse_strategy.py `classify_pdf_profile` L226；`_pdf_is_simple_text_file` bid_document_parser.py L189 |
| RAG 精细切片：小表按行、大表 overview+3 行 row_group、chunk 带 hierarchy_path/item_type/parent_table_header/importance_score/module/vector_filter | 已验证（有例外） | bid_database.py `_table_row_chunk` L2283、`_large_table_chunks` L2317（TABLE_ROW_GROUP_SIZE=3, LARGE_TABLE_ROW_THRESHOLD=20）、`_chunk_metadata` L2428。**例外**：该切片只对"标准 Markdown 表格"（有 `| --- |` 分隔行）生效；python-docx 兜底路径不产生标准表格行 → Word 兜底解析无行级切片；importance_score 除大表 overview=1.3 外恒为 1.0，并非智能评分 |
| 章节摘要 chunk（vector_role=section_summary, summary_of=section_id） | 已验证（"摘要"非 LLM 生成） | `_semantic_chunks_from_markdown` L2176-2192 取前 8 段前 1200 字符作"摘要"——是截断不是 LLM 摘要，README"调用一次 LLM 生成章节摘要"与实现不符（**夸大**，实际为文本截断） |
| 两阶段抽取（规则/正则/标题样式先出候选，LLM 仅补缺，只传局部上下文） | 已验证（触发条件极保守） | bid_rule_extractor.py L126-222；默认 BID_PROJECT_OVERVIEW_RULE_FIRST=true 时需 completeness<0.34 **且** section_tree<2 才触发 LLM——绝大多数情况纯规则直出 |
| 每条原子数据保留 source_chunk_id/source_text/source_heading/evidence_snippet | 已验证（仅 JSON Schema 模式） | bid_structured_extraction.py L301；默认 Markdown 模式无此保证（README 也写明"需要强结构化入库时可开启"） |
| 金额统一 CNY 数值/期限日历天/日期 ISO | 已验证（基础版） | `_normalize_money`/`_normalize_time` bid_database.py L1589-1627（月*30、年*365 的粗换算） |
| SQLite FTS5 + BM25 关键词召回，未命中回退轻量计分 | 已验证 | document_chunks_fts L127；`_search_project_chunks_fts` bid_vector_store.py L403；`_search_project_chunks_count_candidates` 回退 |
| bge-large-zh-v1.5 向量 + bge-reranker-v2-m3 重排 + chunk_embeddings 映射 + 删项目同步删向量 | 已验证 | bid_vector_store.py L47-95/L189-278、`delete_project_vectors` L173 |
| 审查：正则覆盖率+三态区分+证据片段+溯源评分+可选大模型深度审查 | 已验证 | content_review_agent.py；POST /bid-documents/content-review（手动触发） |
| "审查层 `[部分完成]`"、生成层"规划中，已预留标书生成入口" | 部分夸大 | 生成层实际已超出"规划中"：bid_outline_generator/bid_section_writer/前端工作台已可用；但反向看 README"功能概览→生成主流程"又如实描述了三步工作台——README 内部前后小节不完全一致 |
| 知识库 SQLite Demo + localStorage 兜底 | 已验证 | /knowledge/* 接口 + renderer.js L2277-2285 KNOWLEDGE_STORAGE_KEY |
| 知识库八类资产 | 已验证（表已建） | companies/company_qualifications/... 6 张专用表存在但**无任何写入 API**，实际数据全走通用 knowledge_entries 表（专用表=SPEC_ONLY） |
| 标书目录生成浮层 + 生成工作台三步 + 导出 Markdown 初稿 | 已验证 | renderer.js L1380-1560、bid_outline_generator、bid_section_writer；导出为 Blob 下载 |
| 六层能力之"辅助决策层[规划中]" | SPEC_ONLY | 无任何代码 |
| "投标文件提交截止时间等 16 字段按钮字段" | 已验证 | PROJECT_OVERVIEW 16 字段（bid_analysis_prompts.py L27-44）与前端按钮（README 前端展示节） |

## 4. 真实执行链路重建

```mermaid
flowchart TD
    A[输入文件 PDF/DOCX/图片/HTML] --> B[预检与分流 inspect_document_profile / classify_pdf_profile]
    B --> C[解析层 pdfplumber | MinerU vlm/pipeline/parallel | docx2python+OCR | pymupdf4llm/docling]
    C --> D[结构还原 split_bid_markdown_sections → BidDocumentSection 列表]
    D --> E[模块混合召回 bid_section_retriever 宽关键词+语义query+正负加权+Top截断]
    D --> F[资格/废标预筛 轻量LLM逐章标category+confidence]
    E --> G[全局上下文 正则第一阶段 project_profile+section_tree<br/>条件触发 LLM 第二阶段补全]
    F --> H1
    G --> H1[四模块并发 LLM 抽取 Markdown 默认 / JSON Schema 可选]
    H1 --> I[输出清洗 extraction_cleaner 表格行/句子/《材料》去重]
    I --> J[(SQLite 23表+FTS5: sections/chunks/五模块表/review_findings/extraction_runs)]
    J --> K[(Chroma 向量索引 chunk_embeddings 映射)]
    J --> L[内容审查 34项正则覆盖率+溯源评分 → review_findings]
    J --> M[目录生成 规则模板 bid_outline_generator]
    M --> N[逐章草稿 LLM bid_section_writer + 本地模板兜底]
    N --> O[前端汇总 导出 Markdown/txt Blob]
    E2[企业知识库 knowledge_entries LIKE检索] -.未打通生成链.-> N
    P[响应矩阵 requirement×response] -.缺失.-> N
    Q[docx/pdf 导出/模板套版/断点续跑] -.缺失.-> O
```

| 节点 | 入口(文件+函数) | 输入输出结构 | 模型/服务 | 持久化 | 失败处理 | 状态 |
|---|---|---|---|---|---|---|
| 解析 | bid_document_parser.py `parse_bid_document` L54 | → List[BidDocumentSection]{index,title,level,content,markdown,metadata{title_path,tables,images,page_start/end}} | MinerU 云 API / 本地库 | document_sections + document_chunks | 4 类 PDF 分流 + 逐路 RuntimeError 带 hint | IMPLEMENTED |
| 召回 | bid_section_retriever.py `retrieve_sections_for_module` L124 | sections → 模块候选 BidDocumentSection（命中窗 ±context_chars 合并，评分 hits*3+title*5+直接命中4+标题boost12+语义分+表格3+数值2−负向4） | 无 | 无（内存） | 无命中→兜底前 8 章开头 | IMPLEMENTED |
| 预筛 | bid_qualification_prefilter.py `prefilter_qualification_sections` L111 | 规则召回→4500 字符窗→batch 6 → hits{chunk_id,category,confidence,reason,evidence_keywords} | Qwen3-8B（轻量） | 无 | 整体失败→退规则召回，不影响主链 | IMPLEMENTED |
| 全局上下文 | bid_rule_extractor.py `extract_rule_global_context` L126 + bid_analysis_prompts.py `build_global_context_messages_from_sections` L647 | {project_profile(16中文字段), section_tree[{section_id S#,title,level,title_path,page_start/end,module_hint,rule_confidence}], extraction_meta} | 主 LLM（条件触发） | project_profile 表（confidence 固定 0.7） | 规则兜底直出 | IMPLEMENTED |
| 四模块抽取 | bid_analysis_service.py L320-430 + bid_structured_extraction.py | Markdown 文本 或 JSON{business_requirements[]/technical_requirements[]/qualification_requirements[]+rejection_items[]/scoring_items[]}，每条含 4 个溯源字段+enum | 主 LLM（SiliconFlow） | 5 张业务表 | structured→markdown→本地候选片段三级回退 | IMPLEMENTED（默认 Markdown） |
| 清洗 | extraction_cleaner.py `clean_analysis_dict` L19 | 5 字段文本去重 | 无 | 入库前再清 | — | IMPLEMENTED |
| 入库 | bid_database.py `save_analysis_result` L769 | → 23 表 + FTS5 + Chroma | bge-large-zh-v1.5 | data/bid_agent.db + .chroma | try/except pass（落库失败不中断分析返回） | IMPLEMENTED |
| 审查 | content_review_agent.py `build_content_review` L75 | sections+extracted → {score,level,modules[34项],markdown}；LLM 复核拼接"大模型深度审查"节 | 可选 LLM | review_findings 表（按关键词筛段入库 L1898） | LLM 失败保留正则报告 | PARTIAL（无专项业务校验、无阻断） |
| 目录 | bid_outline_generator.py `generate_bid_outline` L11 | project_detail → outline_markdown（规则模板） | 无 LLM | 无 | Project not found 抛错 | IMPLEMENTED（规则版） |
| 分章草稿 | bid_section_writer.py `generate_bid_section_draft` L13 | section_title+outline+context → draft_markdown | 主 LLM | **无**（仅前端内存） | LLM 失败→本地模板 | IMPLEMENTED（不持久） |
| 汇总导出 | renderer.js `assembleGenerationDraft`/`exportText` L1390/L3549 | JS 内存草稿 → Markdown/txt 下载 | 无 | **无** | — | PARTIAL（仅 Markdown；无 docx/pdf） |
| 响应矩阵 | — | — | — | — | — | MISSING |
| 企业证据关联 | knowledge_entries 仅 LIKE 检索 | — | — | — | — | PARTIAL（未进生成链） |

**链路判定：解析→抽取→入库→审查→目录→分章→Markdown 导出为"前半强、中段可用、末端弱"的部分链；响应矩阵、企业证据、docx/pdf 导出、断点恢复完全缺失。**

## 5. 重点审计问题

**Q1 超长文件/附件/表格/扫描件处理？**
- 超长 PDF：pypdf 按 30 页一段切分并发 MinerU（`_chunk_contiguous_pages` L359），按页序合并 markdown（L322-325）；单 chunk 失败即 RuntimeError 整体失败，无部分成功降级。LLM 侧防截断：每模块 max_chars=36000 候选预算 + 命中点 ±1600 字符窗口（`_hit_windows` L335，窗口间距 ≤500 字符合并）；评分模块再压（`sections_to_scoring_context` L511，命中行压缩，仍 36k 上限）。
- 条款丢失防线：①宽召回"任何关键词命中即召回"+前后邻节（neighbor_sections=1）②资格/废标加轻量模型逐章预筛（思路.md L9-13 明确动机："废标项有时隐藏在非独立章节，按标题召回容易漏"）③content_review 34 项正则可发现"原文存在但提取缺失"。
- 残余风险：max_chars 截断仍可能丢（Top12 候选后按预算硬切 L225-240）；`_guess_page_number` 无页码时溯源失效；表格跨页无合并（README 自认）；扫描件完全依赖 MinerU 云端可用性。

**Q2 六类要求如何统一成结构化条款清单？**
未统一成单一清单，是"五张表"模型：business_requirements / technical_requirements / qualification_requirements / rejection_items / scoring_items（+project_profile 存投标人须知）。统一骨架为每表必带：`id, project_id, source_heading, item_sequence, source_text, metadata_json, chunk_id, confirmed_status, created_at`（bid_database.py L180-275）。通用结构化 schema（bid_structured_extraction.py L304-501）以 rejection_items 为例：
```
rejection_items[]: {sequence_no, rejection_item, specific_behavior,
  risk_level∈[高,中,低,未明确], legal_nature∈[资格性,符合性,响应性,其他],
  related_module, source_chunk_id, source_text, source_heading, evidence_snippet}
```
金额/期限/日期在 metadata_json 统一为 `{amount_cny, amount_currency:"CNY", duration_days, date_iso}`（L1589-1627）。**值得注意：project_profile 与 rule extractor 的 dict 键是中文字段名**（"项目名称"/"是否为暗标"），入库再映射英文列——借鉴时建议改为双语键。

**Q3 每条要求如何关联原文/证据/章节/审校结果？有无 ID 体系？**
有部分 ID 体系：`prj_ hex` / `doc_ hex` / `sec_ hex` / `chk_ hex` / `biz_|tech_|qual_|rej_|score_|rf_ hex`（save_analysis_result L782+）；跨模块引用经 metadata_json 的 `related_tech_requirement_ids/related_scoring_item_ids`（`_related_record_ids` L1630：关键词重合分≥2 + source_chunk_id 相同加 5 分）→ 商务↔技术↔评分弱关联（关键词计分，非确定性映射）。chunks 与业务表的 chunk_id 列关联（仅 JSON 模式真实回填）。审校结果 review_findings 不与具体 requirement 行关联（只有 module 字符串）。页码列存在但未回填（见 2c）。

**Q4 企业资料检索是否同时支持语义召回与精确匹配？**
否。仅 `LIKE %q%` 六字段（title/tags/date_text/files/content/notes，bid_database.py L501-505）。无 FTS、无向量、无编号/型号/金额/日期字段化精确匹配；Chroma 只覆盖招标文件 chunks。资质有效期表列（company_qualifications.expire_date）存在但无过期检查逻辑。

**Q5 无证据/证据过期/资格不满足时如何阻止错误内容进入定稿？**
**无硬阻断机制。** 全链没有任何 gate：审查报告只生成不拦截；confirmed_status 只是记录字段；section_writer 仅靠 prompt 软约束"不要编造……使用【待补充】占位"（bid_section_writer.py L76）；导出无校验。人审是唯一兜底（前端展示+确认按钮+复核表）。

**Q6 章节能否拆成可单独执行/重试/修改/验证的任务？**
部分可以。单章粒度存在（POST bid-section-draft 按 section_title 生成；前端可逐章重生成/编辑）；但无"任务"抽象：不落库、无任务状态/依赖/验证钩子，章节列表来自对目录 markdown 的前端正则解析（`parseGenerationOutlineSections` renderer.js L1420，≤80 节），刷新即丢。

**Q7 报价/工期/数量/资质有效期/签章/暗标检查，哪些确定性、哪些靠模型？**
确定性：模块关键词覆盖率、溯源评分、金额/日期/期限正则抽取、暗标/联合体/代理商/中小企业的宽正则布尔判断（`_yes_no_from_text` L345——**否定窗口仅识别 不接受|不允许|不得|否，"本项目不采用暗标"会误判为"是"**）、DOCX 图片公章/签字关键词猜测。靠模型：废标项/资格/评分/商务/技术的全部语义抽取、深度审查、章节正文。**报价合规、工期计算、数量核对、资质有效期、签章完备性：均无实现。**

**Q8 中断/换模型/补充文件后如何恢复？**
不支持。重分析=新 project_id 新库记录（无 file_hash 去重/增量更新）；换模型无影响（每次请求传 llm_model）；补充招标文件无法并入既有项目（一次上传一份文件）；Chroma 删项目时同步删除（delete_project_vectors）但项目间无合并。唯一"恢复"是人工在前端编辑内容后走 /analyze-content 重跑。

**Q9 可导入 Dify DSL / 可运行 MCP Server / 独立 Skill？**
**三者皆无。** 无任何 YAML；无 MCP 协议代码（仅 FastAPI REST + SSE）；无 SKILL.md。该仓库对目标架构（Agent+MCP+Skill）的直接可复用资产为零，价值在数据结构与算法思路。若要跑起来：需 Python 3.10-3.12 + requirements 22 包（含 torch 系 sentence-transformers、docling 重依赖）+ SiliconFlow API key + MinerU token + 首次 HF 模型下载（bge-large-zh-v1.5 + reranker），Windows 友好（.doc 转换用 PowerShell Word COM，L758-793）。

**Q10 哪些可合法复用？**
无许可证 → **代码、提示词文本、正则规则表一律不可复制**（版权默认保留）。可借鉴的"事实/思路"层（不受版权保护的功能性思路）：16 字段项目画像口径、34 项模块检查项清单、五表+统一溯源骨架、chunk metadata 字段集、两阶段抽取策略、混合召回加权公式思路、表格行切片/大表 overview+3行组策略、34 检查项的 severity 分级与四态判定。正则模式本身（如 `(?:项目名称|采购项目名称)\s*[：:]\s*...`）属高度功能性表达，**自行重新编写同义正则通常不构成侵权，但禁止逐字抄录其规则表并保持相同组织结构**；最稳妥做法是按字段清单自研实现。提示词文案是原创文字作品，不可照抄。**结论：仅可"clean-room 借鉴思路"，不可复用任何代码/文本；如需复用必须联系作者（github.com/RudyJunyu）取得授权。**

## 6. 复用价值与许可

- **可直接复用**：无（无许可证，一切代码/提示词/规则表复制均有法律风险）。
- **需改造后复用**：无（同上）。
- **仅可借鉴思路（重点清单）**：
  1. **中间数据结构 schema**（最值得借鉴）：`BidDocumentSection` + `metadata.tables[{headers,rows,row_cell_header_maps}]` + `document_chunks` 列集 {chunk_type, module, title_path, content, content_markdown, page_start/end, source_text, metadata_json{hierarchy_path,item_type,parent_table_header,importance_score,module,section_id,vector_filter{module,item_type,hierarchy_path}}} + table_overview/table_row_group{row_start,row_end,rows[{row_index,cells,cell_header_map}],parent_table_overview_id} + chunk_embeddings{chunk_id,embedding_model,embedding_dim,vector_store,vector_id} 映射表。
  2. 两阶段全局上下文：规则先出 + completeness 阈值决定是否花 LLM（`profile_completeness`/`needs_llm_global_completion` L213-222 是很好的成本控制模式）。
  3. 混合召回打分：`hits*3 + title_hits*5 + 直接命中4 + 标题boost12 + 语义词1.2/bigram0.6 + 表格3 + 数值2 − 负向4*次数 − 标题负向8`（bid_section_retriever.py L253-282），以及"宁可多标"的资格预筛提示结构（category+confidence+evidence_keywords）。
  4. 审查四态判定 + 溯源评分（10 字符分段 45% 命中）+ 加权评分公式。
  5. 五表统一溯源列 + metadata 内 amount_cny/duration_days/date_iso 标准化。
  6. DATABASE_SCHEMA_DESIGN.md 的完整表设计（684 行，含字段口径/示例，设计比实现更全——实现缺 file_hash/timeline_items/parse_quality_score 等，借鉴时以设计文档为参考、以实现为可行域）。
- **不建议采用**：中文键 dict 贯穿内存结构（入库再做映射，工程上易碎）；print 式日志；无重试的 LLM 调用；生成草稿不落库；per-page `## 第 N 页` 伪标题造成章节树噪声。
- **许可证结论**：无许可证 = 默认全版权保留。本仓库对本项目**只能做思路级参考**；任何源码引用、提示词照搬、正则规则表抄录都需要作者授权。其依赖树中的 pymupdf 为 AGPL-3.0，若目标系统未来借鉴其"本地 PDF 快速抽取"路线并闭源分发，需注意 AGPL 传染（当前代码未实际 import pymupdf，pymupdf4llm 路线为手动增强选项）。

## 7. 可靠性风险清单

| # | 风险 | 严重程度 | 证据 | 复现/验证 |
|---|---|---|---|---|
| 1 | **真实业务数据误提交**：.chroma/chroma.sqlite3 (15.3MB, 2,460 embeddings + 39,360 metadata 条，project_id=prj_25e7989f098a44728dcf04795f6b28f6，五模块齐全) 被提交；迁移 zip 内含 `data\dowell_bid_agent.db` 19MB 完整本地库 | **高** | git ls-files 含 .chroma/*；只读 sqlite3 查询确认 embeddings=2460、modules=商务内容/技术要求/投标人须知/评分要求/资格审查；unzip -l 见 dowell_bid_agent.db | `git ls-files \| grep chroma`；sqlite3 只读打开 chroma.sqlite3 |
| 2 | .gitignore 漏 .chroma/ 与 *.zip → 每次解析都会把用户数据再次写入被跟踪目录 | 高 | .gitignore 无 .chroma/.zip 条目；CHROMA_PERSIST_DIR=.chroma 默认 | cat .gitignore |
| 3 | 无 LICENSE：复用即侵权 | 高 | git ls-files 无 LICENSE | — |
| 4 | 表格行级切片对 Word 不生效（兜底路径）且双表格解析器规则不一致：bid_document_parser._extract_markdown_tables_json（不要求分隔行）vs bid_database._parse_table_lines（无 `| --- |` 分隔行直接返回空） | 中-高 | bid_document_parser.py L1127-1141（`" | ".join(cells)` 无首尾管道）；bid_database.py L1977 `if separator_index <= 0: return []`；docx2python .text 的表格输出格式 UNVERIFIED（沙箱无法安装验证） | 读 _parse_table_lines 与 _extract_docx_table_lines 对照 |
| 5 | `_yes_no_from_text` 否定词表过窄（不接受/不允许/不得/否，窗口 60 字符）→ "不采用暗标/不设履约保证金" 等误判为"是" | 中 | bid_rule_extractor.py L345-352 | 读 L345-352 |
| 6 | 无重试/退避；llm 单点失败静默降级为"本地候选片段"，表面有内容实为未抽取 | 中 | llm_client.py 无 retry；bid_analysis_service.py L105-117 except: return [] | grep retry |
| 7 | save_analysis_result 外层 try/except pass（bid_analysis_service.py L495-504）：入库失败用户无感知，项目库缺数据 | 中 | L495-504 `except Exception: pass` | 读代码 |
| 8 | 页码溯源不可用：structured 路径不写 source_page_start/end；MinerU 无页码标记时 page_start=None | 中 | bid_database.py L1486-1511 insert 未含页码列；_guess_page_number L683 | 读 insert 语句 |
| 9 | 深度依赖外部服务：MinerU 云 token（扫描/混排 PDF 唯一出路）+ SiliconFlow key + HF 首次下载 bge 两模型；Windows .doc 转换依赖本机 Word | 中 | MinerU_pdf_parse_tool.py L18；llm_model_config.py L12；bid_document_parser.py L758 | 读依赖路径 |
| 10 | extraction_runs 不记录失败与模型信息（schema 有 llm_vendor/llm_model/prompt_version 列但只写 run_type/status="成功"）| 低 | bid_database.py L859-875 | 读 insert |
| 11 | SerpApi_search_tool.py import 未声明依赖 serpapi；plan_and_solve_agent.py 为与主链无关的通用演示（孤儿模块） | 低 | requirements.txt 无 serpapi；grep 引用仅 run_plan_and_solve.py | grep |
| 12 | 每页一个 section（`## 第 N 页` 伪标题）+ TOC 页码干扰 `_guess_page_number` | 低 | bid_document_parser.py L719/L1293 | 读 _parse_pdf_with_pdfplumber |

### 定向深挖补充结论（对应任务 8 项）
1. **两阶段抽取**：第一阶段规则集 = 11 组字段正则（FIELD_PATTERNS L33-73）+ 6 组时间正则（TIME_PATTERNS L75-82）+ 8+7+6 关键词组 + TITLE_RE 章节正则 + `_module_hint` 5 模块标题映射；第二阶段 LLM 提示 = GLOBAL_CONTEXT_SYSTEM_PROMPT（严格 JSON：project_profile 18 键 + section_tree 8 键）。**默认配置下第二阶段几乎不触发**（completeness<0.34 且章节<2），实质是"规则直出、LLM 兜底"。
2. **content_review_agent 不是废标规则库**：34 检查项中与废标相关的仅 1 项（`废标|无效投标|否决投标|投标无效|响应无效` 关键词存在性检查，L53）；真正的废标条款发现全靠资格模块 LLM 三表提示 + 轻量预筛。误报控制手段：GENERIC_CELLS/EMPTY_MARKERS 白名单过滤、grounding 分段命中 45% 阈值、证据片段人工复核提示；**无基于规则库的废标误报率数据（无测试、无评测集）**。
3. **表格行级切片**：见 2a/风险 4；小表逐行 chunk（item_type=表格行，table_size=small，cells+header_paths+cell_header_map+parent_table_header）；大表（>20 行）= table_overview（importance_score 1.3）+ 每 3 行 table_row_group（parent_table_overview_id 关联）。
4. **SQLite 表结构**：23 表 + FTS5 已验证（见 4 节表格）；xlsx 真实存在且由 scripts/export_db_schema_excel.py 从运行库导出（4 sheets，含表描述字典 L23-47）——初筛"有 xlsx 文档"属实。
5. **生成/导出后半链并非完全缺失**：06-09 至 06-14 提交补上了"规则目录生成 + 单章 LLM 草稿 + 前端工作台 + Markdown 导出"；缺的是 docx/pdf/模板/暗标导出与任务持久化。初筛"无后半链"结论已过时，需更正为"后半链基础版已存在、末端导出弱"。
6. **.chroma 误提交**：确认，且含真实项目数据（风险 1）。
7. **无许可证下复用规则思路**：见 Q10/第 6 节——字段清单/分类体系/评分策略可 clean-room 借鉴；代码、提示词文本、正则规则表的"表达"受版权保护，不可抄。
8. **解析中间数据结构值得借鉴**：值得——见第 6 节借鉴清单第 1 条的完整 schema（BidDocumentSection / tables JSON / document_chunks / table_overview+row_group / chunk_embeddings 五层结构）。
