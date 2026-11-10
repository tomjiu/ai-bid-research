#!/usr/bin/env node
// #313 批 A + 批 B + 批 C + #603 批 A：标书数据面/治理面接线的源级回归门（web-ui 侧）。
//
// 用法（零依赖）：
//   node web-ui/tests/bid-panels.test.mjs
//
// 设计说明（同 md-link.test.mjs 的纪律：不复制实现，断言真源）：
//   * UI 侧：app.js 的活动栏入口 / 工作台伪标签页 / IPC 调用 / 演示桥 stub /
//     章节跳转 / 进度条「不足标红」/ 矩阵页签（筛选/分页/导出/章节跳转）
//     / 自评页签 / 审核门页签（#603 批 A：五门台账/追认/过门拒审）
//     ；styles.css 的面板样式与响应式断点。
//   * 壳侧（防 UI 接了壳没接）：mang-app/src/bid.rs 在场、ipc.rs 分发
//     bid.state / bid.outline / bid.matrix、bid.state / bid.matrix 经
//     bid_mcp::dispatch_with 走真实工具面；bid.gates / bid.gate_pass
//     （#603：DomainStore 直读 + 宿主签发 receipt → record_review_gate）。
//   * 契约侧：docs/mang/IPC-CONTRACT.md 登记了全部命令（改代码要同步改契约）。
// 任一断言红 = 接线被回退或改名，CI 拦下。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const APP_JS = join(ROOT, "web-ui", "mang", "app.js");
const CSS = join(ROOT, "web-ui", "mang", "styles.css");
const BID_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "bid.rs");
const IPC_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "ipc.rs");
const PATHS_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "paths.rs");
const RECENT_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "recent.rs");
const SELFTEST_RS = join(ROOT, "bidcore", "crates", "mang-app", "src", "selftest.rs");
const FENCE_TEST = join(ROOT, "bidcore", "crates", "bid-tools", "tests", "fs_fence.rs");
const CONTRACT = join(ROOT, "docs", "mang", "IPC-CONTRACT.md");

const app = readFileSync(APP_JS, "utf8");
const css = readFileSync(CSS, "utf8");
const bidRs = readFileSync(BID_RS, "utf8");
const ipcRs = readFileSync(IPC_RS, "utf8");
const pathsRs = readFileSync(PATHS_RS, "utf8");
const recentRs = readFileSync(RECENT_RS, "utf8");
const selftestRs = readFileSync(SELFTEST_RS, "utf8");
const fenceTest = readFileSync(FENCE_TEST, "utf8");
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
  "占位面板全部接线（#313 批 A/B/C/D 四面板收官，无禁用占位）",
  // 批 D 合并后四个面板都已接线：不应再有任何「批 X 接线」禁用标注。
  !/title="批 B 接线（#313）"/.test(app)
    && !/title="批 C 接线（#313）"/.test(app)
    && !/title="批 D 接线（#313）"/.test(app),
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

