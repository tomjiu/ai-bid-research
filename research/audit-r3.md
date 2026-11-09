# R3 独立审计报告 —— M1.5 安全加固 + P1 四案例 Rust 化 + P2 真实文件评测

- 审计轮次：R3（继 R1 夹具规格审计 / R2 代码审计之后的第三轮独立审计）
- 审计日期：2026-10-25
- 审计对象：commit `a485a7b`（M1.5+P1）、`6a392d5`（P2）、`f1f65af`（P3，范围外顺带核对）
- 审计方法：源码逐行 + 依赖源码核对（zip 4.6.1 / quick-xml 0.37.5 / calamine 0.28 registry 源码）+ 攻击样本实证（/tmp 独立 crate 依赖 bid-parse 真跑）+ 全量回归（cargo 47 测试 / run_tests 37 项 / xref 0 错误）
- 纪律：只审计不修改业务代码；攻击样本与复现脚本全部置于 /tmp（audit_r3 项目：`/tmp/audit_r3/src/main.rs`），仓库零污染（git status 干净）

---

## 0. 结论速览

| 级别 | 计数 | 摘要 |
|---|---|---|
| **S1 严重防护失效** | **1** | MAX_OCR_PAGES=200 门在其唯一适用分支内数学上不可触发（死门），实证绕过 |
| **S2 应修** | **4** | 孙进程持管道致 run_limited 超时合同失效且晚归 Success；TmpGuard 非唯一目录（并发/残留污染）；评测"分类召回"表未校验 REQ 类别（7/18 错类未披露）；runner ParseStatus::Failed 禁引纪律为死代码且与 guard 文档承诺不符 |
| **S3 建议** | **5** | zip64 绕过 EOCD 守恒门（实证）；PDF 族无输入字节门；calamine declared=0 残余面（已登记，确认真实）；引用支持率判据弱于其名（page_delta 未消费）；编号条款通道不做否决词判定（GT-V03 高风险否决落"其他"） |
| **M 中等** | **2** | Rust C3"零悬空"断言恒真（空转）；Rust C2 外部修改测试为 setter 回环（检测路径未覆盖） |
| **P2 轻微** | **6** | worklog/威胁模型测试计数失真（51≠47 等）；C1 漏 model_v2 断言+try_accept 与 addendum_spec 耦合；无扩展名文件名撞归档扩展名误拒；stderr 截断可致子进程阻塞误判 Timeout；lossy 3×膨胀×并发内存上界未全档化；非 unix 杀树降级 + 测试锁未覆盖全部 run_limited 测试 |

全绿面（核查证据见 §5）：guard.rs 10 项 zip 负向测试全部具备真实杀伤力（逐一核对删门必红）；并发门全路径减计正确；kill(-pgid) 与 pid 回收竞态分析通过；docx 深度计数在 quick-xml 0.37 默认 check_end_names=true 下无漏计无错杀；P1-b C1/C2/C4 与 Python 语义逐条对齐（多处强于 Python）；P2 指标 75%/100% 可由脚本精确复现且 18 处命中经人工核验语义为真、页码全对齐；GT 草案 AI 初标状态在全部 4 个产物中标注在位；工程纪律（无断言删除、提交与内容一致、树干净）通过。

---

## 1. S1 —— 严重防护失效

### S1-1 MAX_OCR_PAGES=200 "OCR 页数门"是死亡之门（在其唯一适用域内恒不可触发）

**位置**：`bidcore/crates/bid-parse/src/pdf.rs:60-64`（门）＋ `pdf.rs:23-27`（pages 口径）＋ `pdf.rs:31`（has_text_layer 阈值）；常量 `guard.rs:331`。

**证据（代码推理）**：
- `pages`（pdf.rs:23-27）= pdftotext 输出按 `\f` 切分的**非空**分片数 `.max(1)`；
- 进入 OCR 分支的前提是 `has_text_layer == false`，即全文非空白字符 `non_ws < 16`（pdf.rs:31）；
- 每个非空分片至少含 1 个非空白字符 ⇒ OCR 分支内 `pages ≤ 16 < 200` **恒成立**——`if pages > MAX_OCR_PAGES` 在其唯一会被执行的分支里是数学上的死代码。纯扫描件（该门的唯一目标形态）pdftotext 只输出逐页 `\f`，`pages = 0 → max(1) = 1`，门距触发还差 199。

