# mrwisdom2/biaoshuv2 源码审计报告

> 审计时间：2026 年（只读静态审计，未安装依赖、未运行代码、未调用任何 LLM API）
> 审计员：深度审计子代理（Task ID: 4-14）
> 审计对象：本地浅克隆 /home/z/my-project/repos/mrwisdom2__biaoshuv2/（github.com/mrwisdom2/biaoshuv2）

## 0. 一句话定性（先给结论）

这不是"标书编写"系统，而是**"标书/商务文件自动评审（审校）"系统**——把业主招标文件/合同按条款逐段与"历史审校规则库"做混合检索比对，用 LLM 判决是否偏离，并把风险点**回写批注到原文 docx**。它精确对应我们目标链条中"审校"环节的工程化实现，是审校链最佳参照；但其无许可证 + 内部真实业务数据泄露（运达能源/Windey 内部项目），**代码与数据均不可复用，仅可借鉴设计**。

---

## 1. 基本信息

### 1.1 LICENSE
- **无 LICENSE 文件**（`git ls-files` 无任何 license 文件）。
- `pyproject.toml:11`：`license = {text = "Proprietary"}`（专有软件声明）。
- `README.md:296-302`：`## License` 段写明 **"Internal use only."**，"内部项目，请联系开发团队"。
- **法律含义**：无许可证 = 默认全部版权保留。作者（提交邮箱 992022356@qq.com，署名 zhangzf1）未授予任何复制/修改/再分发权利。**复制其任何代码进本项目均有法律风险，仅能学习设计思想（思想不受版权保护）。**
- 更严重的问题：仓库内含**真实企业内部数据**（见 1.6 与第 7 节风险 R1），即使有许可证这些数据也不可用。

### 1.2 语言/框架/规模
- 主语言 Python（66 个 .py，除去 .claude 后），总计约 16,996 行（git ls-files 全量 wc）：
  - `app/` 41 个 py ≈ **5,368 行**（业务代码）
  - `tests/` 20 个 py = **2,865 行**（与初筛报告"2865 行测试"完全吻合）
  - `scripts/` 6 个 py ≈ 879 行；`main.py` 47 行 + `worker.py` 255 行
  - 文档 md ≈ 6,012 行（含 `重构/` 13 个设计文档）；`.claude/` ≈1,256 行（OpenSpec 开发流程 skill）
  - `localfile/`：两份规则库 CSV（1,048 + 2,214 行，共 ~1.2MB）+ 一份 3.2MB 真实招标技术规范书 docx
  - `resources/`：两份停用词表（77/89 词，HIT 停用词表的裁剪版）
- 技术栈（`pyproject.toml`）：FastAPI + uvicorn；MySQL（pymysql + DBUtils PooledDB）；Qdrant；sentence-transformers（BAAI/bge-large-zh-v1.5 embedding + BAAI/bge-reranker-base 精排）；rank-bm25 + jieba；DashScope（通义 qwen-plus/qwen-flash）+ tenacity；python-docx + lxml；oss2（阿里云 OSS）；kafka-python（可选）；pydantic-settings；filelock；numpy。
- 顶层目录结构（每目录一句话）：
  | 目录 | 说明 |
  |---|---|
  | `app/api/` | FastAPI 路由（router.py 961 行 + api-contract.md 契约文档） |
  | `app/core/` | 配置/常量/上下文/DTO/异常/日志/运行时参数管理（schemas.py、context.py、parameter_manager.py） |
  | `app/engines/document/` | 文档解析（parser.py）与批注写回（annotator.py） |
  | `app/engines/retrieval/` | 混合检索引擎（engine.py/retriever.py/filters.py） |
  | `app/engines/judgment/` | LLM 判决引擎（engine.py/strategies.py，Tech/Biz 双策略） |
  | `app/infrastructure/` | db(MySQL)/vector(Qdrant)/index(BM25)/llm/messaging(Kafka)/storage(OSS) |
  | `app/orchestration/` | pipeline.py 六步评审流水线编排 |
  | `tests/` | unit/functional/api/e2e 四层 pytest |
  | `scripts/` | init_db / upload_rules(CSV→MySQL) / sync_rules_cli / check_qdrant 等运维脚本 |
  | `localfile/` | **真实规则库 CSV + 真实招标文件 docx（内部数据！）** |
  | `resources/` | 停用词表 |
  | `openspec/` + `.claude/` | OpenSpec 规范驱动开发流程（AI 编码工作流，非业务功能） |
  | `重构/` | 13 个重构设计文档（API 文档、模块模式、harness 工业设计思考文章） |

### 1.3 提交历史
- 浅克隆仅 **2 次提交**（`git rev-list --count HEAD` = 2，未触 depth=20 上限，即全部历史）：
  1. `9ada9c5` "Initial commit"（2026-05-29）
  2. `939b2c4` "feat: convert sync rules API to batch mode"（2026-05-29 16:12:52 +0800）
- 两提交同日完成——**一次性成型 + 一次微调**，非渐进开发。GitHub 元数据显示最近推送 2026-06-23，但可见历史无新提交（可能仅改了默认分支设置等元数据）。
- 第 2 次提交带 `Co-Authored-By: Claude Sonnet 4.6` 署名，且首提交包含完整 OpenSpec/.claude 体系——**这是一个 Claude Code 深度辅助生成的企业内部项目**（`重构/harness工业设计方式.md` 也印证作者是"先定规范再放大 AI 产能"方法论的信奉者）。

### 1.4 测试
- 有；20 个文件 2,865 行，分四层：`test_unit`（schemas/context/constants/parser/filters/strategies/parameter_manager）、`test_functional`（bm25/rrf_fuser/retrieval_pipeline）、`test_api`（rules_crud/config_api/batch_sync，FastAPI TestClient + mock DAO）、`test_e2e`（pipeline 全流程）。
- 覆盖功能：数据结构默认值、租户路由映射、文本清理/滑动窗口、检索过滤器链（门控/MMR/去重）、RRF 融合数学、BM25 分词与检索、双策略 prompt 构建与 JSON 解析、参数管理 CRUD、API 层（上传/规则增删改/同步/参数）、流水线 mock 级 e2e、批注往返（段落/表格/防重）。
- **真实性核查（重点深挖方向 4）**：见 3.4 与 7.3。测试真实存在、风格认真、绝大多数与实现同步；但 `test_rules_crud.py`（446 行，占测试总量 15.6%）**基于旧版单条规则 API 编写，与提交版批量 API 不匹配，运行必失败**；且 **CrossEncoderFilter 是唯一无测试的过滤器**（因需下载模型）。结论：测试为真实工程产物，但存在 AI 生成后未全量回归的痕迹。

