# 初筛报告 — 候选仓库 B 组（Task ID: 3-c）

日期: 2026-12（静态审计，未运行任何仓库代码/未安装依赖）
方法: git ls-files 统计 + rg 关键词检索 + README/源码抽样阅读。浅克隆提交数上限约 20 条。
结论速览: 无一仓库发现 SKILL.md 之外还含真实 Dify DSL 或 MCP Server 代码；全组 "Dify/MCP" 关键词命中均为 modify 等单词的子串误报，已逐一排除。

---

## 1. mag05270__BidAgents (github.com/mag05270/BidAgents, 10★, 无许可证)

**规模与构成**: 105 文件。backend/ 63（54 py，FastAPI 骨架，src/core/{bid_analyzer,generator,knowledge,memory,services}、api/v1、alembic 迁移 2 个）；frontend/ 36（17 ts + 11 vue，Vue3 页面: Projects/BidAnalysis/KnowledgeBase/KnowledgeGraph 等）；docs/ 2。
**提交活跃度**: 仅 1 次提交（2025-12-14 "init:项目初始化"）——单次倾倒式初始化，无迭代历史。
**关键要素**:
- a. SKILL.md: 未发现
- b. Dify DSL: 未发现（仅 docker-compose.yml 常规编排）
- c. MCP: 未发现
- d. 招标解析: backend/src/core/bid_analyzer/{parser.py, extractor.py, requirements.py}（requirements.py 为 LLM 驱动的需求分类器 RequirementsAnalyzer）
- e. 响应矩阵: backend/src/core/generator/document_generator.py L853-881 "需求响应表"模板生成（☑完全响应/△部分响应/○偏离说明，含证明材料列）——**但为硬编码模板骨架，非真实合规计算**
- f. RAG: kg_builder.py 声称"LightRAG 集成"（docstring + settings.lightrag_working_dir + requirements.txt lightrag-hku>=1.4.9），**但全后端无任何 `import lightrag`**——实际是自研 EntityExtractor/RelationExtractor 伪 KG；另有 qdrant/neo4j/minio 依赖声明
- g. 提示词: document_initializer.py（492 行，内嵌中文提示词）、llm_service.py
- h. 测试: 无任何测试文件
- i. 持久化: SQLAlchemy + asyncpg + alembic（2 个迁移）、Redis、MinIO
- j. 导出: generator/formatter.py、api/v1/documents.py（python-docx）
**README 核心声称**: ①基于 LightRAG/RAG-Anything 的智能标书生成系统 ②Vue3+FastAPI 全栈 ③PG+Neo4j+Qdrant+Redis+Celery ④DeepSeek+BGE-M3。**核实: LightRAG 声称与实现不符（未 import，SPEC_ONLY）**。
**相关性评分**: 2/5 — 链条骨架（解析→生成→导出）文件齐全，但单次提交、零测试、核心 RAG 声称虚标，成熟度与可信度低。
**初筛建议**: **EXCLUDE** — 空壳倾向的单次 init 项目 + 无许可证 + 关键声称（LightRAG）与实现不符；唯一残值是 document_generator.py 的需求响应表模板写法，可按需 10 分钟速览，不值得深度审计。

---

## 2. Yohann1024__intelligent-presales-skill (github.com/Yohann1024/intelligent-presales-skill, 17★, 无许可证)