**证据（实证）**：构造 250 页纯空白无文本 PDF（`/tmp/audit_r3/blank250.pdf`，reportlab 生成；`pdftotext -layout` 实测：250 个 `\f`、0 个非空白字符、0 个非空分页）→ 直接调用 `bid_parse::pdf::parse`：
```
门未拒绝：渲染 PNG 已出现（31 张，且继续增长）——MAX_OCR_PAGES=200 门被绕过
```
若门生效应在渲染开始前（<1s）显式拒绝；实测 pdftoppm 开始批量渲染。真实世界的 500 页纯扫描补遗将被完整渲染 + 逐页 tesseract（每页至多 30s），"渲染/OCR 成本与磁盘占用上限"防护实际只剩 180s 渲染超时兜底，单文件可消耗数十分钟 CPU——与 threat-model.md:33/78、verification-plan §6、worklog Task 19 "OCR 页数门 200（超出整体显式拒绝——不留部分结果）" 的 IMPLEMENTED 声明直接矛盾。**这是 R2 轮"假绿"教训（声称的防护 + 无负向测试 = 未必存在的防护）的复现**：全仓无任何 MAX_OCR_PAGES 生效性负向测试（pdf.rs 仅有常量钉死测试 `governance_params_are_pinned`）。

**建议修复**：渲染前取真实页数再过门——三种等价方案任一：(a) `pdfinfo` 解析 `Pages:`；(b) `pdftoppm -l 201` 探测溢出；(c) 轻量解析 PDF `/Type /Pages` 计数。门改判后必须补一条 **>200 页纯扫描样本被整体拒绝**的负向测试（本审计的 blank250.pdf 生成方式可直接采用）。

---

## 2. S2 —— 应修

### S2-1 run_limited：直接子进程退出后 join 无界等待，超时合同失效且晚归 Success（实证）

**位置**：`bidcore/crates/bid-parse/src/guard.rs:449-471`（轮询循环 `Ok(Some(_)) => break`）＋ `guard.rs:473`（`t_out.join()` 无期限）＋ `guard.rs:431-440`（读线程阻塞至管道 EOF）。

**证据（实证，/tmp/audit_r3 hang 模式）**：`sh -c "sleep 60 & echo done"`（孙进程 sleep 60 继承并持有 stdout 管道；直接子进程 sh 即刻退出），`run_limited(cmd, timeout=1s, 4096)` 实测：
```
run_limited 返回: Success { stdout: "done\n" }
声明超时 1s，实际耗时 60.001375989s（孙进程持有 stdout 管道时 join 无界等待）
```
三重违诺：① 1s 治理超时实际挂了 60s（`timeout` 只约束轮询循环，`break` 后 join 无任何期限）；② 期间返回值最终为 **Success**——孙进程仍活着的整个窗口内调用方以为成功；③ threat-model.md:78 "孙进程不残留"不成立——子进程先退路径从不调用 `kill_process_tree`。当前三外部命令（pdftotext/pdftoppm/tesseract）不派生孙进程，日常不可触发；但治理合同本身（T-04 的存在理由）在该路径失效，且 `sh -c` 形态证明可达。

**建议修复**：`break` 后给读线程一个短宽限（如 2s）；到期仍未 EOF 则杀组再收割（注意先杀后 reap 的顺序以规避 pid 回收竞态——在 try_wait 已 reap 的前提下 `kill(-pgid)` 存在理论回收窗口，稳妥实现是 `libc::waitpid(WNOWAIT)` 探活不 reap → 杀组 → 再 reap）。同时考虑杀组后把该结果归为 `Timeout` 而非 Success（"孙进程滞留"应视为治理失败）。

### S2-2 TmpGuard 目录名仅 `tag+pid`，非调用级唯一：并发交叉污染 + 崩溃残留复用

