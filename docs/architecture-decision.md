# 架构决策记录（Architecture Decision）

> 决策编号 AD-01~AD-07。每条含：背景→决策→理由→被否方案→复议条件，并标注**验证状态**（词典见 v2 节尾）。
> v2 变更（评审反馈落实）：① 全部决策加验证状态标注——"源码支持的设计结论"与"已实测"严格分开；② AD-01 论据 1 收紧（DSL 跨版本问题只能证明迁移风险，不能单独证明无法实现补遗回退——补最小对照实验 EXP-1）；③ 新增 AD-07（文档引擎集成决策，基于 docs/doc-engine-audit.md 审计）。
> 全部基于 18 个仓库的实证审计（research/repository-matrix.md、research/workflow-audit.md）+ 文档引擎只读审计（docs/doc-engine-audit.md）。

## 验证状态词典

| 标注 | 含义 |
|---|---|
| `TESTED` | 已实测（实验报告/测试可复现） |
| `VERIFIED_SOURCE` | 结论有开源仓库源码/官方文档一手证据 |
| `DESIGN_ASSUMPTION` | 设计推断，未经实现验证（可能被推翻） |
| `PENDING` | 验证计划中（见 research/verification-plan.md） |

## AD-01 不采用完整 Dify 平台作为编排层 `VERIFIED_SOURCE（论据）+ PENDING（EXP-1 实测补证）`

**决策**：不部署 Dify workflow/Chatflow 承载标书流程；标书业务不依赖其 DSL。仅可选使用其知识库 API 作为对比适配器（见 AD-03）。

**理由（实证）**：
1. **DSL 死板**：Dify workflow 适合固定单链路；标书流程是证据状态驱动的多阶段可重入流程（补遗文件到达→增量抽取→受影响章节 DIRTY 重跑），当前设计用状态机表达条件回退与影响面分析。~~DSL 表达不了~~ **（v2 收紧）**：已有证据（DSL 跨版本兼容的公开问题记录）只能证明**版本迁移存在风险**，不能单独证明 Dify 无法实现补遗回退或章节重跑——该结论待最小对照实验 EXP-1（verification-plan §4：五场景实测，含中断恢复/规则修改成本/状态迁移面）补证后升 `TESTED`。
2. **状态被平台持有**：llm_bidwriting 实证——后端退化为 dify_client.py 粘合层，业务状态一半在 Dify 平台库，**取不干净**（R-12）。`VERIFIED_SOURCE`
3. **版本绑死**：其 DSL schema 0.5.0 与现行 Dify 大版本存在迁移鸿沟；每次升级是持续成本（llm_bidwriting 的 3 个 YAML 即实证）。`VERIFIED_SOURCE`
4. **重量**：自托管栈为全家桶（api/worker/postgres/redis/向量库/sandbox/nginx 多容器），与"轻量可维护"目标冲突。`VERIFIED_SOURCE`

**复议条件**：EXP-1 实测若显示 Dify 在 E2（补遗回退）/E3（中断恢复）/E5（状态迁移）成本相当或更低，则 AD-01/AD-02 的**理由区**按实测改写（决策本身仍可维持，但依据必须是实测维护成本而非缺陷指控）。出现强需求"非技术人员可视化编排单节点任务"时，可把单点原子能力外包给 Dify，业务状态机不迁移。

## AD-02 编排采用路径 A：Skill 驱动封闭 Agent + 后端状态机 `VERIFIED_SOURCE（存活实证）+ TESTED（M1 状态机 E_STATE 守卫与幂等，TC-07/TC-11）+ DESIGN_ASSUMPTION（弱模型约束效果——Skill evals 待测）`

**决策**：路径 A（SKILL.md 定义路径 + 8~9 个 MCP 工具 + 后端状态机/领域库）优于路径 B（Agent 自由规划 / LangGraph 图编排）。MVP 直接按路径 A 实施。

**对比矩阵**：