### 1.5 第三方依赖清单
全部为宽松许可证，无 AGPL 类传染风险组件：
- MIT/Apache-2.0/BSD 系：fastapi、uvicorn、pydantic-settings、qdrant-client、sentence-transformers（Apache-2.0）、rank-bm25（Apache-2.0）、jieba（MIT）、dashscope（Apache-2.0）、tenacity（Apache-2.0）、python-docx（MIT）、lxml（BSD）、oss2（MIT）、kafka-python（Apache-2.0）、dbutils（MIT）、filelock（Unlicense）。
- 注意点：无。若借鉴其"依赖选型"，依赖本身无法律障碍；障碍全部来自仓库自身的无许可证状态。
- `resources/hit_stopwords*.txt`：哈工大 IR 实验室停用词表的裁剪版（77/89 词），业界视为公共资源，风险极低。

### 1.6 数据泄露事实（法律红线）
- `app/core/config.py:36`：默认库名 `windey_bid_center` —— **运达能源科技集团**（WindEY）内部库。
- `localfile/standard_rule_202605271612.csv`（1,048 行）与 `standard_rule_v2_202605271612.csv`（2,214 行）：真实历史审校规则，含**内部核增报价策略**（如"核增认证及模具相关费用 800 万""国产控制器核增 7000 元/台""油液送检技术报价 500 元/台/次"）、机型编号（WD220-6250、190-5.0、YD112A 叶片）、我司内部标准（"我司齿轮箱润滑油取样首检为半年…"）。
- `localfile/测试2.docx`（3.2MB，113,627 字，51 张表，33 个媒体文件）：**真实采购技术规范书**——"国电投神熠围场100MW风电项目风力发电机组（不含塔筒）及附属设备采购技术规范书"，买方：镇江市欣源新能源有限公司，卖方：运达能源科技集团股份有限公司，日期 2026 年 5 月（以 python zipfile 纯文本方式验证 document.xml 内容）。
- **结论**：该仓库是内部项目连同真实业务/客户数据一并公开。对本项目而言：代码不可抄，**数据（规则库 CSV 与 docx 样例）绝对不可使用**。

---

## 2. 能力清单（标签 + 证据）

标签：IMPLEMENTED / PARTIAL / SPEC_ONLY / ROADMAP / UNVERIFIED / MISSING

**能力 a — 招标文件解析：PARTIAL（仅限评审视角的条款切分）**
- 证据：`app/engines/document/parser.py` `DocumentEngine.extract_clauses()`（L43-107）：python-docx 打开 .docx，遍历 `doc.paragraphs` + `doc.tables`（递归嵌套表格，深度 ≤ `MAX_TABLE_DEPTH=3`，L125-143），零宽字符清理（`_ZERO_WIDTH_CHARS` L30-32），长文本滑动窗口分块（`_split_text` L189-214，300 字/重叠 40）。
- 每个条款绑定物理锚点 `DocumentAnchor{anchor_type: paragraph|table, para_idx | table_idx,row_idx,col_idx,cell_para_idx}`（`app/core/schemas.py` L15-38）。
- **不支持**：PDF、扫描件/OCR、页眉页脚、文本框、.doc 老格式（API 声称接受 `.doc`，但 python-docx 无法解析二进制 .doc，任务必然失败）、附件清单、页码级定位。

**能力 b — 条款/要求分类提取（六类）：MISSING**
- 全库无"资格条件/否决项/评分项/技术参数/商务要求/格式要求"任何分类抽取逻辑。`Clause` 只是纯文本块 + 锚点。规则库有 `category` 字段但仅作 prompt 提示（`strategies.py` L462-467），非结构化分类体系。源码未体现。

**能力 c — 原文位置溯源：IMPLEMENTED（段落/表格坐标级，无页码）**
- `DocumentAnchor` 整型物理坐标（schemas.py L15-38）；`clause_id` 格式 `para_{i}_{chunk}` / `table_{t}_{r}_{c}_{p}_{ch}`（parser.py L87、L160-164）；批注按坐标 O(1) 回写（annotator.py）。**无页码**——全库无 page 相关字段（`grep 页码|page_num` 无结果）。

**能力 d — 企业资料检索/证据（语义+精确）：MISSING（语义+关键词检索对象是"规则库"而非企业证据）**
- 检索引擎（见下）只对审校规则库召回；无企业资质/业绩/证据库。编号/型号/金额/日期的精确匹配**仅以"关键词/同义词硬过滤"形式存在于规则侧**（`strategies.py` `_filter_by_keywords` L210-231/L424-445），不是证据检索。

**能力 e — 响应矩阵/合规矩阵：MISSING**
- 无 requirement × response 覆盖关系结构。最接近的是 `RiskItem{clause, judgment, annotation_text}`（schemas.py L79-93）——"条款 × 命中规则"的扁平风险清单，输出到 JSON 与 docx 批注。

**能力 f — 目录生成与分章节生成：MISSING**
- 本系统不生成文档内容，只评审已有文档。`architecture.md` L"本系统不负责"明确排除前端/认证等，也不含任何生成环节。

**能力 g — 审校/校验：IMPLEMENTED（LLM 语义判决为主 + 确定性前置过滤；无报价/工期/签章/暗标的确定性规则检查）**
- 分层确定性检查：关键词/同义词硬过滤（strategies.py）→ 相似度门控 0.30（filters.py `SimilarityGateFilter` L53-83）→ MMR λ=0.6/Top6（L89-178）→ Cross-Encoder 阈值 0.65/Top2（L184-285）→ 意见去重（L291-332）。
- LLM 判决：`JudgmentEngine.evaluate()`（engine.py L42-101）+ Tech/Biz 双策略（见 4.3 详述）。
- **无**报价/工期/数量/资质有效期/签章/暗标等结构化确定性校验——判决完全依赖 LLM 语义比对。

**能力 h — 导出：PARTIAL（批注写回原 docx + JSON 结果；非生成新文档/无 PDF/无模板/无暗标）**
- docx：`AnnotationEngine.apply_annotations()`（annotator.py L38-111）段落标黄 + 红字"【审查意见】"段落、表格单元格红字批注、防重指纹、倒序插入。
- JSON：`pipeline.py` L249-268 生成 `{task_id, lib_type, total_risks, stats, risks:[{clause_text, matched_rule_id, matched_opinion, thought}]}`。
- 结果经 OSS 上传，签名 URL 下载（router.py L166-227）。

**能力 i — 状态持久化与恢复：PARTIAL**
- 持久化：MySQL `review_task`（status: pending/processing/retrieving/generating/completed/failed + stats_json + result_oss_key/error_message，schema.sql L69-86）、`document` 表、规则表；BM25 pickle 缓存本地盘（bm25_manager.py L141-147）；OSS 存源文件与结果。
- 任务抢占：`ReviewTaskDAO.claim_pending_task()`（dao.py L42-76）`SELECT ... FOR UPDATE` + 条件 UPDATE 防竞态（注释称 MySQL 5.7 兼容；`architecture.md` 写的 "SKIP LOCKED" 与代码不符）。
- **恢复：无**——无断点续跑（Pipeline 中途失败整任务作废置 failed）、无 stuck-task 超时回收（Worker 崩溃后 status 永远停在 processing，无人再领取）、无失败自动重试。

