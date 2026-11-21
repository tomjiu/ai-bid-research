# P8 导出细则（export_bid_document）

> 契约依据：仓库根 `docs/bid-mcp-contract.md`（路径约定见 SKILL.md 头部——`docs/` 指仓库根，非本目录相对） §8。导出是全链的收口闸——引擎在
> 此做**前置门链**裁决（1a 矩阵 blocking 清零 + 1b 审核门全过 + 1c–1n
> 独立复算门，全览见下「导出门全览」），任一不过 `E_UNPROCESSABLE`
> 响亮拒（人话理由）。你的职责：把报价决策/主体信息给足、路径给对、
> 豁免参数慎用且理由可审计，产物 sha256 与对账数字向用户复述。

## 调用形

```json
{ "project_id": "…", "format": "docx",
  "output_path": "out/投标文件-技术标.docx",
  "bid_open_date": "2026-12-05",
  "profile": { "bid_amount": 15800000, "project_name": "…招标官方项目名",
               "duration_days": 180, "validity_days": 90,
               "deposit_amount": 300000, "legal_rep_gender": "男",
               "price_breakdown": [ { "item": "…", "unit": "项",
                                      "quantity": 1, "unit_price": 15800000 } ] },
  "project_version": 30 }
```

- `format`：`docx` | `pdf`（pdf 走 docx 链 + Word/LibreOffice headless 转换
  ——两者均未检测到 → `E_UNPROCESSABLE` 响亮拒，不静默降级 docx）；
- `output_path`：**工作区相对路径**（不得绝对路径/含 `..`——违反 →
  `E_UNPROCESSABLE`）。产物落 `<工作区>/<output_path>`，父目录自动创建；
  返回的 `artifact.url` 是解析后的绝对路径；
- `bid_open_date`（#322，可选但强烈建议）：**开标日时效裁决基准日**（ISO
  日期，与 bind_evidence 的同参同口径）。提供则在导出前对全部证据做单向
  翻转（Active/Expiring→Expired，只降不升——Expired 不可逆，重新登记新版
  证据才是正路）；翻转后矩阵同步重算，矩阵门读到的是翻转后状态（翻掉的
  证据不再撑响应面）。未提供但存在带 valid_until 的证据 → warnings 响亮
  告警「时效未裁决」（不硬拒）；非法日期/非字符串 → `E_UNPROCESSABLE`。
  **建议：有带时效字段的证据时必传**（资质证书过期是废标级风险）；
- `profile` 是**投标决策面**（报价/工期/有效期/保证金/分项报价/招标官方
  项目名）——进幂等键，**换报价重导 = 新导出**（不吃旧缓存）；
- `options.tracked_changes` / `options.watermark`：暂不支持——传 truthy 会
  告警后按普通模式导出（不静默吞）；
- 状态窗：Drafting+ 可调（含 EXPORTED——重复导出/换参数重导）。

## 前置检查（1a 矩阵门 + 1b 审核门，fail-closed）

0. **时效裁决**（#322，提供 `bid_open_date` 时）：开标日口径单向翻转证据
   状态（翻转后矩阵重算——矩阵门/响应面读的是翻转后状态；翻转清单进
   warnings 审计面）；

1. **矩阵门（1a）**（`check_export_ready`）：blocking 行（必选未响应）未清零 →
   `E_UNPROCESSABLE` 逐行列出「`REQ-x（CMP-x）: 必选未响应——R-03/R-04
   闸门`」；矩阵未构建同样拒（无矩阵 = 未对账）；
2. **审核门（1b）**（`export_allowed`，单一真源）：
   - 三门均须有 Approved 记录（缺哪门点名哪门）；
   - **#180 审核内容绑定**：最后一条 `pre_export_confirm` Approved 的
     `reviewed_content_digest`（章节树摘要）≠ 当前 → `E_UNPROCESSABLE`
     「审核针对的内容已变更，请重新审核」——**过门后改章节正文/结构 =
     旧审核失效**，重过门重新绑定（详见 `p7-review.md`）。绑摘要不绑
     全局 content_version——过门后导入无关件、不改正文重复导出不受影响；
   - 全部 RevisionTask DONE（未关单逐个点名 RT-id）。

