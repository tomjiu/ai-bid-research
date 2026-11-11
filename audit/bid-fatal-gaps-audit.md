# 投标致命项审计——影响中标/废标的缺口全盘扫描（#88）

> 审查型任务（不改代码）。审计范围：`bidcore` 全链（50 工具面 + 导出门 + 状态机 + 证据/补遗/评分域）。
> 口径：**从投标实务视角**回答「这份标书拿去投，会不会因为某个致命项被废标/扣分」。
> 每条含：证据锚点（文件:行 / 工具名 / 测试名）→ 影响 → 现状 → 建议。
> 优先级：P0（会废标）> P1（会扣分/卡死）> P2（体验/可信度）。

---

## 0. 导出前最后一道门的完整性评估（验收 3）

`export_bid_document`（`bid-tools/src/service.rs:1596` `export_document`）当前实际拦截清单——**四前置门 + 三辅助面**：

| # | 门 | 证据锚点 | 拦截内容 |
|---|---|---|---|
| 1a | 矩阵门 | `service.rs:1613` → `matrix.rs` `check_export_ready` | blocking 行清零：**资格条件/否决项**未响应、必选 PENDING_EVIDENCE（`is_mandatory` = 资格条件∨否决项，`matrix.rs:166`；Agent 标必选并集 `agent_mandatory`，`matrix.rs:181`） |
| 1b | 审核门 | `service.rs:1615` → `review.rs:862` `export_allowed` | 三门（MatrixApproval/OutlineApproval/PreExportConfirm）全 Approved + **内容摘要绑定**（#180：过门后改正文 → 摘要不符 → 拒）+ **计分面摘要绑定**（#474：过门后改矩阵覆写/评分映射 → 拒） |
| 1c | 写作验收门 | `service.rs:1623` → `validate.rs:644` `writing_acceptance_findings` | 空章节（E_SECTION_EMPTY）、评分叶 <80% 配额（E_CHARS_BELOW_MIN，`validate.rs:531`）、全稿总量低于下限（E_TOTAL_CHARS_BELOW_MIN）——**独立复算，审核批准也不放行** |
| 1d | 占位证据门 | `service.rs` 1d（`placeholder_evidence_findings`） | 活跃占位绑定拒——人工豁免只认 NOT_APPLICABLE+偏离说明+可信 Human receipt 三要件（`validate.rs` `is_legitimate_placeholder_exemption`，PR #247 收紧） |
| 辅1 | 暗标防线 | `darkbid.rs`（scan/clean/复验） | **仅当 `profile.dark_bid=true`**：正文/页眉脚/docProps/修订/批注/EXIF 九类泄露面，BLOCKER 复验归零才允许导出 |
| 辅2 | 时效裁决 | `tools.rs:4004-4052` → `evidence.rs:684` `apply_validity` | **仅当显式传 `bid_open_date`**：按开标日单向翻转 EXPIRED + 矩阵重算；未传 → 告警不拒 |
| 辅3 | agent 过门横幅 | `service.rs`（#277） | agent 声明过门 → 正文首页红横幅 + warnings（人工追认后消失） |

**结论：这道门在「已抽取的必选条款面」上是强防线（fail-closed + 独立复算 + 摘要绑定），但它的**输入面**有三个洞：只管已抽取条款（漏抽取=漏响应不拦，见 F-04）、★实质性条款不参与 blocking（F-01）、时效/暗标是 opt-in 辅助面而非门（F-02/F-03）。另：两阶段导出门 `export_gate.rs` 自述 **NOT_WIRED**（`export_gate.rs:16-20`——全仓仅测试引用），产品原子性由 manifest+tmp+rename 承担（`export.rs:37-52`），可接受但 EXPORTING 中间态缺失是已登记债。

---

## 1. 废标风险（P0 级）

### F-01 ★实质性条款漏响应——不拦导出【无防护】

```
证据：bid-domain/src/matrix.rs:194 —— substantive() 注释自述
      「不参与 blocking 派生（★未响应是否阻断导出是门禁分级，Lead 裁决）」；
      matrix.rs:126 —— 「不参与 blocking」同口径；
      工具面：get_star_coverage（coverage_tools.rs:332）「只报不补」（:349）
      ——star_missing 只进响应 JSON，不进任何导出门。
影响：★条款 = 实质性条款（招标法/招标投标法实施条例），不响应或负偏离
      = 评标委员会直接否决投标 = 废标。当前导出四门无一消费 star_missing。
现状：无防护（可编程面已有：params.star 双路写入 [matrix.rs:186-194] +
      get_star_coverage 明细，只差接进导出门这一步）。
建议：加「★响应覆盖门」：star_missing > 0 → E_UNPROCESSABLE（人工豁免走
      set_matrix_override NOT_APPLICABLE 通道——与占位门 1d 同款三要件）。
```