**能力 j — 失败处理：PARTIAL（单条款/单规则级降级良好，任务级恢复缺失）**
- LLM 调用失败/JSON 解析失败 → `is_violation=False`（engine.py L75-95，strategies.py L162-184）——**fail-open：宁可漏报**。
- 条款级异常捕获（pipeline.py L94-99）→ 计入 skip 不中断；单条批注失败跳过（annotator.py L82-96）；Qdrant/BM25 单路检索失败退化为单路（retriever.py L141-150）；OSS 上传失败降级本地（router.py L373-382，但见风险 R6：该降级路径实际断链）；Cross-Encoder 推理失败退化为不精排直接 Top-2（filters.py L259-261）；Kafka 可禁用（kafka_manager.py L27-47）。
- 任务级：失败置 failed + error_message 落库 + Kafka 事件，**无重试/重入队**。

**能力 k — 日志与可观测性：IMPLEMENTED**
- 统一 logger（`app/core/logger.py`）：RotatingFileHandler + **敏感信息脱敏过滤器 SensitiveFilter**（L17-42，正则屏蔽 api_key/password/secret/token/sk-xxx）。
- `PipelineStats` 漏斗打点（schemas.py L96-129：total_clauses/recall_hit/recall_rules/gated_skip/rerank_pass/llm_judged/llm_deviate），随任务落库 stats_json，进度按 chunk 打日志（pipeline.py L216-224）。存在两处统计口径错误（见 7 R4）。

**能力 l — 测试：IMPLEMENTED（含真实 e2e mock 链，但 15.6% 测试过期失效）**
- 见 1.4 与 3.4。可离线运行（mock 全部外部服务，仅需装依赖；唯一重依赖是 import filters 时引入 sentence-transformers/torch）；CrossEncoderFilter 无测试。

**能力 m — Skill 文件：PARTIAL（存在但均为开发流程 skill，非标书业务 skill）**
- `.claude/skills/openspec-{explore,propose,apply,archive}-change/SKILL.md`（frontmatter 完整：name/description/license: MIT/compatibility/metadata.generatedBy: openspec 1.3.1）——OpenSpec 规范驱动开发工作流 skill；`.claude/commands/opsx/*.md` 配套斜杠命令。
- `重构/SKILL.md`：name `grill-me`（拷问式方案访谈 skill），同为开发方法论。
- **无任何标书业务 Skill**。真实性：frontmatter 合规、内容自洽，是 openspec 工具生成 + 人工整理的真 skill，但用途是"开发协作"。

**能力 n — Dify DSL / 工作流编排：MISSING（无 Dify DSL；自研编排真实存在）**
- 无任何 Dify YAML（无 app:/nodes:/edges: 特征文件）。编排 = `app/orchestration/pipeline.py`（六步流水线）+ `worker.py`（DB 轮询）+ MySQL 任务表状态机。

**能力 o — MCP Server：MISSING**
- 全库无 mcp/fastmcp/modelcontextprotocol/jsonrpc 任何实现。API 形态是 REST（FastAPI）。

**能力 p — LLM 调用方式：IMPLEMENTED**
- `app/infrastructure/llm/client.py` `LLMClient`：DashScope SDK `Generation.call`（`dashscope>=1.14.0`），qwen-plus 主模型 / qwen-flash 用于规则关键词抽取（router.py L529），temperature=0.01，60s 超时，tenacity 3 次重试 + 2s 间隔（**仅对 TimeoutError/ConnectionError 重试**，L55-61），内置 20 线程池（`call_async` 提供但流水线未用——pipeline 用自己的 8 线程池同步调用）。
- 提示词全部内置于代码：`strategies.py`（Tech/Biz 双 SYSTEM_PROMPT + 两个子模板）、`router.py` `_extract_keywords_synonyms`（L478-554，关键词抽取 prompt，含"极度严格的提取纪律"防呆条款）。
- 模型/并发/超时可运行时热调（parameter_manager，经 `/config/parameters` API）。

---

## 3. README 声明核对

| # | README 声称 | 判定 | 证据 |
|---|---|---|---|
| 1 | "自动解析 Word 文档（.docx/.doc）" | **夸大** | API 确实放行 `.doc` 后缀（router.py L351），但解析引擎仅 python-docx（parser.py L19 `from docx import Document`），二进制 .doc 必然抛 `DocumentParseError`；Worker 还统一按 `.docx` 命名下载（worker.py L148）。.docx 解析为真 |
| 2 | "混合检索 Qdrant+BM25，RRF 融合" | **已验证** | retriever.py `HybridRetriever`/`RRFFuser`；tests/test_functional/test_rrf_fuser.py 8 个用例 |
| 3 | "多层过滤：相似度门控/MMR/Cross-Encoder 精排/观点去重" | **已验证** | filters.py 四过滤器链；但 MMR 为"字符集 Jaccard 简化版"（filters.py L131 注释自认），非 embedding 相似度；CrossEncoderFilter 无测试 |
| 4 | "基于通义千问（qwen-plus）的条款合规性审查" | **已验证** | llm/client.py + judgment/engine.py + config.py L51 |
| 5 | "自动批注：黄色高亮 + 红色批注" | **已验证（有内涵差异）** | annotator.py：高亮=**整段**所有 run 标黄（非命中片段级）；"批注"=段落后插入红字段落"【审查意见】…"，**不是 Word 原生批注（w:comment）**——`grep comment` 于 app/ 无任何命中 |
| 6 | "多租户支持（技术标/商务标/合同等）" | **已验证** | context.py `TYPE_TO_TENANT_MAP`（7 种 lib_type→2 租户）+ `TENANT_RESOURCE_MAP`（独立 db 表/Qdrant collection/BM25 key/停用词） |
| 7 | "水平扩展：API+Worker 分离，容器化部署" | **已验证（有缺口）** | worker.py DB 悲观锁抢占支持多 Worker；docker-compose.yml 有 api/worker/qdrant，**但没有 MySQL 服务**（须外部提供），Kafka 可选关闭 |
| 8 | "Embedding BAAI/bge-large-zh-v1.5；Cross-Encoder BAAI/bge-reranker-base" | **已验证** | config.py L63、filters.py L210；qdrant_client.py 强制 `normalize_embeddings=True` 与 HF_HUB_OFFLINE=1 |
| 9 | "测试 pytest+pytest-asyncio+httpx" | **部分验证** | 依赖在 pyproject dev 组；测试用 httpx（TestClient）与 pytest；**未见任何 async 测试函数**（全部同步 def test），pytest-asyncio 实际未用上 |
| 10 | "通过 API 修改参数后，新请求立即生效，无需重启" | **已验证** | constants.py `_ParameterMeta` 元类代理 + parameter_manager 单例 override；tests/test_unit/test_parameter_manager.py（300 行）、test_api/test_config_api.py（断言恰好 18 个参数，与 UPDATABLE_PARAMS 数量一致） |
| 11 | README"评审流水线：文档上传→解析→条款提取→规则检索→LLM 判断→批注生成→结果上传" | **已验证** | 与代码完全一致（pipeline.py + worker.py） |
| 12 | `architecture.md` "上传返回 {document_id, file_name, oss_key}"、`api-contract.md` L189 响应示例含 file_name | **文档过期** | 实际 `UploadFileResponse` 仅 {document_id, message}（router.py L328-331、L397-400）；测试 test_rules_crud.py 也按旧契约断言 → 文档、测试、实现三方漂移 |