成功响应里的 `precheck: { blockers: 0, waived: [] }` 是通过后的回显——
**失败路径不进 data 面，直接 Err**（读 `error.what` 人话理由）。

## 导出门全览（1a–1n 收口闸）

导出不止上面两道门。服务层 `export_document`
（`bidcore/crates/bid-tools/src/service.rs`）在 1a/1b 之后还串着一排**独立
复算门**（不消费记审面——审核批准也不放行），全链 1a–1n 共 15 道：

- **1c 写作验收门**（篇幅不足/空章节独立复算）与 **1d 占位证据门**
  （#245 活跃占位绑定即拒）：防「审核已批但稿子是空的/占位冒充」；
- **1e ★实质性条款响应门**（#88 F-01，★不响应 = 废标级；子面 b 漏标可
  `waive_star_missing` 豁免）与 **1f 暗标联动门**（#88 F-02，暗标 mode 与
  导出参数自相矛盾即拒）；
- **1l 三件套数据缺位门**（#88 F-06 硬化面，`waive_format_placeholder`
  豁免）：投标函/法代证明/授权委托书数据字段缺位即拒（装配在 extras
  之后，代码位置在 1n 后面）。

本节主角是 #88/#105/#130 审计轮加进来的**八道门**（service.rs L2000-2236
门链）：

| 门 | 名称（出处） | 拦什么 | 豁免参数 | 典型恢复动作 |
|---|---|---|---|---|
| **1g** | 补遗 DIRTY 门（#88 F-08） | 有 pending 改写指令的 DIRTY 章节——正文按补遗前旧口径起草（S-4：按新口径评审负偏离）；证据换版失效信号（无指令）只告警不拦 | 无（处置完自动清脏——处置面即豁免） | `rewrite_section_partial` 逐指令改写或 `dismiss_rewrite_directive` 人工裁定；证据换版面走 `reopen_section` 重做 |
| **1h** | 评分项未映射门（#88 F-07） | `unmapped_scoring_items` 非空——评分项没映射到章节，评委无从给分 = 按缺项计零（与 `score_document` 同源同口径，明细截断 10 项） | `waive_unmapped_scoring` | `map_scoring_item`（MCP 写面）逐项显式映射；仅无评分项语料误抽经人工确认后才豁免 |
| **1i** | 全局一致性冲突门（#88 F-05） | 金额/工期/术语/承诺四类跨面冲突 Blocker（#423；与 `check_bid_quality` 同源） | **无豁免通道** | 改稿对齐——冲突是客观不一致，只能修不能绕 |
| **1j** | 决策对账门（#88 F-05 决策面） | `profile.duration_days`/`bid_amount` vs 参数账工期/报价行（万/亿归一到元）数值不等——决策按设计不入库，导出时点是唯一对账时机；决策缺省（None）不比不拦 | **无豁免通道** | 改决策值或改参数账，数值改齐 |
| **1j-2** | 决策对账门·正文面（#105） | 章正文 vs 决策值（投标总报价/工期）同维度不同值（合成 DECISION 行临时注入比对，不落库）；非决策冲突归 1i，不双报 | **无豁免通道** | 改决策值或改正文使一致 |
| **1k** | 格式件核对清单（#88 F-06 可见面） | 格式要求类 REQ 指名的件（《X》书名号 ∪ 件名词表）不在七件标准面——**告警不拦**（形式评审缺件是实务最高频废标原因；硬化待件名抽取产品化） | 无（本身不拦） | 读 warnings 逐件核对，缺件人工补 |
| **1m** | 超篇幅可配置门（#88 F-09） | 单叶正文字数超配额 `max_overrun_pct`%（缺省 50；整数算术严格大于——恰等阈值放行；零配额叶不判）→ `E_CHARS_OVER_LIMIT`；带内仍走 `W_CHARS_OFF_TARGET` MINOR（双层信号不冲突） | `waive_length_overrun` / `max_overrun_pct` | 压缩正文 / 调大阈值 / 显式豁免 |
| **1n** | 生成器汇总门（AUD2-CHN-01/#130） | 任一**评分叶** `generator ≠ real`（mock 模板稿/external 外部手稿/未留痕稿）→ 拒——评分面是得分主体，mock 按构造填充到 target±20%，字数门 1c 对它天然失效；非评分叶 mock/未知只告警不拦（风险不对称） | `waive_scoring_leaf_generator` | 配置 `.mang/llm.json` 或 `BID_LLM_API_KEY` 后逐叶 real 重起草；仅 mock 链收官测试/外部手稿经人工确认后才豁免 |

