# #601 公告数据链路——R39-R76 迭代总结

> 会话：2026-11-10（平台迁移 git.mingjiu.store 后第二轮长跑）
> 基线：R38（feat/601-iterate @ c5a756d，389 测试）
> 收官：R76（689 测试全绿 + pyflakes 归零 + 冒烟通过）
> 分支：`feat/601-iterate`（本会话 38 轮提交）

## 批次总览

| 批次 | 轮次 | 主题 | 测试增量 |
| --- | --- | --- | --- |
| G | R39-R46 | **平台兼容专项**（linux/win 区分） | 389 → 452 |
| H | R47-R54 | **分析深化**（画像/离群/共现/层级/环比） | 452 → 509 |
| I | R55-R62 | **链路健壮性**（流式/事务/续跑/优先级） | 509 → 567 |
| J | R63-R70 | **可用性**（TOC/图表/颜色/版本/冒烟/退出码） | 567 → 644 |
| K | R71-R76 | **收尾质量**（备份/日志/文档/卫生/压力） | 644 → 689 |

## 逐轮明细

### 批 G：平台兼容（用户点名的 linux/win 区分）

- **R39** `src/platform.py` 平台检测工具面——`is_windows/linux/macos` 纯函数
  + 路径长度上限（Win 260 / Linux 4096）+ 大小写敏感性启发式 + 控制台
  编码安全探测；测试经 monkeypatch `sys.platform` 双平台分支全覆盖。
- **R40** 控制台输出加固——GBK/ascii 代码页 `reconfigure(errors=replace)`
  就地降级（坏字符变 `?` 不崩溃），`main()` 入口先于一切输出接线。
- **R41** 跨平台文件锁 `src/locking.py`——Linux `fcntl.flock` / Windows
  `msvcrt.locking` 双实现，超时语义统一（`LockTimeoutError` 带路径），
  Windows 分支以注入 msvcrt 替身在 Linux 全测。
- **R42** SQLite PRAGMA 探测-回退——WAL 生效走 `synchronous=NORMAL`，
  网络盘/旧 FAT 切不上如实回报 `delete`+FULL，绝不谎报并发能力。
- **R43** 递归目录源 `--recursive`——`os.walk` + 路径键去重（符号链接环
  防护；Windows 大小写折叠 `Data/`=`data/`，Linux 保持敏感）。
- **R44** Windows 长路径防护——写盘前 MAX_PATH 校验，超限报**可行动**
  三建议（缩短目录/LongPathsEnabled/短词），根除误导性
  `FileNotFoundError`。
- **R45** 输出行尾 LF 钉死——报告/HTML/JSON 产物跨平台**字节一致**
  （`write_text_lf` 显式 `newline="\n"`）+ CRLF 读取归一面。
- **R46** 文件名清洗升级——Windows 保留设备名（CON/NUL/COM1…）加尾
  `_`、尾点空格**原文层**剥离、控制字符/空白折叠（处理顺序经过两轮
  修正锁定）。

### 批 H：分析深化

- **R47/R48** 供应商画像 + 报告十二节——winner 侧聚合（中标数/预算有值
  样本/买方去重/活跃月），未定标不猜数；密度节匿名契约与画像节点名
  契约并存（同报告两语义互不侵扰）。
- **R49** 预算离群 IQR 标记——Q1/Q3/中位锚点 + 高低价双向围栏（下界
  非负）+ 报告十三节；样本 <5 诚实跳过。
- **R50** 领域词共现——同项目词对结伴计数（匹配面同 keywords 口径），
  孤例（<2 次）过滤；「共现 ≠ 因果」警示入节。
- **R51** 省级归一分布——34 省级行政区全/简称解析（浙江省=浙江=浙？否，
  短名表显式生成）、直辖市折叠、裸市名不猜数；报告十五节。
- **R52** 滑动窗口环比——近 N 月 vs 再前 N 月三指标（项目数/预算均值/
  定标数）对照表嵌入三节；月份不足 2×窗口诚实跳过。
- **R53** 重复合作关系——采购人×供应商 ≥2 次聚合（预算样本分账/月份
  序列），「信号非认定」警示；十二节内子表。
- **R54** `analyze --json`——完整 payload 机器可读导出（LF/长路径防护/
  platform 契约复用；`-` = stdout）。

### 批 I：链路健壮性

- **R55** CSV 流式读取——`csv.reader` 逐行喂入（内存与文件尺寸解耦），
  多行单元格标准语义升级，`max_rows` 防失控，解码错误文件级口径保留。
- **R56** schema 版本框架——`PRAGMA user_version` 迁移钩子 + `db
  --status`（版本/表行数/PRAGMA）。
- **R57** 导入导出往返契约——JSON 路（`db --import`）与 CSV 路
  （collect 归一）双链等价锁定（BOM/特殊字符/空字段覆盖）。
- **R58** pipeline 断点续跑——v3 迁移 `extract_status` 列 + `--resume`
  （崩溃参数恢复/降级残留补抽）+ store 单点闭环（extracted 标记 +
  pending 自动清账）；两形态残留（崩溃/降级）都有专属测试路径。
