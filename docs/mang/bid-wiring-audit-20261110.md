# #313 标书工作台数据面接线——总纲审计收口（2026-11-10）

> 总纲 issue：本仓 #16。审计基线：main = `3d5bab9`。审计人：Agent-ww4y（认领评论 #issuecomment-922）。
> 方法：git 全历史考古 + `TOOL_NAMES` 单一真源核对 + `bid.rs`/`ipc.rs` 分发面逐行核对 + `node web-ui/tests/bid-panels.test.mjs` 实跑复验。

## 一、「批 E」存在性结论：**不存在——#313 共 A~D 四批，已全部完成**

证据四条（互相独立）：

1. **git 全历史**：`git log --all --grep="313"` 仅四组系列提交——批 A（`ccefa07`/`47c87aa`）、批 B（`a456970`/`33d51ec`）、批 C（`aba8532`/`347e0c1`）、批 D（`1f731ce`/`6121ccf`）。无任何 313×批 E 提交。
2. **IPC 契约**：`docs/mang/IPC-CONTRACT.md` 中全部 `bid.*` 命令的批次标注只有 批 A/B/C/D 与 **#603 批 A**（`bid.gates`/`bid.gate_pass`——治理面独立系列，不是 #313 的第五批）。
3. **撞名排查**：全仓文本搜「批 E」12 处命中**全部**属于 **#601 批次 E**（`#601` 数据管道/LLM 系列的第 5 批：`tests/test_cli_pending.py`、`test_llm_real_api.py`、`test_bulk_performance.py`、`test_analyze_quality.py`、`src/extract/validator.py`、`src/analyze/quality.py`）。「#313 有批 E」是两个系列批次号撞名引起的误记。
4. **PR 台账**：批 A = 旧站 PR #576、批 B = 旧站 PR #589、批 C = 旧站 PR #592、批 D = 本站 PR #3、审核门 = #603（本站 PR #4）。无第六个 PR。

## 二、数据面缺口盘点：50 工具 vs 8 命令

### 已接线（8 命令 → 7 工具直连 + 1 同源直读）

| IPC 命令 | 后端路径 | MCP 工具 | 批次 |
|---|---|---|---|
| `bid.state` | `bid::state` | `get_bid_project_state` | 批 A |
| `bid.outline` | `bid::outline` | （DomainStore 直读，与 `build_outline` 同源不同路） | 批 A |
| `bid.matrix` | `bid::matrix` | `get_compliance_matrix`（游标分页） | 批 B |
| `bid.quality` | `bid::quality` | `check_bid_quality` | 批 C |
| `bid.score` | `bid::score` | `score_document` | 批 C |
| `bid.gates` | `bid::gates` | （DomainStore 直读五门台账） | #603 |
| `bid.gate_pass` | `bid::gate_pass` | `record_review_gate` | #603 |
| `bid.coverage` | `bid::coverage` | `get_coverage_report` + `get_star_coverage` | 批 D |

前后端命令对齐 8/8（`app.js` `ipc("bid.*")` 与 `ipc.rs:460-479` 分发逐字一致）；五个 `data-bid-panel` 页签无禁用占位；侧栏 5 入口全通。`node web-ui/tests/bid-panels.test.mjs` 实跑 **114 passed / 0 failed**（2026-11-10，main = 3d5bab9）。

### ★ 接线缺口（产品需要、前端无入口）——已按价值立实施 issue

| # | 缺口 | 工具 | 产品理由 | 优先级 |
|---|---|---|---|---|
| 缺口-1 | 导出与校验闭环 | `export_bid_document`、`validate_bid_document` | 标书写完后用户在 UI 上**拿不到成品文档**——产品出口断裂（§0.0.10 同构教训） | P1 |
| 缺口-2 | 项目导入向导 | `create_bid_project`、`import_tender_files` | 现只能代理/CLI 建项；`bid.coverage` 的 next 引导已有空态雏形可接 | P1 |
| 缺口-3 | 治理出口三件 | `set_matrix_override`（#226 否决项死锁出口）、`recover_validating_state`（#243 异常态恢复）、`list_packages`（#316 分包选包） | 均为用户决策/治理动作，天然产品面 | P2 |
| 缺口-7 | 五面板真实 e2e | （见 §三） | 现状全部为源级静态断言，无「点击→数据流→文件变化」全链 | P2 |

### △ 已识别、暂不立 issue（backlog——Lead 可按需提升）

