#!/usr/bin/env node
// #313 批 A + 批 B：标书数据面接线的源级回归门（web-ui 侧）。
//
// 用法（零依赖）：
//   node web-ui/tests/bid-panels.test.mjs
//
// 设计说明（同 md-link.test.mjs 的纪律：不复制实现，断言真源）：
//   * UI 侧：app.js 的活动栏入口 / 工作台伪标签页 / IPC 调用 / 演示桥 stub /
//     章节跳转 / 进度条「不足标红」/ 矩阵页签（筛选/分页/导出/章节跳转）
//     ；styles.css 的面板样式与响应式断点。
//   * 壳侧（防 UI 接了壳没接）：mang-app/src/bid.rs 在场、ipc.rs 分发
//     bid.state / bid.outline / bid.matrix、bid.state / bid.matrix 经
//     bid_mcp::dispatch_with 走真实工具面。
//   * 契约侧：docs/mang/IPC-CONTRACT.md 登记了三个命令（改代码要同步改契约）。
// 任一断言红 = 接线被回退或改名，CI 拦下。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const APP_JS = join(ROOT, "web-ui", "mang", "app.js");
const CSS = join(ROOT, "web-ui", "mang", "styles.css");
const BID_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "bid.rs");
const IPC_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "ipc.rs");
const CONTRACT = join(ROOT, "docs", "mang", "IPC-CONTRACT.md");

const app = readFileSync(APP_JS, "utf8");
const css = readFileSync(CSS, "utf8");
const bidRs = readFileSync(BID_RS, "utf8");
const ipcRs = readFileSync(IPC_RS, "utf8");
const contract = readFileSync(CONTRACT, "utf8");

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

