#!/usr/bin/env node
// #595（R-18 残留切片）：web_smoke.py（W1-W13）不在仓库——main.ts 里
// 引用 W 编号作「等价性护栏/冒烟覆盖」声称的注释必须如实标注缺位，
// 不许以现在时声称护栏在位（读码代理会误信性能优化有门禁保护）。
//
// 本门锁两个面：
//   ① 声称诚实性：main.ts 每一处 web_smoke 引用必须携带缺位标注
//      （含「不在仓」与「R-18」）——新增无标注引用、或回退标注即红；
//   ② W12 结构性前提的零依赖承载：R15「增量装饰 == 全量装饰」等价性
//      的结构性保障 = genLineDecorations 单一定义 + 全量/窗口两条路径
//      都调用它（正则只此一份）。定义被复制（单一来源破裂）或某条
//      路径改走自有实现（共享破裂），等价性前提即破坏——本门即红。
//
// 不承载的面（如实声明，不假装覆盖）：
//   · W7「增量建图 ≡ 强制全量重建」的行为级逐项比对——依赖 CM6/
//     Decoration 运行时，零依赖源码提取无法承载（R-18 完整修 = 浏览器
//     E2E 基建，audit/module-audit-D.md D-06 在案）；
//   · W13 浏览器端到端冒烟、W2 光标协商语义——同上，无浏览器承载。
//
// 用法（零依赖）：
//   node web-ui/tests/web-smoke-claims.test.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const MAIN_TS = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "main.ts");
const src = readFileSync(MAIN_TS, "utf8");
const lines = src.split("\n");

let failures = [];

function fail(msg) {
  failures.push(msg);
}

// ---------- ① web_smoke 引用的缺位标注（声称诚实性门） ----------
const wsRefs = [];
lines.forEach((line, i) => {
  if (line.includes("web_smoke")) {
    wsRefs.push({ line: i + 1, text: line });
  }
});
if (wsRefs.length === 0) {
  fail("main.ts 里没有任何 web_smoke 引用了？若护栏声称已被整体清除，请同步更新本测试的目的说明（测试自身也锁不住被删除的历史——见 #595）。");
}
for (const ref of wsRefs) {
  // 标注允许落在引用行或其后续 ≤3 行的注释续行上（多行注释的自然结构）
  const window = lines.slice(ref.line - 1, ref.line - 1 + 4).join("\n");
  const marked = window.includes("不在仓") && window.includes("R-18");
  if (!marked) {
    fail(`main.ts:${ref.line} 的 web_smoke 引用缺缺位标注（引用行起 ≤4 行内须含「不在仓」+「R-18」）：${ref.text.trim().slice(0, 80)}…`);
  }
}

// ---------- ② W12 结构性前提：单一来源 + 双路径共享 ----------
// 单一定义（「正则只此一份」的来源保障）
const defs = lines
  .map((line, i) => ({ line, n: i + 1 }))
  .filter((x) => /^function genLineDecorations\(/.test(x.line));
if (defs.length !== 1) {
  fail(`genLineDecorations 必须恰好定义 1 次（实际 ${defs.length} 次，位于 ${defs.map((d) => d.n).join(",")}）——W12 等价性前提「全量与增量共享单一来源」破裂：复制实现 = 两路正则可漂移。`);
}

// 双路径调用：视口惰性路径 + 装饰窗口路径都在消费同一来源
const calls = lines
  .map((line, i) => ({ line, n: i + 1 }))
  .filter((x) => /\bgenLineDecorations\(/.test(x.line) && !/^(function|\/\/|\*| \*)/.test(x.line.trimStart()) && !x.line.includes("function genLineDecorations"));
if (calls.length < 2) {
  fail(`genLineDecorations 调用点必须 ≥2（实际 ${calls.length} 处）——全量/窗口两条路径必须共享同一来源（R15 等价性结构性前提），某条路径改走自有实现即破坏共享。`);
}

// 结构前提的语义锚点：来源注释必须仍然宣称「共享的唯一来源」
// （防有人删了设计注释后悄悄复制函数——注释锚与定义/调用断言三面互锁）
const anchor = lines.find((l) => l.includes("共享的唯一来源"));
if (!anchor) {
  fail("main.ts 里找不到「共享的唯一来源」设计注释——genLineDecorations 的单一来源锚点被删？（W12 等价性前提的三面互锁之一）");
}

// ---------- 汇总 ----------
if (failures.length > 0) {
  console.error(`web-smoke-claims: FAIL（${failures.length} 项）`);
  for (const f of failures) console.error("  ✗ " + f);
  process.exit(1);
}
console.log(
  `web-smoke-claims: PASS（web_smoke 引用 ${wsRefs.length} 处全部带缺位标注；` +
    `genLineDecorations 定义 1 + 调用 ${calls.length}（单一来源 + 双路径共享，W12 结构性前提在位））`
);