### F-02 暗标模式与抽取面条款无联动——漏传 profile.dark_bid 则零防线【无防护】

```
证据：bid-mcp/src/tools.rs:3922-3924 —— dark_bid 取自调用方显式传入的
      profile.dark_bid；tools.rs:4076 anonymize = dark_bid ? bidder_name : None。
      抽取面已能识别暗标否决条款（bid-parse/src/veto_lexicon.rs:809-811，
      GT-24 金标准原文「技术标部分采用暗标评审…否则作否决投标处理」），
      但该 REQ 的在场与 profile.dark_bid 之间无任何一致性检查。
影响：招标文件明示暗标评审（否决项）→ 用户/Agent 导出时 profile 未带
      dark_bid → 无脱敏、无泄露扫描、docProps 作者/公司名全裸 → 暗标
      泄露当场废标。darkbid.rs 本身防线很强（九类泄露面+复验归零），
      但它是 opt-in 的——门再好，没开等于没有。
现状：无防护（抽取面信息已有，只差联动检查）。
建议：导出前扫描 REQ：存在暗标类否决条款（可复用 GT-24 词面）而
      profile.dark_bid != true → E_UNPROCESSABLE（或强制人工豁免 receipt）。
```

### F-03 证据时效裁决是 opt-in——不传 bid_open_date 过期证据照常进标书【部分防护】

```
证据：bid-mcp/src/tools.rs:4004-4006（接线注释自述「apply_validity 此前
      全仓生产调用为零」）；tools.rs:4050-4051 —— 未提供 bid_open_date 时
      仅响亮告警「时效未裁决，按当前登记状态导出」，不硬拒（契约兼容
      的显式取舍）；validate.rs:373-378 规则 8 E_EVIDENCE_EXPIRED 只看
      **已落库状态**——状态翻转只发生在 bind 时（携开标日）或导出时
      （显式传参），两次之间到期 + 导出不传参 = Active 假象。
影响：资质证书（如 ISO/安全生产许可证）valid_until 早于开标日 → 绑定时
      有效 → 开标前到期 → 导出未传 bid_open_date → 过期资质进标书 →
      资格性审查不通过 = 废标。
现状：部分防护（有告警 + 有翻转机制，但翻转是拉动式，不传参不翻）。
建议：收紧为「存在带 valid_until 的证据且未传 bid_open_date → 拒绝导出
      或升 BLOCKER」（breaking change 可先做「告警 + 导出报告醒目字段」，
      下版本硬化）。#88 审查后可与 F-10 一起做「导出前证据体检单」。
```

### F-04 漏抽取 → 漏响应不拦——矩阵门的输入面盲区【部分防护】

```
证据：矩阵门 1a 只覆盖**已抽取 REQ**（check_export_ready 遍历 matrix 行，
      matrix 行由 requirements 派生）；漏抽取的资格条款无行 → 无 blocking。
      检漏工具齐全但全是只读：get_star_coverage（★漏标）、
      get_annotation_overlay / bidi_tools.rs:189（suspected_miss——★真值
      无对应 REQ 的块位）、get_coverage_report（覆盖报告）。
影响：解析面漏抽一条资格条款（如分散在表格行/图片里的资质要求）→
      矩阵无行 → 导出放行 → 投标文件缺该响应 → 资格性审查不通过。
      ★类有双腿匹配检漏（star_scan），但非★资格条款（无★标记的
      「应当/必须」句式）没有等价检漏面。
现状：部分防护（★面有检漏工具但只报；非★面靠 kind 启发式与人工复核）。
建议：① star_missing>0 接导出门（同 F-01）；② 把「抽取覆盖置信面」
      （零标记文件数 / suspected_miss 数）进 get_bid_project_state 顶部
      摘要 + 导出 warnings 常驻。
```

### F-05 报价/工期等关键数值一致性——正文比对已有（#423），决策面无对账、只读不拦【部分防护】

> **勘误（审计后修正）**：初版本条误记「零检查」。复查发现 #423 已接线
> 全局一致性检查（`check.rs` check_global + `review_wire.rs` 装配 + 
> check_bid_quality 消费，tools.rs:2838-2846）——正文↔正文跨章冲突与
> 参数账↔正文冲突（金额/工期/术语/承诺四类，Blocker 级）已有防护。
> 以下为修正后的精确口径。