**位置**：`guard.rs:493-505`（`TmpGuard::new` = `temp/bidparse_{tag}_{pid}`）；消费点 `pdf.rs:67,78-84`。

**证据（推理+旁证）**：
- **进程内并发**：T-04 并发门 `MAX_CONCURRENT_SUBPROCS=4` 明示并发解析在支持面内；两线程同时解析两个扫描件 PDF → 同一 `/tmp/bidparse_ocr_<pid>` → pdftoppm 双方都写 `page-001.png`，A 文件 OCR 前被 B 文件覆盖 → **静默交叉污染（错结果，比崩溃更糟）**。当前 runner/real_eval 串行故未触发，属设计内必踩的雷。
- **跨进程残留**：本审计的 ocrgate 测试以 `process::exit` 退出（不 unwind）→ TmpGuard Drop 未运行 → `/tmp/bidparse_ocr_21886`（page-001.png…）实际残留，已人工清理。SIGKILL/崩溃同理；pid 回收后同 pid 进程 `create_dir_all` 复用旧目录 → 陈旧 PNG 混入 `read_dir` 清单（pdf.rs:78-84 无新旧过滤），页数与 OCR 内容均可能掺入上一次运行的残片。
- panic 路径：unwind 会跑 Drop，能回收（prompt 关切点的答案是"能"）；但 exit/kill 不能。

**建议修复**：`TmpGuard::new` 目录名追加原子递增序号或纳秒时间戳（或直接换 `tempfile` crate）；`pdf.rs` 渲染前先建目录再列目录改为"渲染前后快照差集"，双保险。

### S2-3 real_eval_score.py 分类召回表不做 REQ 类别校验：7/18 命中错类未披露（含 2 条否决 GT）

**位置**：`scripts/real_eval_score.py:63-99`（命中判定仅文本，无 REQ `category` 参与）、`:104-110`（`by_category` 按 **GT** 类别分组）；呈现点 `artifacts/real-eval/REPORT.md:24`。

**证据（实测）**：复算 18 条命中的 REQ 类别与 GT 类别的一致性：
```
CATEGORY-MISMATCH GT-R01 GT_cat=资格条件   REQ_cats=['其他']
CATEGORY-MISMATCH GT-V03 GT_cat=否决项     REQ_cats=['其他']     ← 高风险否决条款落"其他"
CATEGORY-MISMATCH GT-V05 GT_cat=否决项     REQ_cats=['资格条件']
CATEGORY-MISMATCH GT-B01 GT_cat=商务要求   REQ_cats=['其他']
CATEGORY-MISMATCH GT-B02 GT_cat=商务要求   REQ_cats=['其他']
CATEGORY-MISMATCH GT-B03 GT_cat=商务要求   REQ_cats=['其他']
CATEGORY-MISMATCH GT-B04 GT_cat=商务要求   REQ_cats=['其他','否决项']
```
且 `real-eval-report.json` 的 `by_category` 显示全量 REQ 中 **"商务要求"类为 0 条**——"分类召回：…商务要求 4/4"在读者眼中是"4 条商务要求被正确识别"，实际是"4 条商务要求 GT 的文本在'其他'类 REQ 里被找到"。GT-V03（"不按 3.4.1 提交保证金→其投标将被否决"，废标级风险）在产品输出中是 `clause=3.4.2, category=其他`——下游合规矩阵按否决类别设防时不会覆盖它。REPORT §3/§5 虽诚实登记了"84% 落其他"，但未披露这 7 处错类命中。

**建议修复**：score 脚本增加 `category_match` 字段与"类别一致召回"次级指标；REPORT 表改名为"按 GT 类别分组召回"并披露 7/18 错类明细（GT-V03/V05 单列——直接关联废标风险）。

### S2-4 runner.rs "解析失败禁引"为死代码，guard.rs 文档承诺的 Failed 落库纪律不存在

