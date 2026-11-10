#!/usr/bin/env node
// #34：DOCX 标签切换卡顿——真实 Chromium 量化基线工具（A 级 content-visibility 验收）。
//
// 用法（需要真实浏览器，不进默认测试门——缺浏览器时 fail-loud，不算 SKIP 通过）：
//   node web-ui/scripts/perf-docx-tab.mjs [fixture.docx]
//
// 前置：
//   cd web-ui && node mang-build.mjs          # 先产出 dist/mang/docx_view.js
//   npm install --no-save playwright-core     # 驱动层（不入 package.json）
//   浏览器：$PLAYWRIGHT_CHROMIUM 或
//     ~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome
//
// 量什么（对应 #34 验收 1/2/4）：
//   ① mount 耗时：renderDocx(bytes) → 首次 onStatus（pages 发布，buildFlow 完成）
//   ② 标签切换耗时：hidden 互斥切换（复刻 app.js activateTab 语义），
//      双 rAF 计帧——目标 < 100ms（issue 验收 1）
//   ③ 页码监听正确性：滚到底/顶，onStatus 报告页码（验收 4：offsetTop 语义）
//   ④ 滚动长任务：PerformanceObserver longtask > 50ms 计数（验收 3 白屏/跳动代理）
//
// 输出：JSON 一行（机器可读）+ 人读摘要，非零退出仅在「无法测量」时（浏览器缺失等）。

