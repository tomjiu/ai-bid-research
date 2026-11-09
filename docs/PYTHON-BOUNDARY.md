# Python 侧模块边界声明（PYTHON-BOUNDARY）

> **定性：选项 A——独立研究工具（非生产链路）。**
> 本文件是 Python 侧模块与 Rust bid 链路职责边界的**唯一真源**。
> 创建于 #563；最后更新 2026-11-09（#601 研究管道四包收录）。

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
| `src/collect/`（采集面） | 本地源（JSON/JSONL）装载→规范化→三级去重 | 默认离线本地文件源，**不内置生产级网络爬虫**；`AnnouncementRecord` 是管道唯一规范化入口 |
| `src/extract/`（抽取面） | 公告原文→LLM 结构化抽取→schema 校验→合并入库；失败进 `pending_announcements` 降级面可重试 | 抽取走研究提示词（`PromptTemplates.bid_extraction`）；「LLM 补全不覆盖」——源字段强证据，模型只填缺 |
| `src/analyze/`（分析面） | 预算分位/区域/趋势/关键词频次/竞争密度 | 全部**描述性统计与启发式估算**（密度分层/HHI），报告明示「估算」口径，不冒充事实 |
| `src/pipeline/`（编排面） | collect→extract→analyze→report 四阶段串联 + `pipeline_runs` 运行台账 + 增量水位 | 研究管道一条命令；台账为审计面（研究可复现），水位只服务增量文件读取 |

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

## 4. CI 隔离

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
