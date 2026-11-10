#!/usr/bin/env node
// 渲染性能诊断：docx ↔ pdf 反复切换累积卡顿复现与量化。
//
// 复刻 app.js 真实结构：
//   #panes > .pane ×2（docx / pdf），activateTab 语义 = hidden 互斥
//   docx: .pane > .view-scroll > host（app.js renderBinaryView 同构）
//   pdf : .pane > host（pdf_view 自建滚动器）
//
// 量化维度（每轮切换）：
//   ① 切换耗时（双 rAF 到帧稳定）
//   ② 文档 DOM 节点总数（document.getElementsByTagName("*").length）
//   ③ addEventListener 累计注册/移除（patch 计数，看净增）
//   ④ IntersectionObserver / ResizeObserver 实例数（patch 构造器计数）
//   ⑤ requestAnimationFrame 未落帧数（patch 计数）
//   ⑥ JS 堆（performance.memory，Chromium 专属）
//
// 输出：JSON 一行 + 人读表格。判定：耗时/节点/监听器随轮次单调增长 = 累积泄漏。

import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
import { createServer } from "node:http";
import { readFile, statSync, existsSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";

const WEBUI = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(WEBUI, "..");
const DOCX = join(REPO, "fixtures/real-tender-batch2/docx-jlyh", "JLYHDH-2026-ZC122医养结合机构能力提升（三次）.docx");
const PDF = join(REPO, "fixtures/corpus-A/files/B1-设备清单.pdf");
for (const f of [DOCX, PDF]) {
  if (!existsSync(f)) { console.error("perf-switch: 夹具不存在 " + f); process.exit(2); }
}

function findChromium() {
  const { homedir } = require("node:os");
  const { readdirSync } = require("node:fs");
  const cache = join(homedir(), ".cache/ms-playwright");
  if (!existsSync(cache)) return null;
  const cands = [];
  for (const d of readdirSync(cache)) {
    if (!d.startsWith("chromium-")) continue;
    for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
      const p = join(cache, d, sub);
      if (existsSync(p)) cands.push(p);
    }
  }
  cands.sort();
  return cands.length ? cands[cands.length - 1] : null;
}
const exe = findChromium();
if (!exe) { console.error("perf-switch: 无 Chromium"); process.exit(2); }
const pw = await import("playwright-core");