import { createServer } from "node:http";
import { readFile, statSync, existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { join, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";

const WEBUI = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(WEBUI, "..");
const FIXTURE_DEFAULT = join(
  REPO, "fixtures/real-tender-batch2/docx-jlyh",
  "JLYHDH-2026-ZC122医养结合机构能力提升（三次）.docx",
);
const fixture = process.argv[2] ? join(process.cwd(), process.argv[2]) : FIXTURE_DEFAULT;
if (!existsSync(fixture)) {
  console.error("perf: 夹具不存在——" + fixture);
  process.exit(2);
}

// ---------- 浏览器定位（fail-loud，不静默降级） ----------
function findChromium() {
  if (process.env.PLAYWRIGHT_CHROMIUM && existsSync(process.env.PLAYWRIGHT_CHROMIUM)) {
    return process.env.PLAYWRIGHT_CHROMIUM;
  }
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
if (!exe) {
  console.error("perf: 找不到 Chromium（~/.cache/ms-playwright 或 $PLAYWRIGHT_CHROMIUM）。无法实测——如实失败，不冒充。");
  process.exit(2);
}
let pw;
try {
  pw = await import("playwright-core");
} catch {
  console.error("perf: playwright-core 未安装（npm install --no-save playwright-core）。无法实测。");
  process.exit(2);
}

// ---------- 静态服务：仓库根（dist 与 fixtures 都在下面） ----------
const MIME = {
  ".js": "text/javascript", ".mjs": "text/javascript", ".html": "text/html",
  ".css": "text/css", ".json": "application/json", ".docx": "application/octet-stream",
  ".pdf": "application/pdf", ".png": "image/png", ".woff": "font/woff",
};
const server = createServer((req, res) => {
  const url = decodeURIComponent(req.url.split("?")[0]);
  const file = join(REPO, url === "/" ? "/web-ui/dist/perf-host.html" : url);
  if (!file.startsWith(REPO) || !existsSync(file) || !statSync(file).isFile()) {
    res.writeHead(404).end("nf");
    return;
  }
  readFile(file, (e, buf) => {
    if (e) res.writeHead(500).end("io");
    else {
      res.writeHead(200, { "content-type": MIME[extname(file)] || "application/octet-stream" });
      res.end(buf);
    }
  });
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

// ---------- 宿主页：复刻 mang 的 #panes/.pane + activateTab hidden 语义 ----------
const HOST_HTML = `<!doctype html><html><head><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:#1b1d21;}
  #panes{position:fixed;inset:0;}
  .pane{position:absolute;inset:0;overflow:hidden;}
  .view-scroll{position:absolute;inset:0;overflow:auto;background:#25272c;}
  .pdf-substitute{color:#ddd;font:14px/2 monospace;padding:40px;}
</style></head><body>
<div id="panes">
  <div class="pane" id="pane-docx"><div class="view-scroll" id="scroll-docx"><div id="host-docx" style="padding:24px 8px"></div></div></div>
  <div class="pane" id="pane-other"><div class="view-scroll"><div class="pdf-substitute" id="other-body">（PDF 面替身：切换目标）</div></div></div>
</div>
<script src="/web-ui/dist/mang/docx_view.js"></script>
<script>
  window.__statusLog = [];
  window.__mountDone = false;
  (async () => {
    const mod = window.__mangRenderers.docx_view;
    const res = await fetch(${JSON.stringify("/" + fixture.slice(REPO.length + 1))});
    const buf = new Uint8Array(await res.arrayBuffer());
    const host = document.getElementById("host-docx");
    const t0 = performance.now();
    const r = mod.renderDocx(buf, host, {
      onStatus: (st) => {
        window.__statusLog.push({ t: performance.now() - t0, page: st.page, pages: st.pages });
      },
    });
    window.__pending = (async () => {
      // renderDocx 的异步构建段没有公开 promise——用 onStatus 首报 + 双 rAF 兜底。
      const deadline = performance.now() + 30000;
      while (performance.now() < deadline) {
        if (r.stats.pages > 0) break;
        await new Promise((rr) => setTimeout(rr, 20));
      }
      await new Promise((rr) => requestAnimationFrame(() => requestAnimationFrame(rr)));
      window.__mountDone = true;
      return { pages: r.stats.pages, blocks: r.stats.blocks, warnings: r.stats.warnings.length };
    })();
  })();
</script></body></html>`;
const HOST_PAGE = join(WEBUI, "dist/perf-host.html");
mkdirSync(join(WEBUI, "dist"), { recursive: true });
writeFileSync(HOST_PAGE, HOST_HTML); // dist/ 已 gitignore——测量宿主页是生成物，不入库

// ---------- 跑测量 ----------
const browser = await pw.chromium.launch({
  headless: true,
  executablePath: exe,
  args: ["--no-sandbox", "--disable-gpu", "--force-device-scale-factor=1"],
});
const results = { fixture: fixture.slice(REPO.length + 1), viewport: "1440x900" };
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "load" });
  await page.waitForFunction("window.__mountDone === true", null, { timeout: 45000 });
  results.mount = await page.evaluate("window.__pending");
  results.statusFirst = await page.evaluate("window.__statusLog[0] || null");
  results.nodeCount = await page.evaluate(
    "document.querySelectorAll('#host-docx *').length",
  );

  // longtask 观察器（滚动段）
  await page.evaluate(() => {
    window.__longTasks = 0;
    try {
      new PerformanceObserver((l) => { window.__longTasks += l.getEntries().length; })
        .observe({ entryTypes: ["longtask"] });
    } catch { window.__longTasks = -1; }
  });

  // ② 标签切换：复刻 activateTab 的 hidden 互斥（10 轮往返取中位）
  const switchTimes = await page.evaluate(async () => {
    const docx = document.getElementById("pane-docx");
    const other = document.getElementById("pane-other");
    const times = [];
    // 预热一轮（首次显示走冷路径，单独记录）
    const warm = async () => {
      docx.hidden = true; other.hidden = false;
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const t0 = performance.now();
      other.hidden = true; docx.hidden = false;
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return performance.now() - t0;
    };
    await warm();
    for (let i = 0; i < 10; i++) {
      docx.hidden = true; other.hidden = false;
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      await new Promise((r) => setTimeout(r, 30));
      const t0 = performance.now();
      other.hidden = true; docx.hidden = false;
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      times.push(performance.now() - t0);
      await new Promise((r) => setTimeout(r, 30));
    }
    times.sort((a, b) => a - b);
    return { median: times[Math.floor(times.length / 2)], p90: times[Math.floor(times.length * 0.9) - 1] ?? times[times.length - 1], all: times.map((t) => Math.round(t)) };
  });
  results.tabSwitch = switchTimes;

  // ③ 页码监听：滚到底 → 等稳定 → 滚回顶
  const pageAt = async (pos) => {
    const st = await page.evaluate(async (p) => {
      const sc = document.getElementById("scroll-docx");
      sc.scrollTo({ top: p === "bottom" ? sc.scrollHeight : 0 });
      await new Promise((r) => setTimeout(r, 500)); // 滚动 + 可能的渐进渲染
      const log = window.__statusLog;
      return { last: log[log.length - 1], scrollH: sc.scrollHeight };
    }, pos);
    return st;
  };
  results.pageTracking = {
    top: (await pageAt("top")).last,
    bottom: (await pageAt("bottom")).last,
    middle: (await page.evaluate(async () => {
      const sc = document.getElementById("scroll-docx");
      sc.scrollTo({ top: sc.scrollHeight / 2 });
      await new Promise((r) => setTimeout(r, 600));
      const log = window.__statusLog;
      return log[log.length - 1];
    })),
  };

  // ⑤ 滚动跳动量化（验收 3 代理）：占位高度 vs 真实高度的 scrollHeight 漂移。
  // 三点采样：挂载后 / 滚底稳定后 / 滚回顶稳定后。漂移 > 15% 视为明显跳动。
  results.scrollHeightStability = await page.evaluate(async () => {
    const sc = document.getElementById("scroll-docx");
    const h0 = sc.scrollHeight;
    sc.scrollTo({ top: sc.scrollHeight });
    await new Promise((r) => setTimeout(r, 600));
    const h1 = sc.scrollHeight;
    sc.scrollTo({ top: 0 });
    await new Promise((r) => setTimeout(r, 600));
    const h2 = sc.scrollHeight;
    return { initial: h0, afterBottom: h1, afterTop: h2, driftPct: Math.round(Math.abs(h1 - h0) / h0 * 1000) / 10 };
  });


  // ④ 滚动长任务：模拟连续滚 4 屏
  await page.evaluate(async () => {
    const sc = document.getElementById("scroll-docx");
    for (let i = 0; i < 8; i++) {
      sc.scrollBy({ top: 900 });
      await new Promise((r) => setTimeout(r, 120));
    }
    await new Promise((r) => setTimeout(r, 400));
  });
  results.scrollLongTasks = await page.evaluate("window.__longTasks");
  results.contentVisibility = await page.evaluate(() => {
    const el = document.querySelector(".mang-docx-page");
    if (!el) return null;
    const cs = getComputedStyle(el);
    return { contentVisibility: cs.contentVisibility, containIntrinsicSize: cs.containIntrinsicSize };
  });
  await page.close();
} finally {
  await browser.close();
  server.close();
}

console.log(JSON.stringify(results));
const sw = results.tabSwitch;
console.error(
  `— mount: ${results.mount.pages} 页 / ${results.mount.blocks} 块 / ${results.nodeCount} DOM 节点，构建+发布 ${Math.round(results.statusFirst?.t ?? -1)}ms\n` +
  `— 标签切换回 DOCX：中位 ${Math.round(sw.median)}ms / p90 ${Math.round(sw.p90)}ms（目标 <100ms）\n` +
  `— 页码：底=${results.pageTracking.bottom?.page}/${results.pageTracking.bottom?.pages} 顶=${results.pageTracking.top?.page}/${results.pageTracking.top?.pages}\n` +
  `— 滚动 longtask(>50ms)：${results.scrollLongTasks}\n` +
  `— content-visibility：${results.contentVisibility ? results.contentVisibility.contentVisibility + " / " + results.contentVisibility.containIntrinsicSize : "（未设置——基线）"}`,
);