> 契约对齐提示：`docs/bid-mcp-contract.md` §8 的「十前置门全量清单」止于
> 1m；1n 的权威描述在 MCP 工具面（`schema.rs` 参数描述 + `tools.rs`
> 非空校验）与服务层 `export_document` 注记。

### 豁免参数使用指引（waive_* / max_overrun_pct）

通用纪律（`FatalGapWaivers` 设计面）：

- **非空理由才生效**：空串/缺省 = 不豁免（fail-closed 不放水）；传非字符
  串类型 → 响亮拒；
- **理由进 warnings 审计面**：豁免不是静默跳过——导出响应携带同一事实；
- **豁免与否进幂等键**：豁免是不同的导出裁决，不吃旧缓存跳门。

| 参数 | 门 | 语义与取值 | 豁免了什么责任（风险） |
|---|---|---|---|
| `waive_unmapped_scoring` | 1h | 评分项未映射豁免理由（字符串，非空生效）。`unmapped_scoring_items` 非空被拒时，人工确认未映射可接受（无评分项语料误抽等）才传 | 评委无从给分的评分项按缺项计零——分值损失由调用方背书，映射通道（`map_scoring_item`）仍开放 |
| `waive_length_overrun` | 1m | 超篇幅豁免理由（字符串，非空生效）。门 1m 拒时，评标办法不设页数限制等人工场景才传 | 页数受限/暗标场景下超带被扣分或截断的风险 |
| `waive_scoring_leaf_generator` | 1n | 评分叶生成器豁免理由（字符串，非空生效）。任一评分叶 generator≠real 被拒时，mock 链收官测试/外部手稿经人工确认等场景才传；正式投标前建议 real 重起草 | mock 模板稿/未留痕稿冒充正式标书出库——评分面（得分主体）非真实生成的风险 |
| `max_overrun_pct` | 1m | 超篇幅阈值（正整数 1..=10000，缺省 50——审计建议值）。判据 `chars×100 > target×(100+pct)` 整数严格大于；实质停用传 10000；页数硬约束项目收紧/无页数约束项目放宽 | 阈值是调用方裁决面：调大 = 放宽超带容忍度，10000 = 实质停用门 1m |

另两道带豁免的门（非上表四参数，顺手记全）：1e 子面 b 漏标豁免
`waive_star_missing`（#88 F-01）、1l 三件套数据缺位豁免
`waive_format_placeholder`（#88 F-06）——同样「非空理由 + 进 warnings +
进幂等键」纪律。

### 被 1n 拒时的排查路径

1. **读错误消息**：`生成器门未过（门 1n）：N / M 个评分叶的生成器非
   real（sec-x(mock)…）`——逐叶点名 section_id + 生成器标签（`mock` /
   `未留痕（旧记录或非 draft 写入）`）；
2. **判定处境**：`mock` = 生成器 auto 且未配 api_key 静默降级
   （AUD2-CHN-01 审计实锤链路）；`external` = 外部手稿；`未留痕` =
   旧记录或非 draft 工具写入；
3. **正式投标**：配置 `.mang/llm.json` 或环境变量 `BID_LLM_API_KEY` →
   对点名评分叶逐个重起草（real 生成器）→ 重导出；
4. **非正式场景**（mock 链收官测试、外部手稿经人工确认）：export 传
   `waive_scoring_leaf_generator`（非空理由）显式豁免——理由进 warnings
   审计面；
5. **对账**：导出响应常驻 `generator_summary`（real/mock/external/unknown
   计数 + 评分叶分拆）——向用户复述；非评分叶 mock/未知只告警不拦，
   正式稿仍建议 real 重起草。

专项测试参考：`bidcore/crates/bid-mcp/tests/generator_gate_1n.rs`（门 1n
点火/豁免通道透出/空串拒绝三面）。

