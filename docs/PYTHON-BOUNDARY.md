# Python 侧模块边界声明（PYTHON-BOUNDARY）

> **定性：选项 A——独立研究工具（非生产链路）。**
> 本文件是 Python 侧模块与 Rust bid 链路职责边界的**唯一真源**。
> 创建于 #563；最后更新 2026-11-10（#601 迭代二段 R31：采集面 CSV 源扩展）。

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
| `src/collect/sanity.py`（健全性规则，R33） | 跨字段启发式告警：日期倒挂/可疑长周期/未来发布/零预算 | **告警不拒收**（区别于必填校验拒收面）；命中≠错误，研究数据质量信号随记录 `warnings` 携带 |
| `src/extract/`（抽取面） | 公告原文→LLM 结构化抽取→schema 校验→合并入库；失败进 `pending_announcements` 降级面可重试 | 抽取走研究提示词（`PromptTemplates.bid_extraction`）；「LLM 补全不覆盖」——源字段强证据，模型只填缺 |
| `src/analyze/`（分析面） | 预算分位/区域/趋势/关键词频次与月度演化（R37）/竞争密度/采购人画像（R35）/预算×区域交叉分桶（R36） | 全部**描述性统计与启发式估算**（密度分层/HHI/分桶均为研究经验口径），报告明示「估算」口径，不冒充事实 |
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
