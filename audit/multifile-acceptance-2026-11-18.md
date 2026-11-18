# 多文件统一矩阵验收（#114 · 2026-11-18）

> **任务面**：#114 完整多文件投标项目验收——评分表驱动大纲与跨件一致性。
> **执行**：zai-fifth（分支 `zai-fifth/114-multifile-matrix`，报告型验收——不改产品源码，issue 明令禁止扩功能）。
> **方法**：`scripts/multifile_acceptance.py --all` 一条龙（素材对账 → 规格 → Rust 真跑 harness `bidcore/crates/bid-mcp/tests/multifile_matrix.rs` → GT/期望独立评审）。评审器独立于被测面（GT 判分在 Python——Rust 只落事实与结构不变量断言，防「断言迁就实现」）。
> **基线**：main `59790da`（2026-11-18 检出）。

## 0. 结论速览

| 验收面（issue 正文） | 判定 | 一句话证据 |
|---|---|---|
| 文件清单哈希/项目身份/真实合成标记 | ✅ | 31 件全对账，登记锚（file-level-report / corpus-A manifest）**31/31 MATCH 零漂移** |
| 统一 REQ 溯源 | ✅（含一项设计边界登记） | 全部 REQ 锚点文件 ⊆ 导入集（硬断言零跨项目泄漏）；辅探针证多主件 REQ 合并溯源在位（302+21） |
| 跨件冲突 | ⚠️ 部分 | 同号异文冲突检出 ✓（澄清件 2/2）；**异号语义冲突（控制价 480→465 万）检不出**——最小面设计边界（发现 F-5） |
| 评分映射逐项正确性 | ⚠️ 机制闭环/语义未证 | 门 1h 闭环 18→0、28→0、4→0（#153 正门通道真跑）；映射为 bigram 启发式（决策留痕），逐项语义正确性超出确定性验收边界（登记） |
| 篇幅分配 | ✅ | 配额守恒**逐项目精确 48000/48000**；分布与映射份额如实落盘 |
| 补遗影响 | ✅（合成对照面） | EV-02 开标日翻转 pre=可绑 / post=EXPIRED 禁绑（GT-02 ✓）；DIRTY+指令面在位 |
| 可复验步骤及未完成原因 | ✅ | `--all` 单命令重放（确定性二次复跑同数）；未覆盖面 §7 逐条登记 |

**总裁定：验收通过（含 7 项真实发现 + 6 项未覆盖登记）**。真实多件统一矩阵首次在 unicom-ry（招标文件+技术规范+详细评审表+投标一览表）与电信淮安（主文件+技术规范+报价+合同）两组**真实四件套**上全链跑通——2026-11-13 可行性注记「仓内同项目多件真实素材不存在」**实测不成立**（telecom/parse-input B1.5 起已入库，本验收即以其为载体）。

## 1. 素材对账（31 件——清单/哈希/身份/真实合成标记）

- **真实件 12**：telecom/parse-input 五组（unicom-ry×4、huaian×4、cqyd×2、zjyd×2）——sha256 对 `real-corpus/telecom/file-level-report.json` 登记值**逐一 MATCH**（重取复现链 `telecom_refetch.py` 在案，B1.5 口径）。
- **合成件 19**：corpus-A 六件主集（A/B1/B2/B3/C/澄清修改——`澄清修改文件-3.1.1.docx` 为 #425 生成件，合成标记如实）+ 证据 13 件——sha256 对 `fixtures/corpus-A/manifest.json`（v0.6）**逐一 MATCH**。
- 项目身份：materialize 留痕（如 unicom-ry 四件同出「2026年中国联通软研院管理中台国资监管中心研发项目」zip 解压件；淮安四件同出「中国电信股份有限公司淮安分公司2026年淮安本地视频能力平台建设采购项目」）。
- 投标人侧证据（EV-01/02/03，unicom/huaian 项目用）为**合成投标人自报面**（收官真测同款纪律，`real_evidence=false` 落盘）。
- 明细：`artifacts/multifile-acceptance-20261118/inventory.json`（`hash_anchor_drift=0`）。

## 2. 六项目矩阵真跑结果