**位置**：`bidcore/crates/bid-tools/src/runner.rs:61-67`（`status` 由 `has_text` 只能取 Ok|OcrRequired，`if status == ParseStatus::Failed` 恒假）＋ `runner.rs:55`（`parse_file(...)?` 整批中止）；文档承诺 `guard.rs:14-16`（"runner 侧落 ParseStatus::Failed + E_UNPROCESSABLE 禁引纪律，R-01"）。

**证据**：`parse_file` 失败一律 `Err` → `import_files` 用 `?` 上抛 → **整个场景中止**；不存在"单件失败 → 记 Failed → 禁引 → 继续导其余文件"的路径。M1.5 后真实用户文件接入场景（含 guard 拒绝面）下，一批招标文件里一个损坏件将阻塞全部导入，且威胁模型声称的禁引纪律在 runner 层无实现。`ParseStatus::Failed` 枚举值在全部代码路径中从未被赋值（`db.totals.parse_failed` 恒 0）。

**建议修复**：import 循环 per-file catch：Err → trace 记 `E_UNPROCESSABLE` + `ParseStatus::Failed` + continue；与 guard.rs 模块文档对齐（或在 guard.rs 文档改为如实描述"解析失败整批中止"——二选一，不能维持现状的文档-代码错位）。

---

## 3. S3 —— 建议

### S3-1 zip64 归档绕过 EOCD 条目守恒门（实证；现势影响低，防线自述失真）

**位置**：`guard.rs:247-257`（`declared == 0xFFFF` 即跳过守恒比对）、`:264-287`（EOCD 尾扫）。

**证据（实证，/tmp/audit_r3 zip64 模式）**：手工构造合法 zip64 归档（zip64 EOCD 声明 2 条，中央目录含 2 条同名 `word/document.xml`——python zipfile 校验结构合法）：
```
zip64 双条目归档 open_guarded → Ok(1)          ← 守恒门被 0xFFFF 跳过，重复条目静默吸收
非 zip64 对照 open_guarded   → Err("中央目录条目数不守恒：声明 2 ≠ 实际 1（重复条目吸收面拒绝）")
```
与 guard.rs:71-73/110 自述"吸收面封死"矛盾。**现势影响评估为低**：已核对 zip 4.6.1 源码（`read.rs:69-79` `Shared.files: IndexMap` 按名吸收、后写覆盖）——prescan(by_index) 与 read(by_name) 读到的是**同一个**（最后一条）重复条目，无"查 A 读 B"影子文件缝隙；calamine 0.28 亦依赖同一 zip 4.6.1（Cargo.lock 单版本），读写语义一致。但该一致性建立在 crate 未升级的前提上，属"一次依赖升级之外"的防线。
**建议修复**：`declared == 0xFFFF` 时解析 zip64 EOCD 记录（尾扫 `PK\x06\x06`）取其真实 count 再比对；用本审计的 dup_zip64 生成逻辑固化为负向测试。

### S3-2 PDF 族无输入字节门（docx 52MB/xlsx 302MB 有门，PDF 任意大）

**位置**：`lib.rs:73-97`（parse_file 按 ext 分发，无 size 检查）＋ `pdf.rs:17`（parse 直接起子进程）。
**证据**：`guard::check_input_size` 仅由 docx/xlsx 的 `open_guarded` 消费；10GB 或构造型 PDF 直接进 pdftotext（poppler 内部分配不受本仓治理，60s 超时前内存面无界——poppler 历史上有构造文件 OOM 的 CVE 类）。
**建议修复**：`parse_file` pdf 分支加 `LIMIT_INPUT_BYTES_PDF`（对齐部署现实，如 512MB）过 `check_input_size`——一行成本闭环。

### S3-3 xlsx "声明 0 字节"绕过 prescan 比例/体量门 → calamine 黑盒解压（已登记残余，确认真实）

**位置**：`guard.rs:168-174`（`declared > 0` 才判压缩比；0 声明跳过单条目门）＋ `xlsx.rs:3-5`（残余面自述）。
**证据**：prescan 中 declared=0 的条目不计入 total/比例门；实际数据可任意大；xlsx 路径读数据在 calamine 内部完成，`read_entry_limited` 真防线不可达。threat-model.md:77 已诚实登记该残余（"威胁极低：需构造声明值异常的畸形 zip"）——本审计确认登记属实、无需改文档，但建议 M2 排期一个可实施的缓解（如 calamine 后置行/单元格数上限拒绝，或 xlsx 读面改走 zip crate 流式自读）。