---

## 4. 真实执行链路重建（评审链，非编写链）

本系统的真实链路是**「上传 → 解析切分 → 规则检索 → LLM 判决 → 批注回写 → 结果下载」**。按主项目通用链路（输入文件→解析→条款抽取→证据检索→响应矩阵→目录→分章节生成→审校→导出）对照：**它是"审校→导出"两节针对已有文档的实现**；证据检索/响应矩阵/目录/分章节生成四节点完全缺失（本系统定位即不负责）。

```mermaid
flowchart TD
    U[POST /api/v1/upload<br/>上传 .docx] --> D[(document 表<br/>document_id/oss_key)]
    S[POST /api/v1/review/submit<br/>document_id+lib_type] --> T[(review_task 表<br/>status=pending)]
    W[worker.py ReviewWorker.run<br/>5s 轮询 FOR UPDATE 抢占] --> T
    W --> CTX[ReviewContextFactory.create<br/>lib_type→tenant→策略/表/索引]
    W --> OSS1[OSSManager.download<br/>下载源 docx]
    OSS1 --> P1[Step1 DocumentEngine.extract_clauses<br/>段落+嵌套表格→List Clause+Anchor<br/>300字/40重叠滑窗]
    P1 --> P2[Step3 分块50条并发8线程<br/>每条条款:]
    P2 --> R[RetrievalEngine.search]
    R --> R1[HybridRetriever<br/>Qdrant向量 + BM25并发<br/>RRF k=60 → Top20]
    R1 --> R2[SimilarityGateFilter<br/>top1 vector_score≥0.30 否则短路]
    R2 --> R3[MMRFilter λ=0.6 → Top6<br/>字符集Jaccard简化版]
    R3 --> R4[CrossEncoderFilter<br/>bge-reranker sigmoid≥0.65 → Top2<br/>失败降级不精排]
    R4 --> R5[OpinionDeduplicator<br/>standard_opinion 去重]
    R5 --> J[JudgmentEngine.evaluate]
    J --> J1{策略路由 STRATEGY_MAP}
    J1 -->|TECH| J2[TechPromptStrategy<br/>核增审计/错误匹配双轨<br/>关键词前置硬过滤]
    J1 -->|BIZ| J3[BizPromptStrategy<br/>语义穿透+意见唯一准绳]
    J2 --> LLM[LLMClient DashScope qwen-plus<br/>temp=0.01 60s 3次重试]
    J3 --> LLM
    LLM --> J4[_extract_json 容错解析<br/>失败→is_violation=False]
    J4 --> ENR[_enrich_opinion<br/>按 rule_id 回填 standard_opinion]
    ENR --> RISK{is_violation?}
    RISK -->|是| RI[RiskItem{clause,judgment,annotation_text}]
    RI --> A[Step5 AnnotationEngine.apply_annotations<br/>倒序插入:整段标黄+红字意见段落<br/>防重指纹]
    A --> OUT[local_storage/output/<br/>task_annotated.docx + task_result.json]
    OUT --> OSS2[OSSManager.upload<br/>review_results/...]
    OSS2 --> TU[(review_task<br/>status=completed+stats_json)]
    TU --> K[Kafka task_completed 可选]
    D -.被 W 读取.-> W
    RUL[(规则库 MySQL standard_rule(_v2)<br/>← /rules/add|update|delete<br/>← /sync/rules 三写同步)] -.被 R 检索.-> R
```

节点表格：

| 节点 | 入口(文件+函数) | 输入输出结构 | 模型/工具/服务 | 持久化 | 失败处理 | 状态 |
|---|---|---|---|---|---|---|
| 上传 | app/api/router.py `upload_file` | UploadFile→`document{document_id,file_name,oss_key,file_type}` | OSS | MySQL document 表 | OSS 失败降级本地路径存 oss_key（断链见 R6） | IMPLEMENTED |
| 提交任务 | router.py `submit_review` | `{document_id,lib_type}`→`review_task{task_id,status=pending}` | — | MySQL | 未校验 document_id 存在性，坏 ID 延迟到 Worker 才失败 | PARTIAL |
| Worker 抢占 | worker.py `ReviewWorker.run`→dao.py `claim_pending_task` | pending→processing | MySQL 悲观锁 | MySQL | 无 stuck-task 回收 | PARTIAL |
| 解析切分 | app/engines/document/parser.py `extract_clauses` | docx→`(doc_obj, List[Clause])`，Clause{id,text,DocumentAnchor} | python-docx | 内存（doc_obj 供批注复用） | 坏文件→DocumentParseError→任务 failed | IMPLEMENTED |
| 混合召回 | retrieval/retriever.py `HybridRetriever.retrieve`+`RRFFuser.fuse` | Clause.text→`[{rule_id,rrf_score,vector_score,bm25_score,payload}]` Top20 | Qdrant(bge-large-zh)+BM25Okapi(jieba) | Qdrant collection / BM25 pickle 缓存 | 单路失败退化单路 | IMPLEMENTED |
| 过滤精排 | retrieval/filters.py 四连过滤器 | Top20→门控→Top6→精排 Top2→去重 | bge-reranker-base | — | 短路返回[]；精排失败跳过阈值 | IMPLEMENTED |
| LLM 判决 | judgment/engine.py `evaluate`+strategies.py | clause+候选→`JudgmentResult{is_violation,thought,matched_rule_id,matched_opinion}` | qwen-plus | 内存（最终落 JSON） | 全部 fail-open 为"合规" | IMPLEMENTED |
| 批注回写 | document/annotator.py `apply_annotations` | `List[RiskItem]`→批注 docx | python-docx+`_p.addnext` XML 指针 | 本地 output 目录 | 单条失败跳过、指纹防重 | IMPLEMENTED |
| 结果输出 | worker.py `_process_task` L165-199 | docx+JSON→OSS→签名 URL | OSS/Kafka | OSS + review_task | JSON 上传失败仅告警 | IMPLEMENTED |
| 规则库维护 | router.py `batch_add/delete/update_rules`+`sync_rules`；scripts/upload_rules.py(CSV→MySQL) | 规则三写：MySQL→Qdrant→BM25 重建；qwen-flash 抽关键词/同义词 | qwen-flash | MySQL/Qdrant/pickle | 从写失败不阻断主写并回传 synced 标志 | IMPLEMENTED |

**缺失节点（对编写链而言）**：企业证据检索、响应矩阵、目录生成、分章节生成、确定性商务校验（报价/工期/签章/暗标）——全部 MISSING。

### 4.1（深挖 1）策略化 LLM 判决设计

