#!/usr/bin/env node
// R25（#47）：建纲流真渲染端到端测试（向导深水区——导入后直达章节树）。
//
// 用法（零依赖）：
//   node web-ui/tests/outline-flow-e2e.test.mjs
//
// 架构（与 bid-e2e.test.mjs 同骨架——仿真宿主）：
//   node vm 加载真实 app.js → 演示桥切「早期相位」（window.__demoBidPhase
//   = "early"：FILES_IMPORTED 零章节起步，phase 随抽取/建纲真改——与真实
//   壳状态机同序）→ 工作台真实渲染 → 树区空态给建纲流卡：
//     抽取卡（files>0 且 reqs==0）→ 点击抽取 → bid.extract IPC →
//     推荐卡（四档单选 + 信号行 + 分包选择器）→ 选包 → 建纲 →
//     bid.build_outline IPC → loadBid 重载 → 章节树呈现（卡退场）。
//   断言层：IPC 帧序列 + 树区 innerHTML 关键文本 + 卡片相位切换 +
//   按钮门（不选包建纲按钮禁用）+ 建纲后矩阵页签可用性。
//
// 与 bid-panels.test.mjs 的关系：那道门拦「改名回退」（源级锚），本门
// 拦「运行时断链」（点击→IPC→渲染）。两道都跑，互不替代。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";
import { createDocument } from "./helpers/mang-dom-shim.mjs";

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

// ---------- ① 沙箱骨架（与 bid-e2e 同款） ----------
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
  Math, Date, JSON, Promise, Object, Array, String, Number, Boolean, RegExp, Error,
  Set, Map, Uint8Array, isFinite, parseInt, parseFloat,
  encodeURIComponent, decodeURIComponent, URL, Uint16Array, Int32Array
});

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

// ---------- ② 加载真实 app.js + 切早期相位 ----------
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
check("e2e 前提：app.js 加载成功且 __mang 钩子在场", !!(mang && mang.state && mang.ui && mang.ipc),
  loadError ? String(loadError).slice(0, 300) : "__mang 未暴露");