### S3-4 "引用支持率"判据弱于其名：任意页子串 + page_delta 只算不用

**位置**：`real_eval_score.py:80-89`（`supported = any(core in p for p in pages_n2)`，全文任意页命中即真；`page_delta` 计算后不参与判定）。
**证据**：对文本层 REQ，excerpt 本就是从同一份 pdftotext 输出截取的行，归一化子串回查近乎恒真（仅 OCR 通道是真检验）；且不校验锚点页与原文页一致。**实测后果良好**：18 条命中 page_delta 全部为 0（仅 GT-S02 为 -1，跨页拆行），所以"100%（18/18）"结论实质性成立——但成立靠数据不靠判据。
**建议修复**：`supported` 增加"excerpt 归一串出现在锚点 locator 声明的页（±1）"约束，或报告页偏差分布——把指标从"可回查"升级为"回查对得上"。

### S3-5 extract_main_pdf 编号条款通道不做否决词判定，高风险否决条款落"其他"

**位置**：`extract.rs:112-123`（re_clause 命中分支：`re_qual` 优先，无 `re_veto` 检查；否决通道仅在无编号 else 分支 `:124-126`）。
**证据**：真实评测 GT-V03（"3.4.2 …其投标将被否决"）实测产出 `category=其他`；与 extract.rs:49-53 自述的"风险不对称：漏否决=废标风险>误报可过滤"纪律直接冲突——恰恰是最高危形态（编号否决条款）被排除在否决词通道外。
**建议修复**：re_clause 分支内 `re_veto.is_match(t)` 时直接判"否决项"（优先于 re_qual），一行改动 + 用 04 号文件回归 GT-V03。

---

## 4. M / P2 —— 中等与轻微

**M-1 Rust C3"零悬空"断言恒真（vacuous）**：`four_contracts.rs:244-247` 断言 `ledger.status_of(c).is_some()`——`LinkageLedger::new`（linkage.rs:42-47）注册后 status 表从不删键，该断言不可能失败；Python Q1 的对位断言是真实书签图等价校验（v3_integration.py:147）。建议：给 LinkageLedger 增加"定位器解析"接口（paragraph_index < 当前指纹长度等）或删去该断言、在文件头注明零悬空证据保留在 SEMUL 侧。

**M-2 Rust C2 外部修改测试为 setter 回环**：`four_contracts.rs:195-209` 调 `detect_external_change`（linkage.rs:95-101，无条件置 Stale）后断言刚设置的值——检测路径（refresh 指纹比对）未被"外部修改"案例覆盖；Python Q2b（v3_integration.py:184-194）走的是真实 refresh 检测。建议：C2 改经 refresh 路径构造外部修改（指纹向量换新值）后断言 degraded==["GT-01"]。

**P2-1 计数失真三处**：worklog Task 19 "cargo 全 workspace 51 测试全绿"——实测 47（`cargo test --workspace -- --list` 逐条清点）；threat-model.md:32 "T-03 11 测试"（guard.rs T-03 面 10 项）、`:33/78` "T-04 9 项/8 测试"（实测 8 项）；REPORT.md:14 "20.3s" vs real-eval-report.json 19.85s（旧轮运行残留数字）。建议回填时统一为实测值。

**P2-2 P1-b 两处弱化**：① `four_contracts.rs:54-56` 仅断言 `current_model`，Python R0 断言的 `model_v2` 参数未验（impact.rs:257 两条都写入了，补断言成本一行）；② `impact.rs:337-359` try_accept 的冲突 GT 集取自**最近一次** addendum_spec 而非 conflict 记录自带关联——corpus-A 等价，多补遗场景语义会漂（Python 硬编码 GT-21/08，两者目前同构）。