| 项目 | 性质 | 件数 | 导入 | REQ | 评分项(hard gate 排除后) | 冲突 | 建纲/配额 | validate |
|---|---|---|---|---|---|---|---|---|
| corpusA-full | 合成对照 | 19 | 19 入账（B2 扫描件 Failed→waive，见 F-2） | 123 | 4（+10 否决） | 2 | 26 节/48000 | ok（blocker 0） |
| unicom-ry | **真实** | 7 | 7 入账（详细评审表 Failed→waive，见 F-1） | 302 | 18（+88 否决） | 0 | 45 节/48000 | ok（blocker 0） |
| huaian | **真实** | 7 | 7 入账（零失败） | 371 | 28（+122 否决） | 0 | 54 节/48000 | ok（blocker 0） |
| cqyd | 真实辅面 | 2 | 零失败 | 339 | 29 | 0 | 建纲探针 ok | — |
| zjyd | 真实辅面（无主件） | 2 | 零失败 | 37 | 0 | 0 | 建纲探针 ok | — |
| unicom-ry-alt | 真实辅探针 | 3 | 零失败 | 323（302+21） | 18 | 0 | 建纲探针 ok（74 节） | — |

- 全链面（前三个）：import → extract → provenance → outline+matrix → 证据登记/绑定 → #153 评分映射 → 审批门 → 全叶起草（mock）→ check_scoring_coverage → validate（blocker=0）→ 补遗探针 → 有效期翻转探针。
- **确定性**：二次复跑逐项目 REQ 数完全一致（123/302/371/339/37/323）。
- `get_requirement_provenance` 抽样真跑：逐 REQ 锚点（file/locator/excerpt/block_idx/resolved_via）在位——溯源读面可用。

## 3. 统一 REQ 溯源（跨件一致性）

**不变量（Rust 硬断言，全部通过）**：每个 REQ 的锚点文件 ⊆ 本项目导入文件集——6 项目零跨项目泄漏（隔离纪律：独立工作区 + external_key 逐件对齐）。

**逐件产出（统一矩阵的关键事实）**：

| 项目 | 主件 REQ | 辅件 REQ | 说明 |
|---|---|---|---|
| unicom-ry | 招标文件 302 | 技术规范书 0 / 投标一览表 0 | 附件/格式模板 kind **设计上无条款抽取面**（extract.rs：附件/图纸/证据/格式模板 → 不产 REQ，块面经 get_document_chunks 可读） |
| huaian | 主文件 371 | 技术规范书 0 / 报价文件 0 / 合同 0 | 同上 |
| unicom-ry-alt | 招标文件 302 | **技术规范书 21**（按招标文件 kind 导入） | 条款面形态下跨件合并溯源**在位**：REQ-0303..0323 逐条 source_file=技术规范书，与主件 REQ 统一进矩阵（323 行/108 阻断→建纲 74 节） |

**发现 F-3（设计边界——需 Lead 裁定口径）**：真实多件项目里**含条款的辅件**（技术规范书是典型——21 条业务要求）按缺省语义导入 kind=附件时对矩阵完全不可见。机制上多主件合并溯源是通的（alt 探针证明）；**kind 指派是语义决策、直接决定条款可见性**。建议后续：导入面或抽取回执对「附件 kind 但块面疑似条款密集」件给可见提示（本验收不实现——禁止扩功能）。

## 4. 跨件冲突

- **同号异文（已证检出）**：corpus-A「澄清修改文件-3.1.1.docx」（kind=补遗，真实命名无前缀）×主文件 → **2 条冲突**（条款 3.1.1/3.2.1），与 #425 已证行为一致（`conflicts[].reason` 逐条指向同号条款）。
- **发现 F-5（未检出——设计边界）**：GT CONFLICT-01 控制价冲突（A 件 6.1「480 万」vs C 补遗「三、招标控制价调整」→ 465 万）**条款号不同**，最小面冲突检测（同 clause_no 异文）口径内**检不出**——两版本 REQ 共在（REQ-0001 A 480 万 / REQ-0121 C 465 万，摘录逐字落盘），但无语义归并/终裁面。GT `resolution_rule: 补遗优先 → expected_final_value 4650000` 的**自动终裁在产品中不存在**（value_changed 经 register_addendum_changes 人工登记后才进入改写指令流——见 §6）。
- 真实四件套（无补遗件）：冲突恒 0 ✓（期望值）。
- 缺号完整性：huaian 1 处 missing_sequence（如实记录）；其余项目 0。

