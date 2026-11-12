# 核心链路 11 环节审计（#118 · 审计阶段2）

> 基线：main `1c153bf4`（阶段1报告合入后）。方法：11 环节逐环节读源码答 7 问（输入/输出/丢失/硬编码/静默降级/可追溯/真实测试），锚点均本轮 Read 复核。
> 与旧六链审计（6105beb）关系：断点修复面逐项核对在位性（不复验运行时行为——那是 #112/#119/#120 的任务）。
> 结论分级：【已证实】【部分证实】【待验证】。本报告不改代码；发现登记 §4 转阶段7（#123）。

---

## 1. 11×7 矩阵

### 环节1 输入（import_tender_files）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | 文件路径列表（PDF/DOCX/XLSX/.doc 两层转换）+ 围栏 resolve_read（fs_fence 双层） | tools.rs:413 |
| 输出 | TenderFile（TF-id + sha256 + kind）+ ParsedFile（blocks） | service.rs:276-530 |
| 丢失 | 失败件不推进状态（#174）；E_PARTIAL 逐件失败显式 | lib.rs:660-662 |
| 硬编码 | 限额：roots/件数 64/单件 500MB/累计 2GB | service.rs:1091-1125 |
| 静默降级 | 无——围栏+限额+幂等（sha256 角色对账 #188） | — |
| 可追溯 | sha256 全程为对账键 | import_files:288-357 |
| 真实测试 | 收官真测三面（真 PDF/DOCX/XLSX）；songling 65页 | closeout-real-20261112 |

### 环节2 解析（PDF 仲裁器 + 引擎 OOXML）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | 原始文件字节（字节门 LIMIT_INPUT_BYTES_PDF 前置） | engines/mod.rs:67 |
| 输出 | ParsedFile(blocks: PdfLine/OcrLine/Para/TableRow/XlsxRow + parse_summary 标签) | PdfPathOutcome :46-62 |
| 丢失 | 混合件逐页路由（#424 修扫描页静默丢失）；乱码 fail-loud；OCR 救援（#200 R2 渲染面独立声音） | mod.rs:75-97 |
| 硬编码 | 文本层门 非空白≥16；残渣比 0.3 | mod.rs:103/116 |
| 静默降级 | 无——六级判决全显式（PrimaryVerified…OcrRecovered），救援不弱化防线（消息不变） | mod.rs:22-25 |
| 可追溯 | parse_summary `[pdf-*]` 标签自报；block idx/页码在场 | — |
| 真实测试 | mixed_pdf_routing/pdf_cid_identity/corpus_probe + songling 真件 | bid-parse/tests |

### 环节3 抽取（extract.rs 确定性规则）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | ParsedFile blocks（PDF 行级含 #35 段落重组/续行窗；康熙部首章节识别归一化副本） | extract.rs:79-91 |
| 输出 | Vec<Requirement>（category/params/anchors） | — |
| 丢失 | 见 §3-1 技术参数机制分析（章名子串映射兜底「其他」） | category_for:1367-1418 |
| 硬编码 | 类别=章名七关键词子串映射；无编号强词行抽取（否决/资格词表） | :1381-1391 |
| 静默降级 | **已修**：#196 kind 分发（真实文件名不再静默零抽取）；#199 反向清单（未知 kind 默认主抽取 fail-visible）；ZERO_REQUIREMENTS 响亮告警 | extract.rs:101-143 |
| 可追溯 | anchors=原文块（excerpt 保真不改写）；_veto_excluded 排除原因入 params（#52 可审计） | :150-171 |
| 真实测试 | extract_kind_dispatch/extract_pdf_para/structure_probe_272；**产品级数值保真→#112** | bid-parse/tests |

