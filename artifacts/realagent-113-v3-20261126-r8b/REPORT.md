# realagent 证据包（#113 真实 LLM 通路）——机器底稿

> 本文件由 run_real_llm_path 末尾自动生成（#113 审计修复批二）：
> 数字全部取 metrics/driver-state 实测，防手写漂移；叙事段与人工判读
> 由人工在其上修改（机器底稿是起点不是终稿）。

## 链路

| 相位 | 结果（实测） |
|---|---|
| 主件/REQ | A-telecom-huaian-主文件.docx · REQ 380 · 叶 48 |
| 起草/校验 | drafted 48 · blocker 0 · 字数 55,826/48,000（偏差 16.3%） |
| 修复决策 | 映射决策 36 · 修复决策 4 节次（state 实留） |
| 导出 | 287015 B · 48 章 · sha256 e33d2b75f797e17e… |
| 细则覆盖 | criteria 36 · 拆点细则 12 · points 52 · covered 52 · ratio 100.0%——无枚举形态细则 24 条不拆点不虚构（批七 D4 诚实面：P9 分母仅拆点细则） |

## LLM 用量（llm-usage.json）

52 calls / 110,549 tokens（模型 glm-4-plus；断点续跑 2 轮，累计耗时 1373s——resume 累计口径）

## 文件（实际清单）

| 文件 |
|---|
| REPORT.md |
| bridge.log |
| driver-state.json |
| llm-usage.json |
| realagent-metrics.json |
| run-console.log |
| tool-call-log.json |
| 投标文件-realagent-113.docx |

## 诚实边界（#113 闭门五条件——人工半边不代填）

1. 真实语料真实 LLM 起草：以 generator_summary（metrics.export）为准
2. 语义覆盖 > 0：以 P9 ratio 为准（字面口径局限如实登记）
3. **人工审校批准：⛔ 未满足——模型审校 ≠ 人工批准（#169 口径），待人工**
4. P8 导出链通：以 export sha256/size 为准
5. #115 收官入口：以 acceptance_closeout 接线状态为准（未接线即 ⛔）

**结论：条件 3/5 人工半边未满足前保持 open——不关单（假绿零容忍）。**
