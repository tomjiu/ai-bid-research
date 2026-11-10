#!/usr/bin/env node
// loadTab 重渲染缺口实证：同一 pane 反复「innerHTML 抹除 + 重渲染」。
// 复刻 app.js loadTab 语义（不 dispose 直接抹）vs 修复语义（先 dispose 再抹）。
import { createServer } from "node:http";
import { readFile, statSync, existsSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);

const WEBUI = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(WEBUI, "..");
const DOCX = join(REPO, "fixtures/real-tender-batch2/docx-jlyh", "JLYHDH-2026-ZC122医养结合机构能力提升（三次）.docx");
const PDF = join(REPO, "fixtures/corpus-A/files/B1-设备清单.pdf");

const { homedir } = require("node:os");
const { readdirSync } = require("node:fs");
function findChromium() {
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
if (!exe) { console.error("no chromium"); process.exit(2); }
const pw = await import("playwright-core");

const MIME = { ".js": "text/javascript", ".html": "text/html", ".pdf": "application/pdf", ".docx": "application/octet-stream" };
const server = createServer((req, res) => {
  const url = decodeURIComponent(req.url.split("?")[0]);
  const file = join(REPO, url === "/" ? "/web-ui/dist/reload-host.html" : url);
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
  html,body{margin:0;height:100%;background:#1b1d21}
  #panes{position:fixed;inset:0}
  .pane{position:absolute;inset:0;overflow:hidden}
  .view-scroll{position:absolute;inset:0;overflow:auto;background:#25272c}
</style></head><body>
<div id="panes"><div class="pane" id="pane"></div></div>
<script>
  window.__probe = { add: 0, remove: 0, io: 0, ro: 0 };
  const _add = EventTarget.prototype.addEventListener, _rem = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (...a) { window.__probe.add++; return _add.apply(this, a); };
  EventTarget.prototype.removeEventListener = function (...a) { window.__probe.remove++; return _rem.apply(this, a); };
  const _IO = window.IntersectionObserver; if (_IO) window.IntersectionObserver = class extends _IO { constructor(...a) { super(...a); window.__probe.io++; } };
  const _RO = window.ResizeObserver; if (_RO) window.ResizeObserver = class extends _RO { constructor(...a) { super(...a); window.__probe.ro++; } };
  // 全局引用池——模拟闭包持有（渲染器被 tab.dispose 引用链持有的形态）
  window.__holders = [];
</script>
<script src="/web-ui/dist/mang/docx_view.js"></script>
<script src="/web-ui/dist/mang/pdf_view.js"></script>
<script type="module">
  window.__reload = async (kind, disposeFirst) => {
    const pane = document.getElementById("pane");
    const old = window.__current;
    if (old && disposeFirst) { try { old.dispose(); } catch {} }
    if (old) window.__holders.push(old); // 旧渲染器引用仍被持有（tab 引用链形态）
    pane.innerHTML = '<div class="view-state">loading</div>'; // loadTab 语义
    const mod = window.__mangRenderers[kind === "docx" ? "docx_view" : "pdf_view"];
    const [dxBuf, pdfBuf] = await Promise.all([
      fetch("/fixtures/real-tender-batch2/docx-jlyh/JLYHDH-2026-ZC122医养结合机构能力提升（三次）.docx").then((r) => r.arrayBuffer()),
      fetch("/fixtures/corpus-A/files/B1-设备清单.pdf").then((r) => r.arrayBuffer()),
    ]);
    let r;
    if (kind === "docx") {
      const scroll = document.createElement("div"); scroll.className = "view-scroll";
      const hostEl = document.createElement("div"); scroll.appendChild(hostEl);
      pane.innerHTML = ""; pane.appendChild(scroll);
      r = mod.renderDocx(new Uint8Array(dxBuf), hostEl, { onStatus: () => {} });
      const deadline = performance.now() + 30000;
      while (performance.now() < deadline) { if (r.stats.pages > 0) break; await new Promise((rr) => setTimeout(rr, 20)); }
    } else {
      pane.innerHTML = "";
      r = await mod.createPdfView(pane, new Uint8Array(pdfBuf), { onStatus: () => {} });
    }
    await new Promise((rr) => requestAnimationFrame(() => requestAnimationFrame(rr)));
    window.__current = r;
    return {
      dom: document.getElementsByTagName("*").length,
      add: window.__probe.add, remove: window.__probe.remove,
      io: window.__probe.io, ro: window.__probe.ro,
      heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null,
    };
  };
</script></body></html>`;
mkdirSync(join(WEBUI, "dist"), { recursive: true });
writeFileSync(join(WEBUI, "dist/reload-host.html"), HOST_HTML);

const browser = await pw.chromium.launch({ executablePath: exe, headless: true });

for (const disposeFirst of [false, true]) {
  console.error(`\n===== ${disposeFirst ? "修复语义（先 dispose）" : "现状（loadTab 直接抹，不 dispose）"} =====`);
  const page = await browser.newPage({ viewport: { width: 2048, height: 1152 } });
  page.on("pageerror", (e) => console.error("PAGE ERROR:", e.message));
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.waitForFunction("!!window.__reload");
  console.error("轮  kind   DOM节点  add累计  remove累计  IO累计  RO累计  堆MB");
  for (let i = 0; i < 6; i++) {
    const kind = i % 2 === 0 ? "docx" : "pdf";
    const s = await page.evaluate(([k, d]) => window.__reload(k, d), [kind, disposeFirst]);
    console.error(String(i).padStart(2) + "  " + kind.padEnd(6) +
      String(s.dom).padStart(8) + String(s.add).padStart(8) + String(s.remove).padStart(10) +
      String(s.io).padStart(8) + String(s.ro).padStart(8) + String(s.heapMB ?? "-").padStart(7));
  }
  await page.close();
}
await browser.close();
server.close();
