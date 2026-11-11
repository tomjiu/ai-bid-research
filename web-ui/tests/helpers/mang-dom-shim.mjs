// mang-dom-shim.mjs —— #21 e2e 用的最小 DOM 实现（零依赖）。
//
// 设计边界（刻意不做完整 DOM）：
//   * innerHTML 写入时用开标签正则解析出元素（扁平化挂到 children——
//     本仓 UI 的选择器全是属性/类/id 过滤面，扁平化不破坏语义）；
//   * querySelector(All) 支持本仓用到的子集：#id / .class / [data-x] /
//     [data-x="v"] / .class[data-x]，组合逗号不支持；
//   * click() 派发到真实 addEventListener 注册的监听器（e.target.closest
//     按属性/类/id 自查 + 祖先链）——「点击」走的是 app.js 真实绑定代码；
//   * 不做的（getBoundingClientRect 等几何面）返回零值常量。
//
// 被 tests/bid-e2e.test.mjs 消费；改渲染器/选择器形态时同步扩这里。

export class ShimElement {
  constructor(tag) {
    this.tagName = String(tag || "div").toUpperCase();
    this.children = [];
    this.attrs = {};
    this.listeners = {};
    this.parentNode = null;
    this._html = "";
    this._text = "";
    this.hidden = false;
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.title = "";
    this.style = makeStyle();
    this.classList = makeClassList(this);
    this.dataset = {};
    this.ownerDocument = null;
  }
  get id() { return this.attrs.id || ""; }
  set id(v) { setAttr(this, "id", v); }
  get className() { return this.attrs.class || ""; }
  set className(v) { setAttr(this, "class", v); }
  get innerHTML() { return this._html; }
  set innerHTML(v) {
    this._html = String(v);
    this._text = "";
    this.children = parseFlat(this._html, this);
  }
  get textContent() { return this._text; }
  set textContent(v) {
    this._text = String(v ?? "");
    this._html = "";
    this.children = [];
  }
  get parentElement() { return this.parentNode && this.parentNode.tagName !== "#FRAGMENT" ? this.parentNode : null; }
  get childNodes() { return this.children; }
  appendChild(c) { detach(c); this.children.push(c); c.parentNode = this; return c; }
  prependChild(c) { detach(c); this.children.unshift(c); c.parentNode = this; return c; }
  insertBefore(c, ref) {
    detach(c);
    const i = this.children.indexOf(ref);
    if (i < 0) this.children.push(c);
    else this.children.splice(i, 0, c);
    c.parentNode = this;
    return c;
  }
  removeChild(c) {
    const i = this.children.indexOf(c);
    if (i >= 0) this.children.splice(i, 1);
    c.parentNode = null;
    return c;
  }
  replaceChild(nu, old) {
    const i = this.children.indexOf(old);
    if (i >= 0) this.children.splice(i, 1, nu);
    nu.parentNode = this;
    return old;
  }
  setAttribute(k, v) { setAttr(this, k, v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; syncDataset(this); }
  hasAttribute(k) { return k in this.attrs; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  removeEventListener(type, fn) {
    const l = this.listeners[type];
    if (!l) return;
    const i = l.indexOf(fn);
    if (i >= 0) l.splice(i, 1);
  }
  dispatch(type, ev) {
    const e = Object.assign({
      target: this,
      currentTarget: this,
      preventDefault() {},
      stopPropagation() {},
      stopImmediatePropagation() {},
      defaultPrevented: false
    }, ev || {});
    (this.listeners[type] || []).slice().forEach((fn) => fn(e));
    return !e.defaultPrevented;
  }
  click() { return this.dispatch("click"); }
  change() { return this.dispatch("change"); }
  input() { return this.dispatch("input"); }
  focus() {}
  select() {}
  getBoundingClientRect() { return { top: 0, left: 0, right: 800, bottom: 600, width: 800, height: 600 }; }
  get clientWidth() { return 800; }
  get clientHeight() { return 600; }
  get scrollHeight() { return 600; }
  get scrollWidth() { return 800; }
  get scrollTop() { return 0; }
  set scrollTop(v) { void v; }
  closest(sel) {
    let cur = this;
    while (cur) {
      if (matches(cur, sel)) return cur;
      cur = cur.parentNode;
    }
    return null;
  }
  querySelector(sel) {
    return queryAll(this, sel)[0] || null;
  }
  querySelectorAll(sel) {
    return queryAll(this, sel);
  }
  contains(node) {
    let cur = node;
    while (cur) {
      if (cur === this) return true;
      cur = cur.parentNode;
    }
    return false;
  }
}

function detach(c) {
  if (c && c.parentNode) c.parentNode.removeChild(c);
}

function makeStyle() {
  const store = {};
  return new Proxy(store, {
    get(t, k) {
      if (k === "setProperty") return (n, v) => { t[n] = String(v); };
      if (k === "removeProperty") return (n) => { delete t[n]; };
      if (k === "getPropertyValue") return (n) => t[n] ?? "";
      return t[k] ?? "";
    },
    set(t, k, v) { t[k] = v; return true; }
  });
}

function makeClassList(el) {
  const read = () => String(el.attrs.class || "").split(/\s+/).filter(Boolean);
  const write = (arr) => { el.attrs.class = arr.join(" "); };
  return {
    add(...cs) { const s = read(); cs.forEach((c) => { if (!s.includes(c)) s.push(c); }); write(s); },
    remove(...cs) { write(read().filter((c) => !cs.includes(c))); },
    toggle(c, force) {
      const s = read();
      const on = force === undefined ? !s.includes(c) : !!force;
      if (on && !s.includes(c)) s.push(c);
      if (!on) write(s.filter((x) => x !== c));
      return on;
    },
    contains(c) { return read().includes(c); },
    get length() { return read().length; }
  };
}

function setAttr(el, k, v) {
  el.attrs[k] = String(v);
  if (k === "id" && el.ownerDocument) el.ownerDocument._ids[String(v)] = el;
  syncDataset(el);
}

function syncDataset(el) {
  // dataset 与 data-* 读面同步
  Object.keys(el.attrs).forEach((k) => {
    if (k.startsWith("data-")) {
      const prop = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      el.dataset[prop] = el.attrs[k];
    }
  });
}

// ---- 开标签扁平解析：提取元素 + 属性（含 id 注册） ----
const OPEN_TAG = /<([a-zA-Z][\w-]*)((?:\s+[\w-]+(?:=(?:"[^"]*"|'[^']*'|[^\s">]+))?)*)\s*(\/?)>/g;
const ATTR = /([\w-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s">]+))?)/g;

const VOID_TAGS = new Set(["input", "br", "img", "hr", "meta", "link", "source", "wbr"]);
export function parseFlat(html, root) {
  // R25（#47 e2e）：嵌套解析——扁平化设计假设（「本仓 UI 选择器全是
  // 属性/类/id 过滤面」）被向导卡的 `.bid-wiz-file input[type=checkbox]`
  // 打破（后代组合器需要真实层级）。开标签入栈、闭标签出栈（弹到最近
  // 同名）、自闭合/void 不入栈。对既有测试是行为超集：queryAll 本就
  // 递归走全部后代（访问集与顺序不变），新增的只是父子链与 closest 的
  // 真实语义。
  const out = [];
  const doc = root && root.ownerDocument;
  const stack = [];
  const TOKEN = /<(\/?)(([a-zA-Z][\w-]*))((?:\s+[\w-]+(?:=(?:"[^"]*"|'[^']*'|[^\s">]+))?)*)\s*(\/?)>/g;
  TOKEN.lastIndex = 0;
  let m;
  while ((m = TOKEN.exec(html))) {
    const closing = m[1] === "/";
    const tag = m[2];
    const selfClose = m[5] === "/";
    if (closing) {
      for (let i = stack.length - 1; i >= 0; i--) {
        if (stack[i].tagName === tag.toUpperCase()) { stack.length = i; break; }
      }
      continue;
    }
    const el = new ShimElement(tag);
    el.ownerDocument = doc;
    const attrStr = m[4] || "";
    ATTR.lastIndex = 0;
    let am;
    while ((am = ATTR.exec(attrStr))) {
      const name = am[1];
      if (name === tag) continue; // 无属性标签的残渣防御
      const val = am[2] ?? am[3] ?? am[4] ?? "";
      el.attrs[name] = val;
      if (name === "id" && doc) doc._ids[val] = el;
    }
    syncDataset(el);
    if (tag === "input" && (el.attrs.type === "checkbox" || el.attrs.type === "radio")) {
      el.checked = el.attrs.checked !== undefined;
    }
    if (tag === "input" || tag === "select" || tag === "textarea" || tag === "option") {
      if (el.attrs.value !== undefined) el.value = el.attrs.value;
    }
    const parent = stack.length ? stack[stack.length - 1] : null;
    if (parent) { parent.children.push(el); el.parentNode = parent; }
    else out.push(el);
    if (!selfClose && !VOID_TAGS.has(tag.toLowerCase())) stack.push(el);
  }
  return out;
}