### 环节4 关键点标记（语义通路）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | get_document_chunks（分页 size≤200）→ Agent 判读 | coverage_tools.rs:55-114 |
| 输出 | BlockMark（区间 verdict）+ SubmittedRequirement（REQ-A 关键点） | coverage.rs:158-218 |
| 丢失 | #422 黑洞防护：requirement 裁决无 submitted 承接 → 正则产物**保留**+计数+告警（旧版静默丢） | merge.rs:9-15 |
| 硬编码 | 区间校验四件套（越界/重叠/双向） | coverage.rs |
| 静默降级 | 无标记严格 no-op（GT 红线——正则产物逐位一致） | merge.rs:20-22 |
| 可追溯 | REQ-Axxxx 编号跨运行稳定（#419/B-19 via merge_extraction_with_prior） | merge.rs:118-129 |
| 真实测试 | star_coverage_acceptance + songling 67条 Agent 提交（fixtures/expected） | — |

### 环节5 分类去重（merge.rs 合并面）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | 正则产物 + marks + submitted（sha256 join 按 TF 对齐） | MergeFace:35-46 |
| 输出 | 最终条款集 + MergeStats（regex_dropped/kept_unbacked/uncovered/coverage_complete） | :50-73 |
| 丢失 | Agent 优先三态：noise/rule/review_table 裁决丢弃（显式拒绝）；requirement 无承接保留（#422）；uncovered 正则兜底保留 | :8-18 |
| 硬编码 | 无面清单（附件/图纸/证据/格式模板 #271）与 extract 同源口径 | has_extraction_face:92-103 |
| 静默降级 | **已修**：B-02 前缀过滤→kind 判定（#250 同根因二次出现修复）；MARKED_REQUIREMENT_WITHOUT_SUBMITTED 告警 | :69-72 |
| 可追溯 | 保留项原 id 原序；REQ-A 追加；CMP 派生 id 零碰撞 | :120-126 |
| 真实测试 | real_corpus_e2e（纯正则链红线零位移）+ merge 单测族 | — |

**去重语义澄清（审计计划「重复条款丢要求」排查）**：合并面无内容级去重——同文条款产生两条 REQ（同块双 statement 亦双 REQ，merge.rs:760 注释自认 replace 语义不去重）；「丢要求」历史形态=旧 B-01 黑洞（已修 #422）。无内容级去重=零丢失但可能重复响应（重复响应进矩阵由人工/审校面消化）【已证实】。

### 环节6 评分表解析（scoring_table.rs 专路）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | PDF 线性化评分表流（pdftotext 列文本按行交错） | 头注:3-13 |
| 输出 | ScoringRow（name/score/objective/track/sub_items①-⑳/block_idxs/locator）→ 评分项 REQ（clause_no 综合评分表-N） | :30-45 |
| 丢失 | 行锚=分值+主客观 token（每行恰一次）保证行不丢；异常形态退化区域末（fail-visible） | :52-56 |
| 硬编码 | 行终判据=缺陷样板/不得分句（真实政采常见形态，非通用文法——模块自认） | :53-55 |
| 静默降级 | **边界诚实登记**：只覆盖 PDF 线性化形态；DOCX 真表格路径待层2 素材对账后立项（不伪装） | :48-50 |
| 可追溯 | excerpt=重建自描述头（NFKC 归一——康熙部首变体统一，检索面可用）；block_idxs 锚定 | :37-40 |
| 真实测试 | 松岭 TF-0002 25-28页实测驱动（#251）+ 8行 extract_name 全验证 | — |

### 环节7 评分映射（scoring.rs）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | REQ params（score/section_title/score_rules） | derive_scoring_items:372-490 |
| 输出 | ScoringItem + ScoringMapping（share ∈(0,1]，聚合不变量 有效份额≤1.0+ε） | upsert:1347-1457 |
| 丢失 | 分值缺失入 gaps 诚实告警（不编造）；unmapped_scoring_items 结构化面 | :1456-1463 |
| 硬编码 | 无（映射来源=派生 params.section 或账本） | — |
| 静默降级 | **已修**：unmapped 进导出门 1h（#88 修复4——豁免制非空理由） | service.rs:1808-1819 |
| 可追溯 | content_version 真变更才 bump；幂等键 (req,section) | :1422-1441 |
| 真实测试 | scoring_mapping.rs 9 测试 + fatal_gates_e2e（1h 门） | — |

