#!/usr/bin/env node
// #34 渲染性能（切换/重载累积卡顿）：标签生命周期回归门。
//
// 两个修复的静态断言（行为量化由 scripts/perf-reload-leak.mjs /
// perf-switch-repro.mjs 在真实浏览器里做——本门拦「修复被回退」）：
//   ① app.js loadTab：抹除 pane 前先 dispose 旧渲染器
//      （不释放 = docx window 滚动监听残留 / pdf 观察器与文档内存累积）
//   ② docx_view.ts dispose：样式表摘除带「还有其他 docx 渲染器在场」保护
//      （重载 A 标签不能把 B 标签的纸面样式带走）
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const app = readFileSync(join(ROOT, "web-ui/mang/app.js"), "utf8");
const docxTs = readFileSync(join(ROOT, "web-ui/src/mang/docx_view.ts"), "utf8");

let pass = 0, fail = 0;
function check(name, ok, why) {
  if (ok) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log("FAIL  " + name + " —— " + why); }
}

check(
  "loadTab 抹除 pane 前先释放旧渲染器（dispose → null → innerHTML 顺序）",
  /const host = ui\.ensurePane\(tab\);[\s\S]{0,900}if \(tab\.dispose\) tab\.dispose\(\);[\s\S]{0,200}tab\.dispose = null;[\s\S]{0,400}host\.innerHTML = '[^']*view-spinner/.test(app),
  "重载/重试路径直接 innerHTML 抹除——旧渲染器监听器/观察器/blob/文档内存随每次重渲染累积（切换越来越卡真因）"
);

check(
  "loadTab dispose 包 try/catch（disposer 不抛纪律——坏渲染器不挡重载）",
  /try \{\s*if \(tab\.dispose\) tab\.dispose\(\);\s*\} catch \(err\) \{\s*console\.warn\("ang\] dispose", err\);\s*\}/.test(app),
  "dispose 裸调用——一个异常渲染器会永久卡死该标签的重载"
);

check(
  "docx dispose 样式表保护（其他 docx 渲染器在场时不摘全局样式单例）",
  /stillInUse[\s\S]{0,200}querySelector\('\[data-mang-renderer="docx"\]'\)[\s\S]{0,300}if \(!stillInUse\) styleEl\.parentNode\.removeChild\(styleEl\)/.test(docxTs),
  "重载 docx A 标签会把 docx B 标签正在用的纸面样式一起摘掉（B 只能等自己重渲才恢复）"
);

check(
  "docx dispose 仍摘宿主标记（保护不能把清理本身省掉——本渲染器痕迹必须清）",
  /host\.removeAttribute\('data-mang-renderer'\);/.test(docxTs) && /host\.classList\.remove\('mang-docx'\);/.test(docxTs),
  "样式保护改写时把宿主 class/attr 清理弄丢了"
);

check(
  "泄漏量化工具在场（perf-reload-leak.mjs——行为证据可复跑）",
  readFileSync(join(ROOT, "web-ui/scripts/perf-reload-leak.mjs"), "utf8").includes("disposeFirst"),
  "perf-reload-leak.mjs 被删——重载泄漏的行为级验收工具消失"
);

check(
  "切换量化工具在场（perf-switch-repro.mjs——docx↔pdf 反复切换的行为证据）",
  readFileSync(join(ROOT, "web-ui/scripts/perf-switch-repro.mjs"), "utf8").includes("__probe"),
  "perf-switch-repro.mjs 被删——切换累积的行为级验收工具消失"
);

console.log(`\n== ${pass} passed, ${fail} failed ==`);
process.exit(fail === 0 ? 0 : 1);
