#!/usr/bin/env node
// #47 R25：证据台账读面真实端到端测试（UI 驱动全链——读面）。
//
// 用法（零依赖）：
//   node web-ui/tests/bid-evidence.test.mjs
//
// 架构（与 bid-e2e.test.mjs 同款仿真宿主）：
//   node vm 里加载真实 web-ui/mang/app.js（file:// 形态 → 内置演示桥
//   自动生效，含 #47 R25 的 bid.evidence / bid.evidence_search stub），
//   DOM shim 走真实 addEventListener 绑定：
//     ui.openBidWorkbench("evidence")（真实渲染）
//     → ui.loadBidEvidence()（真实 IPC 发出）
//     → demo 桥 post/respond（真实异步往返）
//     → onBridgeEvent → 状态面 → 重渲染（真实数据流）
//   断言：IPC 帧序列 + 面板 innerHTML 关键文本 + 过滤/检索可变数据。
//
// 真实宿主扩展点：mang-app --selftest（R25 新增 bid.evidence 无db.json 拒 /
// kind 过滤 / 检索往返三检查）覆盖 Rust 侧真跑往返；本门拦 UI 运行时断链。
// 与静态断言门（bid-panels.test.mjs 的 R25 段）互补：那道拦「改名回退」。

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

  // ---------- ③ 证据台账全链（页签点击 → IPC → 过滤/检索 → 渲染） ----------
  await ui.openBidWorkbench("evidence");
  check("evidence：页签打开（工作台骨架渲染）", !!workbenchHost(), "无 .bid-wb 宿主");
  await waitFor(() => state.bidEvidence.status === "ready" && panelHtml().indexOf("证据台账") >= 0, "证据台账渲染");
  check("evidence：点击页签 → bid.evidence IPC 帧发出", frameHas("bid.evidence"), "帧序列：" + frames.join(","));
  check("evidence：面板 DOM 渲染（13 件 + 表头 + EV-0002 行）",
    panelHtml().indexOf("共 13 件") >= 0 && panelHtml().indexOf("EV-0002") >= 0 && panelHtml().indexOf("有效期至") >= 0,
    "innerHTML 片段：" + panelHtml().slice(0, 140));
  check("evidence：列表含四态（ACTIVE 行在场；SUPERSEDED 行不被清单排除）",
    panelHtml().indexOf("已作废") >= 0 && panelHtml().indexOf("市政水厂自控项目业绩") >= 0,
    "SUPERSEDED 行缺失（清单不应排除——与检索池口径分野）");

  // kind 过滤（真实 change 监听链：select.value → state → 重拉 → 重渲染）
  {
    const host = workbenchHost();
    const sel = host && host.querySelector("[data-ev-kind]");
    check("evidence：过滤控件在场（kind/status select + 检索框 + 模式——带值 data-* 属性：shim 解析约定）",
      !!sel && !!host.querySelector("[data-ev-status]") && !!host.querySelector("[data-ev-q]") && !!host.querySelector("[data-ev-mode]"),
      "控件缺失（注意：shim 的 innerHTML 解析只认带值属性 data-x=\"v\"——裸属性不入 attrs）");
    if (sel) {
      sel.value = "qualification";
      sel.change();
      await waitFor(() => state.bidEvidence.status === "ready" && panelHtml().indexOf("（已过滤）") >= 0, "kind 过滤重拉");
      const items = (state.bidEvidence.data && state.bidEvidence.data.evidence && state.bidEvidence.data.evidence.items) || [];
      check("evidence：kind=qualification 过滤（台账 2 件 + 行内只剩资质类）",
        items.length === 2 && items.every((e) => e.kind === "qualification")
          && panelHtml().indexOf("电子与智能化专业承包二级资质") >= 0,
        "items=" + items.length + " kinds=" + items.map((e) => e.kind).join(","));
    }
  }

  // status 过滤（SUPERSEDED 四值之一——清单面口径；先复位 kindFilter：
    // 过滤叠加是产品语义（kind+status 合取），本用例只测 status 单过滤）
  {
    const host = workbenchHost();
    const st = host && host.querySelector("[data-ev-status]");
    if (st) {
      state.bidEvidence.kindFilter = "";
      st.value = "SUPERSEDED";
      st.change();
      await waitFor(() => state.bidEvidence.status === "ready" && panelHtml().indexOf("共 1 件") >= 0, "status 过滤重拉");
      const items = (state.bidEvidence.data && state.bidEvidence.data.evidence && state.bidEvidence.data.evidence.items) || [];
      check("evidence：status=SUPERSEDED 过滤（1 件 + 中文「已作废」）",
        items.length === 1 && items[0] && items[0].id === "EV-0010",
        "items=" + items.length);
    }
  }

  // 空关键词前端早拒（不发出 IPC 帧——值域在工具面，前端只拦空串）
  {
    const before = frames.length;
    await ui.searchBidEvidence("   ");
    check("evidence：空关键词前端早拒（无 IPC 帧 + 错误可见）",
      state.bidEvidenceSearch.status === "error"
        && String(state.bidEvidenceSearch.error).indexOf("关键词不能为空") >= 0
        && frames.slice(before).indexOf("bid.evidence_search") < 0,
      "error=" + state.bidEvidenceSearch.error);
  }

  // 真实检索链（input.value + 按钮真实监听 → demo 桥 → 状态面 → 渲染）
  {
    const host = workbenchHost();
    const q = host && host.querySelector("[data-ev-q]");
    const go = host && host.querySelector("[data-ev-go]");
    if (q && go) {
      q.value = "压测";
      go.click();
      const ok = await waitFor(() => state.bidEvidenceSearch.status === "ready", "检索 ready");
      check("evidence：检索按钮 → bid.evidence_search IPC 帧 + 命中渲染（并发压测报告）",
        ok && frameHas("bid.evidence_search") && panelHtml().indexOf("命中 1 件") >= 0
          && panelHtml().indexOf("并发压测报告") >= 0,
        "innerHTML：" + panelHtml().slice(0, 160));
      const sd = (state.bidEvidenceSearch.data && state.bidEvidenceSearch.data.search) || {};
      check("evidence：命中行形状（score/match_type/excerpt——工具面字段原样透传）",
        Array.isArray(sd.hits) && sd.hits.length === 1 && typeof sd.hits[0].score === "number"
          && sd.hits[0].match_type === "both" && !!sd.hits[0].excerpt,
        "hits=" + JSON.stringify(sd.hits || []).slice(0, 120));
    }
  }

  // SUPERSEDED 不进检索池（负探针：标题含「自控」的 EV-0010 是 SUPERSEDED——检索 0 命中）
  {
    await ui.searchBidEvidence("自控", "hybrid");
    const ok = await waitFor(() => state.bidEvidenceSearch.status === "ready", "检索（自控）ready");
    const sd = (state.bidEvidenceSearch.data && state.bidEvidenceSearch.data.search) || {};
    check("evidence：SUPERSEDED 不进检索池（「自控」0 命中 + 无命中文案）",
      ok && sd.total === 0 && panelHtml().indexOf("无命中") >= 0,
      "total=" + sd.total);
  }

  // ---------- ④ 登记写面全链（表单 → bridge 真改台账 → 幂等回显 → #245 拒） ----------
  {
    // 复位过滤态（前面用例留下 status=SUPERSEDED——登记后要看到全量）
    state.bidEvidence.statusFilter = "";
    // 种子：向导导入回执（per_file）——登记表单 source 下拉的数据源
    const imp = await mang.ipc("bid.import_files", { files: [{ upload_ref: "资质证书.pdf", kind: "附件" }] });
    state.bidWizard.result = imp && imp.present ? imp : null;
    await ui.loadBidEvidence(true); // 公开重拉路径（内部重渲染——源下拉读 state.bidWizard.result）
    const host = workbenchHost();
    const srcSel = host && host.querySelector("[data-ev-reg-src]");
    check("register：表单在场（source 下拉读 per_file 回执——flat 解析无 children，以面板文本断言）",
      !!srcSel && panelHtml().indexOf("TF-001") >= 0 && panelHtml().indexOf("资质证书.pdf") >= 0 && !!host.querySelector("[data-ev-reg-ph]"),
      "panelHtml 片段：" + panelHtml().slice(0, 160));
    if (srcSel) {
      srcSel.value = "TF-001";
      const k2 = host.querySelector("[data-ev-reg-kind]");
      k2.value = "qualification";
      host.querySelector("[data-ev-reg-title]").value = "E2E 登记资质";
      host.querySelector("[data-ev-reg-subject]").value = "E2E 主体";
      const uEl = host.querySelector("[data-ev-reg-until]");
      if (uEl) uEl.value = "2030-06-30";
      host.querySelector("[data-ev-reg-go]").click();
      const okr = await waitFor(() => state.bidEvidenceReg.info && state.bidEvidenceReg.info.ev_id, "登记回执");
      check("register：提交 → bid.evidence_register IPC 帧 + 新签发回显",
        okr && frameHas("bid.evidence_register") && state.bidEvidenceReg.info.deduplicated === false,
        "info=" + JSON.stringify(state.bidEvidenceReg.info || {}).slice(0, 140));
      await waitFor(() => state.bidEvidence.status === "ready" && panelHtml().indexOf("E2E 登记资质") >= 0, "台账刷新见新件");
      check("register：台账刷新可见新件（共 14 件 + 行在场）",
        panelHtml().indexOf("共 14 件") >= 0 && panelHtml().indexOf("E2E 登记资质") >= 0,
        panelHtml().slice(0, 120));
    }
  }
  {
    // 幂等重放（同参数重提——注意面板已重渲染，元素重查）
    const host = workbenchHost();
    const srcSel = host && host.querySelector("[data-ev-reg-src]");
    if (srcSel) {
      srcSel.value = "TF-001";
      host.querySelector("[data-ev-reg-kind]").value = "qualification";
      host.querySelector("[data-ev-reg-title]").value = "E2E 登记资质";
      host.querySelector("[data-ev-reg-subject]").value = "E2E 主体";
      const uEl = host.querySelector("[data-ev-reg-until]");
      if (uEl) uEl.value = "2030-06-30";
      const firstEv = state.bidEvidenceReg.info && state.bidEvidenceReg.info.ev_id;
      state.bidEvidenceReg.info = null;
      host.querySelector("[data-ev-reg-go]").click();
      const okd = await waitFor(() => state.bidEvidenceReg.info && state.bidEvidenceReg.info.ev_id, "幂等回执");
      check("register：同参数重提 → 幂等重放原直返（deduplicated=true + 同 ev_id）",
        okd && state.bidEvidenceReg.info.deduplicated === true && state.bidEvidenceReg.info.ev_id === firstEv,
        "ev1=" + firstEv + " ev2=" + (state.bidEvidenceReg.info || {}).ev_id);
    }
  }
  {
    // 换版降级（同 key 换 valid_until → 旧降 SUPERSEDED + 新签发；#245/#185 属工具面（MCP 直调），壳白名单不入——e2e 不在此重复）
    const host = workbenchHost();
    const srcSel = host && host.querySelector("[data-ev-reg-src]");
    if (srcSel) {
      srcSel.value = "TF-001";
      host.querySelector("[data-ev-reg-kind]").value = "qualification";
      host.querySelector("[data-ev-reg-title]").value = "E2E 登记资质";
      host.querySelector("[data-ev-reg-subject]").value = "E2E 主体";
      const uEl = host.querySelector("[data-ev-reg-until]");
      if (uEl) uEl.value = "2031-01-15"; // 同 key 换有效期 → 换版
      const oldEv = state.bidEvidenceReg.info && state.bidEvidenceReg.info.ev_id;
      state.bidEvidenceReg.info = null;
      host.querySelector("[data-ev-reg-go]").click();
      const okn = await waitFor(() => state.bidEvidenceReg.info && state.bidEvidenceReg.info.ev_id, "换版回执");
      check("register：同 key 换有效期 → 换版新签发（dedup=false + 新 ev_id ≠ 旧）",
        okn && state.bidEvidenceReg.info.deduplicated === false && state.bidEvidenceReg.info.ev_id !== oldEv,
        "old=" + oldEv + " new=" + (state.bidEvidenceReg.info || {}).ev_id);
      await waitFor(() => state.bidEvidence.status === "ready", "台账重拉");
      const rows = (state.bidEvidence.data.evidence.items || []).filter((e) => e.title === "E2E 登记资质");
      check("register：台账含新旧两版（旧 SUPERSEDED + 新 ACTIVE）",
        rows.length === 2 && rows.some((e) => e.status === "SUPERSEDED") && rows.some((e) => e.status === "ACTIVE"),
        "rows=" + JSON.stringify(rows.map((e) => [e.id, e.status])));
    }
  }
}

console.log(`\nPASS: #47 R25 证据台账 e2e（${pass} 通过，${fail} 失败）`);
process.exit(fail === 0 ? 0 : 1);