**规模与构成**: 12 文件。SKILL.md（核心指令）+ scripts/ 5 个 py 共 1569 行（ingest 519 / export_html 307 / export_docx 284 / search_kb 237 / setup 222）+ requirements.txt + 空占位目录（examples/ knowledge_base/ resources/prompt_templates/ 均仅 .gitkeep）。
**提交活跃度**: 5 次提交，最近 3 次均在 2026-03-24（feat: 新增 Word 导出脚本 + SKILL.md 添加导出阶段；fix: 强化标书生成质量控制）——短周期集中迭代，方向明确。
**关键要素**:
- a. SKILL.md: **有，标准 Claude Skill 格式**（YAML frontmatter name/description + 完整工作流指令），内含结构化解析模板（项目信息/技术要求/商务要求/评分标准逐字段清单）与环境自检流程（setup.py --fix 降级引导）
- b. Dify DSL: 未发现
- c. MCP: 未发现
- d. 招标解析: scripts/ingest.py（docx/pdf/txt/md 清洗入库，段落切分）
- e. 响应矩阵/合规检查: 未发现（SKILL.md 仅要求提取评分标准，无矩阵落盘/核验逻辑）
- f. RAG: ChromaDB + Ollama bge-m3 本地 embedding（ingest.py / search_kb.py，支持语义检索+标签过滤+增量入库）
- g. 提示词: SKILL.md 本体即大段中文提示词（角色+流程+输出格式+质量控制规则）
- h. 测试: 无
- i. 持久化: ChromaDB persist 目录 + metadata.json 文件索引（ingest.py）
- j. 导出: scripts/export_docx.py、export_html.py（2026-03 新增）
**README 核心声称**: ①本地 Ollama+ChromaDB 全离线，适合涉密 ②解析→检索→生成完整流程 ③原创生成非复制历史标书 ④自动标签分类。
**相关性评分**: 3/5 — 一个"活的" Claude 风格投标 Skill：解析→检索→生成→导出四环均有实现，缺矩阵/审校环；与主项目"Skill 提供可重复执行流程"的定位高度同构。
**初筛建议**: **INCLUDE**（定向精读）— 作为 Skill 工程范本的最佳小型参照（成本极低：5 个脚本 + 1 个 SKILL.md 可一次读完），可直接借鉴其 SKILL.md 结构与知识库脚本契约。

---

## 3. sunShineLoveMe__ai_bidding_power_grid (github.com/sunShineLoveMe/ai_bidding_power_grid, 5★, MIT)

**规模与构成**: 422 文件 / 282MB（大头是数据集）。backend/ 48 py ≈13.8k 行（Flask 3.1 单体: parsing/ ai/ rag/ api/ export/ db/）；frontend/ 56（React18 + Vite + antd + tiptap 富文本，ai-bidding-workbench）；tests/ 16 个 py；rag_seed/ ≈180 个（招标文件 PDF/法规/标准/企业画像/产品图片——真实行业数据集，价值高）；assets/ 32（脱敏证书样张）；docs/ sql/ migrations/ scripts/ 齐备。
**提交活跃度**: 20 次提交（浅克隆上限），最近 2026-10-22、09-21、05-30——持续维护中的活项目。
**关键要素**:
- a. SKILL.md: 未发现（根目录 skills-lock.json 是 nexu-io/open-design 第三方视频/设计 skill 锁文件，与本仓库业务无关）
- b. Dify DSL: 未发现
- c. MCP: 未发现（onlyoffice.py 命中为误报）
- d. 招标解析: backend/parsing/document_parser.py（可选 MinerU OCR）、**bid_interpreter.py——关键词分组条款提取（资格/商务/技术/文件要求 4 组 + RISK_KEYWORDS 含"否决/无效/废标/视为" + 评分关键词），并做页码溯源 _source_page_by_snippet**
- e. 合规检查: backend/api/compliance.py、ai/compliance_checker.py、ai/semantic_compliance.py（规则检查 + LLM 语义复核双轨，定位响应缺失给补强建议）
- f. RAG: rag/vector_store.py（**pgvector**）、rag/{ingestion,retrieval}.py、ai/rerank_client.py（DashScope rerank）、关键词兜底；资产打分见 tests/test_rag_asset_scoring.py
- g. 提示词: ai/section_writer.py、interpreter.py、chapter_planner.py、bid_writing_plan.py 内置 + docs/产品库AI生成Prompt.md、企业资信库AI生成Prompt.md
- h. 测试: tests/ 16 个（compliance / semantic_compliance / docx_export / rag_retrieval / chapter_planner / vector_store_pgvector 等，覆盖核心环）
- i. 持久化: PostgreSQL + pgvector（migrations/postgres/001-004.sql）、Supabase 兼容层 + 迁移脚本（scripts/migrate_supabase_to_postgres.py）、文件落盘、用量与成本记录
- j. 导出: backend/export/md_to_word.py（python-docx 转 Word + soffice 刷新域）、api/export.py（导出任务/分册范围下载）、api/onlyoffice.py（在线编辑集成）
**README 核心声称**: ①解析招标文件提取要求/评分项/风险 ②企业知识库向量召回+rerank+关键词兜底 ③分册规划大纲+流式章节写作 ④规则+LLM 语义复核合规 ⑤DOCX 导出+用量成本记录。
**相关性评分**: 4.5/5 — **与目标链条（解析→条款→证据/知识→分册→章节→审校→导出）逐环对应且均为 IMPLEMENTED 级实现，附 16 个测试文件与真实行业数据集**；扣分项：电力/水利行业特化、Flask 单体非 Agent/MCP 架构。
**初筛建议**: **INCLUDE（最高优先）** — B 组最强候选，建议深度审计 parsing/bid_interpreter.py 条款提取、semantic_compliance 双轨复核、md_to_word 导出与 pgvector 检索四块；MIT 许可可安全借鉴。