## 六表七件对账（产物完整性）

导出自动注入**六张表 + 七件格式件**（#117/#122），返回逐张点名：

```
tables_written: 6   table_kinds: ["项目概况表", "技术参数偏离表", "报价明细表",
                                   "业绩一览表", "人员配置表", "设备清单表"]
forms_written:  7   form_titles: ["附件一、投标函", "附件二、法定代表人身份证明书",
                                   "附件三、授权委托书", "附件四、投标保证金退还申请",
                                   "附件五、资格声明", "附件六、无重大违法记录声明",
                                   "附件七、廉洁承诺书"]
```

| 表 | 生成条件（缺输入 → 缺席 + 响亮告警，不静默） |
|---|---|
| ① 项目概况表 | **恒生成**（REQ 参数 + 项目面，缺栏落【待填】） |
| ② 技术参数偏离表 | 有「技术参数」类 REQ（负偏离★整行标红；无技术参数 REQ → 缺席 + 告警） |
| ③ 报价明细表 | `profile.price_breakdown` 在场（分项合计 ≠ 总价 → 响亮告警——评标否决点） |
| ④ 业绩一览表 | 台账有可用（Active/Expiring）业绩证据 |
| ⑤ 人员配置表 / ⑥ 设备清单表 | 工作区 `bidder-profile.json` 的 personnel / equipment 非空 |

七件恒生成（字段从 BidderProfile 铺管，缺 → 【待填】+ 告警；标题 Heading2
样式段进 TOC——评委在目录里看得到七件在哪）。**对账纪律**：`tables_written`/
`forms_written` 与输入面互证——配置齐时应为 6/7；缺席项必伴有 warnings，
逐条向用户转述（缺 bidder-profile.json 时人员/设备表与格式件字段全部
【待填】——主体信息建档是投标方输入面，不编造）。

**必复述**：`产物 sha256 / 尺寸 / 六表 N 张 / 七件 M 件`，与预期比对。

