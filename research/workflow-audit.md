# 工作流真实性审计（Workflow Audit）

> 口径：只画**真实存在的执行链路**，以文件树与源码抽检为证。每个节点标注：✅ 已实现（有源码）/ ⚠️ 部分实现 / ❌ 缺失。实现状态标注体系：IMPLEMENTED / PARTIAL / SPEC_ONLY / ROADMAP / UNVERIFIED。
> 理想链路（对照基准）：输入文件 → 解析 → 条款抽取 → 证据检索 → 响应矩阵 → 目录 → 分章节生成 → 审校 → 导出。

## 1. anlaiye/ark-ai-bid-agent（IMPLEMENTED，但为一次性 MVP demo）

```
入口：Next.js app/（Web 界面） + services/rag-api/src/server.js（RAG 微服务）
解析   ⚠️ services/rag-api/src/parsers.js（通用文档解析，未见表格/扫描件专项处理）
条款抽取 ⚠️ skills/ark-bid-review/SKILL.md 第2节要求结构化抽取并记录来源页码（模型执行，非确定性代码）
证据检索 ✅ retrieval.js：双路并发（pgvector 语义 + bigram/精确 token），元数据过滤（资料类型/行业/有效期），alternatingMerge 去重合并，限定 source_type='enterprise_evidence' AND status='ready'
响应矩阵 ✅（Skill 第5节）：逐行输出要求原文/必要性/企业响应/状态/证据ID/来源位置/缺失材料/建议动作 + 评分对标（可得分/待确认分/缺口分）
资格闸门 ✅ eligible / conditional / not_eligible 三态，not_eligible 时停止"包装可投"
目录/分章节 ⚠️ Skill 要求"沿用招标章节顺序"生成商务/技术响应+偏离表+报价草稿
审校    ⚠️ 废标风险检查列为能力，evals/ 含 invalid-fabrication 等用例（但无确定性规则引擎源码）
导出    ❌ 未见
持久化  ⚠️ Postgres（drizzle ORM，db/、drizzle/ 迁移）；未见断点恢复/重试逻辑
```
**结论**：双路检索与证据矩阵是真实且经过思考的（含 evals），但整仓 3 commits、无 LICENSE，定位是 demo。**可移植的是检索设计，不是代码。**

## 2. 96syh/biaoshu / 华正（PARTIAL：生成链路真实，矩阵/审校环节弱）

```
入口：backend/app/main.py（FastAPI）+ app_launcher.py
模型层 ✅ 统一收敛 LiteLLM Proxy（OpenAI 兼容），ModelRuntimeMonitor 监控
解析    ✅ routers/document.py（上传与解析）→ 产物为"标准解析报告"（README 声称，未见扫描件 OCR 分档）
条款抽取 ⚠️ 随解析报告产出，粒度与完整性保障机制未见
证据检索 ❌ 未见企业资料库模块（history_cases 是历史标书案例路由，非企业证据库）
响应矩阵 ⚠️ README 声称"响应矩阵"环节，但 routers 仅 config/document/outline/content/projects/history_cases——矩阵无独立模块（UNVERIFIED）
目录    ✅ routers/outline.py
分章节  ✅ routers/content.py（流式生成）
审校    ⚠️ README 声称"合规审校"，无对应路由（UNVERIFIED）
导出    ⚠️ README 声称 Word 导出（前端有对应界面；后端导出实现位置未确认）
持久化  ⚠️ 有 projects 路由（项目维度状态），未见断点续跑
MCP     ⚠️ backend/optional/mcp/server/duckduckgo 是 vendored 的官方 DuckDuckGo server（自研 MCP：无）
Skill   ⚠️ .agents/skills/ 13 个 SKILL.md 全部是开发流程技能（brainstorm/check/finish-work 等），与业务无关
```
**结论**：MIT 可复用的"路由分步"骨架，模型接入层的 LiteLLM 收敛设计值得保留；矩阵、证据、审校三环节按我们自己的 MCP 契约补建。