---

## 4. William-GuoWei__ProposalLLM (github.com/William-GuoWei/ProposalLLM, 373★, Apache-2.0)

**规模与构成**: 仅 11 文件。Generate.py（555 行）、Extract_Word.py（202 行）、Template.docx、标书内容.docx(-示例)、需求对应表.xlsx(-示例)、requirements.txt、LICENSE。
**提交活跃度**: 19 次提交，最近 2024-11-14（README 更新/PR 合并）——已停更约两年，373 星反映需求真实性而非活跃度。
**关键要素**:
- a. SKILL.md: 未发现　b. Dify: 未发现　c. MCP: 未发现
- d. 解析: Extract_Word.py——**把产品手册按 1-3 级标题拆分为可复用细粒度文档**（避免每次全手册扫描）
- e. 响应矩阵: **有，且是核心**。Generate.py 以"需求对应表.xlsx"驱动逐条应答：按 G 列匹配手册章节则原文拷贝（保留图片/表格/项目符号，copy_content_with_images），无匹配则调 LLM 生成功能描述（generate_solution_from_chatgpt）；**自动生成技术偏离表、按"Answer: Fully supported, {LLM 生成}"格式回填矩阵、自动编排 1/2/3 级标题与章节号**
- f. RAG/向量库: 无向量库——用手册拆分 + find_word_file() 文件名匹配做"轻量检索"
- g. 提示词: Generate.py 内置中文 prompt（generate/rewrite/optimize_description 系列函数，对接 ERNIE-Speed-8K/Qianfan）
- h. 测试: 无
- i. 持久化: 无（本地 docx/xlsx 落盘）
- j. 导出: python-docx 生成方案 docx + openpyxl 回填矩阵
**README 核心声称**: ①基于需求矩阵+产品文档逐条生成点对点应答方案 ②自动拷贝手册内容保留格式 ③无匹配功能 LLM 自动生成 ④自动生成偏离表并填矩阵 ⑤手册拆分复用提性能。
**相关性评分**: 2.5/5 — 精确命中"矩阵→章节→导出"三环的最小可用实现，验证了"需求矩阵逐条应答"这一核心业务模式；但为脚本级、无 RAG、停更两年。
**初筛建议**: **INCLUDE（轻量）** — 两个脚本共 757 行可整读，矩阵应答/偏离表/手册拆分逻辑可直接映射到我们的响应矩阵模块设计；Apache-2.0 无风险。

---

## 5. mrwisdom2__biaoshuv2 (github.com/mrwisdom2/biaoshuv2, 1★, 无许可证)

