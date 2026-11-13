# DOCX 真表格评分表素材对账（#134 · CHN-03）

> 任务面：scoring_table.rs 自述「DOCX 真表格路径不经过本模块（待层 2 素材
> 对账后立项）」——本文件即该对账交付物（素材先行，不写解析器）。
> 盘点日：2026-11-13。扫描器：`scripts/scan_docx_scoring_tables.py`；
> 现状实测：`bidcore/crates/bid-mcp/tests/docx_scoring_materials.rs`（真实链路真跑）。

## 1. 盘点结论：有素材（非 BLOCKED）

全仓 DOCX 素材 **74 件**（corpus-A 3 / corpus-R 7 / real-tender-batch2 63 /
real-samples 1 / real-corpus-telecom 7 / synth-tender 2——real-tender-batch1
目录为空，无素材），其中 **7 件含真表格评分表形态、共 28 张**：

| # | 件 | sha256_12 | 来源性质 | 评分表数 |
|---|---|---|---|---|
| M1 | real-corpus/telecom/parse-input/A-telecom-huaian-主文件.docx | 95b62593bced | 真件（政采主文件） | 4 |
| M2 | real-corpus/telecom/parse-input/A-telecom-shanghai-songjiang-光终端放装-招标文件.docx | 55c8f074fcc6 | 真件 | 1 |
| M3 | real-corpus/telecom/parse-input/A-telecom-shanxi-灵枢智关-招标正文.docx | 699485806c5b | 真件 | 5 |
| M4 | real-corpus/telecom/parse-input/A-unicom-ry-2026CUC-RJY-PT0783-招标文件.docx | c6e225afd942 | 真件 | 2 |
| M5 | real-samples/北京水利施工示范文本2025-LO.docx | df48dca923a3 | 真件（示范文本） | 13 |
| M6 | fixtures/real-tender-batch2/docx-jlyh/JLYHDH-2026-ZC122医养结合机构能力提升（三次）.docx | 5dc231ecfff3 | 真件（政采） | 1 |
| S1 | fixtures/synth-tender/招标文件/A-招标文件.docx | b5cfe741e924 | 合成件（形态对账面，非真件声明） | 1 |

口径：评分表形态启发式 = 表头/首两行含「评分/评审/评标/得分/分值/细则」词 +
表内存在独立分值数值格 + 主客观列在场（`scan_docx_scoring_tables.py::is_scoring_like`）。

## 2. 逐表结构登记（fixture 登记——来源/sha/结构形态）

行真值口径：数据行 = 总行 − 表头行（表头行 = 首行含评分词）。

| 件 | 表 | 规模 | 合并形态 | 跨页候选 | 分值格行 |
|---|---|---|---|---|---|
| M1 | tbl#2 | 47行×6列 | vMerge=123 gridSpan=32 | ✅ | 16 |
| M1 | tbl#4/5/19 | 12行×5列 ×3 | 无合并 | — | 3/表 |
| M2 | tbl#3 | 42行×5列 | vMerge=69 gridSpan=36 | ✅ | 13 |
| M3 | tbl#5 | 30行×6列 | vMerge=74 gridSpan=23 | ✅ | 12 |
| M3 | tbl#8 | 15行×6列 | vMerge=12 | ✅ | 13 |
| M3 | tbl#9/10/23 | 12行×5列 ×3 | 无合并 | — | 3/表 |
| M4 | tbl#2 | 17行×5列 | vMerge=45 gridSpan=2 | ✅ | 1 |
| M4 | tbl#3 | 6行×3列 | gridSpan=3 | — | 1 |
| M5 | tbl#3 | 45行×4列 | vMerge=84 gridSpan=3 | ✅ | 1 |
| M5 | tbl#7/8/9 | 8/14/16行×6列 | vMerge=6/表 | ✅ | 4/10/12 |
| M5 | tbl#10 | 14行×9列 | vMerge=9 gridSpan=8 | ✅ | 9 |
| M5 | tbl#20/21/22 | 9/14/16行×6列 | vMerge=6/表 | ✅ | 5/10/12 |
| M5 | tbl#24 | 15行×10列 | vMerge=12 gridSpan=8 | ✅ | 10 |
| M5 | tbl#25/28/29 | 6/5/6行×7列 | vMerge=8/表 | ✅ | 3/2/3 |
| M5 | tbl#27 | 6行×6列 | gridSpan=2 | — | 4 |
| M6 | tbl#4 | 15行×4列 | vMerge=26 | ✅ | 1 |
| S1 | tbl#2 | 9行×3列 | 无合并 | — | 8 |