- **策略模式架构**：`BasePromptStrategy` 抽象基类只约束 `build_prompt()→(system,user)` 与 `parse_response()→JudgmentResult` 两个接口（strategies.py L26-58）；`STRATEGY_MAP: {TECH: TechPromptStrategy, BIZ: BizPromptStrategy}`（L483-486）；引擎按 `context.strategy_type` 动态实例化，无 if-else 硬编码（judgment/engine.py L103-110）。**扩展第三种策略 = 实现一个类 + 注册一行**——这是本仓库最值得借鉴的判决扩展点设计。
- **租户→策略路由**：`ReviewContextFactory`（context.py L94-165）把 lib_type→tenant→(db_table, qdrant_collection, bm25_key, stopwords, strategy_type) 一次收敛，全管线只读传递 frozen dataclass。审查规则散落在路由表而非业务代码。
- **TechPromptStrategy（V1 技术标）双轨制**：
  - 轨道分类：规则 `standard_opinion` 含"核增/注意"→audit 轨（核增审计提醒），否则 error 轨（历史错误匹配）（`_classify_rules` L186-208）；
  - 再做关键词+同义词前置硬过滤（L210-231），全不命中则**不调 LLM 直接判合规**（engine.py L70-72 短路——省 token 的确定性闸门）；
  - audit 轨 prompt 是"实体层级核查"：锁定目标实体 → 允许下义词（干式变压器⊂变压器）触发偏离，**绝对禁止上义词**（"电气设备"≠"箱变"）触发（L313-330）——用 prompt 约束 LLM 泛化，工程化地把"核增判断"变成可执行判定规则；
  - 输出 JSON 三分类：偏离/符合/不相关；`judgment in ("偏离","需批注")` 才算违规（L176-177）。
- **BizPromptStrategy（V2 商务/合同）三防呆**：①语义穿透（PBA=可利用率、质保金=保留金，L359-362）；②克制发散（仅泛泛提及一律判合规，"绝对不要…自行脑补其他风险" L363-365）；③**以规则库 standard_opinion 为唯一准绳、主动丢弃 LLM 生成的 violation_summary**（parse_response L414-422 注释"最终意见来自 standard_opinion"）——即：**LLM 只做二值判决，批注文案必须来自规则库原文**，杜绝模型自由发挥污染批注。这是对我们审校链最有价值的防幻觉设计之一。
- **判决数据结构**：`JudgmentResult`（schemas.py L58-76）仅 4 字段：`is_violation: bool, thought: str, matched_rule_id, matched_opinion`。V1 的 `judgment="偏离"` 与 V2 的 `is_violation=true` 在此归一（L60-64 注释）。
- **置信度处理：不存在置信度字段。** 判决是硬布尔；检索侧的 rrf_score/cross_score 仅供漏斗筛选，不进入判决结果，也不输出给下游（JSON 结果无 score）。配合全链 fail-open（空回复/JSON 解析失败/LLM 异常→is_violation=False，engine.py L75-95），系统明确取向"**宁漏报不误报**"（Tech SYSTEM_PROMPT"绝不轻易推断、绝不泛化…只有在满足特定触发条件时，才允许拦截"，L118-122）。**对我们而言：借鉴其"规则库为唯一文案来源 + fail-open"，但必须补上置信度字段与"低置信转人工"路径（它没有）。**
- 判决回填：`_enrich_opinion`（engine.py L112-147）当 LLM 未返回 opinion 时按 matched_rule_id 精确回填；**匹配不到时兜底取 candidates[0] 的意见**——存在错误归因风险（7 R3）。

### 4.2（深挖 2）混合检索组合与参数

- **组合方式**：每条条款并发双路（ThreadPoolExecutor 2 workers）：Qdrant（bge-large-zh-v1.5，1024 维，cosine，`normalize_embeddings=True`，查询时实时编码）+ BM25Okapi（jieba 分词，停用词过滤；语料 = rule_content+standard_opinion+expected_clause+keywords+synonyms+rectification_guidance 拼接，bm25_manager.py L114-129）。RRF：`Σ 1/(k+rank+1)`，按 rule_id 聚合，**只取排名不取分值**（retriever.py L46-83）。
- **过滤链**（Pipes-and-Filters，可插拔，engine.py L46-55）：
  1. `SimilarityGateFilter`：RRF Top-1 的 **vector_score** < 0.30 → 整条条款短路（性能保护；纯 BM25 命中而向量缺席时会被拦截）；
  2. `MMRFilter`：λ=0.6 贪心选 Top6；相关性用 rrf_score 归一化，多样性用**候选文本字符集 Jaccard**（代码注释自认"简化版，避免重新 Embedding"）；
  3. `CrossEncoderFilter`：`(clause_text, rule_content+"["+keywords+", "+synonyms+"]")[:400]` pair → bge-reranker-base → sigmoid → ≥0.65 截断 → Top2；**类级双检锁共享模型单例**；
  4. `OpinionDeduplicator`：standard_opinion 去空白后 Set 去重（无意见规则保留）。
- **参数全部可运行时热调**（parameter_manager.py `UPDATABLE_PARAMS`，18 个，含类型/min/max/白名单校验、批量原子应用、Settings 缓存失效）：默认值——HYBRID_TOP_K=20、RRF_K=60、GATE=0.30、MMR_λ=0.6/Top6、CROSS=0.65/Top2、CHUNK_SIZE=50、MAX_ENRICHED_LEN=400、滑窗 300/40、MAX_TABLE_DEPTH=3、llm_concurrency=20/timeout=60s。
- 评：这是一套**教科书级的"召回→粗排→精排→去重"漏斗**，且把全部超参数元数据化 + API 热更新（比多数开源 RAG 项目完整）。两个工程妥协要注意：MMR 用 Jaccard 替代向量相似度；门控依赖 vector_score 存在性。

### 4.3（深挖 3）docx 原文高亮批注实现

- **解析与定位**：python-docx；每个条款带整型物理坐标 `DocumentAnchor`（段落 idx 或 表格 idx/行/列/单元格段落 idx）；schemas.py L18-19 注释明确："取代旧版的模糊匹配（SequenceMatcher），一切定位基于整型索引"。
- **批注机制（annotator.py）**：
  1. 风险项按物理索引**降序排序**（L113-133）再写入——倒序插入使后插段不影响未处理段落的索引（防索引漂移）；
  2. 段落：`_highlight_paragraph` 对目标段落**所有 run** 设 `run.font.highlight_color = WD_COLOR_INDEX.YELLOW`（L196-200）——**整段标黄而非命中 chunk 精确高亮**；
  3. 红字意见：`_create_annotation_paragraph` 在临时 Document 里新建"【审查意见】+意见"红字 9pt 加粗前缀段落，然后 `target_para._p.addnext(new_para._p)`——**唯一的 XML 级操作**（lxml addnext 把节点从临时文档移入正文，L174-175）；
  4. 表格：单元格命中段落标黄 + `cell.add_paragraph()` 末尾追加红字（L177-194）；
  5. 防重指纹 = 位置+意见前 20 字符（L135-147）；
  6. 单条失败跳过、保存失败抛 AnnotationError。