const MIME = { ".js": "text/javascript", ".html": "text/html", ".pdf": "application/pdf", ".docx": "application/octet-stream" };
const server = createServer((req, res) => {
  const url = decodeURIComponent(req.url.split("?")[0]);
  const file = join(REPO, url === "/" ? "/web-ui/dist/switch-host.html" : url);
  if (!file.startsWith(REPO) || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404).end("nf"); return; }
  readFile(file, (e, buf) => {
    if (e) res.writeHead(500).end("io");
    else { res.writeHead(200, { "content-type": MIME[extname(file)] || "application/octet-stream" }); res.end(buf); }
  });
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const HOST_HTML = `<!doctype html><html><head><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:#1b1d21;}
  #panes{position:fixed;inset:0;}
  .pane{position:absolute;inset:0;overflow:hidden;}
  .view-scroll{position:absolute;inset:0;overflow:auto;background:#25272c;}
  [hidden]{display:none !important;}
</style></head><body>
<div id="panes">
  <div class="pane" id="pane-docx"><div class="view-scroll" id="scroll-docx"><div id="host-docx" style="padding:24px 8px"></div></div></div>
  <div class="pane" id="pane-pdf"><div id="host-pdf"></div></div>
</div>
<script>
  // —— 泄漏探针：patch 原生 API 计数 ——
  window.__probe = { add: 0, remove: 0, io: 0, ro: 0, rafIn: 0, rafOut: 0 };
  const _add = EventTarget.prototype.addEventListener;
  const _rem = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (...a) { window.__probe.add++; return _add.apply(this, a); };
  EventTarget.prototype.removeEventListener = function (...a) { window.__probe.remove++; return _rem.apply(this, a); };
  const _IO = window.IntersectionObserver; if (_IO) window.IntersectionObserver = class extends _IO { constructor(...a) { super(...a); window.__probe.io++; } };
  const _RO = window.ResizeObserver; if (_RO) window.ResizeObserver = class extends _RO { constructor(...a) { super(...a); window.__probe.ro++; } };
  const _raf = window.requestAnimationFrame;
  window.requestAnimationFrame = (cb) => { window.__probe.rafIn++; return _raf(cb); };
</script>
<script src="/web-ui/dist/mang/docx_view.js"></script>
<script src="/web-ui/dist/mang/pdf_view.js"></script>
<script type="module">
  window.__boot = (async () => {
    const [docxMod, pdfMod] = [window.__mangRenderers.docx_view, window.__mangRenderers.pdf_view];
    const [dxBuf, pdfBuf] = await Promise.all([
      fetch(${JSON.stringify("/" + DOCX.slice(REPO.length + 1))}).then((r) => r.arrayBuffer()),
      fetch(${JSON.stringify("/" + PDF.slice(REPO.length + 1))}).then((r) => r.arrayBuffer()),
    ]);
    // docx：app.js renderBinaryView 同构（scroll 容器 + hostEl）
    const r1 = docxMod.renderDocx(new Uint8Array(dxBuf), document.getElementById("host-docx"), { onStatus: () => {} });
    const deadline = performance.now() + 30000;
    while (performance.now() < deadline) {
      if (r1.stats.pages > 0) break;
      await new Promise((rr) => setTimeout(rr, 20));
    }
    await new Promise((rr) => requestAnimationFrame(() => requestAnimationFrame(rr)));
    // pdf：createPdfView 自建滚动器
    const r2 = await pdfMod.createPdfView(document.getElementById("host-pdf"), new Uint8Array(pdfBuf), { onStatus: () => {} });
    await new Promise((rr) => requestAnimationFrame(() => requestAnimationFrame(rr)));
    window.__renders = { docx: r1, pdf: r2 };
    window.__ready = true;
  })();
</script></body></html>`;

mkdirSync(join(WEBUI, "dist"), { recursive: true });
writeFileSync(join(WEBUI, "dist/switch-host.html"), HOST_HTML);

const browser = await pw.chromium.launch({ executablePath: exe, headless: true });
const page = await browser.newPage({ viewport: { width: 2048, height: 1152 } });
page.on("pageerror", (e) => console.error("PAGE ERROR:", e.message));
await page.goto(`http://127.0.0.1:${port}/`);
await page.waitForFunction("window.__ready === true", null, { timeout: 60000 });
const mountInfo = await page.evaluate(() => ({
  docxPages: window.__renders.docx.stats.pages,
  docxBlocks: window.__renders.docx.stats.blocks,
  probeAfterMount: { ...window.__probe },
  domAfterMount: document.getElementsByTagName("*").length,
}));
console.error("mount:", JSON.stringify(mountInfo));

// —— 切换测量：docx→pdf→docx… 每方向各 12 轮 ——
const results = [];
for (let i = 0; i < 24; i++) {
  const toPdf = i % 2 === 0;
  const r = await page.evaluate(async (toPdf) => {
    const t0 = performance.now();
    document.getElementById("pane-docx").hidden = toPdf;
    document.getElementById("pane-pdf").hidden = !toPdf;
    await new Promise((rr) => requestAnimationFrame(() => requestAnimationFrame(rr)));
    await new Promise((rr) => setTimeout(rr, 60)); // 等 IO/RO/RAF 派生工作落地
    const t1 = performance.now();
    return {
      ms: Math.round((t1 - t0) * 10) / 10,
      dom: document.getElementsByTagName("*").length,
      listeners: window.__probe.add - window.__probe.remove,
      addTotal: window.__probe.add,
      io: window.__probe.io,
      ro: window.__probe.ro,
      rafPendingHint: window.__probe.rafIn,
      heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null,
    };
  }, toPdf);
  results.push({ i, dir: toPdf ? "→pdf" : "→docx", ...r });
}
await browser.close();
server.close();

console.log(JSON.stringify({ mount: mountInfo, rounds: results }));
console.error("\n轮次  方向     耗时ms   DOM节点   监听净增   IO数  RO数  RAF累计   堆MB");
for (const r of results) {
  console.error(
    String(r.i).padStart(3) + "  " + r.dir.padEnd(6) +
    String(r.ms).padStart(8) + String(r.dom).padStart(9) +
    String(r.listeners).padStart(9) + String(r.io).padStart(6) + String(r.ro).padStart(6) +
    String(r.rafPendingHint).padStart(9) + String(r.heapMB ?? "-").padStart(7)
  );
}
