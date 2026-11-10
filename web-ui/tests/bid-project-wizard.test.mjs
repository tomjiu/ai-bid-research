#!/usr/bin/env node
// #19：建项/导入向导接线——源级回归门（web-ui 侧 + 壳侧 + 契约侧）。
//
// 用法（零依赖）：
//   node web-ui/tests/bid-project-wizard.test.mjs
//
// 断言面（与 bid-panels.test.mjs 同族纪律——不复制实现，断言真源）：
//   * UI 侧：空态引导卡（「新建标书项目」入口）、向导两步表单、
//     IPC 调用面（bid.create_project / bid.import_tender 参数与读取
//     字段）、演示桥 stub、向导动作绑定（wizard-*）
//   * 接线一致性（防「UI 读 A、桥回 B」断链）：ipc 调用方读的键
//     create.project_id / create.warnings / import.totals.files /
//     import.per_file[].errors ↔ 演示桥 stub ↔ 契约文档三处一致
//   * 壳侧：ipc.rs 分发两条、bid.rs 经 bid_mcp::dispatch_with 走真实
//     工具面、`..` 词法预拒、tender-src 收编、缓存失效
//   * 契约侧：IPC-CONTRACT.md 登记两条命令 + selftest 清单同步
// 任一断言红 = 接线被回退或改名。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const APP_JS = join(ROOT, "web-ui", "mang", "app.js");
const IPC_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "ipc.rs");
const BID_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "bid.rs");
const SELFTEST_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "selftest.rs");
const CONTRACT = join(ROOT, "docs", "mang", "IPC-CONTRACT.md");

const app = readFileSync(APP_JS, "utf8");
const ipcRs = readFileSync(IPC_RS, "utf8");
const bidRs = readFileSync(BID_RS, "utf8");
const selftestRs = readFileSync(SELFTEST_RS, "utf8");
const contract = readFileSync(CONTRACT, "utf8");

let pass = 0, fail = 0;
function check(name, ok, detail = "") {
  if (ok) { pass++; console.log("PASS  " + name + (detail ? "（" + detail + "）" : "")); }
  else { fail++; console.log("FAIL  " + name + (detail ? "（" + detail + "）" : "")); }
}

// ---- ① UI：空工作区引导卡（产品出口——issue #19 核心） ----
check("空态卡含「新建标书项目」主入口",
  app.includes('data-bid-act="wizard-create"') && app.includes("新建标书项目"));
check("向导两步：create（名称/模式/截止日/公告编号）",
  app.includes('data-wz-name') && app.includes('data-wz-mode')
  && app.includes('data-wz-deadline') && app.includes('data-wz-notice'));
check("向导两步：import（路径列表 + textarea 批量添加）",
  app.includes('data-wz-remove') && app.includes('data-wz-paths'));
check("向导动作绑定齐全（create-submit/import-submit/import-skip/cancel）",
  app.includes('"wizard-create-submit"') && app.includes('"wizard-import-submit"')
  && app.includes('"wizard-import-skip"') && app.includes('"wizard-cancel"'));
check("向导态在 state（step/files/busy/error/info）",
  /bidWizard: \{ step: "", files: \[\], busy: false, error: "", info: "" \}/.test(app));
