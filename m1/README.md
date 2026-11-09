# m1 — M1 最小流水线（Rust）

> 研究验证阶段的**被测系统**：后端权威状态机 + import/extract + 确定性切块 + exact 检索通道。
> 业务核心按架构决策用 **Rust** 实现（生产链路 100% Rust；Python 仅保留在 scripts/ 作评测层——
> 夹具生成/判分/一致性检查，不进生产，两侧以 grade.py 冻结的 db.json 契约解耦）。

## 模块

| 文件 | 职责 |
|---|---|
| `src/contract.rs` | db.json / trace.jsonl / blocks.jsonl 冻结契约结构 + 内容寻址 ID（sha256） |
| `src/state.rs` | 权威状态机：INIT→DRAFT→FILES_IMPORTED→REQUIREMENTS_EXTRACTED；未实现/越级工具一律 `E_STATE` 零副作用（TC-11）；文件 sha256 幂等键表（TC-07） |
| `src/import.rs` | 按扩展名分派；PDF 文本层（pdftotext）/扫描件 OCR（pdfimages+tesseract）；per-file parse_report |
| `src/docx.rs` | DOCX 解析（zip + quick-xml）：段落/标题/表格（Row+Cell 双粒度）/分页估算，locator 带章节上下文 |
| `src/xlsx.rs` | XLSX 解析：sharedStrings + inlineStr 双通道，行块 |
| `src/canon.rs` | OCR 文本确定性规整（半角标点全角回正 + CJK 邻接空格删除） |
| `src/chunk.rs` | 确定性切块（120 字符/块；M1 粒度先满足 TC-01 chunks≥100，生产粒度后续调优） |
| `src/extract.rs` | 结构化条款抽取（规则①~⑨，零 GT 窥视）+ 编号序列完整性（无跳号无撞号） |
| `src/search.rs` | exact 通道：token 覆盖率 → 命中密度 → 导入序 → 块序（全确定性排序）+ 数值归一化（"3500000" ≡ "350 万元"）+ 5 次重放一致性 |
| `src/run.rs` | 场景编排（TC-01/02/07/11）：驱动工具序列、自检 expected-transitions 的 step expects、产出契约工件 |

## 冻结契约（db.json，M1 诚实子集）

M1 产出的字段与 `scripts/grade.py` docstring 逐一对齐。**M2/M3/M4 范围字段
（matrix/citation/findings/conflicts/sections 内容/export/recheck）一律不出现**——
判分器按缺字段 FAIL（每场景失败维度必须恰为 `G3_policy/G4_citation/G6_rules`，
出现集合外失败即回归，由 run_tests T8b 把关）。

REQ 纪律：`gt_ids` 恒为空（诚实管道不知道 ground truth）——召回只依赖判分器对齐器
（clause_no 双因子/锚点互含/唯一参数），自报无法虚增覆盖；金额为多值字段（`amounts` 数组）
不参与标量对齐（"200 万"这类跨条款共享阈值会引发跨类别伪对齐，v0.4 实测 REQ-4.3×GT-03）。

## 确定性纪律（兼容性答卷）

- 全部 ID 内容寻址：`REQ-<sha256(clause_no+首锚点)[..10]>`、`F-`、`C-` ——重跑零漂移
- 输出**零时间戳/零随机**；T12 双跑 db/trace/blocks/chunks 四工件**字节一致**
- `Cargo.lock` 提交入仓；tessdata 内容寻址入仓（见下）
- OCR 通道钉死：`OMP_THREAD_LIMIT=1` + 固定 tessdata + 固定 psm 6

## 外部工具链（版本记录 → D5 矩阵）

| 依赖 | 版本口径 | 说明 |
|---|---|---|
| poppler-utils | Debian trixie 系统 pdftotext/pdfimages | PDF 文本层 `-layout`；扫描件原图抽取 |
| tesseract | 5.5.0 | OCR 引擎（C++，无 Python 参与） |
| chi_sim.traineddata | tessdata_fast，`sha256=a5fcb6f0db1e1d6d8522f39db4e848f05984669172e584e8d76b6b3141e1f730` | 提交于 `m1/tessdata/`（离线可复现） |

OCR 规整依据（canon.rs，实测混淆类）：全角标点→半角（`；`→`;`）、CJK 间伪空格；
规整为**确定性回正**（源像素本为全角），非语义修正。已知残余 OCR 噪声（不影响判分，
记录在案）：标题"投标函"→"投标邢"、正文"全册"→"全肌"、"90"→"98" 等——
真实扫描件的 OCR 质量差异归 D5 分层（corpus-R 真实样本）承接，不在此掩盖。

## 构建与运行

```bash
cd m1 && cargo build --release && cargo test --release   # 5 项单测
cd .. && ./m1/target/release/m1 run --scenario TC-01     # 产出 runs/TC-01/{db,trace,blocks,chunks}.json(l)
python3 scripts/grade.py --run runs/TC-01               # 判分（M1 维度见 run-tests T8b）
```

## V1-a 首轮结果（corpus-A）

- **锚点覆盖 27/27 = 100%**（含 GT-07 双锚点：A 正文 + B2 扫描件 OCR；GT-20 双锚点：数字日期 + 中文大写日期）
- 四场景判分：**G1 召回 100%（对齐器通道，零自报）/ G2 精确 25/25 / G5 场景断言全过 / G7 幂等 no-op**
- `parse_failures=0`；编号序列完整（missing_sequence=0）；B2 走 OCR 通道 `ocr_required`（19 行）

## 后续里程碑（pending 维度）

| 维度 | 里程碑 | 内容 |
|---|---|---|
| G3_policy | M2 | 合规矩阵三态判定（GT-02 临界翻转 / GT-04 MISSING / GT-13 禁绑）+ 证据有效期解析 |
| G4_citation | M3 | 章节起草 + 引用回填（V1-b：导出后定位器回查） |
| G6_rules | M4 | 8 类确定性规则（defect-drafts 样本） |
| TC-09/V2 | — | 补遗影响面级联（DIRTY 传播 / 有效期重检 / CONFLICT-01 终裁） |