**P2-3 无扩展名文件名撞归档扩展名误拒**：`guard.rs:209-211` `rsplit('.').next()` 对无点名字返回整名——名为 `zip`/`gz`/`tar`/`7z` 的无扩展名条目（含目录条目）被误判嵌套归档。建议 `name.rsplit_once('.')` 且首段非空才判扩展名。

**P2-4 stderr 64KB 截停可阻塞子进程**：`guard.rs:441-446`（`take(LIMIT_SUBPROC_STDERR+1)` 读满即弃）——子进程 stderr 超 64KB+1 后写管道永久阻塞 → 只能等超时被杀、误判 Timeout（fail-closed，不安全但失真）。建议读线程持续 drain 只保留头部 64KB。

**P2-5 lossy 3× 膨胀 × 并发的内存上界未全档化**：`guard.rs:484-485` Success 路径 `from_utf8_lossy(≤64MB stdout)` 瞬时可 3×（192MB）×4 并发 ≈ 0.75GB+；`guard.rs:66-68` 只为 read_entry_limited 档了此账。建议 run_limited 注释补同款上界说明（或改 `from_utf8_lossy` 前先校验 UTF-8）。

**P2-6 杂项**：① `guard.rs:393-396` 非 unix 杀树降级为只杀直接子（Windows 部署下孙进程漏杀）——Linux 部署可接受，建议文档标注；② `guard.rs:741` SUBPROC_TEST_LOCK 只罩了 4/7 个 run_limited 测试，busy_gate 满席窗口与未上锁的 success/nonzero/spawn 测试存在理论竞态（6 次压测稳定，未红）——建议锁扩到全部 run_limited 测试；③ pdf.rs:103-115 单页 OCR NonZeroExit → break 保留部分 OCR 结果（parse_summary 说明"OCR 失败"）——与 T-03"不留部分结果"措辞的边界值得在文档注明（数据面降级 vs 治理面拒绝，现注释已自洽，仅提示 REPORT 阅读一致性）。

---

## 5. 各维度核查证据（全绿面）

**A. T-03/T-04 防护完备性**
- **负向测试杀伤力逐一核对**（"删门必红"推演）：zip_bomb↔压缩比门、flood↔条目数门、traversal五形态↔名字门、dup↔守恒门、nested↔载具门、big↔输入字节门、lying↔实际读取门——七门各有一对一红证，**无假防护测试**（S1 例外是"有声称无门"而非"有测试无门"）。8 项 T-04 测试同法核对（timeout/overflow/nonzero/busy/spawn/never-lies/tmpguard 均有真实杀伤力）。
- **并发门全路径减计**：acquire 回滚（guard.rs:370-373）、RAII Drop（378-382）、Overflow/Timeout/Err 早退路径、Spawn 失败显式 drop（419）——逐一核对无泄漏。
- **kill(-pgid) pid 回收竞态**：杀组仅发生在 try_wait 返回 None（子进程未 reap，pid 处于占用/僵尸态不可回收）时——窗口分析安全；S2-1 是"该杀不杀"而非"杀错对象"。
- **docx 深度计数 Start/End 不配对问题**：实测 quick-xml 0.37.5 `Config::default().check_end_names == true` 且 `allow_unmatched_ends == false`（registry 源码 `reader/mod.rs:210-222`）——错配 End 直接 Err 整体拒绝，深度计数器无法被恶意错配下压；Empty 事件不计数正确；递减先于 match 处理了 `continue` 路径（docx.rs:102-103）。**无漏计、无错杀**。
- **EOCD 尾扫与 zip crate 扫描方向一致性**：zip 4.6.1 `find_central_directory` 用 `MagicFinder<Backwards>`（spec.rs:613），guard 同为尾向前扫取最后签名——无假 EOCD 失步面；伪 0xFFFF 无 zip64 记录会被 crate 按 65535 头读取失败拒开（实测 dup_zip64 构造过程中的中间态）。
- **攻击样本**：blank250.pdf（死门实证）、`sh -c "sleep 60 & echo done"`（挂起实证）、dup_zip64/dup_zip32.docx（守恒门绕过实证）——全在 /tmp，未入仓。

