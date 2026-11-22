# realagent-113-20261122 —— #113 真实 LLM 通路首跑证据（huaian 四件套面）

> 跑批：2026-11-22 · 驱动 `scripts/run_real_llm_path.py`（断点续跑 9 轮）·
> 模型 glm-4-plus（本地桥 `zai-llm-bridge.mjs`）· 操作者 Agent-xt11（全权轮）

## 链路

| 相位 | 结果 |
|---|---|
| P1-P2 导入/抽取 | huaian 主件 380 REQ + 合成证据 3 件（corpus-A fixture，标注合成） |
| P3 建纲 | 48 叶（目标 48,000 字档） |
| P4 证据/矩阵 | 156 阻断行 → 绑定后 0 |
| P4.6 评分映射 | 36 未映射评分项 → map_scoring_item 逐项映射（bigram 选叶）→ **criteria_unmapped=0**（门 1h 零豁免） |
| P4' 审核门 | matrix/outline/addendum = agent 声明过门（human_confirmed=False——#277 留痕待人工追认） |
| P5b 起草 | **48/48 叶全部 generator=real**（generator_summary：real:48 mock:0 external:0 unknown:0；评分叶 8/8 real） |
| P6/P6.5 校验修复 | 首校 4 blocker（评分节篇幅门 + LLM 金额/工期跨节口径漂移）→ 定向重起草 13 节次 → **零 blocker**（全稿 49,103 字 vs 目标 48,000，偏差 +2.3%） |
| P8 导出 | 257,039 B / 48 章 / sha256 f4af0262…（ waivers：★漏标 2 块章标题装饰（设计内）；格式件三件套企业身份缺位（合成素材红线——不造企业材料，审阅稿定位）） |
| P9 细则覆盖 | criteria 36（否决 120 单列排除）/ points 39 / covered **1** / ratio 2.6% / 建议扣分 27.5（字面子串口径局限如实登记——语义等价表述不识别） |

## LLM 用量（llm-usage.json）

87 calls / prompt 67,031 / completion 50,163 / **total 117,194 tokens**（glm-4-plus）

## 文件

| 文件 | 说明 |
|---|---|
| 投标文件-realagent-113.docx | 成品（48 章，审阅稿——格式件【待填】位人工补齐） |
| realagent-metrics.json | 全链指标（draft/validate/export/coverage/llm_usage） |
| driver-state.json | 断点续跑状态（含 13 节次修复决策日志） |
| bridge.log | 本地桥调用日志（只记时长/状态/字节——不记 prompt 正文） |
| llm-usage.json | 累计用量（工作区 .mang 侧拷贝） |

## 诚实边界（#113 闭门五条件对照）

1. **真实语料真实 LLM 起草** ✅（48/48 real + 用量留痕）
2. **语义覆盖 > 0** ✅（1/39——字面口径下弱正；LLM 复述未逐字引细则关键词，是真实质量发现非门失灵）
3. **人工审校批准** ⛔ 未满足（结构性：模型审校 ≠ 人工批准——#169 口径；agent 声明门全部 human_confirmed=False 待人工追认）
4. **P8 导出链通** ✅（真实起草链上导出成功，含修复轮后的门独立复算）
5. **#115 收官入口** ⛔ 未接线（realagent 面接入 acceptance_closeout 属后续工程面）

**结论：不关单**（条件 3/5 未满足——假绿零容忍）；条件 1/2/4 首次全真跑达成，
成品与决策日志在本目录留档供人工审校消费。
