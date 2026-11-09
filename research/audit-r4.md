# R4 审计报告 —— R3 剩余项修复轮 + 远端合并（主代理自查）

- 审计轮次：R4（继 R1 夹具规格 / R2 代码 / R3 安全审计之后）
- 审计日期：2026-10-25
- 审计对象：commit `3ac962e`（合并远端 m1/ 并行线 + run_tests T10~T13 + _anchor_hit 双口径）、`0e50961`（S3-1 zip64 守恒 + S3-3 xlsx 双轴门 + P2-4 stderr drain + S3-4 严格判据 + fp_sampling + 文档计数），基线 `f59b3f1`
- **审计性质声明（诚实降级）**：子代理基础设施本会话三次启动失败（context deadline exceeded），本轮为**主代理自查审计**——独立性弱于 R1~R3 的子代理审计，已用攻击样本实证 + 红证复核 + 声明逐项复跑补偿；下轮子代理恢复后建议对同一范围复审
- 审计方法：攻击样本实证（独立 crate `/home/z/my-project/scripts/audit_r4` path 依赖 bid-parse 调 pub API 真跑，仓库零污染）+ 全量回归复跑 + 声明逐项核对
- 纪律：只审计不修改业务代码；攻击 crate 与样本全部在仓库外

---

## 0. 结论速览

| 级别 | 计数 | 摘要 |
|---|---|---|
| S1 严重 | **0** | — |
| S2 应修 | **0** | — |
| S3 建议登记 | **3** | A6 形态（declared==absorbed 的一致性畸形归档被接受——单消费者内部一致，低威胁）；A7 形态（前置垃圾 zip64 归档守恒门跳过——未实现 archive-offset 校正，依赖 crate 自身校验）；_anchor_hit 相邻块拼接理论假命中窗口（有界：仅相邻对+归一化逐字） |
| P 轻微 | **1** | 自查审计 harness 自身 2 处构造 bug（A2 deflate 压掉伪记录字节→Stored 修复；A3 patch 文件头偏移而非 eocd 偏移→修复）——过程记录，证明实证是测试驱动的 |

**核心结论**：R3 报告的全部剩余项（S3-1/S3-3/S3-4/P2-1/P2-4/P2-5/P2-6）修复属实且负向测试有真实杀伤力；zip64 守恒门在 7 类攻击变体下无绕过（2 类被本仓门拒绝、3 类被 zip crate 自身一致性校验拒绝、2 类为登记在案的低危 exotica）；合并（m1/）后回归门禁完整。

---

## 1. 攻击面实证（独立 crate 真跑，/home/z/my-project/scripts/audit_r4）

### A. zip64 守恒门（guard.rs eocd_declared_entry_count + open_guarded）

| 变体 | 构造 | 结果 | 裁决层 |
|---|---|---|---|
| A1 R3 原样本复刻 | zip64 EOCD 声明 2 + 中央目录 2 同名条目 | **REJECT**：声明 2 ≠ 实际 1 | **本仓守恒门**（修复生效） |
| A2 伪记录注入 | locator 指向 Stored 条目内容中的伪 PK\x06\x06（count=1） | REJECT：crate 拒开（外层结构不一致） | zip crate |
| A3 标记无 locator | EOCD 0xFFFF 标记、无 zip64 结构 | REJECT：crate "Could not find EOCD" | zip crate（fail-closed） |
| A4 locator 越界 | offset=0xFFFF_FFFF_0000 | REJECT：crate "Invalid EOCD64 Locator CD offset" | zip crate（本仓 OOB 检查为纵深防御） |
| A5 天文计数 | zip64 count=u64::MAX | REJECT：crate "inconsistent number of files" | zip crate（对 zip64 计数做自身一致性校验） |
| A6 声明1+目录2同名 | declared(1)==absorbed(1) | **ACCEPT len=1** | 见 S3-1 登记 |
| A7 前置垃圾+合法 zip64 | 256B 前缀 | **ACCEPT len=1** | 见 S3-2 登记 |

