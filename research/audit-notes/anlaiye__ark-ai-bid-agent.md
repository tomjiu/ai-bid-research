# anlaiye/ark-ai-bid-agent 源码审计报告

> 审计方式：纯静态（git log/ls-files/全文件阅读/rg 检索），未安装依赖、未运行仓库代码、未调用任何 LLM。仅用 python3 做了 JSON/YAML 语法校验与 package-lock 许可证读取（纯文本解析）。
> GitHub 元数据：stars=1，无 license，size≈3.1MB，最近推送 2026-08-04，主语言 TypeScript（全量克隆，git log 完整）。

---

## 1. 基本信息

### LICENSE
- **无任何 LICENSE 文件**（`git ls-files | grep -i license` 为空，根目录无 LICENSE/NOTICE）。
- 法律含义：默认版权全保留（作者保留全部权利），**任何形式的代码复制/改造/再分发都有法律风险**；本仓库只能"学习思路、联系作者取得授权后才可复用代码"。

### 形态与规模（回答主代理指定问题：项目真实形态）
- **真实形态 = 三件套**，不是 Electron、不是 CLI，也非空壳：
  1. **Next.js 16 / React 19 / TypeScript Web 工作台**（`app/`，经 `vinext` 0.0.50 —— 一个兼容 Next App Router 的 Vite 框架，部署目标为 **OpenAI ChatGPT Sites / Cloudflare Workers**：存在 `.openai/hosting.json`（`d1`/`r2` 绑定）、`app/chatgpt-auth.ts`（`oai-authenticated-user-email` 请求头、`/signin-with-chatgptpt` 路径）、`worker/index.ts` Cloudflare Worker 入口）。README 在线演示域名 `nuoya-ai-bid-agent.vchenlinux.chatgpt.site` 印证为 ChatGPT Sites 托管的演示站（登录后仅 UI 体验，本地 RAG 服务不可达）。
  2. **本地私有 RAG API 服务**（`services/rag-api/`，357 行 Fastify 5 Node.js ESM 单体，绑 `127.0.0.1:8787`），为**真正承载全部标书业务逻辑的核心**：解析→切片→pgvector+2-gram 双路检索→条款抽取→响应矩阵→评分估分→四模块生成→Excel/Word 导出，PostgreSQL(pgvector) 持久化 + **Ollama 本地模型**（`qwen2.5` 聊天 + `bge-small-zh` 512 维 embedding，`services/rag-api/src/config.js:8-11`）。
  3. **独立 Codex Skill**（`skills/ark-bid-review/`，2026-08-04 第 2 个 PR 加入）：SKILL.md + 4 篇方法论 references + 1 个 201 行纯 stdlib Python 确定性校验器 + 3 个 eval JSON。
- 前端经 `app/api/rag/[...path]/route.ts` 通用代理访问本地 RAG 服务（`RAG_API_INTERNAL_URL` 默认 `http://127.0.0.1:8787`）。
- **"方舟/Ark" 与火山引擎方舟 LLM 完全无关**：全库 rg 无 `volcengine|doubao|deepseek|api_key|openai.com|anthropic` 命中（已验证），"方舟"是产品品牌命名（旧品牌"挪亚/Nuoya"仍残留在 `exporters.js:14`（"挪亚 AI 招标助手"）、`db/runtime.ts:77`（"挪亚智慧科技有限公司"）、compose 项目名 `nuoya-ai`、库名 `nuoya_rag`）。
- **有真实标书工作流**，且实现密度高于典型 demo：解析/抽取/检索/矩阵/估分/生成/导出全部有可运行代码与确定性规则层，非脚手架。

### 规模
- 文件数：62（git ls-files）；有效代码 ≈ **3,230 行**（TS/JS/Python，不含 lock 与 CSS）+ 500 行 Markdown + 565 行 CSS。最大文件：`app/dashboard/DashboardClient.tsx` 663 行、`services/rag-api/src/generator.js` 529 行、`server.js` 357 行、`skills/.../validate_bid_review.py` 201 行。
- 顶层目录（每目录一句话）：
  - `app/` — Next.js 前端：营销落地页 page.tsx + 663 行工作台 DashboardClient.tsx（知识库/项目/解析/评分/生成/风险/设置 9 视图）+ `/api/rag` 代理 + 2 个**遗留孤儿 D1 demo 路由**（`api/projects`、`api/documents`，无任何前端调用）
  - `services/rag-api/` — 业务核心 Fastify 服务（src 8 模块 + 12 个 node:test 单测 + fixture）
  - `skills/ark-bid-review/` — 独立可复用 Codex Skill（审计方法论的提示词工程化表达）
  - `db/` + `drizzle/` — ChatGPT Sites D1(SQLite) 演示层 schema 与迁移（第一代 MVP 遗留）
  - `worker/` + `build/` + `vite.config.ts` — Cloudflare Worker 入口与 vinext 站点打包插件（模板底座）
  - `examples/d1/` — vinext starter 模板残留示例（notes demo，import 路径已失效）
  - `tests/` — 前端"测试"：对源码做字符串正则匹配（非真实渲染测试）
  - `public/` — 品牌 OG 图（og-ark.png 1.58MB，占仓库体积大头）

### 提交历史（全量克隆，8 条，非浅克隆）
- `8db3ece` 2026-08-01 "Build Nuoya AI bidding platform MVP"（第一代：ChatGPT Sites D1+R2 演示）
- `b55a5f8` 2026-08-01 "feat: add local private RAG bid workflow"（+2724 行，引入整个 rag-api）
- `5a4472d`/`68010f1`/`f0a5b81` 2026-08-01 三个小修（端口隔离/入库状态/切片查看器）
- `11e233b` 2026-08-03 "feat: publish Ark AI bid agent platform"（改名方舟、generator.js +437 行、前端重写 846 行、补测试与 fixture）
- `de2309a` 2026-08-03 README 完善（PR #1，分支 `agent/readme-demo`）
- `27f271f` 2026-08-04 "feat: add bid review skill"（PR #2，分支 `agent/ark-bid-review-skill`）
- 2 位作者（laolv、mindpoint）共用同一邮箱；`agent/*` 分支命名、vite.config 中 `CODEX_SANDBOX === "seatbelt"` 适配、4 天一次成型 — **明显的 AI 编码代理（Codex）快速构建项目**，无人工长期迭代史。