```
证据（已防护面）：check.rs:1-20（S-5 全局一致性单列——金额/工期/术语/
      承诺四类冲突，Blocker 级 findings）；review_wire.rs:1-45 装配面——
      叶章节正文 + 参数响应账（param_responses 逐行合成，PR-xxxx 位置锚）
      都进比对面（「投标函写 3500000 而参数表写 3580000 = 跨面冲突，
      正是 #423 的典型失守场景」——review_wire.rs:16-19 自述）。
证据（剩余缺口）：
  a. review_wire.rs:44-47 自述边界——「导出层的报价决策（ExportDecision
     的 bid_amount/price_breakdown）按设计不入库，check 时不可得，故
     不参与本比对面」→ 正文 480 万 vs 报价一览表（decision）500 万
     仍无对账（decision 只在导出瞬间出现，检查工具看不到它）；
  b. check_bid_quality 是只读诊断（coverage_tools 同款「只报不拦」）——
     四类冲突 Blocker 不进导出门（1a-1d 均不消费），用户不主动调用
     就没人看见。
影响：a 场景（报价表与正文不一致）评标发现 → 按不利解释/澄清失败 →
      扣分乃至废标；b 场景（正文跨章冲突已可检出）依赖用户主动跑
      check_bid_quality——漏跑则冲突带病导出。
现状：部分防护（正文↔正文 + 参数账↔正文有四类冲突检查；decision 面
      无对账；检查只读不拦）。
建议：① 导出门增消费面：check_global 的 Blocker findings 进导出前置门
      （独立复算，与 1c/1d 同款纪律——审核批准也不放行）；
      ② decision 对账：export 时 decision.bid_amount 与正文/参数账的
      金额特征比对（decision 在导出时点可得——恰是比对唯一时机）。
```

### F-06 签字/盖章/授权委托书等格式性要求——无清单核对【无防护】

```
证据：format_spec.rs 的 FormatSpec 字段面 = font/page/margin/line_height/
      页码模板（format_spec.rs:38-97）——纯排版参数；「签字/盖章/法人
      授权委托书/投标函/保证金」等投标实务格式件不在 spec 域。导出
      extras 有授权委托书字段行（export.rs:2189）但仅当 bidder-profile
      配置了才出现，且无「招标文件要求的格式件清单 vs 已提供」核对。
影响：缺投标函/授权委托书/未按要求盖章签字 → 形式评审直接废标
      （实务中最高频废标原因之一）。
现状：无防护。
建议：① 抽取面加「格式要求」子类识别（签字/盖章/格式件名清单——
      REQ_CATEGORIES 已有「格式要求」类别，rewrite.rs:174-182，但
      只用于排版参数派生）；② 导出报告加「格式件核对清单」段：
      从格式要求类 REQ 提取件名 → 核对 extras/profile 在场性 → 缺件
      列进 warnings（先可见，后硬化为门）。
```

---

## 2. 扣分风险（P1 级）

### F-07 评分项未映射章节——只报不拦【部分防护】

```
证据：unmapped_scoring_items 结构化面在 score_document 报告里
      （scoring.rs:893/1456-1463/1547）；check_scoring_coverage
      （coverage_tools.rs:451「只读诊断」，:469「只报不补——#285★漏标
      同款纪律」）。两者均不进导出门（export.rs/service.rs 全文无
      unmapped 消费——grep 零命中）。
影响：评分项漏映射章节 = 评委对该评分项无从给分 → 按缺项计零分。
      带外率 70.8% 的篇幅问题（#47 规模轮）叠加此洞，扣分面进一步放大。
现状：部分防护（可见性已有——报告/工具响应面；强制力无）。
建议：导出门 1a 扩展或 1e 新增：unmapped_scoring_items 非空 → 须逐条
      人工豁免（receipt）才放行。或最低成本：进导出 warnings 首行常驻。
```

### F-08 补遗后 DIRTY 章节不改写——照常导出【部分防护（可见不强制）】