**A6 分析（S3 级登记，不修）**：中央目录物理含 2 同名条目而 zip64 声明 1——crate 视图内部一致（无论其走到第 1 条即停还是全走吸收，by_index/by_name 单一视图无"查A读B"分歧；calamine 同依赖 zip 4.6.1 同视图）。危害需多消费者对畸形归档解读分歧，本流水线单消费者——威胁评级低。守恒门语义（declared ≠ absorbed 即拒）在此形态下 green 是**语义正确**而非漏报。
**A7 分析（S3 级登记，不修）**：前置数据使 locator 绝对偏移失准 → 本仓链解析落 None → 跳过（guard.rs 注释已登记 exotica）；crate 以 archive-offset 检测自行正确解析。要利用该跳过面，攻击者需构造 declared==absorbed 形态（即 A6 无危害形态）——与 crate 的 zip64 计数一致性校验（A5 证据）合围后无实际绕过路径。

### B. xlsx 读后双轴门（xlsx.rs）

- B1 恰 200,000 行（=限值）：**ACCEPT blocks=200000**（边界语义 `>` 非 `>=`，正确）
- B2 200,001 行：**REJECT** "xlsx 有效行 200001 超上限 200000（拒绝不留部分结果）" ✓
- 样本为字节级构造最小合法 xlsx + calamine 真解析（非 mock）；高熵内容验证未误触发压缩比门（触发的是目标门）

### C. stderr drain（run_limited）

- C1 stdout 溢出（yes 100M）+ stderr 洪泛（dd 512KB）并发：**OutputOverflow，20ms 即返**——溢出优先分类未被 drain 破坏，无挂死
- 红证复核（本会话早前）：临时还原 take 行为 → `subprocess_stderr_flood_drained_not_blocked` 以 `NonZeroExit{code:141}`（SIGPIPE=13）失败 → 恢复 drain 后通过——测试杀伤力实证在档；顺带修正 R3 审计对 P2-4 失效模式的推理错误（非"阻塞→Timeout"，实为 SIGPIPE 中杀）

### D. _anchor_hit（run_tests.py T12）

- 双口径评估：单块逐字（原口径不变）优先；回退 = _norm_cn 归一化 + **相邻两块**拼接。假命中需 GT 锚点归一串恰好横跨两相邻块语义边界（段落尾+无关段首）且逐字连续——真实 GT 锚点为完整条款句，跨语义边界拼出完整条款的概率极低且有界（不模糊匹配、不全文件拼接）。评级：理论窗口，可接受（S3-3 登记）。

---

## 2. 声明逐项核实（全绿面）

| 声明 | 复核 | 结果 |
|---|---|---|
| cargo workspace 53/53 | 复跑 `cargo test --workspace` | ✓（48→53：+2 zip64 +2 xlsx +1 stderr） |
| run_tests 46/46 | 复跑（37 本地线 + 9 m1 线） | ✓（m1 四场景判分/锚点 27~27/双跑字节一致真跑） |
| xref 0 错误 | 复跑 | ✓（8 项 C7 谓词告警为历史存量） |
| 引用支持 18/18 严格口径 + {0:17,-1:1} | 复跑 real_eval_score.py | ✓ 逐位一致 |
| fp_sampling 确定性 | 双跑 diff | ✓ 完全一致（seed=20261025） |
| threat-model 计数（T-03 12 项/T-04 9 项） | `cargo test -p bid-parse -- --list` 清点 | ✓（zip 面 12 + 子进程面 9 + xlsx 2 单列） |
| REPORT 20.6s | real-eval-report.json elapsed_secs=20.602 | ✓ |
| T 标签无冲突 | 正则提取 39 个 check 标签 | ✓（T7a/T8 等为组内子项编号，全名唯一） |
| 合并无夹具漂移 | T3 manifest sha256 逐文件 + T6 重生成一致（run_tests 内） | ✓ |
| 远端同步 | git status -sb（3ac962e 已推；0e50961 待本轮推送） | ✓ |

---

## 3. 处置建议

1. S3 三项登记入 threat-model（A6/A7/D 形态）——随本报告同批补一行，无需代码改动。
2. 子代理审计能力恢复后，建议对 0e50961 范围做 R5 独立复审（本轮独立性弱化的补偿）。
3. 无 S1/S2——本轮修复可随 0e50961 + 本报告提交推送。

*审计人：主代理（R4 自查降级轮——子代理基础设施三次启动失败；攻击 crate 与样本留存 /home/z/my-project/scripts/audit_r4，仓库零污染）。*
