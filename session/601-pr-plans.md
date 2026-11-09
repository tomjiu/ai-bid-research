# #601 研究管道——PR 拆分草稿（feat/601-extract 分支，恢复推送后即用）

> 状态：GitHub 账户被 suspended（2026-11-09 ~11:05Z 起全 API 403，R29 终验时仍未恢复）
> **终态：30 轮全部完成**——29 提交 + 1 终验轮；测试 45→305（+2 env 门）；六子命令组冒烟全过。
> 批次 B-F 全部提交安全在本仓库分支 feat/601-extract。
> 恢复推送后的操作序列见文末。

## 批次拆分点（feat/601-extract 上的 commit 区间）

| 批次 | 内容 | commit 区间 | 计划 PR |
|---|---|---|---|
| A 采集面 | collect（PR #602 已开，分支 feat/601-collect） | 5237edc..467f85b | ✅ #602 |
| B 抽取面 | extract | d07c666..3f02c0b | 待开 |
| C 分析面 | analyze | 0af7043..007c3a3 | 待开 |
| D 管道整合 | pipeline + 台账 + 增量 | 3bf14ac..506e845 | 待开 |
| E 数据/质量/文档/真连 | 压测+文档+env门+质量面+pending CLI | 10493e7..c3c1aac | 待开 |
| F 打磨收口 | 统计锚定+卫生+（后续轮次） | 8e3b090.. | 待收口后开 |

## 恢复推送后的操作序列

```bash
cd /home/z/my-project/ai-bid-research
# 0. 确认 PR #602 状态：若已合并 → 1；若未合并 → 等 Lead（批次 B 及以后都 base 在其上）
git fetch origin && git log origin/main -1

# 1. 推送长分支（保底——所有提交先进远端）
git push origin feat/601-extract

# 2. 按批次切分支开 PR（每个 PR 从 feat/601-extract 的区间端点建分支）：
for b in b c d e f; do ...; done
#   批次 B：git branch feat/601-extract-b 3f02c0b && git push origin feat/601-extract-b
#   批次 C：git branch feat/601-analyze 007c3a3 && git push origin feat/601-analyze
#   批次 D：git branch feat/601-pipeline 506e845 && git push origin feat/601-pipeline
#   批次 E：git branch feat/601-hardening c3c1aac && git push origin feat/601-hardening
#   批次 F：收口后从分支头建
# 3. 按「一个 PR 一个 issue」纪律逐个开 PR（正文见下），全部 base main。
#    注意批次 C 的 PR 依赖 B 已合并（stacked——先等 B 合并再开 C，或按 Lead 习惯连开）
```

---

## 批次 B PR 描述（feat/601-extract-b → main，#601）

```
## 批次 B——抽取面 src/extract/（#601）

公告原文 → LLM 结构化抽取 → 校验 → 合并入库，失败降级 pending 可重试。

### 交付面

| 模块 | 内容 |
|---|---|
| `extractor.py` | 直通/LLM 双模式（无原文/无客户端=离线直通，非失败）；输出白名单归一（与采集面同口径）；`merge_fields`「LLM 补全不覆盖」——源字段强证据，幻觉不污染；批量异常隔离 |
| `validator.py` | bid_id/project_name 硬约束拒收面 + 12 字段 hit_rate（质量口径）；推荐字段缺失不拒收 |
| `store.py` | 记录流（合并 upsert）/原文流（LLM 字段即全部；缺编号拒收**不合成伪编号**——保护 dedup 身份锚点）双路入库 |
| `pending.py` | LLM 失败/拒收 → pending_announcements（指纹幂等、可重放载荷）；`retry_pending` 双流重试：成功 resolved、仍失败保持 pending 更新 error——不静默 |
| storage | pending 表 + save/list/update/stats（损坏 payload 反序列化兜底 #563 口径） |
| `main.py` | `extract` 子命令：--source/--no-llm/--retry/--limit/--strict；无 API key 自动降级离线（警告一次）；--retry 无 key 明确拒绝退出 2 |
| CI | 冒烟：extract 离线直通 + retry 拒绝面 |

### 验证

- 全量 **193/193 绿**（批次 A 后 123 → +extract 23 +validator 10 +store 13 +pending 17 +CLI 7）
- CLI 修复实录：outcomes 与源记录位置配对 bug（LLM 失败记录不在 outcomes）→ 改 bid_id 映射逐条入库

### 设计要点（评审关注位）

1. **补全不覆盖**：merge 策略保守——LLM 只填缺，研究面宁可少信模型
2. **降级不静默**：每个失败都进 pending 带可重放载荷 + 台账可见，`--retry` 换模型重跑
3. **token 纪律**：真实 API 验证独立文件 + env 横幅门（批次 E）
```

## 批次 C PR 描述（feat/601-analyze → main，#601）