### 测试
- **有**：`services/rag-api/test/chunking.test.js`（node:test，12 个用例）——覆盖确定性层：中文字符 bigram、表格独立切片、句边界重叠切片、无模型字段抽取（fallbackProjectInfo）、评分表结构化重建（structuredScoringCriteria 含截断到后续章节的边界）、程序性噪声条款过滤、断裂参数行合并、`normalizedRiskLevel`（"证据不足/部分满足不算通过"）、可配置风险规则 clamp、ExcelJS 安全解析 XLSX、拒绝旧版 XLS。fixture：`test/fixtures/scoring-tender.txt`（模拟食堂设备招标评分表）。
- `tests/rendered-html.test.mjs`：2 个用例，读源码文件做 regex 断言（防退化为 starter 模板的回归测试，非真实渲染测试）。
- **无**：LLM 层测试、检索集成测试、CI（无 `.github/`）、E2E。

### 第三方依赖（许可证均宽松，无 AGPL 组件）
- rag-api：fastify 5(MIT)、@fastify/cors|Multipart(MIT)、pg(MIT)、ExcelJS(MIT)、mammoth(BSD-2-Clause)、pdf-parse(MIT，内嵌旧版 pdf.js)、docx(MIT)
- 前端：next 16.2(MIT)、react 19(MIT)、drizzle-orm(Apache-2.0)、vinext(MIT)、vite 8/wrangler(MIT/Apache)
- 基础设施：docker-compose 起 `pgvector/pgvector:pg17` + `redis:7-alpine`（**Redis 声明了但全库代码零使用**，README 技术表却列出）

---

## 2. 能力清单（标签 + 证据）

