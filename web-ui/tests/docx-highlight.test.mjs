#!/usr/bin/env node
// #24：DOCX w:highlight=none 误标黄底——真实语料级回归门。
//
// 用法（零依赖）：
//   node web-ui/tests/docx-highlight.test.mjs
//
// 为什么用真实语料：issue #24 的假绿形态是「单元测试绿、真实文件
// 全页发黄」——3940 处 w:highlight 里 3938 处 val="none"，旧代码把
// 'none' 当真值存下、映射兜底成 #fff59d。静态断言拦不住这种语义
// 断链，所以本门直接解包库内真实招标 DOCX（JLYHDH-2026-ZC122），
// 对文档里**每一个** w:highlight 真跑 readRunFmt + highlightColor：
//   3938 处 none → f.highlight=null → 不产生 background-color
//   2 处 yellow  → f.highlight='yellow' → #fff59d（真高亮保留）
//
// 真源切片纪律（同 spill-unpack.test.mjs）：把 docx_view.ts 里的
// NS_W / wAttr / ooxmlBool / toInt / emptyFmt / readRunFmt /
// highlightColor 切出来，剥掉 TS 类型注解后在沙箱真跑——断言的是
// 真实现的行为，不是测试侧复制品。签名字符串变了 = 切片红 =
// 提醒维护者同步剥除规则。

import { readFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const VIEW_TS = join(ROOT, "web-ui", "src", "mang", "docx_view.ts");
const src = readFileSync(VIEW_TS, "utf8");

// ---- 切片（fail-loud：锚点消失即红） ----
function cut(startMark, endMark) {
  const si = src.indexOf(startMark);
  if (si < 0) throw new Error("切片起点不存在：`" + startMark.slice(0, 40) + "`——docx_view.ts 结构变了？");
  const ei = src.indexOf(endMark, si);
  if (ei < 0) throw new Error("切片终点不存在：`" + endMark.slice(0, 40) + "`——docx_view.ts 结构变了？");
  return src.slice(si, ei);
}

const segNSW = cut("const NS_W = [", "];"); // 常量表（含闭合 ]; 之前的部分，闭合手补
const segDeps = cut("function wAttr(node", "/** 整数解析（失败回退）。 */");
const segRunFmt = cut("/** 空运行格式。 */", "/** 解析段落样式（pStyle 标题 + jc + numPr + 直接格式）。 */");
const segHlColor = cut("/** w:highlight 枚举 → 背景色。 */", "/** 段落对齐映射（jc 枚举 → CSS text-align）。 */");

// ---- TS → JS 剥除（签名级精确替换；签名变更即测试红，提示同步本表） ----
const STRIP = [
  [/function wAttr\(node: Element, name: string, nsList: readonly string\[\] = NS_W\): string \| null \{/g, "function wAttr(node, name, nsList = NS_W) {"],
  [/function ooxmlBool\(node: Element \| null\): boolean \{/g, "function ooxmlBool(node) {"],
  [/function toInt\(v: string \| null, fallback: number\): number \{/g, "function toInt(v, fallback) {"],
  [/function emptyFmt\(\): RunFmt \{/g, "function emptyFmt() {"],
  [/function readRunFmt\(rPr: Element\): RunFmt \{/g, "function readRunFmt(rPr) {"],
  [/function highlightColor\(name: string\): string \{/g, "function highlightColor(name) {"],
  [/const table: Record<string, string> = \{/g, "const table = {"],
];
let js = [segNSW + "];", segDeps, segRunFmt, segHlColor].join("\n");
for (const [re, to] of STRIP) js = js.replace(re, to);
if (/:\s*(Element|RunFmt|string|boolean|number|Record<)/.test(js)) {
  throw new Error("剥除后仍残留 TS 类型注解——更新 STRIP 表：" + js.match(/.{0,40}:\s*(Element|RunFmt|string|boolean|number|Record<).{0,20}/)?.[0]);
}
const { readRunFmt, highlightColor } = new Function(
  js + "\nreturn { readRunFmt, highlightColor };"
)();

// ---- fake Element（readRunFmt 只用 children/localName/getAttributeNS/getAttribute） ----
function fakeEl(localName, attrs = {}) {
  return {
    localName,
    children: [],
    getAttributeNS(_ns, name) { return Object.prototype.hasOwnProperty.call(attrs, name) ? attrs[name] : null; },
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(attrs, name) ? attrs[name] : null; },
  };
}
function runFmtOf(val) { // 构造 <w:highlight w:val="..."/> 单子元素 rPr
  const hl = fakeEl("highlight", val === undefined ? {} : { val });
  return readRunFmt({ children: [hl] });
}

// —— 行为 ①：解析面——none 归一为不设置，真值保持 ——
if (runFmtOf("none").highlight !== null) throw new Error("① val=none 应归一为 null（不设置）");
if (runFmtOf("yellow").highlight !== "yellow") throw new Error("① val=yellow 应保留");
if (runFmtOf("GREEN ").highlight !== "green") throw new Error("① 大小写/空白应归一");
if (runFmtOf(undefined).highlight !== null) throw new Error("① 缺 val 应不设置");
if (runFmtOf("").highlight !== null) throw new Error("① 空 val 应不设置");
console.log("① 解析面：none→null / yellow→yellow / GREEN␣→green / 缺 val→null ✅");

// —— 行为 ②：映射面——未知色不再兜底黄色 ——
if (highlightColor("yellow") !== "#fff59d") throw new Error("② yellow 应映射 #fff59d");
if (highlightColor("green") !== "#c8e6c9") throw new Error("② green 应映射 #c8e6c9");
if (highlightColor("none") !== "") throw new Error("② none 应解析为空串（旧实现兜底 #fff59d）");
if (highlightColor("chartreuse") !== "") throw new Error("② 未知色应解析为空串，不兜底");
if (highlightColor("black") !== "#000000" || highlightColor("white") !== "#ffffff") throw new Error("② 表内黑白映射应保持");
console.log("② 映射面：yellow/green 正常，none/未知→空串不兜底 ✅");

// —— 行为 ③：端到端公式——非空且可解析才上样式 ——
function bgOf(val) {
  const f = runFmtOf(val);
  if (!f.highlight) return null;
  const hl = highlightColor(f.highlight);
  return hl ? "background-color:" + hl : null;
}
if (bgOf("none") !== null) throw new Error("③ none 不应产生 background-color");
if (bgOf("yellow") !== "background-color:#fff59d") throw new Error("③ yellow 应产生 #fff59d");
if (bgOf("chartreuse") !== null) throw new Error("③ 未知色不应产生 background-color");
console.log("③ 端到端：none/未知零样式，yellow→#fff59d ✅");

// ---- 最小 zip 读取（zlib 内置 inflateRawSync；不引入第三方依赖） ----
function readZipEntry(buf, wantName) {
  const SIG_EOCD = 0x06054b50, SIG_CDIR = 0x02014b50;
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65558); i--) {
    if (buf.readUInt32LE(i) === SIG_EOCD) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("zip: EOCD 未找到");
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  for (let n = 0; n < count; n++) {
    if (buf.readUInt32LE(p) !== SIG_CDIR) throw new Error("zip: 中央目录签名错位");
    const method = buf.readUInt16LE(p + 10);
    const compSize = buf.readUInt32LE(p + 20);
    const nameLen = buf.readUInt16LE(p + 28);
    const extraLen = buf.readUInt16LE(p + 30);
    const commentLen = buf.readUInt16LE(p + 32);
    const localOff = buf.readUInt32LE(p + 42);
    const name = buf.slice(p + 46, p + 46 + nameLen).toString("utf8");
    if (name === wantName) {
      const lnLen = buf.readUInt16LE(localOff + 26);
      const leLen = buf.readUInt16LE(localOff + 28);
      const data = buf.slice(localOff + 30 + lnLen + leLen, localOff + 30 + lnLen + leLen + compSize);
      return method === 0 ? data : inflateRawSync(data);
    }
    p += 46 + nameLen + extraLen + commentLen;
  }
  throw new Error("zip: 条目不存在 " + wantName);
}

// —— 行为 ④：真实招标语料全量验证（3938 none / 2 yellow）——
{
  const docxPath = join(ROOT, "fixtures", "real-tender-batch2", "docx-jlyh",
    "JLYHDH-2026-ZC122医养结合机构能力提升（三次）.docx");
  const docXml = readZipEntry(readFileSync(docxPath), "word/document.xml").toString("utf8");
  const vals = [...docXml.matchAll(/<w:highlight w:val="([^"]*)"\s*\/>/g)].map((m) => m[1]);
  const byVal = new Map();
  for (const v of vals) byVal.set(v, (byVal.get(v) || 0) + 1);
  if (byVal.get("none") !== 3938 || byVal.get("yellow") !== 2) {
    throw new Error("④ 语料分布变化（none=" + byVal.get("none") + ", yellow=" + byVal.get("yellow") + "）——更新本断言或语料被动过");
  }
  let styled = 0, unstyled = 0;
  for (const v of vals) {
    if (bgOf(v) !== null) styled++;
    else unstyled++;
  }
  if (styled !== 2) throw new Error("④ 全文档只应上 2 处高亮（2 个 yellow），实上 " + styled + " 处");
  if (unstyled !== 3938) throw new Error("④ 3938 处 none 应零样式，实为 " + unstyled + " 处");
  console.log("④ 真实语料（" + vals.length + " 处 w:highlight）：3938 none 零样式 / 2 yellow 保持 #fff59d ✅");
}

// —— 静态 ⑤：防回退——旧写法不回潮 ——
if (src.includes("?? '#fff59d'")) throw new Error("⑤ 兜底黄色 `?? '#fff59d'` 回潮");
if (!/const hv = \(val \?\? ''\)\.trim\(\)\.toLowerCase\(\);\s*\n\s*if \(hv && hv !== 'none'\) f\.highlight = hv;/.test(src)) {
  throw new Error("⑤ 解析面 none 归一守卫缺失");
}
if (!/if \(hl\) css\.push\('background-color:' \+ hl\);/.test(src)) throw new Error("⑤ 调用面空色守卫缺失");
console.log("⑤ 静态防回退：兜底黄/裸上色不回潮 ✅");

console.log("\ndocx-highlight: 5/5 通过（行为 4 + 静态 1）");