// ---------- app.js：#313 批 D 覆盖报告面板 ----------
check(
  "工作台「覆盖报告」页签已接线（data-bid-panel=coverage）",
  /data-bid-panel="coverage"[^>]*>覆盖报告</.test(app),
  "覆盖报告页签仍是禁用占位或被改名"
);
check(
  "数据面调用 bid.coverage（真实 IPC）",
  /ipc\("bid\.coverage", \{\}, 6e4\)/.test(app),
  "bid.coverage IPC 调用被改名/超时口径被改"
);
check(
  "演示桥补 bid.coverage stub（与真实响应同形）",
  /case "bid\.coverage":/.test(app) && /DEMO_BID\.coverage/.test(app),
  "浏览器预览模式下覆盖报告面板无数据"
);
check(
  "覆盖报告有可视化（issue 验收 5：饼图/柱图——conic 三色环 + 分账条）",
  /conic-gradient\(var\(--ok\)/.test(app) && /bid-cov-bar/.test(app),
  "三态可视化缺失"
);
check(
  "三态分账键（#244：已判定/已排除/未判定——A+B+C=total）",
  /judged_blocks/.test(app) && /excluded_blocks/.test(app) && /unjudged_blocks/.test(app),
  "三态分账面缺失"
);
check(
  "★条款覆盖 N/M（#285：真值★已捕获/真值★）",
  /star_truth/.test(app) && /star_captured/.test(app) && /star_missing/.test(app),
  "★条款覆盖面缺失"
);
check(
  "DRAFT 态分支「覆盖报告尚未开放」引导卡（壳侧 state 码——非错误横幅）",
  /覆盖报告尚未开放/.test(app) && /cv\.code === "state"/.test(app),
  "早态项目显示为故障而非引导"
);
check(
  "逐文件覆盖表（行展开看 by_verdict 分账 + 未判定区间明细 + ★引导）",
  /判定分账（by_verdict）/.test(app) && /未判定区间（C 态——块号含两端）/.test(app) && /★漏标引导（#285）/.test(app),
  "行展开明细缺失"
);
check(
  "建纲门 next 提示（工具面 next 原样——单一真源）",
  /bid-cov-next/.test(app),
  "下一步引导缺失"
);
check(
  "工作区切换/项目面失效重置覆盖面（批 A/B/D 同一重置面）",
  /coverage: \{ status: "idle", data: null, error: "", code: "" \}/.test(app),
  "切工作区后覆盖报告留旧项目数据"
);

// ---------- styles.css：面板样式 + 响应式 ----------
for (const sel of [".bid-wb ", ".bid-tree ", ".bid-node ", ".bid-detail ", ".bid-badge", ".bid-bar-fill", ".bid-mx-table", ".bid-mx-chip", ".bid-mx-badge", ".bid-mx-pager", ".bid-mx-detail td", ".bid-cov-donut", ".bid-cov-table", ".bid-cov-badge", ".bid-cov-next", ".bid-cov-detail td"]) {
  check(`styles.css 定义 ${sel.trim()}`, css.includes(sel.trim() + " {") || css.includes(sel.trim() + ","), "选择器缺失");
}
check(
  "覆盖未判定态=红（--danger）",
  /\.bid-cov-badge\[data-state="un"\]\s*\{[\s\S]{0,80}var\(--danger\)/.test(css),
  "未判定红徽章样式缺失"
);
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
  "bid.coverage 经 bid_mcp::dispatch_with 走 get_coverage_report 真实工具面（批 D）",
  bidRs.includes("get_coverage_report") && bidRs.includes("pub fn coverage("),
  "覆盖报告被绕开工具面另造一套"
);
check(
  "★条款覆盖循 get_star_coverage 逐文件聚合（#285——不复制判定逻辑）",
  bidRs.includes("get_star_coverage"),
  "★面被另造一套"
);
check(
  "工具面 E_STATE 透传壳侧 state 码（批 C/D 契约 §3.3）",
  /ToolError::EState \{ what \} => IpcError::new\("state", what\)/.test(bidRs),
  "早态项目错误码被吞成 io"
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
  "ipc.rs 分发 bid.state / bid.outline / bid.matrix / bid.coverage",
  /"bid\.state" => crate::bid::state\(/.test(ipcRs) && /"bid\.outline" => crate::bid::outline\(/.test(ipcRs) && /"bid\.matrix" => crate::bid::matrix\(/.test(ipcRs) && /"bid\.coverage" => crate::bid::coverage\(/.test(ipcRs),
  "命令没接进 IPC 分发"
);

// ---------- 契约：IPC-CONTRACT.md 登记 ----------
check(
  "契约文档登记 bid.state / bid.outline / bid.matrix / bid.coverage",
  contract.includes("### bid.state") && contract.includes("### bid.outline") && contract.includes("### bid.matrix") && contract.includes("### bid.coverage"),
  "改了代码没同步契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);
check(
  "契约 §3.3 登记 state 错误码（E_STATE 透传——批 C/D）",
  /\| `state` \|/.test(contract),
  "早态项目错误码未入错误码表"
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
  "四个面板入口全部接线（#313 批 A/B/C/D 收官，无禁用占位）",
  // 批 D 合并后：合规矩阵 / 自评 / 覆盖报告  모두已接线，
  // bidDisabledEntry 不应再被调用（保留函数定义供未来新面板）。
  !/bidDisabledEntry\("合规矩阵"/.test(app)
    && !/bidDisabledEntry\("自评"/.test(app)
    && !/bidDisabledEntry\("覆盖报告"/.test(app),
  "仍有面板停在禁用占位"
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

// ---------- 壳侧：IPC 命令真实在场（#603 批 A：治理面） ----------
check(
  "mang-app bid.rs 提供 gates / gate_pass",
  bidRs.includes("pub fn gates(") && bidRs.includes("pub fn gate_pass("),
  "治理面数据面模块被删"
);
check(
  "bid.gates 走 DomainStore 直读（gate_approved / agent_gate_passes / human_review_complete 同源）",
  bidRs.includes("gate_approved") && bidRs.includes("agent_gate_passes") && bidRs.includes("human_review_complete"),
  "门状态被第二套实现取代（必须读域层真源）"
);
check(
  "bid.gate_pass 走宿主签发面 + 真实工具面（#182 receipt → record_review_gate）",
  bidRs.includes("issue_approval_receipt") && bidRs.includes("review_gate_scope") && bidRs.includes("record_review_gate"),
  "receipt 签发链被绕过（Agent 可伪造面）"
);
check(
  "ipc.rs 分发 bid.gates / bid.gate_pass",
  /"bid\.gates" => crate::bid::gates\(/.test(ipcRs) && /"bid\.gate_pass" => crate::bid::gate_pass\(/.test(ipcRs),
  "治理面命令没接进 IPC 分发"
);
check(
  "selftest 覆盖 bid.gates / bid.gate_pass（五门台账 + 人工过门）",
  bidRs.includes("gates_clean_not_found_without_db") && bidRs.includes("gate_pass_full_flow_with_host_receipt"),
  "壳侧单测面被删"
);

// ---------- app.js：#603 批 A——审核门面板接线 ----------
check(
  "数据面调用 bid.gates（真实 IPC）+ 写面 bid.gate_pass",
  /ipc\("bid\.gates", \{\}, 15e3\)/.test(app) && /ipc\("bid\.gate_pass", body, 3e4\)/.test(app),
  "审核门 IPC 调用被删或改形"
);
check(
  "演示桥补 bid.gates / bid.gate_pass stub（同形响应 + 可变台账）",
  /case "bid\.gates":/.test(app) && /case "bid\.gate_pass":/.test(app) && /demoGatePass/.test(app),
  "演示模式面板会空转"
);
check(
  "工作台「审核门」页签接线（data-bid-panel=gates）",
  /data-bid-panel="gates">审核门</.test(app),
  "页签被删或未接线"
);
check(
  "门台账不依赖章节树（大纲未建立分支也渲染 gates 面板）",
  /if \(activePanel === "gates"\) renderBidGatesPanel\(host\);/.test(app),
  "早期项目看不到门台账"
);
check(
  "五门台账渲染 + 追认清单 + 过门/拒审动作",
  /data-gt-ratify=/.test(app) && /data-gt-open=/.test(app) && /data-gt-confirm=/.test(app) && /passBidGate\(/.test(app),
  "治理面交互被删"
);
check(
  "拒审必须携带 BLOCKER 发现（前端预检 + 域层兜底）",
  /拒审必须填写 BLOCKER 发现/.test(app),
  "拒审依据门被绕过"
);
check(
  "侧栏「审核门」入口直达工作台（workbench-gates）",
  /data-bid-act="workbench-gates"/.test(app) && /openBidWorkbench\("gates"\)/.test(app),
  "侧栏入口未接线"
);
check(
  "门台账懒加载 + 工作台刷新联动（refresh-gates）",
  /loadBidGates\(true\)/.test(app) && /refresh-gates/.test(app),
  "台账刷新链断了"
);
check(
  "工作区切换时治理面状态随根失效",
  /state\.bidGates = \{ status: "idle"/.test(app),
  "旧工作区门台账会残留"
);

// ---------- styles.css：#603 批 A 审核门面板样式 ----------
for (const sel of [".bid-gt ", ".bid-gt-head", ".bid-gt-badge", ".bid-gt-row", ".bid-gt-form", ".bid-gt-ratify-row", ".bid-gt-rev"]) {
  check(
    `styles.css 提供 ${sel.trim()} 样式`,
    css.includes(sel),
    "面板样式被删"
  );
}
check(
  "审核门面板响应式断点（1440 / 1920）",
  /@media \(max-width: 1440px\)[\s\S]{0,300}\.bid-gt[\s\S]{0,200}@media \(min-width: 1920px\)[\s\S]{0,200}\.bid-gt/.test(css),
  "响应式被删"
);

// ---------- 契约：IPC-CONTRACT.md 登记（批 C + #603 批 A） ----------
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
check(
  "契约文档登记 bid.gates / bid.gate_pass（#603 批 A）",
  contract.includes("### bid.gates") && contract.includes("### bid.gate_pass"),
  "治理面命令没进契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);

// ---------- #19：导入向导（空态引导卡——新建项目 + 导入文件） ----------
check(
  "#19 壳侧：bid.rs 实现 create_project / import_files 写面",
  /pub fn create_project\(/.test(bidRs) && /pub fn import_files\(/.test(bidRs),
  "写面函数被删/改名"
);
check(
  "#19 壳侧：ipc.rs 注册 bid.create_project / bid.import_files",
  ipcRs.includes('"bid.create_project" => crate::bid::create_project') &&
    ipcRs.includes('"bid.import_files" => crate::bid::import_files'),
  "UI 接了壳没接（分发表缺登记）"
);
check(
  "#19 壳侧：经 dispatch_with 走真实工具面（create_bid_project / import_tender_files）",
  bidRs.includes('"create_bid_project".to_string()') &&
    bidRs.includes('"import_tender_files".to_string()'),
  "写面绕开工具面 = 与 bid-mcp-stdio 两套裁决"
);
check(
  "#19 壳侧：E_PARTIAL 转成功面 + partial 分账（不是故障）",
  /EPartial[\s\S]{0,900}o\.insert\("partial"/.test(bidRs),
  "部分成功被当错误回——向导无法同屏呈现成功件/失败件"
);
check(
  "#19 壳侧：空工作区起步 ensure_or_open（无 db.json 不再 not_found）",
  /fn ensure_or_open/.test(bidRs) && /ensure_or_open\(&mut guard, ws\)/.test(bidRs),
  "create_project 走了只读面的干净拒绝路径"
);
check(
  "#19 壳侧：quick_stats 补 files 计数（判「DRAFT 且未导入」用）",
  bidRs.includes('"files".into()'),
  "导入卡判据缺数据面"
);
check(
  "#19 壳侧：全链集成测试在场（空态→建项→幂等→导入→状态推进）",
  bidRs.includes("fn wizard_create_and_import_roundtrip_19"),
  "向导回归门被删"
);
check(
  "#19 UI：ipc 调用 bid.create_project / bid.import_files（真实命令名）",
  /ipc\("bid\.create_project", \{/.test(app) && /ipc\("bid\.import_files", \{/.test(app),
  "命令名漂移（壳注册与 UI 调用对不上）"
);
check(
  "#19 UI：向导三渲染函数（创建卡 / 导入卡 / 结果面）",
  /function renderBidWizardCreate\(/.test(app) &&
    /function renderBidWizardImport\(/.test(app) &&
    /function renderBidWizardResult\(/.test(app),
  "向导渲染被删/改名"
);
check(
  "#19 UI：工作台空态分支进向导（不再死胡同错误页）",
  /if \(!b\.present\) \{[\s\S]{0,300}renderBidWizardCreate\(treeEl\)/.test(app),
  "空工作区回到错误横幅（§109 引导卡口径被回退）"
);
check(
  "#19 UI：DRAFT 且未导入 → 导入卡（quick_stats.files 判据）",
  /st19 === "DRAFT" && !\(q19\.files > 0\)/.test(app),
  "导入卡判据被改（状态机口径漂移）"
);
check(
  "#19 UI：kind 清单 + 扩展名白名单（契约 §2 同源）",
  app.includes('var BID_FILE_KINDS = ["招标文件", "附件", "图纸", "补遗", "答疑", "评分办法", "格式模板"];') &&
    app.includes('var BID_IMPORT_EXTS = /\\.(docx|xlsx|pdf|doc|ods)$/i;'),
  "kind 合法值/可解析扩展名漂移"
);
check(
  "#19 UI：upload_ref 用工作区相对路径 + filename 显式回显",
  /upload_ref: rel, filename: f\.name, kind: sel\[rel\]/.test(app),
  "导入参数形状漂移（壳侧围栏锚定依赖 rel 形态）"
);
check(
  "#19 演示桥：两写面 stub 在场（浏览器预览不报未知命令）",
  /case "bid\.create_project":/.test(app) && /case "bid\.import_files":/.test(app),
  "演示模式向导死路"
);
for (const sel of [".bid-wiz-card", ".bid-wiz-file", ".bid-table"]) {
  check(
    `#19 样式：styles.css 提供 ${sel.trim()} 样式`,
    css.includes(sel),
    "向导样式被删"
  );
}
check(
  "#19 契约：IPC-CONTRACT.md 登记两写面命令",
  contract.includes("### bid.create_project") && contract.includes("### bid.import_files"),
  "写面命令没进契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);
check(
  "#19 契约：bid.state 的 quick_stats 登记 files 计数",
  /"files": 4,\s*\/\/ #19/.test(contract),
  "files 计数没进契约样例"
);

// ---------- R3（#47）：导入结果反馈面——partial 分账明细 ----------
check(
  "R3 UI：partial 三源合取（壳侧标记 / FAILED 行 / totals.parse_failed）",
  /const partial = !!r\.partial \|\| failedRows\.length > 0 \|\| \(totals\.parse_failed \|\| 0\) > 0;/.test(app),
  "部分成功判据回退到单一来源（演示桥/真实壳任一形态点不亮）"
);
check(
  "R3 UI：摘要计数条（成功/失败/已存在 + 部分成功口径）",
  /bid-wiz-summary/.test(app) && /成功 " \+ okCount \+ " 件/.test(app) && /失败 " \+ failedRows\.length \+ " 件/.test(app),
  "分账计数条被删（R1 的 item_errors 单行拼接回归）"
);
check(
  "R3 UI：失败清单结构化（bid-wiz-fails 逐条独立行 + 全程禁引口径）",
  /bid-wiz-fails/.test(app) && /全程禁引——补遗\/条款抽取\/评分都不会引用/.test(app) && /bid-wiz-fail-row/.test(app),
  "失败清单退回 <br> 拼接或口径文案丢失"
);
check(
  "R3 UI：部分成功不是故障——成功件不回滚口径在场",
  app.includes("部分成功不是故障——成功件照常入库不回滚，失败件全程禁引"),
  "口径文案漂移（向导会把部分成功当故障渲染）"
);
check(
  "R3 演示桥：损坏件教学面（partial:true + item_errors + FAILED 行同形）",
  /\/损坏件\/\.test/.test(app) && /out\.partial = true;/.test(app) && /out\.item_errors = brokenFl\.map/.test(app),
  "演示桥无法教学部分成功面（真实壳 partial 形态无演示对照）"
);
check(
  "R3 演示桥：损坏件失败行 0 页 0 块（成功面不被失败件污染计数）",
  /pages: broken \? 0 : 12/.test(app) && /chunks: broken \? 0 : 48/.test(app) && /chunks: fl\.reduce\(\(s, f\) => s \+ f\.chunks, 0\)/.test(app),
  "totals 计数被失败件污染（chunks 虚高）"
);
check(
  "R3 样式：bid-wiz-summary / bid-wiz-fails 提供 ok|warn 双态",
  /\.bid-wiz-summary\[data-state="warn"\]/.test(css) && /\.bid-wiz-fails summary/.test(css),
  "分账样式缺失"
);

// ---------- R4（#47）：向导完成态首屏 + 会话态生命周期 ----------
check(
  "R4 UI：switchWorkspace 重置向导会话态（result 不跨工作区泄漏）",
  /async switchWorkspace\(p0\) \{[\s\S]{0,3000}state\.bidWizard = \{/.test(app),
  "旧工作区导入现场（result/sel/files）泄漏到新工作区——「文件已入库」错挂新项目"
);
check(
  "R4 UI：完成态卡渲染函数 renderBidWizardDone（重开工作区场景）",
  /function renderBidWizardDone\(/.test(app),
  "重开工作区后右面板无完成态首屏"
);
check(
  "R4 UI：完成态卡数据面 = bid.state quick_stats 同源（files/requirements/evidence/pages_estimate）",
  /q\.files \|\| 0/.test(app) && /q\.requirements \|\| 0/.test(app) && /q\.pages_estimate \|\| 0/.test(app) && /q\.evidence \|\| 0/.test(app),
  "完成态卡造数或字段漂移（quick_stats 是唯一真源）"
);
check(
  "R4 UI：已导入未建纲分支（q19.files > 0 && 无向导现场 → 完成态卡）",
  /\} else if \(q19\.files > 0\) \{[\s\S]{0,600}renderBidWizardDone\(panelEl19, b\)/.test(app),
  "重开工作区回到泛泛「大纲未建立」占位（完成态分支被删）"
);
check(
  "R4 UI：完成态优先级——刚导入现场（result）仍走逐件表",
  /else if \(state\.bidWizard\.result\) \{[\s\S]{0,500}renderBidWizardResult\(panelEl19, state\.bidWizard\.result\)/.test(app),
  "完成态卡盖掉刚导入的逐件结果（现场信息降级）"
);

// ---------- R5（#47 / #19 任务 2）：coverage 早态引导对齐向导交互语言 ----------
// R6（#47 / #19 任务 3）：coverage 两分支收编共享工厂 renderBidEarlyGuide 后，
// 断言改写为收编形态（强度不减：not_found / state 双卡 + CTA 文案 + 切页签
// + next 条，锚点统一为工厂的 data-bid-guide-cta / -retry）。
check(
  "R5 UI：coverage E_NOTFOUND 引导卡（空工作区不再走错误横幅）",
  /cv\.code === "not_found"[\s\S]{0,500}renderBidEarlyGuide\(host, panel, \{[\s\S]{0,500}code: "not_found"[\s\S]{0,400}还没有标书项目/.test(app),
  "空工作区（无 db.json）被渲染成「覆盖报告读取失败」——正常空态当故障（§109 口径违背）"
);
check(
  "R5 UI：coverage E_STATE 引导卡主行动「去导入招标文件」（直通向导第二步）",
  /cv\.code === "state"[\s\S]{0,500}renderBidEarlyGuide\(host, panel, \{[\s\S]{0,500}覆盖报告尚未开放/.test(app),
  "早态卡只有「重新检查」死文案（#19 任务 2 的对齐目标缺失）"
);
check(
  "R5 UI：去导入/去建项按钮切回 detail 页签（向导所在页）",
  /data-bid-guide-cta[\s\S]{0,400}t\.meta\.panel = "detail";[\s\S]{0,120}renderBidWorkbenchPanes\(host\)/.test(app),
  "CTA 按钮不切页签（用户找不到向导入口）"
);
check(
  "R5 UI：早态卡带 bid-cov-next「下一步」条（与结果面同款交互语言）",
  /o\.next \? '<div class="bid-cov-next" data-state="ok"><span>下一步<\/span>' \+ o\.next/.test(app),
  "早态引导缺「下一步」条（交互语言未对齐）"
);

// ---------- R6（#47 / #19 任务 3）：E_NOTFOUND/E_STATE 引导卡约定统一 + IPC-CONTRACT 登记 ----------
check(
  "R6 UI：共享引导卡工厂在场（CTA 文案按 code 推导——单一真源）",
  /function renderBidEarlyGuide\(host, panel, opts\)[\s\S]{0,600}const cta = isNotFound \? "去新建标书项目" : "去导入招标文件";/.test(app),
  "各面板手写引导卡（文案漂移无单源——约定未统一）"
);
check(
  "R6 UI：工厂卡片不带 data-kind=error（空态不是故障）+ 次「重新检查」锚点统一",
  /data-bid-guide-cta>' \+ cta \+ '<\/button> <button class="btn" data-bid-guide-retry>重新检查<\/button>/.test(app)
  && !/data-kind="error"[\s\S]{0,300}data-bid-guide-cta/.test(app),
  "引导卡带错误横幅样式（空态渲染成故障——契约 §3.4 违背）"
);
check(
  "R6 UI：matrix 记错误码（对齐 coverage/gates——面板才能分支引导卡）",
  /state\.bid\.matrix\.code = \(err && err\.code\) \|\| ""/.test(app)
  && /matrix: \{ status: "idle", data: null, error: "", code: "" \}/.test(app),
  "loadBidMatrix 只记 message（mx.code 恒空——not_found/state 永远一把抓成故障横幅）"
);
check(
  "R6 UI：matrix 面板 E_NOTFOUND/E_STATE 双分支引导卡（不再一把抓错误横幅）",
  /mx\.code === "not_found" \|\| mx\.code === "state"[\s\S]{0,700}renderBidEarlyGuide/.test(app),
  "矩阵未建（DRAFT 主路径）与真故障（io）共用「矩阵读取失败」横幅"
);
check(
  "R6 UI：quality 面板 not_found 分支收编引导卡（原「不是标书项目」错误横幅退役）",
  /q\.code === "not_found"[\s\S]{0,500}renderBidEarlyGuide/.test(app),
  "自评面板空工作区仍走 data-kind=error 横幅（§109 引导卡约定违背）"
);
check(
  "R6 UI：quality 面板 state 分支收编引导卡（E_STATE 原文 + hint 进卡不吞）",
  /q\.code === "state"[\s\S]{0,500}renderBidEarlyGuide\(host, panel, \{[\s\S]{0,400}MATRIX_READY[\s\S]{0,300}prepare_outline_and_matrix/.test(app),
  "自评早态卡丢「矩阵就绪后显示什么」与后继管线信息"
);
check(
  "R6 UI：gates 面板 not_found 分支引导卡（注释口径「只在无 db.json 分支引导」落地）",
  /gt\.code === "not_found" \|\| gt\.code === "state"[\s\S]{0,700}renderBidEarlyGuide/.test(app),
  "门台账注释说分支引导、代码一把抓 error 横幅（注释与实现背离）"
);
check(
  "R6 契约：IPC-CONTRACT §3.4 引导卡约定登记（锚点 + 工厂 + 双码口径）",
  /### 3\.4 引导卡约定（E_NOTFOUND \/ E_STATE 的 UI 呈现规范；#47 R6 \/ #19 任务 3）/.test(contract)
  && /data-bid-guide-cta/.test(contract) && /renderBidEarlyGuide/.test(contract)
  && /去新建标书项目/.test(contract) && /去导入招标文件/.test(contract),
  "引导卡约定散在 §109 表格一行 + 注释里，契约文档无正式登记（改代码无同步锚点）"
);

// ---------- R6 merge main（#47 / #19 任务 3 收编 export 面）：#18 出口闭环面板引导卡统一 ----------
check(
  "R6 收编：export 面（#18）not_found 分支进共享工厂（原错误横幅退役）",
  /x\.code === "not_found"[\s\S]{0,500}renderBidEarlyGuide/.test(app),
  "#18 校验面板空工作区仍走 data-kind=error 横幅（契约 §3.4 面板清单违背）"
);
check(
  "R6 收编：export 面（#18）state 分支进共享工厂（E_STATE 原文 + 双前置门 hint 进卡）",
  /x\.code === "state"[\s\S]{0,600}renderBidEarlyGuide\(host, panel, \{[\s\S]{0,500}pre_export_confirm[\s\S]{0,200}校验并导出成品/.test(app),
  "#18 校验早态卡丢双前置门说明或后继管线信息"
);
check(
  "R6 契约：§3.4 面板清单含 export（merge main 后 #18 面板纳入约定）",
  /detail \/ matrix \/ quality \/ gates \/ coverage \/ export/.test(contract),
  "契约 §3.4 面板清单漏 export 面（merge main 新增面板未纳入约定）"
);

// ---------- R7（#47）：向导重入——半完成态（DRAFT 0 文件）重开工作台的新鲜度 ----------
check(
  "R7 UI：重开工作台半完成态 → 双源重拉（bid.state 强制 + 文件列表重置 idle 自动重拉）",
  /bR7\.status === "ready" && pR7\.status === "DRAFT" && !\(qR7\.files > 0\)[\s\S]{0,250}state\.bidWizard\.treeStatus = "idle"[\s\S]{0,120}ui\.loadBid\(true\)/.test(app),
  "重开工作台沿用旧文件列表（壳外新放的招标文件不可见——重入语义缺失，只能手点刷新）"
);
check(
  "R7 UI：文件列表重置只动 ready 态（loading/error 不打断）",
  /if \(state\.bidWizard\.treeStatus === "ready"\) state\.bidWizard\.treeStatus = "idle";/.test(app),
  "重置不分态——进行中拉取被误清白跑 / error 提示丢失"
);
check(
  "R7 merge 热修：openBidWorkbench 单一定义（merge main 双版本收编）",
  (app.match(/async openBidWorkbench\(panel\) \{/g) || []).length === 1,
  "openBidWorkbench 双定义（JS 后定义静默覆盖前定义——单一真源违背，merge 冲突残留）"
);


// ---------- R8（#47 / #19 拖拽导入）：drop 事件接入向导第二步 ----------
check(
  "R8 壳侧：bid.ingest_drop 注册（ipc.rs 分发——UI 调用不经 unknown_cmd）",
  /"bid\.ingest_drop" => crate::bid::ingest_drop\(&ws, &self\.bid, &a\)/.test(ipcRs),
  "拖拽落位命令没进壳侧分发表——UI ingestDroppedBidFiles 调用必 unknown_cmd"
);
check(
  "R8 壳侧：ingest_drop 幂等 + 冲突后缀 + 白名单守卫（单测在场）",
  /fn ingest_drop_copies_idempotent_and_guards\(\)[\s\S]{0,2600}already_present[\s\S]{0,800}招标文件-2\.docx/.test(bidRs),
  "拖拽落位单测缺失（幂等/后缀/守卫回归无门）"
);
check(
  "R8 UI：onDrop 向导半完成态接住拖入招标文件（BID_IMPORT_EXTS 分拣 + ingestDroppedBidFiles）",
  /onDrop\(paths\) \{[\s\S]{0,700}BID_IMPORT_EXTS\.test\(base\(x\)\)[\s\S]{0,200}ui\.ingestDroppedBidFiles\(bidPaths\)/.test(app),
  "壳拖入的招标文件在半完成态仍走 openPath 打开为 tab（拖拽导入接线断裂）"
);
check(
  "R8 UI：ingestDroppedBidFiles 落位后重拉列表 + 新落位件自动勾选 + toast 分账",
  /async ingestDroppedBidFiles\(paths\) \{[\s\S]{0,700}ipc\("bid\.ingest_drop"[\s\S]{0,500}state\.bidWizard\.sel\[c\.rel\] = guessBidFileKind\(c\.rel\)[\s\S]{0,300}已落位/.test(app),
  "落位后不重拉列表/不自动勾选/静默吞 skipped（拖到落位断链）"
);
check(
  "R8 UI：浏览器 drop（无源路径）诚实引导——不装作导入成功",
  /浏览器拖放拿不到文件源路径——把 " \+ f\.name/.test(app),
  "浏览器 drop 的招标文件被静默吞掉或装作导入成功（拿不到路径的事实没说清）"
);
check(
  "R8 契约：bid.ingest_drop 登记（IPC-CONTRACT 唯一权威）",
  contract.includes("### bid.ingest_drop") && /already_present/.test(contract),
  "拖拽落位命令没进契约（落位规则/幂等口径无登记）"
);


// ---------- R9（#47 跨平台硬化①）：upload_ref 分隔符归一（壳侧入口单一真源） ----------
check(
  "R9 壳侧：import_files 入口归一（normalize_upload_ref 接入 + 空段/· 段过滤）",
  /fn normalize_upload_ref\(raw: &str\) -> String[\s\S]{0,700}seg != "\."[\s\S]{0,300}\.join\("\/"\)/.test(bidRs)
  && /let upload_ref = normalize_upload_ref\(upload_ref_raw\);/.test(bidRs),
  "Windows 形态 upload_ref 在 Linux 壳被当单文件名（找不到真文件）；两形态 rel 不一致 → sha 幂等去重失效双入库"
);
check(
  "R9 壳侧：归一不吞 .. 段（穿越裁决仍在域层 fs_fence）+ 绝对路径不压缩",
  /normalize_upload_ref\("a\/\.\.\/b\.docx"\), "a\/\.\.\/b\.docx"/.test(bidRs)
  && /normalize_upload_ref\("C:\\\\ws\\\\x\.docx"\), "C:\/ws\/x\.docx"/.test(bidRs),
  "归一吞 .. 会把 a/../b 错误归一成 a/b（开穿越洞）；绝对路径压缩会破坏绝对语义"
);
check(
  "R9 壳侧：两形态同 sha 幂等单测在场（\ 导入 + / 重放不双入库）",
  /fn upload_ref_separator_normalized_and_idempotent[\s\S]{0,2000}deduplicated[\s\S]{0,600}库内仍只 1 件/.test(bidRs),
  "分隔符归一幂等回归无门（两形态双入库回退无拦）"
);
check(
  "R9 契约：import_files 分隔符归一口径登记",
  /分隔符归一（#47 R9 跨平台硬化①，壳侧入口单一真源）/.test(contract),
  "归一规则没进契约（调用方无从知道两形态等价）"
);

// ---------- #18 出口闭环：校验报告 + 确认导出 ----------
check(
  "#18 工作台头部「校验并导出」按钮（validate-export 动作）",
  /data-bid-act="validate-export"/.test(app) && /校验并导出/.test(app),
  "出口动作入口被删或改名"
);
check(
  "#18 「校验与导出」页签（data-bid-panel=export）",
  /data-bid-panel="export">校验与导出/.test(app),
  "出口页签被删或改名"
);
check(
  "#18 renderBidExportPanel 分发（树空 / 主体两路）",
  (app.match(/renderBidExportPanel\(host\)/g) || []).length >= 3,
  "面板路由断裂——页签点开不渲染（树空引导 + 主体 + 面板函数定义至少 3 处引用）"
);
check(
  "#18 bid.validate IPC 调用 + 状态面",
  /ipc\("bid\.validate", \{\}, 12e4\)/.test(app) && /bidExport: \{/.test(app),
  "校验拉取或状态面被回退"
);
check(
  "#18 bid.export IPC 调用（format + output_path + dark_bid）",
  /ipc\("bid\.export", body, 3e5\)/.test(app) && /output_path: path/.test(app),
  "导出写面接线被回退"
);
check(
  "#18 产物回显（artifact.url/sha256/size）+ explorer.reveal 定位",
  /x\.done\.artifact && x\.done\.artifact\.url/.test(app) && /ipc\("explorer\.reveal", \{ path: url \}, 15e3\)/.test(app),
  "产物回显或定位接线被回退"
);
check(
  "#18 E_STATE 引导卡分支（state 码 → 校验尚未开放 / 导出被前置门拦截）",
  /校验尚未开放/.test(app) && /导出被前置门拦截/.test(app),
  "state 码分支引导卡被删——退回错误横幅即违规（契约 §3.3）"
);
check(
  "#18 侧栏「校验与导出」入口",
  /data-bid-act="validate-export">.*校验与导出/.test(app.replace(/\n/g, "")) || (app.includes('data-bid-act="validate-export"') && app.includes("缺陷清单 · 确认导出 · 产物定位")),
  "侧栏入口被删"
);
check(
  "#18 壳侧分发：ipc.rs 登记 bid.validate / bid.export（经 bid.rs 真实处理）",
  /"bid\.validate" => crate::bid::validate\(&ws, &self\.bid, &a\)/.test(ipcRs)
    && /"bid\.export" => crate::bid::export\(&ws, &self\.bid, &a\)/.test(ipcRs),
  "壳侧 IPC 分发缺命令——UI 调用会 unknown_cmd"
);
check(
  "#18 bid.rs 走真实工具面（dispatch_with validate_bid_document / export_bid_document）",
  /tool: "validate_bid_document"/.test(bidRs) && /tool: "export_bid_document"/.test(bidRs),
  "壳侧没经 bid_mcp 真实工具面（直读 DomainStore 或空实现即违规）"
);
check(
  "#18 契约文档登记 bid.validate / bid.export",
  contract.includes("### bid.validate") && contract.includes("### bid.export"),
  "出口闭环命令没进契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);
check(
  "#18 导出面板样式（bid-export 表单 + 产物路径）",
  /\.bid-export-form/.test(css) && /\.bid-export-path/.test(css),
  "导出面板样式被删"
);

// ---------- 壳侧：IPC 命令真实在场（#603 批 C：补遗豁免） ----------
check(
  "mang-app bid.rs 提供 addenda / addendum_waiver / no_addendum_confirm",
  bidRs.includes("pub fn addenda(") && bidRs.includes("pub fn addendum_waiver(") && bidRs.includes("pub fn no_addendum_confirm("),
  "补遗豁免三面模块被删"
);
check(
  "bid.addenda 走 DomainStore+readiness 直读（addendum_statuses / addendum_waivers 同源）",
  bidRs.includes("bid_tools::readiness::addendum_statuses") && bidRs.includes("addendum_waivers()"),
  "补遗状态被第二套实现取代（必须读域层真源）"
);
check(
  "两写面走宿主签发 + 真实工具面（#182 签域分账：addendum_waiver:{file_id} / no_addendum_confirmed）",
  bidRs.includes("addendum_waiver_scope") && bidRs.includes("no_addendum_confirmed_scope") && bidRs.includes("record_addendum_waiver"),
  "receipt 签发链被绕过或两语义未分账"
);
check(
  "ipc.rs 分发 bid.addenda / bid.addendum_waiver / bid.no_addendum_confirm",
  /"bid\.addenda" => crate::bid::addenda\(/.test(ipcRs) && /"bid\.addendum_waiver" => crate::bid::addendum_waiver\(/.test(ipcRs) && /"bid\.no_addendum_confirm" => crate::bid::no_addendum_confirm\(/.test(ipcRs),
  "补遗面命令没接进 IPC 分发"
);
check(
  "壳侧单测覆盖补遗面（无 db 干净拒 + 全局确认全链 + gates 对账）",
  bidRs.includes("addendum_faces_clean_not_found_without_db") && bidRs.includes("no_addendum_confirm_full_flow"),
  "壳侧单测面被删"
);

// ---------- app.js：#603 批 C——补遗豁免面接线 ----------
check(
  "读面调用 bid.addenda + 两写面 bid.addendum_waiver / bid.no_addendum_confirm（真实 IPC）",
  /ipc\("bid\.addenda", \{\}, 15e3\)/.test(app) && /ipc\("bid\.addendum_waiver", \{ file_id: fileId, reason: reason \}, 3e4\)/.test(app) && /ipc\("bid\.no_addendum_confirm", \{ reason: reason \}, 3e4\)/.test(app),
  "补遗面 IPC 调用被删或改形"
);
check(
  "两补遗门真按钮接线（逐件确认 / 确认无补遗——替掉批 A 占位符）",
  !/bid-gt-batchc/.test(app) && /data-gt-aw-toggle/.test(app) && /data-gt-na-toggle/.test(app),
  "占位符残留或按钮未接线"
);
check(
  "逐件确认列表（不就绪件 + 内联理由 + 已确认审计）",
  /function bidGtAwListHtml/.test(app) && /data-aw-reason=/.test(app) && /data-aw-confirm=/.test(app) && /已确认台账（审计面——放行后不消失）/.test(app),
  "逐件列表被删"
);
check(
  "全局无补遗确认表单（#379 语义引导 + 理由必填）",
  /function bidGtNaFormHtml/.test(app) && /data-na-reason/.test(app) && /data-na-confirm/.test(app) && /仅适用于「未发现补遗/.test(app),
  "全局确认表单被删"
);
check(
  "理由必填前端预检（与域层同口径——不可审计的确认不成确认）",
  /确认理由必填（不可审计的确认不成确认）/.test(app),
  "空白理由会被放行"
);
check(
  "豁免后台账/门台账/侧栏三处同源刷新",
  /ui\.loadBidAddenda\(true\)/.test(app) && /waiveBidAddendum/.test(app) && /confirmNoAddendum/.test(app),
  "写面生效后面板不刷新"
);
check(
  "工作区切换时补遗面状态随根失效",
  /state\.bidAddenda = \{ status: "idle"/.test(app),
  "旧工作区补遗台账会残留"
);
check(
  "演示桥补三命令 stub + 可变台账（waiver 真改演示态 + #379 诚实拒）",
  /case "bid\.addenda":/.test(app) && /demoAddendumWaiver/.test(app) && /demoNoAddendumConfirm/.test(app) && /与事实矛盾/.test(app),
  "演示模式补遗面会空转或假成功"
);

// ---------- styles.css：#603 批 C 补遗豁免面样式 ----------
for (const sel of [".bid-gt-aw ", ".bid-gt-aw-row", ".bid-gt-aw-name", ".bid-gt-aw-actions", ".bid-gt-aw-audit"]) {
  check(
    `styles.css 提供 ${sel.trim()} 样式`,
    css.includes(sel.trim()),
    "补遗面样式被删"
  );
}

// ---------- 契约：IPC-CONTRACT.md 登记（#603 批 C） ----------
check(
  "契约文档登记 bid.addenda / bid.addendum_waiver / bid.no_addendum_confirm（#603 批 C）",
  contract.includes("### bid.addenda") && contract.includes("### bid.addendum_waiver") && contract.includes("### bid.no_addendum_confirm"),
  "补遗面命令没进契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);

// ---------- #21 e2e 骨架（静态面）：漏参防御 + 套件纳入 ----------
check(
  "#21 矩阵页签分发双参调用（漏传 panel = 运行时 TypeError——e2e 首跑捕获的存量 bug 形态）",
  /renderBidMatrixPanel\(host, mxPanel\);/.test(app) && !/\brenderBidMatrixPanel\(host\);/.test(app),
  "renderBidMatrixPanel(host) 单参调用又在场——函数签名是 (host, panel)，漏参必崩"
);
check(
  "#21 e2e 套件在场（run-all glob 自动纳入）",
  readFileSync(join(ROOT, "web-ui", "tests", "bid-e2e.test.mjs"), "utf8").length > 0,
  "tests/bid-e2e.test.mjs 被删——运行时断链门消失"
);

// ---------- R10（#47 平台区分③）：基名跨平台守卫（Win 保留名/非法字符） ----------
check(
  "R10 壳侧：guard_portable_basename 三判据（保留名/非法字符/尾点空格）",
  /pub fn guard_portable_basename\(name: &str\) -> Result<\(\), String> \{[\s\S]{0,900}"COM1" \| "COM2"/.test(pathsRs) && /ends_with\(' '\) \|\| name\.ends_with\('\.'\)/.test(pathsRs),
  "守卫函数被删或判据缺角（基名跨 Windows 迁移失效）"
);
check(
  "R10 壳侧：ingest_drop 分账口径（name_not_portable 一件非法不毁整批）",
  /reason": "name_not_portable"/.test(bidRs),
  "拖拽批次保留名件被当整批错误回（或直接落位）"
);
check(
  "R10 壳侧：import_files 请求级 bad_args（upload_ref 基名 + filename 双查）",
  /for what in \[upload_ref, filename\.as_str\(\)\] \{[\s\S]{0,400}guard_portable_basename/.test(bidRs),
  "导入守卫缺角（显式 filename 或 upload_ref 基名单查漏一面）"
);
check(
  "R10 测试：守卫表驱动单测 + import_files 拒绝零副作用集成",
  /fn guard_portable_basename_table/.test(pathsRs) && /fn import_files_rejects_non_portable_basename/.test(bidRs),
  "守卫回归门被删"
);
check(
  "R10 selftest：保留名守卫双项（ingest 分账 + import bad_args）",
  selftestRs.includes("bid.ingest_drop(保留名守卫)") && selftestRs.includes("bid.import_files(保留名基 bad_args)"),
  "集成自检项缺失"
);
check(
  "R10 契约：ingest_drop 节登记基名跨平台守卫（双平台同拒 + 分账/bad_args 口径）",
  contract.includes("基名跨平台守卫（R10") && contract.includes("双平台同拒"),
  "守卫口径没进契约（docs/mang/IPC-CONTRACT.md 是唯一权威）"
);

// ---------- R11（#47 平台区分④）：大小写不敏感同名去重 ----------
check(
  "R11 壳侧：occupied 闭包 CI 占位判定（精确名快路径 + read_dir 变体扫描；R13 增强为 NFC+CI 键）",
  /let occupied = \|want: &str\| -> Option<\(std::path::PathBuf, bool\)> \{[\s\S]{0,600}to_lowercase\(\) == lower/.test(bidRs),
  "落位判定退回精确名匹配（大小写变体放行——拷 Windows 互覆）"
);
check(
  "R11 壳侧：IngestSlot 枚举携带实际占位（Dup 指名不猜请求名）",
  /enum IngestSlot \{[\s\S]{0,120}Free\(std::path::PathBuf\),[\s\S]{0,120}Dup\(std::path::PathBuf\),/.test(bidRs) && /Ok\(IngestSlot::Dup\(slot\)\) => \{[\s\S]{0,600}占位 \{present_name\}/.test(bidRs),
  "already_present 回显指错占位（用请求名猜变体）"
);
check(
  "R11 测试：CI 去重集成（变体幂等不放行 + 异内容后缀占位 + 后缀位 CI）",
  /fn ingest_drop_case_insensitive_dedupe/.test(bidRs) && /招标文件-2\.DOCX/.test(bidRs),
  "CI 去重回归门被删"
);
check(
  "R11 selftest：大小写变体幂等项在场",
  selftestRs.includes("bid.ingest_drop(大小写变体幂等)"),
  "集成自检项缺失"
);
check(
  "R11 契约：大小写不敏感占位口径登记（Windows FS 语义预演）",
  contract.includes("大小写不敏感占位（R11") && contract.includes("NTFS upcase 折叠"),
  "CI 占位口径没进契约"
);

// ---------- R12（#47 平台区分⑤）：MAX_PATH 长路径预检 ----------
check(
  "R12 壳侧：guard_windows_max_path 边界（>259 拒，CJK 按字符计）",
  /pub fn guard_windows_max_path\(full: &str\) -> Result<\(\), String> \{[\s\S]{0,400}chars\(\)\.count\(\) > 259/.test(pathsRs) && /fn guard_windows_max_path_boundary/.test(pathsRs),
  "MAX_PATH 守卫被删或边界漂移"
);
check(
  "R12 壳侧：ingest_drop 落位预检（path_too_long 批次分账）",
  /reason": "path_too_long"/.test(bidRs),
  "超长落位路径被当错误整批回（或直接落位）"
);
check(
  "R12 壳侧：import_files rel 估算预检（请求级 bad_args——绝对取本体/相对取根+1+rel）",
  /upload_ref\.chars\(\)\.count\(\);[\s\S]{0,500}est > 259/.test(bidRs),
  "upload_ref 长度预检缺角（记录的 rel 在 Windows 解析失败）"
);
check(
  "R12 测试：深目录真驱动集成（40 层嵌套根 + import bad_args）",
  /fn ingest_drop_maxpath_guard/.test(bidRs) && /mang-maxpath/.test(bidRs),
  "MAX_PATH 回归门被删"
);
check(
  "R12 selftest：MAX_PATH 预检项在场",
  selftestRs.includes("bid.ingest_drop(MAX_PATH 预检)"),
  "集成自检项缺失"
);
check(
  "R12 契约：MAX_PATH 口径登记（双平台同拒 + 分账/bad_args 分野）",
  contract.includes("MAX_PATH 预检（R12") && contract.includes("LongPathsEnabled"),
  "MAX_PATH 口径没进契约"
);

// ---------- R13（#47 平台区分⑥）：NFC 归一（macOS NFD 互操作） ----------
check(
  "R13 壳侧：paths::nfc 助手 + 占位键 nfc 先于 lowercase（双形态同占位）",
  /pub fn nfc\(s: &str\) -> String \{[\s\S]{0,200}UnicodeNormalization/.test(pathsRs) && /crate::paths::nfc\(want\)\.to_lowercase\(\)/.test(bidRs) && /crate::paths::nfc\(&e\.file_name\(\)\.to_string_lossy\(\)\)\.to_lowercase\(\)/.test(bidRs),
  "占位键未 NFC 化（NFD/NFC 视觉同名两份——占位与幂等键错位）"
);
check(
  "R13 壳侧：ingest 落位名归一（净化后、守卫前——单一口径）",
  /let name = paths::nfc\(&raw_name\);/.test(bidRs),
  "落位名保留 NFD 形态（拷 Windows 后与 NFC 重名成幽灵重复）"
);
check(
  "R13 壳侧：import_files filename 归一 / upload_ref 原样（定位键不动）",
  /let filename = paths::nfc\(&filename\);/.test(bidRs) && /upload_ref 是\*\*定位键\*\*/.test(bidRs),
  "filename 显示名未归一（台账/检索分裂）或 upload_ref 被错误归一（找不到文件）"
);
check(
  "R13 测试：NFD→NFC 落位 + NFC 重拖占位幂等 + filename 归一集成",
  /fn ingest_drop_nfc_normalization/.test(bidRs) && /fn nfc_normalization_forms/.test(pathsRs),
  "NFC 回归门被删"
);
check(
  "R13 selftest：NFD 落位归一 + NFC 重拖幂等双项在场",
  selftestRs.includes("bid.ingest_drop(NFD 落位归一 NFC)") && selftestRs.includes("bid.ingest_drop(NFC 重拖占位幂等)"),
  "集成自检项缺失"
);
check(
  "R13 契约：NFC 归一口径登记（落位/占位键 NFC + upload_ref 原样的分野）",
  contract.includes("NFC 归一（R13") && contract.includes("定位键"),
  "NFC 口径没进契约"
);

// ---------- R14（#47 平台区分⑦）：混合分隔符矩阵（跨平台字符串基名） ----------
check(
  "R14 壳侧：paths::str_basename 双分隔符助手（最后非空段 + 回退原样）",
  /pub fn str_basename\(s: &str\) -> &str \{[\s\S]{0,220}s\.rsplit\(\['\/', '\\\\'\]\)[\s\S]{0,120}find\(\|seg\| !seg\.is_empty\(\)\)/.test(pathsRs),
  "跨平台字符串基名助手缺失或语义漂移（std Path::file_name 按平台解析——两侧答案分叉）"
);
check(
  "R14 壳侧：recent 台账 name 回退接 str_basename（Windows 形态路径两侧同答）",
  recentRs.includes("paths::str_basename(path)"),
  "recent.rs 回退仍走 Path::file_name（Unix 上 C:\\a\\b.md 整串当基名——跨机台账显示面分裂）"
);
check(
  "R14 壳侧：import_files filename 回退接 str_basename（跨平台字符串不走 std Path）",
  bidRs.includes("paths::str_basename(upload_ref)"),
  "import filename 回退仍走 Path::file_name（归一不变量未写死）"
);
check(
  "R14 UI：web-ui baseName 双分隔符（与壳侧 str_basename 同口径）",
  /Math\.max\(s\.lastIndexOf\("\/"\),\s*s\.lastIndexOf\("\\\\"\)\)/.test(app),
  "JS baseName 丢双分隔符口径（两侧分叉回潮）"
);
check(
  "R14 测试：归一深度矩阵 + cfg 双分支对照（paths.rs / bid.rs 双面）",
  /fn r14_mixed_separator_normalize_matrix/.test(bidRs)
    && /fn str_basename_dual_separator_matrix/.test(pathsRs)
    && /fn path_file_name_diverges_but_str_basename_is_platform_stable/.test(pathsRs),
  "R14 回归门被删（金样矩阵/平台对照测试缺失）"
);
check(
  "R14 测试：fs_fence 混合分隔符共享不变量 + cfg 双分支（Unix 字面名 / Windows 分隔词）",
  /fn mixed_separator_never_escapes_fence/.test(fenceTest)
    && /fn mixed_separator_unix_backslash_is_literal_character/.test(fenceTest)
    && /fn mixed_separator_windows_backslash_is_separator/.test(fenceTest),
  "围栏混合形态矩阵缺失（不逃逸不变量未锁定）"
);
check(
  "R14 selftest：Windows 形态 upload_ref 归一导入 + 两形态同件幂等双项在场",
  selftestRs.includes("bid.import_files(Windows 形态归一导入)")
    && selftestRs.includes("bid.import_files(两形态同件幂等)"),
  "集成自检项缺失"
);
check(
  "R14 契约：混合分隔符矩阵口径登记（str_basename 与守卫严格/宽松分野）",
  contract.includes("混合分隔符矩阵（R14") && contract.includes("str_basename"),
  "R14 口径没进契约"
);

console.log(`\n== ${pass} passed, ${fail} failed ==`);
process.exit(fail === 0 ? 0 : 1);
