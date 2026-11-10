#!/usr/bin/env node
// #21：五面板真实端到端测试（UI 驱动全链）。
//
// 用法（零依赖）：
//   node web-ui/tests/bid-e2e.test.mjs
//
// 架构（仿真宿主——「真实/仿真二选一」的仿真侧，先立骨架后扩面）：
//
//   node vm 里加载真实 web-ui/mang/app.js（file:// 形态 → 内置演示桥
//   自动生效，覆盖 bid.state/outline/matrix/quality/score/gates/
//   gate_pass/coverage；gate_pass 会真改演示台账——与真实壳同语义）
//     ↓
//   DOM shim（tests/helpers/mang-dom-shim.mjs）：innerHTML 开标签解析 +
//   querySelector 子集 + click() 走 app.js 真实 addEventListener 绑定
//     ↓
//   驱动层全部经真实代码路径：
//     boot()（真实启动——bridge.onEvent(onBridgeEvent) 在其尾部，是
//           ipc 往返的前提；宿主骨架元素预建后 shim 上可全程跑完）
//     ui.openBidWorkbench(panel)（= 侧栏按钮点击的处理器）
//     → renderBidWorkbenchView/Panes（真实渲染）
//     → ui.loadBidXxx()（真实 IPC 发出）
//     → demo 桥 post/respond（真实异步往返）
//     → onBridgeEvent → 状态面 → 重渲染（真实数据流）
//     → 断言：IPC 帧序列 + 面板 innerHTML 关键文本 + 台账可变数据
//
// 与静态断言门（bid-panels.test.mjs）的关系：那道门拦「改名回退」，本门
// 拦「运行时断链」（点击→IPC→渲染）。两道都跑，互不替代。
//
// 真实宿主扩展点：mang-app --selftest（IPC-CONTRACT §10 无窗口清单）覆盖
// Rust 侧真跑往返；有 Windows 环境后可把本骨架的驱动层换成 WebView2 注入
// （断言层不变）。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";
import { createDocument, ShimElement } from "./helpers/mang-dom-shim.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const APP_JS = join(ROOT, "web-ui", "mang", "app.js");

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
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(cond, label, timeoutMs = 4000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (cond()) return true;
    await sleep(25);
  }
  if (cond()) return true;
  console.error(`  ⏱ 等待超时：${label}`);
  return false;
}

// ---------- ① 沙箱：window/document + 宿主骨架（boot() 的挂点） ----------
const doc = createDocument();
const errLogs = [];
const sandbox = {};
const windowObj = {
  document: doc,
  location: { protocol: "file:", href: "file:///mang/index.html", host: "", origin: "null" },
  navigator: { userAgent: "mang-e2e-shim", language: "zh-CN", platform: "linux" },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() {},
  matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
  getComputedStyle: () => ({ getPropertyValue: () => "", overflowY: "auto" }),
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  innerWidth: 2048,
  innerHeight: 1152,
  devicePixelRatio: 1,
  scrollX: 0,
  scrollY: 0,
  localStorage: (() => {
    const store = {};
    return {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; }
    };
  })(),
  fetch: () => Promise.reject(new Error("e2e shim: fetch 不可用（演示桥全内联，不应走到）")),
  console: Object.assign({}, console, { error: (...a) => errLogs.push(a.join(" ")) })
};
windowObj.window = windowObj;
windowObj.parent = windowObj;
windowObj.self = windowObj;
Object.assign(sandbox, {
  window: windowObj,
  document: doc,
  navigator: windowObj.navigator,
  location: windowObj.location,
  localStorage: windowObj.localStorage,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  fetch: windowObj.fetch,
  console: windowObj.console,
  Math,
  Date,
  JSON,
  Promise,
  Object,
  Array,
  String,
  Number,
  Boolean,
  RegExp,
  Error,
  Set,
  Map,
  Uint8Array,
  isFinite,
  parseInt,
  parseFloat,
  encodeURIComponent,
  decodeURIComponent,
  URL,
  Uint16Array,
  Int32Array
});

