#!/usr/bin/env node
// #20：治理出口三件接线——源级回归门（web-ui 侧 + 壳侧 + 契约侧）。
//
// 用法（零依赖）：
//   node web-ui/tests/bid-governance-exits.test.mjs
//
// 断言面（同 bid-panels / bid-project-wizard 的纪律——断真源防回退）：
//   * UI：矩阵行裁定出口（#226）/ VALIDATING 恢复入口（#243）/ 分包页签（#316）
//   * 接线一致性：UI 读取字段 ↔ 演示桥 stub ↔ 契约文档三方同形
//   * 壳侧：ipc.rs 分发三条、receipt 签发（#182 四重绑定）、域层守门透传
//   * 顺手修：matrix 面板单参路由调用防御（panel 缺省取 #bid-panel——
//     否则工作台点「合规矩阵」页签即 TypeError 的预存断链）
//   * 契约：三节登记 + 形状一致

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const APP_JS = join(ROOT, "web-ui", "mang", "app.js");
const IPC_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "ipc.rs");
const BID_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "bid.rs");
const CONTRACT = join(ROOT, "docs", "mang", "IPC-CONTRACT.md");

const app = readFileSync(APP_JS, "utf8");
const ipcRs = readFileSync(IPC_RS, "utf8");
const bidRs = readFileSync(BID_RS, "utf8");
const contract = readFileSync(CONTRACT, "utf8");

let pass = 0, fail = 0;
function check(name, ok, detail = "") {
  if (ok) { pass++; console.log("PASS  " + name + (detail ? "（" + detail + "）" : "")); }
  else { fail++; console.log("FAIL  " + name + (detail ? "（" + detail + "）" : "")); }
}

// ---- ① UI：矩阵人工裁定出口（#226） ----
check("详情行裁定入口（data-mo-open + #226 注记）",
  app.includes('data-mo-open') && app.includes("人工裁定（#226）"));
check("裁定表单四态枚举 + 偏离说明 textarea",
  app.includes('value="NOT_APPLICABLE"') && app.includes('data-mo-status') && app.includes("data-mo-deviation"));
check("NOT_APPLICABLE 前置拦截（偏离说明必填——不可审计的豁免不算豁免）",
  /status === "NOT_APPLICABLE" && !deviation/.test(app));
check("裁定接线（open/cancel/confirm 三动作 + 表单内点击不触发行折叠）",
  app.includes('"[data-mo-open]"') && app.includes('"[data-mo-cancel]"')
  && app.includes('"[data-mo-confirm]"') && app.includes("closest(\"[data-mo-form]\")"));

// ---- ② UI：VALIDATING 恢复入口（#243） ----
check("恢复入口仅在 VALIDATING 态显示（异常态引导卡非常驻）",
  /projSt === "VALIDATING"/.test(app) && app.includes("校验异常态（VALIDATING）"));