```
证据：register_addendum_changes（rewrite.rs:101）登记时 DIRTY 打标 +
      改写指令生成 + 矩阵重算（blocking 面会刷新——新增必选条款会被
      矩阵门拦住）；但 dirty_sections 只出现在工具响应里（tools.rs:355-
      400 get_bid_project_state、tools.rs:6081-6089）——export.rs/
      validate.rs/readiness.rs 对 dirty **零消费**（grep 零命中，export.rs
      里唯一的 dirty 是 TOC 域 dirty=true 标志，无关）。
影响：补遗改了实质性数值（如工期/质保期）→ 已起草章节仍是旧口径 →
      用户忽略改写指令直接导出 → 按补遗后口径评审 → 扣分；若补遗条款
      是实质性条款（★），旧响应=负偏离 → 废标。
现状：部分防护（新增/修改条款的矩阵行会刷新——若被判必选未响应会被
      1a 拦；但**已有章节正文**的 stale 无门）。
建议：导出门加第五门：dirty_sections 非空 → 拒（每章须 rewrite 后或
      record_addendum_waiver 豁免——该工具已存在，正好补强制面）。
```

### F-09 篇幅偏离门只覆盖评分叶下限——非评分叶/超篇幅放行【部分防护】

```
证据：writing_acceptance_findings（validate.rs:644）—— E_CHARS_BELOW_MIN
      仅评分叶 && <80%（validate.rs:528-533 + is_scoring_leaf 谓词）；
      非评分叶短稿只 W_CHARS_BELOW_MIN（MAJOR，:553）；超篇幅只有
      W_CHARS_OFF_TARGET（MINOR，:291）。#47 100w 字规模轮实测：
      35/120 叶带内，带外率 70.8%、偏离均值 24.8%、最大 58.8%
      （根因：prompt 字数口径 vs 引擎 words 口径——已另线修复）。
影响：评分办法常按「页数/字数超限扣分」「要点覆盖密度」给分；行政章
      过长挤占装订/页数上限 → 扣分。量化：带外 85 叶中偏离均值 24.8%，
      若评分细则含篇幅约束（常见 1-3 分/项），直接失分。
现状：部分防护（评分叶下限已 fail-closed；上界与非评分叶仅告警）。
建议：W_CHARS_OFF_TARGET 升级为可配置门（招标文件有页数/字数上限时
      ——格式要求类 REQ 提取到再启用，无则维持 W——「不硬编码」纪律）。
```

### F-10 证据 Expiring（90 天窗口）无导出前汇总提醒【部分防护】

```
证据：Expiring 语义 = 开标日前 90 天内到期可绑+告警（evidence.rs:28）；
      告警只在 search_evidence（tools.rs:2191-2207 EVIDENCE_EXPIRING
      降权面）与 bind 时出现；导出路径不汇总 Expiring 面。
影响：开标日当天证书还在有效期内（不翻转 EXPIRED）但评委复核时已过期
      → 资格项存疑扣分/废标边界。
现状：部分防护（bind/search 时有提示；导出体检无）。
建议：导出报告加「证据体检单」：Active/Expiring/Expired/Superseded
      四态计数 + Expiring 明细清单（与 F-03 收口一起做）。
```

---

## 3. 流程断点（P1 级）——两条正面结论 + 一条登记债

### F-11 状态机无卡死路径【已有防护——正面结论】

```
证据：ProjectStatus 十态（lib.rs:153-164）+ SectionStatus 八态
      （outline.rs:31-45，含 Failed 显式失败态）；每态 next_allowed
      均有后继（outline.rs:58-59：Validating→[Revising|Accepted]、
      Revising→[Accepted]；Failed→Drafting 重试，:36-38 注释）；出口
      齐备：reopen_section（#321）、recover_validating_state
      （service.rs:1896——VALIDATING 回 Drafting，三重约束防滥用）、
      ACCEPTED 重开（service.rs:1207 → Revising）。测试锁定：
      outline.rs:2452（零发现直通+有发现修订）。
结论：无「无法推进也无法退出」的死态。注意 advance_project_to_
      exported（service.rs，export 成功后半边）会自动补齐 Drafting→
      Exported 全链——状态序本身不构成防线，防线在四前置门（这是
      设计取舍，不是缺陷，但值得在文档里写明）。
```

### F-12 validate 失败恢复路径可达【已有防护——正面结论】

```
证据：validate 产出 BLOCKER/MAJOR/MINOR 分级 findings；恢复路径：
      ① 修稿后重 validate（幂等）；② VALIDATING 卡态 → recover_
      validating_state（#243，service.rs:1896——域层三重约束：仅
      VALIDATING/仅缺章/理由非空白）；③ 否决项死锁人工出口
      set_matrix_override（#226）；④ 占位豁免通道（#245/PR#247
      三要件）。以上四路均有测试（readiness_check.rs /
      store_roundtrip.rs / draft_section.rs 实测引用）。
```

