# 初筛报告 — A 组候选仓库（Task ID: 3-b）

> 审计方式：纯静态检查（git ls-files / rg / 只读源码抽查），未安装依赖、未运行任何仓库代码。
> 浅克隆限制：提交数均为约 20 条上限内的计数，不代表全历史。
> 评估链条：解析 → 条款 → 证据 → 矩阵 → 章节 → 审校 → 导出。

---

## 1. FB208/OpenBidKit_Yibiao（3202★, JavaScript/Electron+C#, AGPL-3.0）

### 规模与构成
- 文件数：**727**（git ls-files）
- 扩展名粗分：.cjs 176、.tsx 90、.ts 62、.cs 61、.js 58、.png、.md、.css、.sql 19、.json
- 顶层结构：
  - `client/`（410 文件）Electron 41+ / React 19 / TS 桌面主应用（主进程 .cjs + 渲染层 .tsx）
  - `openxmlhelper/`（64 文件）独立 .NET 10 控制台，Word/OpenXML 文档内核（C#）
  - `analytics/`（97 文件）Cloudflare Worker + 仪表盘，应用使用量统计平台
  - `使用说明/`（61 文件）带截图的完整用户手册
  - `screenshots/`、`文章/`（宣传文章）、`.github/`、`.agents/skills/yibiao-user-manual/`（仓库维护用技能）、`sql/workspace_schema.sql`

### 提交活跃度
- 提交数（浅克隆）：21 条
- 最近 3 条：2026-10-21 优化atomgit上传链路 / 2026-10-21 清理存储空间功能 / 2026-10-20 解决生图类型被关闭bug → **非常活跃**

### 关键要素核查
- a. SKILL.md：`.agents/skills/yibiao-user-manual/SKILL.md`（仅用于用户手册维护，非标书生成技能）；另有 `skills-lock.json`（技能包 lockfile，引用 ibelick/ui-skills）
- b. Dify DSL：**未发现**（无 app:/graph:/nodes: 特征 yaml）
- c. MCP Server：**未发现**；Agent 工具走 Electron 内部 IPC（`client/electron/services/agent/agentToolEnvironment.cjs`、`agentOpenAiProxy.cjs`）
- d. 招标解析：`client/electron/services/bidAnalysisTask.cjs`、`bidSectionExtractionTask.cjs`（主进程任务）
- e. 废标/合规检查：**真实实现** — `client/src/shared/prompts/rejectionPrompts.ts`（"废标项检查输入 v1"结构化提示词，明确界定检查口径与忽略纸质事项）；`client/electron/ipc/rejectionCheckIpc.cjs`；另有暗标检查全家桶 `blindCheckAgent.cjs`/`blindCheckFixTask.cjs`/`blindCheckPresets.cjs` + C# 侧 `openxmlhelper/src/OpenXmlHelper/BlindCheck/*`（Inspect/Fix 分离）
- f. RAG/向量库：**未发现向量库**；知识库走 `client/electron/ipc/knowledgeBaseIpc.cjs`、`credentialLibraryService.cjs`（本地库，深度未验证）
- g. 提示词：`client/src/shared/prompts/{analysisPrompts,rejectionPrompts,jsonRepairPrompts,index}.ts`（结构化、版本化的提示词模块）
- h. 测试：仅 `client/electron/services/developerExpansionReplaceTest.cjs`（开发自测），**无系统化测试**
- i. 持久化：Electron 本地存储（`storageIpc.cjs`、`configStore.cjs`）+ `sql/workspace_schema.sql`（19 个 .sql 为 schema/迁移）
- j. 文档导出：`openxmlhelper/`（C# OpenXML 引擎：docx 结构修复、标题编号、属性修复）+ `exportIpc.cjs`、`templateIpc.cjs`；`openxmlhelper/开发说明.md` 明确"一行 JSON 协议、Main 懒启动"的**独立文档内核进程边界**——与我们"文档内核独立、经稳定接口提供"的架构高度同构

### README 核心声称
1. "易标投标工具箱 — AI 智能标书写作助手"（Electron 桌面应用）
2. 招标文件解析 → 目录生成 → 全局事实 → 正文生成 → Word 导出全流程（`使用说明/` 截图 07–11 印证）
3. 废标项检查 + 暗标检查（BlindCheck，含图片/颜色合规与自动修复）
4. 文档知识库、企业凭证库、查重（duplicateCheckIpc）
5. Electron 41+ / React 19 / Vite 7，trendshift 榜单项目