| 维度 | 路径 A：Skill+MCP+状态机 | 路径 B：自由规划/图编排（LangGraph 型） |
|---|---|---|
| 低能力 Agent 兼容 | ✅ 路径写死，门禁在后端（E_STATE 拒越级） | ❌ 依赖模型规划力，弱模型跑偏（tender-master"顺序锁死"的存在即证明业界踩过此坑） |
| 可恢复性 | ✅ 状态在自家库，断点/影响面分析任意实现 | ⚠️ 依赖框架 checkpointer（BidMaster 文件式 checkpoint 仅有 latest，无影响面）；LangGraph 有 checkpointer 但状态模型受框架约束 |
| 可测试性 | ✅ MCP 工具契约测试 + 状态机单测 + Skill evals（ark/LingYan 均有 evals 先例） | ⚠️ 图行为测试要 mock 节点集合，回归面大 |
| Token 成本 | ✅ 封闭路径→按阶段加载 references（渐进披露），长文件靠 offset/limit（LingYan 禁整读纪律） | ❌ 自由规划上下文易膨胀重试 |
| 维护成本 | ✅ 状态机表+Skill 文档化，人均可维护 | ⚠️ 图结构演化需懂框架；bidcraft 12 agent 图是维护反例风险 |
| 实证存活度 | LingYan / tender-master / claude-bid-gen 三个活跃实现（MIT） | bidcraft（Apache-2.0）单点存在，LUV803 宣称未深扫（UNVERIFIED） |

**结论**：路径 B 元素（图编排）仅在"多 Agent 并行起草+复杂回退"需求出现时局部引入（bidcraft 可作那时对照），MVP 不需要（见 AD-04）。**v2 备注**：路径 A 对"低能力模型"的实际约束效果是 DESIGN_ASSUMPTION——TC-11（越级防护）+ Skill evals 执行后升 TESTED。**v3 回填**：M1 Rust 状态机（m1/src/state.rs）已实测 TC-11 越级 E_STATE 零副作用 + TC-07 sha256 幂等 no-op（run_tests T11b 把关）；弱模型约束效果仍待 Skill evals。

## AD-03 RAG 知识库选型：自建薄服务为默认，Dify API 为可选适配器，Cherry Studio 否决 `VERIFIED_SOURCE`

**背景**（用户问）：不部署完整 Dify（太重），但需要它的 RAG 知识库能力；Skill 驱动封闭 Agent 完成文件处理→入库→检索；Cherry Studio 备选；"不方便自建的话用 Dify API 怎么样"。

**决策**：知识库做成 `KBAdapter` 接口（ingest/search 两个方法），**AdapterA 自建薄服务为默认实现**；**AdapterB = Dify Knowledge API 仅作为检索质量 A/B 对比与过渡期兜底**（锁版本+契约测试）；**Cherry Studio 知识库否决**。MCP 契约中知识库不是独立工具，而是 `import_tender_files` / `search_evidence` 的可替换实现层（docs/bid-mcp-contract.md 附录 A）。

**理由**：

| 维度 | A 自建（PGVector/Qdrant+FTS+确定性切块） | B Dify KB API（自托管） | B' Dify Cloud | C Cherry Studio |
|---|---|---|---|---|
| 部署重量 | 一个服务+一个向量库（或 PGVector 零新增） | **全家桶容器栈**（重量回来了） | 零部署 | 桌面应用（无服务端） |
| 数据边界 | ✅ 私有 | ✅ 私有 | ❌ **标书/资质出域，投标业务一票否决（R-09）** | 本地（但仅限单人桌面） |
| 分块控制 | ✅ 按条款编号结构切块，chunk_id 稳定，证据链可回溯 | ⚠️ 归 Dify：只能靠 create-by-text 逐段注入锚点硬拼 | 同左 | 客户端黑盒 |
| 精确匹配通道 | ✅ FTS/结构化索引等值查询（编号/型号/金额/日期） | ⚠️ hybrid 可配关键词权重，但无确定性精确保证，混合权重黑盒 | 同左 | — |
| 版本漂移 | 自控 | ⚠️ 端点命名/参数多次变更（create_by_file→create-by-file），15MB 文件上限需拆分 | 跟随云版本 | — |
| 许可证 | 自有 | 修改版 Apache2.0（多租户/品牌条款，对外 SaaS 需商业授权） | SaaS 条款 | **AGPL-3.0**（复用其代码传染） |
| 业界实证 | ark（pgvector+bigram）、rag-tender（FTS5+向量）均为 MIT 可复用 | llm_bidwriting 绑死 0.5.0 | — | 第三方 api-for-cherrystudio 另建 API 反证其客户端定位 |

