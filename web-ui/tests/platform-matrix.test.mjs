#!/usr/bin/env node
// #47 R16（平台矩阵收口）：平台区分专项回归清单的防漂移契约门。
//
// 用法（零依赖）：
//   node web-ui/tests/platform-matrix.test.mjs
//
// 设计说明（同 bid-panels.test.mjs 纪律：不复制实现，断言真源）：
//   * docs/mang/PLATFORM-MATRIX.md 是跨平台硬化专列（R2/R9-R15 九面）的
//     权威回归清单——每面引用了实现真源函数与测试锚（cargo fn 名 /
//     selftest 检查名）。
//   * 本门逐条校验：清单说有的东西必须在源码真实在场。清单被删、
//     锚测试被删/改名、cfg 双分支被删一面、双平台同拒守卫被改成
//     cfg 分支——任一漂移即红。
//   * 后续轮新增平台面必须同步加行加锚（三方锁定：清单/实现/测试）。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const read = (...p) => readFileSync(join(ROOT, ...p), "utf8");

const MATRIX = read("docs", "mang", "PLATFORM-MATRIX.md");
const bidRs = read("bidcore", "crates", "mang-app", "src", "bid.rs");
const pathsRs = read("bidcore", "crates", "mang-app", "src", "paths.rs");
const selftestRs = read("bidcore", "crates", "mang-app", "src", "selftest.rs");
const fenceSrc = read("bidcore", "crates", "bid-tools", "src", "fs_fence.rs");
const datesRs = read("bidcore", "crates", "bid-domain", "src", "dates.rs");
const mcpTest = read("bidcore", "crates", "bid-mcp", "tests", "import_tender_files_tool.rs");

let pass = 0;
let fail = 0;
function check(name, cond, detail) {
  if (cond) {
    pass++;
    console.log(`PASS  ${name}`);
  } else {
    fail++;
    console.log(`FAIL  ${name}${detail ? "：" + detail : ""}`);
  }
}

// ---------- 一、清单在场与结构 ----------
check(
  "R16 清单：PLATFORM-MATRIX.md 在场且含三段结构（口径总则/回归矩阵/实测账）",
  MATRIX.includes("平台区分专项回归清单") &&
    MATRIX.includes("## 一、口径总则") &&
    MATRIX.includes("## 二、回归矩阵") &&
    MATRIX.includes("## 三、平台运行面实测账"),
  "清单被删或结构漂移"
);
check(
  "R16 清单：九面齐全（R2/R9/R10/R11/R12/R13/R14/R15 + 既有两行）",
  ["R2", "R9", "R10", "R11", "R12", "R13", "R14", "R15"].every((r) =>
    new RegExp(`\\| ${r} \\|`).test(MATRIX)
  ) && MATRIX.includes("| 既有 | 围栏 is_inside"),
  "矩阵行缺失"
);

// ---------- 二、cargo 测试锚在场（清单引用的每个 fn 必须真实存在） ----------
const cargoAnchors = [
  // [描述, 源文件内容, fn 名]
  ["R9 归一幂等", bidRs, "upload_ref_separator_normalized_and_idempotent"],
  ["R10 基名表", pathsRs, "guard_portable_basename_table"],
  ["R10 import 拒", bidRs, "import_files_rejects_non_portable_basename"],
  ["R11 CI 去重", bidRs, "ingest_drop_case_insensitive_dedupe"],
  ["R12 边界", pathsRs, "guard_windows_max_path_boundary"],
  ["R12 深目录集成", bidRs, "ingest_drop_maxpath_guard"],
  ["R13 形态", pathsRs, "nfc_normalization_forms"],
  ["R13 落位集成", bidRs, "ingest_drop_nfc_normalization"],
  ["R14 归一矩阵", bidRs, "r14_mixed_separator_normalize_matrix"],
  ["R14 形态矩阵", bidRs, "r14_normalize_mixed_separator_shape_matrix"],
  ["R14 CJK 往返", bidRs, "r14_mixed_separator_cjk_roundtrip_and_cross_spelling_idempotence"],
  ["R14 围栏外拒", bidRs, "r14_outside_root_separator_forms_rejected"],
  ["R14 尾噪声拒", bidRs, "r14_trailing_paste_noise_rejected_by_basename_guard"],
  ["R14 ..请求级拒", bidRs, "r14_dotdot_mixed_separator_request_level_reject"],
  ["R14 目录 ref 分账", bidRs, "r14_directory_ref_partial_failure_accounting"],
  ["R14 NFD 定位键契约", bidRs, "r14_nfd_locator_exact_bytes_contract"],
  ["R14 字符串基名矩阵", pathsRs, "str_basename_dual_separator_matrix"],
  ["既有 围栏组件比较", fenceSrc, "is_inside_is_component_wise_not_string_prefix"],
  ["既有 前缀陷阱", pathsRs, "sibling_prefix_not_inside"],
  ["既有 盘符平台语义", pathsRs, "drive_letter_form_platform_semantics"],
  ["R15 偏移矩阵", datesRs, "ymd_at_utc_offset_matrix"],
  ["R15 本地/UTC 健全性", datesRs, "today_ymd_local_vs_utc_sanity"],
  ["R15 月长边界", datesRs, "parse_ymd_month_length_edges"],
  ["R15 MCP 面拒坏日历日", mcpTest, "nonexistent_calendar_date_rejected_at_mcp_face"],
];
for (const [label, src, fn] of cargoAnchors) {
  check(
    `R16 锚：${label}（fn ${fn}）在场`,
    new RegExp(`fn ${fn}\\(`).test(src) && MATRIX.includes(fn),
    "源码缺失或清单未引用"
  );
}