### 环节8 大纲（outline.rs 三轨配额）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | 评分叶/REQ 数/三轨分类/分值权重 + target（DEFAULT_TARGET_TOTAL_CHARS=1.2M） | allocate_quotas:784 |
| 输出 | SEC 树（target_chars 父=子和守恒，配额账不平即 Err） | :1360-1385 |
| 丢失 | 无（守恒不变量硬校验） | — |
| 硬编码 | **三轨单价**：ADMIN_CHARS_PER_REQ=300/BODY_CHARS_PER_REQ=2000/MIN_SCORING_LEAF_CHARS=10000/MIN_LEAF_CHARS=500/CHARS_PER_PAGE=844 | :442-467 |
| 静默降级 | 让渡序=评分轨(按分值权重)→实质轨(按条数)→行政轨(按条数)——**无评分项挤占篇幅在机制层已防**（评分轨先取底价+先分让渡）；退化面（底价和>target）按 REQ 数均摊 | :784-830 |
| 可追溯 | 配额派生纯函数单测直测 | #253 第二段 |
| 真实测试 | 收官 47 叶配额面 + length_feedback_312（#312 写作时刻反馈：draft/append 返回体 warnings+quota 字段——修复「引擎任何字数都推 DRAFTED」假确认） | bid-mcp/tests |

