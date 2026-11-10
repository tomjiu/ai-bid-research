#!/usr/bin/env node
// #25：PDF 默认缩放 100%（free 模式不被 applyFit 重算）——回归门。
//
// 用法（零依赖）：
//   node web-ui/tests/pdf-default-zoom.test.mjs
//
// 背景：旧默认 fitMode='fit-width'，2048px 窗下 A4 被铺到 ~285%+，
// 打开即刺眼；用户要求默认 100%（与 Word 一致）、拉伸窗口不重算。
// 真源切片纪律（同 spill-unpack / docx-highlight）：把 pdf_view.ts 的
// 常量段 + applyFit 切出来剥类型后沙箱真跑，断言：
//   行为 ① free 模式 applyFit 早退（默认 100% 保住——核心）
//   行为 ② fit-width / fit-page 语义保持（工具栏「宽」「整页」仍工作）
//   行为 ③ 空页 / 宿主不可见时零调用
//   静态 ④ 默认值 / setZoom 数值→free / onHostResize free 分支 / rotate
//         fit-width 语义锚定（#25 最小改动不碰的部分，被回退即红）

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const VIEW_TS = join(ROOT, "web-ui", "src", "mang", "pdf_view.ts");
const src = readFileSync(VIEW_TS, "utf8");

function cut(startMark, endMark) {
  const si = src.indexOf(startMark);
  if (si < 0) throw new Error("切片起点不存在：`" + startMark.slice(0, 40) + "`——pdf_view.ts 结构变了？");
  const ei = src.indexOf(endMark, si);
  if (ei < 0) throw new Error("切片终点不存在：`" + endMark.slice(0, 40) + "`——pdf_view.ts 结构变了？");
  return src.slice(si, ei);
}

// 常量段（ZOOM_* 到 clamp，含完整箭头函数体）+ applyFit 方法体
// 注意：endMark 不能落在 clamp 行内——箭头函数体被切掉的话，
// 残头 `const clamp = (v, lo, hi) =>` 会把后面的 function 声明吞成
// 它的函数体，applyFit 从外部作用域消失（踩过的坑）。
const segConsts = cut("const ZOOM_MIN = 0.25;", "/** 可选资源目录");
const segApplyFit = cut("private applyFit(): void {", "private applyScale(next");

const STRIP = [
  [/const pct = \(z: number\): number =>/g, "const pct = (z) =>"],
  [/const clamp = \(v: number, lo: number, hi: number\): number =>/g, "const clamp = (v, lo, hi) =>"],
  [/private applyFit\(\): void \{/g, "function applyFit() {"],
];
let js = segConsts + "\n" + segApplyFit;
for (const [re, to] of STRIP) js = js.replace(re, to);
if (/:\s*(number|void|string|boolean)\b/.test(js)) throw new Error("剥除后仍残留类型注解——更新 STRIP 表");

const { applyFit, clamp, ZOOM_MIN, ZOOM_MAX } = new Function(
  js + "\nreturn { applyFit, clamp, ZOOM_MIN, ZOOM_MAX };"
)();

// —— mock 宿主：A4 页（595×842pt）、视口 1788×900（2048 窗 - 260 侧栏）。
// applyFit 内部再减 PAGE_GUTTER×2=36 / PAGE_GAP×2=28，可用宽 1752 ——
// 这就是 issue 里 285%+ 观感的计算路径。 ——
function hostOf(fitMode, extra = {}) {
  const applied = [];
  return Object.assign({
    pages: [{ baseW: 595, baseH: 842 }],
    scroller: { clientWidth: 1788, clientHeight: 900 },
    rotation: 0,
    fitMode,
    applyScale: (v) => applied.push(v),
    _applied: applied,
  }, extra);
}

// —— 行为 ①：free 模式零重算（#25 核心：默认 100% 不被打开/拉伸改写）——
{
  const h = hostOf("free");
  applyFit.call(h);
  if (h._applied.length !== 0) throw new Error("① free 模式不应触发 applyScale（" + h._applied + "）——100% 会被改写");
  console.log("① free 模式 applyFit 早退，100% 保住 ✅");
}

// —— 行为 ②：fit-width / fit-page 语义保持（工具栏按钮仍工作）——
{
  const h = hostOf("fit-width");
  applyFit.call(h);
  const expect = clamp((1788 - 36) / 595, ZOOM_MIN, ZOOM_MAX); // =1752/595≈2.944→294%（大屏刺眼根源，行为保持）
  if (h._applied.length !== 1 || Math.abs(h._applied[0] - expect) > 1e-9) throw new Error("② fit-width 计算被改变: " + h._applied);
  const h2 = hostOf("fit-page");
  applyFit.call(h2);
  const expect2 = clamp(Math.min((1788 - 36) / 595, (900 - 28) / 842), ZOOM_MIN, ZOOM_MAX); // ≈1.036
  if (h2._applied.length !== 1 || Math.abs(h2._applied[0] - expect2) > 1e-9) throw new Error("② fit-page 计算被改变: " + h2._applied);
  console.log("② fit-width→" + Math.round(expect * 100) + "% / fit-page→" + Math.round(expect2 * 100) + "% 语义保持 ✅");
}

// —— 行为 ③：空页 / 宿主不可见 → 零调用（既有护栏不回归）——
{
  const h = hostOf("fit-width", { pages: [] });
  applyFit.call(h);
  const h2 = hostOf("fit-width", { scroller: { clientWidth: 0, clientHeight: 0 } });
  applyFit.call(h2);
  if (h._applied.length !== 0 || h2._applied.length !== 0) throw new Error("③ 空页/隐藏宿主不应触发 applyScale");
  console.log("③ 空页 / 隐藏宿主零调用 ✅");
}

// —— 静态 ④：语义锚定（默认值/交互面，回退即红） ——
if (!/private fitMode: 'fit-width' \| 'fit-page' \| 'free' = 'free';/.test(src)) {
  throw new Error("④ 默认 fitMode 不再是 free");
}
if (!/if \(this\.fitMode === 'free'\) return;/.test(src)) throw new Error("④ applyFit free 早退守卫缺失");
if (!/if \(this\.fitMode === 'free'\) \{\s*\n\s*this\.scheduleVisibleRender\(\);\s*\n\s*return;/.test(src)) {
  throw new Error("④ onHostResize 的 free 分支（拉伸只重渲不重算）缺失");
}
if (!/this\.fitMode = 'free';/.test(src)) throw new Error("④ setZoom 数值缩放→free 语义被删（手动 150% 会被拉伸覆盖）");
if (!/this\.fitMode = 'fit-width';\s*\n\s*this\.applyFit\(\);/.test(src)) {
  throw new Error("④ rotate 的 fit-width 重排语义被改——#25 是最小改动，如需改变旋转行为请另开 issue");
}
if (!/buildPages\(proxxies\);|buildPages\(proxies\);\s*\n\s*this\.applyFit\(\);/.test(src) && !/this\.buildPages\(proxies\);\s*\n\s*this\.applyFit\(\);/.test(src)) {
  throw new Error("④ 打开文件后的 applyFit 调用点消失——free 早退是靠它兜住 100% 的");
}
console.log("④ 默认 free / onHostResize free 分支 / setZoom→free / rotate 语义 / 打开调用点 全部锚定 ✅");

console.log("\npdf-default-zoom: 4/4 通过（行为 3 + 静态 1）");
