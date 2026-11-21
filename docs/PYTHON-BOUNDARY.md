# Python 侧模块边界声明（PYTHON-BOUNDARY）

> **定性：选项 A——独立研究工具（非生产链路）。**
> 本文件是 Python 侧模块与 Rust bid 链路职责边界的**唯一真源**。
> 创建于 #563；最后更新 2026-11-21（#196 文档卫生包：§2 补登 scripts/ 验收与评测脚本面——AUD2-20；
> 章节编号重排——原两个误编的「## 6.」（维护纪律 / SEMUL 引用口径）顺为 §7 / §9——P3.17）。

---

## 1. 定性结论

`src/llm` / `src/report` / `src/storage` + `main.py` 定性为
**独立研究工具**（数据探索 / 竞品分析 / 快速原型），**不进生产链路**。

```
· 纯 Python CLI（python main.py），不被 Rust 侧调用，也不调用 Rust 侧产物
· 无状态机、无版本管理、无审核门（对比 Rust P0-P8 链路）
· SQLite 为本地研究工作区文件，不是服务、不入库（.gitignore 钉死）
· CI 独立（python-tests.yml 只跑 pytest，不接入 bid 的 4 项检查）
· 研究管道（#601）：collect/extract/analyze/pipeline 四包同属研究面——
  采集默认本地文件源（离线可测），LLM 抽取失败降级 pending 不阻塞，
  分析产物是启发式估算，全部不回流生产链路
```

**若未来要转成生产链路辅助工具（选项 B）**，必须先修订本文件并满足：
数据模型对齐 `bid-domain`、改走 `bid-mcp` MCP 协议、报告格式复用
`export_bid_document` 定义、明确读写方、接入 P0-P8 状态机——五条缺一不可。

## 2. 模块对照与真源声明

| Python 模块 | Rust 对应 | 谁是真源 | 边界说明 |
|---|---|---|---|
| `src/storage/database.py`（`bids` 表） | `bid-domain`（`BidProject` 等领域对象） | **Rust bid-domain** | Python `bids` 表是研究侧自建的**临时数据缓存**，仅服务竞品分析检索；投标生产数据一律以 bid-domain + bid-tools 持久化为准 |
| `requirements` 字段（JSON 文本） | `bid-domain::Requirement` + 合规矩阵 | **Rust Requirement** | Python 侧的 `requirements` 是研究用的自由文本列表（见 §3 schema），与 Requirement 无对齐义务；正式抽取/合规判定只在 Rust 侧进行 |
| `src/llm/client.py`（LLM 调用封装） | `bid-tools` 的 LLM 面 | **各自独立，互不调用** | Python 封装只服务研究脚本；生产 LLM 调用一律走 Rust bid-tools |
| `src/report/generator.py`（Markdown/HTML 报告） | `export_bid_document`（DOCX/PDF） | **Rust export** | Python 报告是研究快照（Markdown/HTML），非投标交付物；正式投标文件导出只在 Rust 侧 |
| `src/llm/prompts.py`（提示词模板） | bid-tools 的提示词（如有） | **各自独立** | 研究提示词与生产提示词分开演进，不共享 |

**研究管道模块（#601 新增，同样是非生产研究面）**：