- **实现方式结论：python-docx 高层 API + 一处 `_p.addnext` 指针操作；不是手写 OOXML，也没有 Word 原生批注（w:comment）**。模块 docstring 声称的"底层 XML 覆写/Run 拆分"未实现——`deepcopy/OxmlElement/qn` 三个导入零使用（L15-21），是上代实现的残迹。README"红色批注"实为插入的红字正文段落。
- **对我们文档内核的启示**：审校结果回写=①整型锚点体系（解析时建立、批注时 O(1) 消费）②倒序插入防漂移 ③指纹防重 ④"意见文本来自规则库而非 LLM 自由文本"。若要求原生批注气泡或片段级高亮，需在此设计上扩展 Run 拆分（它没做）。

### 4.4（深挖 4）2865 行测试真实性

- 数量属实：`wc -l` 全部测试文件=2,865 行整。
- **测什么**：①单元：DTO 默认值/序列化、租户映射全覆盖（参数化 7 种 lib_type，test_context.py L63-110，甚至断言"映射表每个 tenant 都有策略和资源"）、文本清理/滑窗（含"无内容丢失"断言）、四过滤器边界、双策略 prompt/解析、参数管理校验；②功能：BM25 真实建索引检索（内存语料）、RRF 数学性质、过滤链串联；③API：TestClient + mock DAO/向量库——batch_sync 与新批量 API 同步（7 用例），config_api 断言 18 参数；④e2e：**真实 python-docx 建测试文档→解析→mock 检索/判决→真批注→重开 docx 验证段落数**（test_pipeline.py L157-265），批注往返 3 用例。
- **能否离线运行**：能。所有外部依赖（MySQL/Qdrant/DashScope/OSS）均 mock；不需下载模型（无测试触碰 CrossEncoderFilter）。但**import 链需要安装完整依赖**（filters.py 顶层 import sentence-transformers/torch、dao→pymysql、router→全 infrastructure），未装则整个套件无法收集——"离线"指无外部服务，不指无依赖。
- **真实性瑕疵（实锤）**：`test_rules_crud.py`（446 行）按**旧版单条 API** 写：请求体是平铺字段（无 `rules` 列表），断言顶层 `rule_id/mysql_id/qdrant_synced`、409/404 语义、上传响应含 `file_name`——与提交版 `BatchAddRulesRequest`/`BatchRuleOperationResponse`/`UploadFileResponse` 全不匹配（首提交即批量版，该测试两提交间未改动，`git diff`=0）。**这批测试运行必失败**，说明 AI 生成测试后未对 API 层做全量回归。其余四层测试与实现同步、质量真实。

### 4.5（深挖 5）审校规则库来源与可扩展性

- **来源**：人工整理的历史审校经验。V1 表字段语义：`rule_content`=历史错误示例（业主/投标方踩过的坑）、`standard_opinion`=标准审查意见（含核增/注意标记与内部报价）、`keywords/synonyms`=检索与硬过滤元数据；V2 表增加 `expected_clause`=期望条款/修改建议、`category`=系统分类（schema.sql L12-48）。`localfile/*.csv` 即 2026-05-27 导出的两库快照（V1 1,048 行、V2 2,214 行），由 `scripts/upload_rules.py`（CSV→MySQL，自动生成 TECH-0001/BIZ-0001 式 rule_id，支持 --start-id 断点续传/--batch-size）导入。
- **入库三写一致性**：`/rules/add|update|delete` 走"MySQL 主写 → Qdrant 单点覆写（以 MySQL 自增 id 为 point_id）→ BM25 全量重建（filelock 防多 Worker 竞态）"，从写失败不阻断并回传 `bm25_synced` 标志（router.py L557-842；AGENTS.md 规则 4）。删除=软删（is_active=0）。
- **LLM 增强元数据**：新增/修改规则时用 qwen-flash 自动抽取"实体名词+严格等价同义词"，prompt 带五条防呆纪律（禁动词/禁上位词/宁缺毋滥/禁引号换行/纯 JSON）（router.py L497-520）——把"规则可被硬过滤命中"做成入库质量门。
- **可扩展性评价：优秀**。多租户=加映射表行+建表即可；新策略=实现策略类+注册；新库类型=lib_type 别名。规则库既是检索语料又是批注文案的唯一来源，单一事实源清晰。

### 4.6（深挖 6）评审流水线入口与数据流

入口两个：
1. **API 写任务**：`main.py`(uvicorn)→`router.py`：`/upload`（写 document 表）→`/review/submit`（写 review_task pending）。**API 不执行评审**。
2. **Worker 执行**：`worker.py ReviewWorker.run` 每 5s `claim_pending_task`（FOR UPDATE 抢占→processing）→ 建 ReviewContext → OSS 下载源件 → `ReviewPipeline.execute`（状态回调写 retrieving→generating）→ 上传 docx+JSON → completed + stats_json + Kafka 事件；异常→failed + error_message[:5000]。

数据流主线：`UploadFile → document(MySQL) → review_task(MySQL) → Clause[](内存) → 候选规则[](内存) → JudgmentResult → RiskItem[] → annotated.docx + result.json(本地) → OSS → 签名URL`。规则侧独立线：`CSV/Excel → MySQL → (Qdrant ∥ BM25 pickle) → 检索时消费`。上下文：frozen `ReviewContext` 单向只读透传全管线。

### 4.7（深挖 7）无许可证的法律约束

- 无 LICENSE + `license="Proprietary"` + "Internal use only" = **作者保留全部权利**（中国《著作权法》自动保护；Github ToS 仅授权他人"查看/fork"于平台内使用，不授予再利用）。**任何形式的代码复制（含改写式移植、逐函数翻译）都构成侵权风险，绝对禁止。**
- 附带数据更不可触碰：规则库 CSV（含运达内部核增价格策略）与真实招标文件（国电投项目、镇江市欣源新能源、运达能源署名）属**商业秘密/企业内部资料**，使用可能违反《反不正当竞争法》，即使技术上是公开可见的。
- 可安全进行：阅读学习其架构与提示词设计思想、参数体系、测试组织方式（思想/方法不受版权保护）；依赖清单中的第三方库（均宽松许可证）可正常选用。
- 附注：`.claude/skills` 的 frontmatter 声明 license: MIT（openspec 工具生成物），该部分文本理论可引用，但其对本项目无业务价值。

---

## 5. 重点审计问题