### 环节9 正文（draft.rs + llm.rs）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | SectionDraftInput（REQ/EV/配额/readiness） | draft.rs:112 |
| 输出 | 章节正文 + stats（words/citations/unanchored_claims/uncovered_requirements/**generator**） | tools.rs:2610-2622 |
| 丢失 | readiness 八阻塞在位（NoRequirements…UnreadyInput） | readiness.rs:33-41 |
| 硬编码 | mock 填充到 target ±20%（确定性扩句池）；迭代轮 target_ratio | draft.rs:392-401 |
| 静默降级 | **发现 CHN-01**：generator=auto 无 api_key → mock（响应 stats.generator 记录，但 validate/export **零消费**——见 §4） | tools.rs:2480-2500 |
| 可追溯 | 引用回查（防幻觉白名单 #1237）；#127 起草指令/缺失回报与正文分离留档 | draft.rs |
| 真实测试 | mock 确定性（字节级重放）；**真实 LLM 质量验收→#113**（收官线走 mock 已自认） | — |

### 环节10 证据（evidence.rs）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | EvidenceSpec（tier 服务端裁决——调用方无从自报 :212；locator 对账；excerpt/tier 不可拆 #245） | :428-446 |
| 输出 | Evidence（四态+单向降级 degrade_to：任何→Active 拒）+ bindings | :89-95 |
| 丢失 | 换版旧件 Superseded；same_payload 幂等（tier 入幂等键 #245） | :523/560 |
| 硬编码 | Expiring=开标前 90 天窗口 | evidence.rs:28 |
| 静默降级 | **已修**：占位绑定不静默——导出门 1d 拦（NOT_APPLICABLE+偏离说明+Human receipt 三要件）；时效未裁决→bid_open_date 截止日兜底裁决（#88 修复5） | tools.rs:3809 |
| 可追溯 | EV-id + file_sha + block 锚全程；绑定打脏关联叶（#456 A-09 残留收口） | bind_evidence:774-780 |
| 真实测试 | placeholder_evidence_e2e + 变异 M2 KILLED（R-03 禁绑） | — |

### 环节11 导出（export.rs + service.rs 门族）

| 问 | 答 | 锚点 |
|---|---|---|
| 输入 | 全库态（矩阵/审校/章节/证据/决策）+ profile/format_spec/extras | service.rs:1161+ |
| 输出 | docx（manifest v2 + tmp+rename 原子）+ 证据体检单 + PDF 通道（幂等+sha 对账） | export.rs:37-66 |
| 丢失 | 组装失败/未完成 fail-closed 拒（绝不静默跳章 export.rs:7）；GhostSection 门（重开纲后已提交记录不在树→拒） | — |
| 硬编码 | 门 m 超篇幅阈值默认 +50% | service.rs:1611 |
| 静默降级 | **无**——门族 1a-1m 全 fail-closed：a 矩阵/b 审校三门+双 digest/c 写作验收独立复算/d 占位三要件/e ★响应/f 暗标联动/g 补遗 DIRTY 两分级/h 评分未映射(豁免制)/i 全局四类冲突 Blocker/j 决策对账+j-2 正文面/l 三件套缺位/m 超篇幅可配置 | service.rs:1584-1611（实测 1e-1m 代码在位 :1707-1866+） |
| 可追溯 | manifest inputs_digest（anonymize/extras/format_spec/evidences 全指纹——换名/换证据台账触发全量重建不吃旧缓存） | export.rs |
| 真实测试 | fatal_gates_e2e/b4 + export_readback（产物 zip 解包逐章断言）+ 收官真测导出复现 | — |

---

## 2. 数据流图（丢失点/降级点/硬编码点标注）

```
文件 ──(围栏/限额)──> TF+sha256 ──> ParsedFile
  PDF: [仲裁器 fail-loud | 混合页 #424 | OCR 救援]      ← 无静默丢失点
  OOXML: [mdc-office-io 单一真源]
        │
        ▼ blocks
extract（#196 kind 分发 | 章名子串类别映射 ⚠H1 | 强词行 | 段落重组）
        │
        ▼ 正则 REQ ◄── merge ◄── marks/submitted（语义通路）
        │            （Agent 优先三态 | #422 黑洞防护 | no-op 红线）
        ▼
Requirement ──> 矩阵（blocking 派生）+ 大纲
  配额三轨 ⚠H2（单价 300/2000/10000；评分轨优先让渡）
        │
        ▼
draft（readiness 八阻塞 | 引用回查 | ⚠D1 auto→mock 降级）
        │
        ▼
validate 四桶 → 审校三门（receipt 验签 + 双 digest 绑定）
        │
        ▼
export 门 1a-1m（fail-closed）→ docx 原子落盘
```

⚠H1=硬编码映射（类别兜底其他）；⚠H2=硬编码配额（不按复杂度）；⚠D1=静默降级面（唯一残留）。

## 3. 重点排查项结论（用户点名六项）

| # | 排查项 | 链路层结论 |
|---|---|---|
| 1 | 技术参数误归类 | 机制：技术参数 REQ 三个来源（技术章编号条款/语义表 #266/裸「符合」K2）+ category_for 章名子串映射（七关键词）。**章名不含关键词的技术内容全落「其他」**——67点失衡（技术参数仅1）的机制层根因候选【已证实机制，产品级数值保真→#112 逐条核验】 |
| 2 | 资格/否决/评分混淆 | 三层防线：veto_lexicon 强词+语境传播+#52 排除面统一后置（_veto_excluded 可审计，GT 1752 零误伤）；审查表接管（表7/8→资格，表9→评分）；分值形态锚定评标办法章。残留：后置否定从句（health-check 报告问题2）已有 K2/语境面——**运行时复核→#112**【部分证实】 |
| 3 | 评分表解析完整性 | 专路保证行不丢（分值 token 行锚）；跨行合并单元格轨道列块处理（:412）；**DOCX 真表格评分表路径未覆盖**（诚实登记待立项）→ 登记 CHN-03 |
| 4 | 重复条款丢要求 | 无内容级去重=零丢失（重复响应由审校面消化）；历史黑洞 B-01 已修（#422 保留+告警）【已证实】 |
| 5 | 无评分项挤占篇幅 | 机制层已防：评分轨底价 10000/叶 + 让渡序评分优先；行政组关键词单一真源分类（is_admin_group）【已证实——机制；实际分布→#119 子项A】 |
| 6 | 正文注水虚构 | 真实通路：引用回查防幻觉+占位拦截（PLACEHOLDER_MARKERS 同纪律）；**mock 通路：扩句池填充到 target ±20% = 设计性注水**，靠 generator 记录可辨识但无门消费 → CHN-01【已证实】 |

## 4. 转阶段7（#123）登记（AUD2-CHN 系列）

| 编号 | 级 | 项 | 证据 | 建议 |
|---|---|---|---|---|
| AUD2-CHN-01 | **P1** | generator=auto 无 key 静默降 mock；gen_kind 仅记 stats/chapters json；validate/导出门族零消费 → mock 稿（面向 target 的填充文）可过 1c 字数门（mock 按构造达标）直达导出 | tools.rs:2480-2500/2616；validate.rs+export.rs grep generator 零命中 | 导出报告增「生成器汇总」常驻字段（任一评分叶 generator≠real → 响亮警告）；或门 n：评分叶 mock → 须显式豁免 |
| AUD2-CHN-02 | P2 | 类别映射=章名子串（七关键词兜底其他）——真实件章名形态长尾（如「项目需求」「供货要求」）系统性落其他 | category_for:1381-1391 | 与 #112 复验联动：按 67 点实测分布补关键词或改语义面；不许静默 |
| AUD2-CHN-03 | P2 | DOCX 真表格评分表路径未覆盖（模块自认待立项） | scoring_table.rs:48-50 | 素材对账后立项（corpus-A 类真表格样本先行） |
| AUD2-CHN-04 | P3 | 配额退化面（底价和>target）按 REQ 数均摊——评分叶 10000 下限在该面不保证 | outline.rs:827-830 注释 | 小 target 场景登记边界；阶段3子项A 实测分布时顺带验证 |
| AUD2-CHN-05 | P3 | 评分表行终判据=政采样板文法（缺陷说明闭括号/不得分句）非通用 | scoring_table.rs:53-55 | 样本扩展时补形态（fail-visible 已保行不丢） |

## 5. 旧六链断点在位性核对（修复确认清单——不复验运行时）

| 旧断点 | 修复 | 在位证据 |
|---|---|---|
| P0-1 validate 单向门 | #243 recover_validating_state + #321 reopen_section | tools.rs 工具面 50 含二者；service.rs:1896 三重约束 |
| P0-2 占位绑定 | #245/PR#247 三要件 + 门 1d | validate is_legitimate_placeholder_exemption |
| A-02 时效无翻转 | #88 修复5 截止日兜底裁决 | tools.rs:3809 apply_validity |
| A-04 waiver 共门 | #379 拆门 | 867b8801 |
| A-09 dirty 零传播 | #456 bind 打脏 + 门 1g DIRTY | bind_evidence:774 |
| A-10 digest 窄面 | #474 计分面绑定 + #323 receipt v2 内容绑定（sections_digest 七段） | review.rs:862-905 |
| A-12 幂等吞重放 | #429 重放键收全负载 | 8089be3 |
| B-01 黑洞 | #422 保留+告警 | merge.rs:9-15 |
| B-02 前缀过滤 | #196/#250 kind 同源 | has_extraction_face |
| B-28 混合 PDF | #424 逐页路由 | engines/mod.rs:75 |
| #244 覆盖闭环 | 1m 前置抽取健康度常驻 + 1e ★门 | service.rs 门族 |

**全部在位**【已证实——代码面】；运行时生效面复验归 #119（历史复核）与 #120（测试真实性）。

## 6. 阶段2结论

11 环节中 10 个环节无静默降级（fail-closed/fail-loud 纪律贯穿：解析仲裁六级判决、抽取 fail-visible、合并 no-op 红线、门族 1a-1m）。**唯一残留静默降级面 = 生成器 auto→mock**（CHN-01，P1）——它同时命中审计计划两处点名（正文注水 + mock 冒充真实），是阶段2最重要发现。硬编码面集中在类别章名映射（CHN-02）与配额单价（阶段3子项A深挖）。数据丢失面：历史黑洞全部修复在位；现役丢失风险唯一登记 = DOCX 评分表路径未覆盖（CHN-03，模块诚实自认）。
