#!/usr/bin/env node
// #25：PDF 默认缩放 100% 的回归门。
//
// 用法（零依赖）：
//   node web-ui/tests/pdf-default-zoom.test.mjs
//
// 背景：旧默认 fitMode='fit-width'，2048px 窗口下 A4 被放大到 285%。
// 用户预期与 Word 一致：默认 100%（真实大小），需要时手动点「宽」/「整页」。
//
// 本门断言（源级，防回退）：
//   ① 默认 fitMode = 'free'（= 100%，首屏由 setAllPageSize 按 scale 排版）
//   ② applyFit 对 free 早退（打开文件/拉窗口不得把 100% 改写回 fit-width）
//   ③ zoomLabel 构造初值 '100%'（与 scale=1 一致）
//   ④ setZoom('fit-width'/'fit-page') 仍可切换（工具栏按钮不破坏）
//   ⑤ rotate 仍显式设 fit-width（旋转重排行为不变）
// 任一断言红 = 修复被回退，CI 拦下。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "mang", "pdf_view.ts");
const src = readFileSync(SRC, "utf8");

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

// ---------- ① 默认 fitMode = free ----------
check(
  "① 默认 fitMode='free'（默认 100% 真实大小）",
  /private fitMode: 'fit-width' \| 'fit-page' \| 'free' = 'free';/.test(src),
  "默认又变回 fit-width（大屏 285% 回归）"
);
check(
  "① 旧默认 fit-width 已移除",
  !/= 'fit-width';\s*\n\s*private disposed/.test(src),
  "fitMode 声明的默认值仍是 fit-width"
);

// ---------- ② applyFit 对 free 早退 ----------
check(
  "② applyFit 对 free 早退（fitMode === 'free' return 在场）",
  /private applyFit\(\): void \{\s*\/\/[^]*?if \(this\.pages\.length === 0 \|\| this\.scroller\.clientWidth === 0\) return;\s*\/\/[^]*?if \(this\.fitMode === 'free'\) return;/.test(src),
  "free 模式又被宿主尺寸变化重算——拉伸窗口会覆盖 100%/手动缩放"
);
check(
  "② applyFit 主体仍按模式分算（fit-page 取 min，否则按宽）",
  /let next = this\.fitMode === 'fit-page' \? Math\.min\(availW \/ maxW, availH \/ maxH\) : availW \/ maxW;/.test(src),
  "applyFit 主体算法被改动（宽/整页语义可能回归）"
);

// ---------- ③ zoomLabel 初值 100% ----------
check(
  "③ zoomLabel 构造初值 '100%'",
  /'mang-pdf-zoomval', '100%'\)/.test(src),
  "首屏缩放标签与 scale=1 不一致"
);

// ---------- ④ setZoom 切换路径不破坏 ----------
check(
  "④ setZoom('fit-width'/'fit-page') 仍写 fitMode 并 applyFit",
  /if \(z === 'fit-width' \|\| z === 'fit-page'\) \{\s*this\.fitMode = z;\s*this\.applyFit\(\);/.test(src),
  "工具栏「宽」/「整页」按钮接线被改动"
);
check(
  "④ setZoom 数值路径仍置 free（手动缩放不被后续 fit 覆盖）",
  /this\.fitMode = 'free';\s*this\.applyScale\(clamp\(value, ZOOM_MIN, ZOOM_MAX\), anchor\);/.test(src),
  "手动数值缩放的 free 语义被改"
);

// ---------- ⑤ rotate 行为不变 ----------
check(
  "⑤ rotate 仍显式设 fit-width 后重排（旋转行为不变）",
  /this\.fitMode = 'fit-width';\s*this\.applyFit\(\);/.test(src),
  "旋转后的重排行为被改动"
);

console.log(`\n${fail === 0 ? "PASS" : "FAIL"}: #25 PDF 默认缩放回归门（${pass} 通过，${fail} 失败）`);
process.exit(fail === 0 ? 0 : 1);