| Python 模块 | 职责 | 边界说明 |
|---|---|---|
| `src/collect/`（采集面） | 本地源（JSON/JSONL/CSV）装载→规范化→三级去重 | 默认离线本地文件源，**不内置生产级网络爬虫**；`AnnouncementRecord` 是管道唯一规范化入口；CSV 源表头别名自动归一（R31） |
| `src/collect/dedupe.py` 完备性合并（R101） | 同件后到证据填充保留者空缺字段（字段级 coalesce：冲突值 keep-first）+ `merged_fields` 分账 + 合并后证据键补登记（新指纹/新链接第三件不逃逸） | 同 dedup 键 = 同一公告证据，字段填充是**证据合并非臆造**；冲突值同批快照无时间性故 keep-first（跨批更新走 `merge_bid` 时序语义）；已收编 unique 不做级联回溯重裁（登记先到优先，如实登记的边界） |
| `src/storage/database.py` `merge_bid`/`merge_bids`（R102/R104） | 不倒退合并写入：传入空缺不覆盖库内值、传入有值新证据胜；批量单事务原子 + filled/changed/preserved 三分账 | 稀疏源重导**不抹库**（save_bid 盲覆盖保留为显式重建库工具语义）；跨批新证据胜出是变更公告修正的合法更新口径；unchanged 零写入（total_changes 可验）；`budget=0.0` 是记录在案值非空缺（十七节审计揭示，合并面不吞证据） |
| `src/collect/sanity.py`（健全性规则，R33） | 跨字段启发式告警：日期倒挂/可疑长周期/未来发布/零预算 | **告警不拒收**（区别于必填校验拒收面）；命中≠错误，研究数据质量信号随记录 `warnings` 携带 |
| `src/extract/`（抽取面） | 公告原文→LLM 结构化抽取→schema 校验→合并入库；失败进 `pending_announcements` 降级面可重试 | 抽取走研究提示词（`PromptTemplates.bid_extraction`）；「LLM 补全不覆盖」——源字段强证据，模型只填缺 |
| `src/analyze/`（分析面） | 预算分位/区域/趋势/关键词频次与月度演化（R37）/竞争密度/采购人画像（R35）/预算×区域交叉分桶（R36） | 全部**描述性统计与启发式估算**（密度分层/HHI/分桶均为研究经验口径），报告明示「估算」口径，不冒充事实 |
| `src/pipeline/`（编排面） | collect→extract→analyze→report 四阶段串联 + `pipeline_runs` 运行台账 + 增量水位 + 断点续跑（R58 `--resume`/`extract_status`） | 研究管道一条命令；台账为审计面（研究可复现），水位只服务增量文件读取；批量写单事务（R62） |
| `src/platform.py` / `src/locking.py` / `src/colors.py` / `src/progress.py` / `src/exit_codes.py`（平台与运行时基建，R39-R72） | 跨平台检测（win/linux）/文件锁/WAL 探测/控制台加固与颜色/进度/退出码 | **纯 Python 基建，无 Rust 对应**；平台差异唯一权威口径见 `docs/PLATFORM-NOTES.md`；`src/version.py` 为版本唯一真源 |
| `src/analyze/suppliers.py` / `outliers.py` / `cooccurrence.py` / `regions.py` / `rolling.py` / `relationships.py` / `charts.py`（分析深化，R47-R64） | 供应商画像/预算 IQR 离群/领域词共现/省级归一/滑动窗口环比/重复合作关系/ASCII 图表 | 全部**描述性统计**（离群是统计标记非错误；共现≠因果；重复中标是信号非认定）；省份表为封闭 34 项枚举 |
| `src/analyze/duplicates.py`（近重复检测，R79-R80） | 项目名归一 + pigeonhole 块倒排候选 + Ukkonen 带限编辑距离 + 传递闭包聚类；报告十六节与 `--export --dedupe` 消费 | **研究信号非事实认定**（一期/二期与改包重发同为 1-2 步编辑——聚族是提示人工复核）；候选对预算 5 万，超限**诚实截断**不装完成 |
| `src/analyze/quality.py` 语义扩展（R81/R89） | 四类语义审计（预算负/零/超大/非数值、日期逻辑、标识完整/唯一）+ 加权健康分 + 单位错位群体对照 | 健康分是**加权启发**（权重服务研究可信度排序，非认证）；审计揭示不拦截（`data-quality` 发现问题仍退 0，门槛面 `--min-score` 才拦截） |
| `src/analyze/windows.py` / `agencies.py` / `categories.py` / `platforms.py`（沉睡字段唤醒，R95-R98） | 响应窗口（发布→截止天数分布+短窗提示）/代理机构画像/品类分布/平台来源（域名归一+跨平台转发信号）——deadline/agency/category/source_url 四字段首次进分析面，报告十八至二十一节 | 短窗是**研究提示非违规认定**（法定 20 日起算点是招标文件发出日，本节以发布日近似偏短估计）；品类自由文本**精确匹配**归并不做词表归一（映射由研究者判断）；跨平台信号是簇成员≥2 平台的**实证**（缺 URL 不参与判定，非猜测） |