### F-13 导出后改文件——双摘要绑定防「旧审新稿」【已有防护；export_gate NOT_WIRED 为登记债】

```
证据：#180 内容摘要绑定 + #474 计分面摘要绑定（review.rs:862-905：
      过门后 sections_digest/scoring_surface_digest 变化 → 拒绝导出
      「请重新审核」）；导出产物原子性 = manifest v2 + tmp+rename
      （export.rs:37-66，inputs_digest 含 anonymize/extras/format_spec/
      evidences——换投标人名/换证据台账都会触发全量重建，不吃旧缓存）。
      两阶段导出门 ExportGate（export_gate.rs:45）自述 NOT_WIRED
      （:16-20——全仓仅 four_contracts.rs 测试引用，EXPORTING 中间态
      不在产品路径）——manifest 方案已覆盖原子性，此为已登记债非缺口。
结论：「导出后改文件再投」场景有防护（重导必触发复算）；剩余风险是
      导出**产物**本身的版本管理（save_version 是 AI 主动快照，
      tools.rs:2275——产物文件被外部改动无检测，属可接受残余）。
```

---

## 4. 数据可信度（P2 级）

### F-14 抽取覆盖率不足不阻止建纲【部分防护——设计上有意】

```
证据：build_outline 前置门 = coverage_gate（tools.rs:4600「#244 建纲前
      覆盖闭环门：标记过的文件必须标完（C 态零容忍），零标记文件走
      正则兜底不受限（GT 红线保护）」）——这是**标记闭环门**不是
      覆盖率门：文件可以零标记通过（正则兜底抽取）。
影响：低覆盖抽取 → 建纲 → 起草 → 矩阵行少 → 看起来全 RESPONDED——
      「假绿」：不是系统错了，是输入面缺了没看见。
现状：部分防护（有意取舍：强制标记会卡死零 Agent 场景；检漏面齐全
      但须主动查询）。
建议：get_bid_project_state 顶部加「抽取健康度」常驻字段（零标记文件
      数 / suspected_miss 数 / star_missing 总数），UI/Agent 一眼可见。
```

### F-15 导出成品不嵌条款溯源【无防护——弱影响】

```
证据：导出面 evidences 仅用于 EV-id → 图片解析（export.rs:900「EV-id
      图片解析面」、:948-956 with_evidences/resolve_image_target）；
      溯源面是查询工具（get_requirement_provenance / get_annotation_
      overlay——bidi_tools.rs），不进 docx 成品。
影响：评标答辩/内部复核时无法从成品反查「本段响应哪条条款、依据哪份
      证据」——不影响评标得分本身，影响复盘与澄清效率。
现状：无防护（工具面数据齐全，只差导出侧呈现）。
建议：可选导出附件（如 appendices：条款-章节-证据对照表）——P2 优先
      级，非本审计强制项。
```

### F-16 大纲↔矩阵一致性——必选面有门，评分面无门【部分防护】

```
证据：必选面：矩阵门 1a（未响应必选拒导出）+ 建纲驱动 = 评分树
      derive_scoring_tree（scoring.rs 同源，check_bid_quality 复用
      同一派生——tools.rs:2715-2725 注释自述「真实评分项 REQ 驱动」）。
      评分面：unmapped_scoring_items 只报（同 F-07）；大纲重构
      （重开纲）后 GhostSection 防线（export.rs fail-closed 门 2：
      已提交记录不在树中 → 拒）保证工作区/树一致。
影响：评分项漏章 → 失分（同 F-07 面）；结构面一致性已有防线。
现状：部分防护。
建议：同 F-07（一个修法收两个缺口）。
```

---

## 5. 用户实际废标/扣分场景（可复现，验收 2）

### S-1 ★漏响应废标（对应 F-01/F-04）

```
1. 导入招标文件 → extract_requirements（★条款被抽取，params.star=true）
2. 建纲/起草/绑证据/三门过审——全程没有任何工具强制查 star 覆盖
3. get_star_coverage 从不调用（它是只读诊断，不进任何门）
4. export_bid_document → 四门全过 → 导出成功
5. 投标 → 评标委员会发现 ★条款未响应 → 否决投标（废标）
复现锚点：矩阵门 1a 只查 blocking（=必选类），★不属于必选类时零拦截
（matrix.rs:194 Lead 裁决原文）。
```

