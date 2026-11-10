#!/usr/bin/env node
// #34（A 级）：DOCX 纸面 content-visibility 虚拟化回归门。
//
// 用法（零依赖，无需 node_modules）：
//   node web-ui/tests/docx_content_visibility.test.mjs
//
// 设计说明（沿 md-link.test.mjs 的「源码提取执行」纪律——不复制实现，
// 提取真实 buildStyleSheet 跑出真 CSS 再断言；实现回退/改名/属性丢失都会红，
// 提取失败也红）：
//   ① 屏外纸面必须 content-visibility:auto + contain-intrinsic-size:auto 1123px
//     （#34 标签切换卡顿的 A 级修复；缺失 = 8500 节点全量重排回归）
//   ② 打印媒体必须强制 content-visibility:visible（屏外页不跳过，防打印丢页）
//   ③ 页码 offsetTop 跟踪的样式前提不变：纸面仍是常规盒（position:relative
//     在位），.mang-docx-page[data-page] 页脚规则不被本次改动挤掉
//
// 背景：#34——buildFlow 一次性同步构建 ~8500 DOM 节点无虚拟化，切换标签
// 停顿 0.3-1s。A 级修复 = 纸面级 content-visibility（Chromium/WebView2 原生
// 屏外跳过布局绘制）。实测证据见 web-ui/scripts/perf-docx-tab.mjs 与 issue。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "mang", "docx_view.ts");
const src = readFileSync(SRC, "utf8");

// ---------- 源码提取（brace 匹配，非正则截断） ----------
function extractFn(name) {
  const marker = "function " + name + "(";
  const start = src.indexOf(marker);
  if (start === -1) throw new Error(`docx_view.ts 里找不到函数 ${name}——实现被改名或删除？测试无法继续`);
  const open = src.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") {
      depth--;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error(`函数 ${name} 的 brace 不闭合——提取器无法工作`);
}
function extractConst(name) {
  const re = new RegExp("const " + name + " = ");
  const m = re.exec(src);
  if (!m) throw new Error(`docx_view.ts 里找不到常量 ${name}——测试无法继续`);
  const rest = src.slice(m.index, src.indexOf("\n", m.index));
  return rest;
}

// ---------- 拼装执行（buildStyleSheet 只依赖 SCOPE 常量） ----------
const scopeDecl = extractConst("SCOPE");
const SCOPE = scopeDecl.match(/'([^']+)'/)[1];
const buildStyleSheet = eval("(" + extractFn("buildStyleSheet").replace(/^function\s+buildStyleSheet\(\):\s*string\s*\{/, "function buildStyleSheet() {") + ")");
const css = buildStyleSheet();

// ---------- 断言 ----------
let failed = 0;
const ok = (cond, label) => {
  console.log((cond ? "  ok  " : "  FAIL") + " " + label);
  if (!cond) failed++;
};

// ① .mang-docx-page 规则块内有 content-visibility:auto（按规则块切片，防误配到别处）
function ruleBlock(selector) {
  const idx = css.indexOf(selector + " {");
  if (idx === -1) return null;
  const open = css.indexOf("{", idx);
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) return css.slice(open + 1, i);
    }
  }
  return null;
}
const pageRule = ruleBlock(SCOPE + " .mang-docx-page");
ok(pageRule !== null, "`.mang-docx-page` 规则块存在");
ok(pageRule && /content-visibility:\s*auto/.test(pageRule), "纸面 content-visibility:auto 在位（#34 A 级虚拟化）");
ok(pageRule && /contain-intrinsic-size:\s*auto\s+1123px/.test(pageRule), "contain-intrinsic-size:auto 1123px（A4 高占位 + 记忆尺寸）在位");
ok(pageRule && /position:\s*relative/.test(pageRule), "position:relative 保持（证据高亮层/offsetTop 页码跟踪前提）");
ok(pageRule && /width:\s*100%/.test(pageRule), "width:100% 保持（显式宽度——尺寸包含不改宽度语义）");

// ② 打印媒体重置
const printIdx = css.indexOf("@media print");
ok(printIdx !== -1, "@media print 块存在");
const printBlock = printIdx === -1 ? "" : css.slice(printIdx, css.indexOf("}", css.indexOf("content-visibility", printIdx)) + 1);
ok(/content-visibility:\s*visible/.test(printBlock), "打印强制 content-visibility:visible（防打印丢页）");

// ③ 页脚页码规则未被挤掉
ok(css.includes(SCOPE + " .mang-docx-page[data-page]::after"), "页脚页码 ::after 规则在位");

if (failed > 0) {
  console.error(`\nFAIL: ${failed} 项断言失败——#34 A 级虚拟化样式被回退？`);
  process.exit(1);
}
console.log("\nPASS: #34 DOCX 纸面 content-visibility 虚拟化全部在场");