**scripts/ 验收与评测脚本面（AUD2-20 补登记 · #196 校准 2026-11-21）**：

scripts/ 顶层共 **48 个 `.py`**（实测 `ls scripts/*.py | wc -l`），按下表功能族
分组登记（各族括号内为该族文件数，八个顶层族合计 48）；子目录另有 12 个 `.py`
（4 个 Python 子包）、5 个 Rust harness 子包（Cargo 工程，非 Python）与
9 个非 Python 辅件，一并登记防再漏。**全部为验收/评测/语料工作面**：消费仓内
夹具与语料、驱动 cargo 真跑（bid-mcp `real_closeout` / `multifile_matrix` 等），
产物落 `artifacts/` / `baseline/` / `audit/`——不属 §1 研究管道生产面，产物
不回流生产链路；SEMUL 仿真族的结论引用遵守 §9 口径。

| 脚本族（文件数） | 代表文件 | 职责 | 消费边界（读 → 写） |
|---|---|---|---|
| 验收链族（5） | `run_tests.py`、`multifile_acceptance.py`、`closeout_real_test.py`、`acceptance_closeout.py`、`run_real_llm_path.py` | 每轮验收/收官编排：夹具自检 → cargo 真跑 → GT 对照 → 审计报告（四分栏五态结果 schema） | 读 `fixtures/`、`real-corpus/`、`real-samples/`、`baseline/`、`artifacts/`；写 `artifacts/`、`audit/`（验收/收官报告） |
| 基线族（1） | `baseline_run.py` | #2 基线冻结一键复现：逐文件解析结果 + 敌意件行为基线 + 环境指纹，双跑确定性比对 | 读 `real-corpus/` 全语料；写 `baseline/`（`env.json`、`MANIFEST.json`、`parse/**`、`security/**`） |
| 合成夹具族（6） | `fixture_spec.py`、`fixture_gen.py`、`synth_tender_spec.py`、`synth_tender_gen.py`、`make_425_addendum.py`、`add_1n_waiver.py` | 评测夹具与内容规格单一真源（corpus-A / synth-tender，sha256 确定性可复现） | 规格自含；写 `fixtures/corpus-A/`、`fixtures/corpus-R/`、`fixtures/synth-tender/`（`make_425_addendum.py` 默认写 `/tmp`） |
| 真实链语料族（8） | `telecom_chain.py`、`telecom_fetch.py`、`telecom_file_level.py`、`telecom_gt_draft.py`、`telecom_prepare_files.py`、`telecom_refetch.py`、`m17_real_chain.py`、`m17_inventory.py` | 通信/政采真实公告链采集、镜像落盘、溯源核验与 GT 草案 | 读 `real-corpus/telecom/`、`real-corpus/gov-procurement/`；写 `real-corpus/**`（sources/files/链报告/GT 草案） |
| 评测族（12） | `grade.py`、`b5_engine_gt_eval.py`、`real_eval_score.py`、`real_eval_gt_enrich.py`、`real_eval_gt_crosscheck.py`、`fp_sampling.py`、`title_impact_score.py`、`title_impact_summary.py`、`repro_112.py`、`repro_132.py`、`m145_repro.py`、`review_113_analysis.py` | corpus-A 判分器、引擎路径 GT 评测、真实语料 GT 草案/异源抽检/判分、issue 复现与独立审校 | 读 `fixtures/**/ground-truth/`、`real-corpus/`、`artifacts/`、运行产物 `runs/`；写 `artifacts/real-eval/`、`artifacts/title-impact/`、stdout 报告 |
| 诊断族（7） | `gh_audit.py`、`gh_deep.py`、`gh_search.py`、`engine_diff.py`、`scan_docx_scoring_tables.py`、`check_mdcore_rev_sync.py`、`xref_check.py` | GitHub 仓外审计取证、B3 双跑差分、DOCX 评分表素材盘点、mdcore rev 一致性门禁（FG-08）、跨文档一致性检查 | 读 `baseline/parse/`、`bidcore/Cargo.lock`、`research/*.md`、全仓 DOCX 素材；写 `research/raw/`、stdout 报告 |
| SEMUL 仿真族（8） | `v1_citation.py`、`v1_corpus_r.py`、`v1_darkbid.py`、`v1_export.py`、`v1_pipeline.py`、`v2_impact.py`、`v3_integration.py`、`ooxml_util.py` | Python 语义仿真验证（自认 SEMUL ≠ ENGINE_RUN，引用口径见 §9） | 读 `fixtures/`；写 `runs/`、临时产物 |
| 文档工具族（1） | `patch_docs_r10.py` | 文档状态回填（verification-plan / test-plan / README） | 读写 `research/` 计划文档与 `README.md`（`DOCS_BASE` 可覆盖） |
| Python 子包（12 `.py`） | `e2e_bid/`（2）、`fp_attribution/`（2）、`mang-dev/`（2）、`veto_gt/`（6） | #269 黑盒 MCP 调用留痕 + 人肉 LLM 中继；FP 归因/TP 误伤扫描；#76 设置面板 UI 探针；GT 增补轮裁决/合并 | 读 `artifacts/`、web-ui dist、`/tmp` 工作区（`BID_WS`）；写 `artifacts/`（`veto-gt/`、`mang-shots/`）、`scripts/fp_attribution/`、`/tmp` |
| Rust harness 子包（非 Python） | `baseline_harness/`、`bid_health_check/`、`engine_probe/`、`title_impact/`、`veto_measure/` | Cargo 探针/harness 工程（引擎双跑、健康自检、标题影响实验、否决测量） | 各自 `src/`；产物经上列 Python 编排器汇入 `baseline/` / `artifacts/` |
| 非 Python 辅件（9） | `run_bidmcp_direct.sh`、`run_pkg_direct.sh`、`rust-env.sh`、`smoke-linux.sh`、`smoke-windows.ps1`、`syntax-check.sh`、`package-mang-app.ps1`、`fixtures-requirements.txt`、`zai-llm-bridge.mjs` | 测试直跑器（分批链接防盘满）、Rust 沙箱环境自愈、离线全链冒烟、秒级语法检查、mang-app 绿色版打包、夹具依赖钉版、真实 LLM 本地桥 | 读仓内构建面；写 `dist-pkg/`、`/tmp` 日志 |