| # | 能力 | 标签 | 证据（文件+函数+引用） |
|---|------|------|------|
| a | 招标文件解析 | **IMPLEMENTED** | `services/rag-api/src/parsers.js:35-57 extractText()`：PDF→pdf-parse（文本<40 字符时抛错"可能是扫描件；请先执行 OCR"，行 40）、DOCX→mammoth、XLSX/CSV→ExcelJS（`worksheetText()` 以 `【工作表：名】` 头+`\t` 连接保留表格结构）、TXT/MD/JSON 直读；旧版 `.xls` 显式拒绝（行 50-52）。入口 `server.js:175 POST /v1/projects`、`server.js:137 POST /v1/knowledge/upload` |
| b | 条款/要求提取 | **IMPLEMENTED** | 混合式：`generator.js:327 parseTenderRequirements()` = LLM(chatJson, 系统提示词行 328 要求输出 JSON、保留数字/型号/否决条件、≤120 条) + `fallbackRequirements()`(行 120 正则全文行扫描) 合并去重（相似度≥0.62/0.72 丢弃）。分类 `categoryRules`（行 4-10）：报价/交付/商务(含资质证书业绩)/格式(含签字盖章装订)/响应(含废标否决偏离)/技术；`mandatory` 判定正则（行 101）：`必须|不得|无效投标|废标|否决|★|不允许负偏离`。评分项独立链路 `structuredScoringCriteria()`（行 257-296 正则状态机解析"评分细则（100分）"编号-分值表）+ LLM + `fallbackScoringCriteria`。注意：目标六类taxonomy（资格/否决/评分/技术参数/商务/格式）映射为 商务≈资格、mandatory≈否决项、scoring_criteria 独立表、技术含参数——覆盖但边界不同 |
| c | 原文位置溯源 | **PARTIAL** | 字段存在但弱：`tender_requirements.source_location` 为 LLM 自报文本或默认"招标文件正文"（`generator.js:338`）；`generator.js:102` 对疑似截断条款追加"（疑似截断，请核对原文）"标记；**无页码锚点**（pdf-parse 只输出全文）。Skill 侧 `references/tender-schema.md` 要求 `source_location` 如"招标文件.pdf 第 12 页"（文档约定） |
| d | 企业资料检索/证据 | **IMPLEMENTED** | `retrieval.js:58 hybridSearch()` = vectorSearch(pgvector HNSW 余弦，行 16-27) ∥ keywordSearch(行 29-41：char-bigram Jaccard×0.72 + 精确 token 命中率×0.28，行 5-14) → `alternatingMerge()` 交替合并去重（行 43-56）。SQL 过滤：仅 `source_type='enterprise_evidence' AND status='ready'` 且 `metadata->>'validUntil' >= CURRENT_DATE`（行 18）。主体冲突过滤 `generator.js:390 findForeignCompanyNames()`（公司名正则，剔除本企业名）+ `validEnterpriseEvidence()`（行 395）。**无字段级编号/金额/日期匹配器**（token 级 `includes` 而已） |
| e | 响应矩阵 | **IMPLEMENTED** | `response_matrix` 表（`db.js:64-74`，UNIQUE(project_id, requirement_id)，evidence jsonb 存 chunkId/content/score/route/metadata）；构建 `generator.js:450 buildResponseMatrix()`（每条要求 hybridSearch topK=6 → `judgeRequirement()` LLM 判定，批大小 4）；展示 `server.js:218 GET /v1/projects/:id`；导出 Excel 矩阵 `exporters.js:11 exportMatrixExcel()`。覆盖率以前端 `matrixCount/requirementCount` 呈现，无显式覆盖率计算 |
| f | 目录生成与分章节生成 | **PARTIAL** | **无目录生成环节**；模块固定 4 类：`generator.js:509 generateModules()` 按要求 category 分组 → 商务标(商务+交付)/技术标(技术)/偏离表/报价清单；商务标与技术标经 LLM 重写（系统提示词行 524：只许使用输入逐条响应、禁止添加不存在资质），偏离表与报价清单**仅为矩阵行原文拼装**（行 523）；无单章重试/修改/任务拆分，生成一次全量 |
| g | 审校/校验 | **PARTIAL** | 确定性部分：`normalizedRiskLevel()`（`generator.js:406-416`：主体冲突/不满足/证据缺失/部分满足→按可配置规则分级）、`validEnterpriseEvidence` 主体剔除、有效期 SQL 过滤、估分 clamp（行 479 `Math.max(0, Math.min(estimated, maxScore))`）、评分表边界截断。LLM 部分：`judgeRequirement`（行 418-448，系统提示词"证据不能证明时必须写证据不足"）/`judgeScoringCriterion`（行 471-486"保守估分，语义相关但不能证明时计 0 分"）。**缺**：报价/金额交叉校验、签章/暗标/大小写金额的确定性检查（仅存在于 Skill 文档 `risk-rules.md` 清单）；无独立"废标项清单"，废标风险=矩阵逐条结论汇总。Skill 校验器为确定性硬闸（见 m） |
| h | 导出 | **IMPLEMENTED** | `exporters.js:11 exportMatrixExcel()`（ExcelJS 7 列：序号/分类/招标要求/企业响应/结论/风险/证据来源）+ `exporters.js:46 exportBidDocx()`（docx npm，标题+模块正文+120 行响应矩阵表格）；版本化文件名 `-v{versionNo}`，路径存 `generation_versions` 表；下载端点 `server.js:331/340`。**无 PDF、无暗标格式、无模板回填**（Roadmap 明示规划中） |
| i | 状态持久化与恢复 | **IMPLEMENTED** | PostgreSQL 10 表（`db.js:7-134`：organizations/kb_articles/kb_chunks(vector(512)+bigrams jsonb)/tender_projects(**含 source_text 全文**)/tender_requirements/response_matrix/scoring_criteria/scoring_assessments/generated_documents/generation_versions/organization_settings + HNSW/GIN 索引，`migrate()` 启动自建）；`generation_versions` 快照不覆盖历史（server.js:316 `MAX(version_no)+1`）；恢复=重新打开项目（GET /v1/projects/:id 全量返回）；上传原件落 `data/uploads/`、导出落 `data/exports/`（.gitignore 排除）。**缺**：任务队列/中断自动恢复——生成中断时 status 卡 'generating'，无后台补偿 |
| j | 失败处理 | **IMPLEMENTED** | 全链降级：chatJson 失败→null（`ollama.js:66-69 console.warn "Chat model unavailable, using rule fallback"`）→要求抽取退回正则（generator.js:332）、字段抽取退回正则+评分选择（`chooseFieldValue`/`fieldValueScore`）、判定退回"待人工确认"（行 442-447）、模块退回矩阵拼装（行 526）；embedding 失败→确定性哈希伪向量（`ollama.js:3-17 hashEmbedding()`，行 39-42 降级）；Ollama 状态探测 `/health` 前端显示"AI 服务未启动"。**无重试机制**（一次失败即降级） |
| k | 日志与可观测性 | **PARTIAL** | Fastify `logger: true`（pino→stdout，server.js:16）+ `request.log.error/warn`；`setErrorHandler` 统一 JSON 错误（server.js:349-352）；无日志文件/指标/trace/任务进度上报（`onProgress` 回调在 server.js 中定义了但**未接线到任何端点**，generator.js:450/488 形参存在） |
| l | 测试 | **PARTIAL** | 见"基本信息·测试"：12 个单测覆盖确定性层（含 8 类边界用例+fixture），前端 2 个源码字符串断言；无 CI、无 LLM 层/检索集成测试 |
| m | Skill 文件 | **IMPLEMENTED** | `skills/ark-bid-review/SKILL.md`：标准 frontmatter（name/description），8 阶段工作流（输入分界→结构化抽取→**资格闸门 eligible/conditional/not_eligible**→双路检索→证据矩阵+评分对标→生成→废标风险检查→人工审核包），强制原则（不以"行业常见"代替证据、不使用过期/主体不一致证据、不自动签章报价提交）；4 篇 references（tender-schema 81 行含完整 JSON 契约、retrieval-and-evidence 含 A/B/C/D 证据分级、risk-rules 含 fatal/high/medium/low 分级规则、output-contracts 含占位符规范`【待补材料】`）；`scripts/validate_bid_review.py`（201 行纯 stdlib）：硬校验 met 必须有证据、证据不得重复/悬空、**投标截止日前过期的证据不得支撑 met**（行 75-77,128-129）、negative_deviation/insufficient_evidence 必须有风险项（行 131-133）、**mandatory 未满足阻断 eligible**（行 134-135）、**未关闭 fatal 必须 not_eligible**（行 89-96）、估分∈[0,满分]（行 160-161）；`evals/`（evals.json 4 用例 + valid-review.json 正例 + invalid-fabrication.json 反例"无证据却 met"）均通过 JSON 语法校验；`agents/openai.yaml`（8 行 OpenAI 接口描述符，YAML 可解析）。安装 `cp -R skills/ark-bid-review ~/.codex/skills/` |
| n | Dify DSL | **MISSING** | 全库唯一 YAML 为 `agents/openai.yaml`（OpenAI 界面描述符）与 docker-compose，无任何 `app:/graph:/nodes:/edges:` Dify 特征文件 |
| o | MCP Server | **MISSING** | 无 `mcp`/`modelcontextprotocol`/JSON-RPC 代码；Agent 一词仅为产品命名，工具调用形态为 Fastify REST + Skill 提示词，非 MCP 协议 |
| p | LLM 调用方式 | **IMPLEMENTED** | **Ollama 本地 REST**：`ollama.js:19 post()` → `/api/chat`（`format:"json"`、temperature 0.1、240s 超时，行 56-64）与 `/api/embed`（bge-small-zh、512 维、180s、批 24，行 30-43）；`extractJson()` 剥 ```json 围栏+首尾括号截取（行 45-54）。**提示词位置：全部内联于 `generator.js`**，共 5 处中文系统提示词（行 328 解析器、行 353 项目信息+评分、行 434 合规审核员、行 477 保守评分员、行 524 标书编制专家）+ Skill SKILL.md/references 为提示词方法论。模型经 env 切换（`OLLAMA_CHAT_MODEL`/`OLLAMA_EMBED_MODEL`），无版本随项目记录。"方舟"与火山引擎 Ark 无关（已 rg 验证） |

---

## 3. README 声明核对

| README 声称 | 判定 | 证据 |
|---|---|---|
| 企业私有知识库与 AI 标书生成系统（面向工程/后勤/软硬件服务商） | 已验证 | rag-api 全链路实现 + 前端工作台；行业枚举偏食堂/后勤（DashboardClient.tsx:480 高校食堂/园区后勤/智慧食安/弱电集成） |
| 在线演示站（需登录授权，请勿上传真实资料） | 未验证（外部 URL 无法静态核验） | `.openai/hosting.json`+`chatgpt-auth.ts` 佐证 ChatGPT Sites 部署形态存在；演示站 RAG 指向 127.0.0.1 必然离线，与其"主要体验界面"说法自洽 |
| 文档接入：PDF/DOCX/XLSX/CSV/TXT 解析；招标文件误传隔离 | 已验证 | `parsers.js:35-57`；隔离 `server.js:39 isLikelyTenderDocument()`（文件名+正文 5 信号≥3）→ `source_type='tender', status='quarantined'`，检索 SQL 双重排除（retrieval.js:18），db.js:144 启动时按文件名回溯隔离 |
| 知识库：300–500 字切片、表格独立切片、业务标签、有效期 | 已验证（数字略宽） | `chunking.js:33 chunkDocument({size:450, overlap:50})`，句界对齐+重叠；表格块独立 type='table'（1000/80）；标签=category/industry/productType 入 metadata；validUntil+`expiryState()`（server.js:53-61）+ 检索期 SQL 过滤 |
| 检索：pgvector 向量 + 2-gram 关键词 + 交替合并去重 | 已验证 | `retrieval.js` 全文（见能力 d） |
| 招标解析：关键字段、硬性要求、评分表与证明材料抽取 | 已验证 | `parseTenderAnalysis()` 15 字段 projectInfo（generator.js:132-148 规则字典）+ requirements + scoringCriteria(evidenceRequirements) |
| 标书生成：商务标、技术标、偏离表、报价清单初稿 | 已验证（带保留） | `generateModules()` 四模块真实生成；但偏离表/报价清单=矩阵行拼装（generator.js:523），非独立成文 |
| 审核风控：资格判断、负偏离、评分缺口、废标风险报告 | 已验证（范围有限） | judgeRequirement/judgeScoringCriterion + normalizedRiskLevel + 前端"废标风险检测"视图；**无**金额/签章/暗标确定性检查 |
| 文件导出：Excel 响应矩阵、Word 标书审核稿 | 已验证 | exporters.js 两个导出函数 + 下载端点 |
| 企业后台：新手引导、项目工作区、历史恢复、系统设置 | 已验证 | Overview onboarding、版本切换（GenerationVersionBar）、Settings 风险规则（PUT 后 `reclassifyOrganizationMatrix` 全量重算，server.js:63-73/101-107） |
| OCR / 无损回填 / 企业级治理 = 🧭规划中 | 已验证（诚实标注） | 代码确无；Roadmap 一致 |
| 推荐流程第 3 步"核对招标要求，**处理缺失或识别错误的条目**" | **部分不实** | **无任何条款编辑/增删端点**（server.js 全部 14 个路由中无 requirement CRUD）；`reanalyze` 仅重抽 projectInfo+评分（server.js:274-289），requirements 不可重抽不可修正——识别错误的条目无法在系统内处理，只能重建项目 |
| 技术架构表列 Redis | 夸大 | compose 有 redis 容器但**全库零代码使用**（rg 验证仅 compose/env/README 命中） |
| "人工闭环：项目恢复、分模块生成、风险修正、版本快照" | 部分验证 | 恢复/快照已验证；"分模块生成"=一次生成后按模块预览切换（DashboardClient.tsx:577-585），无单模块重新生成；"风险修正"=只能改知识库后整体重编 |
| Skill 声明（资格闸门/双路检索/证据矩阵/废标风险/确定性 JSON 校验） | 已验证 | skills/ 全部对应实体；invalid-fabrication.json 即"无证据却 met"反例 |
| 落地页 `app/page.tsx`："RBAC 权限/凭证加密/完整审计/按角色隔离/90% 重复内容可复用/生成与修改全程留痕" | **夸大** | README 自己承认 RBAC/审计为规划中；无凭证加密代码；"90%"无度量代码；人工修改不可持久化（无编辑端点），"留痕"仅版本快照。营销页与 README 功能表自相矛盾 |
| Docker 隔离与数据安全（独立端口/卷、不加 -v 保留数据、.env 默认演示密码） | 已验证 | docker-compose.yml 端口 54329/63799/8787 全绑 127.0.0.1；.gitignore 排除 .env* 与 services/rag-api/data/ |

---

## 4. 真实执行链路重建

```mermaid
flowchart TD
    U1[企业资料上传<br/>PDF/DOCX/XLSX/CSV/TXT] --> P1[extractText<br/>parsers.js]
    U2[招标文件上传<br/>POST /v1/projects] --> P1b[extractText]
    P1 --> Q{isLikelyTenderDocument?}
    Q -- 是 --> QU[隔离: source_type=tender<br/>status=quarantined<br/>不参与证据检索]
    Q -- 否 --> C1[chunkDocument 450字/表格1000字<br/>句界对齐+重叠]
    C1 --> E1[embedTexts: Ollama bge-small-zh<br/>失败降级 hashEmbedding]
    E1 --> DB1[(kb_articles / kb_chunks<br/>vector(512)+bigrams+metadata)]
    P1b --> TX[parseTenderAnalysis<br/>LLM qwen2.5 JSON + 正则双轨]
    TX --> R1[tender_requirements R-001..≤120<br/>六分类+mandatory]
    TX --> R2[tender_projects.project_info 15字段<br/>source_text 全文留存]
    TX --> R3[scoring_criteria S-001..≤80<br/>max_score+evidence_requirements]
    R1 --> M1[buildResponseMatrix<br/>逐条: hybridSearch topK6 + judgeRequirement LLM]
    DB1 --> M1
    R3 --> M2[buildScoreAssessments<br/>逐条: hybridSearch topK8 + judgeScoringCriterion LLM 保守估分]
    DB1 --> M2
    M1 --> MX[(response_matrix<br/>response/conclusion/risk/evidence jsonb)]
    M2 --> SA[(scoring_assessments<br/>estimated_score/gap/evidence)]
    MX --> G1[generateModules: 商务标/技术标 LLM 重写<br/>偏离表/报价清单 = 矩阵拼装]
    G1 --> GD[(generated_documents<br/>+ generation_versions v1,v2.. 快照)]
    MX --> X1[exportMatrixExcel xlsx]
    G1 --> X2[exportBidDocx docx]
    GD --> F1[前端人工终审视图<br/>主体名冲突 → 前端禁用下载]
    X1 --> F1
    X2 --> F1