**关键原则**：**解析和切块是后端确定性代码，Agent 只做编排**（调导入工具、核对统计数字、重试失败件）。"条款因分块遗漏丢失"（R-01）这类最重的风险必须由代码兜底，不能靠模型自觉。**v2 备注**：AdapterA 的检索质量是否 ≥ AdapterB 是 PENDING（TC-10）。

## AD-04 MVP 不引入 LangGraph/图编排框架 `VERIFIED_SOURCE`

状态机用"枚举+转换表+乐观锁"实现于后端（bid-domain-model.md §2），不引框架。理由：转换表 ~10 个状态、回退规则 1 条（DIRTY 重跑），LangGraph 的价值（复杂图/并行/人机中断）在此规模下是负资产；换框架成本 = 迁移全部状态语义。**复议条件**：多 Agent 并行起草（>3 个并发写作 Agent）或跨阶段复杂回退图出现时重评（对照 bidcraft）。

## AD-05 文档内核独立、接口最小、ID 隔离 `REVISED（v2：接口假设已被引擎审计修正）`

- 不修改/不替换现有文档内核；经**稳定接口**访问。
- **v2 修订（依据 docs/doc-engine-audit.md）**：原设想的 `create_block/update_block/get_block/render/export` 五函数最小面与引擎实际能力不匹配——引擎已产品化的契约面是 **mdcore 操作流（op/anchor/revision/event）+ workbench 八步命令 + wasm 出口（export_docx/import_docx/WasmWorkbench）**，且其证据系统（三态/只降不升/显式重验）与标书业务同构。集成接口**对齐引擎既有契约**（AD-07），不再要求引擎实现本业务自设的五函数面。
- 文档块 ID（DOC-* = 引擎 BlockId）由内核签发，业务侧只存 `content_ref` 引用 + DocumentRef（版本+指纹）快照；REQ/EV/SEC 与 DOC 三个命名空间**永不混用、不做映射改写**（用户要求，维持）。
- 导出产物经 sha256 校验回传；页数统计以 Word 渲染口径为准（claude-bid-gen 实证：LibreOffice 页数不可信）——渲染级自动化复验依赖引擎 G6（office-f C 路线产品化，doc-engine-audit §4）。

## AD-06 可测试与可回滚 `VERIFIED_SOURCE（先例）+ PENDING（本项执行）`

1. 每个 MCP 工具一条契约测试（含幂等重放）；状态机转换全覆盖单测。
2. 合成招标文件埋点回归集（research/test-plan.md）：条款完整性、精确匹配、断点恢复、审校命中四类是发布门禁。**v2 补**：可执行夹具三件套（文件+标准答案+预期状态转换）与跨文档一致性检查脚本见 verification-plan §2。
3. KBAdapter 可切换 → 检索层 A/B（TC-10）不锁定供应商；模型层沿用 biaoshu 的 LiteLLM 统一入口思想（BYOK、可换模型）。
4. 复用代码白名单仅限 MIT/Apache 仓库（LingYan、rag-tender、tender-master、claude-bid-gen、bidcraft、biaoshu、rejection-check）；AGPL/无许可仓库只读设计不抄代码（R-10）。

## AD-07 文档引擎集成：对齐 mdcore 既有契约面，差距走引擎能力需求清单 `VERIFIED_SOURCE（引擎审计）+ DESIGN_ASSUMPTION（映射契约，V3 验证后升 TESTED）`

**背景**（v2 新增）：对 mmqz/mdcore（main=6daeace）与 mmqz/cleanroom-analysis 的只读审计（docs/doc-engine-audit.md）确认引擎成熟度高于原假设。