**规模与构成**: 109 文件。app/ 41 py ≈5.4k 行（api/ core/ engines/{document,judgment,retrieval}/ infrastructure/{db,llm,vector,index,messaging,storage}/ orchestration/）；tests/ 20 py ≈2.9k 行；重构/ 13 个设计 md；.claude/ 8（openspec 开发流程 skill）+ openspec/ 4；scripts/ 6。
**提交活跃度**: 仅 2 次提交（2026-05-29 Initial + feat: convert sync rules API to batch mode）——一次性成型后微调。
**关键要素**:
- a. SKILL.md: .claude/skills/openspec-{explore,propose,apply,archive}/SKILL.md 与 重构/SKILL.md——**为开发流程 skill（OpenSpec 工作流），非标书业务 skill**；说明作者是 Claude Code 重度用户
- b. Dify DSL: 未发现　c. MCP: 未发现
- d. 解析: app/engines/document/parser.py（python-docx 条款提取）、annotator.py（**黄色高亮 + 红色批注写回原文档**）
- e. 合规检查: **app/engines/judgment/{engine.py, strategies.py}——策略模式 LLM 判决：TechPromptStrategy（双轨制: 核增审计+错误匹配）/ BizPromptStrategy（语义穿透+意见唯一准绳），build_prompt/parse_response 抽象接口**；对应 tests/test_unit/test_strategies.py、test_e2e/test_pipeline.py
- f. RAG: app/infrastructure/vector/qdrant_client.py + index/bm25_manager.py + engines/retrieval/{engine.py,filters.py,retriever.py}——**混合检索 BM25+RRF 融合、相似度门控、MMR、Cross-Encoder(bge-reranker) 精排、观点去重**，embedding BAAI/bge-large-zh-v1.5
- g. 提示词: strategies.py、infrastructure/llm/client.py 内置中文提示词（qwen-plus/qwen-flash）
- h. 测试: tests/ 20 文件 2865 行（unit + e2e pipeline），pytest+pytest-asyncio+httpx
- i. 持久化: MySQL（pymysql+DBUtils 池化，schema.sql）、Kafka 可选、Aliyun OSS
- j. 导出: 批注写回 docx（审校型"导出"，非生成新文档）
**README 核心声称**: ①风电行业 LLM 标书自动评审系统 ②Word 解析+混合检索规则+LLM 条款合规判断 ③原文直接批注风险点 ④多租户规则库（技术标/商务标/合同）⑤API+Worker 水平扩展。
**相关性评分**: 3.5/5 — 精确命中目标链条的"条款→规则检索→审校判决→批注"段，工程化分层清晰、测试充分；但它是"读标书评审"而非"写标书"，无生成/导出环。
**初筛建议**: **INCLUDE（高优先）** — 审校/合规段最佳参照：策略化 LLM 判决 + 混合检索精排 + 原文批注三件套可整体借鉴；注意无许可证（借鉴思路而非抄码）。

---

## 6. tlyyxjz__BidAgent (github.com/tlyyxjz/BidAgent, 2★, Apache-2.0)