check("恢复表单理由必填（前端前置 + 域层三重约束兜底）",
  app.includes("data-rv-reason") && /if \(!reason\) \{[\s\S]{0,120}恢复理由必填/.test(app));
check("恢复接线（rv-open/rv-cancel/rv-confirm → ui.recoverBidState）",
  app.includes('"[data-rv-open]"') && app.includes('"[data-rv-confirm]"') && app.includes("ui.recoverBidState(reason)"));

// ---- ③ UI：分包页签（#316 只读 + 选包状态） ----
check("工作台页签含「分包」（第六页签）",
  app.includes('data-bid-panel="packages">分包</button>'));
check("分包面板渲染（识别/逐包条款/选包状态/共用条款/usage 提示）",
  app.includes("function renderBidPackagesPanel")
  && app.includes("#316 识别面") && app.includes("已选包") && app.includes("共用条款"));
check("分包只读纪律（选包不在本面板——usage 呈现）",
  app.includes("未伪装可写") || app.includes("不伪装可写") || /选包动作不在本面板/.test(app));
check("两处路由（有树/空树）+ 侧栏入口 + 数据面",
  /if \(activePanel === "packages"\) \{\s*\n\s*renderBidPackagesPanel\(host\);/.test(app)
  && app.includes('data-bid-act="workbench-packages"')
  && app.includes("bidPackages: { status: \"idle\", data: null, error: \"\" }"));

// ---- ④ 顺手修：matrix 面板单参路由防御（预存断链） ----
check("matrix 面板 panel 缺省防御（单参调用不再 TypeError）",
  /if \(!panel\) panel = host\.querySelector\("#bid-panel"\);\s*\n\s*if \(!panel\) return;/.test(app));

// ---- ⑤ UI：IPC 调用面与读取字段 ----
check("passMatrixOverride 调 bid.matrix_override（行/状态/偏离）",
  /ipc\("bid\.matrix_override", \{\s*requirement_id: reqId,\s*status: status,\s*deviation: deviation \|\| ""\s*\}, 3e4\)/.test(app));
check("recoverBidState 调 bid.recover_state（reason）",
  /ipc\("bid\.recover_state", \{ reason: reason \}, 3e4\)/.test(app));
check("loadBidPackages 调 bid.packages（只读）",
  app.includes('ipc("bid.packages", {}, 15e3)'));
check("UI 读 override.blocking_after / override.status（覆写后阻断重算回显）",
  app.includes("ov.blocking_after") && app.includes("ov.status || status"));
check("UI 读 recover.to_status（恢复目标态回显）",
  app.includes("rc.to_status || \"DRAFTING\""));
check("UI 读 packages.items / selected_package / shared_req_count",
  app.includes("d.items") && app.includes("d.selected_package") && app.includes("d.shared_req_count"));

// ---- ⑥ 演示桥 stub：与 UI 读取字段同形 ----
check("桥 stub bid.packages（detected/items/selected/shared/usage）",
  /case "bid\.packages":[\s\S]{0,400}detected: 2/.test(app)
  && app.includes('selected_package: { id: "PKG-A"') && app.includes("shared_req_count: 6"));
check("桥 stub bid.matrix_override（blocking_after/from_status/audit）",
  /case "bid\.matrix_override":[\s\S]{0,700}blocking_after: 2/.test(app)
  && app.includes("from_status: \"NOT_RESPONDED\"") && app.includes("method: \"human_receipt\""));
check("桥 stub bid.recover_state（from/to/recovered_sections）",
  /case "bid\.recover_state":[\s\S]{0,500}to_status: "DRAFTING"/.test(app)
  && app.includes("recovered_sections: [\"SEC-T03\"]"));

// ---- ⑦ 壳侧 ----
check("ipc.rs 分发 bid.packages / bid.matrix_override / bid.recover_state",
  ipcRs.includes('"bid.packages" => crate::bid::packages(&ws, &self.bid, &a)')
  && ipcRs.includes('"bid.matrix_override" => crate::bid::matrix_override(&ws, &self.bid, &a)')
  && ipcRs.includes('"bid.recover_state" => crate::bid::recover_state(&ws, &self.bid, &a)'));
check("matrix_override receipt 宿主签发（#182 四重绑定签域）",
  bidRs.includes("bid_mcp::matrix_override_scope(&project_id, &requirement_id, &status, &deviation)")
  && bidRs.includes("svc.issue_approval_receipt(&actor_id, &scope)"));
check("三面均经 bid_mcp::dispatch_with 走真实工具面",
  bidRs.includes('tool: "list_packages".to_string()')
  && bidRs.includes('tool: "set_matrix_override".to_string()')
  && bidRs.includes('tool: "recover_validating_state".to_string()'));
check("壳侧预检：空 requirement_id / 空理由（不签发不路由）",
  bidRs.includes("requirement_id 不能为空") && bidRs.includes("reason 必填非空白（不可审计的恢复不成恢复）"));
check("bid.rs 单测覆盖（governance_exits_read_and_guards）",
  bidRs.includes("fn governance_exits_read_and_guards()")
  && bidRs.includes("REQ-9999 不存在，工具面必拒"));

// ---- ⑧ 契约 ----
check("契约三节登记（packages/matrix_override/recover_state）",
  contract.includes("### bid.packages") && contract.includes("### bid.matrix_override")
  && contract.includes("### bid.recover_state"));
check("契约 receipt 签域说明（四重绑定）",
  contract.includes("matrix_override:<project_id>:<requirement_id>:<status>:<sha256(deviation)>"));
check("契约三重约束说明（仅 VALIDATING/仅缺章/理由非空白）",
  contract.includes("仅 VALIDATING / 仅缺章 / 理由非空白"));
check("契约选包纪律（选包 = build_outline 的 package 参数）",
  contract.includes("build_outline 传 package=<id|label|number>"));

console.log();
if (fail > 0) {
  console.error(`bid-governance-exits: ${pass} 通过，${fail} 失败`);
  process.exit(1);
}
console.log(`bid-governance-exits: ${pass}/${pass + fail} 全部通过`);
