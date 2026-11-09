# 仓库对比矩阵（Repository Matrix）

> 审计时间：2026-10-23（GitHub API 实时取数 + 源码抽检）。共 18 个仓库：5 个指定仓库 + 8 个搜索补充 + 5 个框架参考。
> 原始证据：`research/raw/*__audit.json`（元数据+完整文件树）、`*__README.md`、深度扫描缓存文件。
> 判定口径：**可直接复用**（许可证宽松且实现可用）/ **需改造**（有价值但结构/许可证需处理）/ **仅借鉴**（设计思想可学，代码不可用）/ **不采用**（许可证冲突或无实现）。
> ⚠️ README 声明一律不算实现证据，所有"已实现"判定均以文件树+源码抽检为准。

## 一、指定审计仓库（5 个）

| 仓库 | 许可证 | Stars | 语言/规模 | 活跃度 | 实现状态 | 判定 |
|---|---|---|---|---|---|---|
| anlaiye/ark-ai-bid-agent | **无 LICENSE** | 1 | TS+JS, 62 文件 | 2026-08-03~04，仅 3 commits | MVP demo：Next.js 前端 + Node RAG 微服务；双路 RAG 与审标 Skill 真实存在 | **仅借鉴**（无许可证=默认版权保留，代码不可用） |
| 96syh/biaoshu（华正 ai 标书） | MIT | 0 | Python 1.4MB, 282 文件 | 2026-04~06 | FastAPI 后端（document/outline/content/projects/history_cases 路由）+ LiteLLM 统一模型入口；README 声称的"响应矩阵/合规审校"未见独立路由模块 | **需改造**（MIT 可复用，链路结构可取，矩阵/审校环节需自建补全） |
| joychin/LingYan-Bid-Agent | MIT | 3 | Py+TS+Rust, 658 文件 | 2026-08~09，持续提交 | Tauri 本地优先桌面 Agent；6 个业务 SKILL.md + 状态门禁 + 证据引用纪律 + 4 个 artifact JSON Schema；tracked-changes docx | **可直接复用**（Skill 纪律与 schema 设计是全量最佳参考） |
| Chengyihaowen/llm_bidwriting | **无 LICENSE** | 0 | Vue+Flask, 80 文件 | 2026-04-06，2 commits（一次性生成） | Flask 后端调 Dify API；**3 个真实 Dify DSL**（mode:workflow, version 0.5.0） | **仅借鉴**（DSL 可导入性证据 + 版本绑死反面教材；无许可证不可复用） |
| guangshu100/BidMaster-Pro | **AGPL-3.0**（README 徽章写 MIT，**冲突**） | 407 | Python, 201 文件 | 2026-05~09 | FastMCP Server（8 工具）+ CheckpointManager 断点恢复 + SkillRegistry + doc/rag engine；衍生仓库多（ZhiBiao 等） | **不采用**（AGPL 传染性 + 许可证标注不一致是红线；架构思想可借鉴） |

### 指定仓库要点备注

- **ark-ai-bid-agent**：`services/rag-api/src/retrieval.js` 实证双路检索——pgvector 语义路 + 字符 bigram Jaccard/精确 token 关键词路，`alternatingMerge` 交替合并，检索限定 `source_type='enterprise_evidence' AND status='ready'`。`skills/ark-bid-review/SKILL.md` 含资格闸门三态（eligible/conditional/not_eligible）、证据矩阵字段（证据ID/来源位置/缺失材料）与 evals 用例。是"双通道检索"的最佳实证，但无许可证。
- **biaoshu**：唯一采用"后端路由分步服务"形态（非 Skill 非 MCP）；`.agents/skills/` 下 13 个 SKILL.md 均为开发流程技能（brainstorm/check 等），非业务 Skill；`backend/optional/mcp/` 只是内置 vendored 的 DuckDuckGo MCP server，并非自研。模型层统一走 LiteLLM Proxy 的思路值得保留。
- **LingYan-Bid-Agent**：证据纪律最完备——`check_pipeline_state` 门禁、解析产物新鲜度校验（防旧版混跑）、outline.json 行号锚点 + grep 双通道导航、禁止整读（offset/limit）、出处引用键（文件名+行号区间）、五类陈述区分（未发现/尚未检查/用户补充/原文证据/模型归纳）、OCR 分档（pdf-plain/paddleocr-vl）、防提示注入条款。
- **llm_bidwriting**：`backend/utils/dify_client.py` 四函数（uploadFile → run_parse_workflow → stream_generate_chapter → run_check_workflow）证明"Dify 承载业务流程"路线的真实形态：后端变成 Dify 的粘合层，业务状态在 Dify 平台库内，DSL 版本（0.5.0）与 Dify 大版本强绑定。
- **BidMaster-Pro**：`services/mcp/server.py` 用 FastMCP 暴露 interpret_tender / generate_outline / run_compliance_check / run_full_check / run_selfcheck / search_knowledge / list_skills / get_project_status；`core/agent_framework/checkpoint.py` 提供 save / load_latest / resume_from_checkpoint（文件式 JSON 检查点）。工具面与恢复思路可借鉴，但代码本体 AGPL，闭源商业系统不得抄。

