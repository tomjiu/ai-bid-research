# 平台区分专项回归清单（#47 R16 收口）

> **定位**：跨平台硬化专列（R2 / R9-R15，共 9 面）的**权威回归清单**——每面
> 的行为口径、实现真源、测试锚、平台运行面一表可查。防漂移契约：
> `web-ui/tests/platform-matrix.test.mjs` 校验本文引用的每个测试锚在源码
> 真实在场（清单与实现不脱钩）。
>
> **平台纪律**（AGENTS.md §13）：平台特定断言走 cfg 分支 + SKIP 横幅；环境
> 缺件如实报告不以未跑为通过；**跨平台守卫双平台同拒（非 cfg）**——「Linux
> 合法但拷 Windows 即坏」的形态在入口统一拒，不留平台分叉洞。

## 一、口径总则（三类平台面）

| 类 | 语义 | 判定特征 | 例 |
|---|---|---|---|
| **双平台同拒** | 非 cfg 守卫：不可跨 Windows 迁移的形态**入口即拒**（Linux 上也拒） | 纯字符串/长度判定，无 `#[cfg]` | R10 保留名、R12 MAX_PATH、R11 CI 占位 |
| **cfg 双分支对照** | 平台语义**本质分叉**的断言面：Linux/Windows 各断一面 | `#[cfg(unix)]` / `#[cfg(windows)]` 成对 | R14 反斜杠语义、R2 越界样本形态 |
| **平台启发式** | 运行时探测（文件系统/时区），双平台标准路径 | 探测函数 + 回退 | R15 时区偏移（iana-time-zone）、is_inside 组件比较 |

## 二、回归矩阵（10 面——R17 后缀白名单入列）

### ② 系列：硬化专列（R9-R15 + R17）