check("空态分支路由向导（notProject && wizard.step → renderBidWizard）",
  /if \(notProject && state\.bidWizard\.step\) \{[\s\S]{0,80}renderBidWizard\(body\)/.test(app));

// ---- ② UI：IPC 调用面（参数 + 读取字段——接线一致性源头） ----
check("createBidProject 调 bid.create_project（name/mode/bid_deadline/notice）",
  /ipc\("bid\.create_project", args, 3e4\)/.test(app)
  && app.includes("name: name, mode: mode, bid_deadline: bidDeadline")
  && app.includes("args.tender_notice_ref = noticeRef"));
check("importTenderFiles 调 bid.import_tender（files:[{path}]）",
  /ipc\("bid\.import_tender", \{\s*files: files\.map\(\(p\) => \(\{ path: p \}\)\)\s*\}, 12e4\)/.test(app));
check("UI 读 create.project_id / create.warnings / create.status",
  app.includes("r.create || {}") && app.includes("create.warnings") && app.includes("create.status"));
check("UI 读 import.totals / import.per_file（逐件失败回显）",
  app.includes("imp.totals") && app.includes("imp.per_file")
  && /perFile\.filter\(\(f\) => f\.errors && f\.errors\.length\)/.test(app));
check("E_STATE 分支引导文案（不弹故障横幅——IPC-CONTRACT §109 约定）",
  /code === "state"\s*\n\s*\? "已有项目且状态不允许再建/.test(app));
check("去重导入（Set 防重复提交）",
  /const seen = \/\* @__PURE__ \*\/ new Set\(\);[\s\S]{0,120}for \(const p of paths\) if \(!seen\.has\(p\)\)/.test(app));

// ---- ③ 演示桥 stub：与 UI 读取字段同形（防「UI 读 A 桥回 B」） ----
check("演示桥 stub bid.create_project（present/create.project_id/warnings）",
  /case "bid\.create_project":[\s\S]{0,400}create: \{[\s\S]{0,120}project_id: "PRJ-DEMO-0001"[\s\S]{0,200}warnings: \[\]/.test(app));
check("演示桥 stub bid.import_tender（import.file_ids/per_file/totals）",
  /case "bid\.import_tender":[\s\S]{0,600}import: \{[\s\S]{0,80}file_ids: \["TF-DEMO-0001"\]/.test(app)
  && /per_file: \[\{ file_id: "TF-DEMO-0001", filename: "招标文件\.pdf"/.test(app)
  && app.includes('totals: { files: 1, chunks: 120, parse_failed: 0, partial: 0 }'));

// ---- ④ 壳侧：分发 + 真实工具面 + 收编 + 防御面 ----
check("ipc.rs 分发 bid.create_project / bid.import_tender",
  ipcRs.includes('"bid.create_project" => crate::bid::create_project(&ws, &self.bid, &a)')
  && ipcRs.includes('"bid.import_tender" => crate::bid::import_tender(&ws, &self.bid, &a)'));
check("bid.rs create_project 经 dispatch_with 走真实工具面",
  bidRs.includes('tool: "create_bid_project".to_string()') && bidRs.includes("bid_mcp::dispatch_with"));
check("bid.rs import_tender 经 dispatch_with 走真实工具面",
  bidRs.includes('tool: "import_tender_files".to_string()'));
check("壳侧收编：工作区外绝对路径拷入 tender-src/",
  bidRs.includes('let dst_dir = root.join("tender-src");') && bidRs.includes("std::fs::copy(p, &dst)"));
check("壳侧预拒：`..` 词法分量先于一切磁盘操作",
  /matches!\(c, std::path::Component::ParentDir\)/.test(bidRs));
check("filename 净化（防目录入侵）+ 空名响亮拒",
  bidRs.includes("fn sanitize_filename") && bidRs.includes("filename 非法"));
check("建项后缓存显式失效（lock(cache).take()）",
  bidRs.includes("lock(cache).take()"));
check("幂等键缺省 shell::<工作区名>::<项目名>",
  bidRs.includes('format!("shell::{ws_name}::{name}")'));
check("selftest 覆盖 #19（建项/幂等/收编/逃逸拒/空批次拒）",
  selftestRs.includes("bid.create_project(建项)") && selftestRs.includes("bid.create_project(幂等重放)")
  && selftestRs.includes("bid.import_tender(真件收编)") && selftestRs.includes("bid.import_tender(词法逃逸拒)")
  && selftestRs.includes("bid.import_tender(空批次拒)"));

// ---- ⑤ 契约侧：登记 + 形状一致（三方同形） ----
check("契约登记 bid.create_project / bid.import_tender",
  contract.includes("### bid.create_project") && contract.includes("### bid.import_tender"));
check("契约 create 形状 = UI 读取面（create.project_id/status/warnings）",
  /"create": \{ "project_id": "PRJ-0001", "status": "DRAFT",[\s\S]{0,80}"warnings": \[\] \}/.test(contract));
check("契约 import 形状 = UI 读取面（file_ids/per_file/totals）",
  contract.includes('"import": { "file_ids": ["TF-0001"]')
  && contract.includes('"per_file"') && contract.includes('"totals": { "files": 1'));
check("契约 selftest 清单同步 #19",
  contract.includes("bid.create_project+bid.import_tender（#19"));
check("契约记录收编语义（tender-src + 围栏不豁免）",
  contract.includes("tender-src") && contract.includes("不豁免围栏"));

// ---- ⑥ CSS：向导样式在场（防样式断链） ----
const css = readFileSync(join(ROOT, "web-ui", "mang", "styles.css"), "utf8");
check("styles.css 向导样式（bid-wiz-field/input/files/error/info）",
  css.includes(".bid-wiz-field") && css.includes(".bid-wiz-input")
  && css.includes(".bid-wiz-files") && css.includes(".bid-wiz-error") && css.includes(".bid-wiz-info"));

console.log();
if (fail > 0) {
  console.error(`bid-project-wizard: ${pass} 通过，${fail} 失败`);
  process.exit(1);
}
console.log(`bid-project-wizard: ${pass}/${pass + fail} 全部通过`);