**规模与构成**: 1098 文件。app/ 192 py ≈27.9k 行（processors 40 / api 34 / core 23 / models 19 / llm 11 / agents 9 / report 5 / scheduler…）；tests/ 87 py ≈28.5k 行 + pytest.ini + .github/workflows/ci.yml；_w2~w5_raw/_outputs/annotations 600+ txt 为评测数据集与金标；scripts/ 47；annotation_tool/ 7。
**提交活跃度**: 20 次提交（浅克隆上限），最近 2026-10-09 / 09-26 / 08-24——高度活跃，提交信息精细（"覆盖率 88.31% · 存证 822/828"）。
**关键要素**:
- a. SKILL.md: 未发现　b. Dify: 未发现　c. MCP: 未发现
- d. 解析: app/processors/{pdf_parser.py, pdf_fields.py, ccgp_field_parser.py, tender_ingestor.py, attachment_downloader.py}——**面向中标/招标公告与政府采购网页面**，pdfplumber + ddddocr OCR 兜底
- e. 合规/矩阵: 非标书评审系统——但 observation_signals.py 六维观察含"废标公告关联/明确投标否决/信息冲突观察"
- f. RAG: 无向量库（走确定性抽取+验证路线，非生成路线）
- g. 提示词: app/llm/{prompts.py, extractor_prompts.py, extractor_prompt_builder.py, prompts/winner_name_v2.txt}
- h. 测试: **87 个测试文件 ≈28.5k 行，README 称 2435 passed（本地全量）/ CI 子集 2335 passed**
- i. 持久化: SQLAlchemy+aiosqlite、Redis+rq、网页快照版本化 + **SHA-256 存证**
- j. 导出: app/report/{docx_generator.py, docx_sections.py, docx_components.py}（python-docx 分析报告，反幻觉校验后输出）
- **独有价值（方法论）**: LLM 仅生成候选 → 确定性程序验证：processors/evidence_locator/（字符级证据定位 _coordinate_mapping/_matchers/_verify）、field_validator_{amount,date,identifier,tolerance}.py、hallucination_checker.py + hallucination_patterns.py、simhash.py（jieba 分词去重）、source_lineage*.py（来源血缘）
**README 核心声称**: ①24 秒核验一篇中标公告真伪，每字段可指回原文第几个字符 ②620 篇金标实测字段准确率 97.60%、无依据输出率 0%、SHA-256 存证 822/828 ③LLM 生成候选+确定性程序验证的可验证抽取引擎 ④GOAI 2026 参赛项目（曾用名 ScrapeFlow）。
**相关性评分**: 2/5 — 业务对象是"中标公告核验"（供应链金融贷前尽调），不是标书编写；但其证据定位/字段验证/反幻觉子系统正是我们链条中"证据→审校"环的方法论金矿。
**初筛建议**: **INCLUDE（仅定向）** — 不做全库审计，定向深挖 evidence_locator、field_validator、hallucination_checker 三个子系统用于标书事实核查/证据溯源设计；Apache-2.0 可安全借鉴。

---

## 7. kcaaaa__bid-writing-agent (github.com/kcaaaa/bid-writing-agent, 3★, 无许可证)

**规模与构成**: 32 文件，**全部为 .md（31 md），零代码**。1 总 SKILL.md + skills/ 12 个子技能（每个 = SKILL.md 轻定义 + <name>-rules.md 按需加载细则）+ schemas/ 3（state-schema / input-output-contract / human-review-gates）+ workflows/ 2（bid-writing-workflow.md / workflow-rules.md）+ 使用场景介绍.md。
**提交活跃度**: 4 次提交，最近 2026-08-12（删指导方案文档 / 更新规则文档与 task-metric-monitor / 优化流程与篇幅控制）。
**关键要素**:
- a. SKILL.md: **有，且是全组最完整的 Skill 体系**——Trae IDE 纯文档技能包：tender-file-parser、tender-requirement-analyzer、hardware-description-guard、bid-template-outline、anti-duplication-strategy、bid-content-writer、technical-solution-writer、function-item-expansion、task-checklist-manager、bid-review-optimizer、task-metric-monitor、skill-exception-handler
- b. Dify DSL: 未发现　c. MCP: 未发现（导出走 OfficeCLI 约定）
- d. 解析: tender-file-parser/tender-requirement-analyzer（提示词级解析与需求分析，含硬件 S1 清单提取）
- e. 合规: bid-review-optimizer（跨章查重/招标响应/硬件溯源/篇幅检查）+ **11 个人工门禁 GATE-01..11**（任何门禁未确认业务停止）
- f. RAG: 无代码（防重复走"防重复缓存 + 关键词/技术维度登记"机制）
- g. 提示词: 全仓库即提示词本体
- h. 测试: 无
- i. 持久化: **文件型状态机设计**——"标书任务进度-{项目名}.md"单一事实来源，version/updated_at/session_id 占用校验、断点续写（进行中-已中断 + 接续会话登记）、历史版本不覆盖
- j. 导出: OfficeCLI 批量 Word 导出 + validate/视觉检查（流程约定）
**README 核心声称**: ①总调度+12 子 Skill+11 人工门禁+三阶段超长文档工作流，稳定生成 10-15 万字标书 ②四阶段懒加载（解析前置/大纲规划/正文撰写/审查收尾）③熔断规则：同 Skill 连续 3 次、总调用 8 轮、token≥28000 触发 ④单轮仅 1 Skill、暴露工具≤6。
**相关性评分**: 3/5 — 以纯提示词覆盖了"解析→需求→大纲→防重→正文→审校→导出"全链条，且长文档多会话状态管理设计（进度文档+门禁+熔断+断点续写）是工程级思考；但零代码、无许可证、效果数字无第三方验证（UNVERIFIED）。
**初筛建议**: **INCLUDE（定向精读文档）** — 对主项目"Skill 提供可重复执行流程"的方案设计而言，这是顶级参照物：状态 schema、门禁、熔断、会话隔离与断点恢复可直接映射进我们的 SKILL.md 规范；只需读文档无需代码审计。