| # | 面 | 行为口径 | 实现真源 | 测试锚 | 平台运行面 |
|---|---|---|---|---|---|
| R9 | upload_ref 分隔符归一 | `\`→`/`；相对形态压缩空段/`.` 段；`..` 保留（域层围栏裁决）；绝对形态只换分隔符不压缩 | `mang-app/src/bid.rs` `normalize_upload_ref` | cargo `upload_ref_separator_normalized_and_idempotent`；selftest `bid.import_files(Windows 形态归一导入)` + `bid.import_files(两形态同件幂等)` | 双平台（字符串面无平台分叉） |
| R17 | 后缀白名单对齐解析面 | **双平台同拒（非 cfg）**：白名单 = 解析路由真支持面四类（docx/xlsx/pdf/doc——`.ods` 等落位必败件在壳侧拒之门外，ext_blocked 分账 + detail 指明合法四类，混拖批次不连坐）；壳/UI 两面声明同源 | `mang-app/src/bid.rs` `INGEST_DROP_EXTS`（壳单一真源）+ `web-ui/mang/app.js` `BID_IMPORT_EXTS`（同源声明） | cargo `ingest_drop_ods_blocked_as_unsupported_parse_face`；selftest `bid.ingest_drop(.ods 摘除对齐解析面)`；bid-panels R17 白名单锚 + R22 跨面等值门（壳表=UI 表双向零差） | 双平台同拒（字符串判定无 cfg——改一面不改另一面即等值门红） |
| R10 | 基名可移植守卫 | Windows 保留设备名/非法字符（含基名内 `/` `\`）/尾部点空格——**双平台同拒**；import 请求级 `bad_args`、ingest 批次分账 | `mang-app/src/paths.rs` `guard_portable_basename` | cargo `guard_portable_basename_table` + `import_files_rejects_non_portable_basename`；selftest `bid.import_files(保留名基 bad_args)` + `bid.ingest_drop(保留名守卫)` | 双平台同拒（预演 Windows 语义——Linux 合法 `CON.docx` 也拒） |
| R11 | 大小写不敏感占位 | 落位判定按 NTFS upcase 折叠预演：`A.docx` 在场时 `a.docx` 同占位；同内容 `already_present`（Dup 指名不猜）、异内容 `-2` 后缀 | `mang-app/src/bid.rs` `IngestSlot`（占位键 `nfc(name).to_lowercase()`） | cargo `ingest_drop_case_insensitive_dedupe`；selftest `bid.ingest_drop(大小写变体幂等)` | 双平台同拒（占位语义预演） |
| R12 | MAX_PATH 预检 | 落位/rel 估算超 259 字符（Win32 上限 260 含 NUL，CJK 按字符计）→ ingest 分账 `path_too_long` / import `bad_args` | `mang-app/src/paths.rs` `guard_windows_max_path` | cargo `guard_windows_max_path_boundary` + `ingest_drop_maxpath_guard`；selftest `bid.ingest_drop(MAX_PATH 预检)` | 双平台同拒 |
| R13 | NFC 归一 | 落位名/占位键统一 NFC（归一先于大小写折叠）；`filename` 显示名归一；`upload_ref` 定位键**原样**（逐字节匹配磁盘真名） | `mang-app/src/paths.rs` `nfc` | cargo `nfc_normalization_forms` + `ingest_drop_nfc_normalization`；selftest `bid.ingest_drop(NFD 落位归一 NFC)` + `bid.ingest_drop(NFC 重拖占位幂等)` | 双平台 |
| R14 | 混合分隔符矩阵 + 字符串基名 | `\` 恒按分隔符处理（含混合形态收敛/`..` 保留/绝对不压缩/全角斜杠**不过度归一**）；`str_basename` 双分隔符取末段（`Path::file_name` 平台分叉的字符串面单一真源） | `mang-app/src/bid.rs` `normalize_upload_ref`；`mang-app/src/paths.rs` `str_basename` | cargo `r14_mixed_separator_normalize_matrix` + `r14_normalize_mixed_separator_shape_matrix` + `r14_mixed_separator_cjk_roundtrip_and_cross_spelling_idempotence` + `r14_outside_root_separator_forms_rejected` + `r14_trailing_paste_noise_rejected_by_basename_guard` + `r14_dotdot_mixed_separator_request_level_reject` + `r14_directory_ref_partial_failure_accounting` + `r14_nfd_locator_exact_bytes_contract` + `str_basename_dual_separator_matrix`；selftest `workspace.open(R14 矩阵工作区)` | 双平台 + **cfg 双分支**（`r14_unix_backslash_literal_name_ambiguity` 仅 Unix / `r14_windows_backslash_is_separator_identity` 仅 Windows） |
| R15 | 日期时区口径 | `today_ymd` 本地日历日（chrono Local 只供偏移秒，日期数学走 `civil_from_days` 单一真源）；严格公历校验单一真源（不存在的日历日 MCP 面即拒）；截止日比较 ISO 字符串字典序 | `bid-domain/src/dates.rs` `today_ymd` / `today_ymd_utc` / `ymd_at_utc_offset` / `parse_ymd` | cargo `ymd_at_utc_offset_matrix` + `today_ymd_local_vs_utc_sanity` + `parse_ymd_month_length_edges`（域层）+ `nonexistent_calendar_date_rejected_at_mcp_face`（MCP 面）；selftest `workspace.open(R15 工作区)` + `bid.create_project(不存在的日历日拒)` + `bid.create_project(过期截止警告)` | 双平台（iana-time-zone：Unix 读 TZ//etc/localtime、Windows 读注册表） |

### ① 系列：围栏与路径基础（先于硬化专列的既有平台面）

| # | 面 | 行为口径 | 实现真源 | 测试锚 | 平台运行面 |
|---|---|---|---|---|---|
| R2 | 绝对越界样本平台自适应 | 围栏外路径样本按平台取形态（Windows 盘符 `C:/Windows/win.ini` / Unix 根 `/etc/passwd`）——写死盘符在 Linux 是合法相对路径（假绿教训） | `mang-app/src/selftest.rs`（`cfg!(windows)` 分支样本） | selftest `path-guard 越界全拦` + `path-guard 盘符形态平台语义` | **cfg 分支样本**（双平台各断本平台形态） |
| 既有 | 围栏 is_inside 组件比较 | 前缀陷阱：`c:/bid/work-evil` 不命中 `c:/bid/work`——组件级而非字符串前缀；Windows verbatim `\\?\` 前缀不干扰 | `bid-tools/src/fs_fence.rs` `is_inside`（mang-app 侧 `paths.rs` 同名） | cargo `is_inside_is_component_wise_not_string_prefix`（fs_fence）+ `sibling_prefix_not_inside` + `drive_letter_form_platform_semantics`（paths.rs） | 双平台 + Windows verbatim 分支 |
| 既有 | 展示/记录路径规范 | `rel_join` 记录 rel 一律 `/` 分隔（fs.tree 的 rel 即此口径——upload_ref 的规范形态来源）；`display` 展示面反斜杠转 `/` | `mang-app/src/paths.rs` `rel_join` / `display` | cargo `upload_ref_separator_normalized_and_idempotent`（消费面） | 双平台 |

## 三、平台运行面实测账（如实标注）

| 平台 | 已实测面 | 记录 |
|---|---|---|
| Linux（Debian 沙箱，rustc 1.99） | 三件套全量：cargo（mang-app 80 + bid-domain 334 + bid-mcp 22）· selftest 81 · web-ui run-all 13/13 | 2026-11-10，R15 合并后基线；环境备忘：磁盘 97% 满触发 `ld Bus error`（清增量缓存后恢复）——issue #47 备忘同款 |
| Windows（真机/CI） | **未实测**——cfg(windows) 分支断言（R14 windows identity / R2 盘符样本 / verbatim 前缀）在 Windows CI 真跑，本轮无 Windows 真机 | 缺口如实标注：Windows 绝对值归 Lead 复核线（AGENTS §13：不以未跑为通过） |

## 四、防漂移契约（本清单如何被守护）

`web-ui/tests/platform-matrix.test.mjs`（随 R16 入库）逐条校验：

1. **测试锚在场**：本文 §二 引用的每个 cargo 测试名（`fn 名`）在其声明源文件
   真实存在——清单说有的测试被删即红；
2. **selftest 项在场**：本文引用的 selftest 检查名在 `selftest.rs` 在场；
3. **cfg 双分支成对**：R14 的 unix/windows 对照测试名同时在场（删一面即红）；
4. **三类口径标记不漂移**：`guard_portable_basename` / `guard_windows_max_path`
   保持纯函数无 cfg（双平台同拒语义被改成 cfg 分支即红）。

清单新增面（后续轮）必须同步加行 + 加锚——清单、实现、测试三方锁定。