### 相关性评分：**4 / 5**
全链条闭环且废标/暗标检查为独家实现，但全部逻辑封装在 Electron 桌面端（.cjs 主进程），无可直接复用的服务端形态；技术栈 JS/C# 与目标 Python 后端不同构。

### 初筛建议：**INCLUDE**
一句话理由：废标项检查提示词 + 暗标 BlindCheck（Inspect/Fix 分离）+ C# OpenXML 独立文档内核（一行 JSON 协议）是本组独有的"审校与文档内核"参考样本，值得深度审计其协议设计与检查规则库。

---

## 2. Get00/BiaoShu-SKILL（186★, Python, Apache-2.0）

### 规模与构成
- 文件数：**56**
- 扩展名粗分：.md 29（含 27 个中文文件名模板）、.py 23、.json 2、.txt
- 顶层结构：`BiaoShu-writer-pro/` 单一技能包（SKILL.md + install.py + scripts/ 23 个 py + templates/ 27 个行业/文书模板 md + references/industry_configs.json + requirements.txt）+ README/LICENSE

### 提交活跃度
- 提交数（浅克隆）：9 条
- 最近 3 条：2026-09-24 README 加 star history / 2026-05-22 Update README ×2 → **2026-05 后核心代码基本冻结**

### 关键要素核查
- a. SKILL.md：**真实存在** `BiaoShu-writer-pro/SKILL.md`（YAML frontmatter：name: bid-writer-pro v2.2 + description，标准 Claude 技能格式）— IMPLEMENTED
- b. Dify DSL：**未发现**
- c. MCP Server：**未发现**
- d. 招标解析：`scripts/parse_bid_file.py`、`convert_pdf_to_md.py`、`convert_doc_to_md.py`、`convert_to_md.py`（PDF/DOCX/DOC/TXT/XLSX → Markdown 中转）
- e. 响应矩阵/合规：**部分** — `scripts/extract_scoring.py`（评分项/分值/权重提取）、`extract_requirements.py`（资质/技术/商务要求）、`check_word_count.py`（字数达标检查）；无废标项检查闭环
- f. RAG/向量库：**未发现**；"知识库"即 templates/ 行业指南 md + 遇新行业自动生成指南（`industry_content_generator.py`、`industry_detector.py`）
- g. 提示词：分散于 scripts/（generate_content.py、humanizer.py 等）+ templates/ 行业 md 作为领域知识
- h. 测试：**未发现**
- i. 持久化：无 DB；每次运行生成带时间戳独立输出目录（JSON 中间态落盘）
- j. 文档导出：`scripts/convert_to_docx.py`（python-docx）、`format_docx.py`（行业标准格式）、`generate_cover.py`、`generate_toc.py`、`generate_placeholder.py`（图片/表格/资质占位符）

### README 核心声称
1. "发送招标文件，自动生成符合行业标准的专业投标书"，14 步全自动流水线（`bid_writer_pipeline.py`：解析→评分→要求→大纲→并发写章节→字数检查→去痕→docx）
2. 8 大行业支持 + 行业自动检测 + 新行业自动创建指南（自我进化）
3. AI 去痕处理（humanizer.py）、智能占位符
4. 标书质量检查（对照模板检查完整性）
5. 面向 Claude 等 AI 助手的技能包（install.py 安装脚本）

### 相关性评分：**4 / 5**
本组唯一"纯 Skill 形态"的完整链条实现（解析→评分→要求→大纲→内容→检查→导出），与我们 Skill 体系可直接对标；短板是无服务端状态、无 RAG、无合规检查、无测试。

### 初筛建议：**INCLUDE**
一句话理由：作为"可重复执行流程的 Skill 打包范式"（SKILL.md + scripts + 行业知识模板 + 安装器）的一手参照，值得深挖其 14 步流水线的步骤切分与人审插入点设计。

---

## 3. Router0824/BidPilot-AI（102★, Python, AGPL-3.0）