// ---- 选择器匹配（子集：#id / .class / tag / [data-x] / [data-x="v"] /
// [type=checkbox] 无引号值 / 后代组合器「.a .b」） ----
// R25（#47 e2e）：向导卡的真实绑定选择器是 `.bid-wiz-file input[type=checkbox]`
// （后代 + 无引号属性值——合法 CSS）。此前 shim 两面都不支持 → 真实监听
// 在仿真宿主上绑不上（sel 恒空）。按 CSS 语义补齐（零 app 代码让步）。
export function matches(el, sel) {
  return String(sel)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .some((s) => matchChain(el, s));
}
// 后代组合器：从右向左在祖先链上找前缀段的匹配（CSS 祖先语义）
function matchChain(el, sel) {
  const parts = splitCompounds(sel);
  if (!parts.length) return false;
  if (!matchOne(el, parts[parts.length - 1])) return false;
  let cur = el.parentNode;
  let idx = parts.length - 2;
  while (idx >= 0 && cur) {
    if (cur instanceof ShimElement && matchOne(cur, parts[idx])) idx--;
    cur = cur.parentNode;
  }
  return idx < 0;
}
// 按括号外空白切段（属性值内空格不分段）
function splitCompounds(sel) {
  const out = [];
  let buf = "";
  let depth = 0;
  for (const ch of String(sel)) {
    if (ch === "[") depth++;
    if (ch === "]") depth--;
    if (depth === 0 && /\s/.test(ch)) {
      if (buf) { out.push(buf); buf = ""; }
    } else buf += ch;
  }
  if (buf) out.push(buf);
  return out;
}
function matchOne(el, sel) {
  const parts = [];
  const rest = String(sel).replace(/\[([-\w]+)(?:="([^"]*)"|=([-\w]+))?\]/g, (_, k, q, u) => {
    parts.push(q === undefined && u === undefined ? (el.attrs[k] !== undefined) : (el.attrs[k] === (q !== undefined ? q : u)));
    return "";
  });
  const tokens = rest.split(/(?=[.#])/).filter(Boolean);
  const ok = tokens.every((t) => {
    if (t.startsWith("#")) return el.attrs.id === t.slice(1);
    if (t.startsWith(".")) return String(el.attrs.class || "").split(/\s+/).includes(t.slice(1));
    return el.tagName === t.toUpperCase();
  });
  return ok && parts.every(Boolean);
}
function queryAll(root, sel) {
  const res = [];
  const walk = (el) => {
    (el.children || []).forEach((c) => {
      if (c instanceof ShimElement) {
        if (matches(c, sel)) res.push(c);
        walk(c);
      }
    });
  };
  walk(root);
  return res;
}

// ---- document 工厂 ----
export function createDocument() {
  const doc = {
    _ids: {},
    documentElement: null,
    body: null,
    hidden: false
  };
  const de = new ShimElement("html");
  de.ownerDocument = doc;
  const body = new ShimElement("body");
  body.ownerDocument = doc;
  de.appendChild(body);
  doc.documentElement = de;
  doc.body = body;
  doc.createElement = (t) => {
    const el = new ShimElement(t);
    el.ownerDocument = doc;
    return el;
  };
  doc.createDocumentFragment = () => {
    const f = new ShimElement("#fragment");
    f.ownerDocument = doc;
    return f;
  };
  doc.createTextNode = (t) => ({ nodeType: 3, textContent: String(t), parentNode: null });
  doc.getElementById = (id) => doc._ids[id] || null;
  doc.querySelector = (sel) => queryAll(de, sel)[0] || null;
  doc.querySelectorAll = (sel) => queryAll(de, sel);
  doc.addEventListener = () => {};
  doc.removeEventListener = () => {};
  return doc;
}