- **R59** LLM 重试退避纪律——确定性 4xx 立即放弃、429 尊重 Retry-After、
  等抖动（`delay/2 + U(0, delay/2)`）防惊群、30s 封顶、`max_retries=0`
  语义修正（原 `or` 吞 0）。
- **R60** 研究快照 diff——`db --diff OLD NEW`（bid_id 锚定/字段级明细/
  形态归一防伪变更）+ `--out` 机器可读。
- **R61** pending 队列优先级——重试价值序（llm_error 先于 rejected /
  hit_rate 降序 NULL 末），`retry_pending` 有限预算优先消费；
  `park_raw_failure` 补 hit_rate 参数（真实 API 缺口）。
- **R62** 批量写事务——`import_bids` 原子化（万条万次 fsync→一次）+
  pipeline collect 消 N+1（单查询身份预取）；异常整批回滚（首版漏
  rollback 的 bug 由测试抓出修正）。

### 批 J：可用性

- **R63** 报告目录 TOC——h2/h3 锚点（中文 slug/代码块防护），标题块后
  注入；HTML 导出兼容。
- **R64** ASCII 条形图——`ascii_bar/render_bars`（比例填充/零占位/对齐）
  + 控制台编码自适应（**GBK 含块区原样用 █**——实测 A880 后修正了
  「GBK 需降级」的错误预设；ascii 降 `#`）+ analyze 区域 Top5。
- **R65** ANSI 颜色——NO_COLOR 规范最高优先 / 非 tty 关色 / Windows
  VT ctypes 使能（WT_SESSION 直通）+ `ColorPrinter` + stderr 错误路径。
- **R66** `--version`——语义化版本 + Python/平台环境横幅（报障定位面）。
- **R67** 双平台冒烟脚本——`smoke-linux.sh`（实测通过）+ `smoke-windows.ps1`
  （UTF-8 BOM/严格模式/路径反斜杠归一），步序对齐契约测试锁定。
- **R68** 批抽取进度——`ProgressPrinter`（tty 行内刷新/非 tty 静默 +
  DEBUG 四分位）+ `extract_batch` 回调（展示层异常隔离）。
- **R69** `templates --show NAME`——脱敏样例渲染真实提示词全貌。
- **R70** 退出码规范——`src/exit_codes.py` 唯一权威（**按实测锚定**：
  argparse 用法错误=2 与数据错误同码的历史现实如实入档）+ 23 处裸 2
  改常量 + USER-GUIDE 表 + 帮助尾注。

### 批 K：收尾质量

- **R71** db 在线备份——SQLite backup API（WAL 未 checkpoint 内容不丢，
  与拷 .db 文件的差异被测试证明）+ 幽灵库不静默建库。
- **R72** `--log-file` 双通道日志——文件 DEBUG/控制台 INFO；**修真缺陷**：
  `basicConfig` 在预置 handler 环境（pytest/嵌入宿主）是空操作吞 INFO，
  改显式 `setLevel`。
- **R73** `docs/PLATFORM-NOTES.md`——八节平台权威口径 + 文档-实现契约
  测试（12 主题标记防漂移）。
- **R74** 全仓静态卫生——pyflakes 归零（31 处未用导入/变量/f 前缀）；
  **修真 bug**：`main.py` 两处 `Dict` 未导入（运行时 NameError）。
- **R75** 数据量压力 e2e——2000 条/嵌套月目录/2% 坏行：递归采集 0.1s、
  全分析 0.2s、快照自比较零差异。
- **R76** USER-GUIDE 功能速查——链路命令/全局参数/报告节序/内建可靠
  性面/自检五节 + 契约测试。

## 本会话抓出的真 bug（测试驱动发现）

| # | bug | 发现轮 | 修复轮 |
| --- | --- | --- | --- |
| 1 | `console_encoding_safe` 空编码语义不一致 | R40 | R40 |
| 2 | 文件名清洗顺序缺陷（rstrip 时机/范围两轮） | R46 | R46 |
| 3 | `normalize_path_key` POSIX 路径不折叠 | R43 | R43 |
| 4 | 事务上下文异常路径漏 rollback | R62 | R62 |
| 5 | `basicConfig` 预置 handler 环境空操作吞 INFO | R72 | R72 |
| 6 | `main.py` `Dict` 未导入（NameError×2） | R74 | R74 |
| 7 | `max_retries=0` 被 `or` 吞成默认 3 | R59 | R59 |
| 8 | `--backup` 幽灵库静默建库 | R71 | R71 |
| 9 | `park_raw_failure` 缺 hit_rate（API 缺口） | R61 | R61 |
| 10 | 「GBK 需降级块字符」错误预设（实测 A880 在 GBK 区） | R64 | R64 |

## 测试与质量口径

- 每轮 **pytest 真退出码为 0 才 commit**（R43/R46 两次教训后立规）；
- 全程 pyflakes 零告警（R74 起为不变量）；
- 冒烟脚本（Linux 实测）为每批 push 前置检查；
- 压力时界（60s）远宽于实测（0.2s）——Windows 业务机留 3 个量级余量。