### 规模与构成
- 文件数：**131**
- 扩展名粗分：.py 60、.vue 20、.js 10、.yaml 7、.png 7、.md 5
- 顶层结构：
  - `app/`（54 py）FastAPI 分层架构：api/v1（12 路由）、application（13 个服务）、agents、workflows（自研引擎）、domain/models、core
  - `frontend/`（37）Vue 3 工作台；`docs/`（截图）；`deploy/`+`docker/`；`tests/`；`modelscope_release/`

### 提交活跃度
- 提交数（浅克隆）：21 条
- 最近 3 条：2026-10-03 Refresh README / 2026-10-03 Release v1.1.0 / 2026-08-09 Polish README → **近期有 v1.1.0 发布**

### 关键要素核查
- a. SKILL.md：**未发现**
- b. Dify DSL：**未发现**（自研工作流引擎 `app/workflows/{engine,dependency_graph,nodes}.py`）
- c. MCP Server：**未发现**；内部 `app/agents/__init__.py` BaseAgent + LLM gateway（可 Mock）
- d. 招标解析：`app/application/document_service.py`、`word_template.py`（DOCX 模板字段校验）、`api/v1/productivity.py`
- e. 响应矩阵/合规：**真实实现** — `app/agents/planner_agent.py`（任务图含 extract_scoring/generate_matrix）、`app/agents/__init__.py: generate_matrix()`、`api/v1/bid.py:120 coverage-matrix` 端点、`application/evidence_service.py: list_matrix()`（证据追溯）；工作流状态机含 MATRIX_GENERATED→OUTLINE→DRAFTING→REVIEWING→READY_TO_EXPORT
- f. RAG/向量库：`application/knowledge_service.py` + `enterprise_service.py`（企业材料复用/引用），**未发现向量库/embedding**，疑为 DB 检索
- g. 提示词：内联于 agents（如 specialized_agents.py 的商务/资格标系统提示词，含"不得编造价格/证书"约束）
- h. 测试：`tests/test_llm_connection.py`、`tests/test_productivity.py`、`frontend/tests/*.spec.js`（Playwright）— PARTIAL
- i. 持久化：SQLAlchemy + SQLite（README 徽章），章节版本历史/内容保护/并发冲突检测（v1.1.0）
- j. 文档导出：`application/review_export_service.py`、`document_service.py`（Word 交付 + 范本下载）

### README 核心声称
1. "投标团队 AI Agent 工作台"：项目待办 → 章节编写 → 企业材料复用 → 证据追溯 → 审查确认 → Word 交付
2. 招标文件解析 + 补遗影响分析（addendum_agent）
3. 轻量 Mock 模式：无 API Key 可体验全流程；真实生成失败不冒充成功
4. 人工修改保留历史版本、重要承诺人工确认
5. 注意：README 徽章写 Apache-2.0，但 LICENSE 文件实为 **AGPL-3.0**（以 LICENSE 为准）

### 相关性评分：**4 / 5**
服务端形态的完整工作流状态机（含矩阵/证据/人审 gate），与目标后端最同构的范本之一；但 LLM 调用多为 Mock/兜底 canned 文本，真实生成链路深度存疑，且 AGPL 传染性强。

### 初筛建议：**INCLUDE**
一句话理由：其 workflow 状态机的状态枚举（facts_confirmed→matrix_generated→outline→draft→review→export）+ coverage-matrix 证据服务可直接映射我们的后端状态模型，值得审计其人审确认节点设计。

---

## 4. zeronezer/bidcraft（73★, Python, Apache-2.0）

### 规模与构成
- 文件数：**121**
- 扩展名粗分：.py 60、.vue 12、.md 18、.png/jpg 12、.js 4、.html 4
- 顶层结构：
  - `backend/`（54 py）FastAPI：`app/agents/`（13 个智能体：orchestrate/parser/tender/requirement/heading/writer/method/knowledge/fact/lot/experience/chat/compile_graph）+ `app/services/`（20 个服务）
  - `frontend/`（20）Vue 3 三栏工作台；`docs/`；`思路/`（8 篇设计决策文章）；`tests/`（5 个 probe/verify 脚本）；`scripts/`

### 提交活跃度
- 提交数（浅克隆）：**2 条**（2026-09-17 初始 feat、2026-10-09 Add files via upload）→ **一次性上传式仓库，无迭代历史**