// ---------- app.js：活动栏 + 工作台 ----------
check(
  "SIDEBARS 含「标书」视图（icon=bid，Ctrl+Shift+B）",
  /id:\s*"bid",\s*icon:\s*"bid",\s*title:\s*"标书"/.test(app),
  "活动栏入口被删或改名"
);
check("ICON.bid 徽标在场", /bid:\s*'<svg viewBox="0 0 24 24"/.test(app), "图标被删");
check("KIND_ICON 映射 bidwork", /bidwork:\s*"bid"/.test(app), "工作台 tab 无图标映射");
check(
  "renderSidebar 分发 bid 视图",
  /view === "bid"\s*\)\s*{\s*if \(state\.bid\.status === "idle"\)/.test(app),
  "侧栏不分发标书视图"
);
check(
  "loadTab 有 bidwork 分支（伪标签页不读文件系统）",
  /tab\.kind === "bidwork"\s*\)\s*\{\s*\/\/ #313 批 A[\s\S]{0,200}renderBidWorkbenchView\(tab, host\);/.test(app),
  "工作台 tab 走了 fs.read 路径或渲染入口被改名"
);
check(
  "openBidWorkbench 创建 kind=bidwork 的 tab",
  /kind:\s*"bidwork"/.test(app),
  "伪标签页构造被改"
);
check(
  "数据面调用 bid.state / bid.outline（真实 IPC）",
  /ipc\("bid\.state", \{\}, 15e3\)/.test(app) && /ipc\("bid\.outline", \{\}, 15e3\)/.test(app),
  "IPC 调用被改名/超时口径被改"
);
check(
  "演示桥补 bid.state / bid.outline stub",
  /case "bid\.state":/.test(app) && /case "bid\.outline":/.test(app),
  "浏览器预览模式下标书面板无数据"
);
check(
  "章节状态中文映射含 FAILED / ACCEPTED（issue 状态标记要求）",
  /FAILED:\s*"起草失败"/.test(app) && /ACCEPTED:\s*"已验收"/.test(app),
  "状态徽章文案缺失"
);
check(
  "进度条「不足标红」三态（low/ok/pending）",
  /pct >= 100 \? "ok" : "low"/.test(app),
  "字数进度条判定被改"
);
check(
  "章节详情读 chapters/{id}.json 并跳转（打开章节文件）",
  /data-bid-act="open-chapter"/.test(app) && /absPathOf\(openBtn\.dataset\.path\)/.test(app),
  "章节跳转被删"
);
check(
  "工作区切换重置标书数据面（#194 联动）",
  /标书数据面随根失效/.test(app),
  "切工作区后标书面板显示旧项目"
);
check(
  "占位面板不造数据（批 C/D 禁用态标注 #313；批 B 已接线）",
  /title="批 C 接线（#313）"/.test(app) && /title="批 D 接线（#313）"/.test(app) && !/title="批 B 接线（#313）"/.test(app),
  "未接线面板被启用或假数据"
);

// ---------- app.js：#313 批 B 合规矩阵面板 ----------
check(
  "工作台「合规矩阵」页签已接线（data-bid-panel=matrix）",
  /data-bid-panel="matrix"[^>]*>合规矩阵</.test(app),
  "矩阵页签仍是禁用占位或被改名"
);
check(
  "数据面调用 bid.matrix（真实 IPC）",
  /ipc\("bid\.matrix", \{\}, 6e4\)/.test(app),
  "bid.matrix IPC 调用被改名/超时口径被改"
);
check(
  "演示桥补 bid.matrix stub",
  /case "bid\.matrix":/.test(app),
  "浏览器预览模式下矩阵面板无数据"
);
check(
  "矩阵行展开看原文（条款原文/锚点/证据/响应章节四块）",
  /bid-mx-d-k">条款原文</.test(app) && /bid-mx-d-k">锚点</.test(app) && /bid-mx-d-k">证据</.test(app) && /bid-mx-d-k">响应章节</.test(app),
  "「点未响应项看原文」交互缺失"
);
check(
  "矩阵筛选三面：状态 chips / 类别下拉 / 只看阻断（issue 验收「筛选 blocking」）",
  /data-mx-status=""/.test(app) && /data-mx-cat/.test(app) && /data-mx-blocking/.test(app),
  "筛选面缺失"
);
check(
  "矩阵客户端分页（上一页/下一页/页宽）",
  /data-mx-page="prev"/.test(app) && /data-mx-page="next"/.test(app) && /data-mx-size/.test(app),
  "分页控件缺失"
);
check(
  "矩阵导出 CSV（UTF-8 BOM + fs.writeBytes 落 .mang/exports/——不越权写正文）",
  /\\ufeff/.test(app) && /\.mang\/exports\//.test(app) && /fs\.writeBytes/.test(app),
  "导出被删或写出工作区护栏"
);
check(
  "矩阵行章节跳转（跳转大纲树 selectedId + 页签切回详情）",
  /data-mx-sec/.test(app) && /t\.meta\.selectedId = b\.dataset\.mxSec/.test(app),
  "矩阵→大纲树跳转缺失"
);
check(
  "五态徽章中文映射（T-2 + #245 五态派生）",
  /NOT_RESPONDED: "未响应"/.test(app) && /PENDING_EVIDENCE: "待补证据"/.test(app) && /NOT_APPLICABLE: "不适用"/.test(app),
  "状态徽章文案缺失"
);
check(
  "工作区切换重置矩阵面（批 A/B 同一重置面）",
  /matrix: \{ status: "idle", data: null, error: "" \}/.test(app),
  "切工作区后矩阵面板留旧项目数据"
);

// ---------- styles.css：面板样式 + 响应式 ----------
for (const sel of [".bid-wb ", ".bid-tree ", ".bid-node ", ".bid-detail ", ".bid-badge", ".bid-bar-fill", ".bid-mx-table", ".bid-mx-chip", ".bid-mx-badge", ".bid-mx-pager", ".bid-mx-detail td"]) {
  check(`styles.css 定义 ${sel.trim()}`, css.includes(sel.trim() + " {") || css.includes(sel.trim() + ","), "选择器缺失");
}
check(
  "进度条不足=红（--danger）",
  /\.bid-bar-fill\[data-state="low"\]\s*\{[\s\S]{0,120}var\(--danger\)/.test(css),
  "红条样式缺失"
);
check(
  "矩阵未响应徽章=红（--danger）",
  /\.bid-mx-badge\[data-status="NOT_RESPONDED"\]\s*\{[\s\S]{0,80}var\(--danger\)/.test(css),
  "未响应红徽章样式缺失"
);
check(
  "响应式断点（1440/1920/2560 验收面）",
  /@media \(max-width: 1360px\)/.test(css) && /@media \(min-width: 1920px\)/.test(css),
  "媒体查询被删"
);

// ---------- 壳侧：IPC 命令真实在场 ----------
check(
  "mang-app/src/bid.rs 在场",
  bidRs.includes("pub fn state(") && bidRs.includes("pub fn outline(") && bidRs.includes("pub fn matrix("),
  "数据面模块被删"
);
check(
  "bid.state 经 bid_mcp::dispatch_with 走真实工具面",
  bidRs.includes('bid_mcp::dispatch_with') && bidRs.includes("get_bid_project_state"),
  "直连工具面被绕过"
);
check(
  "bid.matrix 经 bid_mcp::dispatch_with 走 get_compliance_matrix 真实工具面（批 B）",
  bidRs.includes("get_compliance_matrix"),
  "矩阵被绕开工具面另造一套"
);
check(
  "矩阵壳内聚合循 next_cursor（工具面 S-4 分页契约不被绕过）",
  /next_cursor"\)\.and_then\(\|c\| c\.as_str\(\)\)/.test(bidRs) && /PAGE_LIMIT: u64 = 1000/.test(bidRs),
  "聚合循环被改或一次拉超限"
);
check(
  "无 db.json → 干净 not_found（不落副作用）",
  /IpcError::not_found/.test(bidRs) && /没有 db\.json/.test(bidRs),
  "空工作区拒绝语义被改"
);
check(
  "ipc.rs 分发 bid.state / bid.outline / bid.matrix",
  /"bid\.state" => crate::bid::state\(/.test(ipcRs) && /"bid\.outline" => crate::bid::outline\(/.test(ipcRs) && /"bid\.matrix" => crate::bid::matrix\(/.test(ipcRs),
  "命令没接进 IPC 分发"
);

// ---------- 契约：IPC-CONTRACT.md 登记 ----------
check(
  "契约文档登记 bid.state / bid.outline / bid.matrix",
  contract.includes("### bid.state") && contract.includes("### bid.outline") && contract.includes("### bid.matrix"),
  "改了代码没同步契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);

console.log(`\n== ${pass} passed, ${fail} failed ==`);
process.exit(fail === 0 ? 0 : 1);