// 宿主骨架元素（真实浏览器由 index.html + boot() 建；shim 预建——id 面
// 与 app.js 的 $("#...") / getElementById 枚举一致，boot() 才能全程跑完）
const HOST_IDS = [
  "activitybar", "menubar-menus", "window-controls", "btn-win-min", "btn-win-max",
  "btn-win-close", "tabs", "btn-tab-overflow", "panes", "empty", "statusbar",
  "status-left", "status-right", "sidebar", "sidebar-body", "sidebar-actions",
  "sidebar-workspace", "sidebar-resize", "btn-refresh-tree", "toasts", "overlay-root"
];
HOST_IDS.forEach((id) => {
  const el = doc.createElement("div");
  el.setAttribute("id", id);
  doc.body.appendChild(el);
});

// ---------- ② 加载真实 app.js（IIFE 自执行 → boot() 真实启动） ----------
let mang = null;
let loadError = null;
try {
  const src = readFileSync(APP_JS, "utf8");
  const ctx = vm.createContext(sandbox);
  vm.runInContext(src, ctx, { filename: "app.js" });
  mang = windowObj.__mang || null;
} catch (e) {
  loadError = e && e.stack || String(e);
}
check("e2e 前提：app.js 加载成功且 __mang 钩子在场（state/ui/ipc）",
  !!(mang && mang.state && mang.ui && mang.ipc),
  loadError ? String(loadError).slice(0, 300) : "__mang 未暴露");

