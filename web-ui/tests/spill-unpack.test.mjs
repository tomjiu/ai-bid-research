#!/usr/bin/env node
// #23：spill 大响应解包——行为级回归门（修复「>1.5MB 文件全部打不开」）。
//
// 用法（零依赖）：
//   node web-ui/tests/spill-unpack.test.mjs
//
// 与 bid-panels 的源级静态断言互补：这里把 app.js 中 isSpillEnvelope /
// materializeBigResult 两个函数的**真源**切出来，在 Function 沙箱里以 mock
// fetch 真跑解包路径（issue #21 的教训：静态断言拦得住改名回退，拦不住
// 运行时断链——比如旧 bug「写进 result.payload 却无人读」就是改名完好、
// 语义断掉的典型）。
//
// 断言面：
//   行为 ① spill 壳 + 完整响应壳落盘 → 返回解包后的 result 本体（顶层字段）
//   行为 ② 落盘 body 无 result 键 → 返回 body 本身（宽容路径不丢数据）
//   行为 ③ 非 spill 壳（inline 未设 / file 含分隔符）→ 原样透传，不 fetch
//   行为 ④ 非法 JSON / HTTP 非 2xx → throw code=ipc_file（fail-loud）
//   静态 ⑤ app.js 不再含 `result.payload = JSON.parse`（防回退）
//   静态 ⑥ 调用方仍读顶层 `r.data` / `r.bytes`（fs.readBytes 面）

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const APP_JS = join(ROOT, "web-ui", "mang", "app.js");
const app = readFileSync(APP_JS, "utf8");

// ---- 从真源切出函数段（fail-loud：标记变了就红，提示测试要跟着挪） ----
const START = "  function isSpillEnvelope(result) {";
const END = "  function ipc(cmd, args, timeoutMs) {";
const si = app.indexOf(START);
if (si < 0) throw new Error("找不到 isSpillEnvelope 起点——app.js 结构变了？");
const ei = app.indexOf(END);
if (ei < 0 || ei <= si) throw new Error("找不到 ipc() 终点——app.js 结构变了？");
const snippet = app.slice(si, ei);
if (!snippet.includes("materializeBigResult")) throw new Error("切出的段里没有 materializeBigResult——切取范围错了？");

/** 用 mock fetch 构造沙箱，返回 { materializeBigResult } */
function loadSandbox(mockFetch) {
  const factory = new Function(
    "fetch",
    snippet + "\nreturn { isSpillEnvelope, materializeBigResult };"
  );
  return factory(mockFetch);
}

// —— 行为 ①：spill 壳 + 响应壳落盘 → 解包出 result 本体（#23 核心路径）——
{
  const inner = { bytes: 660480, data: "JVBERi0xLjQK", enc: "base64", path: "C:\\招标文件.pdf" };
  const spilled = JSON.stringify({ id: "r7", ok: true, result: inner });
  const fetchedUrls = [];
  const { materializeBigResult } = loadSandbox(async (url) => {
    fetchedUrls.push(url);
    return { ok: true, status: 200, text: async () => spilled };
  });
  const env = { file: "abc123.json", bytes: 1500123, inline: false };
  const out = await materializeBigResult(env);
  if (out.bytes !== inner.bytes || out.data !== inner.data || out.enc !== inner.enc) throw new Error("① 解包失败：返回值不是落盘响应壳里的 result 本体");
  if (out.file !== undefined) throw new Error("① 解包失败：返回的仍是外层小壳（带 file 字段）而非 result 本体");
  if (fetchedUrls[0] !== "/__ipc/abc123.json") throw new Error("① 取回 URL 不对: " + fetchedUrls[0]);
  console.log("① spill 壳 → 解包出 result 本体（r.data/r.bytes 顶层可达） ✅");
}

// —— 行为 ②：落盘 body 无 result 键 → 返回 body（宽容但不丢数据）——
{
  const { materializeBigResult } = loadSandbox(async () => ({
    ok: true, status: 200, text: async () => JSON.stringify({ bytes: 42, data: "QkFTRTY0" })
  }));
  const out = await materializeBigResult({ file: "x.json", bytes: 99, inline: false });
  if (out.bytes !== 42 || out.data !== "QkFTRTY0") throw new Error("② 无 result 键的 body 应原样返回顶层可用形态");
  console.log("② 落盘 body 无 result 键 → 原样返回不丢数据 ✅");
}

// —— 行为 ③：非 spill 壳原样透传，不触发 fetch ——
{
  let fetched = 0;
  const { materializeBigResult, isSpillEnvelope } = loadSandbox(async () => { fetched++; return { ok: true, status: 200, text: async () => "{}" }; });
  if (isSpillEnvelope({ file: "a.json", bytes: 1, inline: false }) !== true) throw new Error("③ isSpillEnvelope 对标准壳应返回 true");
  for (const notEnv of [
    { file: "a.json", bytes: 1 },                      // inline 未设
    { file: "C:\\x\\a.json", bytes: 1, inline: false }, // file 含路径分隔符（防穿越壳）
    { bytes: 1, inline: false },                         // 无 file
    null,
  ]) {
    const out = await materializeBigResult(notEnv);
    if (out !== notEnv) throw new Error("③ 非 spill 壳必须原样透传");
  }
  if (fetched !== 0) throw new Error("③ 非 spill 壳不应发起 fetch");
  console.log("③ 非 spill 壳原样透传、零 fetch ✅");
}

// —— 行为 ④：非法 JSON / HTTP 非 2xx → throw code=ipc_file ——
{
  const { materializeBigResult } = loadSandbox(async () => ({ ok: true, status: 200, text: async () => "not-json{" }));
  let threw = null;
  try { await materializeBigResult({ file: "x.json", bytes: 1, inline: false }); } catch (e) { threw = e; }
  if (!threw || threw.code !== "ipc_file") throw new Error("④ 非法 JSON 应 throw code=ipc_file");
  const { materializeBigResult: m2 } = loadSandbox(async () => ({ ok: false, status: 500, text: async () => "{}" }));
  threw = null;
  try { await m2({ file: "x.json", bytes: 1, inline: false }); } catch (e) { threw = e; }
  if (!threw || threw.code !== "ipc_file") throw new Error("④ HTTP 非 2xx 应 throw code=ipc_file");
  console.log("④ 非法 JSON / HTTP 500 → throw code=ipc_file（fail-loud） ✅");
}

// —— 静态 ⑤：旧 bug 写法不得回潮（payload 写入后无人读）——
if (/result\.payload\s*=\s*JSON\.parse/.test(app)) throw new Error("⑤ 旧 bug 回潮：`result.payload = JSON.parse` 又出现了");
if (!app.includes("body.result && typeof body.result === \"object\"")) throw new Error("⑤ 解包守卫缺失");
console.log("⑤ 旧写法 `result.payload = JSON.parse` 已根除 ✅");

// —— 静态 ⑥：调用方读顶层字段（fs.readBytes 面，防接线断）——
if (!/tab\.meta\.data\s*=\s*r\s*&&\s*r\.data\s*\|\|\s*""/.test(app)) throw new Error("⑥ 调用方 `r.data` 顶层读取被改动——解包形态与读取点失配");
console.log("⑥ 调用方仍读顶层 r.data / r.bytes ✅");

console.log("\nspill-unpack: 6/6 通过（行为 4 + 静态 2）");