**决策**：
1. **集成姿态**：不自建文档编辑/证据/审校内核，**直接对齐引擎契约**——业务侧把 REQ/EV/CMP/SEC 映射到引擎对象（§5 映射表）；证据三态、只降不升、显式重验、human: 审批门禁、原子发布、乐观并发全部继承引擎实现，业务层不重复防守。
2. **映射要点**：业务 content_ref = 引擎 BlockId；失效判定用引擎内容指纹、审计用版本戳（引擎定谳原则）；编辑态引用 Locator::MarkdownBlock、导出态 Locator::DocxParagraph 双载体；审批动作映射 Review 命令且操作者前缀强制 human:。
3. **差距处理**：交付格式面缺口（G1 目录域/G2 文档级样式/G3 暗标元数据清零 = P0；G4 分节页码/G5 模板套用/G6 渲染复验/G7 文本框读面 = P1）**不在业务侧变通实现**（暗标元数据清零等无法在引擎外可靠完成），统一走引擎能力需求清单（doc-engine-audit §6）由引擎团队排期——在补齐前，M3/M4 里程碑的导出面验收范围相应缩减（V1-d 依赖 G1/G2/G3）。
4. **职责边界**（防范围蔓延）：PDF/OCR 表格提取、招标语义规则、知识库检索均**留在业务侧**，不请求引擎实现（doc-engine-audit §6"明确不需要引擎做的"清单）。

**复议条件**：引擎团队对 P0 项排期显著晚于本业务 MVP 需要 → 暗标场景降级为"人工后处理 + 检查单"过渡方案（R-11 缓解措施临时降档，风险册记录）；或引擎侧给出等价替代路径（如 G1 以静态目录方案交付）。V3 三问断言脚本（verification-plan §3.3）执行后本条映射契约升 TESTED。

## AD-08 实现语言：核心全 Rust，运行产物契约类型化 `TESTED（bidcore M1 端到端）`

**背景**（v3 新增，用户裁决）：文档引擎（mdcore）为 Rust。若业务后端用 Python，
集成边界为 FFI/IPC + 双语言双份 schema 维护——db.json 契约靠 docstring「冻结」，
漂移只能靠人肉比对（研究阶段 grade.py docstring 即此形态），属结构性兼容风险。

**决策**：
1. **核心全 Rust**：状态机（bid-domain）/ 解析（bid-parse）/ 切块检索（bid-kb）/ 工具薄壳（bid-tools）/
   判分器（bid-grade）五 crate 工作区 `bidcore/`。同语言可直接消费 mdcore 契约类型（AD-07 映射面），
   部署单二进制无运行时依赖矩阵。
2. **运行产物契约 = serde 共享类型**（`bid-tools/src/schema.rs` 单一真源）：判分器与后端链接同一组类型，
   schema 漂移在编译期即被捕获；运行期防线 = 反序列化拒绝（自测固化：伪装类型字段在解析 db.json 时即报错）。
3. **Python 保留面收敛为存档用途**：夹具生成器（fixture_gen.py——33 文件已 sha256 冻结，
   生成器是数据出处，不进 CI 主链）与 xref_check.py（研究文档检查器，非产品）。
   原 grade.py 被 bid-grade 完整取代（含七判分项、反标记回声对齐器、11 类破坏注入自测）。
4. **外部引擎适配器钉版本**：PDF 文本层（poppler pdftotext）/ 扫描层（pdftoppm + tesseract chi_sim）
   为外部进程适配器，入组件版本矩阵（test-plan §5.2）——解析引擎从来不是手写自由度，
   引擎版本差异走矩阵分档，不属语言决策范围。

**实测依据**（M1 端到端，corpus-A 真实夹具）：TC-01 导入+抽取 G1 召回 100%（160 REQ 全量抽取，
25 GT 对齐器全命中）；TC-02 25 精确查询全命中 + 5 次重放一致；TC-07 sha256 幂等 no-op；
TC-11 状态机越级 E_STATE 零副作用。判分器自测：完美库 + 11 类破坏注入全捕获 + 类型化 schema 拒绝。
`cargo test --workspace` 12 用例全绿（含真实夹具端到端）。

**复议条件**：若 M3（起草）需要快速接模型的探索期脚本，允许临时 Python 探针做**研究验证**，
但产品链路（工具面 + 判分面）不允许 Python 产出回归。