### 关键要素核查
- a. SKILL.md：**未发现**（根 `AGENTS.md` 是面向 AI 编程助手的"把项目跑起来"指引，非业务技能）
- b. Dify DSL：**未发现**
- c. MCP Server：**未发现**；编排用 **LangGraph**（`backend/app/agents/compile_graph.py`：StateGraph + `interrupt()` 人工把关 + PyMySQLSaver 检查点，进程重启可恢复）
- d. 招标解析：`services/docx_parser.py`（python-docx 对象级切章）、`services/mineru.py`（MinerU 云端 API 解析 PDF/图片）、pypdf/pdfplumber；`思路/05-为什么用-MinerU-解析-PDF.md`
- e. 响应矩阵/合规：**部分** — `services/requirement_service.py`、`思路/06-如何保障生成准确性与降低幻觉.md`（设计层面）；招标目录最高优先级建模（compile_graph.py tender_toc）
- f. RAG/向量库：**刻意不用 RAG** — `services/knowledge_service.py` 走 "LLM-Wiki 知识页" 路线（`思路/01-为什么用-LLM-Wiki-而不是-RAG.md`、`02-如何让-AI-精准命中知识.md`）；未发现向量库
- g. 提示词：内联于 13 个 agents（含防重复策略 `思路/07-如何保证内容不重复.md`）
- h. 测试：`tests/probe_*.py`、`verify_*.py` 为人工探针脚本，**非单元测试**
- i. 持久化：MySQL（pymysql + `core/database.py`）+ LangGraph MySQL checkpoint（PyMySQLSaver）
- j. 文档导出：`services/spreadsheet.py`、`doc_convert.py`、`compile_service.py`（docx 装配）

### README 核心声称
1. "标书匠 — 对话式工程标书编制智能体"，聚焦施工组织设计（工程标）
2. 把"抄改拼装 80%"交给 AI：历史施组 → 结构化知识页（怎么写/要点/典型表图）
3. 全局事实表：每条数字有出处、可编辑、可追溯（fact_agent/fact_service）
4. Mermaid 流程/组织图，编辑器内实时渲染
5. 100% 免费开源（Apache-2.0），编制周期从数周压到数天

### 相关性评分：**4 / 5**
工程标（施组）垂直场景的 LangGraph 编排 + 事实溯源 + 反幻觉设计文档（思路 01–08）质量高；但仅 2 次提交、无真正测试、无向量检索路线（是设计选择非缺陷）。

### 初筛建议：**INCLUDE**
一句话理由：`compile_graph.py` 的 interrupt() 人审门 + PyMySQLSaver 断点续跑实现，与 8 篇"思路"设计文章构成一套可直接借鉴的"人工把关型编排"工程样本。

---

## 5. NewbieCoderLab/ai_bidding（62★, Python, MIT）

### 规模与构成
- 文件数：**119**
- 扩展名粗分：.py 82、.vue 13、.md 9、.js 4、.svg 3、.sql
- 顶层结构：
  - `services/`（31 py，含 `services/v2/` 12 个新架构服务：工作台、章节生成、引用、图片规划、上下文构建）
  - `tests/`（**21 个 pytest 文件**）+ `api/`（Flask 蓝图，含 v2）+ `core/`（db/celery/llm_providers/pg）+ `storage/`（vector_store）+ `export/`（md_to_word、flowchart_renderer）+ `front/`（Vue3+Tiptap）+ `migrations/postgres/001_rag_pgvector.sql` + `docs/`（PRD/架构文档 + superpowers specs/plans）

### 提交活跃度
- 提交数（浅克隆）：20 条
- 最近 3 条：2026-06-24 merge: sync remote master / 2026-06-24 feat: 工作台编排 ×2 → **2026-06 后停更**

