# 数据模型与架构审计（#121 · 审计阶段5）

> 基线：main `102887ab`。方法：跨工作区真跑对比实验（ID 稳定性）+ db.json 全库结构核验 + mdcore f4328eb checkout 能力面比对 + 逐概念 grep 重复定义。
> 结论分级：【已证实】【部分证实】【待验证】。

---

## 1. 子项A：数据模型

### 1.1 重复定义——逐概念核验【已证实：无意外重复】

| 概念 | 定义处 | 其他消费方 | 判定 |
|---|---|---|---|
| Requirement/Anchor | bid-domain（唯一） | bid-parse `use bid_domain::{Anchor, Requirement}`（merge.rs:30） | 单一真源 ✓ |
| ParsedFile/Block | bid-parse（唯一） | service/tools 经引用；mang-app/web-ui 经 IPC JSON | 单一真源 ✓ |
| EvidenceSpec | bid-domain evidence.rs | bid-tools `EvidenceRegistration`（service.rs:83） | **有意双结构**——工具层入参不含来源三件套（source_file/sha/fingerprint 由服务端从库内生成，「调用方自报来源不可信」#185）；文档自证边界 ✓ |
| ScoringItem/Mapping | bid-domain scoring.rs | tools/coverage 经引用 | 单一真源 ✓ |
| 传输信封 | bid-mcp schema.rs（仅 3 个 struct：{tool,args}/{ok,data|error}） | — | 不复制域类型 ✓ |

### 1.2 稳定 ID——跨工作区重跑实验【已证实】

实验：两个独立持久化工作区（ws-songling / ws-path1），同一 65 页 PDF（sha 同），各跑 导入→抽取：

```
run1: 317 条  run2: 318 条（含 1 条 Agent 标记 REQ-A）
位置对齐相同: 317/317 —— REQ-0001..0317 逐位一致，REQ-A 追加在后
ID 不一致对: 无
```

- 正则 REQ：序号稳定（merge.rs 编号纪律：保留项原 id 原序）
- Agent REQ：REQ-A 前缀 + 跨运行稳定（#419/B-19 merge_extraction_with_prior——阶段2已核）
- 重导入幂等：sha256 为键（import_files #188 角色对账）——代码面【已证实】；运行时受状态门限（MATRIX_READY 后不可重导，C-05 已知边界）
- CMP 派生 id（CMP-000N / CMP-0000-REQ-A0001 回退）零碰撞（merge.rs:120-126）

### 1.3 原文证据保留链【已证实（至导出前的全链）；导出面 P2 已知】

```
TenderFile(sha256) → ParsedFile(block_idx/page/line/locator) → Requirement.anchors
  [file, kind, locator, excerpt, block_idx, page, line] —— 七字段实测在位
→ matrix 行（requirement_id 引用）→ SEC.requirement_ids → 起草引用回查（防幻觉白名单）
→ 章节 json（chapters/{id}.json 含起草指令/缺失回报 #127）
→ 导出：evidences 面 EV-id→图片解析；溯源查询工具（get_requirement_provenance）
```

- 全链锚点在场【已证实——db.json 实测 + 代码核】
- 已知缺口（#88 F-15，P2）：导出 docx 成品不嵌条款溯源（可对照表附件属 P2 建议，未做）——不重复报，维持登记
- 评分细则链：anchors excerpt=重建自描述头（NFKC）——非逐字摘录（scoring_table 专路自述，检索面可用性优先）【已证实——设计取舍有文档】

### 1.4 中断恢复【已证实（代码面）】

- auto_checkpoint：service.rs:846，全部写路径调用（:897/:922/:932/:950/:958…）——每次工具变更后落盘
- 落盘原子性：store_io tmp+rename（#59）；manifest 幂等
- 恢复面：recover_validating_state（#243，三重约束）+ reopen_section（#321）+ state_recoveries 台账（db.json domain 键在位）+ 证据登记「不可绑态重放幂等」（#429）
- 沙箱实测佐证：阶段3 两工作区进程退出后重开，项目态完整恢复（ws 复用续跑）【已证实——本审计实际用到】

---

## 2. 子项B：重复实现矩阵（BID vs mdcore f4328eb 实测比对）