**B. P1-b 语义对齐（four_contracts × v2_impact/v3_integration 逐条）**
- C1 四测 ↔ Python R1/R2/R3/R4/R5/R6 逐条对照：DIRTY 恰三章节、GT-18 v2、CONFLICT-01 双版本未裁决、version 恰 +1、GT-02 翻转+not_eligible、GT-13 维持 EXPIRED+细项 0 分、GT-01/05/06 零误翻、recheck_log 两轮、NOT DIRTY 恰三章、脏/冲突双阻断、终裁 465+双 GT 口径（Rust 侧比 Python 多断言了 GT-08 的 caliber）、幂等同 sha+脏集不变（Rust 多断言脏集）——**多数强于 Python，仅 M-1/M-2/P2-2 三处弱化**（见上）。
- C4 ↔ Python Q3 全对齐且多出 ProjectStatus 终态/唯一入边断言（four_contracts.rs:298-309）。
- corpus_a() 硬编码值 vs fixture_spec：抽查 SECTIONS_SPEC 六章节/related 列与 Python R3 判定一致性——`项目团队`related=[GT-15] 等不影响 DIRTY 判定的子集口径自洽（xref_check 0 错误背书）。

**C. P2 评测诚实性**
- **指标复现**：`python3 scripts/real_eval_score.py` 重跑 → "召回 18（75.0%）| 引用支持 18/18（100.0%）"，与 REPORT.md §2 逐位一致；分类分布（否决 7/7·商务 4/4·资格 5/6·评分 2/5·技术 0/2）与 score-report.json 一致；解析面数字（8107/3525/2272 行块、OCR 100 块、zip 显式拒绝）与 real-eval-report.json 一致。
- **GT 初标状态**：ground-truth-draft.json 头部 `ground_truth_status` + REPORT.md 头部 + score-report.json `gt_status` + real-eval-report.json `ground_truth_status` 四处齐备——**AI 初标草案标注在位**。
- **对齐算法过拟合评估**：结构上确有松面（12 字符滑窗、双向前缀互含、无一对一消费），但**逐一人工复核 18 条命中的最弱证据**——每条命中 REQ 的 excerpt 均为 GT 条款本体或其跨行拼接（如 GT-V04 续行窗拼回"共资源交易平台…"），page_delta 17/18 为 0、1/18 为 -1——**75% 未被虚报**；风险面已列 S2-3/S3-4（类别盲区与判据弱化）。

**D. 工程纪律**
- `cargo test --workspace`：47/47 全绿（e2e_m1 OCR 真跑 30s）；guard 压测 6 轮稳定。
- `run_tests.py` 37/37 全绿；`xref_check.py` 0 错误（8 项 C7 断言谓词告警为历史存量，非本轮引入）。
- git 三提交 diff 逐一核对：M1.5/P1/P2 全为增量改动，**无误删既有断言**（pdf.rs 旧 `run()` 无超时实现被治理版整体替换属功能升级；docx/lib/xlsx 测试全保留）；提交信息与 stat 内容相符；工作树干净。
- worklog/威胁模型计数失真已列 P2-1（不构成漂绿，属记录精度）。

---

## 6. 处置建议优先序

1. **S1-1**（补真实页数门 + 负向测试）——真实用户文件接入前的安全前置承诺，必须先兑现。
2. **S2-1 / S2-2**（join 期限 + TmpGuard 唯一化）——各约 ≤20 行；与 S1-1 同批过 cargo 回归。
3. **S2-3 / S2-4**（评测类别披露 + runner 禁引纪律落地）——文档-代码一致性收口。
4. **S3-1**（zip64 守恒）——负向测试样本本报告已给出生成逻辑，随批固化。
5. **S3-2/S3-5**（PDF 字节门一行；编号否决一行）——低成本高价值。
6. M/P2 项可随下轮整理批处理；S3-3 维持威胁模型登记、M2 排期缓解。

*审计人：R3 独立安全与质量审计代理（只审计未修改业务代码；复现脚本与攻击样本留存 /tmp/audit_r3，仓库零污染）。*