if (mang) {
  const { state, ui } = mang;
  check("e2e 前提：演示桥生效（mode=demo——仿真宿主侧）",
    state.bridge && state.bridge.mode === "demo",
    "bridge.mode=" + (state.bridge && state.bridge.mode));

  // boot() 必须全程跑完（bridge.onEvent(onBridgeEvent) 在 boot 尾部——
  // 中断则 demo 桥响应无人收，所有 ipc 永挂）。
  const booted = await waitFor(() => state.booted === true, "boot() 完成");
  if (!booted && errLogs.length) {
    console.error("  boot 未完成——errLogs 尾部：");
    errLogs.slice(-3).forEach((l) => console.error("   ", l.slice(0, 200)));
  }
  check("e2e 前提：boot() 全程跑完（onEvent 注册——ipc 往返的前提）", booted,
    "boot 在 shim 上中断——需补 shim 的 DOM 面（见上方 errLogs）");

  // IPC 帧序列 spy（包一层 post——demo 桥真实方法保留）
  const frames = [];
  const rawPost = state.bridge.post.bind(state.bridge);
  state.bridge.post = (msg) => {
    frames.push(msg && msg.cmd);
    return rawPost(msg);
  };
  const frameHas = (cmd) => frames.indexOf(cmd) >= 0;

  const workbenchHost = () => {
    const panesEl = doc.getElementById("panes");
    if (!panesEl) return null;
    return panesEl.querySelector(".bid-wb") || null;
  };
  const panelHtml = () => {
    const h = workbenchHost();
    const p = h && h.querySelector("#bid-panel");
    return p ? p.innerHTML : "";
  };

  // ---------- ③ 面板一：gates 全链（点击→IPC→台账落库→刷新） ----------
  await ui.openBidWorkbench("gates");
  check("gates：页签打开（工作台骨架渲染）", !!workbenchHost(), "无 .bid-wb 宿主");
  await waitFor(() => state.bidGates.status === "ready" && panelHtml().indexOf("门台账") >= 0, "gates 台账渲染");
  check("gates：点击页签 → bid.gates IPC 帧发出", frameHas("bid.gates"), "帧序列：" + frames.join(","));
  check("gates：面板 DOM 渲染非空（台账 + 待追认清单）",
    panelHtml().indexOf("门台账") >= 0 && panelHtml().indexOf("待追认") >= 0,
    "innerHTML 片段：" + panelHtml().slice(0, 120));
  const beforeReviews = (state.bidGates.data && state.bidGates.data.reviews || []).length;
  const beforeWaivers = (state.bidGates.data && state.bidGates.data.agent_waivers || []).length;
  check("gates：初始台账有 agent 待追认门（e2e 素材在场）", beforeWaivers >= 1, "agent_waivers=" + beforeWaivers);

  // 点「追认」按钮（真实监听链：data-gt-ratify → ui.passBidGate → ipc）
  const host0 = workbenchHost();
  const ratifyBtn = host0 && host0.querySelector('[data-gt-ratify="matrix_approval"]');
  check("gates：追认按钮在场（matrix_approval 待追认）", !!ratifyBtn, "按钮未解析出");
  if (ratifyBtn) {
    ratifyBtn.click();
    const okPass = await waitFor(() => frameHas("bid.gate_pass") && state.bidGates.passInfo.indexOf("已过门") >= 0, "gate_pass 往返");
    check("gates：点击追认 → bid.gate_pass IPC 帧发出 → 演示台账落库", okPass && frameHas("bid.gate_pass"),
      "passInfo=" + state.bidGates.passInfo + " 帧：" + frames.join(","));
    await waitFor(() => panelHtml().indexOf("REV-000") >= 0, "台账刷新");
    const after = state.bidGates.data || {};
    const afterReviews = (after.reviews || []).length;
    const afterWaivers = (after.agent_waivers || []).length;
    check("gates：落库断言——追认后 REV 记录 +1（审计账）", afterReviews === beforeReviews + 1,
      `reviews ${beforeReviews} → ${afterReviews}`);
    check("gates：落库断言——agent_waivers 消项（-1）", afterWaivers === beforeWaivers - 1,
      `agent_waivers ${beforeWaivers} → ${afterWaivers}`);
    check("gates：台账刷新——human 确认面在渲染里（REV 消息/已过）",
      panelHtml().indexOf("REV-") >= 0 || panelHtml().indexOf("已过") >= 0);
  }

  // ---------- ④ 面板二~五：detail / matrix / quality / coverage（点击→IPC→渲染） ----------
  const panelCases = [
    { panel: "detail", cmd: "fs.read", text: "技术参数", label: "章节详情（大纲节点 + 正文预览）" },
    { panel: "matrix", cmd: "bid.matrix", text: "REQ-", label: "合规矩阵（REQ 行渲染）" },
    { panel: "quality", cmd: "bid.quality", text: "评分", label: "自评（评分卡渲染）" },
    { panel: "coverage", cmd: "bid.coverage", text: "已判定", label: "覆盖报告（三态分账渲染）" }
  ];
  for (const c of panelCases) {
    frames.length = 0;
    const host = workbenchHost();
    const tabBtn = host && host.querySelector('.bid-tab[data-bid-panel="' + c.panel + '"]');
    if (tabBtn) tabBtn.click(); // 真实页签点击（页签切换监听 → 重渲染）
    await waitFor(() => frameHas(c.cmd) && panelHtml().indexOf(c.text) >= 0, c.panel + " 渲染");
    check(`${c.panel}：页签点击 → ${c.cmd} IPC 帧 → 面板渲染（${c.label}）`,
      frameHas(c.cmd) && panelHtml().indexOf(c.text) >= 0,
      "帧：" + frames.join(",") + " | innerHTML 片段：" + panelHtml().slice(0, 80));
  }

  // ---------- ⑤ ipc 直返健康度（#23 同型回归：demo 全内联无 spill 信封） ----------
  const okDirect = await mang.ipc("bid.state", {}, 3000).then((r) => !!(r && r.present === true)).catch(() => false);
  check("ipc 往返：bid.state 直返 present:true（无 spill 信封泄漏）", okDirect,
    "demo 全内联——materializeBigResult 应旁路");
}

console.log(`\n${fail === 0 ? "PASS" : "FAIL"}: #21 五面板 e2e（${pass} 通过，${fail} 失败）`);
console.log("  （骨架：仿真宿主 = 内置演示桥；真实宿主扩展点见本文件头注释——mang-app --selftest + WebView2 注入）");
process.exit(fail === 0 ? 0 : 1);