| 面 | BID 侧 | mdcore 侧 | 重复度 | 判定 |
|---|---|---|---|---|
| OOXML 读 | bid-engine→mdc-office-io（钉 rev） | office-io（docx.rs/xlsx） | **已收敛**（#11 任务3 删自研栈） | ✓ 单一真源 |
| PDF 文本抽取 | bid-parse/engines：poppler CLI + tesseract + pdf_text 纯 Rust + 乱码仲裁 + OCR 救援（#200） | pdf crate：pdfium 全引擎（engine_pdfium/annotate/forms/layers） | **低**（用途不同：标书文本抽取 vs 完整 PDF 引擎） | 各守其位 |
| DOCX 写 | bid-tools/export.rs（docx-rs：format_spec/extras/darkbid 九面扫描清零/EV图片/manifest） | office-io write.rs/rebuild.rs | **中-高**（同产 DOCX，但 BID 侧深度集成标书特有面） | 拆分方案见 §3 |
| 表格语义 | bid-parse/table_semantics（标书参数/评分表语义） | office-io（结构层切片） | **低**（语义层 vs 结构层） | 各守其位 |
| 证据域 | bid-domain/evidence.rs（四态/tier/绑定台账——业务证据） | evidence crate（fingerprint/audit——文档级指纹） | **名义重叠、语义不同**（BID 曾 borrow 其纪律：linkage_only_degrades_never_recovers） | 不迁移 |
| 快照 | mang-snap（.mang/history 单一真源） | — | 无 | — |

## 3. 子项C：BID/mdcore 边界拆分方案

**原则**（用户指令）：不为迁移而迁移，先识别真实重复；BID 留业务规则/资格否决识别/评分理解/策略映射/大纲组织/业务审核；mdcore 承接文档解析/DOCX 生成/PDF 转换/表格结构/证据锚点。

### 3.1 现状边界（本审计实测描绘）

```
已自然收敛：
  OOXML 读 → mdcore（bid-engine 唯一接触面 + rev 钉 + 对账工作流 rev-sync）
待决策（真实重复）：
  DOCX 写 → 双栈并存（export.rs docx-rs vs office-io write.rs）
刻意不迁（用途/语义不同）：
  PDF 文本抽取（bid-parse 标书专用栈，真件回归锁 structure_probe_272/real_corpus_e2e）
  表格语义 / 证据域 / 评分域 / 大纲配额（BID 业务核心）
```

### 3.2 拆分建议（分阶段，收益驱动）

| 阶段 | 动作 | 前置条件 | 收益/风险 |
|---|---|---|---|
| P0（现在） | 边界文档化（本报告）+ bid-parse PDF 栈「不迁」决策记录 | 无 | 消除边界模糊（AUD2-INV-03 收口） |
| P1（随 #90） | DOCX 写面迁移评估：office-io write vs export.rs docx-rs 等价性 harness（同输入双栈 diff 产物） | mdcore mang-shell 稳定（#90 前置即此） | 收益=统一写栈+复用 mdcore 排版能力；风险=darkbid 九面/EV图片/manifest 回归面大——**无等价 harness 不动** |
| P2（远期） | PDF 文本抽取重评估 | mdcore/pdf 文本面在真实语料基线（structure_probe_272/L1≥0.9717）上证明 ≥ 现栈 | 无证据不迁 |
| 不迁 | 证据域/表格语义/评分/大纲 | — | 语义不同层，迁移=负收益 |

### 3.3 依赖关系

- #90（bidwork GPUI 迁移）等 mdcore mang-shell 收口——本方案 P1 与其同源（都是「等 mdcore 产品面成熟」）
- mdcore#163（双内核收敛）是 mdcore 侧的镜像决策——两侧收敛后 BID 的 bid-engine 钉 rev 升级路径才畅通

## 4. 转阶段7（#123）登记

| 编号 | 级 | 项 |
|---|---|---|
| AUD2-DM-1 | P2 | DOCX 写面双栈并存——P1 迁移评估挂 #90/mang-shell 前置；先建等价性 harness 再动（本报告 §3.2） |
| AUD2-DM-2 | P3 | PDF 文本栈「不迁」决策成文（收口 AUD2-INV-03 的边界模糊面） |
| AUD2-DM-3 | P3 | 导出成品溯源附件（F-15 遗留登记，维持 P2 建议不重复报） |

## 5. 阶段5结论

数据模型纪律良好：概念单一真源（唯二双结构是文档自证的有意边界），ID 跨运行稳定（317/317 实测零漂移），锚点七字段全链在场，中断恢复面齐（checkpoint+原子写+三恢复工具+台账）。**架构层无新增 P0/P1 问题**。BID/mdcore 的真实重复只有 DOCX 写面一处（中-高重复但深度集成），拆分方案采取「等价 harness 先行 + 挂 #90 前置」的保守路径——不为迁移而迁移。