```
## 批次 C——分析面 src/analyze/（#601）

入库记录 → 描述性统计 → 关键词/密度 → 纯数据 Markdown 报告（全离线）。

### 交付面

- `dataset.py`：AnalysisDataset 只读视图（budgets/publish_dates 已清洗派生序列、award_rate、complete_rate）；路径不存在→空集不抛
- `stats.py`：预算分位（最近邻秩位法——分位必是观测值）、区域分布（top N 尾并「其他」）、月度趋势、时间跨度；空集不猜数全 None
- `keywords.py`：内置 45 词领域词表（可扩展）+ 预算关联（命中项目 budget_total/mean）+ bigram 发现模式（助词/泛词停用）
- `density.py`：发布密度（条/月）分层（低/中/高——启发式，报告标注）、采购人 top3/HHI（0-10000）、定标率、中标人 top3
- `report_data.py`：12 键 payload（JSON 可序列化）+ 六节 Markdown 渲染（预算表/区域表/趋势表/词表/新词/密度）；空集渲染缺口节；全未知区域跳节
- `generator.py`：`generate_analysis_report` 离线落盘（走现有 _save_report/export_html 面）
- `main.py`：`analyze` 子命令（--keyword/--days/--html）+ CI 冒烟

### 验证

- 全量 **249/249 绿**（B 后 193 → +dataset 12 +stats 12 +keywords 13 +density 8 +report 9 +CLI 5…参数化口径见 PR 末）
- 纯标准库（零新依赖——requirements 不变）

### 设计要点

1. 全部纯 dict（JSON 可序列化）——批次 D 管道直接喂报告
2. 密度分层/HHI 是**启发式估算**，报告口径节明示「不冒充事实」
3. 「只有未知桶」的区域分布跳节——数据缺口不伪装成分布
```

## 批次 D PR 描述（feat/601-pipeline → main，#601）

```
## 批次 D——管道整合 src/pipeline/（#601）

collect → extract → analyze → report 一条命令 + 运行台账 + 增量水位。

### 交付面

- `runner.py`：ResearchPipeline 四阶段编排；StageResult（ok/skipped/empty + detail + failures——阶段空转也说清楚为什么）；collect 新/更新分账（先查后写）；extract 只处理新公告（重跑不重复耗 API）
- storage：pipeline_runs 台账（started/finished/source/keyword/stages JSON/report_path/status；损坏兜底 #563）+ watermark REAL（epoch 亚秒——秒级人读时刻比对文件 mtime 有同秒竞态，实测暴露后双轨）
- 增量：`--incremental` 只读上次 done 运行后 mtime 变化的文件；水位缺失/损坏→退化全量不炸；无新文件=空结果（正常结局）
- `main.py`：`pipeline` 子命令（阶段状态行逐条打印 + run #id 台账可见）+ CI 冒烟（全链 + 增量重跑零新文件）
- `tests/fixtures/announcements/`：合成脱敏 6 文件（别名/重复/原文流/坏行/坏文件/缺必填/定标面）
- `tests/test_e2e_pipeline.py`：分账全对账（6 文件/11 装载/10 新/3 失败 origin 逐一）→ 报告六节逐节 → 台账 → 幂等重跑 → 关键词切片
- docs/PYTHON-BOUNDARY.md：管道四包边界收录 + §4 使用面（五要点）

### 验证

- 全量 **279/279 绿**（C 后 249 → +pipeline 9 +台账 7 +CLI 7 +e2e 7 修去重项）
- 本地冒烟：全链 run#1 → 增量 run#2 零新文件，全过
```

## 批次 E PR 描述（feat/601-hardening → main，#601）

```
## 批次 E——性能护栏 + 真连门 + 质量面 + pending 可见性（#601）

| 轮 | 内容 |
|---|---|
| 20 | 千条级性能护栏（装载 0.05s/入库 0.12s/查询 0.08s/全链 0.98s——护栏 30s/60s，只抓数量级回退） |
| 21 | README（结构段/283 用例/pipeline 示例）+ PYTHON-BOUNDARY §4 使用面 |
| 22 | LLM 真实 API 端到端：env 横幅门（#295 口径——CI 无 secret 恒跳不红）；token 纪律全程只 2 次真调用 |
| 23 | 字段级质量评估：validator 私有名转正公共 API；field_quality 逐字段填充率 + most_missing 前 5（补采行动面）→ 报告「七、数据质量」节（无缺口跳节） |
| 24 | db --pending / --pending-stats（降级队列研究可见）+ 默认统计带最近管道运行；修复 Round 18 编辑事故误删 run_db db_path 赋值（新 CLI 测试抓出的潜伏 NameError） |

验证：全量 **295/295 绿 + 2 skipped（env 门）**；CI 冒烟 11 项全链本地演练过。
```

## 批次 F PR 描述（feat/601-final → main，#601）

```
## 批次 F——打磨收口（#601）

| 轮 | 内容 |
|---|---|
| 25 | LLM 叙述报告统计锚定：_grounding_block 权威事实块（中位/分位/密度/定标率）注入 competition report 提示词——模型只解读不自算，数字幻觉源头收口 |
| 26 | 全仓卫生自查：AST 未用 import 清零（density List / report 测试 pytest）+ CI 冒烟 11 项全链演练 |
| 27 | fixture 数据集契约 README（分账预期/覆盖面/扩展约定/脱敏纪律） |
| 28 | 领域对照面：analyze --compare 多领域 9 指标并排报告（无命中领域如实 0 条/——） |
| 29 | PYTHON-BOUNDARY 使用面补对照命令 |

验证：全量 **305 全绿 + 2 skipped（env 门）**；六子命令组完整冒烟过。
```
