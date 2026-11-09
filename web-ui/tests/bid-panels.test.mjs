#!/usr/bin/env node
// #313 批 A：标书数据面接线的源级回归门（web-ui 侧）。
//
// 用法（零依赖）：
//   node web-ui/tests/bid-panels.test.mjs
//
// 设计说明（同 md-link.test.mjs 的纪律：不复制实现，断言真源）：
//   * UI 侧：app.js 的活动栏入口 / 工作台伪标签页 / IPC 调用 / 演示桥 stub /
//     章节跳转 / 进度条「不足标红」；styles.css 的面板样式与响应式断点。
//   * 壳侧（防 UI 接了壳没接）：mang-app/src/bid.rs 在场、ipc.rs 分发
//     bid.state / bid.outline、bid.state 经 bid_mcp::dispatch_with 走真实工具面。
//   * 契约侧：docs/mang/IPC-CONTRACT.md 登记了两个命令（改代码要同步改契约）。
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
  "占位面板不造数据（批 B/C/D 禁用态标注 #313）",
  /title="批 B 接线（#313）"/.test(app),
  "未接线面板被启用或假数据"
);

// ---------- styles.css：面板样式 + 响应式 ----------
for (const sel of [".bid-wb ", ".bid-tree ", ".bid-node ", ".bid-detail ", ".bid-badge", ".bid-bar-fill"]) {
  check(`styles.css 定义 ${sel.trim()}`, css.includes(sel.trim() + " {") || css.includes(sel.trim() + ","), "选择器缺失");
}
check(
  "进度条不足=红（--danger）",
  /\.bid-bar-fill\[data-state="low"\]\s*\{[\s\S]{0,120}var\(--danger\)/.test(css),
  "红条样式缺失"
);
check(
  "响应式断点（1440/1920/2560 验收面）",
  /@media \(max-width: 1360px\)/.test(css) && /@media \(min-width: 1920px\)/.test(css),
  "媒体查询被删"
);

// ---------- 壳侧：IPC 命令真实在场 ----------
check("mang-app/src/bid.rs 在场", bidRs.includes("pub fn state(") && bidRs.includes("pub fn outline("), "数据面模块被删");
check(
  "bid.state 经 bid_mcp::dispatch_with 走真实工具面",
  bidRs.includes('bid_mcp::dispatch_with') && bidRs.includes("get_bid_project_state"),
  "直连工具面被绕过"
);
check(
  "无 db.json → 干净 not_found（不落副作用）",
  /IpcError::not_found/.test(bidRs) && /没有 db\.json/.test(bidRs),
  "空工作区拒绝语义被改"
);
check(
  "ipc.rs 分发 bid.state / bid.outline",
  /"bid\.state" => crate::bid::state\(/.test(ipcRs) && /"bid\.outline" => crate::bid::outline\(/.test(ipcRs),
  "命令没接进 IPC 分发"
);

// ---------- 契约：IPC-CONTRACT.md 登记 ----------
check(
  "契约文档登记 bid.state / bid.outline",
  contract.includes("### bid.state") && contract.includes("### bid.outline"),
  "改了代码没同步契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);

// ---------- app.js：#313 批 C——自评面板接线 ----------
check(
  "数据面调用 bid.quality / bid.score（真实 IPC）",
  /ipc\("bid\.quality", \{\}, 3e4\)/.test(app) && /ipc\("bid\.score", \{\}, 3e4\)/.test(app),
  "IPC 调用被改名/超时口径被改"
);
check(
  "演示桥补 bid.quality / bid.score stub（同形响应）",
  /case "bid\.quality":/.test(app) && /case "bid\.score":/.test(app),
  "浏览器预览模式下自评面板无数据"
);
check(
  "工作台「自评」页签从占位禁用转为接线（data-bid-panel=quality）",
  /data-bid-panel="quality">自评</.test(app),
  "自评页签仍禁用或被改名"
);
check(
  "占位面板只剩批 B/D（批 C 已接线，不再出现在禁用列表）",
  /bidDisabledEntry\("合规矩阵", "REQ × 响应状态 × 证据", "批 B"\)/.test(app)
    && /bidDisabledEntry\("覆盖报告", "已判定 \/ 未判定 \/ ★条款", "批 D"\)/.test(app)
    && !/bidDisabledEntry\("自评"/.test(app),
  "禁用占位与已接线状态不一致"
);
check(
  "侧栏「自评」入口直达工作台自评页签（workbench-quality）",
  /data-bid-act="workbench-quality"/.test(app) && /openBidWorkbench\("quality"\)/.test(app),
  "侧栏入口未接线"
);
check(
  "自评页签懒加载（loadBidQuality）+ 刷新动作（refresh-quality）",
  /async loadBidQuality\(force\)/.test(app) && /ui\.loadBidQuality\(true\)/.test(app),
  "自评数据面拉取/刷新被删"
);
check(
  "#186 语义降级徽章在场（规则诊断 · 非评标模拟）",
  /规则诊断 · 非评标模拟/.test(app),
  "自评分数被伪装成评标结果"
);
check(
  "E_STATE → 壳侧 state 码分支成「尚未开放」引导卡（非故障）",
  /q\.code === "state"/.test(app) && /自评尚未开放/.test(app),
  "早态项目会显示成读取失败"
);
check(
  "价格未报价 = null 诚实显示（不伪缺 0）",
  /未报价不计/.test(app) && /"未报价"/.test(app),
  "价格面被伪装成数值"
);
check(
  "BLOCKER 面（提交就绪 + 跨章冲突 + 负偏离）点击展开",
  /提交就绪与废标风险/.test(app) && /bid-qual-list/.test(app) && /global_conflicts/.test(app) && /negative_deviations/.test(app),
  "BLOCKER 清单被删"
);
check(
  "评分项明细（by_item：估分/档位/覆盖 + 逐章贡献 + 细则检查点）",
  /评分项明细/.test(app) && /by_item/.test(app) && /rule_checkpoints/.test(app)
    && /Array\.isArray\(it\.contributions\) \? it\.contributions : \[\]/.test(app),
  "逐项明细被删（注意 contributions 拼写——演示冒烟曾抓到 contribions 拼错致贡献区恒空）"
);
check(
  "工作区切换重置自评数据面（#194 联动）",
  /自评数据面同理随根失效/.test(app),
  "切工作区后自评面板显示旧项目"
);

// ---------- styles.css：批 C 自评面板样式 ----------
for (const sel of [".bid-qual ", ".bid-qual-scores", ".bid-qual-score ", ".bid-qual-list", ".bid-qual-item", ".bid-qual-tier", ".bid-qual-row"]) {
  check(`styles.css 定义 ${sel.trim()}`, css.includes(sel.trim() + " {") || css.includes(sel.trim() + ","), "选择器缺失");
}
check(
  "评分卡中档过渡态（data-state=mid）",
  /\.bid-bar-fill\[data-state="mid"\]/.test(css),
  "中档进度条样式缺失"
);
check(
  "窄窗评分项行响应式（1150px 收覆盖列）",
  /@media \(max-width: 1150px\)[\s\S]{0,400}grid-template-columns: minmax\(140px, 1fr\) 46px 46px 84px/.test(css),
  "窄窗布局被删"
);

// ---------- 壳侧：IPC 命令真实在场（批 C） ----------
check(
  "mang-app bid.rs 提供 quality / score",
  bidRs.includes("pub fn quality(") && bidRs.includes("pub fn score("),
  "自评数据面模块被删"
);
check(
  "bid.quality / bid.score 经 bid_mcp::dispatch_with 走真实工具面",
  bidRs.includes("check_bid_quality") && bidRs.includes("score_document") && bidRs.includes("bid_mcp::dispatch_with"),
  "直连工具面被绕过"
);
check(
  "E_STATE 映射为壳侧 state 码（区别于 io 故障）",
  /ToolError::EState \{ what \} => IpcError::state\(what\)/.test(bidRs),
  "早态拒绝会被误报成 IO 故障"
);
check(
  "ipc.rs 分发 bid.quality / bid.score",
  /"bid\.quality" => crate::bid::quality\(/.test(ipcRs) && /"bid\.score" => crate::bid::score\(/.test(ipcRs),
  "命令没接进 IPC 分发"
);

// ---------- 契约：IPC-CONTRACT.md 登记（批 C） ----------
check(
  "契约文档登记 bid.quality / bid.score",
  contract.includes("### bid.quality") && contract.includes("### bid.score"),
  "改了代码没同步契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);
check(
  "契约错误码表登记 state（#313 批 C）",
  /\| `state` \| bid 项目未到该命令的状态窗/.test(contract),
  "state 错误码没进 §3.3 错误码表"
);

console.log(`\n== ${pass} passed, ${fail} failed ==`);
process.exit(fail === 0 ? 0 : 1);
