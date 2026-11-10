#!/usr/bin/env node
// #24：DOCX w:highlight=none 整页黄底的回归门。
//
// 用法（零依赖）：
//   node web-ui/tests/docx-highlight.test.mjs
//
// 背景（真实数据，JLYHDH-2026-ZC122 医养结合机构能力提升（三次）.docx）：
//   w:highlight 共 3940 处，其中 3938 处 w:val="none"（= 明确无高亮），
//   仅 2 处真 yellow。旧实现三处叠加（解析存 none / 映射兜底黄 / 无条件上色）
//   把 3938 处 none 全涂成 #fff59d → 整页发黄。
//
// 本门三层：
//   ① 解析层：none 归一为不设置（源形态在场 + 旧形态不在场）
//   ② 映射层：未知色返回空串，不兜底 '#fff59d'（从真源提取 highlightColor
//      运行时验证：none→''、yellow 保留、green→绿、乱色→''）
//   ③ 调用层：空色不上 background-color 样式
// 任一断言红 = 修复被回退，CI 拦下。

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "mang", "docx_view.ts");
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

// ---------- ① 解析层：none 归一为「不设置」 ----------
check(
  "① 解析层过滤 w:val=none（hv !== 'none' 在场）",
  /case 'highlight':\s*\{\s*\/\/[^]*?const hv = \(val \?\? ''\)\.trim\(\)\.toLowerCase\(\);\s*if \(hv && hv !== 'none'\) f\.highlight = hv;/.test(src),
  "none 又会被当真实高亮色存下（整页黄底回归）"
);
check(
  "① 旧解析形态已移除（if (val) f.highlight 不在场）",
  !/if \(val\) f\.highlight = val\.toLowerCase\(\);/.test(src),
  "旧的裸存逻辑还在——none 是真值会被存下"
);

// ---------- ② 映射层：未知色空串 + 行为验证 ----------
check(
  "② 映射层未知色返回空串（?? '' 在场）",
  /return table\[name\] \?\? '';\s*\n\}/.test(src),
  "highlightColor 又开始兜底非表色"
);
check(
  "② 旧兜底黄色已移除（?? '#fff59d' 不在场）",
  !/\?\? '#fff59d'/.test(src),
  "未知名（含 none）又会被涂成黄色"
);

// 行为验证：从真源提取 highlightColor 并运行（不复制实现，断言真源）。
const fnMatch = src.match(/function highlightColor\(name: string\): string \{[\s\S]*?\n\}/);
if (!fnMatch) {
  check("② 能从真源提取 highlightColor", false, "函数签名被改或被删——本门需同步更新提取锚点");
} else {
  check("② 能从真源提取 highlightColor", true);
  const js = fnMatch[0]
    .replace(/name: string\): string \{/, "name) {")
    .replace(/const table: Record<string, string>/, "const table");
  const fn = new Function(`${js}; return highlightColor;`)();
  check("② 行为：none → ''（无底色）", fn("none") === "", `实得 ${JSON.stringify(fn("none"))}`);
  check("② 行为：yellow → '#fff59d'（真高亮保留）", fn("yellow") === "#fff59d", `实得 ${JSON.stringify(fn("yellow"))}`);
  check("② 行为：green → '#c8e6c9'（真高亮保留）", fn("green") === "#c8e6c9", `实得 ${JSON.stringify(fn("green"))}`);
  check("② 行为：乱色 'teal' → ''（不兜底）", fn("teal") === "", `实得 ${JSON.stringify(fn("teal"))}`);
}

// ---------- ③ 调用层：空色不上样式 ----------
check(
  "③ 调用层空色不上样式（if (hl) 条件上色在场）",
  /if \(fmt\.highlight\) \{\s*\/\/[^]*?const hl = highlightColor\(fmt\.highlight\);\s*if \(hl\) css\.push\('background-color:' \+ hl\);/.test(src),
  "又变回无条件上色——空串也进 background-color"
);
check(
  "③ 旧无条件上色已移除",
  !/css\.push\('background-color:' \+ highlightColor\(fmt\.highlight\)\);/.test(src),
  "旧的直推样式行还在"
);

console.log(`\n${fail === 0 ? "PASS" : "FAIL"}: #24 高亮回归门（${pass} 通过，${fail} 失败）`);
process.exit(fail === 0 ? 0 : 1);