- **缺口-4 证据材料管理**：`list_evidence`/`search_evidence`/`register_evidence`/`bind_evidence`（代理可驱动；人工登记/绑定是材料治理面）
- **缺口-5 业绩材料库**：`register_performance`/`list_performance`/`recommend_performance`/`write_performance_section`（跨项目资产，登记/推荐有人工面）
- **缺口-6 任务台账**：`list_tasks`/`advance_task`/`batch_task`（`bid.state` 已有快速统计；列表/推进是细粒度面）

### 明确不接（代理纪律面，MCP/stdio 驱动，by design）

`extract_requirements`、`draft_response_section`、`append_section_segment`、`rewrite_section_segment`、`list_section_segments`、`register_addendum_changes`、`rewrite_section_partial`、`assign_revision`、`advance_revision`、`complete_revision`、`reopen_section`、`set_param_responses`、`score_price`、`score_section`、`check_scoring_coverage`、`recommend_length_profile`、`get_document_chunks`、`submit_block_marks`、`get_requirement_provenance`、`get_block_requirements`、`save_version`（与桌面壳 `snapshots.*` 正交，属代理「每章一存」纪律）、`list_tools`（行协议握手）、`build_outline`（数据面已由 `bid.outline` 直读覆盖，工具本身供代理重建大纲）——共 24 件。

### 观察项（登记不展开）

- `get_annotation_overlay`（#285 块级 overlay 渲染数据面）与 `annotations.load`（#42 `.mang/annotations/` 边车）是**两套标注数据面**——是否统一属产品方向决策，建议 Lead 裁定后立独立 issue（与 mdcore 仓 §0.0.10 教训②「overlay 层孤岛」同构风险）。

**核算**：7 直连 + 18 缺口（4 立-issue + 14 backlog）+ 24 不接 + 1 观察 = 50 ✓

## 三、五面板 §0.0.10 三行闭环

| 面板 | 用户入口 | 操作后变化 | 端到端测试 |
|---|---|---|---|
| detail（批 A） | 侧栏「标书工作台」→ detail 页签；大纲树节点点击 | 只读渲染章节详情（`bid.outline` DomainStore 直读）；无 db.json 变化 | **缺失**（静态断言 + 后端往返，无全链） |
| matrix（批 B） | 工作台 matrix 页签 / 侧栏「合规矩阵」 | `get_compliance_matrix` 游标分页读；筛选/翻页为前端态；CSV 导出为浏览器下载（不改 db.json）；行跳转 `explorer.reveal` | **缺失**（同上） |
| quality（批 C） | 工作台 quality 页签 / 侧栏「自评」 | `check_bid_quality` 只读报告 + 进度条（不足标红）；无落库 | **缺失**（同上） |
| gates（#603） | 工作台 gates 页签 / 侧栏「审核门」 | 「追认/过门」→ `bid.gate_pass` → `record_review_gate` **写 db.json**（门记录 + receipt）→ 台账刷新 | 后端 `bid.rs` 有 gate_pass 拒审/追认往返；**UI 全链缺失** |
| coverage（批 D） | 工作台 coverage 页签 / 侧栏「覆盖报告」 | `get_coverage_report` + `get_star_coverage` 只读（conic 三色环 + 分账条 + 逐文件表）；未导入件诚实口径 `total_blocks=0` + next 引导 | **缺失**（同上） |

现状佐证：`bid-panels.test.mjs` 114 条全部为源级断言（`readFileSync` + 字符串检查，其文件头自称「源级回归门」）；后端 `bid.rs` 测试经 `dispatch_with` 真跑工具面。缺的是「用户点击 → IPC 数据流 → db.json/界面变化」的 UI 驱动全链——IPC-CONTRACT.md:745 的无窗口跑清单可作起点。

## 四、总纲收口

1. **#313 确认完成**（A~D 四批全合入，无批 E）→ 本总纲打 `status/done` 关闭。
2. 衍生实施 issue（本 PR 同批登记）：缺口-1（P1）、缺口-2（P1）、缺口-3（P2）、缺口-7（P2）。
3. backlog（缺口-4/5/6）与观察项（双标注面）留档于本文档，Lead 按产品方向提升。

## 本地验证

- `node web-ui/tests/bid-panels.test.mjs` → **114 passed, 0 failed**
- `git log --all --grep="313"` / `grep -rn "批 E"` 全仓考古 → 证据见 §一
- `TOOL_NAMES`（`bidcore/crates/bid-mcp/src/lib.rs:77`，50 件）逐件分类 → §二核算

Refs #16