```

### 节点表格

| 节点 | 入口(文件+函数) | 输入输出结构(关键字段) | 模型/工具/服务 | 持久化 | 失败处理 | 状态 |
|---|---|---|---|---|---|---|
| 输入/解析 | parsers.js `extractText(buffer, filename, mime)` | 文本(归一化)；表格带 `【工作表：名】` 头 | pdf-parse/mammoth/ExcelJS | 原件落 data/uploads | 扫描件/XLS 显式报错；单文件≤50MB | IMPLEMENTED |
| 切片/嵌入 | chunking.js `chunkDocument(text)`; ollama.js `embedTexts()` | chunk{content,type:text\|table}; embedding(512) | Ollama embed | kb_chunks | 哈希伪向量降级 | IMPLEMENTED |
| 条款抽取 | generator.js `parseTenderAnalysis/parseTenderRequirements/parseTenderProfileAndScoring` | requirements[{requirementNo,category,content,mandatory,sourceLocation}] ≤120; projectInfo 15 字段; scoringCriteria[{criterionNo,category,content,maxScore,evidenceRequirements}] ≤80 | Ollama qwen2.5 (JSON mode) + 正则三重 fallback | tender_requirements/tender_projects/scoring_criteria | LLM 失败→正则；字段按 `fieldValueScore` 择优；疑似截断标记 | IMPLEMENTED |
| 证据检索 | retrieval.js `hybridSearch()` | {rows:[{id,content,chunk_type,metadata,score,route:vector\|keyword}]} | pgvector + JS bigram | 读 kb_chunks | 无结果→判定层"证据缺失" | IMPLEMENTED |
| 响应矩阵 | generator.js `buildResponseMatrix()`→`judgeRequirement()` | {requirement, response, conclusion(满足/部分满足/不满足/证据不足/待人工确认/证据主体不一致), riskLevel, evidence[]} | Ollama + `normalizedRiskLevel` 确定性分级 + `validEnterpriseEvidence` 主体剔除 | response_matrix(evidence jsonb: chunkId/content/score/route/metadata) | LLM 失败→"待人工确认" | IMPLEMENTED |
| 评分对标 | generator.js `buildScoreAssessments()`→`judgeScoringCriterion()` | {criterion, estimatedScore∈[0,max], conclusion, gap, evidence} | Ollama 保守估分 + clamp | scoring_assessments | 无证据→0 分"材料缺失" | IMPLEMENTED |
| 目录 | — | — | — | — | — | **缺失**（固定 4 模块替代） |
| 分模块生成 | generator.js `generateModules(project, matrix)` | modules{商务标,技术标,偏离表,报价清单: string} | Ollama(商务/技术标) | generated_documents(挂 version_id) | LLM 失败→矩阵拼装降级 | PARTIAL（无单章重试） |
| 审校 | 前端 Risk 视图 + normalizedRiskLevel + identityConflicts | riskSummary{high,medium,low}; identityConflicts[] | 确定性正则为主 | 内存计算（每次 GET 重算） | 主体冲突→前端禁下载 | PARTIAL（API 侧不阻断） |
| 导出 | exporters.js `exportMatrixExcel/exportBidDocx` | xlsx 7 列 / docx 标题+模块+120 行矩阵表 | ExcelJS/docx | generation_versions(excel_path/docx_path) + data/exports 文件 | 版本不存在→404 | IMPLEMENTED |

**链路判定：完整链（解析→抽取→证据→矩阵→评分→四模块生成→审校→导出）全部存在且可运行**；唯二结构性缺口：无目录生成节点、无条款级人工修正回路。

---

## 5. 重点审计问题

**Q1 超长招标文件/附件/表格/扫描件如何处理？如何防止截断、解析失败或分块遗漏导致条款丢失？**
- LLM 抽取提示词输入 `String(text).slice(0, 70000)`（generator.js:329、354）≈ 7 万字符，超长招标尾部**不进 LLM 视野**；缓解：`fallbackRequirements()`（行 120）对**全文**逐行正则扫描并按 0.62 相似度并集去重补入，`structuredScoringCriteria()` 也是全文扫描；故尾部条款只可能经规则路漏检（规则弱于 LLM 的语义合并）。要求总量硬顶 120 条（行 115），超出的直接丢弃。
- 截断防遗漏：切片按句界（。！？；\n）对齐 + 50 字重叠（chunking.js:14-29）；条款级"疑似截断"检测（长度>28 且无完整结尾标点，generator.js:102）+ 断裂续行合并（行 106-112，`^(?:于|及|或|且|并...)` 接续词模式）；评分细则超长 `trimScoringContent` 截 1400 字并标"（内容过长，已截断，请回看招标原文）"（行 223-231）。
- 表格：XLSX 每工作表独立文本块、`【工作表：名】` 头，表格块独立切片 type='table'（1000 字/80 重叠）；**无行级切片**（一行参数不会成为独立 chunk，参数逐行比对靠检索整表块+LLM 判断）。
- 扫描件：pdf-parse 提取文本<40 字符即报错"请先执行 OCR"（parsers.js:40），README 将 OCR 列为规划中——**诚实拒绝而非静默猜测**，与 Skill 强制原则"OCR 不可靠时标记人工复核页"一致。

**Q2 六类要求如何统一成结构化条款清单？数据结构定义是什么？**
- Web 侧：`tender_requirements` 表（db.js:54-63）= {requirement_no, category∈{报价,交付,商务,格式,响应,技术}, content, is_mandatory, source_location}；评分项独立 `scoring_criteria` = {criterion_no, category∈{商务,技术,价格,服务,其他}, content, max_score≤100, evidence_requirements jsonb, source_location}。分类映射：目标六类中"资格条件"≈商务(资质正则)、"否决/废标项"≈mandatory 标志(正则 必须|不得|无效投标|废标|否决|★)、"评分项"=scoring_criteria 独立表、"技术参数"≈技术(品牌|型号|规格|分辨率 正则强制归类，generator.js:96)、"商务要求/格式要求"各有独立 category。
- Skill 侧契约更精细：`references/tender-schema.md` category∈{qualification, technical, delivery, pricing, format, commercial} + status∈{met, positive_deviation, negative_deviation, insufficient_evidence, not_applicable} ——**两套 taxonomy 不一致**（Web 无 status 枚举、以 conclusion 中文短语表达），复用设计时需统一。

**Q3 每条要求如何关联原文位置、证据、响应章节、审校结果？有无 ID 体系？**
- ID 体系：业务号 R-001…（sanitizeTenderRequirements 统一重编号，generator.js:117）、S-001…（行 247）；DB 主键 UUID；`response_matrix.requirement_id` FK → tender_requirements（UNIQUE(project_id, requirement_id)）；`scoring_assessments.criterion_id` FK → scoring_criteria；证据=kb_chunks.id 存入 response_matrix.evidence jsonb（含 content/score/route/metadata.filename，server.js:307）。
- 原文位置：source_location 仅 LLM 自报或"招标文件正文"，**无页码/段落锚点**（pdf-parse 丢页信息）；证据侧溯源=metadata.filename+chunk 内容（文件名级）。
- Skill 契约要求证据级溯源：source_file+source_location(页码/工作表/单元格)+excerpt+retrieval_route+valid_until+confidence+verified（tender-schema.md:64-73）——设计完备但 Web 未实现页级锚点。
- 结论：有 ID 体系（R/S/UUID/chunkId 三级），关联完整；**原文位置溯源是全链最弱一环**。

**Q4 企业资料检索是否同时支持语义召回与精确匹配（编号/型号/金额/日期）？**
- 是，双路真实现：语义路=pgvector HNSW 余弦（bge-small-zh）；精确路=char-bigram Jaccard×0.72 + 精确 token（`[A-Za-z]+[\w.-]*|\d+(\.\d+)*|[\u4e00-\u9fff]{2,8}`）包含率×0.28（retrieval.js:5-14），交替合并去重保留 route 标记。
- 但精确匹配是**token 级 includes**，无字段级抽取器（金额/日期/证书编号不做结构化解析再比对，编号"XX-123"若被 chunk 切断则依赖 bigram 部分命中）；日期仅做有效期过滤（SQL `validUntil::date >= CURRENT_DATE`）。检索质量依赖切片运气，弱于 tlyyxjz/Bid_Agent 的字段验证器路线。

**Q5 无证据/证据过期/证据冲突/资格不满足时，如何阻止错误内容进入定稿？有无硬阻断机制？**
- 证据过期：检索 SQL 直接排除（retrieval.js:18）——**确定性硬阻断**（过期资料根本不进候选）。
- 主体冲突：`validEnterpriseEvidence()` 剔除含他企业名的证据（generator.js:395-404）；全部冲突时判定"证据主体不一致"（high）；**前端终审页检测生成文本中的他企业名后禁用两个下载按钮**（DashboardClient.tsx:594-598 `disabled={conflicts.length > 0}` + "主体名称冲突，已阻止导出"）。
- 资格不满足/证据缺失：生成"请补充后再响应"文本 + high/medium 风险，**不阻断导出**（初稿可下载，风险由人工处理）。
- **关键缺口**：后端导出端点（server.js:331-347）**不校验冲突/风险**，直接按路径返回文件——硬阻断仅存在于前端 UI 层，绕过 UI（curl）即可拿到带冲突定稿。导出文件本身标注"AI 初稿·人工终审前"（exporters.js:50）。
- Skill 侧是真正的硬闸：validate_bid_review.py 强制 met→必有证据、过期证据无效、mandatory 未满足→不得 eligible、未关闭 fatal→必须 not_eligible（行 89-96、122-135），配 `--strict` 把警告也当失败；invalid-fabrication.json 即反例。**但它是离线脚本，靠 Agent 自律调用，未接入 Web 系统。**

**Q6 章节能否拆成可单独执行/重试/修改/验证的任务？**
- 不能。生成是单 HTTP 请求内同步全量（matrix→assessments→modules→exports，server.js:291-329），模块=4 固定类；无单模块重试、无任务队列、无进度推送（onProgress 形参未接线）。前端只能整项目"重新编制并检测"。i 项的状态机（parsed/generating/review）是粗粒度项目级。

**Q7 报价/工期/数量/资质有效期/签章/暗标等检查，哪些是确定性代码、哪些依赖模型？**
- 确定性：资质有效期（SQL 过滤+expiryState 预警天数可配置+`organization_settings.risk_rules` 修改后全量重算 server.js:63-73）、主体冲突（正则）、风险分级（normalizedRiskLevel 纯规则、级别可由企业配置，DEFAULT_RISK_RULES generator.js:33-41）、mandatory/分类（正则）、估分上限 clamp、评分表结构化解析（正则状态机）、Skill 的全部 JSON 校验。
- 依赖模型：条款判定 conclusion（满足/不满足/证据不足）、估分、商务标/技术标成文、数值严格比较（靠提示词"数值、日期、有效期和型号必须严格比较"，行 434）。
- **无**：报价合计/大小写金额交叉校验、签章/密封/暗标确定性检查——仅 Skill risk-rules.md 文档清单要求，无代码。skill-rules 的"报价、税率、合计或大小写金额异常"在 Web 完全未实现。

**Q8 项目中断、更换模型、补充招标文件后，如何恢复状态、识别受影响章节并重新执行？**
- 恢复：全部状态在 PG（含 tender source_text 全文、矩阵、估分、模块、版本、导出文件路径），重启服务/浏览器后打开项目即恢复（GET /v1/projects/:id 一次返回全部）；generate 幂等（先 DELETE 再 INSERT，行 304-305），重跑安全。
- 中断：generate 中途失败 status 卡 'generating'（无后台补偿、无队列），但数据一致性由事务保证（矩阵/估分/版本各自 BEGIN-COMMIT）；10 分钟 requestTimeout（server.js:16）对 120 条×LLM 串行批可能不够。
- 更换模型：env 改 OLLAMA_CHAT_MODEL 即可，**无模型版本记录**于 generation_versions——旧版本结果不标注是哪个模型产出。
- 补充招标文件/补遗：**无更新项目源文件端点**；`reanalyze` 只对已存 source_text 重抽 projectInfo+评分（不重抽 requirements）；补遗影响分析、受影响章节识别完全缺失（Roadmap 的"补遗/addendum"能力为零）。Skill 文档把"历史侧/风险规则"列为输入，但系统无补遗工作流。

**Q9 是否存在可导入 Dify DSL / 可运行 MCP Server / 独立 Skill？给出实际文件与验证结果。**
- **Dify DSL：无**（全库无 Dify 特征 YAML；唯一 YAML 为 agents/openai.yaml 8 行 OpenAI 界面描述符——display_name/short_description/brand_color/default_prompt/policy.allow_implicit_invocation，YAML 语法已验证可解析，但属 OpenAI ChatGPT Apps/Codex 生态而非 Dify）。
- **MCP Server：无**（无任何 MCP SDK/stdio/JSON-RPC 代码）。
- **独立 Skill：有且完整可复用**——`skills/ark-bid-review/`：SKILL.md（117 行，标准 name/description frontmatter + 8 阶段流程 + 强制原则 + 质量标准）；references/ 4 篇（共 210 行方法论契约）；scripts/validate_bid_review.py（201 行，**仅 Python stdlib**，json/argparse/datetime/pathlib，源码含 `from __future__ import annotations`，Python 3.8+ 可运行；无需安装任何依赖）；evals/ 3 个 JSON 全部通过语法校验（evals.json 4 用例、valid-review.json 正例、invalid-fabrication.json 反例）。**还缺什么才能跑起来**：只需任何遵守 SKILL.md 的 Agent 运行时（Codex/Claude Code 等）+ 把目录拷进 skills 目录；检索/证据获取本身由宿主 Agent 能力承担（Skill 是方法论+校验器，不含检索代码）。
- 附加发现：仓库本身以 Codex 工作流开发（agent/* 分支、`vite.config.ts:12` 的 `CODEX_SANDBOX` 适配、.openai/hosting.json），Skill 与宿主平台同构。

**Q10 哪些代码/提示词/数据结构可合法复用？哪些仅可借鉴思路？**
- **许可证结论：仓库无 LICENSE → 一切代码不可合法复用**（默认全版权保留，复用/改造/分发均有侵权风险），第三方依赖本身全为 MIT/Apache-2.0/BSD-2-Clause（无 AGPL 传染，已从 package-lock 逐项核实）不构成额外负担。**如需采用任何代码，必须先联系作者（github.com/anlaiye）取得授权**；现阶段：**仅可借鉴思路/设计**。
- 值得借鉴（按价值排序）：
  1. **Skill 硬校验契约**（validate_bid_review.py 的规则族 + tender-schema.json 契约 + evals 正反例）——这是把"无证据不得满足"写成可执行断言的最小完备样本，思路可直接吸收（注意不可抄码）；
  2. **generator.js 的确定性清洗层**（proceduralNoiseRules 程序噪声过滤、疑似截断检测+续行合并、requirementSimilarity 去重、fieldValueScore 字段择优、评分表正则状态机）——LLM+规则双轨互验的工程模式；
  3. **风险规则外置**（organization_settings.risk_rules 可配置分级 + 保存即全量重算）；
  4. **双路检索交替合并** + 主体名冲突证据剔除 + 招标文件隔离闸门（isLikelyTenderDocument 防甲方需求污染企业证据池——少见的好设计）；
  5. **评分对标与废标风险分离**（"能拿多少分"vs"会不会废标"双视图）。
- 不建议采用：单租户 env 配置、无鉴权本地 API、D1 遗留层、前端字符串匹配测试法。

---

## 6. 复用价值与许可

- **可直接复用：无**（无 LICENSE，法律上全部锁定）。
- **需改造后复用：仅指取得授权后的情形**——rag-api 8 个模块结构清晰（Fastify 单体、无框架魔法、纯 SQL schema 自迁移），若授权可整体移植为 Python 后端参考的 JS 对照实现；ExcelJS/docx 导出模板、pgvector+bigram 双路检索、风险规则重算逻辑。
- **仅可借鉴思路（当前合法可行的全部）**：上节 Q10 五项 + "LLM 判定失败即降级为待人工确认而非编造"的保守策略 + 招标文件隔离 + 证据 A/B/C/D 分级 + Skill 输出契约（占位符体系【待补材料】【负偏离风险】）+ evals 反例测试法。
- **许可证结论**：无 LICENSE = 默认版权全保留；本项目**禁止复制其代码**（包括"改写式复用"），设计/流程/规则思路不受版权保护可借鉴；若业务确需其代码，唯一路径是取得作者书面授权。仓库内 Skill 同样受此约束（SKILL.md 无独立 license 声明）。

---

## 7. 可靠性风险清单

| # | 风险描述 | 严重程度 | 证据(文件+位置) | 复现/验证方法 |
|---|---|---|---|---|
| 1 | **导出硬阻断仅在前端**：主体冲突时 UI 禁用下载，但 `/export.xlsx`/`/export.docx` 端点不校验任何风险/冲突，直接按版本路径返回文件 | 高 | services/rag-api/src/server.js:331-347（无校验直读文件）；对比 DashboardClient.tsx:594-598（前端 disabled） | 启动服务生成含他企名的版本后，绕过 UI 直接 curl 导出端点即可下载 |
| 2 | **LLM 抽取 70k 字符截断**：超长招标尾部要求仅靠正则 fallback 覆盖，语义弱、上限 120 条硬截断 | 中-高 | generator.js:329、354 `slice(0, 70000)`；行 115 `length >= 120` break | 构造 >7 万字符、尾部含密集技术条款的招标文本，对比解析结果 |
| 3 | **无条款编辑回路**：README"处理缺失或识别错误的条目"无对应端点；识别错误的要求无法修正，只能重建项目；reanalyze 不重抽 requirements | 中 | server.js 全部 14 路由无 requirement CRUD；server.js:274-289 | 通读路由表 + 尝试寻找条款编辑 API（不存在） |
| 4 | **embedding 静默降级为哈希伪向量**：Ollama 关闭时"向量路"退化为 char-bigram FNV 哈希（非语义），仅 console.warn，检索质量塌陷用户难察觉 | 中 | ollama.js:3-17 hashEmbedding、39-42 fallback | 停 Ollama 后上传资料并检索，观察 /health.ollama.online=false 但流程照常走通 |
| 5 | **溯源无页码锚点**：source_location 为 LLM 自报或"招标文件正文"；证据仅到文件名级；矩阵无法回指原文页/段 | 中 | generator.js:338；pdf-parse 输出无页信息（parsers.js:37-41） | 解析任意 PDF 招标，检查 requirements.sourceLocation 取值 |
| 6 | **同步长事务无队列**：generate 单请求串行 120×(检索+LLM)+80 评分+成文+导出，10 分钟超时可能中途失败，status 卡 'generating'，无重试/恢复/取消 | 中 | server.js:16 requestTimeout 10min、server.js:291-329 单端点全量 | 大项目（>60 条要求+本地慢模型）生成计时 |
| 7 | **keywordSearch 内存全扫**：每次查询拉最近 500 chunk 进 JS 评分，无倒排/索引；知识库大后性能塌陷且"最近优先"有偏 | 中 | retrieval.js:34-35 `ORDER BY created_at DESC LIMIT 500` | 灌入 >500 chunk 后检索旧资料，观察召回偏置 |
| 8 | **pdf-parse@1.1.1 内嵌旧版 pdf.js**：恶意 PDF 解析面（本地部署缓解，多租户/服务化后放大） | 中（本地场景低） | services/rag-api/package.json:18 | 查 npm pdf-parse 已知问题（test 文件劫持、旧依赖） |
| 9 | **单租户无鉴权**：组织 ID/名称来自 env（config.js:14-15），RAG API 绑 127.0.0.1 但本机任意进程可读写全部企业证据与导出文件；ChatGPT Sites 演示层与本地层数据模型割裂（D1 五表 vs PG 十表双 schema 并存） | 中 | config.js；db/runtime.ts vs db.js；无任何 token 校验代码 | 审读 server.js 全部端点（无鉴权中间件） |
| 10 | **规则层过拟合单一行业样例**：proceduralNoiseRules/分类正则明显围绕"高校食堂/智慧食安"招标调优（fixture 即食堂评分表），跨行业泛化未验证；mandatory 正则可能误标 | 中 | generator.js:13-30、96；test/fixtures/scoring-tender.txt | 用非后勤行业招标文本跑规则层（静态审读正则即可预估） |
| 11 | **双品牌/死代码残留**："挪亚"旧品牌散落（exporters.js:14、db/runtime.ts:77）、孤儿 D1 路由（app/api/projects|documents 无调用方）、examples/d1 模板失效 import、Redis 声明未使用——反映工程卫生与真实成熟度 | 低 | rg 挪亚/nuoya；grep 前端无 /api/projects 调用；docker-compose.yml redis | git grep 调用关系 |
| 12 | **AI 一次性代写痕迹**：8 commit/4 天/2 人同邮箱/agent 分支/CODEX_SANDBOX 适配/Codex 模板底座（vinext site-creator 占位 ID）——无长期维护承诺，1 星无社区 | 低（采购风险评估项） | git log 全记录、vite.config.ts:6-12、.openai/hosting.json | git log --format 全量查看 |

---

### 审计员总评（一句话）
这不是空壳：是一个 **4 天内由 AI 代理一次性构建、真实可跑的本地私有 RAG 标书 MVP**（Fastify+pgvector+Ollama+Next 工作台+Codex Skill），确定性护栏层（隔离/主体冲突/过期/风险分级/Skill 硬校验）的设计质量显著高于其规模，但**无 LICENSE 锁死一切代码复用**，溯源页码、条款修正回路、API 侧导出阻断、任务队列四项为最大结构性缺口。