**判定规则**：任何"投标生产"语义的数据与产物 → Rust 侧是真源；
Python 侧产物（研究缓存/研究快照）**永不回流**生产链路。

## 3. `requirements` 字段 schema 说明

`bids.requirements` 列存储 JSON 文本，schema 约定如下（#563 验收 3：
不允许隐式真源）：

```json
["ISO9001 认证", "近三年类似业绩不少于 2 项"]
```

- **类型**：字符串数组（`list[str]`），元素为资格/技术要求的**人读摘要**；
- **来源**：研究侧从招标公告人工/LLM 辅助整理，**非正式抽取结果**；
- **非对齐声明**：该 schema 与 `bid-domain::Requirement` 的结构化模型
  （ID/分类/★条款/矩阵状态）**无映射关系**，禁止拿它做合规判定；
- **反序列化兜底**：损坏数据在 `BidDatabase._row_to_dict` 中回退为空列表。

## 4. 研究管道使用面（#601）

```bash
# 全链：公告源 → 采集 → LLM 抽取 → 分析 → 报告（一条命令）
python main.py pipeline --source announcements/ --db data/bids.db --incremental --html

# 分阶段单命令
python main.py collect  --source announcements/ --dry-run     # 演练（不写库）
python main.py collect  --source exports.csv                # CSV 源（表头别名自动归一）
python main.py extract  --source announcements/              # LLM 抽取（失败进 pending）
python main.py extract  --retry                               # 重试 pending 面（需 API key）
python main.py analyze  --keyword 智慧城市 --days 90 --html   # 离线纯数据报告
python main.py analyze  --compare 智慧城市,政务云 --html     # 多领域指标对照报告
python main.py db --export csv --out snap.csv               # 研究快照导出（--query 过滤，R34）
```