## 二、搜索补充仓库（8 个，均经 API 审计）

| 仓库 | 许可证 | Stars | 规模/活跃 | 定位与实现状态 | 判定 |
|---|---|---|---|---|---|
| FB208/OpenBidKit_Yibiao（易标） | **AGPL-3.0** | 3206 | 727 文件，2026-10 活跃 | Electron+React+C#(OpenXML 处理)+Python 工具箱：标书生成/查重/废标项检查/知识库；功能面最全 | **不采用**（AGPL）；功能清单可对照借鉴 |
| HunterLzap/rag-tender | MIT | 95 | 138 文件，2026-10 活跃 | 投标响应工作台：SourceSpan→EvidenceItem/EvidenceFact 字段级溯源 + SQLite FTS5 + 缓存向量混合检索；明言"不把向量相似度当最终判断"；有 workflow_gaps 等测试 | **可直接复用/重点借鉴**（证据链模型与混合检索同路） |
| zeronezer/bidcraft（标书匠） | Apache-2.0 | 73 | 121 文件，2026-09~10 | LangGraph 图编排（compile_graph + parser/requirement/lot/writer 等 12 agents）+ parse_cache | **需改造**（许可证最佳；作为路径 B 对照样本保留） |
| railwise-cn/tender-master | MIT | 10 | 155KB 纯 Skill | 供 coding agent 调用的九步流程 Skill：顺序锁死、用户确认门、风控台账与正文物理隔离、评分镜像目录、五专家评审、两个完整样例 | **可直接复用**（Skill 流程范本，与目标架构同路） |
| tiettuo/claude-bid-gen | MIT | 8 | 147 文件 | Extract→plan→write→assemble→compliance 脚本管道 + Skill：`bid_run.py --resume` 断点恢复、evaluation_method.json/disqualification.json 驱动、Word 渲染页数校验、memory/ 生产经验沉淀 | **可直接复用**（确定性脚本 + Agent 编排范本） |
| shandianT/bid-dog（中标狗） | NOASSERTION（EULA+LICENSE 需人工复核） | 8 | 226 文件 | Tauri 桌面 Agent；含 generation-checkpoint-pipeline 设计文档与 evidence 测试 | **仅借鉴**（检查点管道设计）；另发现仓库提交了 v5.3.zip 源码包（工程卫生问题） |
| maike-china/rejection-check | MIT | 6 | 20KB/11 文件 | DSH 插件式废标项检查（三轮风险检查+错别字检查+PDF 报告，无需 API Key） | **可直接复用**（轻量插件思路） |
| ImGoodBai/good-autobid | **无 LICENSE** | 154 | 24 文件，2025-03 停更 | 20 万字标书生成工具（提示词工程为主） | **仅借鉴**（提示词可参考；无许可证+停更，代码不可用） |

## 三、框架参考仓库（5 个）

| 仓库 | 许可证 | Stars | 与本项目的关系 |
|---|---|---|---|
| langgenius/dify | NOASSERTION（**Dify 开源许可证**：修改版 Apache2.0 + 品牌/多租户限制条款） | 159k | 仅评估其知识库 API（见 architecture-decision AD-03）；不上其 workflow |
| CherryHQ/cherry-studio | **AGPL-3.0** | 52.9k | Electron **桌面客户端**，知识库为本地客户端功能，无 headless 服务端 API；第三方 api-for-cherrystudio（141★）的存在反证其"客户端定位" |
| langchain-ai/langgraph | MIT | 43.7k | 图编排 + checkpointer 对照项（AD-04 结论：MVP 不引入） |
| modelcontextprotocol/servers | NOASSERTION | 91k | MCP Server 官方参考实现（工具命名/错误语义参照） |
| anthropics/skills | 仓库无 LICENSE（子目录各自带 LICENSE.txt） | 183k | Agent Skills 规范源（SKILL.md frontmatter 格式、渐进披露、evals 结构） |

## 四、许可合规结论（汇总）

1. **可自由复用（MIT/Apache-2.0）**：LingYan、rag-tender、tender-master、claude-bid-gen、bidcraft、biaoshu、rejection-check。
2. **AGPL-3.0（传染性，闭源商业产品禁抄代码）**：BidMaster-Pro、OpenBidKit、cherry-studio。
3. **无 LICENSE（默认版权保留，代码不可用）**：ark-ai-bid-agent、llm_bidwriting、good-autobid。
4. **自定义许可证待复核**：bid-dog（EULA）、dify（品牌与多租户条款）。
5. **标注不一致警报**：BidMaster-Pro README 徽章 MIT vs LICENSE 文件 AGPL-3.0——引用任何仓库前必须以 LICENSE 文件为准，这是本次审计最重要的合规教训。
