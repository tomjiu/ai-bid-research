# 真实 Agent 标书起草验收报告（#113 · 2026-11-13）

- 执行人：agent-zai（模型审校面——**非人工批准**，全部审核门 `human_confirmed=false`）
- 主件：`real-corpus/telecom/parse-input/A-telecom-huaian-主文件.docx`（sha256 `95b62593bced…`，收官真测同件）
- 真实模型：glm-4-plus（本环境 z-ai 通路 → `scripts/zai-llm-bridge.mjs` 本地 OpenAI 兼容桥 → bid-mcp RealGenerator，`generator="real"` 显式模式）
- 驱动：`scripts/run_real_llm_path.py`（纯 MCP 面逐工具调用，与外部 Agent 同路——不进程内直调）
- 复验：`python3 scripts/run_real_llm_path.py <ws> <out>`（断点续跑：限流窗口内多轮跑齐 47 叶）

## 1. 执行范围与结果

| 阶段 | 结果 | 证据 |
|---|---|---|
| P1 导入 | 4 件（主件+3 证据附件） | driver.log |
| P2 抽取 | 371 REQ（正则兜底口径） | 大纲回执 requirements=371 |
| P2' ★门 | 漏标 2 块（`第四章 ★商务规范书`/`★第五章 技术规范书`——章标题装饰）→ 只报不标（保零标记兜底），导出面豁免 | driver.log |
| P3 建纲 | 54 节点/47 叶/48k 档（收官 mock 同口径） | counts 回执 |
| P4 证据 | 3 件登记（FILE_EXISTS 文件级锚，**合成素材**——主体名标注）+ 158 阻断全绑定 → 0 | driver.log |
| P4' 审核门 | matrix/outline/pre_export + 补遗门 4 门全 `agent_declared`（#277 留痕，`human_confirmed=false`） | tool-call 台账 |
| P5b 起草 | **47/47 叶全真实 LLM 起草，55,946 字**（收官 mock 口径 55,794 字） | llm-usage.json：47 calls / 61,142 tokens / glm-4-plus；chapters/*.json 生成器分布 `real×47` |
| P6 校验 | ok=true，blocker=0（deterministic 21 / major 5 / minor 16） | quality-summary.txt |
| P8 导出 | **被门 1i（全局一致性·金额冲突）拦截——如实止步**（§4 根因链） | §4 |

对照基线：收官 mock 链（closeout-real-20261112）同件 47 叶 / 55,794 字——本验收真实 LLM 面 55,946 字，量级一致。

## 2. 真实模型调用证据

- `.mang/llm-usage.json`（落盘副本 `artifacts/realagent-2026-11-13/llm-usage.json`）：
  `{"calls": 47, "prompt_tokens": 28965, "completion_tokens": 32177, "total_tokens": 61142, "by_model": {"glm-4-plus": {…47 calls…}}}`
- 47 章成稿 `generator` 字段全 `real`（chapters/SEC-*.json）
- 通路全链：RealGenerator（ureq HTTP）→ 桥（127.0.0.1:8787，凭据不落日志）→ z-ai glm-4-plus；`generator="real"` 无 key 响亮拒纪律保持（显式模式）

## 3. 独立审校（模型审校——四维，`review-analysis.txt` 全量数据）

| 维度 | 结果 | 判读 |
|---|---|---|
| 重复模板 | 高相似章对 0（8-gram Jaccard>0.25）；开头句式无聚集 | ✓ 无模板复读 |
| 证据引用 | `[EV-0060]`（合成资质证）被引 25 处；EV-0061/0062 零引用；未锚资质断言 8 条（泛化承诺句） | ⚠ **合成证据被当实料引用**——正式投标必须换真实材料后重跑（素材真伪红线如实登记） |
| 遗漏 | 36 REQ 未被任何章节引用：28 评分项 + 8 程序性条款（评标报告/公示/中标通知/合同签订等——招标方程序条款示响为合理） | ⚠ 评分项面遗漏与门 1h 豁免同根（评分映射 MCP 写面未提供——§5-F5） |
| 数值对账 | 投标有效期 90 天 ×3 处 ✓ 一致；**工期 37 天 0 处、报价 480 万 0 处**（正文无承诺句，决策值只在导出 profile 面） | ⚠ 采样遗漏：正文缺工期/报价承诺句（gate 1j 因此空比对通过——决策句缺位使对账门形同虚设） |

## 4. P8 导出拦截——根因链（本验收头号发现）

门 1i 报文：`金额冲突：投标保证金 在 SEC-0015=106 与 SEC-0044=800000`。

逐层根因（全部坐实，非猜测）：

- **F1（扫描器·引用编号误取）**：SEC-0015 正文「针对投标保证金要求，我方已严格按照 [REQ-0106] 的规定，足额递交了人民币肆万陆仟圆整（￥46000）」——`scan_amount`（check.rs）取维度词后**首个合规数字**，`[REQ-0106]` 的编号 `0106` 抢先命中 → 特征值 106。正文真实金额 46000（与 REQ-0106 原文一致）反而被跳过（同句已被首个数字占用）。扫描器对 `[REQ-*]`/`[EV-*]` 引用形态无守卫（现有守卫仅 %/月/年/第）。
- **F2（扫描器·上限语误取）**：SEC-0044 引用条款原文「投标保证金一般不超过项目估算价的2%，但**最高不得超过80万元**人民币」——法规上限语被当承诺值 → 特征值 800000。「不超过/不得超过/最高不高于」形态无守卫。
- **F3（validate 与 export 门不对称）**：`validate_bid_document scope=all`（P6）的 21 条 deterministic findings 中**零金额面**（实测复核），却推进 DRAFTING→VALIDATING；export 门 1i 读同一 `run_review_from_store` 真源硬拦（无豁免通道）。同一冲突面，P6 不报 blocker、P8 硬拒——**先过门后撞门**。
- **F4（VALIDATING 健康态无改稿通道 → 结构性死锁）**：门 1i 的解决出口是「改稿对齐」，但 VALIDATING 态：`draft_response_section` E_STATE 拒；`recover_validating_state` 只收缺章异常态（全叶 DRAFTED 的健康态拒）；`reopen_section` 只收 ACCEPTED；段账本为空（整稿路径）且追加不消除既有特征。**门 1i 一旦在 VALIDATING 触发，MCP 面无任何合法改稿路径**。mock 链不触发是因为 mock 文风不复述条款原文带数字——**真实 LLM 文风（逐项引用原文）必踩**。

结论：本案例冲突的两侧取值（106/800000）均为扫描器伪值，正文实际金额表述（46000）与招标原文一致——**内容层无真实不一致**；死锁由 F1×F2×F3×F4 叠加造成。恢复点完整保留（`/tmp/ws113-run` 工作区 + driver-state.json，续跑指令可复验）。

## 5. 后续 issue 提案（按优先级）

| # | 提案 | 级别 |
|---|---|---|
| F1 | `scan_amount` 补引用编号守卫（`[REQ-*]`/`[EV-*]` 紧邻维度词不取数） | P1（本案例直接成因） |
| F2 | `scan_amount` 补上限语守卫（前邻「不超过/不得超过/最高不高」的数字非承诺值） | P1 |
| F3 | validate(P6) 与 export 门 1i 同源对齐——global_conflicts 进 validate blocker 面（先把关再过门，改稿通道保持在 DRAFTING 开放） | P1（死锁的结构根因） |
| F4 | VALIDATING 健康态的受支持改稿通道（如 recover 扩「门 1i 冲突在案」出口或 1i 拦截时零副作用回 DRAFTING） | P2（F3 落地后此面触发率大降） |
| F5 | 评分项显式映射 MCP 写面（契约门 1h 注记的「后续 issue」——28 评分项遗漏的根） | P2 |
| F6 | 正文决策承诺句引导（工期/报价在正文的显式响应——生成器素材面或 Skill 指引补） | P3 |

## 6. 如实止步面（NOT_RUN 登记）

- 人工确认/追认：全部审核门 agent 声明过（GP 审计账在案）——**人工追认 NOT_RUN**（无宿主人工环节；正式投标前须人工重过门）
- 真实企业证据：**无**（3 件均为仓内合成 fixture，主体名标注「合成」）——证据分栏如实登记，正文引用面见 §3
- 正式可投标：**本验收交付审阅稿**（47 章成稿 + 台账），不等正式可投标
- P8 成品 docx：门 1i 拦截未产出（恢复点在案，F1-F3 修复后重跑即出）

## 7. 交付物清单

- `scripts/run_real_llm_path.py`（驱动·断点续跑）、`scripts/zai-llm-bridge.mjs`（环境桥）、`scripts/review_113_analysis.py`（审校分析）
- `artifacts/realagent-2026-11-13/`：chapters/SEC-*.json ×47、llm-usage.json、driver-state.json、driver.log、bridge.log、quality-summary.txt、review-analysis.txt
- 本报告 `audit/realagent-acceptance-2026-11-13.md`
