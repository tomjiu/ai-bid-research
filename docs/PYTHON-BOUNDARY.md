# Python 侧模块边界声明（PYTHON-BOUNDARY）

> **定性：选项 A——独立研究工具（非生产链路）。**
> 本文件是 Python 侧模块与 Rust bid 链路职责边界的**唯一真源**。
> 创建于 #563；最后更新 2026-11-08。

---

## 1. 定性结论

`src/llm` / `src/report` / `src/storage` + `main.py` 定性为
**独立研究工具**（数据探索 / 竞品分析 / 快速原型），**不进生产链路**。

```
· 纯 Python CLI（python main.py），不被 Rust 侧调用，也不调用 Rust 侧产物
· 无状态机、无版本管理、无审核门（对比 Rust P0-P8 链路）
· SQLite 为本地研究工作区文件，不是服务、不入库（.gitignore 钉死）
· CI 独立（python-tests.yml 只跑 pytest，不接入 bid 的 4 项检查）
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
| `src/collect/`（采集面，#601-A） | `import_tender_files`（P1 导入） | **各自独立** | 研究采集只吃本地 JSON/JSONL 源（离线），不做生产级爬虫；去重/规范化语义与 P1 链路无对齐义务 |
| `src/extract/`（抽取面，#601-B） | `extract_requirements`（P2 抽取） | **各自独立** | 研究抽取（规则基线/LLM）产研究缓存；正式条款抽取/★扫描/语义表只在 Rust 侧（分记不折抵） |
| `src/analyze/`（分析面，#601-C） | 无对应 | — | 五维统计为纯研究结论（口径在 docstring 声明，可由原始数据复算）；无生产语义 |
| `src/pipeline/`（管道面，#601-D） | P0-P8 链路 | **各自独立** | 研究管道四阶段（collect→extract→analyze→report）是研究工作区编排，不是 P0-P8 状态机；无门禁/审核语义 |
| `src/extract/eval.py`（评估面，#601-E） | 评测链（research/） | **各自独立** | gold 字段命中率只评 Python 研究抽取器（rule/api 模式），与 Rust 评测链（GT 红线/召回门）分轨 |

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

## 4. raw 公告暂存面与管道留档（#601 批次 B/D）

`raw_announcements` 表是抽取面的**失败降级暂存**（研究工作区内）：

```
· 用途：公告原文（.txt）装载 → LLM/规则抽取 → 成功进 bids 表 +
  标 extracted；失败保持 pending + error 留档（重试不丢原文）
· content_sha 唯一索引：同文重复导入幂等（研究面防重复占位）
· 生命周期：extracted 的记录不再处理；pending 的可反复重试
  （attempts 计数可见）；不属于任何生产状态机
```

`pipeline_runs` 表是研究管道的**运行留档**（批次 D）：

```
· 每次正式运行记一行：started_at/finished_at/ok/stages_json
  （各阶段统计）/report_path——研究面可回溯「哪次跑了什么」
· dry-run 不留档（零副作用语义）
· 管道阶段失败不中断（analyze/report 只依赖库内数据）——
  这与 P0-P8 门禁语义完全不同，勿混淆
```

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

## 5. .gitignore 钉死项

```
output/            # Python 报告输出目录（研究快照，可再生）
data/              # SQLite 研究数据库（本地工作区，不入库）
.pytest_cache/     # 测试缓存
__pycache__/       # 字节码缓存
```

## 6. 维护纪律（#563 验收 4）

**未来新增任何 Python 模块，必须同步更新本文件**：

1. 在 §2 对照表中登记模块名、Rust 对应物、真源归属；
2. 涉及数据存储的，在 §3 补 schema 说明；
3. 模块 docstring 首行必须带「非生产链路——仅供研究」标注
   （与本文件定性一致）；
4. 需要跑测试的，路径加入 python-tests.yml 的触发列表。

违反任一条 = 新的隐式真源 = 重复 #563 的问题。

## 7. 关联

- #554 PR——引入 Python 模块（本边界声明所回应的对象）
- #563 Issue——边界任务（本文件即其交付物）
- #457 PR——ai-bid 三层架构（bid-domain / bid-tools / bid-mcp）
- `AGENTS.md` 0.0.10——引擎能力 ≠ 产品可用（模块存在 ≠ 职责清晰）