if (mang) {
  const { state, ui } = mang;
  check("e2e 前提：演示桥生效（mode=demo）",
    state.bridge && state.bridge.mode === "demo",
    "bridge.mode=" + (state.bridge && state.bridge.mode));
  const booted = await waitFor(() => state.booted === true, "boot() 完成");
  check("e2e 前提：boot() 全程跑完", booted, "boot 在 shim 上中断");

  // R25 相位开关：早期态（FILES_IMPORTED · 零章节 · 2 文件 0 条款）
  windowObj.__demoBidPhase = "early";

  // IPC 帧 spy（包一层 post——demo 桥真实方法保留；建纲帧记全量供参数断言）
  const frames = [];
  const buildMsgs = [];
  const rawPost = state.bridge.post.bind(state.bridge);
  state.bridge.post = (msg) => {
    frames.push(msg && msg.cmd);
    if (msg && msg.cmd === "bid.build_outline") buildMsgs.push(msg);
    return rawPost(msg);
  };
  const frameHas = (cmd) => frames.indexOf(cmd) >= 0;

  const workbenchHost = () => {
    const panesEl = doc.getElementById("panes");
    if (!panesEl) return null;
    return panesEl.querySelector(".bid-wb") || null;
  };
  const treeHtml = () => {
    const h = workbenchHost();
    const t = h && h.querySelector("#bid-tree");
    return t ? t.innerHTML : "";
  };

  // ---------- ③ 相位一：抽取卡 ----------
  await ui.openBidWorkbench("detail");
  await waitFor(() => state.bid.status === "ready", "bid.state 首载");
  check("抽取卡：早期态渲染（files=2 且 reqs=0 → 抽取入口）",
    treeHtml().indexOf("抽取条款") >= 0 && treeHtml().indexOf("确定性规则抽取") >= 0,
    "树区片段：" + treeHtml().slice(0, 120));
  check("抽取卡：步骤条呈现向导第 3 步（1✓ 2✓ 3）",
    treeHtml().indexOf("抽取条款 · 建纲") >= 0, "步骤条缺抽取位");

  const host0 = workbenchHost();
  const extractBtn = host0 && host0.querySelector('[data-bid-act="build-extract"]');
  check("抽取卡：按钮在场且可点",
    !!extractBtn && extractBtn.attrs.disabled === undefined,
    "按钮缺失或禁用（attrs.disabled=" + (extractBtn && JSON.stringify(extractBtn.attrs.disabled)) + "）");
  if (extractBtn) {
    // 零抽取告警可见性（#196）：注入零抽取现场（reqs 仍为 0 → 卡驻留相位①），
    // 重渲染后告警逐条透出——不伪装成功
    state.bidBuild.extractWarns = ["ZERO_REQUIREMENTS: 抽取结果为 0 条（演示注入——零抽取可见性探针）"];
    state.bidBuild.extractInfo = "抽取结果为 0 条";
    await ui.loadBid(true);
    await waitFor(() => treeHtml().indexOf("条告警") >= 0, "零抽取告警渲染");
    check("抽取卡：零抽取告警逐条透出（不伪装成功）",
      treeHtml().indexOf("ZERO_REQUIREMENTS") >= 0 && treeHtml().indexOf("条告警") >= 0,
      "告警块缺失");
    // 复位注入 → 干净卡再走真实抽取
    state.bidBuild.extractWarns = [];
    state.bidBuild.extractInfo = "";
    await ui.loadBid(true);
    await waitFor(() => treeHtml().indexOf("ZERO_REQUIREMENTS") < 0, "告警复位");

    extractBtn.click();
    const okEx = await waitFor(() => frameHas("bid.extract") && state.bidBuild.extractInfo.indexOf("已抽取") >= 0, "bid.extract 往返");
    check("抽取：点击 → bid.extract IPC 帧 → 计数回执（零抽取不伪装成功）",
      okEx && frameHas("bid.extract"),
      "extractInfo=" + state.bidBuild.extractInfo + " 帧：" + frames.join(","));
    // 告警捕获在状态面（非零抽取 → 相位推进，告警面让位——可见性驻留在
    // 零抽取场景，上方已验证）
    check("抽取：告警捕获不吞（state 面可见）",
      state.bidBuild.extractWarns.length >= 1,
      "warns=" + state.bidBuild.extractWarns.length);
  }

  // ---------- ④ 相位二：推荐卡 ----------
  await waitFor(() => state.bidBuild.recStatus === "ready", "篇幅推荐首载");
  await waitFor(() => treeHtml().indexOf("选择篇幅档位") >= 0, "推荐卡渲染");
  check("推荐卡：抽取后相位切换（requirements>0 → 选档面）",
    treeHtml().indexOf("选择篇幅档位，建立章节树") >= 0 && treeHtml().indexOf("已抽取 53 条条款") >= 0,
    "树区片段：" + treeHtml().slice(0, 150));
  check("推荐卡：bid.length_profile IPC 帧发出", frameHas("bid.length_profile"),
    "帧序列：" + frames.join(","));
  const host1 = workbenchHost();
  const profRadios = host1 ? host1.querySelectorAll('input[name="bid-build-prof"]') : [];
  check("推荐卡：四档单选全量在场（#287 alternatives）",
    profRadios.length === 4,
    "实得 " + profRadios.length + " 档");
  const recChecked = Array.from(profRadios).filter((r) => r.checked);
  check("推荐卡：默认选中推荐档（standard）",
    recChecked.length === 1 && recChecked[0].value === "standard",
    "checked=" + (recChecked[0] && recChecked[0].value));
  check("推荐卡：推荐标记 + 信号行在场（决策可核对）",
    treeHtml().indexOf("推荐") >= 0 && treeHtml().indexOf("信号：") >= 0 && treeHtml().indexOf("评分细则") >= 0,
    "推荐标记/信号行缺失");
  check("推荐卡：改选档可覆盖推荐（决策权在用户）", (() => {
    const pr = Array.from(profRadios).find((r) => r.value === "practical");
    if (!pr) return false;
    pr.checked = true;
    pr.change();
    return state.bidBuild.profileSel === "practical";
  })(), "profileSel=" + state.bidBuild.profileSel);

  // ---------- ⑤ 分包选择器与按钮门 ----------
  await waitFor(() => state.bidBuild.pkgStatus === "ready", "分包识别首载");
  await waitFor(() => treeHtml().indexOf("选择投标分包") >= 0, "分包选择器渲染");
  check("分包：detected=2 → 选择器在场 + bid.packages 帧发出",
    frameHas("bid.packages") && treeHtml().indexOf("检测到 2 包") >= 0,
    "帧：" + frames.join(","));
  const host2 = workbenchHost();
  const buildBtn = host2 && host2.querySelector('[data-bid-act="build-go"]');
  check("分包：未选包时建纲按钮禁用（UI 先挡——不靠工具面报错兜底）",
    !!buildBtn && buildBtn.attrs.disabled !== undefined,
    "按钮未禁用（attrs.disabled=" + (buildBtn && JSON.stringify(buildBtn.attrs.disabled)) + "）");
  const pkgRadio = host2 && host2.querySelector('input[name="bid-build-pkg"]');
  check("分包：两个包可选（PKG-A / PKG-B）",
    !!pkgRadio && host2.querySelectorAll('input[name="bid-build-pkg"]').length === 2,
    "分包单选数不对");
  if (pkgRadio) {
    pkgRadio.checked = true;
    pkgRadio.change();
    check("分包：选包后 packageSel 记录 + 按钮解禁", (() => {
      const btn = workbenchHost() && workbenchHost().querySelector('[data-bid-act="build-go"]');
      return state.bidBuild.packageSel === "PKG-A" && btn && btn.attrs.disabled === undefined;
    })(), "packageSel=" + state.bidBuild.packageSel);
  }

  // ---------- ⑥ 建纲 → 章节树呈现 ----------
  const buildBtn2 = workbenchHost() && workbenchHost().querySelector('[data-bid-act="build-go"]');
  if (buildBtn2) {
    buildBtn2.click();
    const okBuild = await waitFor(() => frameHas("bid.build_outline") && state.bidBuild.buildInfo.indexOf("章节树已建立") >= 0, "build_outline 往返");
    check("建纲：点击 → bid.build_outline IPC 帧 → 计数回执",
      okBuild && frameHas("bid.build_outline"),
      "buildInfo=" + state.bidBuild.buildInfo + " 帧：" + frames.join(","));
    // 发出参数真捕获：改选档（practical）+ 选中包（PKG-A）——决策链不丢
    const lastBuild = buildMsgs[buildMsgs.length - 1] || {};
    check("建纲：参数口径（length_profile=改选档 + package=选中包）",
      lastBuild.length_profile === "practical" && lastBuild.package === "PKG-A",
      "实发参数=" + JSON.stringify(lastBuild));
    await waitFor(() => treeHtml().indexOf("SEC-E01") >= 0, "章节树渲染");
    check("建纲后：章节树呈现（卡自然退场）",
      treeHtml().indexOf("第一章 技术方案") >= 0 && treeHtml().indexOf("1.1 技术参数响应") >= 0,
      "树区片段：" + treeHtml().slice(0, 150));
    check("建纲后：状态徽章翻「矩阵就绪」（MATRIX_READY）",
      ((workbenchHost().querySelector("#bid-wb-status") || { innerHTML: "" }).innerHTML.indexOf("矩阵就绪") >= 0),
      "状态未推进");
  }

  // ---------- ⑦ 残余相位门：full 相位零位移（既有 DRAFTING 演示面不受 early 开关影响） ----------
  windowObj.__demoBidPhase = "full";
  state.bidBuild = {
    extractBusy: false, extractError: "", extractInfo: "", extractWarns: [],
    recStatus: "idle", recError: "", rec: null,
    profileSel: "", packageSel: "",
    pkgStatus: "idle", packages: null,
    buildBusy: false, buildError: "", buildInfo: ""
  };
  await ui.loadBid(true);
  await waitFor(() => state.bid.status === "ready" && state.bid.outline, "full 相位重载");
  check("full 相位：既有完整演示面零位移（DRAFTING 章节树照常）",
    treeHtml().indexOf("大纲树") >= 0 && treeHtml().indexOf("第一章") >= 0,
    "full 相位被 early 开关污染");
}

console.log(`\n${fail === 0 ? "PASS" : "FAIL"}: R25 建纲流 e2e（${pass} 通过，${fail} 失败）`);
console.log("  （骨架：仿真宿主 = 内置演示桥早期相位；真实宿主 = mang-app --selftest 的 bid.extract/length_profile/build_outline 真链路检查）");
process.exit(fail === 0 ? 0 : 1);