**Q1 超长招标文件/附件/表格/扫描件如何处理？如何防截断/分块遗漏？**
- 仅支持 .docx（.doc 是虚假支持，见 3.1）；PDF/扫描件/图片附件/OCR **完全不支持**（无任何 pdf/ocr 依赖）；页眉页脚/文本框不解析（`doc.paragraphs` 只覆盖正文）。
- 防截断/遗漏手段：零宽字符清理（parser.py L30-32）；>300 字段落滑动窗口（300 字/40 重叠，L189-214，测试断言"无内容丢失"）；嵌套表格递归（深度≤3，超出告警丢弃）；合并单元格异常捕获后跳过（L170-176）——**跳过即静默丢弃**（仅 debug 日志），存在表格遗漏风险。
- 真实样例 3.2MB/113k 字/51 表可被该引擎处理（约 380+ 条块）；重叠分块可能对同一段落产生重复判决 → 由批注指纹去重（同意见）兜底，不同意见则会产生相邻多条批注。
- 大文档内存策略：CHUNK_SIZE=50 条款流式分块处理 + 每 chunk `gc.collect()`（pipeline.py L155-215）。

**Q2 六类要求如何统一成结构化条款清单？数据结构？**
- **源码未体现**——本系统不抽取要求类别。统一单元是 `Clause{clause_id, text, anchor}`（schemas.py L41-55），语义中立。六类分类需在我们自己的"条款抽取"层完成，本仓库无可借鉴实现（其规则库 `category` 字段是规则侧弱分类）。

**Q3 要求如何关联原文位置/证据/响应章节/审校结果？有无 ID 体系？**
- 有局部 ID 体系：`document_id`(UUID) / `task_id`(UUID) / `clause_id`(para_{i}_{c} / table_{t}_{r}_{c}_{p}_{ch}) / `rule_id`(TECH-0001/BIZ-0001) / `matched_rule_id`。
- 关联链：clause.anchor → 原文段落/单元格（批注可回写）；judgment.matched_rule_id → 规则库；输出 JSON risks[] 含 clause_text+matched_rule_id+matched_opinion+thought。
- **无页码、无"响应章节"、无证据概念**；批注定位粒度=段落/单元格。

**Q4 企业资料检索是否同时支持语义与精确匹配？**
- **不适用/缺失**。检索对象是审校规则库。其"语义(Qdrant)+关键词(BM25+关键词硬过滤)"双路模式可平移到企业证据检索，但本仓库无证据库实现。

**Q5 无证据/证据过期/冲突/资格不满足时如何阻止错误内容进入定稿？**
- 本系统输出的是**评审批注**而非标书定稿，因此无"阻断定稿"语义。自身取向是高精度低召回：门控 0.30 + 精排 0.65 + 关键词硬过滤 + prompt 防泛化 + fail-open。
- **全部失败路径 fail-open 为"合规"**（LLM 失败/解析失败/空候选都判不违规）——作为评审工具可接受，**若移植为"定稿门禁"则是致命漏洞，必须反向设计 fail-closed + 人工兜底**。

**Q6 章节能否拆成可单独执行/重试/修改/验证的任务？**
- 无章节概念。条款级：8 线程并发、单条款异常隔离（skip 不中断）、但**无单条款重试/重跑**；任务粒度=整文档一次性执行，失败无法部分续跑（见 Q8）。

**Q7 报价/工期/数量/资质有效期/签章/暗标检查，哪些是确定性代码、哪些依赖模型？**
- 确定性：文件类型白名单、关键词/同义词硬过滤、相似度门控/精排阈值、意见去重、滑窗切表、批注防重。**报价/工期/数量/资质/签章/暗标的业务校验：全部不存在**（既无确定性规则也无对应 prompt 模板）——判决语义全权交给 LLM 对"历史错误 vs 原文"的比对。

**Q8 中断、更换模型、补充规则后如何恢复状态、识别受影响章节并重新执行？**
- 换模型/改参数：`/config/parameters` 热更新，`ParameterManager` 使 Settings 缓存失效，**新请求立即生效**（config.py `get_settings` 每次经 ParameterManager）——但**只影响之后的任务，不追溯**。
- 补充规则：三写同步后新任务即刻用新规则；**无"已完成任务重审"机制**（无任务级重跑 API、无受影响任务反查）。
- 中断恢复：**缺失**。Worker 崩溃→任务永久停在 processing（claim 只取 pending，无超时回收）；LLM 层失败→任务 failed（有 error_message 落库）但无自动重试/重入队；Pipeline 无 checkpoint。

**Q9 可导入 Dify DSL / 可运行 MCP Server / 独立 Skill？**
- **均无**。Dify DSL：0（无 YAML 工作流文件）。MCP Server：0。Skill：`.claude/skills/*` 与 `重构/SKILL.md` 均为开发流程 skill（OpenSpec/grill-me），非业务可执行资产。
- 还缺什么才能跑起来：MySQL 8（schema.sql 建库，库名 windey_bid_center）+ Qdrant server + DashScope API key + 阿里云 OSS bucket + 本地预下载 bge-large-zh-v1.5(~1.3GB) 与 bge-reranker-base(~1GB)（代码设 HF_HUB_OFFLINE=1 强制离线模型）+ `.env`。docker-compose 缺 MySQL/Kafka 服务定义。工程上"能跑"，但任何一个外部件缺失都导致任务失败而非降级。

**Q10 哪些可合法复用？哪些仅借鉴思路？**
- **可直接复用：无**（无许可证）。第三方依赖与停用词表可自行引入。
- 仅可借鉴思路（详见第 6 节清单）：策略模式判决、规则库三写一致性、混合检索漏斗与参数热调、整型锚点+倒序批注、"批注文案唯一来源=规则库"、fail-open 取向、测试分层组织、OpenSpec 式规范先行开发。

---

## 6. 复用价值与许可

- **可直接复用（许可证兼容，具体文件清单）**：**无**。任何文件都不满足"可复制"条件（无许可证 + Proprietary 声明）。
- **需改造后复用**（指设计经重写后落地，非代码搬运）：
  1. `JudgmentResult/RiskItem/DocumentAnchor/Clause` 的 DTO 形状（schemas.py）——四表结构简单清晰，值得作为我们"审校结果"数据结构的起草蓝本（自行重写）；
  2. `UPDATABLE_PARAMS` 元数据化 + 元类热调（constants.py + parameter_manager.py）——18 参数白名单/类型/min-max/原子批量/重置，作为我们后端"运行时可调参数"设计的样板；
  3. `/rules/*` 三写一致性流程（MySQL 主 + Qdrant/BM25 从 + synced 降级标志 + qwen-flash 抽关键词入库）——规则/知识库维护 API 的形态参照。
- **仅可借鉴思路**：
  - Tech/Biz 双策略判决（含"核增双轨+实体层级上/下义词判定"prompt 工程、"意见唯一准绳+丢弃 LLM 自由文本"防幻觉）；
  - 混合检索漏斗：RRF(仅排名)→Top1 向量门控→MMR→CrossEncoder sigmoid 阈值→意见去重，全参数白名单热调；
  - 整型物理锚点 + 倒序插入 + 指纹防重的批注回写（若需原生 Word 批注/Run 级高亮需自行扩展）；
  - MySQL `FOR UPDATE` 任务抢占 + API/Worker 分离 + Kafka 可选事件；
  - 分层单向依赖纪律（api/worker→orchestration→engines→infrastructure→core，AGENTS.md 成文化的工程治理）。