---

## 汇总表

| # | 仓库 | 评分 | 建议 | 一句话理由 |
|---|------|------|------|-----------|
| 1 | mag05270__BidAgents | 2 | **EXCLUDE** | 单次 init 提交、零测试、LightRAG 声称与实现不符（无 import） |
| 2 | Yohann1024__intelligent-presales-skill | 3 | INCLUDE（Skill 范本定向） | 真实 Claude Skill + 5 脚本 1569 行，解析→检索→生成→导出闭环 |
| 3 | sunShineLoveMe__ai_bidding_power_grid | **4.5** | **INCLUDE（最高优先）** | 全链条 IMPLEMENTED + 16 测试 + 真实数据集 + MIT |
| 4 | William-GuoWei__ProposalLLM | 2.5 | INCLUDE（轻量） | 373 星验证的"需求矩阵逐条应答+偏离表"最小实现，757 行整读 |
| 5 | mrwisdom2__biaoshuv2 | **3.5** | **INCLUDE（高优先）** | 合规审校段完整工程化：策略化 LLM 判决+混合检索+docx 批注 |
| 6 | tlyyxjz__BidAgent | 2 | INCLUDE（仅证据子系统定向） | 业务为中标公告核验非标书，但 evidence_locator/幻觉检查可迁移 |
| 7 | kcaaaa__bid-writing-agent | 3 | INCLUDE（Skill 设计定向） | 零代码但 12 子 Skill+11 门禁+状态机是 Skill 方案设计金本位 |

**全组关键否定结论**: 7 个仓库中 **Dify DSL = 0、MCP Server = 0**（"dify/mcp"关键词命中均为 modify 等误报）；SKILL.md 体系存在于 #2、#5（开发流程）、#7 三家。

**最值得深挖 Top 3**:
1. **sunShineLoveMe__ai_bidding_power_grid** — 唯一的全链条可运行系统（解析条款含废标关键词分组→pgvector+rerank 证据召回→分册章节写作→规则+LLM 双轨合规→md_to_word 导出），MIT 许可，深度审计产出可直接进入方案设计。
2. **mrwisdom2__biaoshuv2** — 审校环最佳工程参照（Qdrant+BM25/RRF 混检、Tech/Biz 双策略 LLM 判决、原文高亮批注），测试 2865 行可验证设计意图。
3. **kcaaaa__bid-writing-agent**（并列可选 Yohann1024）— Skill 工程设计参照：若主项目优先落地 Skill 规范则选它（12 子技能+门禁+熔断+断点续写状态机）；若优先落地可执行脚本型 Skill 则选 Yohann1024。