跨页候选口径（如实）：DOCX 无显式跨页标记（分页由渲染器决定）——以
「行数 >15 或 vMerge 在场」标注**候选**；vMerge 重度（M1 tbl#2 123 处）+
行数大（M5 tbl#3 45 行）是真实政采评分表的典型大表形态。**二级表头**
（评审项列 vMerge 纵向合并 + 评审因素/标准/分值横向 gridSpan）是 M1-M4
政采件的主形态；M5 示范文本是「序号/评审内容/标准/分值」平铺形态。

## 3. 现状缺口实测（真实链路真跑——2026-11-13）

方法：`docx_scoring_materials.rs` 每件独立工作区+独立项目，真实链路
`import_tender_files → extract_requirements`（受信根接线与 real_closeout
同款），对账「评分表数据行 vs 评分项 REQ」：

| 件 | 评分表数据行 | 评分项 REQ（现状抽取） | 缺口 | 缺口率 |
|---|---|---|---|---|
| M1 淮安主件 | ≈159 | 28 | 131 | 82% |
| M2 上海松江 | ≈41 | 27 | 14 | 34% |
| M3 山西灵枢 | ≈76 | 28 | 48 | 63% |
| M4 联通日阅 | ≈21 | 18 | 3 | 14% |
| M5 北京水利示范 | ≈152 | 39 | 113 | 74% |
| M6 医养结合 | ≈14 | 1 | 13 | 93% |
| S1 合成件 | ≈8 | 5 | 3 | 38% |

（评分项 REQ = 现状确定性抽取的「评分项」类条数——其中 M1 的 28 条
含 PDF 线性化评分表专路可达的部分与语义表行——**真表格单元格**里
的评分行没有专路。）

## 4. 缺口解读（给「解析器立项」的立项依据）

1. **真表格路径确实不经过 scoring_table.rs**（模块自述验证成立）：DOCX
   件走 `import_tender_files` 的 docx 解析栈后，评分表以真表格结构在
   块流里，专路的「N.NN 主观|客观」行锚判据在表格单元格文本上失配
   （扫描器锚对账：28 张表全部 0 行命中 PDF 锚——判据本就不该复用，
   此为形态差异证据非缺陷定罪）。
2. **缺口分布与表形态强相关**：缺口率最低的 M4（14%）= 平铺小表；
   最高的 M6（93%）= vMerge=26 的二级表头大表——**合并单元格展开**
   是立项的核心难点（vMerge 纵向合并的评审项名要下填充到细则行）。
3. **M5 示范文本 13 张表都是评分相关形态**——平铺多、合并少，适合做
   立项后的第一优先验收件（结构简单、分值格密集）。
4. 现有抽取对 7 件都**非零产出**（最低 1 条）——即 docx 解析栈把表格
   内容流转成了某种 REQ，但评分行的结构化（评审项名/分值/细则切分）
   未发生。立项时不从零开始，从「表格块 → 结构化行」的装配面开始。

## 5. 立项建议（凭本对账数据——新 issue 事宜归用户/Lead 裁决）

- 优先序：M5（平铺形态起步）→ M4（小合并）→ M2/M3（二级表头）→
  M1/M6（重度 vMerge 大表——下填充 + 跨页）；
- 验收基线：本文件 §3 的缺口列为「修复前基线」——立项 PR 应附重跑
  对照（评分项 REQ ↑ 且与数据行的差收敛到表头/说明行的合理残余）；
- 验收口径注意：数据行真值含表头/说明行（如「评分细则」标题行、
  备注行）——立项时需人工核每件的可抽取行真值（对齐松岭
  run-notes.md D1 的复核纪律），不能拿本表数据行直接当金标准。

## 6. 素材登记清单（复现）

```bash
python3 scripts/scan_docx_scoring_tables.py          # 重扫（stdout JSON）
cd bidcore && cargo test -p bid-mcp --test docx_scoring_materials -- --nocapture
# ↑ 现状缺口实测（§3 数据源；每件独立工作区真跑）
```

BLOCKED 登记：无（素材在位、可对账、可复验——外采真表格政采 DOCX 的
需求不存在阻塞）。解析器立项另开 issue（凭本对账数据）。