- **不建议采用**：
  - fail-open 判决默认（作为门禁时致命）；`_enrich_opinion` 兜底取 candidates[0] 意见（错误归因）；
  - MMR 用字符 Jaccard（语义多样性名不副实）；门控依赖 vector_score（向量路挂掉会静默零批注）；
  - 上传 OSS 失败把本地路径写进 oss_key 的"降级"（与 Worker 下载逻辑断链）；
  - 无 stuck-task 回收的任务表设计。
- **许可证结论**：无许可证（Proprietary）+ 内部真实数据泄露 → **代码与数据双重不可复用；仅以"设计参照"身份进入我们的方案文档**，报告中引用其结构时应以"参考 biaoshuv2 的设计"并重写实现。

---

## 7. 可靠性风险清单

| # | 风险 | 严重度 | 证据（文件+位置） | 复现/验证方式 |
|---|---|---|---|---|
| R1 | **真实企业内部数据公开泄露**：规则库含运达内部核增报价（800 万/7000 元每台等）、真实招标文件（国电投围场 100MW 项目、双方公司署名）| 高（合规/法律） | localfile/standard_rule*.csv（全文可见）、localfile/测试2.docx（zipfile 读 document.xml 首部即真实标题）、config.py:36 windey_bid_center | `head localfile/*.csv`；python zipfile 提取 docx 文本 |
| R2 | **无许可证默认版权保留**，复用代码即侵权；README"Internal use only" | 高（法律） | 无 LICENSE 文件；pyproject.toml:11；README.md:296 | git ls-files 无 license |
| R3 | 判决失败一律 fail-open 判"合规"（空回复/JSON 解析失败/LLM 异常/关键词过滤后空）→ **漏检无告警**；`_enrich_opinion` 兜底取 candidates[0] 意见可能**错误归因规则** | 高（业务正确性；移植为门禁时致命） | judgment/engine.py L75-95、L134-145；strategies.py L164-184 | 读代码路径；e2e mock 失败用例可观察 is_violation=False |
| R4 | **向量检索故障→静默零批注**：retriever 捕获 Qdrant/编码异常继续（L141-150），RRF 命中全靠 BM25 时 top1 vector_score=0 → 门控 0.30 拦截全部条款 → 任务"completed"但 0 风险 | 高（静默失效） | retrieval/retriever.py L141-150 + filters.py L75-83 | 停掉 Qdrant 跑任务：日志只见"门控拦截"，stats.gated_skip=total |
| R5 | test_rules_crud.py（446 行）按旧单条 API 编写，与提交版批量 API 不匹配，**运行必失败**——测试与实现漂移，AI 生成后未回归 | 中（工程可信度） | tests/test_api/test_rules_crud.py L57（断言 data["file_name"]，而 router.py L328-331 UploadFileResponse 无此字段）、L140-168（平铺请求体缺 rules 列表 vs BatchAddRulesRequest L416-419） | 对照 router.py 请求模型与测试请求体 |
| R6 | 上传 OSS 失败"降级"把 oss_key 写成本地路径（router.py L380-382），但 Worker 一律走 OSSManager.download（worker.py L150），oss_key 非法→StorageError→任务 failed——**降级路径断链**，纯本地部署（无 OSS）时评审全不可用 | 中 | router.py L373-382；worker.py L142-150；oss_manager.py L49-66 | 断开 OSS 再提交任务 |
| R7 | `.doc` 后缀放行但 python-docx 不支持二进制 .doc（README/上传校验 vs parser 能力不符）；Worker 还把文件统一存为 .docx 名 | 中 | router.py L351；parser.py L19；worker.py L148 | 上传 .doc 后提交评审→DocumentParseError→failed |
| R8 | 无 stuck-task 回收：Worker 执行中崩溃→status 永停 processing/retrieving/generating，claim 只抢 pending，任务永久丢失 | 中 | dao.py L54-61（WHERE status='pending'）；worker.py 无看门狗 | kill worker 于任务执行中，重启后该任务永不被领取 |
| R9 | 统计口径错误：①`error` 类条款计入 gated_skip（pipeline.py L183-185）②`dedup_removed = rerank_rules - llm_judged`（L227）把"候选条次-判决条款数"当去重数，数值无意义——stats_json 对外展示失真 | 低 | pipeline.py L179-195、L227 | 读代码推演 |
| R10 | tenacity 只对 TimeoutError/ConnectionError 重试（llm/client.py L55-61），DashScope SDK 实际抛异常类型未必匹配→**多数错误实际只打一次**；`Settings.llm_api_url` 定义未用 | 低-中 | llm/client.py L55-61；config.py L53 | 读代码（运行验证被禁止） |
| R11 | 每次 `/sync/rules`、`/rules/add|update|delete` 请求都 `QdrantVectorStore()` → 重新加载 bge-large-zh-v1.5（约 30-60s+1.3GB 内存/请求） | 低-中（性能） | router.py L242、L574、L662、L739；qdrant_client.py L38-49 | 读代码 |
| R12 | CrossEncoderFilter 失败降级=跳过阈值直接放行 Top2（filters.py L259-261），且**无任何测试覆盖该过滤器**；模型类级共享+双检锁正确但无卸载路径 | 低 | filters.py L259-261；tests 无 CrossEncoder 引用（rg 验证 0 命中） | 读代码 |
| R13 | 高亮粒度=整段所有 run（非命中 300 字 chunk）→ 长段落全黄，批注定位粗；同段多意见时相邻重复段序 | 低（体验） | annotator.py L196-200 | e2e 批注往返用例可见段落级效果 |
| R14 | docker-compose 无 MySQL 服务（API/Worker 均依赖），部署故事不完整；Kafka 缺省关闭属合理 | 低 | docker-compose.yml（仅 api/worker/qdrant） | 读 yml |
| R15 | api-contract.md/architecture.md 与实现漂移（上传响应字段、SKIP LOCKED 措辞）——文档可信度打折 | 低 | api-contract.md L189；architecture.md "FOR UPDATE SKIP LOCKED" vs dao.py L54-60 | 对照阅读 |

---

## 8. 审计纪律执行说明

- 全程只读：git log/ls-files/show、Read/Grep 工具、一次 python3 zipfile 纯文本提取（未 import 仓库代码、未安装任何依赖、未启动服务、未调用 LLM）。
- README/架构文档声称均已单独核对并逐条标注（第 3 节），未将任何声称当作实现证据。
- 所有标签均附文件+函数+行号证据；无法确认处标注 UNVERIFIED（本报告无实质 UNVERIFIED 项——两提交全量可读，浅克隆未截断）。
- 初筛报告（screening-b.md 第 5 节）的结论经复核：规模/2 提交/2865 行测试/核心模块定位均属实；其"app/ 41 py ≈5.4k 行"与本审计实测 5,368 行一致。初筛未发现的增量事实：test_rules_crud 失配、数据泄露细节（具体项目名与报价）、OSS 降级断链、stats 口径错误、.doc 虚假支持。