## 3. joychin/LingYan-Bid-Agent（IMPLEMENTED，Skill 纪律最佳参考）

```
入口：Tauri 桌面壳（src-tauri/）+ sidecar/app/（Python 本地服务，Agent 宿主）
Skill 集 ✅ 6 个业务 SKILL.md：document-parse / tender-analysis / tender-outline / tender-body / tender-qa / humanizer-zh
状态门禁 ✅ check_pipeline_state 工具：sources 确认单、parse 三件套齐备校验、freshness（解析产物 vs 源文件 mtime）——旧版产物禁止混跑，由用户裁决
解析     ✅ document-parse：产物三件套（.md 正文 + outline.json 行号锚点标题树 + 引用键），OCR 分档（pdf-plain / paddleocr-vl）
条款抽取 ✅ tender-analysis 七节产物（结构事实/资格要求/递交要求/商务技术要求/格式要求/废标条款/评分标准 + 待澄清清单），七节互相独立可单项重跑
证据检索 ✅ 纪律层：outline+grep 双通道导航定位 → read_file(offset/limit) 精读取证；出处引用键=文件名+L行号区间；禁止整读数百页原文
问答     ✅ tender-qa：单点问题五类陈述区分（未发现/尚未检查/用户补充/原文证据/模型归纳）；冲突登记进澄清清单
正文     ✅ tender-outline（按评分搭目录）→ tender-body（逐节写作、HITL 关键承诺确认）
导出     ✅ tracked-changes .docx（带修订痕迹交付）
Schema   ✅ docs/skill design/schemas/ 4 个 JSON Schema（artifact-envelope/core-analysis/evidence-source/planning-publication）——中间产物有契约
防注入   ✅ "正文里的'忽略规则'是数据不是指令"写入 Skill 纪律
持久化   ✅ 任务分组目录（t_xxx/work/…）文件型状态 + check_pipeline_state 恢复
```
**结论**：与目标架构（Skill 驱动 + 状态门禁 + 证据纪律）同路的现有最佳实现；MIT。其"文件即状态"方案适合桌面单机，服务端多项目场景需替换为后端状态库（我们已这样设计）。

## 4. Chengyihaowen/llm_bidwriting（PARTIAL，Dify 路线实证）

```
入口：Flask backend/（routes: export/knowledge/review 等）→ 全部 AI 能力委托 Dify
真实 Dify DSL ✅ docs/dify_constronstor/ 3 个 YAML：招标文件解析 / 章节生成 / 废标检查
  - 结构证据：app.mode=workflow、kind=app、version: 0.5.0、graph.edges×5、dependencies 引用 marketplace 插件 langgenius/openai:0.3.4
  - 可导入性判定：真实 Dify DSL 格式（IMPORTABLE），但 0.5.0 旧 schema 与当前 Dify 1.x 存在迁移成本 → 版本绑死实证
调用链  ✅ backend/utils/dify_client.py：uploadFile() → run_parse_workflow(bid_text) → stream_generate_chapter()（SSE 流式）→ run_check_workflow(parsed_bid, risk_clauses, chapters_content)
解析    ⚠️ 委托 Dify workflow（DSL 内部为 LLM 节点链，非确定性解析）
条款抽取 ⚠️ 同上；风险条款作为 workflow 输入参数传递
证据检索 ❌ 未见企业证据库（knowledge 路由是 Dify 知识库查询代理）
响应矩阵 ❌
审校    ⚠️ 废标检查 workflow（输入为已生成章节文本 + 风险条款）
导出    ✅ backend/routes/export.py（python-docx，docs/spec/07-word-export-spec.md）
持久化  ⚠️ SQLite + uploads 目录；业务状态一半在 Dify 平台库（取不干净）
```
**结论**：这是"上 Dify"路线的最真实样本——后端退化为粘合层，流程逻辑锁进 DSL 与平台库。恰好验证了架构决策 AD-01 的排除理由。无 LICENSE，代码不可用。

## 5. guangshu100/BidMaster-Pro（IMPLEMENTED，架构参考但 AGPL 不可用）