### S-2 暗标泄露废标（对应 F-02）

```
1. 招标文件含「技术标采用暗标评审…否则作否决投标处理」（GT-24 类条款，
   抽取面可识别，veto_lexicon.rs:809-811 金标准在场）
2. 起草正文中含公司名/项目班子成员姓名（业绩章、施工组织设计常态）
3. 导出时 profile 未带 dark_bid（调用方遗漏——没有任何检查提醒）
4. export_bid_document → 暗标防线完全不启动（darkbid.rs 是 opt-in）
   → docProps 作者、页眉公司名、修订记录全裸
5. 投标 → 暗标评审发现身份标记 → 否决投标（废标）
```

### S-3 过期资质废标（对应 F-03）

```
1. register_evidence：安全生产许可证 valid_until=2026-06-30（登记时
   Active，bind 时开标日口径 2026-05-01 仍有效 → 绑定成功）
2. 项目延期，实际开标日 2026-07-15
3. 导出时未传 bid_open_date（tools.rs:4050 只告警「时效未裁决」不拒）
4. E_EVIDENCE_EXPIRED 不触发（状态仍是 Active——翻转从未发生）
5. 投标 → 资格性审查：证书已过期 → 废标
```

### S-4 补遗后旧口径废标/扣分（对应 F-08）

```
1. 起草完成：工期章写「总工期 540 天」（响应原招标文件）
2. 补遗发布：工期变更为 480 天 → register_addendum_changes → DIRTY
   打标 + 改写指令生成（工具响应里可见 dirty_sections）
3. 用户/Agent 忽略改写指令（无任何门强制）
4. 导出：矩阵行已刷新但若「工期」条款类别是商务要求（非必选类）→
   不 blocking；章节正文 stale 无门 → 导出成功
   （勘误注：新旧工期数值若同在正文/参数账会命中 #423 工期冲突——
   但只读不拦，且改写后旧值消失即不再冲突，stale 本身仍无门）
5. 投标 → 评标按补遗口径：工期响应负偏离 → 扣分；若工期为★条款 →
   本仓 F-01 ★响应门收口后拦（响应未更新 = 矩阵行刷新后未响应态）
```

---

## 6. 修复优先级排序（建议路线）

| 序 | 修法 | 收口的缺口 | 工作量预估 |
|---|---|---|---|
| 1 | ★响应覆盖门（star_missing>0 → 拒/人工豁免） | F-01 + S-1 | 小（数据面全有，接门即可） |
| 2 | 暗标联动检查（暗标否决条款在场 + dark_bid≠true → 拒） | F-02 + S-2 | 小（词面复用 GT-24） |
| 3 | DIRTY 门（dirty_sections 非空 → 拒或 record_addendum_waiver 豁免） | F-08 + S-4 | 小（waiver 工具已存在） |
| 4 | unmapped_scoring_items 进导出门（豁免制） | F-07 + F-16 | 小 |
| 5 | 证据体检单 + bid_open_date 硬化 | F-03 + F-10 + S-3 | 中（先报告面后硬化） |
| 6 | 决策面对账（export 时 decision.bid_amount ↔ 正文/参数账金额特征）+ check_global Blocker 进导出门 | F-05（勘误后：正文↔正文已有 #423） | 中 |
| 7 | 格式件核对清单（签字/盖章/授权委托书） | F-06 | 中（依赖格式要求抽取子类） |
| 8 | 超篇幅可配置门 + 抽取健康度常驻 | F-09 + F-14 | 中 |
| 9 | 溯源附件导出（可选） | F-15 | 低优 |

> 审计结论：**工具面/门禁工程质量高于预期（fail-closed、独立复算、摘要绑定、豁免三要件都是硬防护），但「门禁的输入面」（漏抽取/★/时效/暗标联动/正文 stale）存在 6 个 P0 级洞——其中 4 个（序 1-4）修法都是「把已有的只读数据接进门」的小改动，建议作为 #89 面板补做之前的先决批次执行。**

---

## 审计方法与复核路径

- 全文 grep 锚点复核：`grep -rn "<锚点>" bidcore/crates/`（导出门/validate 规则/dirty 消费/unmapped 消费均做过零命中验证）
- 状态机出口：outline.rs next_allowed 全枚举 + 测试锁定（:2452）
- 正面结论（F-11/F-12/F-13）基于代码面与测试面双重确认
- 关联：#47（迭代线/规模轮数据）、#89（审查后面板补做）、#313（总纲审计）