- **离线可测**：无 `DEEPSEEK_API_KEY`/`OPENAI_API_KEY` 或 `--no-llm`
  时抽取阶段自动降级直通（警告一次，不静默）；
- **失败降级**：LLM 失败/校验拒收的公告进 `pending_announcements`
  表（可重放载荷），`extract --retry` 换模型/提示词后重跑；
- **增量水位**：`pipeline --incremental` 只读上次成功运行后的
  新文件（`pipeline_runs.watermark`，亚秒精度）；
- **审计台账**：每次管道运行（含失败）自动登记 `pipeline_runs`
  （stages 明细 + 报告路径），研究可复现「报告基于哪次运行」；
- **fixture 全链**：`tests/fixtures/announcements/`（合成脱敏）+
  `tests/test_e2e_pipeline.py` 覆盖全部特性面，`pytest` 离线可跑。

## 5. CI 隔离

```
.github/workflows/python-tests.yml
  触发路径：src/** 、tests/** 、main.py 、requirements.txt 、pytest.ini
  动作：pip install -r requirements.txt → python -m pytest tests/
```

- Python 测试**只**在上述路径变更时触发，不混入 bid 的
  windows-check / windows-release / rev-sync / web-ui-tests；
- 反向隔离：Rust 侧检查（cargo 等）不受 Python 文件变更触发；
- 该 workflow 同样挂 concurrency 组（#568 全仓纪律），
  `cancel-in-progress: true`（检查类，可安全取消）。

## 6. .gitignore 钉死项

```
output/            # Python 报告输出目录（研究快照，可再生）
data/              # SQLite 研究数据库（本地工作区，不入库）
.pytest_cache/     # 测试缓存
__pycache__/       # 字节码缓存
```

## 7. 维护纪律（#563 验收 4；原误编为「## 6.」——#196 编号校准 2026-11-21）

**未来新增任何 Python 模块，必须同步更新本文件**：

1. 在 §2 对照表中登记模块名、Rust 对应物、真源归属；
2. 涉及数据存储的，在 §3 补 schema 说明；
3. 模块 docstring 首行必须带「非生产链路——仅供研究」标注
   （与本文件定性一致）；
4. 需要跑测试的，路径加入 python-tests.yml 的触发列表；
5. scripts/ 下新增脚本，按 §2 scripts/ 面的功能族归组登记（新起族须写明
   代表文件、职责与消费边界）——AUD2-20 整改项，#196 校准 2026-11-21。

违反任一条 = 新的隐式真源 = 重复 #563 的问题。

## 8. 关联（原编号 7——#196 编号校准 2026-11-21）

- #554 PR——引入 Python 模块（本边界声明所回应的对象）
- #563 Issue——边界任务（本文件即其交付物）
- #457 PR——ai-bid 三层架构（bid-domain / bid-tools / bid-mcp）
- `AGENTS.md` 0.0.10——引擎能力 ≠ 产品可用（模块存在 ≠ 职责清晰）

## 9. SEMUL 引用口径（TA-2 / FG-06 残余收口——审计 #135；原误编为「## 6.」——#196 编号校准 2026-11-21）

**规则：凡结论来自 Python 语义仿真（`v2_impact.py` / `ooxml_util.py` / `v1_*.py` 等自认
`SEMUL ≠ ENGINE_RUN` 的脚本——已按 §2 scripts/ SEMUL 仿真族登记），文档/报告/issue
引用时必须带 `(SEMUL)` 标注。**

- 仿真件验证的是**语义设计的自洽性**，不构成对 Rust 产品面行为的验证；
- Rust 产品面结论只能引用 cargo 测试（如 `four_contracts.rs` / `changediff_chain.rs`）
  或真跑产物；
- 历史文档中以「V1/V2/V3 全绿」表述仿真结果的段落，阅读时按本节口径重新解释
  （audit/false-green-register.md FG-06 登记的假绿族不再新增）。
