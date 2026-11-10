#!/usr/bin/env node
// #47 R33 性能面（一次性探针→入库）：PDF 标签切换基线（#59 修复面量化）。
// 测什么：PDF 页面视图 hidden 互斥切换（复刻 activateTab）回切耗时 +
// 视图重建行为观察。夹具 = 丹青水库 645KB 真件（#23/#34 同源语料）。
import { createServer } from "node:http";
import { readFile, statSync, existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { join, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";

const WEBUI = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(WEBUI, "..");
const FIXTURE = process.argv[2] || join(REPO, "fixtures/real-tender-batch1/danqing-reservoir-230001",
  "丹青水库工程溢洪道模型试验招标文件（[230001]SLSJY[GK]2026000520261105001）.pdf");
if (!existsSync(FIXTURE)) { console.error("夹具缺失: " + FIXTURE); process.exit(2); }

function findChromium() {
  if (process.env.PLAYWRIGHT_CHROMIUM && existsSync(process.env.PLAYWRIGHT_CHROMIUM)) return process.env.PLAYWRIGHT_CHROMIUM;
  const cache = join(homedir(), ".cache/ms-playwright");
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
if (!exe) { console.error("无 Chromium"); process.exit(2); }
const pw = await import("playwright-core");

const MIME = { ".js": "text/javascript", ".html": "text/html", ".css": "text/css", ".pdf": "application/pdf", ".mjs": "text/javascript", ".woff": "font/woff" };
const server = createServer((req, res) => {
  const url = decodeURIComponent(req.url.split("?")[0]);
  const file = join(REPO, url === "/" ? "/web-ui/dist/perf-pdf-host.html" : url);
  if (!file.startsWith(REPO) || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404).end("nf"); return; }
  readFile(file, (e, buf) => {
    if (e) res.writeHead(500).end();
    else { res.writeHead(200, { "content-type": MIME[extname(file)] || "application/octet-stream" }); res.end(buf); }
  });
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const HTML = `<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:#1b1d21}
#panes{position:fixed;inset:0}.pane{position:absolute;inset:0}
.view-scroll{position:absolute;inset:0;overflow:auto;background:#25272c}
.sub{color:#ddd;font:14px/2 monospace;padding:40px}
</style></head><body><div id="panes">
<div class="pane" id="pane-pdf"><div class="view-scroll"><div id="host-pdf" style="padding:16px"></div></div></div>
<div class="pane" id="pane-other"><div class="view-scroll"><div class="sub">（替身面板）</div></div></div>
</div>
<script src="/web-ui/dist/mang/pdf_view.js"></script>
<script>
window.__log=[];window.__done=false;
(async()=>{
  const mod=window.__mangRenderers.pdf_view;
  const res=await fetch(${JSON.stringify("/" + FIXTURE.slice(REPO.length + 1))});
  const buf=new Uint8Array(await res.arrayBuffer());
  const t0=performance.now();
  const r=mod.createPdfView(document.getElementById("host-pdf"),buf,{
    onStatus:(st)=>{window.__log.push({t:Math.round(performance.now()-t0),page:st.page,pages:st.pages})}
  });
  window.__r=r;
  const dl=performance.now()+30000;
  while(performance.now()<dl){
    if(window.__log.length&&window.__log[window.__log.length-1].pages>0)break;
    await new Promise(rr=>setTimeout(rr,20));
  }
  await new Promise(rr=>setTimeout(rr,600));
  window.__done=true;
})();
</script></body></html>`;
mkdirSync(join(WEBUI, "dist"), { recursive: true });
writeFileSync(join(WEBUI, "dist/perf-pdf-host.html"), HTML);

const browser = await pw.chromium.launch({ headless: true, executablePath: exe, args: ["--no-sandbox", "--disable-gpu"] });
const out = {};
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "load" });
  await page.waitForFunction("window.__done===true", null, { timeout: 45000 });
  out.mount = await page.evaluate("window.__log[window.__log.length-1]");
  out.firstPaint = await page.evaluate("document.querySelectorAll('#host-pdf canvas, #host-pdf img, #host-pdf .pdf-page, #host-pdf [class*=page]').length");

  const sw = await page.evaluate(async () => {
    const pdf = document.getElementById("pane-pdf");
    const other = document.getElementById("pane-other");
    const times = [];
    const settle = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    // 预热
    pdf.hidden = true; other.hidden = false; await settle();
    other.hidden = true; pdf.hidden = false; await settle();
    for (let i = 0; i < 10; i++) {
      pdf.hidden = true; other.hidden = false; await settle();
      await new Promise((r) => setTimeout(r, 40));
      const t0 = performance.now();
      other.hidden = true; pdf.hidden = false;
      await settle();
      times.push(Math.round(performance.now() - t0));
      await new Promise((r) => setTimeout(r, 40));
    }
    times.sort((a, b) => a - b);
    return { median: times[Math.floor(times.length / 2)], p90: times[Math.floor(times.length * 0.9) - 1] ?? times[times.length - 1], all: times };
  });
  out.tabSwitch = sw;
  // 30s 静置后再切一次（观察 #59 面：hidden 期间是否释放重建——重耗时骤增即重建）
  await page.evaluate(() => new Promise((r) => setTimeout(r, 3000)));
  out.afterIdleSwitch = await page.evaluate(async () => {
    const pdf = document.getElementById("pane-pdf");
    const other = document.getElementById("pane-other");
    const settle = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    pdf.hidden = true; other.hidden = false; await settle();
    await new Promise((r) => setTimeout(r, 2500));
    const t0 = performance.now();
    other.hidden = true; pdf.hidden = false;
    await settle();
    return Math.round(performance.now() - t0);
  });
  await page.close();
} finally { await browser.close(); server.close(); }
console.log(JSON.stringify(out));