## 5. 评分映射逐项正确性 + 篇幅分配

**门 1h 闭环（机制面 ✅）**：三全链项目评分项（hard gate/价格项排除后）**unmapped 18→0、28→0、4→0**——全部经 `map_scoring_item`（#153 正门通道，AGENT_SUBMITTED 落账）逐项映射，映射决策逐条留痕（criteria/目标章节/重合度/方法）。

**逐项语义正确性（诚实边界 ⚠️）**：

- 映射决策 = bigram 重合度启发式（harness 决策，非人工/LLM 金标准）。样本：corpusA REQ-0026（技术分 55 分）→「资格证明材料响应」——闭环达成但语义存疑。**语义正确的逐项映射超出确定性验收边界**（评分表结构化专路未覆盖 DOCX 真表格——#134 已登记缺口，本验收不扩功能）。
- **发现 F-4**：真实 DOCX 主件的评分项 REQ **零 params.score**（unicom 0/18、huaian 0/28；corpus-A 合成件 4/4 有：30/55/15/3 分）→ 分值驱动的配额保底（HIS-A1/#131 Track::Scoring 分值比例面）在真实 DOCX 项目上**无从触发**（无分值数据）。评分表行结构化（名称/分值/细则切分）仍是 #134 立项面的前置。
- 覆盖面（评分细则↔章节↔正文）：check_scoring_coverage 真跑——huaian 6 细则 22 点 / **mock 正文命中 0 点**（mock 生成器不做关键词覆盖——「字数/引用面为门禁口径非内容质量口径」，真 LLM 内容覆盖是 #113 边界）；unicom/corpusA 细则无可拆点（points_total 0）。
- **评分项现状基线（对 #134 冻结基线的复测）**：unicom 18（#134 基线 18——**持平**）、huaian 28（基线 28——**持平**）。多件导入不稀释主件评分面。

**篇幅分配 ✅**：三全链项目叶片配额和**精确等于 target**（48000/48000/48000——守恒修正验收容差内零偏差）。分布：corpusA 19 叶 top5=3227×5（近均匀）；映射评分叶配额份额 corpusA 12.6% / unicom 24.8% / huaian 18.5%（全量分布落盘 `section_tree`）。

## 6. 补遗影响（corpus-A 合成对照面）

- **EV-02 有效期翻转（GT-02 ✓）**：`valid_until=2026-11-25`，开标日双口径绑定——**pre（2026-11-15）可绑**（新建绑定成功）/ **post（2026-11-27）被拒**（`E_UNPROCESSABLE: 状态 EXPIRED 禁止绑定（R-03）`）。翻转语义与 GT `eligible@11-15;not_eligible@11-27` 一致。链尾执行不污染主链（起草面 R-03 拒失效证据——探针先行为会阻断起草，已按产品语义排序）。
- **补遗后改写指令面 ✓**：控制价 value_changed 登记（REQ-0001 480 万→465 万）→ `register_addendum_changes` 回执：1 条 change（AC-0069）/ **1 条 directive / 1 个 DIRTY 章节**（SEC-0024）/ 矩阵重算 123 行 0 阻断——「补遗改了什么 → 哪些章节哪些段要改」的翻译链在位。
- **版本优先级（诚实边界）**：A/C 两版本共在（§4 F-5）——产品无自动「补遗优先」终裁；终裁 = 人工经 value_changed 登记（上项）或导出门人工裁定。GT `expected_final_value=4650000` 以**登记后改写指令**形态达成（非自动）。

## 7. 真实发现登记（本验收产出——修复立项归 Lead 裁决）