### 关键要素核查
- a. SKILL.md：**未发现**（`docs/superpowers/` 是 AI 编程代理的 spec/plan 文档，可佐证其开发方法论）
- b. Dify DSL：**未发现**
- c. MCP Server：**未发现**（Flask REST + Celery 异步任务）
- d. 招标解析：`services/tender_format_parser.py`（**响应文件格式章节**正则识别，含"投标函/偏离表/格式"等模板关键词分类）+ `services/ingestion_service.py`（Mammoth/PyPDF2）
- e. 响应矩阵/合规：`services/agent_orchestrator.py:796` 输出"响应矩阵覆盖率：xx%"（要求覆盖统计 — IMPLEMENTED）+ `services/template_validation.py` + `services/v2/citation_service.py`（引用核验）
- f. RAG/向量库：**真实实现且多后端** — `services/file_to_chroma.py`（Chroma）、`services/rag/hybrid_search.py` + `reranker.py`（混合检索+重排）、`storage/vector_store.py`、`migrations/postgres/001_rag_pgvector.sql`（PGVector+FTS 主路线）、`scripts/check_milvus.py`（Milvus 降级）
- g. 提示词：内联于 services/v2/* 与 agent_orchestrator（选区改写、章节重写、大纲）
- h. 测试：**本组最佳** — 21 个 pytest：`test_tender_format_parser.py`、`test_rag_hybrid_search.py`、`test_v2_project_generation_service.py`、`test_outline_builder.py`、`test_template_merge.py` 等
- i. 持久化：MySQL（PyMySQL，core/db.py）+ Celery + generation_cache_service + pgvector
- j. 文档导出：`export/md_to_word.py`（python-docx，含中文字体/段落样式处理）+ `export/flowchart_renderer.py`（Mermaid 渲染）+ OnlyOffice 在线编辑集成

### README 核心声称
1. "招标文件解析、项目资料沉淀、章节生成、AI 改写、在线编辑、Word 导出"完整工作流
2. 企业知识库 RAG：PGVector+FTS+Rerank，ChromaDB/Milvus 作开发降级
3. 多模型配置（DeepSeek/通义/方舟/Kimi/OpenAI/MiMo，OpenAI 兼容）
4. 选区改写（不重写整章）、章节级重写、Tiptap 三栏工作台
5. 技术栈 Flask + MySQL + Vue3，MIT 许可

### 相关性评分：**5 / 5**
与本组评估链条一一对应：解析(tender_format_parser)→条款(extract)→证据(citation_service)→矩阵(覆盖率统计)→章节(v2 chapter_generation)→审校(technical_review)→导出(md_to_word)，MIT 许可 + 21 个测试 + RAG 多后端，是目标后端最直接的同构样本。

### 初筛建议：**INCLUDE（本组最高优先级）**
一句话理由：许可证最干净（MIT）、链条最完整、唯一带成体系测试，其 services/v2 分层（context_builder/chapter_strategy/citation）值得逐文件深审。

---

## 6. aigc-open/tender-cli（48★, Python, Apache-2.0）

### 规模与构成
- 文件数：**32**
- 扩展名粗分：.py 25、.md 2、其余为 toml/配置
- 顶层结构：`src/tender_cli/`（core：config/conversation/project_manager/tender_ai；mcp_tools：base/mcp_server/mcp_agent/file_tools/tender_tools/content_tools/document_tools；prompts/prompt_library；utils/ai_client）+ `examples/`（5 个含 MCP_BASE_USAGE.md）+ `tests/test_basic.py` + `design.MD`

### 提交活跃度
- 提交数（浅克隆）：**2 条**（2025-09-12 Initial commit、2025-09-13 README 更新）→ **一次性项目，已停滞约一年**

### 关键要素核查
- a. SKILL.md：**未发现**
- b. Dify DSL：**未发现**
- c. MCP Server：**真实实现** — `src/tender_cli/mcp_tools/base.py` 首行 `from mcp.server.fastmcp import FastMCP`（官方 MCP SDK）+ OpenAI Agents SDK（`Agent, Runner, function_tool, MCPServer, MCPServerStdio`）；`mcp_server.py` 聚合 file/tender/content/document 四类工具；`examples/MCP_BASE_USAGE.md` — IMPLEMENTED
- d. 招标解析：`mcp_tools/tender_tools.py`（extract_pdf_content、解析招标要求、评分标准分析）
- e. 响应矩阵/合规：仅提示词层（analyze_tender/评分标准），无检查闭环
- f. RAG/向量库：**未发现**
- g. 提示词：`prompts/prompt_library.py` — 9 个中文提示词（system/analyze_intent/analyze_tender/generate_outline/generate_content/optimize_content/task_planning/general_chat/export_docx）— IMPLEMENTED
- h. 测试：`tests/test_basic.py`（仅 Config/ProjectManager/FileTools 基础测试）
- i. 持久化：`core/project_manager.py` JSON 落盘工作区/项目（无 DB）
- j. 文档导出：`mcp_tools/document_tools.py`（导出 Word/PDF、合并章节、应用模板）

### README 核心声称
1. "一个命令，智能对话，完成所有标书工作"的 CLI 助手
2. 内置 MCP 工具集：文件操作/招标处理/内容生成/文档处理
3. 智能任务规划：自动分解 4 阶段 20+ 子任务 + 时间预估
4. 上下文记忆、多轮对话、自适应调整

### 相关性评分：**3 / 5**
规模小且停更一年，功能深度浅（无 RAG/DB/合规闭环）；但它是本组**唯一真实 FastMCP + OpenAI Agents SDK 落地样本**，与目标架构"Agent 经 MCP 调用业务能力"直接对口。

### 初筛建议：**INCLUDE（限定范围：MCP 集成范式参考）**
一句话理由：作为"MCP 工具切分 + 提示词库 + 代理循环"的最小可行参考实现值得半天级快审，不足以支撑全链条深审。

---

## 7. RudyJunyu/Bid_Agent（38★, Python, **无许可证**）

### 规模与构成
- 文件数：**47**
- 扩展名粗分：.py 23、.bin 4（**.chroma/ 向量二进制数据被提交**）、.js 3、.md 2、.bat 2、.zip 1（**迁移 zip 被提交**）、.xlsx、.sqlite3、.pickle — 仓库卫生差
- 顶层结构：根目录平铺约 20 个管线模块（bid_parse_strategy / bid_document_parser / bid_rule_extractor / bid_structured_extraction / bid_qualification_prefilter / bid_outline_generator / bid_section_retriever / bid_section_writer / content_review_agent / bid_analysis_service / bid_analysis_prompts / plan_and_solve_agent / bid_vector_store / bid_database / MinerU_pdf_parse_tool / SerpApi_search_tool / bid_parser_api）+ `electron_client/`（简易桌面壳）+ `scripts/` + `docs/`（数据库表结构 xlsx）+ `DATABASE_SCHEMA_DESIGN.md` + `思路.md`

### 提交活跃度
- 提交数（浅克隆）：19 条
- 最近 3 条：2026-06-14 Merge remote master / 2026-06-14 update ×2 → **2026-06 后停更**

### 关键要素核查
- a. SKILL.md：**未发现**
- b. Dify DSL：**未发现**
- c. MCP Server：**未发现**（`bid_parser_api.py` 为普通 FastAPI REST）
- d. 招标解析：**本组最强** — `MinerU_pdf_parse_tool.py`（MinerU 集成）、`bid_parse_strategy.py`、`bid_document_parser.py`（BidDocumentSection 对象）、`bid_rule_extractor.py`（两阶段抽取：正则 project_profile/section_tree + LLM 局部补全）、README 记载 RAG 精细切片设计（小表按行、大表 table_overview + 3 行 table_row_group、chunk 带 hierarchy_path/importance_score/module 元数据）
- e. 响应矩阵/合规检查：**规则引擎式实现** — `bid_rule_extractor.py`（废标项/资格审查等模块正则抽取）、`content_review_agent.py`（对抽取模块做正则复查，含 high/medium 严重度）、`bid_qualification_prefilter.py`
- f. RAG/向量库：`bid_vector_store.py`（chromadb PersistentClient，env 开关可选，SQLite 记录 chunk 映射）；.chroma/ 运行时数据被误提交
- g. 提示词：`bid_analysis_prompts.py`（集中提示词模块）+ `plan_and_solve_agent.py`（Planner/Executor 模板）
- h. 测试：**未发现**
- i. 持久化：`bid_database.py`（sqlite3，DB_PATH）+ `DATABASE_SCHEMA_DESIGN.md` + `docs/招投标智能体数据库表结构.xlsx`（**完整表结构设计文档，可直接参考**）
- j. 文档导出：`scripts/export_db_schema_excel.py`（openpyxl，仅 schema 导出）；**无标书 docx 导出**

### README 核心声称
1. 六层能力建设：文件解析层 → 结构化抽取层（可入库、可溯源、可检索、可生成的原子数据）→ 后续核查/生成/审查/辅助决策
2. 支持 PDF/Word/图片/HTML，原生文本/扫描件/图文混排/表格结构识别
3. RAG 精细切片策略（表格行级 + 元数据标注）
4. FastAPI 后端 + Electron 前端本地桌面工具
5. MinerU Token + SerpAPI 搜索工具集成

### 相关性评分：**3.5 / 5**
"解析 → 条款/废标项抽取 → 规则核查"前半链条扎实且切片设计文档化，但**无标书生成与导出后半链条**、无测试、无许可证。

### 初筛建议：**INCLUDE（带许可证警示）**
一句话理由：招标文件解析与结构化抽取（含废标项正则规则库、表格行级切片、SQLite 表结构设计）是可直接移植的前置能力样本，但**无许可证 = 默认全版权保留，仅供学习参考，禁止复用代码**；仓库卫生（提交 .chroma 二进制与迁移 zip）反映工程成熟度低。

---

## 汇总表

| # | 仓库 | 文件数 | 提交(浅) | 最近提交 | 评分 | 建议 |
|---|------|--------|----------|----------|------|------|
| 1 | FB208/OpenBidKit_Yibiao | 727 | 21 | 2026-10-21 | 4 | INCLUDE |
| 2 | Get00/BiaoShu-SKILL | 56 | 9 | 2026-09-24 | 4 | INCLUDE |
| 3 | Router0824/BidPilot-AI | 131 | 21 | 2026-10-03 | 4 | INCLUDE |
| 4 | zeronezer/bidcraft | 121 | 2 | 2026-10-09 | 4 | INCLUDE |
| 5 | NewbieCoderLab/ai_bidding | 119 | 20 | 2026-06-24 | 5 | INCLUDE（最高优先） |
| 6 | aigc-open/tender-cli | 32 | 2 | 2025-09-13 | 3 | INCLUDE（限定 MCP 参考） |
| 7 | RudyJunyu/Bid_Agent | 47 | 19 | 2026-06-14 | 3.5 | INCLUDE（无许可证警示） |

### 横向观察
- **无人用 Dify DSL**：7 个候选全部未发现 Dify 工作流文件，编排实现分别为 自研引擎(Router0824)、LangGraph(zeronezer)、Celery+自编排(NewbieCoderLab)、Electron 内部 IPC(FB208)、OpenAI Agents SDK(aigc-open)、Plan-and-Solve 自循环(RudyJunyu)。
- **无人有 Claude 式 SKILL.md 的标书技能**，除 Get00（恰好是纯技能包）外均无 a 项命中；FB208 的 .agents/ 是维护技能而非业务技能。
- **MCP 仅 aigc-open 真实落地**（FastMCP + MCPServerStdio），其余声称 Agent 的仓库均为内部 Agent 抽象。
- 许可证分布：MIT 1（NewbieCoderLab）、Apache-2.0 3（Get00、zeronezer、aigc-open）、AGPL-3.0 2（FB208、Router0824）、无许可证 1（RudyJunyu）。目标系统若复用代码需优先 MIT/Apache 两个。
- 明显 README 徽章错误：Router0824 README 徽章标 Apache-2.0，实际 LICENSE 为 AGPL-3.0；Get00 技能内 README 徽章标 MIT，实际 LICENSE 为 Apache-2.0 — 引用时以 LICENSE 文件为准。

### 最值得深挖 Top 3（建议深度审计顺序）
1. **NewbieCoderLab/ai_bidding** — MIT + 全链条 + 21 个 pytest + 多后端 RAG（PGVector/Chroma/Milvus），与目标后端同构度最高，产出物可直接对标逐模块移植评估。
2. **FB208/OpenBidKit_Yibiao** — 独家"废标项检查提示词 + 暗标 BlindCheck（Inspect/Fix 分离）+ C# OpenXML 独立文档内核（单行 JSON 协议、懒启动进程）"，对目标"文档内核独立 + 稳定接口 + 审校能力"是唯一现成参照（注意 AGPL 只可学习设计、不可抄代码）。
3. **Router0824/BidPilot-AI** — 服务端工作流状态机（facts_confirmed→matrix→outline→draft→review→export）+ coverage-matrix 证据服务 + 人审确认门，是后端状态模型与"重要承诺人工确认"的最佳流程参照（AGPL 同样只可学设计）。
（次选补充：zeronezer/bidcraft 的 LangGraph interrupt+MySQL 检查点实现、RudyJunyu 的两阶段抽取与表格切片设计、Get00 的 Skill 打包范式、aigc-open 的 FastMCP 集成范式，均值得在对应专题时二次抽查。）
