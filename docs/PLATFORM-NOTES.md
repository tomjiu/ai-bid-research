# 平台支持说明（Windows / Linux）

> 适用版本 ≥ 0.2.0。本文档是跨平台行为的**唯一权威**口径，对应实现面
> `src/platform.py` / `src/locking.py` / `src/storage/pragmas.py` / `src/colors.py`。
> 最后更新：2026-11-10（#601 R73）。

研究 CLI 在 Linux（CI/研究机）与 Windows（业务机）双平台一等公民支持。
两平台行为差异全部收敛在下列已实现面——**没有**需要用户记忆的隐藏坑。

---

## 1. 控制台输出

| 面 | Linux | Windows |
| --- | --- | --- |
| 缺省编码 | UTF-8（locale 回退 UTF-8 模式） | 代码页（chcp）：936/GBK、65001/UTF-8 |
| 中文/制表符打印 | 直接可用 | GBK 覆盖常用汉字与 `█▏│`（A880/A9A6）；`ascii` 代码页自动降级 `errors=replace`（坏字符变 `?`，**绝不崩溃**，R40） |
| ANSI 颜色 | 终端可用；`NO_COLOR=1` 关闭 | Win10 1511+ 自动开 VT 模式（ctypes）；Windows Terminal 原生；旧控制台自动关色（R65） |
| 进度条 | tty 行内刷新；管道静默 | 同左（行为一致，R68） |

推荐：Windows 上 `chcp 65001` 或使用 Windows Terminal 获得最佳体验。

## 2. 路径与文件名

- **长度上限**：写盘前按平台校验（Windows MAX_PATH=260 / Linux PATH_MAX=4096），
  超限报**可行动错误**（缩短 `--output-dir` / 启用注册表 `LongPathsEnabled` /
  缩短关键词），而非误导性 `FileNotFoundError`（R44）。
- **大小写**：Windows 大小写不敏感卷上递归源的路径键折叠（`Data/` 与 `data/`
  只读一次）；Linux 保持敏感（R43/R39）。
- **非法文件名**：报告文件名统一清洗——`<>:"/\|?*` 与控制字符替换、
  Windows 保留设备名（`CON`/`NUL`/`COM1`…）加尾 `_`、尾点尾空格剥离（R46）。
- **符号链接环**：`--recursive` 目录遍历内置环防护（R43）。

## 3. 行尾与字节契约

所有产物（报告 `.md` / `.html` / JSON / JSONL）**统一 LF 行尾、UTF-8**——
同一命令在两平台产出**字节一致**（golden 对比/diff 无噪音，R45）。
例外：`db export csv` 落盘用 `utf-8-sig`（BOM）——Excel 双击直开不乱码
（R34 口径不变）。

## 4. 数据库（SQLite）

- **WAL 自动探测-回退**：本地卷启用 WAL（写不堵读，`synchronous=NORMAL`）；
  Windows 网络盘（SMB）/旧 FAT 切不上时**如实回报** `journal_mode=delete`，
  不静默谎报并发能力（R42）。
- **进程互斥**：`src/locking.py` 文件锁——Linux `fcntl.flock` / Windows
  `msvcrt.locking`，语义一致（非阻塞抢占 + 轮询 + 超时 `LockTimeoutError`，R41）。
- **在线备份**：`db --backup FILE` 走 SQLite backup API——比拷贝 `.db`
  文件多保住 `-wal` 未 checkpoint 内容（R71）。
- **schema 迁移**：`PRAGMA user_version` 逐级自动升级（v3 = 断点续跑
  `extract_status` 列；旧库打开即迁，R56/R58）。

## 5. 并发与长任务

- 批量写**单事务**：万条级导入从万次 fsync 降为一次（Windows 本地盘与
  网络盘收益最显著），任一行失败整批回滚（R62）。
- `pipeline --resume` 断点续跑：崩溃后参数自动恢复（source/keyword/days），
  崩溃残留（`raw` 记录）重新补抽，pending 挂账自动清账（R58）。
- LLM 重试纪律：确定性 4xx（401/404）立即放弃；429 尊重 `Retry-After`；
  等抖动指数退避（防惊群）封顶 30s（R59）。

## 6. 冒烟自检

```bash
# Linux / macOS / WSL / Git Bash
bash scripts/smoke-linux.sh            # 或指定解释器：bash scripts/smoke-linux.sh python3.12
```

```powershell
# Windows（PowerShell 5.1+；脚本带 UTF-8 BOM）
powershell -ExecutionPolicy Bypass -File scripts\smoke-windows.ps1
```

两脚本步序对齐（版本 → collect → db --status → analyze → export → 产物断言），
结尾打 `SMOKE OK` 即全链健康。改动其一须同步另一处（测试锁定，R67）。

## 7. 退出码

见 `docs/USER-GUIDE.md` 退出码一节（`src/exit_codes.py` 唯一权威）：
`0` 成功（含容忍降级）/ `1` 无子命令 / `2` 用法或数据环境错误 / `3` LLM 运行时失败（R70）。

## 8. 已知平台差异（不修——如实记录）

| 差异 | 原因 | 影响 |
| --- | --- | --- |
| Windows 文件锁按字节区间，POSIX 按文件 | OS 语义 | 单写者用途下等价（锁文件无数据） |
| WAL 在 Windows 网络盘不可用 | SMB 无共享内存 | 自动回退 delete 模式（R42 探测面） |
| `utf-8-sig` CSV 仅 Windows Excel 需要 | Excel BOM 依赖 | Linux 上 `read_text(utf-8-sig)` 同样可读（BOM 容忍） |
| msvcrt 锁在 Jupyter 内嵌 IO 下不可用 | 控制台 API 限制 | `LockTimeoutError` 超时路径兜底（R41） |