**#277 agent 过门警告面**：`agent_waivers[]` 非空且 `human_review_complete:
false` → 产物首页带红色警告横幅（「本标书的部分审核门由 AI 声明通过，
未经人工复核」+ 门清单）——这是 agent 声明过门（见 p7-review.md）的预期
代价，不是导出错误。交付时把 agent_waivers 清单（哪些门/理由/何时）与
「待人工追认」一并复述；要无横幅的正式稿 = 先请用户以本人 receipt 追认
再导出（追认必须在导出前——EXPORTED 是审核门终态）。

## 幂等与缓存

幂等键 = `(project_id, content_version, format, dark_bid, output_path,
决策指纹)`——同键重调直返首次 artifact（`deduplicated: true`，零 IO）。
换报价/换路径/内容版本推进后 = 新导出。pdf 面另有转换幂等（staging docx
未变 → 不重转，产物字节不重写）。

## 暗标模式（profile.dark_bid）

`dark_bid: true` + `bidder_name` → 正文与章标题的公司名替换为「投标人」。
`bidder_name` 缺失/空白 → **响亮 warning：未做脱敏**（无名字可替——用户
漏配），补齐后重导。P6 已做暗标禁字扫描，导出面是第二道。

## 产物验证（引擎侧回读——你要知道它存在）

e2e 不信任工具返回值：`tests/export_readback.rs`（#172）把落盘 docx **解
包**用独立解析器回读——自数 `<w:tbl>` 表数（六表应全部成真表格，不是
markdown 残文本）、七件关键词、表行数下限、负偏离红 run、报价合计一致、
零 markdown 星号/占位符残留（#129 深断言）。你侧的对应动作：复述
sha256 + 对账数字；用户拿到产物后抽查【待填】残留（缺决策的字段引擎会
如实留白并告警——**留给人工补，不由 AI 编**）。

## 状态推进与恢复

- 单次 export 内部经 `Drafting→Validating→Reviewing→ReadyToExport→
  Exported` 逐态补链（REVIEWING 是瞬态，不出现在两次调用之间）；终态
  `EXPORTED`；
- 导出需要**持久化工作区**（纯内存态 → `E_UNPROCESSABLE`「无章内容可导」
  ——`BID_WS` 建服务态）；
- 恢复点：同参幂等直返；改稿/换报价 → 重走对应上游（改稿需重过
  pre_export_confirm 门）。

## 常见错误

| 错误 | 触发 | 动作 |
|---|---|---|
| `E_UNPROCESSABLE`（必选未响应） | 矩阵 blocking 未清零 | 回 P4 补绑定（见 `p3-matrix.md` 排查表） |
| `E_UNPROCESSABLE`（缺门/RT 未关/内容已变更） | 审核门三面任一不过 | 补过门 / 关 RT / 重过 pre_export_confirm |
| `E_UNPROCESSABLE`（output_path） | 绝对路径/含 `..` | 改工作区相对路径 |
| `E_UNPROCESSABLE`（PDF 环境） | Word/LibreOffice 均未装 | 装 Office/LO，或导 docx |
| `E_UNPROCESSABLE`（门 1g–1n） | DIRTY/评分未映射/全局冲突/决策对账/超篇幅/生成器等八门任一未过 | 见「导出门全览」逐门恢复动作（1i/1j/1j-2 无豁免——只能改齐） |
| `E_CONFLICT` | project_version 过期 | 重读状态拿新值重试 |

## 来源锚点

- `docs/bid-mcp-contract.md` §8（export 契约：入参/豁免参数 L436-454、
  #180 门禁 L523-531、前置门全量清单 L532-616（止于 1m——1n 见工具面/
  服务层锚点）、六表七件/幂等键/状态，L419-621）
- `bidcore/crates/bid-mcp/src/tools.rs` L3683-4216（export_bid_document
  壳层：format 校验 L3727-3742、路径形状校验 L3744-3754、豁免参数校验
  （非空理由/值域 1..=10000）L3947-4085、幂等键 L4103-4114、出参组装
  L4150-4215——precheck 注释「失败路径在 Err 面」在 L4203-4206）
- `bidcore/crates/bid-mcp/src/schema.rs` L518-564（export 入参 schema：
  profile 决策字段/options 告警位；waive_* 豁免理由描述位 L558-560）
- `bidcore/crates/bid-tools/src/service.rs` L1844-2444（export_document
  业务半边：门 1a/1b L1862-1865、门 1c/1d L1866-1920、门 1e/1f
  L1922-1999、**门 1g–1n 八门链 L2000-2236**、bidder-profile 装载
  L2257-2283、门 1l L2284-2318、#189 resolve_write 围栏 L2337-2343、
  pdf staging 与转换 L2370-2431、推进 EXPORTED L2432）；
  `FatalGapWaivers` 豁免面定义 L2611-2661
- `bidcore/crates/bid-tools/src/export.rs` L240-398（build_export_extras
  ——六表生成条件与告警）、L400-491（七件构造：决策缺项告警/大写金额
  换写）、L761-798（ExportReport：tables_written/table_kinds/
  forms_written/form_titles/generator_summary）、L1241-1330（渲染计数
  与七件锚定）
- `bidcore/crates/bid-tools/src/tables.rs` L343-355（BidTable::kind 六表名）
- `bidcore/crates/bid-domain/src/forms.rs` L68-186（StandardForm 七件
  枚举）、L211-242（kind/appendix_no 附件一~七/title 带编号标题）
- `bidcore/crates/bid-domain/src/matrix.rs` L499-522（export_blockers/
  check_export_ready）、`bidcore/crates/bid-domain/src/review.rs`
  L862-943（export_allowed：三门 + #180 摘要 + 全 RT DONE）
- `bidcore/crates/bid-domain/src/lib.rs` L196-202（allowed_tools：export
  的状态窗 Drafting+）
- `bidcore/crates/bid-mcp/tests/export_readback.rs` L1-25（#172 独立回读
  纪律）、L658-662（真表格数 ≥6 断言）；
  `bidcore/crates/bid-mcp/tests/mcp_scaffold_tools.rs` L340-360
  （纯 MCP 全链 export → EXPORTED 终态）；
  `bidcore/crates/bid-mcp/tests/generator_gate_1n.rs` L281-286（门 1n
  点火/豁免通道透出断言）