| # | 发现 | 证据 | 定性 |
|---|---|---|---|
| F-1 | **真实详细评审表.xlsx 引擎拒收**：`engine rejected: invalid part customXml/item1.xml: truncated: 16 unclosed element(s) at EOF`——unicom-ry 附件1 详细评审表（sha c6ee8eb61c98，平台原始件）导入 parse FAILED | `waived_failed_files` / `import_item_errors` 逐字留痕；file-level-report（B1.5 时代 bid-parse 旧路径）当时 17/17 可解析——**引擎路径（mdcore）对真实世界 xlsx 的 customXml 容错差异** | 产品缺口候选（引擎健壮性）；本验收内按产品设计走逐件 waiver → **RESTRICTED 受限起草**（input_integrity.status=RESTRICTED + waived_files 逐件 + 告警点名——门行为与文档一致 ✓） |
| F-2 | B2 扫描件在 pdfium 库缺失环境 fail-loud（`pdfium 库定位失败`）→ parse FAILED | 本沙箱无 pdfium（poppler 在位——文本层 PDF 全部正常）；#167 修复后不再静默乱码 | 环境限制 + 门诚实性复证（拒绝乱码兜底 ✓）；格式模板 kind 不阻塞起草（设计内） |
| F-3 | 含条款辅件按附件 kind 对矩阵不可见（§3） | unicom-ry 0/21 对照 | 设计边界——kind 指派语义决策，建议提示面（不扩功能） |
| F-4 | 真实 DOCX 评分项零分值参数（§5） | 0/18、0/28 vs 合成 4/4 | #134 评分表结构化立项的前置证据 |
| F-5 | 异号语义冲突（控制价 480/465）检不出（§4） | CONFLICT-01 GT 未达 | 最小面设计边界——语义冲突归并属新功能 |
| F-6 | huaian 缺号 1 处（missing_sequence 如实登记） | extract 回执 | 待人工核（缺号可能是真缺号或抽取切分） |
| F-7 | GT 型号锚（GW-8000-T4 等 3 条）不在锚摘录形态——excerpt 召回 22/25 | hits_detail | 表格锚摘录形态边界（型号在表格块/参数面，非锚摘录）——登记不判罪 |

## 8. 未覆盖面登记（issue 口径——如实，不凑数）

1. **真实企业证据**：库内无真实投标人证据（EV 全为合成——`real_evidence=false`）。
2. **真实补遗完整链**：zjyd 变更公告无主件在库（补遗×主件冲突面无法真实触发——本面以 corpus-A 合成补遗 + #425 合成澄清件验证机制）；「生成补遗当真实被禁」遵从。
3. **真实评分表驱动大纲**：评分表 xlsx 引擎拒收（F-1）+ DOCX 真表格评分行未结构化（#134 缺口）——评分驱动大纲（scoring_outline 专路）在真实多件项目上未可达；本验收记录的即现状基线。
4. **起草正文质量/真 LLM**：mock 生成器（#130 门 1n 语义——非正式标书口径）；正文语义覆盖 0/22 点（§5）——#113 独立边界。
5. **Windows 面**：本沙箱 Linux；xlsx customXml 拒收的平台相关性未验证（Windows 真机归 Lead 复验口径）。
6. **导出面**：本验收止于 validate（blocker=0）；导出/解包深检是收官真测（closeout-real-20261112）已覆盖面，不重复宣称。

## 9. 复现

```bash
# 全链一条龙（素材对账 → 规格 → cargo 真跑 → GT 评审 → 评估落盘）
python3 scripts/multifile_acceptance.py --all
# 分步
python3 scripts/multifile_acceptance.py --emit-spec   # 31 件对账 + 6 项目规格
python3 scripts/multifile_acceptance.py --run-rust    # cargo test -p bid-mcp --test multifile_matrix
python3 scripts/multifile_acceptance.py --evaluate    # GT 对照 + 期望评审
# Rust 面单体：MULTIFILE_SPEC 未设 → 响亮 SKIP（CI 安全，实测 1 passed=skip 分支）
cd bidcore && cargo test -p bid-mcp --test multifile_matrix
```

- 产物：`artifacts/multifile-acceptance-20261118/`（inventory / multifile-spec / multifile-all / evaluation / rust-run.log / 六项目工作区指标）。
- 环境依赖：poppler 在位（本沙箱 ✓）；pdfium 缺失时 B2 扫描件面按 F-2 记录（不影响其余面）；cargo + GITEA_TOKEN（mdcore git 依赖）经 `scripts/rust-env.sh` 恢复。

## 10. 关联

- 母 issue：#114（本报告即其验收交付物）；审计总纲 #116（阶段 3/4 多件验收载体）。
- 对照基线：#134（评分表现状缺口——本报告 §5 复测持平）；#425（同号冲突行为）；#167（PDF 兜底 fail-loud 复证）；#153（映射写面正门——本验收首次在真实多件项目全量使用）。