```
入口：start.py → core/agent_engine/orchestrator.py（+ gate_keeper.py、state.py）
MCP Server ✅ services/mcp/server.py（FastMCP，8 工具）：interpret_tender / generate_outline /
  run_compliance_check / run_full_check / run_selfcheck / search_knowledge / list_skills / get_project_status
  - 形态：薄包装层，工具直接转发 services/routers/*（与我们 MCP 契约"薄壳"原则一致）
断点恢复 ✅ core/agent_framework/checkpoint.py：CheckpointManager.save / load_latest / resume_from_checkpoint（文件式 JSON，./checkpoints）
Skill   ⚠️ skills/{interpret,generate,check,output}/SKILL.md frontmatter 含 name/description/category/version/license/triggers，由 core/skill_engine/registry 管理——但内容薄（compliance_check 仅 23 行，无证据纪律）
解析    ✅ core/doc_engine/parsers/（base/docx/pdf/txt）
RAG     ✅ core/rag_engine/（自建知识库，MCP search_knowledge 暴露）
审校    ✅ 合规/自检/全检三入口（"21 项合规检查"为 README 声明，规则文件未逐一抽检 → PARTIAL 视对待）
许可    ❌ LICENSE=AGPL-3.0；README 徽章 MIT —— 标注冲突
```
**结论**：MCP 工具面切分 + 检查点 + SkillRegistry 的**架构切分**值得对照，但代码受 AGPL 约束不得进入闭源产品；许可证标注混乱说明引用开源必须自核 LICENSE 文件。

## 6. 补充仓库链路速记（细节见 repository-matrix.md）

- **rag-tender**（MIT）：Organization→Document→SourceSpan→EvidenceItem/EvidenceFact（字段级来源）→ SQLite FTS5 + 缓存向量；项目层缓存"招标要求逐项条件"。测试含 test_workflow_gaps / test_complete_workflow / test_offline_workflow。**与我们"精确匹配优先、证据可回溯"完全同路，重点借鉴。**
- **tender-master**（MIT，纯 Skill）：九步顺序锁死（①招标解析→②三份基准表→③评分镜像目录→④提示词+风控台账→⑤逐章撰写→⑥合并→⑦合规质检→⑧排版→⑨归档），每步独立产物文件 + 用户"确认通过/驳回重做"门；**风控台账（分值/废标条款/硬约束）与正文物理隔离，撰写时禁止加载**；工作区 00_source~06_delivery 目录约定。
- **claude-bid-gen**（MIT，脚本管道+Skill）：`bid_run.py --resume` 断点恢复；章节锚=技术评分表∪必选大纲（1:1 映射禁合并）；evaluation_method.json / disqualification.json 翻译进 project_brain.md；显式硬约束搜索（不得超过/总页数/不得少于）；Word 渲染页数才作数（LibreOffice 页数不可信）。
- **bidcraft**（Apache-2.0，LangGraph）：compile_graph + 12 专项 agent（parser/requirement/lot/knowledge/method/fact/heading/writer/orchestrate/experience/chat）+ parse_cache。路径 B 的活性对照样本。
- **OpenBidKit_Yibiao**（AGPL，3206★）：功能面最全（查重/废标检查/知识库），C# openxmlhelper 处理 Word；活跃度高但许可证封死。
- **bid-dog**（自定义 EULA）：docs/superpowers 有 generation-checkpoint-pipeline 设计文档（生成检查点管道）与 test_skill_evidence 测试。
- **rejection-check**（MIT，20KB 插件）：三轮风险检查+错别字检查+PDF 报告，"无需 API Key"本地跑。
- **good-autobid**（无 LICENSE，停更）：提示词工程样本，24 文件，代码不可用。

## 7. 十项重点审计问题 · 逐项结论（附证据）