// ---------- 三、selftest 锚在场 ----------
const selftestAnchors = [
  "path-guard 越界全拦",
  "path-guard 盘符形态平台语义",
  "bid.import_files(Windows 形态归一导入)",
  "bid.import_files(两形态同件幂等)",
  "bid.import_files(保留名基 bad_args)",
  "bid.ingest_drop(保留名守卫)",
  "bid.ingest_drop(大小写变体幂等)",
  "bid.ingest_drop(MAX_PATH 预检)",
  "bid.ingest_drop(NFD 落位归一 NFC)",
  "bid.ingest_drop(NFC 重拖占位幂等)",
  "workspace.open(R14 矩阵工作区)",
  "workspace.open(R15 工作区)",
  "bid.create_project(不存在的日历日拒)",
  "bid.create_project(过期截止警告)",
];
for (const name of selftestAnchors) {
  check(
    `R16 selftest 锚：「${name}」在场`,
    selftestRs.includes(name) && MATRIX.includes(name),
    "selftest.rs 缺失或清单未引用"
  );
}

// ---------- 四、cfg 双分支成对（R14 平台语义对照不许删一面） ----------
// 注意：cfg 属性在 fn 名**之前**（#[cfg(unix)] #[test] fn …）——窗口
// 必须从 fn 名前一段开始取。
const r14UnixFn = "fn r14_unix_backslash_literal_name_ambiguity";
const r14WinFn = "fn r14_windows_backslash_is_separator_identity";
const r14Fns = bidRs.slice(
  Math.max(0, bidRs.indexOf(r14UnixFn) - 300),
  bidRs.indexOf(r14WinFn) + 3000
);
check(
  "R16 cfg 成对：R14 unix 反斜杠字面名歧义（#[cfg(unix)] 断言面）",
  /#\[cfg\(unix\)\]\s*\n\s*#\[test\]\s*\n\s*fn r14_unix_backslash_literal_name_ambiguity/.test(bidRs),
  "unix 分支被删（Linux 字面反斜杠名诚实失败的锚）"
);
check(
  "R16 cfg 成对：R14 windows 反斜杠分隔符同一性（#[cfg(windows)] 断言面）",
  /#\[cfg\(windows\)\]\s*\n\s*#\[test\]\s*\n\s*fn r14_windows_backslash_is_separator_identity/.test(bidRs),
  "windows 分支被删（native 命中的锚）"
);

// ---------- 五、双平台同拒守卫不许变成 cfg 分支 ----------
// 窗口只取函数体本身（到下一个顶层声明为止）——避免误吞测试模块的
// #[cfg(test)] 属性。
function cfgFree(src, fn) {
  const i = src.indexOf(`pub fn ${fn}(`);
  if (i < 0) return false;
  let end = src.indexOf("\n}\n", i); // 函数体收尾
  if (end < 0 || end - i > 2000) end = i + 800;
  const body = src.slice(i, end);
  return !body.includes("#[cfg");
}
check(
  "R16 同拒语义：guard_portable_basename 保持纯函数无 cfg（双平台同拒）",
  cfgFree(pathsRs, "guard_portable_basename"),
  "守卫被改成 cfg 分支 = Linux 放走不可迁移形态（R10 口径破坏）"
);
check(
  "R16 同拒语义：guard_windows_max_path 保持纯函数无 cfg（双平台同拒）",
  cfgFree(pathsRs, "guard_windows_max_path"),
  "守卫被改成 cfg 分支 = Linux 放走超长路径（R12 口径破坏）"
);

// ---------- 六、清单 ↔ 实现真源函数三方锁定 ----------
check(
  "R16 真源锚：normalize_upload_ref / str_basename / nfc / today_ymd / ymd_at_utc_offset 在清单与源码双侧在场",
  ["normalize_upload_ref", "str_basename", "guard_windows_max_path", "guard_portable_basename"].every(
    (f) => MATRIX.includes(f) && (bidRs.includes(`fn ${f}(`) || pathsRs.includes(`fn ${f}(`))
  ) &&
    ["today_ymd", "ymd_at_utc_offset"].every((f) => MATRIX.includes(f) && datesRs.includes(`pub fn ${f}(`)),
  "清单引用的真源函数缺失（实现被改名/删除）"
);

console.log(`\n== ${pass} passed, ${fail} failed ==`);
process.exit(fail === 0 ? 0 : 1);