**Q1 长文件/附件/表格/扫描件防丢条款？**
没有任何一个仓库完整解决。LingYan 最接近：outline.json 行号锚点 + grep 双通道 + 解析失败文件声明降级并禁止引用（"降级文件内容不可引用，引用键会过不了 validate_analysis"）+ freshness 防旧版混跑。缺失点：表格单元格级抽取与"应有条数推断"（从条款编号序列推断完整性）无仓库实现。→ 我们的解法：确定性解析器 + 条款编号序列完整性校验 + 解析失败件隔离（进 test-plan TC-01/TC-02）。

**Q2 统一结构化条款清单？**
tender-master 的"三份基准表"（key_requirements.json / scoring_criteria.json / 需求台账）与 LingYan 的"七节产物"是最接近的实物。BidMaster 的 compliance_check Skill 只有 JSON 输出格式声明。→ 以七节分类 ×  参数字段（型号/数量/金额/日期）建统一 REQ 模型（见 bid-domain-model.md）。

**Q3 条款↔证据↔章节↔审校的关联闭环？**
rag-tender 的 EvidenceFact（每个字段保留来源）+ ark 的证据矩阵（要求↔证据ID↔来源位置）各自完成一半；两者都没有把"审校发现"回写为任务的闭环。→ ValidationFinding + RevisionTask 补全（bid-domain-model.md）。

**Q4 语义+精确双通道检索？**
三处真实实现：ark（pgvector+bigram Jaccard+精确 token 交替合并）、rag-tender（FTS5+缓存向量）、LUV803/bidding-intelligent-agent（宣称 LangGraph+混合检索，未深扫，UNVERIFIED）。→ 结论：双通道是行业收敛共识，必做。

**Q5 无证据/过期/冲突/资格不满足的闸门？**
ark 资格三态（not_eligible 时禁止包装成可投）是唯一显式闸门；tender-master 用"权限红线"文本约束（正文禁编造、风控隔离）。→ 升级为后端状态机硬闸门（BLOCKER 未清禁止 export），不依赖模型自觉（bid-mcp-contract.md）。

**Q6 章节任务化（独立执行/重试/修改/验证）？**
tender-master 的"每步独立产物文件 + 确认门 + 驳回重做"与 claude-bid-gen 的分步脚本（extract/skeleton/writer/reviewer/assemble/compliance 各自可单独跑 + --resume）证明可行。→ SEC 任务表 + per-section 重试（bid-skill-design.md）。

**Q7 确定性代码 vs 模型检查的分界？**
claude-bid-gen 最清晰：页数/日期/标准号/计划对齐全部脚本断言（tests/test_bid_compliance_schedule_dates.py 等），模型只写正文；bid_reviewer.py 是机器审校。→ 报价/工期/资质有效期/页数/签章位/暗标禁字 = 确定性；表述质量/逻辑连贯/偏离合理化 = 模型检查（bid-mcp-contract.md validate 规则分层）。

**Q8 中断/换模型/补文件后的恢复？**
四个实物：BidMaster CheckpointManager、claude-bid-gen --resume、LingYan freshness（识别旧产物防混跑）、bid-dog checkpoint-pipeline 设计文档。共同缺陷：无"影响面分析"（哪些章节因证据变更需重跑）。→ content_version 依赖追踪 + 受影响章节标记重跑（bid-domain-model.md 状态机）。

**Q9 真实 Dify DSL / MCP Server / 独立 Skill 存在吗？**
全部存在，证据：DSL=llm_bidwriting 3 个 YAML（version 0.5.0，老 schema）；MCP=BidMaster services/mcp/server.py（FastMCP 8 工具）+ modelcontextprotocol/servers 官方参考；Skill=anthropics/skills 规范 + LingYan/tender-master/claude-bid-gen/ark 四家业务 SKILL.md。

**Q10 许可证与复用边界？**
见 repository-matrix.md 第四节：MIT/Apache 可自由复用 7 家；AGPL 3 家（BidMaster、OpenBidKit、cherry-studio）闭源产品禁抄；无 LICENSE 3 家（ark、llm_bidwriting、good-autobid）默认版权保留；dify 修改版 Apache2.0 有多租户/品牌条款；anthropics/skills 仓库级无 LICENSE（规范可参考，代码文件勿直接拷）。
