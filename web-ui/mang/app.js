(() => {
  // mang/app.js
  var $ = (sel, root = document) => root.querySelector(sel);
  function esc(s) {
    return String(s == null ? "" : s).split("&").join("&amp;").split("<").join("&lt;").split(">").join("&gt;").split(String.fromCharCode(34)).join("&quot;").split(String.fromCharCode(39)).join("&#39;");
  }
  var ICON = {
    files: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4.2l1.8 2H19.5A1.5 1.5 0 0 1 21 9.5v8A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z"/></svg>',
    history: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.8"/></svg>',
    changes: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4.5h9.5L20 11v8.5H4z"/><path d="M13.2 4.6V11H20"/><path d="M7.6 15.2h4.4M7.6 17.8h7.2"/></svg>',
    star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3.8 2.6 5.3 5.9.85-4.25 4.15 1 5.85L12 17.2l-5.25 2.75 1-5.85L3.5 9.95l5.9-.85z"/></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.1"/><path d="M19.4 15a1.6 1.6 0 0 0 .32 1.77l.06.06a1.94 1.94 0 1 1-2.74 2.74l-.06-.06a1.6 1.6 0 0 0-1.77-.32 1.6 1.6 0 0 0-.97 1.47V21a1.94 1.94 0 1 1-3.88 0v-.1a1.6 1.6 0 0 0-1.05-1.47 1.6 1.6 0 0 0-1.77.32l-.06.06a1.94 1.94 0 1 1-2.74-2.74l.06-.06a1.6 1.6 0 0 0 .32-1.77 1.6 1.6 0 0 0-1.47-.97H3a1.94 1.94 0 1 1 0-3.88h.1a1.6 1.6 0 0 0 1.47-1.05 1.6 1.6 0 0 0-.32-1.77l-.06-.06a1.94 1.94 0 1 1 2.74-2.74l.06.06a1.6 1.6 0 0 0 1.77.32H9a1.6 1.6 0 0 0 .97-1.47V3a1.94 1.94 0 1 1 3.88 0v.1a1.6 1.6 0 0 0 .97 1.47 1.6 1.6 0 0 0 1.77-.32l.06-.06a1.94 1.94 0 1 1 2.74 2.74l-.06.06a1.6 1.6 0 0 0-.32 1.77V9a1.6 1.6 0 0 0 1.47.97H21a1.94 1.94 0 1 1 0 3.88h-.1a1.6 1.6 0 0 0-1.5.97z"/></svg>',
    close: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round"><path d="m4 4 8 8M12 4l-8 8"/></svg>',
    chevron: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 4 4 4-4 4"/></svg>',
    folder: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M1.8 4.2h4.1l1.3 1.6h7v6.4a.9.9 0 0 1-.9.9H2.7a.9.9 0 0 1-.9-.9z"/></svg>',
    folderOpen: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M1.8 4.2h4.1l1.3 1.6h7v1.4H4.4L2.6 13.4a.9.9 0 0 1-2-.5z"/><path d="M4.6 7.2h10.2l-1.7 5.2a.9.9 0 0 1-.85.6H2.9"/></svg>',
    refresh: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M13.2 8a5.2 5.2 0 1 1-1.6-3.75"/><path d="M13.4 2.2v3.1h-3.1"/></svg>',
    docx: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M3.4 1.8h5.4l3.8 3.7v8.7H3.4z"/><path d="M8.7 1.9v3.7h3.8"/><path d="M5.3 8.4h1.3l.65 3 .65-3h1.3l.65 3 .65-3H11"/></svg>',
    xlsx: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M3.4 1.8h5.4l3.8 3.7v8.7H3.4z"/><path d="M8.7 1.9v3.7h3.8"/><path d="m5.5 8.2 3.4 3.5M8.9 8.2l-3.4 3.5"/></svg>',
    pdf: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M3.4 1.8h5.4l3.8 3.7v8.7H3.4z"/><path d="M8.7 1.9v3.7h3.8"/><path d="M5.4 12V8.6h1.2a1 1 0 0 1 0 2H5.4"/></svg>',
    md: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M3.4 1.8h5.4l3.8 3.7v8.7H3.4z"/><path d="M8.7 1.9v3.7h3.8"/><path d="M5 12V8.8l1.2 1.5 1.2-1.5V12"/><path d="M9.4 8.8v3.2M8.4 11l1 1.1 1-1.1"/></svg>',
    text: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"><path d="M3.4 1.8h5.4l3.8 3.7v8.7H3.4z"/><path d="M8.7 1.9v3.7h3.8"/><path d="M5.4 8.4h5.2M5.4 10.4h5.2M5.4 12.2h3"/></svg>',
    warning: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2.2 14.4 13H1.6z"/><path d="M8 6.2v3.1M8 11.4v.6"/></svg>',
    info: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6.2"/><path d="M8 7.3v4M8 5.1v.6"/></svg>',
    check: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m3.2 8.4 3 3 6.6-6.8"/></svg>',
    shield: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.8 13.4 3.8v3.4c0 3.2-2.2 5.6-5.4 6.9-3.2-1.3-5.4-3.7-5.4-6.9V3.8z"/><path d="m5.7 7.9 1.6 1.6 3-3.1"/></svg>',
    export: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2.2v7.6"/><path d="m5.2 6.9 2.8 2.9 2.8-2.9"/><path d="M2.8 10.4v2.2a1.2 1.2 0 0 0 1.2 1.2h8a1.2 1.2 0 0 0 1.2-1.2v-2.2"/></svg>',
    outline: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5h2.2M4 12h2.2M4 18.5h2.2"/><path d="M10 5.5h10M10 12h7.5M10 18.5h9"/></svg>',
    bid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.5h9.5L19 7v13.5H6z"/><path d="M15.2 3.6V7H19"/><path d="M9 11.5h6M9 14.5h6"/><path d="m9.2 17.4 1.4 1.4 2.7-2.8"/></svg>'
  };
  var KIND_ICON = { docx: "docx", xlsx: "xlsx", pdf: "pdf", md: "md", text: "text", dir: "folder", bidwork: "bid" };
  function fmtBytes(n) {
    if (!Number.isFinite(n)) return "";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(n < 10 * 1024 ? 1 : 0) + " KB";
    return (n / 1024 / 1024).toFixed(1) + " MB";
  }
  function timeAgo(ts) {
    if (!ts) return "";
    const d = Date.now() - ts;
    if (d < 5e3) return "\u521A\u521A";
    if (d < 6e4) return Math.floor(d / 1e3) + " \u79D2\u524D";
    if (d < 36e5) return Math.floor(d / 6e4) + " \u5206\u949F\u524D";
    if (d < 864e5) return Math.floor(d / 36e5) + " \u5C0F\u65F6\u524D";
    if (d < 1728e5) return "\u6628\u5929";
    if (d < 6048e5) return Math.floor(d / 864e5) + " \u5929\u524D";
    return new Date(ts).toLocaleDateString("zh-CN");
  }
  function kindOf(name) {
    const m = /\.([a-z0-9]+)$/i.exec(name || "");
    const ext = m ? m[1].toLowerCase() : "";
    if (ext === "docx" || ext === "doc") return "docx";
    if (ext === "xlsx" || ext === "xls") return "xlsx";
    if (ext === "pdf") return "pdf";
    if (ext === "md" || ext === "markdown") return "md";
    return "text";
  }
  function baseName(p) {
    const s = String(p || "");
    const i = Math.max(s.lastIndexOf("/"), s.lastIndexOf("\\"));
    return i >= 0 ? s.slice(i + 1) : s;
  }
  function dirName(p) {
    const s = String(p || "");
    const i = Math.max(s.lastIndexOf("/"), s.lastIndexOf("\\"));
    return i > 0 ? s.slice(0, i) : s;
  }
  var LS_SETTINGS = "mang.settings.v1";
  var SETTINGS_DEFAULT = {
    theme: "system",
    sidebarVisible: true,
    sidebarWidth: 260,
    sidebarActive: "files",
    statusbarVisible: true,
    wordWrap: true,
    showLineNumbers: true,
    // #76：自动快照间隔（秒）。0 = 关闭。旧 localStorage 无此键 → 默认 30（原硬编码值）
    snapshotIntervalSec: 30
  };
  function loadSettings() {
    try {
      const raw = localStorage.getItem(LS_SETTINGS);
      if (!raw) return Object.assign({}, SETTINGS_DEFAULT);
      const parsed = JSON.parse(raw);
      return Object.assign({}, SETTINGS_DEFAULT, parsed && typeof parsed === "object" ? parsed : {});
    } catch (e) {
      return Object.assign({}, SETTINGS_DEFAULT);
    }
  }
  function saveSettings() {
    try {
      localStorage.setItem(LS_SETTINGS, JSON.stringify(settings));
    } catch (e) {
    }
  }
  var settings = loadSettings();
  // #76：自动快照定时器（间隔可配，原 30s 硬编码）。声明在 settings 之后、
  // boot 之前：renderSettingsView 改间隔时会调 armSnapshotTimer，不能等文件尾再声明。
  var snapshotTimer = 0;
  function armSnapshotTimer() {
    if (snapshotTimer) {
      clearInterval(snapshotTimer);
      snapshotTimer = 0;
    }
    const sec = Number(settings.snapshotIntervalSec);
    if (sec > 0) snapshotTimer = setInterval(snapshotTick, sec * 1000);
  }
  var systemDark = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  function applyTheme() {
    const want = settings.theme === "system" ? systemDark && systemDark.matches ? "dark" : "light" : settings.theme;
    document.documentElement.dataset.theme = want;
    document.documentElement.style.colorScheme = want;
    state.theme = want;
    return want;
  }
  if (systemDark) {
    const onSys = () => {
      if (settings.theme === "system") {
        applyTheme();
        renderStatusBar();
      }
    };
    if (systemDark.addEventListener) systemDark.addEventListener("change", onSys);
    else if (systemDark.addListener) systemDark.addListener(onSys);
  }
  function nativeIpc() {
    try {
      if (window.ipc && typeof window.ipc.postMessage === "function") return window.ipc;
    } catch (e) {
    }
    return null;
  }
  function findHostInternal() {
    try {
      if (window.parent && window.parent !== window) {
        const internal = window.parent.__mangInternal;
        if (internal && typeof internal.post === "function") return internal;
      }
    } catch (e) {
    }
    return null;
  }
  var bridgeListeners = /* @__PURE__ */ new Set();
  function dispatchBridge(ev) {
    bridgeListeners.forEach((cb) => {
      try {
        cb(ev);
      } catch (e) {
        console.warn("[mang] bridge \u56DE\u8C03\u5F02\u5E38", e);
      }
    });
  }
  window.__ipcResolve = function(id, resp, ok) {
    let frame = resp;
    if (!frame || typeof frame !== "object" || !("ok" in frame)) {
      frame = { id, ok: ok !== false, result: ok !== false ? resp : void 0 };
    }
    if (ok === false) frame.ok = false;
    dispatchBridge(frame);
  };
  window.__ipcEvent = function(ev) {
    if (ev && typeof ev === "object") dispatchBridge(ev);
  };
  window.__mangDispatch = dispatchBridge;
  function createBridge() {
    const raw = nativeIpc();
    if (raw) {
      return {
        mode: "host",
        post: (msg) => {
          try {
            raw.postMessage(JSON.stringify(msg));
          } catch (e) {
            console.warn("[mang] IPC \u53D1\u9001\u5931\u8D25", e);
          }
        },
        onEvent: (cb) => {
          bridgeListeners.add(cb);
          return () => bridgeListeners.delete(cb);
        }
      };
    }
    const internal = findHostInternal();
    if (internal && internal.native !== false) {
      return {
        mode: "host",
        post: (msg) => internal.post(msg),
        onEvent: (cb) => internal.onMessage(cb)
      };
    }
    if (window.location.protocol === "file:") {
      console.warn("[mang] file:// \u4E0B\u4EE5\u6F14\u793A\u6A21\u5F0F\u8FD0\u884C\uFF1B\u6B63\u5F0F\u8FD0\u884C\u8BF7\u7528 mang-app.exe");
    }
    return createDemoBridge();
  }
  function createDemoBridge() {
    const root = String.raw`C:\演示工作区`;
    const now = Date.now();
    const docs = [
      { path: root + String.raw`\项目A\技术标.md`, size: 1620, mtime: now - 36e5 },
      { path: root + String.raw`\项目A\报价单.xlsx`, size: 18320, mtime: now - 36e5 },
      { path: root + String.raw`\项目A\资质证明.pdf`, size: 120232, mtime: now - 1728e5 },
      { path: root + String.raw`\项目A\招标文件.docx`, size: 58320, mtime: now - 2592e5 },
      { path: root + String.raw`\项目B\商务标.md`, size: 2200, mtime: now - 1728e5 }
    ];
    const tree = {
      root,
      nodes: [
        {
          name: "\u9879\u76EEA",
          rel: "\u9879\u76EEA",
          kind: "dir",
          children: [
            { name: "\u62DB\u6807\u6587\u4EF6.docx", rel: String.raw`项目A\招标文件.docx`, kind: "file", size: 58320, mtimeMs: now - 2592e5 },
            { name: "\u6280\u672F\u6807.md", rel: String.raw`项目A\技术标.md`, kind: "file", size: 1620, mtimeMs: now - 36e5 },
            { name: "\u62A5\u4EF7\u5355.xlsx", rel: String.raw`项目A\报价单.xlsx`, kind: "file", size: 18320, mtimeMs: now - 36e5 },
            { name: "\u8D44\u8D28\u8BC1\u660E.pdf", rel: String.raw`项目A\资质证明.pdf`, kind: "file", size: 120232, mtimeMs: now - 1728e5 },
            { name: "\u635F\u574F\u4EF6.pdf", rel: String.raw`项目A\损坏件.pdf`, kind: "file", size: 65536, mtimeMs: now - 864e5 }
          ]
        },
        {
          name: "\u9879\u76EEB",
          rel: "\u9879\u76EEB",
          kind: "dir",
          children: [{ name: "\u5546\u52A1\u6807.md", rel: String.raw`项目B\商务标.md`, kind: "file", size: 2200, mtimeMs: now - 1728e5 }]
        },
        { name: "README.md", rel: "README.md", kind: "file", size: 900, mtimeMs: now - 432e6 }
      ]
    };
    const mdDoc = [
      "# \u6280\u672F\u65B9\u6848",
      "",
      "> \u672C\u6587\u6863\u7531 mang \u5DE5\u4F5C\u53F0\u6253\u5F00\uFF08\u6F14\u793A\u6A21\u5F0F\uFF09\u3002",
      "",
      "## \u4E00\u3001\u603B\u4F53\u67B6\u6784",
      "",
      "\u672C\u6B21\u6295\u6807\u65B9\u6848\u91C7\u7528**\u5206\u5E03\u5F0F\u67B6\u6784**\uFF0C\u5404\u4E1A\u52A1\u6A21\u5757\u6309\u9886\u57DF\u62C6\u5206\uFF0C\u901A\u8FC7\u6D88\u606F\u603B\u7EBF\u89E3\u8026\u3002",
      "",
      "| \u6A21\u5757 | \u8BF4\u660E | \u8D1F\u8D23\u4EBA |",
      "| --- | --- | --- |",
      "| \u63A5\u5165\u5C42 | \u7EDF\u4E00\u7F51\u5173\u3001\u9650\u6D41\u7194\u65AD | \u5F20\u5DE5 |",
      "| \u4E1A\u52A1\u5C42 | \u6807\u4E66\u7F16\u6392\u3001\u6A21\u677F\u5F15\u64CE | \u674E\u5DE5 |",
      "| \u6570\u636E\u5C42 | \u6587\u6863\u5E93\u3001\u5411\u91CF\u5E93 | \u738B\u5DE5 |",
      "",
      "## \u4E8C\u3001\u5B9E\u65BD\u8BA1\u5212",
      "",
      "1. \u7B2C\u4E00\u5468\uFF1A\u9700\u6C42\u6F84\u6E05\u4E0E\u539F\u578B",
      "2. \u7B2C\u4E8C\u5468\uFF1A\u6838\u5FC3\u7F16\u8F91\u94FE\u8DEF",
      "3. \u7B2C\u4E09\u5468\uFF1A\u5BFC\u51FA\u4E0E\u9A8C\u6536",
      "",
      "```",
      "mang-app.exe --workspace " + String.raw`D:\项目A`,
      "```",
      "",
      "## \u4E09\u3001\u98CE\u9669\u63A7\u5236",
      "",
      "- \u6587\u6863\u4E00\u81F4\u6027\u98CE\u9669 \u2192 \u7EDF\u4E00\u6A21\u677F + \u7248\u672C\u5FEB\u7167",
      "- \u4EA4\u4ED8\u8FDB\u5EA6\u98CE\u9669 \u2192 \u6BCF\u5468\u91CC\u7A0B\u7891\u9A8C\u6536",
      ""
    ].join("\n");
    let recent = [{ path: docs[0].path, name: "\u6280\u672F\u6807.md", openedAt: now - 72e5 }];
    const listeners = /* @__PURE__ */ new Set();
    const push = (ev) => listeners.forEach((cb) => cb(ev));
    const respond = (id, result) => {
      if (id) push({ id, ok: true, result });
    };
    const fail = (id, code, message) => {
      if (id) push({ id, ok: false, error: { code, message } });
    };
    const findDoc = (p) => docs.find((d) => d.path === p);
    // #313 批 A：标书面板演示数据（与真实 bid.state / bid.outline 响应同形——
    // docs/mang/IPC-CONTRACT.md §6；只在此处造数，渲染代码零分支）
    const demoChapterContent = (sec) =>
      [
        "## " + sec + " 章节正文（演示）",
        "",
        "> 本节由标书工作台演示桥提供——真实运行时来自 chapters/" + sec + ".json 的 content 字段。",
        "",
        "本节对招标文件技术参数逐项应答：",
        "",
        "| 参数项 | 招标要求 | 本方案响应 |",
        "| --- | --- | --- |",
        "| 并发容量 | ≥1000 路 | 2000 路（留双倍冗余） |",
        "| 响应时延 | ≤50ms | 32ms 实测 |",
        "| 可用性 | 99.9% | 99.95%（双活架构） |",
        "",
        "实施计划与质量保证措施见后续章节。"
      ].join("\n");
    const DEMO_BID = {
      state: {
        present: true,
        workspace: root,
        db: root + "\\db.json",
        project: { id: "PRJ-0001", name: "演示·智慧园区弱电工程", code: "", mode: "明标", status: "DRAFTING" },
        state: {
          status: "DRAFTING",
          allowed_next_tools: ["draft_response_section", "validate_bid_document"],
          terminal: false,
          dirty_sections: [{ section_id: "SEC-0002", title: "1.1 技术参数", section_status: "DRAFTED", pending_directives: 1 }],
          pending_rewrite_directives: [
            { id: "RD-0001", section_id: "SEC-0002", change_id: "CH-0001", req_id: "REQ-0007", change_type: "MODIFIED", old_text: "支持 1000 路并发", new_requirement: "支持 2000 路并发", affected_segments: [], created_at: "2026-11-07T09:00:00Z" }
          ],
          content_binding: { sections_digest: "demo-digest", content_version: 12 },
          agent_waivers: [],
          human_review_complete: false
        },
        quick_stats: { requirements: 1120, evidence: 13, evidence_bindings: 46, sections: 26, sections_leaf: 20, sections_drafted: 12, sections_accepted: 3, sections_failed: 1, sections_dirty: 1, target_total_chars: 150000, actual_total_chars: 81200, pages_estimate: 97 }
      },
      outline: {
        present: true,
        workspace: root,
        project: { id: "PRJ-0001", name: "演示·智慧园区弱电工程", status: "DRAFTING" },
        nodes: [
          { id: "SEC-0001", parent_id: null, title: "第一章 技术方案", level: 1, order: 1, status: "DRAFTING", dirty: false, target_chars: 15000, actual_chars: 12000, req_count: 8, is_leaf: false, has_content: false, content_attempt: 0, chapter_file: null },
          { id: "SEC-0002", parent_id: "SEC-0001", title: "1.1 技术参数", level: 2, order: 2, status: "DRAFTED", dirty: true, target_chars: 6000, actual_chars: 5000, req_count: 5, is_leaf: true, has_content: true, content_attempt: 2, chapter_file: "chapters/SEC-0002.json" },
          { id: "SEC-0003", parent_id: "SEC-0001", title: "1.2 商务要求", level: 2, order: 3, status: "PENDING", dirty: false, target_chars: 9000, actual_chars: 0, req_count: 3, is_leaf: true, has_content: false, content_attempt: 0, chapter_file: null },
          { id: "SEC-0004", parent_id: null, title: "第二章 施工组织", level: 1, order: 4, status: "OUTLINING", dirty: false, target_chars: 12000, actual_chars: 0, req_count: 4, is_leaf: false, has_content: false, content_attempt: 0, chapter_file: null },
          { id: "SEC-0005", parent_id: "SEC-0004", title: "2.1 施工进度计划", level: 2, order: 5, status: "FAILED", dirty: false, target_chars: 5000, actual_chars: 0, req_count: 2, is_leaf: true, has_content: false, content_attempt: 0, chapter_file: null },
          { id: "SEC-0006", parent_id: "SEC-0004", title: "2.2 质量保证", level: 2, order: 6, status: "ACCEPTED", dirty: false, target_chars: 7000, actual_chars: 7150, req_count: 2, is_leaf: true, has_content: true, content_attempt: 1, chapter_file: "chapters/SEC-0006.json" }
        ],
        stats: { sections: 6, sections_leaf: 4, sections_drafted: 2, sections_accepted: 1, sections_failed: 1, sections_dirty: 1, target_total_chars: 27000, actual_total_chars: 12150, pages_estimate: 15 }
      },
      // #313 批 B：合规矩阵演示数据（与真实 bid.matrix 响应同形——行字段 =
      // get_compliance_matrix 工具输出原样透传；只在此处造数，渲染代码零分支）
      matrix: {
        present: true,
        workspace: root,
        project: { id: "PRJ-0001", name: "演示·智慧园区弱电工程", status: "DRAFTING" },
        rows: [
          { cmp_id: "CMP-0001", requirement: { id: "REQ-0001", clause_no: "3.2.1", category: "技术参数", category_key: "tech_param", statement: "投标人须提供 2000 路并发能力", mandatory: false, source_anchor: { file: "A-招标文件.docx", kind: "para", locator: "第三章 3.2/REQ-0001", excerpt: "投标人须提供 2000 路并发能力" }, params: {} }, status: "RESPONDED", evidence: [{ ev_id: "EV-0001", title: "并发压测报告", status: "ACTIVE", valid_until: "2027-06-30", verification_tier: "SELF_TEST" }], pending_evidence_ids: [], evidence_required: false, evidence_missing: false, substantive: false, gap: null, response_policy: "default", draft_section_id: "SEC-0002", blocking: false },
          { cmp_id: "CMP-0002", requirement: { id: "REQ-0002", clause_no: "1.4.2", category: "资格条件", category_key: "qualification", statement: "投标人须具备电子与智能化专业承包二级资质", mandatory: true, source_anchor: { file: "A-招标文件.docx", kind: "para", locator: "第一章 1.4/REQ-0002", excerpt: "投标人须具备电子与智能化专业承包二级资质" }, params: {} }, status: "NOT_RESPONDED", evidence: [], pending_evidence_ids: [], evidence_required: true, evidence_missing: true, substantive: false, gap: null, response_policy: "default", draft_section_id: "SEC-0003", blocking: true },
          { cmp_id: "CMP-0003", requirement: { id: "REQ-0003", clause_no: "3.5.1", category: "技术参数", category_key: "tech_param", statement: "★核心设备须为回产主流型号，提供原厂授权及服务承诺", mandatory: false, source_anchor: { file: "A-招标文件.docx", kind: "para", locator: "第三章 3.5/REQ-0003", excerpt: "★核心设备须为回产主流型号，提供原厂授权及服务承诺" }, params: { star: true } }, status: "PARTIAL", evidence: [], pending_evidence_ids: [], evidence_required: true, evidence_missing: true, substantive: true, gap: null, response_policy: "default", draft_section_id: "SEC-0002", blocking: false },
          { cmp_id: "CMP-0004", requirement: { id: "REQ-0004", clause_no: "6.1.1", category: "商务要求", category_key: "commercial", statement: "质保期不少于三年，附服务网点清单", mandatory: false, source_anchor: { file: "A-招标文件.docx", kind: "para", locator: "第六章 6.1/REQ-0004", excerpt: "质保期不少于三年，附服务网点清单" }, params: {} }, status: "NOT_RESPONDED", evidence: [], pending_evidence_ids: [], evidence_required: true, evidence_missing: true, substantive: false, gap: null, response_policy: "default", draft_section_id: "SEC-0003", blocking: false },
          { cmp_id: "CMP-0005", requirement: { id: "REQ-0005", clause_no: "1.4.5", category: "资格条件", category_key: "qualification", statement: "项目经理须持有一级建造师注册证书（扫描件）", mandatory: true, source_anchor: { file: "A-招标文件.docx", kind: "para", locator: "第一章 1.4/REQ-0005", excerpt: "项目经理须持有一级建造师注册证书（扫描件）" }, params: {} }, status: "PENDING_EVIDENCE", evidence: [{ ev_id: "EV-0002", title: "建造师证书（占位待补）", status: "ACTIVE", valid_until: null, verification_tier: "PLACEHOLDER" }], pending_evidence_ids: ["EV-0002"], evidence_required: true, evidence_missing: true, substantive: false, gap: null, response_policy: "default", draft_section_id: null, blocking: true },
          { cmp_id: "CMP-0006", requirement: { id: "REQ-0006", clause_no: "6.3.2", category: "商务要求", category_key: "commercial", statement: "★付款方式按里程碑分期，响应人须逐项确认", mandatory: false, source_anchor: { file: "A-招标文件.docx", kind: "para", locator: "第六章 6.3/REQ-0006", excerpt: "★付款方式按里程碑分期，响应人须逐项确认" }, params: { star: true } }, status: "RESPONDED", evidence: [{ ev_id: "EV-0003", title: "付款确认函", status: "ACTIVE", valid_until: "2027-12-31", verification_tier: "COUNTERSIGNED" }], pending_evidence_ids: [], evidence_required: true, evidence_missing: false, substantive: true, gap: null, response_policy: "default", draft_section_id: "SEC-0003", blocking: false }
        ],
        total: 6,
        summary: { by_status: { NOT_RESPONDED: 2, RESPONDED: 2, PARTIAL: 1, NOT_APPLICABLE: 0, PENDING_EVIDENCE: 1 }, blocking: 2, mandatory: 3, substantive: 2, evidence_missing: 4 },
        star_summary: { total: 2, responded: 1, partial: 0, not_responded: 1, not_applicable: 0, responded_share: 0.5, note: "★实质性条款（params.star）——一条不响应即响应无效；not_responded>0 时不废标风险存在" },
        warnings: [],
        project_version: 12,
        fetched_pages: 1
      },
      // #313 批 C：自评面板演示数据（与真实 bid.quality / bid.score 响应同形——
      // check_bid_quality / score_document 的 out；只在此处造数，渲染代码零分支）
      quality: {
        present: true,
        workspace: root,
        project: { id: "PRJ-0001", name: "演示·智慧园区弱电工程", status: "DRAFTING" },
        quality: {
          project_id: "PRJ-0001",
          summary: { total: 20, drafted: 12, failed: 1, pending: 7, uncovered_req_total: 3, out_of_band: 2, unanchored_total: 1, dup_pairs: 1, dup_max_similarity: 0.83, char_total: 81200, char_target: 150000, char_deviation_pct: -45.9 },
          needs_human: ["SEC-0005", "SEC-0009"],
          submission_readiness: {
            ready: false, not_built: false, blockers: 4, unresponded_count: 1, evidence_missing_count: 3,
            unresponded: [{ requirement_id: "REQ-0007", row_id: "CMP-0007", category: "技术参数", excerpt: "支持 2000 路并发", message: "矩阵行未响应（正文未提及该条款）" }],
            evidence_missing: [
              { requirement_id: "REQ-0003", row_id: "CMP-0003", category: "资格条件", excerpt: "具备电子与智能化二级资质", message: "响应条款无可用证据佐证" },
              { requirement_id: "REQ-0011", row_id: "CMP-0011", category: "商务要求", excerpt: "质保期不少于三年", message: "响应条款无可用证据佐证" },
              { requirement_id: "REQ-0018", row_id: "CMP-0018", category: "技术参数", excerpt: "磁盘阵列双活架构", message: "响应条款无可用证据佐证" }
            ]
          },
          sections: [
            { section_id: "SEC-0002", title: "1.1 技术参数", status: "DRAFTED", chars: 5000, target_chars: 6000, covered_reqs: ["REQ-0001"], uncovered_reqs: [], needs_human: false },
            { section_id: "SEC-0005", title: "2.1 施工进度计划", status: "FAILED", chars: 0, target_chars: 5000, covered_reqs: [], uncovered_reqs: ["REQ-0007"], needs_human: true }
          ],
          global_conflicts: [
            { kind: "amount_conflict", severity: "blocker", section_id: "SEC-0002", message: "投标保证金 在 SEC-0002=3500000 与 PR-0001=3580000（首现位置见各自锚点）" }
          ],
          negative_deviations: [
            { param_id: "PR-0003", requirement_id: "REQ-0009", param_name: "并发容量", required_value: "2000 路", response_value: "1500 路" }
          ],
          artifact: { path: root + "\\artifacts\\quality-report.json", size: 20480 },
          warnings: []
        }
      },
      score: {
        present: true,
        workspace: root,
        project: { id: "PRJ-0001", name: "演示·智慧园区弱电工程", status: "DRAFTING" },
        score: {
          project_id: "PRJ-0001",
          diagnostic_only: true,
          result_kind: "rule_heuristic",
          technical: 34.5,
          commercial: 18,
          price: null,
          total: 52.5,
          target: 85,
          gap: 32.5,
          by_item: [
            { item_id: "REQ-0102", criteria: "技术方案完整性、先进性、可行性优者得 20 分", max: 20, estimated: 12.5, tier: "良", coverage: 0.62, section_id: "SEC-0002", mapping_ids: ["SEC-0002"], weight_share: 1, contributions: [{ section_id: "SEC-0002", estimated: 12.5, tier: "良", coverage: 0.62, weight_share: 1, rule_gaps: 1 }], score_rules: null, rule_checkpoints: [{ text: "双活架构与冗余设计", hits: [2, 0], mentioned: true }, { text: "与招标参数逐项对比表", hits: [0, 0], mentioned: false }], rule_gaps: 1 },
            { item_id: "REQ-0105", criteria: "施工组织方案合理、进度计划可行", max: 15, estimated: 9, tier: "中", coverage: 0.55, section_id: "SEC-0005", mapping_ids: ["SEC-0005"], weight_share: 1, contributions: [{ section_id: "SEC-0005", estimated: 9, tier: "中", coverage: 0.55, weight_share: 1, rule_gaps: 0 }], score_rules: null, rule_checkpoints: [{ text: "横道图或网络图", hits: [1, 0], mentioned: true }], rule_gaps: 0 }
          ],
          breakdown: [],
          mappings: [],
          unmapped_scoring_items: ["REQ-0021"],
          notes: [],
          price_input: null,
          sections_scored: 12
        }
      },
      // #313 批 D：覆盖报告演示数据（与真实 bid.coverage 响应同形——coverage =
      // get_coverage_report 工具输出原样透传；summary = 壳侧三态分账；star =
      // 逐文件 get_star_coverage 聚合。数字取 issue #313 面板规格例：
      // 已判定 1,120 / 未判定 80 / 已排除 40、★条款覆盖 45/48）
      coverage: {
        present: true,
        workspace: root,
        project: { id: "PRJ-0001", name: "演示·智慧园区弱电工程", status: "DRAFTING" },
        coverage: {
          project_id: "PRJ-0001",
          complete: false,
          total_blocks: 1240,
          covered_blocks: 1160,
          uncovered_range_count: 2,
          unjudged_blocks: 80,
          files: [
            { file_id: "TF-0001", total_blocks: 1240, covered_blocks: 1160, complete: false, uncovered_ranges: [[210, 254], [892, 917]], uncovered_range_count: 2, excluded_blocks: 40, unjudged_blocks: 80, by_verdict: { requirement: 1080, review_table: 40, noise: 40 } }
          ],
          next: "有未判定块——submit_block_marks 补标（已开始标记的文件必须标满才能建纲，#244；未标记过的文件走正则兜底不受限）"
        },
        summary: {
          total_blocks: 1240,
          judged_blocks: 1120,
          excluded_blocks: 40,
          unjudged_blocks: 80,
          uncovered_range_count: 2,
          complete: false,
          by_verdict: { requirement: 1080, review_table: 40, noise: 40 }
        },
        star: {
          files: [
            { file_id: "TF-0001", file_name: "A-招标文件.docx", star_total: 50, declarations: 2, star_truth: 48, star_captured: 45, star_missing: 3, next: "有★漏标——用 missing[].block_idx 定位后 submit_block_marks 补标（substantive=true），重跑 extract_requirements 生效" }
          ],
          total: { star_total: 50, declarations: 2, star_truth: 48, star_captured: 45, star_missing: 3 }
        }

      },
      // #603 批 A：审核门台账演示数据（与真实 bid.gates 响应同形——
      // DomainStore 直读面；演示态 = agent 已声明过矩阵/大纲两门未追认，
      // 恰好展示「追认」交互；gate_pass 的演示模拟见 demo 桥 case 分支）
      gates: {
        present: true,
        workspace: root,
        project: { id: "PRJ-0001", name: "演示·智慧园区弱电工程", status: "DRAFTING" },
        gates: [
          { gate: "matrix_approval", title: "矩阵定稿门", note: "门序第一：条款响应矩阵定稿（MATRIX_READY+ 可过）", approved: true, latest_pass: { gate: "matrix_approval", actor: "agent-01", actor_type: "agent", method: "agent_declared", human_confirmed: false, at: Math.floor(now / 1000) - 86400 * 2, reason: "条款矩阵已全量核对（1120/1120 行）" } },
          { gate: "outline_approval", title: "大纲定稿门", note: "门序第二：章节树定稿（前置：矩阵门已过）", approved: true, latest_pass: { gate: "outline_approval", actor: "agent-01", actor_type: "agent", method: "agent_declared", human_confirmed: false, at: Math.floor(now / 1000) - 86400, reason: "章节树与字数配额核对完成" } },
          { gate: "pre_export_confirm", title: "导出前确认门", note: "门序第三：导出前置确认（前置：前两门均过）", approved: false, latest_pass: null },
          { gate: "addendum_waiver", title: "补遗逐件确认门", note: "L3 人工出口（#131/#379——逐件路径不再写本门）", approved: false, latest_pass: null },
          { gate: "no_addendum_confirmed", title: "无补遗全局确认门", note: "#379 拆门——「本项目无补遗」全局显式确认", approved: false, latest_pass: null }
        ],
        human_review_complete: false,
        agent_waivers: [
          { gate: "matrix_approval", actor: "agent-01", actor_type: "agent", method: "agent_declared", human_confirmed: false, at: Math.floor(now / 1000) - 86400 * 2, reason: "条款矩阵已全量核对（1120/1120 行）" },
          { gate: "outline_approval", actor: "agent-01", actor_type: "agent", method: "agent_declared", human_confirmed: false, at: Math.floor(now / 1000) - 86400, reason: "章节树与字数配额核对完成" }
        ],
        reviews: [
          { id: "REV-0002", gate: "outline_approval", decision: "APPROVED", reviewer: "agent:agent-01", actor: { actor_id: "agent-01", actor_type: "agent", authentication_method: "hmac_receipt_v2" }, findings: [], at: Math.floor(now / 1000) - 86400, reviewed_content_digest: "demo-digest" },
          { id: "REV-0001", gate: "matrix_approval", decision: "APPROVED", reviewer: "agent:agent-01", actor: { actor_id: "agent-01", actor_type: "agent", authentication_method: "hmac_receipt_v2" }, findings: [], at: Math.floor(now / 1000) - 86400 * 2, reviewed_content_digest: "demo-digest" }
        ]
      }
    };
    // #603 批 A：演示桥的治理面可变态（gate_pass 会真改台账——与真实壳
    // 同语义：追认后最新条翻 human、agent_waivers 消项、human_review_complete
    // 重算；演示刷新页面即重置，与其它演示面一致）
    const demoGates = JSON.parse(JSON.stringify(DEMO_BID.gates));
    // #603 批 C：补遗台账演示数据（与真实 bid.addenda 响应同形——
    // readiness::{total, ready, not_ready[]} + waivers）。演示态 = 2 件
    // 补遗（1 就绪 + 1 OCR 未完——逐件确认的目标件）；全局确认对它
    // 响亮拒（#379 语义分账的现场教学：确认无补遗 ≠ 坏件免责）
    DEMO_BID.addenda = {
      present: true,
      workspace: root,
      project: { id: "PRJ-0001", name: "演示·智慧园区弱电工程", status: "DRAFTING" },
      readiness: { total: 2, ready: 1, not_ready: [ { file_id: "TF-0003", name: "补遗-01（扫描件）", readiness: "OCR_PENDING", waived: false, reason: "OCR 未完成——图像层有字但文本层为空，修复重传或人工确认后放行" } ] },
      waivers: []
    };
    const demoAddenda = JSON.parse(JSON.stringify(DEMO_BID.addenda));
    function demoAddendumWaiver(m) {
      const fid = String(m.file_id || "");
      const reason = String(m.reason || "");
      if (!reason.trim()) return fail(m.id, "bad_args", "演示模式：reason 必填——确认理由不得为空白（不可审计的确认不成确认）");
      const f = demoAddenda.readiness.not_ready.find((x) => x.file_id === fid);
      if (!f) return fail(m.id, "not_found", "演示模式：文件 " + fid + " 不存在（对不存在的件做确认 = 凭空免责）");
      const at = Math.floor(Date.now() / 1000);
      f.waived = true;
      demoAddenda.waivers.push({ file_id: fid, reason: reason, at: at, principal: "human:shell-operator" });
      // 过门同步（addendum_waiver 门最新一条 human——与真实壳同语义，gates 同源）
      const g = demoGates.gates.find((x) => x.gate === "addendum_waiver");
      if (g) {
        g.approved = true;
        g.latest_pass = { gate: "addendum_waiver", actor: "shell-operator", actor_type: "human", method: "human_receipt", human_confirmed: true, at: at, reason: reason };
      }
      demoGateRevSeq += 1;
      demoGates.reviews.unshift({ id: "REV-" + String(demoGateRevSeq).padStart(4, "0"), gate: "addendum_waiver", decision: "APPROVED", reviewer: "human:shell-operator", actor: { actor_id: "shell-operator", actor_type: "human", authentication_method: "hmac_receipt_v2" }, findings: [], at: at, reviewed_content_digest: "demo-digest" });
      demoGates.agent_waivers = demoGates.gates.filter((x) => x.latest_pass && x.latest_pass.human_confirmed === false).map((x) => x.latest_pass);
      demoGates.human_review_complete = demoGates.agent_waivers.length === 0;
      return respond(m.id, {
        present: true,
        workspace: root,
        project: demoAddenda.project,
        addendum_waiver: {
          recorded: { file_id: fid, reason: reason, at: at, principal: "human:shell-operator", actor: { actor_id: "shell-operator", actor_type: "human", authentication_method: "hmac_receipt_v2" } },
          addendum_waivers: demoAddenda.waivers.slice(),
          addendum_readiness: { total: demoAddenda.readiness.total, ready: demoAddenda.readiness.ready, not_ready: demoAddenda.readiness.not_ready.slice() },
          agent_waivers: demoGates.agent_waivers.slice(),
          human_review_complete: demoGates.human_review_complete,
          status: "DRAFTING",
          project_version: 13
        }
      });
    }
    function demoNoAddendumConfirm(m) {
      const reason = String(m.reason || "");
      if (!reason.trim()) return fail(m.id, "bad_args", "演示模式：reason 必填——确认理由不得为空白（不可审计的确认不成确认）");
      if (demoAddenda.readiness.total > 0) {
        return fail(m.id, "bad_args", "演示模式：项目已有补遗/澄清件（共 " + demoAddenda.readiness.total + " 件在场）——「确认本项目无补遗」与事实矛盾。坏件的正确出口是逐件确认（record_addendum_waiver file_id=…）或修复重传；全局确认只适用于「未发现补遗」的阻塞（NotProvided）");
      }
      const at = Math.floor(Date.now() / 1000);
      const g = demoGates.gates.find((x) => x.gate === "no_addendum_confirmed");
      if (g) {
        g.approved = true;
        g.latest_pass = { gate: "no_addendum_confirmed", actor: "shell-operator", actor_type: "human", method: "human_receipt", human_confirmed: true, at: at, reason: reason };
      }
      demoGateRevSeq += 1;
      demoGates.reviews.unshift({ id: "REV-" + String(demoGateRevSeq).padStart(4, "0"), gate: "no_addendum_confirmed", decision: "APPROVED", reviewer: "human:shell-operator", actor: { actor_id: "shell-operator", actor_type: "human", authentication_method: "hmac_receipt_v2" }, findings: [], at: at, reviewed_content_digest: "demo-digest" });
      demoGates.agent_waivers = demoGates.gates.filter((x) => x.latest_pass && x.latest_pass.human_confirmed === false).map((x) => x.latest_pass);
      demoGates.human_review_complete = demoGates.agent_waivers.length === 0;
      return respond(m.id, {
        present: true,
        workspace: root,
        project: demoAddenda.project,
        no_addendum_confirm: {
          confirmed_no_addendum: { review_id: "REV-" + String(demoGateRevSeq).padStart(4, "0"), gate: "no_addendum_confirmed", reason: reason, at: at, actor: { actor_id: "shell-operator", actor_type: "human", authentication_method: "hmac_receipt_v2" }, method: "human_receipt", human_confirmed: true },
          addendum_waivers: demoAddenda.waivers.slice(),
          addendum_readiness: { total: 0, ready: 0, not_ready: [] },
          agent_waivers: demoGates.agent_waivers.slice(),
          human_review_complete: demoGates.human_review_complete,
          status: "DRAFTING",
          project_version: 14
        }
      });
    }
    let demoGateRevSeq = 2;
    function demoGatePass(m) {
      const gate = String(m.gate || "");
      const decision = String(m.decision || "APPROVED").toUpperCase();
      const actor = String(m.actor_id || "shell-operator");
      const at = Math.floor(Date.now() / 1000);
      const g = demoGates.gates.find((x) => x.gate === gate);
      if (!g) return fail(m.id, "bad_args", "演示模式：gate 非法（合法值：matrix_approval|outline_approval|pre_export_confirm|addendum_waiver）");
      // 门序模拟（三主门）：矩阵 → 大纲 → 导出确认
      const order = ["matrix_approval", "outline_approval", "pre_export_confirm"];
      if (order.indexOf(gate) >= 0) {
        for (let i = 0; i < order.indexOf(gate); i++) {
          if (!demoGates.gates.find((x) => x.gate === order[i]).approved) {
            return fail(m.id, "state", "当前状态 DRAFTING 不允许调用 record_review(" + gate + ")——前置门 " + order[i] + " 未 Approved（门序强制）");
          }
        }
      }
      if (decision === "REJECTED" && !(Array.isArray(m.findings) && m.findings.some((f) => String(f.severity || "").toUpperCase() === "BLOCKER"))) {
        return fail(m.id, "bad_args", "演示模式：Rejected 必须携带至少一条 BLOCKER finding（Warning 不构成拒审依据——诚实状态）");
      }
      const pass = { gate, actor, actor_type: "human", method: "human_receipt", human_confirmed: true, at, reason: m.reason || "" };
      if (decision === "APPROVED") g.approved = true;
      g.latest_pass = pass;
      demoGateRevSeq += 1;
      demoGates.reviews.unshift({ id: "REV-" + String(demoGateRevSeq).padStart(4, "0"), gate, decision, reviewer: "human:" + actor, actor: { actor_id: actor, actor_type: "human", authentication_method: "hmac_receipt_v2" }, findings: [], at, reviewed_content_digest: "demo-digest" });
      demoGates.agent_waivers = demoGates.gates.filter((x) => x.latest_pass && x.latest_pass.human_confirmed === false).map((x) => x.latest_pass);
      demoGates.human_review_complete = demoGates.agent_waivers.length === 0;
      const approved = demoGates.gates.filter((x) => x.approved).map((x) => x.gate);
      return respond(m.id, {
        present: true,
        workspace: root,
        project: demoGates.project,
        gate_pass: {
          receipt: { review_id: "REV-" + String(demoGateRevSeq).padStart(4, "0"), gate, decision, reviewer: "human:" + actor, actor: { actor_id: actor, actor_type: "human", authentication_method: "hmac_receipt_v2" }, method: "human_receipt", human_confirmed: true, finding_ids: [], spawned_rt_ids: [], reviewed_content_digest: "demo-digest" },
          gates_approved: approved,
          agent_waivers: demoGates.agent_waivers.slice(),
          human_review_complete: demoGates.human_review_complete,
          status: "DRAFTING",
          project_version: 12
        }
      });
    }
    return {
      mode: "demo",
      post(msg) {
        const m = msg || {};
        window.setTimeout(() => {
          switch (m.cmd) {
            case "ping":
              return respond(m.id, { pong: true, t: Date.now() });
            case "app.info":
              return respond(m.id, { version: "0.1.0-demo", workspace: root, ui_dir: "", exe: "mang-app.exe" });
            case "bid.state":
              return respond(m.id, DEMO_BID.state);
            case "bid.outline":
              return respond(m.id, DEMO_BID.outline);
            case "bid.matrix":
              return respond(m.id, DEMO_BID.matrix);
            case "bid.addenda":
              // #603 批 C：演示桥回可变补遗台账（waiver 会真改——已确认件审计不消失）
              return respond(m.id, demoAddenda);
            case "bid.addendum_waiver":
              return demoAddendumWaiver(m);
            case "bid.no_addendum_confirm":
              return demoNoAddendumConfirm(m);
            case "bid.quality":
              return respond(m.id, DEMO_BID.quality);
            case "bid.score":
              return respond(m.id, DEMO_BID.score);
            case "bid.gates":
              // #603 批 A：演示桥回可变台账（gate_pass 会真改——追认后消项）
              return respond(m.id, demoGates);
            case "bid.gate_pass":
              return demoGatePass(m);
            case "bid.packages":
              // #20 演示桥：分包 stub（真实壳 = 工具面 list_packages——#316 识别面）
              return respond(m.id, {
                present: true,
                workspace: root,
                project: { id: "PRJ-DEMO-0001", name: "演示水厂项目", status: "DRAFTING" },
                packages: {
                  detected: 2,
                  items: [
                    { id: "PKG-A", label: "一标段：设备采购", kind: "标段", number: "1", req_count: 42, sources: ["A-招标文件.docx"], selected: true },
                    { id: "PKG-B", label: "二标段：安装服务", kind: "标段", number: "2", req_count: 18, sources: ["A-招标文件.docx"], selected: false }
                  ],
                  shared_req_count: 6,
                  total_requirements: 60,
                  selected_package: { id: "PKG-A", label: "一标段：设备采购", kind: "标段", number: "1" },
                  usage: "build_outline 传 package=<id|label|number> 选定投哪个包（共用条款自动进纲）；投全部 = 每包各建一个项目",
                  status: "DRAFTING",
                  project_version: 3
                }
              });
            case "bid.matrix_override":
              // #20 演示桥：人工裁定 stub（真实壳 = 宿主签发 receipt → set_matrix_override）
              return respond(m.id, {
                present: true,
                workspace: root,
                project: { id: "PRJ-DEMO-0001", name: "演示水厂项目", status: "DRAFTING" },
                override: {
                  requirement_id: m.requirement_id || "REQ-0001",
                  status: m.status || "NOT_APPLICABLE",
                  from_status: "NOT_RESPONDED",
                  blocking_after: 2,
                  audit: { actor_id: "shell-operator", at: Math.floor(Date.now() / 1000), method: "human_receipt" }
                }
              });
            case "bid.recover_state":
              // #20 演示桥：异常态恢复 stub（真实壳 = 工具面 recover_validating_state——三重约束守门）
              return respond(m.id, {
                present: true,
                workspace: root,
                project: { id: "PRJ-DEMO-0001", name: "演示水厂项目", status: "DRAFTING" },
                recover: { from_status: "VALIDATING", to_status: "DRAFTING", recovered_sections: ["SEC-T03"], audit_reason: m.reason || "" }
              });
            case "bid.coverage":
              return respond(m.id, DEMO_BID.coverage);
            case "bid.create_project":
              // #19：演示桥——向导第一步（真实壳经 bid_mcp 工具面幂等建项）
              return respond(m.id, { present: true, project_id: "PRJ-DEMO-19", status: "DRAFT", warnings: [] });
            case "bid.import_files": {
              // #19：演示桥——向导第二步（per_file / totals / 就绪面同形；
              // 依据请求 files 数组装回显，验证参数面与真实壳一致）。
              // R3（#47）：补部分成功教学面——「损坏件」按真实 E_PARTIAL
              // 转换后的同形态回 partial:true + item_errors + FAILED 行
              // （成功件照常入库——与真实壳口径一字不差）。
              const fl = (m.files || []).map((f, i) => {
                const broken = /损坏件/.test(String(f.filename || f.upload_ref || ""));
                return {
                  file_id: "TF-00" + (i + 1), filename: f.filename || f.upload_ref, kind: f.kind || "附件",
                  sha256: broken ? "demo-broken" : "demo", pages: broken ? 0 : 12, tables: broken ? 0 : 3,
                  chunks: broken ? 0 : 48, ocr_tier: broken ? "none" : "text",
                  parse_status: broken ? "failed" : "ok", deduplicated: false
                };
              });
              const brokenFl = fl.filter((f) => f.parse_status === "failed");
              const out = {
                present: true, file_ids: fl.map((f) => f.file_id), per_file: fl,
                totals: { files: fl.length, chunks: fl.reduce((s, f) => s + f.chunks, 0), parse_failed: brokenFl.length, partial: brokenFl.length },
                addendum_readiness: { total: 0, ready: 0, not_ready: [] },
                input_integrity: { complete: true, restricted: false, unready: [], waived_unready: [] },
                status: "FILES_IMPORTED", warnings: []
              };
              if (brokenFl.length) {
                out.partial = true;
                out.partial_what = "import_tender_files：" + brokenFl.length + " 件解析失败（演示桥教学面）";
                out.item_errors = brokenFl.map((f) => f.filename + "：parse FAILED（0 页 0 块——损坏件全程禁引）");
              }
              return respond(m.id, out);
            }

            case "fs.tree":
              return respond(m.id, tree);
            case "fs.read": {
              // #313 批 A：章节详情面——演示桥回 chapters/SEC-xxxx.json（与真实壳同形）
              const secMatch = /chapters[/\\](SEC-[\w-]+)\.json$/i.exec(String(m.path || ""));
              if (secMatch) {
                const rec = { section_id: secMatch[1], content: demoChapterContent(secMatch[1]), char_count: 0, attempt: 1, citations: [], updated_at: Math.floor(now / 1000) };
                const recText = JSON.stringify(rec);
                return respond(m.id, { path: root + "\\" + String(m.path).replace(/[/\\\\]+/g, "\\"), bytes: recText.length, text: recText, mtimeMs: now });
              }
              const d = findDoc(m.path);
              if (!d) {
                const name = baseName(m.path || "") || "\u793A\u4F8B\u6587\u6863";
                const demo = "# " + name + "\n\n> \u6F14\u793A\u6A21\u5F0F\uFF1A\u8FD9\u4E2A\u6587\u4EF6\u4E0D\u5728\u793A\u4F8B\u6570\u636E\u91CC\uFF0C\u4E0B\u9762\u662F\u5360\u4F4D\u5185\u5BB9\u3002\n\n- \u6253\u5F00\u771F\u5B9E\u7684 " + name + " \u8BF7\u7528 mang-app.exe \u542F\u52A8\u5E76\u6307\u5B9A\u5DE5\u4F5C\u533A\n- \u4FA7\u680F\u300C\u6253\u5F00\u6587\u4EF6\u5939\u300D\u53EF\u5207\u6362\u5DE5\u4F5C\u533A\n";
                return respond(m.id, { path: m.path, bytes: demo.length, text: demo, mtimeMs: Date.now() });
              }
              if (/\.(md|txt)$/i.test(d.path)) {
                return respond(m.id, { path: d.path, bytes: mdDoc.length, text: mdDoc, mtimeMs: d.mtime });
              }
              return fail(m.id, "unsupported", "\u6F14\u793A\u6A21\u5F0F\u53EA\u80FD\u9884\u89C8 .md/.txt\uFF1B\u4E8C\u8FDB\u5236\u6587\u4EF6\u8BF7\u7528 mang-app.exe \u6253\u5F00");
            }
            case "fs.writeBytes": {
              // #313 批 B：矩阵导出落盘（.mang/exports/）——演示桥回同形结果
              const relPath = String(m.path || "").replace(/[/\\]+/g, "\\");
              return respond(m.id, { path: root + "\\" + relPath, rel: String(m.path || ""), bytes: ((m.data || "").length * 3) / 4 | 0 });
            }
            case "fs.readBytes":
              return fail(m.id, "unsupported", "\u6F14\u793A\u6A21\u5F0F\u4E0D\u652F\u6301\u4E8C\u8FDB\u5236\u8BFB\u53D6\uFF08\u8BF7\u7528 mang-app.exe \u6253\u5F00\uFF09");
            case "recent.load":
              return respond(m.id, { items: recent.slice() });
            case "recent.save":
              if (Array.isArray(m.items)) recent = m.items.slice();
              return respond(m.id, { ok: true });
            case "dialog.openFile":
            case "dialog.openFolder":
              return fail(m.id, "unsupported", "\u6F14\u793A\u6A21\u5F0F\u65E0\u6CD5\u5F39\u51FA\u7CFB\u7EDF\u6587\u4EF6\u5BF9\u8BDD\u6846");
            case "explorer.reveal":
              return respond(m.id, { ok: true });
            case "history.list": {
              const now2 = Date.now();
              return respond(m.id, { items: [
                { ts: now2 - 36e5, kind: "ai", message: "第2章 技术方案完成", file: "技术标.md", snapshot: "demo/1.md" },
                { ts: now2 - 108e5, kind: "auto", message: "", file: "技术标.md", snapshot: "demo/2.md" }
              ] });
            }
            case "snapshots.check":
              return respond(m.id, { saved: [], skipped: (m.paths || []).map((p) => ({ file: p, reason: "演示模式" })) });
            case "snapshots.save":
              return respond(m.id, { ok: true, file: m.path, ts: Date.now(), snapshot: "demo/" + Date.now() + ".md" });
            case "snapshots.read": {
              const c1 = "# \u6280\u672F\u6807\uFF08\u7B2C2\u7AE0\u5B8C\u6210\u540E\u7684\u7248\u672C\uFF09\n\n> \u6F14\u793A\u6A21\u5F0F\uFF1A\u5FEB\u7167\u6B63\u6587\u5360\u4F4D\u3002\n\n## \u7B2C1\u7AE0 \u6982\u8FF0\n\n\u672C\u6587\u6863\u4E3A\u6F14\u793A\u5360\u4F4D\uFF0C\u7528\u4E8E\u5C55\u793A\u7248\u672C diff\u3002\n\n## \u7B2C2\u7AE0 \u6280\u672F\u65B9\u6848\n\n- \u5206\u5E03\u5F0F\u67B6\u6784\uFF1A\u4E3B\u5907\u53CC\u6D3B\n- \u5B58\u50A8\uFF1A\u5206\u5E03\u5F0F\u6570\u636E\u5E93\n- \u76D1\u63A7\uFF1A\u5168\u94FE\u8DEF\u8FFD\u8E2A\n\n## \u7B2C3\u7AE0 \u5B9E\u65BD\u8BA1\u5212\n\n\uFF08\u5F85\u7EED\uFF09";
              const c2 = "# \u6280\u672F\u6807\uFF08\u521D\u7A3F\uFF09\n\n> \u6F14\u793A\u6A21\u5F0F\uFF1A\u5FEB\u7167\u6B63\u6587\u5360\u4F4D\u3002\n\n## \u7B2C1\u7AE0 \u6982\u8FF0\n\n\u672C\u6587\u6863\u4E3A\u6F14\u793A\u5360\u4F4D\u3002\n\n## \u7B2C2\u7AE0 \u6280\u672F\u65B9\u6848\n\n\uFF08\u5F85\u5199\uFF09";
              const content = String(m.snapshot || "").endsWith("2.md") ? c2 : c1;
              return respond(m.id, { content, bytes: content.length });
            }
            
            case "snapshots.rollback":
              return respond(m.id, { ok: true, file: m.file, snapshot: m.snapshot, bytes: 128, backupTs: Date.now() });
            case "annotations.load": {
              const isDemoMd = /\u6280\u672F\u6807\.md$/.test(String(m.path || ""));
              return respond(m.id, isDemoMd ? {
                file: m.path, present: true,
                items: [
                  { id: "1", block: "b4", quote: "\u672C\u6B21\u6295\u6807\u65B9\u6848\u91C7\u7528\u5206\u5E03\u5F0F\u67B6\u6784",
                    source: { file: "\u62DB\u6807\u6587\u4EF6.docx", page: 12, section: "3.2", quote: "\u6295\u6807\u4EBA\u987B\u63D0\u4F9B\u5206\u5E03\u5F0F\u67B6\u6784\u65B9\u6848" },
                    status: "pending", note: "" },
                  { id: "2", block: "b9", quote: "\u4E09\u3001\u98CE\u9669\u63A7\u5236",
                    source: { file: "\u62DB\u6807\u6587\u4EF6.docx", page: 18, section: "6.1", quote: "\u6295\u6807\u4EBA\u5E94\u5236\u5B9A\u98CE\u9669\u5E94\u5BF9\u63AA\u65BD\u4E0E\u7F13\u91CA\u673A\u5236" },
                    status: "confirmed", note: "\u5DF2\u5BF9\u7167\u8BC4\u5206\u529E\u6CD5\u7B2C\u516D\u7AE0" }
                ]
              } : { file: m.path, present: false, items: [] });
            }
            case "annotations.setStatus": {
              window.__demoAnno = window.__demoAnno || {};
              window.__demoAnno[m.id] = m.status;
              return respond(m.id, { ok: true, file: m.file, id: m.id, status: m.status });
            }
            default:
              return fail(m.id, "unknown_cmd", "\u6F14\u793A\u6A21\u5F0F\u672A\u5B9E\u73B0\u8BE5\u547D\u4EE4\uFF1A" + m.cmd);
          }
        }, 15);
      },
      onEvent(cb) {
        listeners.add(cb);
        return () => listeners.delete(cb);
      }
    };
  }
  var state = {
    bridge: null,
    booted: false,
    theme: "light",
    workspace: "",
    appInfo: null,
    tree: null,
    treeError: "",
    treeBusy: false,
    expanded: /* @__PURE__ */ new Set(),
    selectedRel: "",
    recent: [],
    favorites: [],
    changes: [],
    tabs: [],
    activeTabId: "",
    statusBar: { cursor: "", saved: "idle", savedText: "", message: "", annotations: "" },
    busyOps: 0,
    /** 是否运行在桌面壳里（自绘标题栏/窗口按钮只在这种模式下启用） */
    nativeChrome: false,
    // git 数据（「改动」面板）：{ status, available, branch, items, log, error }
    git: { status: "idle", available: false, branch: "", items: [], log: [], error: "" },
    // 版本快照（issue #42 阶段 7）：{ status, file, entries, error }
    snapshots: { status: "idle", file: "", entries: [], error: "" },
    // #313 批 A/B/C/D：标书数据面（bid.state / bid.outline / bid.matrix 拉取缓存）
    // + 大纲树折叠态 + 矩阵筛选/分页/展开态（mx）+ 覆盖报告展开态（cov）
    // ——面板本地 UI 态，随数据面重置
    bid: {
      status: "idle", present: false, data: null, outline: null, error: "", ts: 0,
      matrix: { status: "idle", data: null, error: "" },
      mx: { status: "", cat: "", blockingOnly: false, page: 1, pageSize: 50, expandedId: "", formReq: "", passing: false, passError: "", passInfo: "" },
      coverage: { status: "idle", data: null, error: "", code: "" },
      cov: { expandedFile: "" }
    },
    bidCollapsed: /* @__PURE__ */ new Set(),
    // #313 批 C：自评数据面（bid.quality + bid.score 拉取缓存——工作台「自评」页签用）。
    // code 透传壳侧错误码：state = 项目未到 MatrixReady+（UI 显示「尚未开放」引导而非故障）
    bidQuality: { status: "idle", quality: null, score: null, error: "", code: "", scoreError: "", ts: 0 },
    // #603 批 A：治理面（审核门台账 + 过门/追认写面）——与 bidQuality 同款
    // 生命周期（idle/loading/ready/error + code 分支引导卡）
    bidGates: { status: "idle", data: null, error: "", code: "", ts: 0, passing: false, passError: "", passInfo: "", formGate: "", formMode: "" },
    // #19：导入向导（空态引导卡）——新建项目（bid.create_project）→
    // 导入招标文件（bid.import_files）。向导是工作台空态的主内容，
    // 独立于面板态（面板数据由 bid.state 系列管理，向导只管表单/选择/结果）
    bidWizard: {
      createBusy: false, createError: "",
      treeStatus: "idle", treeError: "", files: [], sel: {},
      importBusy: false, importError: "", result: null
    },
    // #18 出口闭环（校验报告 + 导出落盘）：validate 报告面与 export 写面
    // 分开记——报告可独立重看，导出有自己的 loading/产物回显；两码
    // （state/not_found/bad_args）都走引导卡而非错误横幅
    bidExport: {
      status: "idle", report: null, error: "", code: "", ts: 0,
      exporting: false, format: "docx", path: "", darkBid: false, bidderName: "",
      done: null, doneError: "", doneCode: "",
    },
    // #20 分包视图（bid.packages 只读拉取缓存——工作台「分包」页签用）
    bidPackages: { status: "idle", data: null, error: "" },
    // #603 批 C：补遗台账 + 豁免写面（gates 面板补遗门接线用）
    bidAddenda: { status: "idle", data: null, error: "", ts: 0, waiving: false, waiveError: "", waiveInfo: "", formOpen: false, formGlobal: false },
  };
  var SIDEBARS = [
    { id: "files", icon: "files", title: "\u8D44\u6E90\u7BA1\u7406\u5668", key: "Ctrl+Shift+E" },
    { id: "bid", icon: "bid", title: "标书", key: "Ctrl+Shift+B" },
    { id: "outline", icon: "outline", title: "\u5927\u7EB2", key: "Ctrl+Shift+U" },
    { id: "history", icon: "history", title: "\u5386\u53F2", key: "Ctrl+Shift+H" },
    { id: "changes", icon: "changes", title: "\u6539\u52A8", key: "Ctrl+Shift+G" },
    { id: "star", icon: "star", title: "\u6536\u85CF", key: "Ctrl+Shift+S" },
    { id: "settings", icon: "settings", title: "\u8BBE\u7F6E", key: "Ctrl+," }
  ];
  function activeTab() {
    for (const t of state.tabs) if (t.id === state.activeTabId) return t;
    return null;
  }
  var pending = /* @__PURE__ */ new Map();
  var ipcSeq = 0;
  function isSpillEnvelope(result) {
    if (!result || typeof result !== "object") return false;
    if (result.inline !== false) return false;
    const f = result.file;
    return typeof f === "string" && f.length > 0 && !/[:\\/]/.test(f);
  }
  async function materializeBigResult(result) {
    if (!isSpillEnvelope(result)) return result;
    const url = "/__ipc/" + encodeURIComponent(result.file);
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw Object.assign(new Error("\u8BFB\u53D6\u5927\u54CD\u5E94\u5931\u8D25\uFF08HTTP " + res.status + "\uFF09"), { code: "ipc_file" });
    const text = await res.text();
    let body;
    try {
      body = JSON.parse(text);
    } catch (e) {
      throw Object.assign(new Error("\u5927\u54CD\u5E94\u4E0D\u662F\u5408\u6CD5 JSON\uFF1A" + e.message), { code: "ipc_file" });
    }
    // spill 落盘的是**完整响应壳**（ipc.rs::spill_if_large 写的是整个 resp）：
    //   { id, ok, result: { ...真实结果... } }
    // 调用方（如 fs.readBytes 读 r.data）期望的却是**解包后的 result 本体**。
    // 旧实现把壳塞进 result.payload，谁都没读 → 大文件静默变空（PDF「数据为空」）。
    if (body && typeof body === "object" && body.result && typeof body.result === "object") {
      return body.result;
    }
    return body && typeof body === "object" ? body : result;
  }
  function ipc(cmd, args, timeoutMs) {
    const payload = Object.assign({}, args || {});
    return new Promise((resolve, reject) => {
      if (!state.bridge) {
        reject(Object.assign(new Error("\u5BBF\u4E3B\u6865\u672A\u5C31\u7EEA"), { code: "no_bridge" }));
        return;
      }
      const id = "r" + ++ipcSeq;
      pending.set(id, { resolve, reject });
      window.setTimeout(() => {
        if (pending.has(id)) {
          pending.delete(id);
          reject(Object.assign(new Error("\u8BF7\u6C42\u8D85\u65F6\uFF1A" + cmd), { code: "timeout" }));
        }
      }, timeoutMs || 2e4);
      payload.id = id;
      payload.cmd = cmd;
      state.bridge.post(payload);
    });
  }
  function onBridgeEvent(ev) {
    if (!ev || typeof ev !== "object") return;
    if (ev.id && pending.has(ev.id)) {
      const p = pending.get(ev.id);
      pending.delete(ev.id);
      if (ev.ok) {
        materializeBigResult(ev.result).then(
          p.resolve,
          (e) => p.reject(Object.assign(new Error(e.message || "\u5927\u54CD\u5E94\u8BFB\u53D6\u5931\u8D25"), { code: "ipc_file" }))
        );
      } else {
        const err = ev.error || { code: ev.code, message: ev.message };
        p.reject(
          Object.assign(new Error(err.message || ev.message || "IPC \u5931\u8D25"), {
            code: err.code || ev.code || "ipc",
            detail: err
          })
        );
      }
      return;
    }
    if (ev.ev === "drop") {
      ui.onDrop(Array.isArray(ev.paths) ? ev.paths : []);
      return;
    }
    // #76：LLM 连接测试的异步回执（后台线程 HTTP 完成后由壳推送）
    if (ev.ev === "llm.test") {
      DIAG.llmTest = ev;
      DIAG.llmTestBusy = false;
      updateLlmTestResult();
      return;
    }
    if (ev.ev === "window" && ev.maximized !== void 0) {
      ui.setMaximized(!!ev.maximized);
      // 桌面壳的窗口缩放不会触发 window resize（见 reportWindowButtonsWidth 注释），
      // 但最大化/还原后布局确实变了 —— 这里主动补一次重排，
      // 否则按最大化尺寸排好的视图缩回去仍用旧尺寸，外圈会被裁掉。
      relayoutAfterWindowChange();
      return;
    }
    if (ev.ev === "theme") {
      if (settings.theme === "system") applyTheme();
      return;
    }
  }
  function boot() {
    state.bridge = createBridge();
    state.nativeChrome = !!(window.__mangShell && state.bridge.mode === "host");
    settings.sidebarActive = "files";
    settings.sidebarVisible = true;
    document.documentElement.dataset.chrome = state.nativeChrome ? "native" : "browser";
    renderWindowControls();
    if (state.nativeChrome) {
      ipc("window.info", {}, 4e3).then((info) => {
        if (info && typeof info.maximized === "boolean") ui.setMaximized(info.maximized);
        if (info && info.captionHeight) {
          document.documentElement.style.setProperty("--h-menubar", info.captionHeight + "px");
        }
      }).catch(() => {
      });
    }
    loadRenderer("docx_view").catch(() => {
    });
    applyTheme();
    renderActivityBar();
    renderMenus();
    renderTabs();
    renderSidebar();
    renderEmpty();
    renderStatusBar();
    bindShellEvents();
    applyLayoutSettings();
    state.bridge.onEvent(onBridgeEvent);
    if (state.bridge.mode === "host") {
      ipc("app.info", {}, 5e3).then((info) => {
        state.appInfo = info;
        state.workspace = info && info.workspace || "";
        setWorkspaceLabel(state.workspace);
        ui.refreshTree();
      }).catch((e) => ui.toast("error", "\u65E0\u6CD5\u8BFB\u53D6\u5E94\u7528\u4FE1\u606F\uFF1A" + e.message));
    } else {
      document.body.dataset.bridge = "demo";
      state.workspace = String.raw`C:\演示工作区`;
      setWorkspaceLabel(state.workspace + "\uFF08\u6F14\u793A\uFF09");
      ui.refreshTree();
    }
    loadRecent().then(() => {
      renderEmpty();
      renderHistoryViewIfVisible();
    });
    markBooted();
  }
  function markBooted() {
    if (state.booted) return;
    state.booted = true;
    document.documentElement.dataset.mangReady = "1";
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ ev: "ready", bridge: state.bridge.mode }, "*");
      }
    } catch (e) {
    }
  }
  async function loadRecent() {
    try {
      const r = await ipc("recent.load", {}, 4e3);
      state.recent = r && Array.isArray(r.items) ? r.items : [];
    } catch (e) {
      state.recent = [];
    }
  }
  function saveRecent() {
    state.recent = state.recent.slice(0, 50);
    ipc("recent.save", { items: state.recent }, 4e3).catch(() => {
    });
  }
  function touchRecent(path) {
    const name = baseName(path);
    state.recent = [{ path, name, openedAt: Date.now() }].concat(
      state.recent.filter((r) => r.path !== path)
    );
    saveRecent();
  }
  // #194：工作区目录进最近列表（kind="dir"——与文件区分图标/语义）。
  function touchRecentWorkspace(path) {
    const name = baseName(path) || path;
    state.recent = [{ path, name, kind: "dir", openedAt: Date.now() }].concat(
      state.recent.filter((r) => r.path !== path)
    );
    saveRecent();
  }
  var menusById = {};
  function menuDefs() {
    return [
      {
        id: "file",
        label: "\u6587\u4EF6",
        items: [
          { label: "\u6253\u5F00\u6587\u4EF6\u2026", key: "Ctrl+O", act: () => ui.openFileDialog() },
          { label: "\u6253\u5F00\u5DE5\u4F5C\u533A\u2026", key: "Ctrl+K Ctrl+O", act: () => ui.openFolderDialog() },
          { sep: true },
          { label: "\u5173\u95ED", key: "Ctrl+W", act: () => ui.closeActiveTab(), enabled: () => !!activeTab() },
          { label: "\u5173\u95ED\u5176\u4ED6", act: () => ui.closeOtherTabs(), enabled: () => state.tabs.length > 1 },
          { label: "\u5173\u95ED\u5168\u90E8", act: () => ui.closeAllTabs(), enabled: () => state.tabs.length > 0 },
          { sep: true },
          { label: "\u4FDD\u5B58", key: "Ctrl+S", act: () => ui.saveActive(), enabled: () => !!activeTab() },
          { label: "\u53E6\u5B58\u4E3A\u2026", act: () => ui.saveActiveAs(), enabled: () => !!activeTab() },
          { sep: true },
          { label: "\u5237\u65B0\u6587\u4EF6\u6811", key: "F5", act: () => ui.refreshTree() },
          { sep: true },
          { label: "\u9000\u51FA", key: "Alt+F4", act: () => ui.quit() }
        ]
      },
      {
        id: "edit",
        label: "\u7F16\u8F91",
        items: [
          { label: "\u64A4\u9500", key: "Ctrl+Z", disabled: true },
          { label: "\u91CD\u505A", key: "Ctrl+Y", disabled: true },
          { sep: true },
          { label: "\u67E5\u627E\u2026", key: "Ctrl+F", act: () => ui.findInDocument() },
          { label: "\u590D\u5236\u6587\u4EF6\u8DEF\u5F84", key: "Ctrl+Alt+C", act: () => ui.copyActivePath(), enabled: () => !!activeTab() }
        ]
      },
      {
        id: "view",
        label: "\u67E5\u770B",
        items: [
          { label: "\u5207\u6362\u4FA7\u680F", key: "Ctrl+B", act: () => ui.toggleSidebar() },
          { label: "\u5207\u6362\u72B6\u6001\u680F", act: () => ui.toggleStatusBar() },
          { sep: true },
          { label: "\u8D44\u6E90\u7BA1\u7406\u5668", key: "Ctrl+Shift+E", act: () => ui.showSidebar("files") },
          { label: "标书", key: "Ctrl+Shift+B", act: () => ui.showSidebar("bid") },
          { label: "标书工作台", act: () => ui.openBidWorkbench() },
          { label: "\u5927\u7EB2", key: "Ctrl+Shift+U", act: () => ui.showSidebar("outline") },
          { label: "\u5386\u53F2", key: "Ctrl+Shift+H", act: () => ui.showSidebar("history") },
          { label: "\u6539\u52A8", key: "Ctrl+Shift+G", act: () => ui.showSidebar("changes") },
          { label: "\u6536\u85CF", key: "Ctrl+Shift+S", act: () => ui.showSidebar("star") },
          { sep: true },
          { label: "\u4E3B\u9898\uFF1A\u8DDF\u968F\u7CFB\u7EDF", act: () => ui.setTheme("system"), checked: () => settings.theme === "system" },
          { label: "\u4E3B\u9898\uFF1A\u6D45\u8272", act: () => ui.setTheme("light"), checked: () => settings.theme === "light" },
          { label: "\u4E3B\u9898\uFF1A\u6DF1\u8272", act: () => ui.setTheme("dark"), checked: () => settings.theme === "dark" },
          { sep: true },
          { label: "\u91CD\u65B0\u52A0\u8F7D\u754C\u9762", key: "Ctrl+R", act: () => location.reload() }
        ]
      },
      {
        id: "help",
        label: "\u5E2E\u52A9",
        items: [
          { label: "\u5FEB\u6377\u952E\u901F\u67E5", key: "Ctrl+K Ctrl+S", act: () => ui.showShortcuts() },
          { label: "\u5173\u4E8E mang", act: () => ui.showAbout() }
        ]
      }
    ];
  }
  function renderMenus() {
    menusById = {};
    const defs = menuDefs();
    for (const m of defs) menusById[m.id] = m;
    const host = $("#menubar-menus");
    host.innerHTML = defs.map(
      (m) => '<button class="menu-btn" role="menuitem" aria-haspopup="true" aria-expanded="false" data-menu="' + esc(m.id) + '">' + esc(m.label) + "</button>"
    ).join("");
    host.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-menu]");
      if (!btn) return;
      const rect = btn.getBoundingClientRect();
      const wasOpen = btn.getAttribute("aria-expanded") === "true";
      closeOverlays();
      if (wasOpen) return;
      btn.setAttribute("aria-expanded", "true");
      openMenu(menusById[btn.dataset.menu], { x: rect.left, y: rect.bottom + 2 }, "menubar");
    });
  /**
   * 桌面壳里窗口尺寸变了（最大化 / 还原）之后补一次布局。
   * 壳用 SetWindowPos 改几何，WebView 的 resize 事件不保证触发；
   * 这里先在下一帧、再晚 120ms / 400ms 各做一次，覆盖 WebView 排版慢一拍的情况。
   */
  function relayoutAfterWindowChange() {
    const run = () => {
      try {
        // 派发一次 resize，让各视图按新容器尺寸重新测量
        window.dispatchEvent(new Event("resize"));
      } catch (_) {
      }
    };
    requestAnimationFrame(run);
    setTimeout(run, 120);
    setTimeout(run, 400);
  }
  }
  /**
   * 已上报过的按钮占位宽度（**DIP / CSS 像素**），用来避免重复上报。
   *
   * ⚠ 单位约定：getBoundingClientRect() 返回的已经是 CSS 像素，而壳侧的
   * BUTTONS_W 也按「逻辑像素」存、命中测试时才乘一次 DPI。所以这里**绝不能**
   * 自己再乘 devicePixelRatio，否则 125%/150% 缩放下标题栏右侧会多出一大段
   * 既不是按钮、也不响应拖动的死区。
   */
  let reportedButtonsW = 0;
  function measureWindowButtons() {
    const host = $("#window-controls");
    if (!host || host.hidden) return 0;
    const r = host.getBoundingClientRect();
    // 只留一点右侧余量（圆角），单位仍是 CSS 像素
    return Math.round(r.width + 8);
  }
  function reportWindowButtonsWidth(force) {
    if (!state.nativeChrome) return;
    // 布局没算完时 getBoundingClientRect 可能是 0，下一帧再试一次
    const w = measureWindowButtons();
    if (!w) {
      requestAnimationFrame(() => reportWindowButtonsWidth(force));
      return;
    }
    if (!force && w === reportedButtonsW) return;
    reportedButtonsW = w;
    document.documentElement.dataset.buttonsW = String(w);
    ipc("window.buttons", { width: w }, 5e3).catch(() => {});
  }
  function renderWindowControls() {
    const host = $("#window-controls");
    if (!host) return;
    if (!state.nativeChrome) {
      host.innerHTML = "";
      host.hidden = true;
      return;
    }
    host.hidden = false;
    host.innerHTML = '<button class="winbtn" id="btn-win-min" title="\u6700\u5C0F\u5316" aria-label="\u6700\u5C0F\u5316"><svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><path d="M2 5h6" stroke="currentColor" stroke-width="1" fill="none"/></svg></button><button class="winbtn" id="btn-win-max" title="\u6700\u5927\u5316" aria-label="\u6700\u5927\u5316"><svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><rect x="2.5" y="2.5" width="5" height="5" fill="none" stroke="currentColor" stroke-width="1"/></svg></button><button class="winbtn winbtn-close" id="btn-win-close" title="\u5173\u95ED" aria-label="\u5173\u95ED"><svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><path d="m2.5 2.5 5 5M7.5 2.5l-5 5" stroke="currentColor" stroke-width="1" fill="none"/></svg></button>';
    const wmin = $("#btn-win-min");
    const wmax = $("#btn-win-max");
    const wclose = $("#btn-win-close");
    if (wmin) wmin.addEventListener("click", () => ui.winAction("minimize"));
    if (wmax) wmax.addEventListener("click", () => ui.winAction("toggle"));
    if (wclose) wclose.addEventListener("click", () => ui.winAction("close"));
    reportWindowButtonsWidth();
    watchWindowButtonsWidth();
  }
  // 给壳上报「右上角三个按钮占多宽」：壳的标题带命中测试要把这一段排除掉，
  // 否则点最大化会被当成拖窗口。只在桌面壳里报（浏览器预览没有意义）。
  // ⚠ 不用 window 的 resize：桌面壳里窗口不会真的缩放视口（无边框窗口，
  //   窗口尺寸变化时 resize 不会触发），改成盯按钮组的实际宽度。
  function watchWindowButtonsWidth() {
    if (!state.nativeChrome || typeof ResizeObserver === "undefined") return;
    const host = $("#window-controls");
    if (!host) return;
    try {
      new ResizeObserver(() => reportWindowButtonsWidth()).observe(host);
    } catch (_) {
    }
  }
  // 双击标题栏这种「系统窗口循环」改状态时，壳推 window 事件 → 按钮图标跟着换
  window.addEventListener("mang:windowstate", (e) => {
    if (e && e.detail && typeof e.detail.maximized === "boolean") ui.setMaximized(e.detail.maximized);
  });
  function renderActivityBar() {
    const bar = $("#activitybar");
    bar.innerHTML = SIDEBARS.map(
      (s) => '<button class="activity-item" role="tab" aria-selected="' + String(settings.sidebarActive === s.id) + '" data-sidebar="' + esc(s.id) + '" title="' + esc(s.title + "  (" + s.key + ")") + '" aria-label="' + esc(s.title) + '">' + ICON[s.icon] + "</button>"
    ).join("") + '<div class="activity-spacer"></div>';
    bar.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-sidebar]");
      if (!btn) return;
      ui.showSidebar(btn.dataset.sidebar);
    });
  }
  function setWorkspaceLabel(ws) {
    const el = document.getElementById("sidebar-workspace");
    if (!el) return;
    if (!ws) {
      el.textContent = "\u672A\u6253\u5F00\u5DE5\u4F5C\u533A";
      el.title = "\u70B9\u4E00\u4E0B\u9009\u62E9\u5DE5\u4F5C\u533A (Ctrl+K Ctrl+O)";
      el.dataset.empty = "1";
      return;
    }
    delete el.dataset.empty;
    const clean = String(ws).replace(/[\\/]+$/, "");
    const cut = Math.max(clean.lastIndexOf("\\"), clean.lastIndexOf("/"));
    const name = cut >= 0 ? clean.slice(cut + 1) : clean;
    el.textContent = name || clean;
    el.title = clean + "\uFF08\u70B9\u51FB\u5207\u6362\u5DE5\u4F5C\u533A\uFF09";
  }
  function renderSidebarHeader() {
    const view = SIDEBARS.find((s) => s.id === settings.sidebarActive) || SIDEBARS[0];
    const actions = {
      files: [
        { icon: "folderOpen", title: "\u5207\u6362\u5DE5\u4F5C\u533A (Ctrl+K Ctrl+O)", act: () => ui.openFolderDialog() },
        { icon: "refresh", title: "\u5237\u65B0 (F5)", act: () => ui.refreshTree() }
      ],
      history: [{ icon: "close", title: "\u6E05\u7A7A\u5386\u53F2", act: () => ui.clearRecent() }],
      changes: [],
      star: [],
      bid: [{ icon: "refresh", title: "刷新标书数据（bid.state / bid.outline）", act: () => ui.loadBid(true) }],
      settings: []
    };
    const acts = actions[view.id] || [];
    const host = $("#sidebar-actions");
    host.innerHTML = acts.map(
      (a, i) => '<button class="sidebar-action" data-act="' + i + '" title="' + esc(a.title) + '" aria-label="' + esc(a.title) + '">' + ICON[a.icon] + "</button>"
    ).join("");
    Array.prototype.forEach.call(host.querySelectorAll(".sidebar-action"), (b, i) => {
      b.addEventListener("click", () => acts[i] && acts[i].act());
    });
  }
  function syncActivitySelection() {
    Array.prototype.forEach.call(document.querySelectorAll("#activitybar .activity-item"), (b) => {
      b.setAttribute("aria-selected", String(settings.sidebarVisible && b.dataset.sidebar === settings.sidebarActive));
    });
  }
  function renderSidebar() {
    renderSidebarHeader();
    const body = $("#sidebar-body");
    const view = settings.sidebarActive;
    body.dataset.view = view;
    syncActivitySelection();
    if (view === "files") renderFilesView(body);
    else if (view === "bid") {
      if (state.bid.status === "idle") setTimeout(() => ui.loadBid(), 0);
      renderBidView(body);
    } else if (view === "outline") renderOutlineView(body);
    else if (view === "history") renderHistoryView(body);
    else if (view === "changes") {
      if (state.git.status === "idle") setTimeout(() => ui.loadGit(), 0);
      renderChangesView(body);
    } else if (view === "star") renderStarView(body);
    else renderSettingsView(body);
  }
  // ============ #313 批 A：标书数据面（bid.state / bid.outline → 侧栏视图 + 标书工作台） ============
  // 数据来源：壳侧 bid.state（经 bid_mcp::dispatch_with 走 get_bid_project_state 真实工具面
  // + project 元信息 + quick_stats）与 bid.outline（DomainStore 直读章节树）。
  // 契约：docs/mang/IPC-CONTRACT.md §6。合规矩阵/自评/覆盖报告 = 批 B/C/D（占位禁用态）。
  function bidStatusZh(s) {
    return (
      {
        PENDING: "待起草",
        OUTLINING: "大纲中",
        DRAFTING: "起草中",
        FAILED: "起草失败",
        DRAFTED: "已起草",
        VALIDATING: "校验中",
        REVISING: "修订中",
        ACCEPTED: "已验收"
      }[s] || s
    );
  }
  function bidProjectStatusZh(s) {
    return (
      {
        DRAFT: "草稿",
        FILES_IMPORTED: "已导入文件",
        REQUIREMENTS_EXTRACTED: "已抽取条款",
        MATRIX_READY: "矩阵就绪",
        EVIDENCE_BOUND: "证据已绑定",
        DRAFTING: "起草中",
        VALIDATING: "校验中",
        REVIEWING: "审核中",
        READY_TO_EXPORT: "待导出",
        EXPORTED: "已导出"
      }[s] || s
    );
  }
  function bidDrafted(status) {
    return ["DRAFTED", "VALIDATING", "REVISING", "ACCEPTED"].indexOf(status) >= 0;
  }
  function fmtChars(n) {
    return Number(n || 0).toLocaleString("zh-CN");
  }
  function renderBidViewIfVisible() {
    if (settings.sidebarActive === "bid" && settings.sidebarVisible) renderSidebar();
  }
  function bidWorkbenchTab() {
    for (const t of state.tabs) if (t.kind === "bidwork") return t;
    return null;
  }
  function renderBidWorkbenchIfOpen() {
    const tab = bidWorkbenchTab();
    if (!tab || state.activeTabId !== tab.id) return;
    const host = document.getElementById("pane-" + tab.id);
    if (host && host.querySelector(".bid-wb")) renderBidWorkbenchPanes(host);
  }
  function bidStatCell(v, label) {
    return '<div class="bid-stat"><span class="bid-stat-v">' + esc(v) + '</span><span class="bid-stat-k">' + esc(label) + "</span></div>";
  }
  function bidDisabledEntry(name, sub, batch) {
    return '<button class="bid-entry" disabled title="后续批次接线（#313 ' + esc(batch) + '）"><span class="bid-entry-icon"></span><span class="bid-entry-main"><span class="bid-entry-name">' + esc(name) + '</span><span class="bid-entry-sub">' + esc(sub) + "</span></span>" + '<span class="bid-entry-state">' + esc(batch) + " 待接线</span></button>";
  }
  function bindBidViewActions(root) {
    Array.prototype.forEach.call(root.querySelectorAll("[data-bid-act]"), (btn) => {
      btn.addEventListener("click", () => {
        const act = btn.dataset.bidAct;
        if (act === "refresh") ui.loadBid(true);
        else if (act === "open-folder") ui.openFolderDialog();
        else if (act === "workbench") ui.openBidWorkbench();
        else if (act === "workbench-mx") ui.openBidWorkbench("matrix");
        else if (act === "workbench-quality") ui.openBidWorkbench("quality");
        else if (act === "workbench-gates") ui.openBidWorkbench("gates");
        else if (act === "refresh-quality") ui.loadBidQuality(true);
        else if (act === "refresh-gates") ui.loadBidGates(true);
        else if (act === "workbench-cov") ui.openBidWorkbench("coverage");
        // #19：空态向导入口（侧栏卡按钮 / 工作台空态共用）
        else if (act === "wizard") ui.openBidWorkbench("detail");
        else if (act === "wizard-refresh-tree") ui.loadBidWizardTree(true);
        else if (act === "wizard-retry-import") ui.submitBidWizardImport();
        // #18 出口闭环：工具栏「校验并导出」（切页签 + 触发校验）/ 重新校验 /
        // 确认导出 / 产物定位
        else if (act === "validate-export") ui.openBidWorkbench("export");
        else if (act === "refresh-validate") ui.loadBidValidate(true);
        else if (act === "confirm-export") ui.runBidExport();
        else if (act === "reveal-artifact") ui.revealBidArtifact();
        else if (act === "workbench-packages") ui.openBidWorkbench("packages");

      });
    });
  }
  /** 侧栏「标书」视图：项目状态 / 门审 / 快速统计 + 工作台与四面板入口 */
  function renderBidView(body) {
    const b = state.bid;
    if (b.status === "idle" || b.status === "loading") {
      body.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>正在读取标书项目…</div></div>';
      return;
    }
    if (!b.present) {
      const notProject = b.error && b.error.indexOf("db.json") >= 0;
      body.innerHTML =
        '<div class="bid-side"><div class="bid-card" data-kind="empty">'
        + '<div class="bid-card-title">' + (notProject ? "当前工作区还不是标书项目" : "读取失败") + "</div>"
        + '<div class="bid-card-sub">' + esc(b.error || "无数据") + "</div>"
        + '<div class="bid-card-actions">'
        // #19：空工作区给「新建项目」入口（向导第一步）——不再只能切走
        + (notProject ? '<button class="btn btn-primary" data-bid-act="wizard">' + ICON.bid + "新建标书项目</button>" : "")
        + (notProject ? '<button class="btn" data-bid-act="open-folder">' + ICON.folderOpen + "切换工作区</button>" : "")
        + '<button class="btn" data-bid-act="refresh">重试</button></div>'
        + "</div></div>";
      bindBidViewActions(body);
      return;
    }
    const d = b.data || {};
    const p = d.project || {};
    const st = d.state || {};
    const q = d.quick_stats || {};
    const dirtyCount = (st.dirty_sections || []).length;
    const directives = (st.pending_rewrite_directives || []).length;
    const waivers = (st.agent_waivers || []).length;
    const human = !!st.human_review_complete;
    body.innerHTML =
      '<div class="bid-side">'
      + '<div class="bid-card">'
      + '<div class="bid-proj-row"><span class="bid-proj-name" title="' + esc(p.name) + '">' + esc(p.name || "未命名项目") + '</span><span class="bid-badge" data-status="' + esc(p.status) + '">' + esc(bidProjectStatusZh(p.status)) + "</span></div>"
      + '<div class="bid-card-sub">' + esc(p.mode || "") + " · " + esc(p.id || "") + "</div>"
      + '<div class="bid-gates">'
      + '<div class="bid-gate" data-state="' + (human ? "ok" : "pending") + '"><span class="bid-gate-dot"></span>人工复核' + (human ? "完成" : "未完成") + "</div>"
      + '<div class="bid-gate" data-state="' + (waivers ? "warn" : "ok") + '"><span class="bid-gate-dot"></span>Agent 门审声明 ' + waivers + " 项</div>"
      + (dirtyCount ? '<div class="bid-gate" data-state="warn"><span class="bid-gate-dot"></span>DIRTY 章节 ' + dirtyCount + " 个</div>" : "")
      + (directives ? '<div class="bid-gate" data-state="warn"><span class="bid-gate-dot"></span>待处置改写指令 ' + directives + " 条</div>" : "")
      + "</div>"
      + '<div class="bid-stats">'
      + bidStatCell(fmtChars(q.requirements), "条款")
      + bidStatCell(fmtChars(q.sections_leaf) + "/" + fmtChars(q.sections), "叶/总章节")
      + bidStatCell(fmtChars(q.sections_drafted), "已起草")
      + bidStatCell(fmtChars(q.evidence), "证据")
      + bidStatCell(fmtChars(q.actual_total_chars), "实际字数")
      + bidStatCell(fmtChars(q.target_total_chars), "配额字数")
      + "</div>"
      + '<div class="bid-card-sub">≈ ' + fmtChars(q.pages_estimate) + " 页（844 字/页）· " + (b.ts ? timeAgo(b.ts) : "—") + "</div>"
      + '<div class="bid-card-actions"><button class="btn btn-primary" data-bid-act="workbench">' + ICON.bid + "打开标书工作台</button></div>"
      + "</div>"
      + '<div class="bid-card"><div class="bid-card-title">面板</div>'
      + '<button class="bid-entry" data-bid-act="workbench"><span class="bid-entry-icon">' + ICON.outline + '</span><span class="bid-entry-main"><span class="bid-entry-name">大纲树</span><span class="bid-entry-sub">章节层级 · 字数进度 · 状态标记</span></span><span class="bid-entry-state ok">已接线</span></button>'
      + '<button class="bid-entry" data-bid-act="workbench-mx"><span class="bid-entry-icon">' + ICON.grid + '</span><span class="bid-entry-main"><span class="bid-entry-name">合规矩阵</span><span class="bid-entry-sub">REQ × 响应状态 × 证据</span></span><span class="bid-entry-state ok">已接线</span></button>'
      + '<button class="bid-entry" data-bid-act="workbench-quality"><span class="bid-entry-icon">' + ICON.check + '</span><span class="bid-entry-main"><span class="bid-entry-name">自评</span><span class="bid-entry-sub">评分 · 质量摘要 · BLOCKER</span></span><span class="bid-entry-state ok">已接线</span></button>'
      + '<button class="bid-entry" data-bid-act="workbench-gates"><span class="bid-entry-icon">' + ICON.shield + '</span><span class="bid-entry-main"><span class="bid-entry-name">审核门</span><span class="bid-entry-sub">五门台账 · 追认 · 人工过门</span></span><span class="bid-entry-state ok">已接线</span></button>'
      + '<button class="bid-entry" data-bid-act="workbench-packages"><span class="bid-entry-icon">' + ICON.grid + '</span><span class="bid-entry-main"><span class="bid-entry-name">分包</span><span class="bid-entry-sub">多标段/多包识别 · 选包状态（#316）</span></span><span class="bid-entry-state ok">已接线</span></button>'
      + '<button class="bid-entry" data-bid-act="workbench-cov"><span class="bid-entry-icon"></span><span class="bid-entry-main"><span class="bid-entry-name">覆盖报告</span><span class="bid-entry-sub">已判定 / 未判定 / ★条款</span></span><span class="bid-entry-state ok">已接线</span></button>'
      + '<button class="bid-entry" data-bid-act="validate-export"><span class="bid-entry-icon">' + ICON.export + '</span><span class="bid-entry-main"><span class="bid-entry-name">校验与导出</span><span class="bid-entry-sub">缺陷清单 · 确认导出 · 产物定位</span></span><span class="bid-entry-state ok">已接线</span></button>'
      + "</div></div>";
    bindBidViewActions(body);
  }
  /** 「标书工作台」伪标签页骨架（数据由 renderBidWorkbenchPanes 就地补齐） */
  function renderBidWorkbenchView(tab, host) {
    host.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "bid-wb";
    wrap.innerHTML =
      '<header class="bid-wb-head">'
      + '<span class="bid-wb-title">' + ICON.bid + "标书工作台</span>"
      + '<span class="bid-wb-project" id="bid-wb-project"></span>'
      + '<span class="bid-wb-status" id="bid-wb-status"></span>'
      + '<span class="bid-wb-spacer"></span>'
      + '<button class="btn btn-sm btn-primary" data-bid-act="validate-export" title="先校验出报告，确认后导出成品文档（#18 出口闭环）">' + ICON.export + "校验并导出</button>"
      + '<button class="btn btn-sm" data-bid-act="refresh" title="重新读取 bid.state / bid.outline / bid.matrix / bid.coverage / 自评数据">刷新</button>'
      + "</header>"
      + '<div class="bid-wb-body">'
      + '<aside class="bid-tree" id="bid-tree" role="tree" aria-label="标书大纲树"></aside>'
      + '<section class="bid-main">'
      + '<nav class="bid-tabs" role="tablist">'
      + '<button class="bid-tab" role="tab" data-bid-panel="detail">章节详情</button>'
      + '<button class="bid-tab" role="tab" data-bid-panel="matrix">合规矩阵</button>'
      + '<button class="bid-tab" role="tab" data-bid-panel="quality">自评</button>'
      + '<button class="bid-tab" role="tab" data-bid-panel="gates">审核门</button>'
      + '<button class="bid-tab" role="tab" data-bid-panel="coverage">覆盖报告</button>'
      + '<button class="bid-tab" role="tab" data-bid-panel="export">校验与导出</button>'
      + '<button class="bid-tab" role="tab" data-bid-panel="packages">分包</button>'
      + "</nav>"
      + '<div class="bid-panel" id="bid-panel"></div>'
      + "</section></div>";
    host.appendChild(wrap);
    wrap.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-bid-act]");
      if (btn && btn.dataset.bidAct === "refresh") {
        ui.loadBid(true);
        if (state.bidQuality.status !== "idle") ui.loadBidQuality(true);
        if (state.bid.matrix && state.bid.matrix.status !== "idle") ui.loadBidMatrix(true);
        // 门台账同款（#603 批 A）
        if (state.bidGates.status !== "idle") ui.loadBidGates(true);
        if (state.bid.coverage && state.bid.coverage.status !== "idle") ui.loadBidCoverage(true);
        // #18：出口面已看过也一并刷新（报告是导出前置，不能拿旧报告导新内容）
        if (state.bidExport.status !== "idle") ui.loadBidValidate(true);
      }
      // #313 批 B/C/D：右侧页签切换（章节详情 / 合规矩阵 / 自评 / 覆盖报告）
      const tabBtn = e.target.closest('.bid-tab[data-bid-panel]');
      if (tabBtn && !tabBtn.disabled) {
        const t = bidWorkbenchTab();
        if (t && t.meta.panel !== tabBtn.dataset.bidPanel) {
          t.meta.panel = tabBtn.dataset.bidPanel;
          renderBidActivePanel(host);
        }
      }
    });
    // 页签切换（#313 批 C：自评接线；批 B/D 仍占位禁用）
    wrap.querySelectorAll(".bid-tab[data-bid-panel]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const t = bidWorkbenchTab();
        if (!t || !t.meta) return;
        if (t.meta.panel === btn.dataset.bidPanel) return;
        t.meta.panel = btn.dataset.bidPanel;
        syncBidTabBar(host, t.meta.panel);
        renderBidWorkbenchPanes(host);
      });
    });
    syncBidTabBar(host, (tab.meta && tab.meta.panel) || "detail");
    renderBidWorkbenchPanes(host);
  }
  /** 页签选中态与 tab.meta.panel 同步（aria-selected 驱动样式） */
  function syncBidTabBar(host, panel) {
    Array.prototype.forEach.call(host.querySelectorAll(".bid-tab[data-bid-panel]"), (b) => {
      b.setAttribute("aria-selected", String(b.dataset.bidPanel === panel));
    });
  }
  function bidOutlineNodes() {
    const o = state.bid.outline;
    return o && Array.isArray(o.nodes) ? o.nodes : [];
  }
  /** 可见行 = 祖先全部未被折叠的节点（nodes 本身按 order 升序——壳侧保证） */
  function bidVisibleRows(nodes) {
    const byId = {};
    nodes.forEach((n) => {
      byId[n.id] = n;
    });
    return nodes.filter((n) => {
      let cur = n;
      while (cur && cur.parent_id) {
        if (state.bidCollapsed.has(cur.parent_id)) return false;
        cur = byId[cur.parent_id];
      }
      return true;
    });
  }
  /** 工作台数据面：头部（项目/状态）+ 左树 + 右详情（选中节点） */
  function renderBidWorkbenchPanes(host) {
    if (!host || !host.querySelector) return;
    const b = state.bid;
    const projEl = host.querySelector("#bid-wb-project");
    const statEl = host.querySelector("#bid-wb-status");
    const treeEl = host.querySelector("#bid-tree");
    if (!projEl || !statEl || !treeEl) return;
    if (b.status === "idle") {
      ui.loadBid();
      return;
    }
    if (b.status === "loading") {
      projEl.textContent = "";
      statEl.textContent = "读取中…";
      treeEl.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>正在读取章节树…</div></div>';
      return;
    }
    if (!b.present) {
      // #19：空工作区 → 向导第一步（新建标书项目引导卡）——空态不再是
      // 死胡同错误页；§109 同口径：这是主路径引导，不是故障横幅
      projEl.textContent = "";
      statEl.textContent = "";
      renderBidWizardCreate(treeEl);
      const panelEl = host.querySelector("#bid-panel");
      if (panelEl) panelEl.innerHTML = '<div class="view-state"><div class="view-state-title">新建项目后开始</div><div>填左侧表单创建 db.json——项目元信息（名称/模式/截止）与招标公告编号就位后，进入文件导入</div></div>';
      return;
    }
    const p = (b.data && b.data.project) || {};
    projEl.textContent = p.name || "未命名项目";
    projEl.title = (b.data && b.data.workspace) || "";
    statEl.innerHTML = '<span class="bid-badge" data-status="' + esc(p.status) + '">' + esc(bidProjectStatusZh(p.status)) + "</span>";
    const nodes = bidOutlineNodes();
    // 右面板路由（#313 批 C）：自评页签优先——树空也能给「先建纲」引导卡
    const wbTab = bidWorkbenchTab();
    const activePanel = (wbTab && wbTab.meta && wbTab.meta.panel) || "detail";
    if (!nodes.length) {
      // #19：建项后的向导第二步——DRAFT 且未导入文件时，树区给「导入
      // 招标文件」卡（fs.tree 工作区文件勾选 + kind 分派）；已导入但未
      // 建纲（FILES_IMPORTED）给「下一步」引导（对齐 bid.coverage 的
      // next 语言——单一真源由 MCP 管线持有，UI 只引导）
      const q19 = (b.data && b.data.quick_stats) || {};
      const st19 = p.status || "";
      if (st19 === "DRAFT" && !(q19.files > 0)) {
        renderBidWizardImport(treeEl, host);
      } else if (state.bidWizard.result) {
        // #19：导入刚完成——树区给「下一步」引导（对齐 bid.coverage next 语言），
        // 右面板保留导入结果面（per_file 逐件表）
        treeEl.innerHTML = '<div class="view-state"><div class="view-state-title">文件已入库</div><div>下一步由 Agent 走 extract_requirements 抽取条款——build_outline 建纲后，这里显示章节树</div></div>';
        const panelEl19 = host.querySelector("#bid-panel");
        if (panelEl19) renderBidWizardResult(panelEl19, state.bidWizard.result);
      } else if (q19.files > 0) {
        // R4（#47）：向导完成态首屏——重开工作区场景（无进行中向导）：
        // 已导入未建纲，树区给 quick_stats 驱动的「已入库」引导，右面板
        // 完成态卡（不再是泛泛「大纲未建立」占位——数据同源 bid.state）
        treeEl.innerHTML = '<div class="view-state"><div class="view-state-title">文件已入库（' + (q19.files || 0) + " 件）</div><div>下一步由 Agent 走 extract_requirements 抽取条款——build_outline 建纲后，这里显示章节树</div></div>";
        const panelEl19 = host.querySelector("#bid-panel");
        if (panelEl19 && activePanel === "detail") renderBidWizardDone(panelEl19, b);
      } else {
        treeEl.innerHTML = '<div class="view-state"><div class="view-state-title">大纲未建立</div><div>当前项目还没有章节树——MCP 管线 build_outline 之后，这里显示章节层级、字数进度与状态标记</div></div>';
      }
      if (activePanel === "quality") renderBidQualityPanel(host);
      // #603 批 A：门台账不依赖章节树（任何阶段可看/可过合法门）
      if (activePanel === "gates") renderBidGatesPanel(host);
      // #18：出口面板不依赖章节树——早期态给 E_STATE 引导卡（先建纲）
      if (activePanel === "export") renderBidExportPanel(host);
      // #20：分包清单同样不依赖章节树（#316 识别面任何阶段可看）
      if (activePanel === "packages") renderBidPackagesPanel(host);
      return;
    }
    const byId = {};
    nodes.forEach((n) => {
      byId[n.id] = n;
    });
    const stats = (b.outline && b.outline.stats) || {};
    let html = '<div class="bid-tree-head"><span>大纲树</span><span class="bid-tree-meta">' + fmtChars(stats.sections_drafted) + "/" + fmtChars(stats.sections) + " 章成稿 · " + fmtChars(stats.actual_total_chars) + " 字</span></div>";
    html += '<div class="bid-tree-body">';
    for (const n of bidVisibleRows(nodes)) {
      const hasKids = nodes.some((m) => m.parent_id === n.id);
      const collapsed = state.bidCollapsed.has(n.id);
      const pad = 10 + (n.level - 1) * 14;
      const pct = n.target_chars > 0 ? Math.min(100, Math.round((n.actual_chars / n.target_chars) * 100)) : 0;
      // 字数进度条：未起草 = 中性灰；已起草不足配额 = 红（issue 验收「不足标红」）；达标 = 绿
      const barState = !bidDrafted(n.status) ? "pending" : pct >= 100 ? "ok" : "low";
      html +=
        '<div class="bid-node" role="treeitem" data-id="' + esc(n.id) + '" data-leaf="' + String(!hasKids) + '" aria-expanded="' + (hasKids ? String(!collapsed) : "false") + '" tabindex="0" style="padding-left:' + pad + 'px">'
        + '<span class="bid-caret"' + (hasKids ? "" : " aria-hidden=" + String.fromCharCode(34) + "true" + String.fromCharCode(34)) + ' style="transform:rotate(' + (hasKids && !collapsed ? "90deg" : "0deg") + ')">' + (hasKids ? ICON.chevron : "") + "</span>"
        + '<span class="bid-node-label" title="' + esc(n.title) + '">' + esc(n.title) + "</span>"
        + (n.dirty ? '<span class="bid-dirty" title="补遗/重开致脏——待增量重写">脏</span>' : "")
        + '<span class="bid-badge" data-status="' + esc(n.status) + '">' + esc(bidStatusZh(n.status)) + "</span>"
        + '<span class="bid-node-chars">' + fmtChars(n.actual_chars) + "/" + fmtChars(n.target_chars) + "</span>"
        + '<span class="bid-bar"><span class="bid-bar-fill" data-state="' + barState + '" style="width:' + pct + '%"></span></span>'
        + "</div>";
    }
    html += "</div>";
    treeEl.innerHTML = html;
    treeEl.querySelectorAll(".bid-node").forEach((row) => {
      row.addEventListener("click", () => {
        const node = byId[row.dataset.id];
        if (!node) return;
        if (row.dataset.leaf === "false") {
          if (state.bidCollapsed.has(node.id)) state.bidCollapsed.delete(node.id);
          else state.bidCollapsed.add(node.id);
          renderBidWorkbenchIfOpen();
          return;
        }
        // #313 批 B/C：点树节点回到章节详情面（页签联动）
        const wt = bidWorkbenchTab();
        if (wt) wt.meta.panel = "detail";
        if (typeof renderBidTabsState === "function") renderBidTabsState(host);
        if (typeof syncBidTabBar === "function") syncBidTabBar(host, "detail");
        renderBidDetail(host, node);
      });
    });
    if (activePanel === "quality") {
      renderBidQualityPanel(host);
      return;
    }
    if (activePanel === "gates") {
      renderBidGatesPanel(host);
      return;
    }
    if (activePanel === "export") {
      // #18：校验报告 + 确认导出 + 产物回显（不依赖选中节点）
      renderBidExportPanel(host);
      return;
    }
    if (activePanel === "packages") {
      renderBidPackagesPanel(host);
      return;
    }
    if (activePanel === "matrix") {
      // #21 e2e 首跑捕获的存量 bug：此处原为 renderBidMatrixPanel(host)——
      // 漏传第二参 panel，函数体首屏 panel.innerHTML 直接 TypeError，矩阵
      // 页签点击无响应。静态断言未拦住（正是 #21 立项的论据）。
      const mxPanel = host.querySelector("#bid-panel");
      if (mxPanel) renderBidMatrixPanel(host, mxPanel);
      return;
    }
    // 选中态：保持已选（刷新后仍指向同一节）；初次进入选第一片叶
    const tab = bidWorkbenchTab();
    const selId = tab && tab.meta && tab.meta.selectedId;
    if (!(selId && byId[selId])) {
      const firstLeaf = nodes.find((n) => !nodes.some((m) => m.parent_id === n.id));
      if (firstLeaf && tab) tab.meta.selectedId = firstLeaf.id;
    }
    renderBidActivePanel(host);
  }
  // #19：招标文件业务角色（契约 §2 kind 合法值——与工具面 TENDER_FILE_KINDS 同源；
  // UI 缺省「附件」，按文件名启发式预选最常见角色）
  var BID_FILE_KINDS = ["招标文件", "附件", "图纸", "补遗", "答疑", "评分办法", "格式模板"];
  function guessBidFileKind(name) {
    const n = String(name || "");
    if (/补遗|澄清|更正/.test(n)) return "补遗";
    if (/答疑|质疑|回答/.test(n)) return "答疑";
    if (/图纸/.test(n)) return "图纸";
    if (/评分|办法/.test(n)) return "评分办法";
    if (/格式|模板/.test(n)) return "格式模板";
    if (/招标|采购|比选|竞谈/.test(n)) return "招标文件";
    return "附件";
  }
  // #19：导入候选扩展名白名单（解析管线支持面：docx/xlsx 引擎 + pdf 三降级链
  // + .doc 转换通道；其余扩展名必 parse FAILED，不列进来免得用户白跑一趟）
  var BID_IMPORT_EXTS = /\.(docx|xlsx|pdf|doc|ods)$/i;

  // ============ #19：导入向导（空态引导卡——新建项目 → 导入招标文件） ============
  // 交互语言对齐 bid.coverage 的 next 引导（bid-cov-next 同款「下一步」条）；
  // E_STATE / not_found 分支复用 §109 引导卡约定：空态是主路径不是故障。

  /** 向导第一步：新建标书项目（bid.create_project——壳侧隐式幂等键 =
   *  工作区路径，重试/重复提交不会建出第二个项目） */
  function renderBidWizardCreate(treeEl) {
    const w = state.bidWizard;
    const today = new Date();
    const dl = new Date(today.getTime() + 30 * 86400e3);
    const dlStr = dl.getFullYear() + "-" + String(dl.getMonth() + 1).padStart(2, "0") + "-" + String(dl.getDate()).padStart(2, "0");
    treeEl.innerHTML =
      '<div class="bid-wizard">'
      + '<div class="bid-wiz-card">'
      + '<div class="bid-wiz-step"><span class="bid-wiz-n ok">1</span>新建标书项目<span class="bid-wiz-n">2</span>导入招标文件</div>'
      + '<div class="bid-wiz-title">' + ICON.bid + "从这个工作区开始一个标书项目</div>"
      + '<div class="bid-wiz-sub">当前目录还没有 db.json——填基本盘即可创建（项目数据落在本工作区，随时可换目录另起）</div>'
      + '<form id="bid-wiz-form" autocomplete="off">'
      + '<label class="bid-wiz-field"><span>项目名称 *</span><input name="name" type="text" placeholder="如：市政水厂 EPC 项目" required maxlength="80"></label>'
      + '<label class="bid-wiz-field"><span>招标模式 *</span><select name="mode"><option value="明标">明标</option><option value="暗标">暗标</option></select></label>'
      + '<label class="bid-wiz-field"><span>投标截止 *</span><input name="bid_deadline" type="date" value="' + dlStr + '" required></label>'
      + '<label class="bid-wiz-field"><span>招标公告编号</span><input name="tender_notice_ref" type="text" placeholder="选填——公告/项目编号" maxlength="64"></label>'
      + (w.createError ? '<div class="bid-wiz-error" data-state="error">' + esc(w.createError) + "</div>" : "")
      + '<div class="bid-wiz-actions"><button type="submit" class="btn btn-primary"' + (w.createBusy ? " disabled" : "") + ">" + (w.createBusy ? "创建中…" : "创建项目") + "</button></div>"
      + "</form></div></div>";
    const form = treeEl.querySelector("#bid-wiz-form");
    if (form) form.addEventListener("submit", (ev) => { ev.preventDefault(); ui.submitBidWizardCreate(form); });
  }

  /** 向导第二步：导入招标文件（bid.import_files——工作区文件勾选 + kind 分派） */
  function renderBidWizardImport(treeEl, host) {
    const w = state.bidWizard;
    const selCount = Object.keys(w.sel).length;
    let bodyHtml;
    if (w.treeStatus === "loading") {
      bodyHtml = '<div class="view-state"><div class="view-spinner"></div><div>正在读取工作区文件…</div></div>';
    } else if (w.treeStatus === "idle") {
      // 首进导入卡：发起拉取（loadBidWizardTree 置 loading 后重渲染，
      // 不会重复触发——renderBidWorkbenchIfOpen 是幂等重入）
      bodyHtml = '<div class="view-state"><div class="view-spinner"></div><div>正在读取工作区文件…</div></div>';
      ui.loadBidWizardTree();
    } else if (w.treeStatus === "error") {
      bodyHtml = '<div class="view-state" data-kind="error"><div class="view-state-title">读取工作区失败</div><div>' + esc(w.treeError) + '</div><button class="btn" data-bid-act="wizard-refresh-tree">重试</button></div>';
    } else if (!w.files.length) {
      bodyHtml = '<div class="view-state"><div class="view-state-title">工作区里没有可导入的文件</div><div>把招标文件（.docx / .xlsx / .pdf / .doc）放进当前工作区后点刷新——导入围栏只认本工作区内的文件</div><button class="btn" data-bid-act="wizard-refresh-tree">' + ICON.refresh + "刷新文件列表</button></div>";
    } else {
      let rows = "";
      for (const f of w.files) {
        const checked = Object.prototype.hasOwnProperty.call(w.sel, f.rel);
        // kind 默认值：勾选过的用勾选值，否则按文件名启发式预选（用户可改）
        const kindDef = checked ? w.sel[f.rel] : guessBidFileKind(f.name);
        rows +=
          '<label class="bid-wiz-file" data-on="' + String(checked) + '">'
          + '<input type="checkbox" data-rel="' + esc(f.rel) + '"' + (checked ? " checked" : "") + ">"
          + '<span class="bid-wiz-file-name" title="' + esc(f.rel) + '">' + esc(f.name) + "</span>"
          + '<span class="bid-wiz-file-meta">' + fmtBytes(f.size || 0) + "</span>"
          + '<select data-kind-for="' + esc(f.rel) + '">'
          + BID_FILE_KINDS.map((k) => '<option value="' + k + '"' + (kindDef === k ? " selected" : "") + ">" + k + "</option>").join("")
          + "</select></label>";
      }
      bodyHtml =
        '<div class="bid-wiz-files">' + rows + "</div>"
        + '<div class="bid-wiz-bar"><span class="bid-wiz-count">已选 ' + selCount + " / " + w.files.length + " 件</span>"
        + '<button class="btn btn-primary" data-bid-act="wizard-go"' + (w.importBusy || !selCount ? " disabled" : "") + ">" + (w.importBusy ? "解析入库中…" : "导入 " + selCount + " 件") + "</button>"
        + '<button class="btn" data-bid-act="wizard-refresh-tree" title="重读工作区文件">' + ICON.refresh + "</button></div>";
    }
    treeEl.innerHTML =
      '<div class="bid-wizard">'
      + '<div class="bid-wiz-card">'
      + '<div class="bid-wiz-step"><span class="bid-wiz-n ok">✓</span>新建标书项目<span class="bid-wiz-n ok">2</span>导入招标文件</div>'
      + '<div class="bid-wiz-title">' + ICON.folderOpen + "导入招标文件</div>"
      + '<div class="bid-wiz-sub">解析 → 结构化切块 → 证据注册（失败件全程禁引，成功件即时入库）</div>'
      + bodyHtml
      + (w.importError ? '<div class="bid-wiz-error" data-state="error">' + esc(w.importError) + "</div>" : "")
      + "</div></div>";
    bindBidViewActions(treeEl);
    const goBtn = treeEl.querySelector('[data-bid-act="wizard-go"]');
    if (goBtn) goBtn.addEventListener("click", () => ui.submitBidWizardImport());
    treeEl.querySelectorAll(".bid-wiz-file input[type=checkbox]").forEach((cb) => {
      cb.addEventListener("change", () => {
        const rel = cb.dataset.rel;
        if (cb.checked) {
          const sel = treeEl.querySelector('[data-kind-for="' + CSS.escape(rel) + '"]');
          state.bidWizard.sel[rel] = sel ? sel.value : guessBidFileKind(rel);
        } else delete state.bidWizard.sel[rel];
        renderBidWorkbenchIfOpen();
      });
    });
    treeEl.querySelectorAll(".bid-wiz-file select").forEach((s) => {
      s.addEventListener("change", () => {
        const rel = s.dataset.kindFor;
        if (Object.prototype.hasOwnProperty.call(state.bidWizard.sel, rel)) state.bidWizard.sel[rel] = s.value;
      });
    });
    // 导入结果面（右面板）——成功/部分成功同屏分账
    const panelEl = host && host.querySelector("#bid-panel");
    if (panelEl) {
      if (w.result) renderBidWizardResult(panelEl, w.result);
      else panelEl.innerHTML = '<div class="view-state"><div class="view-state-title">选择左侧文件开始导入</div><div>勾选招标正本、附件、图纸、补遗——每件分派业务角色（kind），导入后逐件显示解析统计</div></div>';
    }
  }

  /** 导入结果（右面板，R3 #47 分账明细）：摘要计数条 + per_file 逐件表 +
   * 失败清单（全程禁引口径）+ totals + 告警 + 补遗就绪/输入完整性。
   * partial 判据三源合取（壳侧 partial 标记 / per_file FAILED 行 /
   * totals.parse_failed）——演示桥与真实壳任一形态都能点亮部分成功面。 */
  function renderBidWizardResult(panelEl, r) {
    const perFile = r.per_file || [];
    const totals = r.totals || {};
    let rows = "";
    for (const f of perFile) {
      const failed = String(f.parse_status || "").toLowerCase() === "failed";
      rows +=
        '<tr class="' + (failed ? "is-failed" : "") + '">'
        + "<td>" + esc(f.filename || "—") + "</td><td>" + esc(f.kind || "—") + "</td>"
        + "<td>" + (f.pages || 0) + "</td><td>" + (f.tables || 0) + "</td><td>" + (f.chunks || 0) + "</td>"
        + '<td><span class="bid-badge" data-status="' + (failed ? "FAILED" : "OK") + '">' + (failed ? "失败" : "成功") + "</span></td>"
        + "<td>" + (f.deduplicated ? "已存在" : "新入库") + "</td></tr>";
    }
    const warns = r.warnings || [];
    const integrity = (r.input_integrity && r.input_integrity.unready) || [];
    // R3（#47）：分账计数 + partial 三源合取（壳侧标记 / FAILED 行 / totals）
    const failedRows = perFile.filter((f) => String(f.parse_status || "").toLowerCase() === "failed");
    const okCount = perFile.length - failedRows.length;
    const dedupedCount = perFile.filter((f) => f.deduplicated).length;
    const itemErrors = (r.item_errors || []).map(String);
    const partial = !!r.partial || failedRows.length > 0 || (totals.parse_failed || 0) > 0;
    // R3（#47）：摘要计数条——成功/失败/已存在 + 部分成功口径一频位
    const summary =
      '<div class="bid-wiz-summary" data-state="' + (partial ? "warn" : "ok") + '">'
      + "<span>成功 " + okCount + " 件</span><span>失败 " + failedRows.length + " 件</span><span>已存在 " + dedupedCount + " 件</span>"
      + (partial
        ? '<span class="bid-wiz-summary-note">部分成功不是故障——成功件照常入库不回滚，失败件全程禁引</span>'
        : '<span class="bid-wiz-summary-note">全部入库</span>')
      + "</div>";
    // R3（#47）：失败清单结构化（取代 R1 的单行拼接）——每条独立行 +
    // 修复引导（失败件不阻断后续步骤，修好重新导入即可）
    const fails = itemErrors.length
      ? '<details class="bid-wiz-fails" open><summary>' + itemErrors.length + " 件失败（全程禁引——补遗/条款抽取/评分都不会引用；修复文件后重新导入即可，成功件不回滚）</summary>"
        + (r.partial_what ? '<div class="bid-wiz-fail-what">' + esc(r.partial_what) + "</div>" : "")
        + itemErrors.map((e) => '<div class="bid-wiz-fail-row">' + esc(e) + "</div>").join("")
        + "</details>"
      : "";
    panelEl.innerHTML =
      '<div class="bid-panel-card">'
      + '<div class="bid-panel-title">导入结果' + (partial ? '（部分成功）' : "") + "</div>"
      + summary
      + '<table class="bid-table"><thead><tr><th>文件</th><th>角色</th><th>页</th><th>表</th><th>块</th><th>解析</th><th>幂等</th></tr></thead><tbody>' + rows + "</tbody></table>"
      + '<div class="bid-wiz-total">共 ' + (totals.files || perFile.length) + " 件 · " + (totals.chunks || 0) + " 块 · 解析失败 " + (totals.parse_failed || 0) + " 件</div>"
      + fails
      + (integrity.length ? '<div class="bid-cov-next" data-state="warn"><span>输入完整性</span>' + integrity.map((f) => esc(f.name + "：" + (f.reason || ""))).join("；") + "</div>" : "")
      + (warns.length ? '<details class="bid-wiz-warns"><summary>' + warns.length + " 条告警</summary>" + warns.map((x) => "<div>" + esc(x) + "</div>").join("") + "</details>" : "")
      + '<div class="bid-cov-next" data-state="ok"><span>下一步</span>文件已入库——由 Agent 走 extract_requirements 抽取条款（MCP 管线），随后 build_outline 建纲进入起草</div>'
      + "</div>";
  }

  /** R4（#47）：向导完成态卡（右面板）——重开工作区场景：quick_stats
   * 驱动的项目就绪面（文件/条款/证据/页数估计），下一步引导对齐
   * bid.coverage next 语言。刚导入的现场（result 在场）仍走
   * renderBidWizardResult（逐件表更详细）；本卡是无现场时的同源降级。 */
  function renderBidWizardDone(panelEl, b) {
    const p = (b.data && b.data.project) || {};
    const q = (b.data && b.data.quick_stats) || {};
    panelEl.innerHTML =
      '<div class="bid-panel-card">'
      + '<div class="bid-panel-title">导入完成 · 项目就绪</div>'
      + '<div class="bid-wiz-summary" data-state="ok">'
      + "<span>文件 " + (q.files || 0) + " 件</span>"
      + "<span>需求条款 " + fmtChars(q.requirements || 0) + " 条</span>"
      + "<span>证据 " + fmtChars(q.evidence || 0) + "</span>"
      + "<span>约 " + fmtChars(q.pages_estimate || 0) + " 页</span>"
      + "</div>"
      + '<table class="bid-table"><tbody>'
      + "<tr><td>项目</td><td>" + esc(p.name || "未命名项目") + "</td></tr>"
      + "<tr><td>模式</td><td>" + esc(p.mode || "—") + "</td></tr>"
      + "<tr><td>状态</td><td>" + esc(bidProjectStatusZh(p.status || "")) + "</td></tr>"
      + "</tbody></table>"
      + '<div class="bid-cov-next" data-state="ok"><span>下一步</span>由 Agent 走 extract_requirements 抽取条款（MCP 管线），随后 build_outline 建纲进入起草——建纲后左侧显示章节树与本面板详情</div>'
      + "</div>";
  }

  /** 章节详情（右面板）：元信息 + 章节正文预览（chapters/{id}.json 的 content） */
  function renderBidDetail(host, node) {
    const tab = bidWorkbenchTab();
    if (tab) tab.meta.selectedId = node.id;
    const panel = host.querySelector("#bid-panel");
    if (!panel) return;
    host.querySelectorAll("#bid-tree .bid-node").forEach((row) => {
      row.dataset.selected = String(row.dataset.id === node.id);
    });
    const pct = node.target_chars > 0 ? Math.round((node.actual_chars / node.target_chars) * 100) : 0;
    let html =
      '<div class="bid-detail">'
      + '<div class="bid-detail-head">'
      + '<h3 class="bid-detail-title">' + esc(node.title) + ' <span class="bid-badge" data-status="' + esc(node.status) + '">' + esc(bidStatusZh(node.status)) + "</span>" + (node.dirty ? ' <span class="bid-dirty" title="补遗/重开致脏——待增量重写">脏</span>' : "") + "</h3>"
      + '<div class="bid-detail-meta">'
      + "<span>" + esc(node.id) + "</span>"
      + "<span>层级 L" + esc(node.level) + "</span>"
      + "<span>配额 " + fmtChars(node.target_chars) + " 字</span>"
      + "<span>实际 " + fmtChars(node.actual_chars) + " 字（" + pct + "%）</span>"
      + (node.is_leaf ? "<span>响应条款 " + fmtChars(node.req_count) + " 条</span>" : "<span>结构节点</span>")
      + (node.content_attempt ? "<span>提交 v" + esc(node.content_attempt) + "</span>" : "")
      + "</div>"
      + '<div class="bid-detail-actions">'
      + (node.chapter_file ? '<button class="btn btn-sm" data-bid-act="open-chapter" data-path="' + esc(node.chapter_file) + '">' + ICON.text + "打开章节文件</button>" : "")
      + "</div></div>";
    if (!node.is_leaf) {
      html += '<div class="bid-detail-body"><div class="view-state"><div class="view-state-title">结构节点</div><div>本节点是大纲的调度单元，正文在子章节——点左侧树的子节点查看详情</div></div></div>';
    } else if (!node.has_content) {
      html += '<div class="bid-detail-body"><div class="view-state"><div class="view-state-title">未起草</div><div>本章节还没有正文——MCP 管线 draft_response_section 之后，这里展示章节内容预览</div></div></div>';
    } else if (!node.chapter_file) {
      html += '<div class="bid-detail-body"><div class="view-state"><div class="view-state-title">正文未落盘</div><div>章节内容在项目内存态（chapters/' + esc(node.id) + '.json 不存在）</div></div></div>';
    } else {
      html += '<div class="bid-detail-body" data-bid-content="' + esc(node.chapter_file) + '"><div class="view-state"><div class="view-spinner"></div><div>正在读取章节正文…</div></div></div>';
    }
    html += "</div>";
    panel.innerHTML = html;
    const openBtn = panel.querySelector('[data-bid-act="open-chapter"]');
    if (openBtn) openBtn.addEventListener("click", () => ui.openPath(absPathOf(openBtn.dataset.path)));
    const bodyEl = panel.querySelector("[data-bid-content]");
    if (bodyEl && bodyEl.dataset.bidContent) {
      const file = bodyEl.dataset.bidContent;
      ipc("fs.read", { path: file }, 3e4)
        .then((r) => {
          if (!bodyEl.isConnected) return;
          let content = "";
          try {
            const rec = JSON.parse(typeof r.text === "string" ? r.text : "");
            content = rec && typeof rec.content === "string" ? rec.content : "";
          } catch (err) {
            content = "";
          }
          if (content) {
            bodyEl.innerHTML = '<div class="md-view bid-detail-md">' + mdToHtml(content) + "</div>";
          } else {
            bodyEl.innerHTML = '<div class="view-state" data-kind="error"><div class="view-state-title">章节文件不可读</div><div>' + esc(file) + "</div></div>";
          }
        })
        .catch((err) => {
          if (!bodyEl.isConnected) return;
          bodyEl.innerHTML = '<div class="view-state" data-kind="error"><div class="view-state-title">读取章节失败</div><div>' + esc(err.message || String(err)) + "</div></div>";
        });
    }
  }
  // ============ #313 批 B：矩阵面板（bid.matrix） ============
  // 数据来源：壳侧 bid.quality（check_bid_quality 真实工具面——summary /
  // submission_readiness / global_conflicts / negative_deviations / artifact）与
  // bid.score（score_document——diagnostic_only / technical / commercial / price /
  // total / by_item）。契约：docs/mang/IPC-CONTRACT.md §6。
  // 合规矩阵 = 批 B / 覆盖报告 = 批 D（占位禁用态）。
  /** 全局冲突 kind 中文面（#423 金额/工期/术语/承诺——四类恒 blocker） */
  function bidConflictZh(kind) {
    return (
      {
        amount_conflict: "金额冲突",
        schedule_conflict: "工期冲突",
        term_conflict: "术语冲突",
        commitment_conflict: "承诺冲突"
      }[kind] || kind
    );
  }
  function fmtScore(v) {
    return typeof v === "number" && isFinite(v) ? String(Math.round(v * 10) / 10) : "—";
  }
  /** 评分卡单元：无报价/无数据 → 「未报价」诚实显示（不伪缺 0） */
  function bidQualScoreCell(label, v, max, hint) {
    const has = typeof v === "number" && isFinite(v);
    const pct = has && max > 0 ? Math.min(100, Math.round((v / max) * 100)) : 0;
    return (
      '<div class="bid-qual-score" data-has="' + String(has) + '">'
      + '<span class="bid-qual-score-v">' + (has ? fmtScore(v) : "未报价") + "</span>"
      + '<span class="bid-qual-score-k">' + esc(label) + (hint ? " · " + esc(hint) : "") + "</span>"
      + '<span class="bid-bar"><span class="bid-bar-fill" data-state="' + (has ? (pct >= 80 ? "ok" : pct >= 50 ? "mid" : "low") : "pending") + '" style="width:' + pct + '%"></span></span>'
      + "</div>"
    );
  }
  /** BLOCKER 清单（<details> 原生展开——无 JS 状态） */
  function bidQualList(title, rows) {
    return (
      '<details class="bid-qual-list"><summary>' + esc(title) + "</summary>"
      + rows.map((r) => '<div class="bid-qual-row">' + esc(r) + "</div>").join("")
      + "</details>"
    );
  }
  /** R6（#47 / #19 任务 3）：E_NOTFOUND / E_STATE 引导卡统一工厂（契约
   * §3.4 引导卡约定）——全部 bid.* 读面板共用一套呈现，不再各面板手写
   * （R5 coverage 首创，R6 收编 matrix / quality / gates）。
   * 结构：标题 + 说明 + 主行动 CTA（data-bid-guide-cta，切回 detail
   * 页签——向导所在页）+ 次行动「重新检查」（data-bid-guide-retry，
   * 重发原命令）+ bid-cov-next「下一步」条（说明后继管线）。
   * 纪律：空态是主路径不是故障——卡片不带 data-kind="error"（错误
   * 横幅只留给真故障，如 io）；单一真源在 code 不在文案（not_found →
   * 去新建标书项目（向导第一步）；state → 去导入招标文件（向导第
   * 二步）），E_STATE 原文（含状态与前置说明）原样进卡不吞。
   * wrapClass：各面板容器类（bid-cov / bid-mx / bid-qual / bid-gt），
   * 保持各页签既有样式上下文。 */
  function renderBidEarlyGuide(host, panel, opts) {
    const o = opts || {};
    const isNotFound = o.code === "not_found";
    const cta = isNotFound ? "去新建标书项目" : "去导入招标文件";
    panel.innerHTML =
      '<div class="' + (o.wrapClass || "bid-cov") + '">'
      + '<div class="view-state"><div class="view-state-title">' + (o.title || (isNotFound ? "还没有标书项目" : "此面板尚未开放")) + "</div>"
      + "<div>" + (o.text || "") + "</div>"
      + (o.hint ? '<div class="bid-qual-hint">' + o.hint + "</div>" : "")
      + '<div><button class="btn btn-primary" data-bid-guide-cta>' + cta + '</button> <button class="btn" data-bid-guide-retry>重新检查</button></div></div>'
      + (o.next ? '<div class="bid-cov-next" data-state="ok"><span>下一步</span>' + o.next + "</div>" : "")
      + "</div>";
    const go = panel.querySelector("[data-bid-guide-cta]");
    if (go) go.addEventListener("click", () => {
      // 主行动 → 向导所在页（detail 页签：第一步建项 / 第二步导入）
      const t = bidWorkbenchTab();
      if (!t || !t.meta) return;
      t.meta.panel = "detail";
      syncBidTabBar(host, "detail");
      renderBidWorkbenchPanes(host);
    });
    const retry = panel.querySelector("[data-bid-guide-retry]");
    if (retry && o.retry) retry.addEventListener("click", () => o.retry());
  }
  /** #18 出口闭环面板：校验报告（bid.validate）→ 确认导出（bid.export）
   * → 产物回显 + explorer.reveal 定位。E_STATE/not_found 走引导卡
   * （IPC-CONTRACT §109 约定），不弹错误横幅。 */
  function renderBidExportPanel(host) {
    const panel = host.querySelector("#bid-panel");
    if (!panel) return;
    const x = state.bidExport;
    if (x.status === "idle") {
      panel.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>正在读取校验报告…</div></div>';
      ui.loadBidValidate();
      return;
    }
    if (x.status === "loading") {
      panel.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>正在校验全文档（规则 + 模型复核）…</div></div>';
      return;
    }
    if (x.code === "not_found") {
      // R6（#47 / #19 任务 3）merge main 收编：export 面（#18）原错误横幅
      // → 共享工厂引导卡（契约 §3.4——全部 bid.* 读面板同一约定）
      renderBidEarlyGuide(host, panel, {
        code: "not_found",
        wrapClass: "bid-export",
        title: "还没有标书项目",
        text: "当前工作区没有 db.json——新建标书项目并导入招标文件后，在这里校验全文档并导出成品标书",
        next: "新建标书项目（向导第一步）——建项导入、抽取条款建纲起草之后，到这里「校验并导出」",
        retry: () => ui.loadBidValidate(true)
      });
      return;
    }
    if (x.code === "state") {
      // 工具面 E_STATE 原文已含状态与前置说明（如「DRAFTING 态无章节树——先建纲再校验」）
      // R6（#47 / #19 任务 3）merge main 收编：手写引导卡 → 共享工厂（§3.4）
      renderBidEarlyGuide(host, panel, {
        code: "state",
        wrapClass: "bid-export",
        title: "校验尚未开放",
        text: esc(x.error || ""),
        hint: "校验需要章节树已建立；导出还需过双前置门（校验通过 + pre_export_confirm 过门确认——审核门页签可人工过门）。",
        next: "导入招标文件（向导第二步）——extract_requirements 抽取条款、build_outline 建纲、起草应答之后，到这里校验并导出成品",
        retry: () => ui.loadBidValidate(true)
      });
      return;
    }
    if (!x.report) {
      panel.innerHTML = '<div class="view-state" data-kind="error"><div class="view-state-title">校验报告读取失败</div><div>' + esc(x.error || "未知错误") + '</div><button class="btn" data-bid-act="refresh-validate">重试</button></div>';
      bindBidViewActions(panel);
      return;
    }
    // ---- 校验报告（validate_bid_document 工具输出：ok/errors/warnings/findings/counts）----
    const r = x.report;
    const counts = r.counts || {};
    const errors = Array.isArray(r.errors) ? r.errors : [];
    const warnings = Array.isArray(r.warnings) ? r.warnings : [];
    let html = '<div class="bid-export">';
    html +=
      '<div class="bid-qual-head">'
      + '<span class="bid-qual-tag ' + (r.ok ? "ok" : "warn") + '">' + (r.ok ? ICON.check + " 校验通过" : ICON.warning + " 存在缺陷") + "</span>"
      + '<span class="bid-qual-sub">' + (x.ts ? timeAgo(x.ts) : "—") + "</span>"
      + '<span class="bid-wb-spacer"></span>'
      + '<button class="btn btn-sm" data-bid-act="refresh-validate" title="重新跑 bid.validate（会推进项目至 VALIDATING）">' + ICON.refresh + "重新校验</button>"
      + "</div>";
    html +=
      '<div class="bid-card"><div class="bid-card-title">校验计数</div><div class="bid-stats">'
      + bidStatCell(fmtChars(counts.blocker), "BLOCKER")
      + bidStatCell(fmtChars(counts.major), "MAJOR")
      + bidStatCell(fmtChars(counts.minor), "MINOR")
      + bidStatCell(fmtChars(counts.deterministic), "规则命中")
      + bidStatCell(fmtChars(counts.model), "模型复核")
      + "</div></div>";
    if (errors.length) {
      html += bidQualList("缺陷清单（BLOCKER/MAJOR · " + errors.length + "）", errors.map((e2) => (e2.rule_code || "?") + " · " + (e2.severity || "?") + (e2.section_id ? " · " + e2.section_id : "") + "：" + (e2.message || "")));
    } else {
      html += '<div class="bid-card"><div class="bid-card-sub">' + ICON.check + " 无 BLOCKER/MAJOR 缺陷</div></div>";
    }
    if (warnings.length) {
      html += bidQualList("警告（MINOR · " + warnings.length + "）", warnings.map(String));
    }
    // ---- 导出表单（看完报告确认后落盘）----
    const proj = (state.bid.data && state.bid.data.project) || {};
    const defName = (proj.name || "标书").replace(/[\\/:*?"<>|]/g, "_");
    if (!x.path) x.path = "export/" + defName + "." + x.format;
    html +=
      '<div class="bid-card" data-kind="export-form"><div class="bid-card-title">' + ICON.export + " 确认导出</div>"
      + '<div class="bid-export-form">'
      + '<label class="bid-export-field"><span>格式</span>'
      + '<select id="bid-export-format"><option value="docx"' + (x.format === "docx" ? " selected" : "") + '>DOCX（Word）</option><option value="pdf"' + (x.format === "pdf" ? " selected" : "") + '>PDF（需 Word/LibreOffice）</option></select></label>'
      + '<label class="bid-export-field"><span>输出路径（工作区相对）</span>'
      + '<input type="text" id="bid-export-path" value="' + esc(x.path) + '" placeholder="export/' + esc(defName) + '.docx" /></label>'
      + '<label class="bid-export-check"><input type="checkbox" id="bid-export-dark"' + (x.darkBid ? " checked" : "") + ' /> 暗标模式（脱敏投标人名）</label>'
      + '<label class="bid-export-field"' + (x.darkBid ? "" : ' style="display:none"') + ' id="bid-export-bidder-row"><span>投标人名称（暗标脱敏用）</span>'
      + '<input type="text" id="bid-export-bidder" value="' + esc(x.bidderName) + '" placeholder="公司全称" /></label>'
      + '<div class="bid-export-actions">'
      + '<button class="btn btn-primary" data-bid-act="confirm-export"' + (x.exporting ? " disabled" : "") + ">" + (x.exporting ? "正在导出…" : ICON.export + " 导出成品文档") + "</button>"
      + (r.ok ? "" : '<span class="bid-qual-warn">' + ICON.warning + " 校验未通过——导出前置门可能拦截，建议先按缺陷清单修复</span>")
      + "</div></div></div>";
    // ---- 产物回显 / 导出失败引导 ----
    if (x.done) {
      const art = x.done.artifact || {};
      html +=
        '<div class="bid-card" data-kind="export-done"><div class="bid-card-title">' + ICON.check + " 导出完成</div>"
        + '<div class="bid-stats">'
        + bidStatCell(fmtBytes(art.size), "产物大小")
        + bidStatCell(fmtChars(x.done.chapters_written), "章节写入")
        + bidStatCell(fmtChars(x.done.total_chars), "总字数")
        + bidStatCell(String(art.sha256 || "").slice(0, 12) || "—", "SHA-256 前 12 位")
        + "</div>"
        + '<div class="bid-card-sub bid-export-path" title="' + esc(art.url || "") + '">产物：' + esc(art.url || "") + "</div>"
        + '<div class="bid-card-actions"><button class="btn" data-bid-act="reveal-artifact">' + ICON.folderOpen + " 在工作区中显示</button></div>"
        + (Array.isArray(x.done.warnings) && x.done.warnings.length ? '<div class="bid-card-sub bid-qual-warn">' + ICON.warning + " " + x.done.warnings.length + " 条导出警告（如暗标未提供投标人名未脱敏）——见上方报告</div>" : "")
        + "</div>";
    } else if (x.doneError) {
      html +=
        '<div class="bid-card" data-kind="export-error"><div class="bid-card-title">' + ICON.warning + (x.doneCode === "state" ? " 导出被前置门拦截" : " 导出失败") + "</div>"
        + "<div>" + esc(x.doneError) + "</div>"
        + '<div class="bid-qual-hint">双前置门：校验通过 + pre_export_confirm 过门确认（审核门页签可人工过门）。E_STATE 原文见上——补前置后重试。</div>'
        + "</div>";
    }
    html += "</div>";
    panel.innerHTML = html;
    bindBidViewActions(panel);
    // 表单 → 状态（重渲染不丢输入；change 后按需联动暗标行）
    const fmtSel = panel.querySelector("#bid-export-format");
    const pathInput = panel.querySelector("#bid-export-path");
    const darkChk = panel.querySelector("#bid-export-dark");
    const bidderInput = panel.querySelector("#bid-export-bidder");
    if (fmtSel) fmtSel.addEventListener("change", () => {
      x.format = fmtSel.value;
      if (pathInput && /export\/.+\.(docx|pdf)$/i.test(x.path)) x.path = x.path.replace(/\.(docx|pdf)$/i, "." + x.format);
      renderBidWorkbenchIfOpen();
    });
    if (pathInput) pathInput.addEventListener("change", () => { x.path = pathInput.value.trim(); });
    if (darkChk) darkChk.addEventListener("change", () => {
      x.darkBid = darkChk.checked;
      const row = panel.querySelector("#bid-export-bidder-row");
      if (row) row.style.display = x.darkBid ? "" : "none";
    });
    if (bidderInput) bidderInput.addEventListener("change", () => { x.bidderName = bidderInput.value.trim(); });
  }
  /** 自评面板主体（工作台右面板） */
  function renderBidQualityPanel(host) {
    const panel = host.querySelector("#bid-panel");
    if (!panel) return;
    const q = state.bidQuality;
    if (q.status === "idle") {
      panel.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>正在读取自评数据…</div></div>';
      ui.loadBidQuality();
      return;
    }
    if (q.status === "loading") {
      panel.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>正在评估质量与评分…</div></div>';
      return;
    }
    if (q.code === "not_found") {
      // R6（#47 / #19 任务 3）：空工作区（无 db.json）不是错误——E_NOTFOUND
      // 引导卡（契约 §3.4）：主行动「去新建标书项目」直通向导第一步，
      // 不再走错误横幅（正常空态渲染成故障违反引导卡约定）
      renderBidEarlyGuide(host, panel, {
        code: "not_found",
        wrapClass: "bid-qual",
        title: "还没有标书项目",
        text: "当前工作区没有 db.json——新建标书项目并导入招标文件后，自评面板在这里给出评分、质量摘要与提交就绪清单",
        next: "新建标书项目（向导第一步）——建项后导入招标文件、抽取条款建纲建矩阵，自评面板自动可用",
        retry: () => ui.loadBidQuality(true)
      });
      return;
    }
    if (q.code === "state") {
      // 壳侧 state 码 = 项目未到 MatrixReady+（如刚抽取条款还没建矩阵）——
      // 引导卡而非故障横幅（E_STATE 原文已含状态与前置说明）。
      // R6（#47 / #19 任务 3）：收编共享工厂——主行动「去导入招标文件」
      // 直通向导第二步（detail 页签），与 coverage 早态卡同一交互语言。
      renderBidEarlyGuide(host, panel, {
        code: "state",
        wrapClass: "bid-qual",
        title: "自评尚未开放",
        text: esc(q.error || ""),
        hint: "矩阵就绪（MATRIX_READY）后此面板显示：评分（技术 / 商务 / 总分 + 逐评分项估分档位）、质量摘要（未覆盖条款 / 字数偏离 / 查重）与提交就绪 BLOCKER 清单。",
        next: "导入招标文件（向导第二步）——extract_requirements 抽取条款、build_outline 建纲、prepare_outline_and_matrix 建矩阵之后，自评面板在这里给出评分与就绪清单",
        retry: () => ui.loadBidQuality(true)
      });
      return;
    }
    if (!q.quality) {
      panel.innerHTML = '<div class="view-state" data-kind="error"><div class="view-state-title">自评数据读取失败</div><div>' + esc(q.error || "未知错误") + '</div><button class="btn" data-bid-act="refresh-quality">重试</button></div>';
      bindBidViewActions(panel);
      return;
    }
    const ql = q.quality;
    const sm = ql.summary || {};
    const rd = ql.submission_readiness || {};
    const unresp = Array.isArray(rd.unresponded) ? rd.unresponded : [];
    const evMissing = Array.isArray(rd.evidence_missing) ? rd.evidence_missing : [];
    const conflicts = Array.isArray(ql.global_conflicts) ? ql.global_conflicts : [];
    const negs = Array.isArray(ql.negative_deviations) ? ql.negative_deviations : [];
    const needsHuman = Array.isArray(ql.needs_human) ? ql.needs_human : [];
    const blockerCount = unresp.length + evMissing.length + conflicts.length + negs.length;
    const sc = q.score;
    let html = '<div class="bid-qual">';
    // 头部：语义徽章 + 刷新
    html +=
      '<div class="bid-qual-head">'
      + '<span class="bid-qual-tag" title="#186 语义降级：估分与档位是关键词覆盖 / 长度 / 证据词存在性的启发式诊断（rule_heuristic），不代表评委会会给的分与档">规则诊断 · 非评标模拟</span>'
      + '<span class="bid-qual-sub">' + (q.ts ? timeAgo(q.ts) : "—") + "</span>"
      + '<span class="bid-wb-spacer"></span>'
      + '<button class="btn btn-sm" data-bid-act="refresh-quality" title="重新读取 bid.quality / bid.score">' + ICON.refresh + "刷新自评</button>"
      + "</div>";
    // ① 评分卡（bid.score）
    if (sc) {
      const unmapped = Array.isArray(sc.unmapped_scoring_items) ? sc.unmapped_scoring_items : [];
      html +=
        '<div class="bid-card"><div class="bid-card-title">评分（自评估分）</div>'
        + '<div class="bid-qual-scores">'
        + bidQualScoreCell("技术", sc.technical, sc.target)
        + bidQualScoreCell("商务", sc.commercial, sc.target)
        + bidQualScoreCell("价格", sc.price, sc.target, "未报价不计")
        + bidQualScoreCell("总分", sc.total, sc.target, "目标 " + fmtScore(sc.target))
        + "</div>"
        + '<div class="bid-card-sub">距目标差 ' + fmtScore(sc.gap) + " 分 · 已评章节 " + fmtChars(sc.sections_scored)
        + (unmapped.length ? ' · <span class="bid-qual-warn">' + ICON.warning + " 未映射评分项 " + unmapped.length + " 个（总分可能偏低）</span>" : "")
        + "</div></div>";
    } else {
      html += '<div class="bid-card"><div class="bid-card-title">评分（自评估分）</div><div class="bid-card-sub">' + (q.scoreError ? "bid.score 读取失败：" + esc(q.scoreError) : "无评分数据") + "</div></div>";
    }
    // ② 质量摘要（check_bid_quality 的 summary 面）
    const dev = typeof sm.char_deviation_pct === "number" ? (sm.char_deviation_pct > 0 ? "+" : "") + sm.char_deviation_pct + "%" : "—";
    html +=
      '<div class="bid-card"><div class="bid-card-title">质量摘要</div><div class="bid-stats">'
      + bidStatCell(fmtChars(sm.total), "章节总数")
      + bidStatCell(fmtChars(sm.drafted), "已起草")
      + bidStatCell(fmtChars(sm.failed), "失败")
      + bidStatCell(fmtChars(sm.pending), "待起草")
      + bidStatCell(fmtChars(sm.uncovered_req_total), "未覆盖条款")
      + bidStatCell(fmtChars(sm.out_of_band), "字数带外")
      + bidStatCell(fmtChars(sm.unanchored_total), "无锚断言")
      + bidStatCell(fmtChars(sm.dup_pairs), "严重重复对")
      + bidStatCell(fmtChars(sm.char_total) + "/" + fmtChars(sm.char_target), "实际/配额字数")
      + bidStatCell(dev, "字数偏离")
      + "</div>"
      + (needsHuman.length ? '<div class="bid-card-sub bid-qual-warn">' + ICON.warning + " 需人工处理 " + needsHuman.length + " 章：" + esc(needsHuman.join("、")) + "</div>" : "")
      + "</div>";
    // ③ 提交就绪与废标风险（BLOCKER 面——点击展开）
    html += '<div class="bid-card" data-kind="blockers"><div class="bid-card-title">' + (blockerCount ? ICON.warning + " " : ICON.check + " ") + "提交就绪与废标风险（" + blockerCount + "）</div>";
    if (!blockerCount) {
      html += '<div class="bid-card-sub">' + ICON.check + " 无 BLOCKER：未响应 0 · 证据缺口 0 · 跨章冲突 0 · 负偏离 0" + (rd.ready ? " · 已就绪" : "") + "</div>";
    } else {
      if (unresp.length) html += bidQualList("未响应条款（" + unresp.length + "）", unresp.map((r) => r.requirement_id + " · " + r.category + "：" + r.message));
      if (evMissing.length) html += bidQualList("证据缺口（" + evMissing.length + "）", evMissing.map((r) => r.requirement_id + " · " + r.category + "：" + r.message));
      if (conflicts.length) html += bidQualList("跨章冲突（" + conflicts.length + "）", conflicts.map((c) => bidConflictZh(c.kind) + " · " + c.section_id + "：" + c.message));
      if (negs.length) html += bidQualList("技术参数负偏离（" + negs.length + "）", negs.map((p) => p.param_name + "：" + p.required_value + " → 我方 " + p.response_value + "（" + p.param_id + "）"));
      html += '<div class="bid-card-sub">导出可过而提交未就绪是合法状态（#241 两分账）——按清单逐项补件后复核</div>';
    }
    html += "</div>";
    // ④ 评分项明细（by_item——<details> 行原生展开：逐章贡献 + 细则检查点）
    if (sc && Array.isArray(sc.by_item)) {
      html += '<div class="bid-card"><div class="bid-card-title">评分项明细（' + sc.by_item.length + "）</div>";
      if (!sc.by_item.length) {
        html += '<div class="bid-card-sub">无评分项条款（category=评分项 且带分值）——评分面为空是诚实态，不伪装</div>';
      } else {
        html += '<div class="bid-qual-items"><div class="bid-qual-item bid-qual-item-head"><span>评分项</span><span>满分</span><span>估分</span><span>档位</span><span>覆盖</span></div>';
        sc.by_item.forEach((it) => {
          const cov = typeof it.coverage === "number" ? Math.round(it.coverage * 100) + "%" : "—";
          const contribs = Array.isArray(it.contributions) ? it.contributions : [];
          const cps = Array.isArray(it.rule_checkpoints) ? it.rule_checkpoints : [];
          const crit = it.criteria ? String(it.criteria).slice(0, 60) : "";
          html +=
            '<details class="bid-qual-item"><summary>'
            + "<span class=\"bid-qual-item-name\" title=\"" + esc(it.item_id + (it.criteria ? "：" + it.criteria : "")) + "\">" + esc(it.item_id) + (crit ? '<span class="bid-qual-item-crit">' + esc(crit) + "</span>" : "") + "</span>"
            + "<span>" + fmtScore(it.max) + "</span>"
            + "<span>" + fmtScore(it.estimated) + "</span>"
            + "<span><span class=\"bid-qual-tier\">" + esc(it.tier) + "</span></span>"
            + "<span>" + cov + "</span>"
            + "</summary><div class=\"bid-qual-item-body\">";
          if (contribs.length) {
            html += '<div class="bid-qual-sec">逐章贡献</div>';
            contribs.forEach((c) => {
              html += '<div class="bid-qual-row"><span class="bid-qual-sec-id">' + esc(c.section_id) + "</span><span>估分 " + fmtScore(c.estimated) + " · " + esc(c.tier) + " · 份额 " + Math.round((c.weight_share || 0) * 100) + "%</span></div>";
            });
          }
          if (cps.length) {
            const hit = cps.filter((c) => c.mentioned).length;
            html += '<div class="bid-qual-sec">细则检查点（提及 ' + hit + "/" + cps.length + "）</div>";
            cps.forEach((c) => {
              html += '<div class="bid-qual-row" data-hit="' + String(!!c.mentioned) + '"><span class="bid-qual-cp">' + (c.mentioned ? ICON.check : ICON.warning) + "</span><span>" + esc(c.text) + "</span></div>";
            });
          }
          if (!contribs.length && !cps.length) html += '<div class="bid-card-sub">无逐章明细（未起草 / 未映射）</div>';
          html += "</div></details>";
        });
        html += "</div>";
      }
      html += "</div>";
    }
    // 落盘与告警面
    if (ql.artifact && ql.artifact.path) {
      html += '<div class="bid-card-sub">质量报告已落盘：' + esc(ql.artifact.path) + "（" + fmtChars(ql.artifact.size) + " B）</div>";
    }
    if (Array.isArray(ql.warnings) && ql.warnings.length) {
      html += '<div class="bid-card-sub bid-qual-warn">' + ql.warnings.map(esc).join("；") + "</div>";
    }
    html += "</div>";
    panel.innerHTML = html;
    bindBidViewActions(panel);
  }

  // ============ #603 批 A：审核门面板（bid.gates → 五门台账 + 追认 + 人工过门） ============
  // 数据来源：壳侧 bid.gates（DomainStore 直读——五门 approved/latest_pass/
  // agent_waivers/human_review_complete/reviews）；写面 bid.gate_pass（宿主
  // 签发 receipt #182 → record_review_gate 真实工具面）。门序/状态窗裁决
  // 全在域层——壳侧拒绝文案原样透传成引导，不假成功。
  var BID_GT_TITLES = {
    matrix_approval: "矩阵定稿门",
    outline_approval: "大纲定稿门",
    pre_export_confirm: "导出前确认门",
    addendum_waiver: "补遗逐件确认门",
    no_addendum_confirmed: "无补遗全局确认门"
  };
  /** 三主门可人工过/拒审；两补遗门的写面走 record_addendum_waiver（批 C） */
  var BID_GT_MAIN = ["matrix_approval", "outline_approval", "pre_export_confirm"];
  function bidGtTitle(g) {
    return BID_GT_TITLES[g] || g;
  }
  function bidGtMethodZh(m) {
    return m === "human_receipt" ? "人工确认" : m === "agent_declared" ? "Agent 声明" : m || "—";
  }
  function bidGtTime(at) {
    if (!at) return "—";
    const d = new Date(at * 1000);
    const p = (x) => String(x).padStart(2, "0");
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }
  /** 过门/拒审内联确认表单（写面动作——显式二次确认 + 理由/发现输入） */
  function bidGtFormHtml(gate, mode) {
    const isReject = mode === "reject";
    return (
      '<div class="bid-gt-form" data-gt-form="' + esc(gate) + '" data-gt-mode="' + esc(mode) + '">'
      + '<div class="bid-gt-form-title">' + (isReject ? ICON.warning + " 拒审 " : ICON.shield + " 过门确认 ") + esc(bidGtTitle(gate)) + "</div>"
      + '<div class="bid-gt-form-sub">由宿主用本工作区审批密钥签发回执（#182——Agent 不可伪造），经审核门工具落账，审计留痕不可抹除。</div>'
      + '<label class="bid-gt-field"><span>理由（可空）</span><input type="text" class="bid-gt-input" data-gt-reason placeholder="' + (isReject ? "如：条款 3.2 响应不实" : "如：已逐条核对响应矩阵") + '"></label>'
      + (isReject
        ? '<label class="bid-gt-field"><span>BLOCKER 发现（拒审必填）</span><textarea class="bid-gt-input" rows="2" data-gt-blocker placeholder="拒审依据——Warning 不构成拒审（诚实状态），将派生修订工单 RT"></textarea></label>'
        : "")
      + '<div class="bid-gt-form-actions">'
      + '<button class="btn btn-sm' + (isReject ? " btn-danger" : " btn-primary") + '" data-gt-confirm="' + esc(gate) + '" data-gt-decision="' + (isReject ? "REJECTED" : "APPROVED") + '">' + (isReject ? "确认拒审" : "确认过门") + "</button>"
      + '<button class="btn btn-sm" data-gt-cancel>取消</button>'
      + "</div></div>"
    );
  }
  /** #603 批 C：补遗逐件确认列表（不就绪件 + 内联理由表单 + 已确认审计） */
  function bidGtAwListHtml(aw) {
    const d = aw.data || {};
    const rd = d.readiness || {};
    const notReady = Array.isArray(rd.not_ready) ? rd.not_ready : [];
    const waivers = Array.isArray(d.waivers) ? d.waivers : [];
    let html =
      '<div class="bid-gt-aw">'
      + '<div class="bid-gt-form-sub">' + (rd.total
        ? "不就绪件逐件确认后放行（#184——起草标 RESTRICTED，不静默当完整输入）；已确认件审计不消失。共 " + rd.total + " 件 · 就绪 " + (rd.ready || 0) + "。"
        : "未发现补遗/澄清件（NotProvided）——本门无可逐件确认的对象；「本项目无补遗」走无补遗全局确认门（#379 语义分账）。") + "</div>";
    if (aw.status === "loading" || aw.status === "idle") {
      html += '<div class="bid-gt-form-sub">正在读取补遗台账…</div>';
    } else if (aw.status === "error") {
      html += '<div class="bid-gt-form-sub">补遗台账读取失败：' + esc(aw.error || "未知") + "</div>";
    } else {
      notReady.forEach((f) => {
        html +=
          '<div class="bid-gt-aw-row" data-file="' + esc(f.file_id) + '">'
          + '<div class="bid-gt-aw-main"><span class="bid-gt-aw-name">' + esc(f.name || f.file_id) + '</span>'
          + '<span class="bid-gt-aw-meta">' + esc(f.file_id) + " · " + esc(f.readiness || "") + (f.waived ? ' · <span class="bid-gt-aw-waived">已确认放行</span>' : "") + "</span></div>"
          + '<div class="bid-gt-aw-reason" title="' + esc(f.reason || "") + '">' + esc(f.reason || "") + "</div>";
        if (!f.waived) {
          html +=
            '<div class="bid-gt-aw-actions">'
            + '<input type="text" class="bid-gt-input" data-aw-reason="' + esc(f.file_id) + '" placeholder="确认理由（必填——不可审计的确认不成确认）">'
            + '<button class="btn btn-sm btn-primary" data-aw-confirm="' + esc(f.file_id) + '"' + (aw.waiving ? " disabled" : "") + ">确认放行</button>"
            + "</div>";
        }
        html += "</div>";
      });
      if (!notReady.length && rd.total) {
        html += '<div class="bid-gt-form-sub">全部补遗件就绪——无需逐件确认。</div>';
      }
      if (waivers.length) {
        html += '<div class="bid-gt-form-sub">已确认台账（审计面——放行后不消失）：</div>';
        waivers.forEach((w) => {
          html += '<div class="bid-gt-aw-audit">' + esc(w.file_id) + " · " + esc(w.principal || "") + " · " + bidGtTime(w.at) + " · " + esc(w.reason || "") + "</div>";
        });
      }
    }
    html += '<div class="bid-gt-form-actions"><button class="btn btn-sm" data-aw-cancel>收起</button></div></div>';
    return html;
  }
  /** #603 批 C：全局无补遗确认表单（#379——NotProvided 阻塞的唯一出口） */
  function bidGtNaFormHtml(aw) {
    return (
      '<div class="bid-gt-aw">'
      + '<div class="bid-gt-form-title">' + ICON.shield + " 确认「本项目无补遗」</div>"
      + '<div class="bid-gt-form-sub">全局显式确认（#379）——仅适用于「未发现补遗/澄清件」的 NotProvided 阻塞；项目已有补遗件时域层响亮拒（那是逐件确认或修复重传的场）。宿主签发回执（#182——Agent 不可伪造），确认即过门 + 审计留痕。</div>'
      + '<label class="bid-gt-field"><span>确认理由（必填）</span><input type="text" class="bid-gt-input" data-na-reason placeholder="如：已核对招标文件全册与答疑纪要，本项目无补遗/澄清件"></label>'
      + '<div class="bid-gt-form-actions">'
      + '<button class="btn btn-sm btn-primary" data-na-confirm' + (aw.waiving ? " disabled" : "") + ">确认无补遗</button>"
      + '<button class="btn btn-sm" data-na-cancel>取消</button>'
      + "</div></div>"
    );
  }
  /** 审核门面板主体（工作台右面板的 gates 页签） */
  function renderBidGatesPanel(host) {
    const panel = host.querySelector("#bid-panel");
    if (!panel) return;
    const gt = state.bidGates;
    const aw = state.bidAddenda;
    if (gt.status === "idle") {
      panel.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>正在读取审核门台账…</div></div>';
      ui.loadBidGates();
      return;
    }
    if (gt.status === "loading") {
      panel.innerHTML = '<div class="bid-gt"><div class="view-state"><div class="view-spinner"></div><div>正在读取门台账…</div></div></div>';
      return;
    }
    if (gt.code === "not_found" || gt.code === "state") {
      // R6（#47 / #19 任务 3）：E_NOTFOUND 引导卡（契约 §3.4）——门台账
      // 面注释口径「只在无 db.json 时分支引导」此前只写在注释里（代码
      // 一把抓 error 横幅），R6 补上实现：空工作区 → 去建项向导第一步；
      // state 码兜底同走引导卡（读面无状态窗，出现即透传给用户看原文）。
      renderBidEarlyGuide(host, panel, {
        code: gt.code,
        wrapClass: "bid-gt",
        title: gt.code === "not_found" ? "还没有标书项目" : "门台账尚未开放",
        text: gt.code === "not_found"
          ? "当前工作区没有 db.json——新建标书项目后，审核门台账在这里追踪五个门的通过 / 追认 / 拒审记录"
          : esc(gt.error || ""),
        next: gt.code === "not_found"
          ? "新建标书项目（向导第一步）——建项后导入招标文件、起草应答，三门过审（结构 / 内容 / 格式）在这里逐门落账"
          : "导入招标文件（向导第二步）——按门台账的状态提示完成前置动作后，门台账在这里逐门给出可过门状态",
        retry: () => ui.loadBidGates(true)
      });
      return;
    }
    if (gt.status === "error" || !gt.data) {
      panel.innerHTML =
        '<div class="bid-gt"><div class="view-state" data-kind="error"><div class="view-state-title">审核门台账读取失败</div><div>'
        + esc(gt.error || "无数据")
        + '</div><div><button class="btn" data-gt-retry>重试</button></div></div></div>';
      const retry = panel.querySelector("[data-gt-retry]");
      if (retry) retry.addEventListener("click", () => ui.loadBidGates(true));
      return;
    }
    const d = gt.data;
    const gates = Array.isArray(d.gates) ? d.gates : [];
    const waivers = Array.isArray(d.agent_waivers) ? d.agent_waivers : [];
    const reviews = Array.isArray(d.reviews) ? d.reviews : [];
    const human = !!d.human_review_complete;
    const approvedN = gates.filter((g) => g.approved).length;
    const passing = gt.passing;
    let html = '<div class="bid-gt">';
    // 头部：人工复核完成度徽章 + 刷新
    html +=
      '<div class="bid-gt-head">'
      + '<span class="bid-gt-badge" data-state="' + (human ? "ok" : "warn") + '">' + (human ? ICON.check + " 人工复核完成" : ICON.warning + " 存在待追认门") + "</span>"
      + '<span class="bid-gt-sub">' + approvedN + "/" + gates.length + " 门已过 · " + (gt.ts ? timeAgo(gt.ts) : "—") + "</span>"
      + '<span class="bid-wb-spacer"></span>'
      + '<button class="btn btn-sm" data-bid-act="refresh-gates" title="重新读取 bid.gates">' + ICON.refresh + "刷新台账</button>"
      + "</div>";
    // 写面消息（成功/失败——域层拒绝原样透传，不假成功）
    if (gt.passInfo) html += '<div class="bid-gt-msg ok">' + ICON.check + " " + esc(gt.passInfo) + "</div>";
    if (gt.passError) html += '<div class="bid-gt-msg err">' + ICON.warning + " " + esc(gt.passError) + "</div>";
    // #20：VALIDATING+缺章异常态恢复出口（#243——域层三重约束守门：
    // 仅 VALIDATING / 仅缺章 / 理由必填；非死锁态按了也 E_STATE 响亮拒）
    const projSt = (state.bid.data && state.bid.data.state && state.bid.data.state.status) || "";
    if (projSt === "VALIDATING") {
      html +=
        '<div class="bid-card" data-kind="recover"><div class="bid-card-title">' + ICON.warning + " 校验异常态（VALIDATING）</div>"
        + '<div class="bid-card-sub">项目停在 VALIDATING 且存在未起草叶（旧版校验误推进所致）——恢复回 DRAFTING 解锁起草面；每次恢复落审计记录（何时/为何/缺哪些章）</div>';
      if (gt.formGate === "__recover__") {
        html +=
          '<div class="bid-gt-form" data-rv-form>'
          + '<div class="bid-gt-form-title">人工恢复（审计留痕）</div>'
          + '<textarea class="bid-gt-input" data-rv-reason rows="2" placeholder="恢复理由（必填非空白）——如：旧版校验在缺章时误推进 VALIDATING"></textarea>'
          + '<div class="bid-gt-form-actions">'
          + '<button class="btn btn-primary btn-sm" data-rv-confirm' + (passing ? " disabled" : "") + ">" + (passing ? "恢复中…" : "确认恢复") + "</button>"
          + '<button class="btn btn-sm" data-rv-cancel>取消</button></div>'
          + "</div>";
      } else {
        html += '<div class="bid-card-actions"><button class="btn btn-sm" data-rv-open' + (passing ? " disabled" : "") + ">恢复起草面（回 DRAFTING）</button></div>";
      }
      html += "</div>";
    }
    // 写面消息（#603 批 C——补遗豁免，域层拒绝原样透传，不假成功）
    if (aw.waiveInfo) html += '<div class="bid-gt-msg ok">' + ICON.check + " " + esc(aw.waiveInfo) + "</div>";
    if (aw.waiveError) html += '<div class="bid-gt-msg err">' + ICON.warning + " " + esc(aw.waiveError) + "</div>";
    // ① agent 豁免追认清单（#277——human_confirmed=false 的门）
    if (waivers.length) {
      html += '<div class="bid-card" data-kind="ratify"><div class="bid-card-title">' + ICON.warning + " Agent 声明过门待追认（" + waivers.length + "）</div>";
      html += '<div class="bid-card-sub">以下门由 Agent 自行声明通过（导出正文将带警告横幅）——真人补签即追认：追加一条人工确认记录，警告消除，历史两条并存可审计。</div><div class="bid-gt-ratify-list">';
      waivers.forEach((w) => {
        html +=
          '<div class="bid-gt-ratify-row">'
          + '<span class="bid-gt-ratify-gate">' + esc(bidGtTitle(w.gate)) + "</span>"
          + '<span class="bid-gt-ratify-meta" title="' + esc(w.reason || "") + '">' + esc(w.actor || "") + " · " + bidGtTime(w.at) + " · " + esc((w.reason || "").slice(0, 40)) + "</span>"
          + '<button class="btn btn-sm btn-primary" data-gt-ratify="' + esc(w.gate) + '"' + (passing ? " disabled" : "") + ">追认（补人工确认）</button>"
          + "</div>";
      });
      html += "</div></div>";
    } else {
      html += '<div class="bid-card"><div class="bid-card-sub">' + ICON.check + " 无待追认门——每门最新一条过门记录均为人工确认（或尚无 agent 声明），导出不带警告</div></div>";
    }
    // ② 五门状态卡（三主门带过门/拒审入口；两补遗门写面归批 C）
    html += '<div class="bid-card"><div class="bid-card-title">' + ICON.shield + " 门台账（" + approvedN + "/" + gates.length + " 已过）</div>";
    gates.forEach((g) => {
      const isMain = BID_GT_MAIN.indexOf(g.gate) >= 0;
      const lp = g.latest_pass;
      const agentLatest = lp && lp.human_confirmed === false;
      html +=
        '<div class="bid-gt-row" data-gate="' + esc(g.gate) + '" data-approved="' + String(!!g.approved) + '">'
        + '<div class="bid-gt-row-main">'
        + '<span class="bid-gt-dot" data-state="' + (g.approved ? (agentLatest ? "warn" : "ok") : "pending") + '"></span>'
        + '<span class="bid-gt-name">' + esc(g.title || bidGtTitle(g.gate)) + "</span>"
        + '<span class="bid-gt-state" data-state="' + (g.approved ? (agentLatest ? "warn" : "ok") : "pending") + '">' + (g.approved ? (agentLatest ? "已过（Agent）" : "已过") : "未过") + "</span>"
        + "</div>"
        + '<div class="bid-gt-row-note">' + esc(g.note || "") + "</div>"
        + (lp
          ? '<div class="bid-gt-row-pass">最近过门：' + esc(lp.actor || "") + " · <span class=\"bid-gt-method\" data-m=\"" + esc(lp.method || "") + "\">" + bidGtMethodZh(lp.method) + "</span> · " + bidGtTime(lp.at) + (lp.reason ? " · " + esc(lp.reason) : "") + "</div>"
          : "")
        + '<div class="bid-gt-row-actions">';
      if (isMain) {
        html +=
          '<button class="btn btn-sm" data-gt-open="' + esc(g.gate) + '" data-gt-mode="approve"' + (passing ? " disabled" : "") + ">过门</button>"
          + '<button class="btn btn-sm" data-gt-open="' + esc(g.gate) + '" data-gt-mode="reject"' + (passing ? " disabled" : "") + ">拒审</button>";
      } else if (g.gate === "addendum_waiver") {
        html += '<button class="btn btn-sm" data-gt-aw-toggle' + (aw.waiving ? " disabled" : "") + ">逐件确认</button>";
      } else {
        html += '<button class="btn btn-sm" data-gt-na-toggle' + (aw.waiving ? " disabled" : "") + ">确认无补遗</button>";
      }
      html += "</div>";
      if (gt.formGate === g.gate && gt.formMode) html += bidGtFormHtml(g.gate, gt.formMode);
      // #603 批 C：两补遗门的写面（逐件/全局——#379 语义分账）
      if (g.gate === "addendum_waiver" && aw.formOpen) html += bidGtAwListHtml(aw);
      if (g.gate === "no_addendum_confirmed" && aw.formGlobal) html += bidGtNaFormHtml(aw);
      html += "</div>";
    });
    html += "</div>";
    // ③ 裁决历史（REV 记录——append-only 审计面）
    html += '<div class="bid-card"><div class="bid-card-title">裁决历史（' + reviews.length + "）</div>";
    if (!reviews.length) {
      html += '<div class="bid-card-sub">尚无记审记录——过门/拒审/Agent 声明都会在此留痕（不可抹除）</div>';
    } else {
      html += '<div class="bid-gt-reviews">';
      reviews.slice(0, 30).forEach((rv) => {
        const actor = rv.actor || {};
        html +=
          '<div class="bid-gt-rev" data-decision="' + esc(rv.decision || "") + '">'
          + "<span>" + esc(rv.id || "") + "</span>"
          + "<span>" + esc(bidGtTitle(rv.gate)) + "</span>"
          + '<span class="bid-gt-rev-decision">' + (rv.decision === "REJECTED" ? "拒审" : "过门") + "</span>"
          + "<span>" + esc(rv.reviewer || (actor.actor_id || "")) + "（" + esc(actor.actor_type || "") + "）</span>"
          + "<span>" + bidGtTime(rv.at) + "</span>"
          + "</div>";
      });
      html += "</div>";
      if (reviews.length > 30) html += '<div class="bid-card-sub">仅显示最近 30 条（共 ' + reviews.length + " 条）</div>";
    }
    html += "</div></div>";
    panel.innerHTML = html;
    bindBidViewActions(panel);
    // ---- 面板本地交互（写面动作都走 ui.passBidGate——域层裁决）----
    panel.querySelectorAll("[data-gt-open]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const gate = btn.dataset.gtOpen;
        const mode = btn.dataset.gtMode;
        // 同门同模式 → 收起；否则展开（切换门/模式）
        if (gt.formGate === gate && gt.formMode === mode) {
          gt.formGate = "";
          gt.formMode = "";
        } else {
          gt.formGate = gate;
          gt.formMode = mode;
        }
        renderBidGatesPanel(host);
      });
    });
    panel.querySelectorAll("[data-gt-cancel]").forEach((btn) => {
      btn.addEventListener("click", () => {
        gt.formGate = "";
        gt.formMode = "";
        renderBidGatesPanel(host);
      });
    });
    panel.querySelectorAll("[data-gt-confirm]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const gate = btn.dataset.gtConfirm;
        const decision = btn.dataset.gtDecision;
        const form = panel.querySelector('[data-gt-form="' + gate + '"]');
        const reasonEl = form && form.querySelector("[data-gt-reason]");
        const blockerEl = form && form.querySelector("[data-gt-blocker]");
        const reason = reasonEl ? reasonEl.value.trim() : "";
        const blocker = blockerEl ? blockerEl.value.trim() : "";
        if (decision === "REJECTED" && !blocker) {
          gt.passError = "拒审必须填写 BLOCKER 发现（Warning 不构成拒审依据——诚实状态）";
          renderBidGatesPanel(host);
          return;
        }
        ui.passBidGate(gate, decision, {
          reason: reason || undefined,
          blockerMessage: blocker || undefined,
          blockerCode: "SHELL-REJECT"
        });
      });
    });
    panel.querySelectorAll("[data-gt-ratify]").forEach((btn) => {
      btn.addEventListener("click", () => {
        ui.passBidGate(btn.dataset.gtRatify, "APPROVED", {
          reason: "追认 agent 声明过门（人工补确认）",
          actorId: "shell-operator"
        });
      });
    });
    // ---- #20 恢复出口交互（data-rv-*——VALIDATING 异常态，#243）
    panel.querySelectorAll("[data-rv-open]").forEach((btn) => {
      btn.addEventListener("click", () => {
        gt.formGate = "__recover__";
        gt.passError = "";
        renderBidGatesPanel(host);
      });
    });
    panel.querySelectorAll("[data-rv-cancel]").forEach((btn) => {
      btn.addEventListener("click", () => {
        gt.formGate = "";
        renderBidGatesPanel(host);
      });
    });
    panel.querySelectorAll("[data-rv-confirm]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const form = panel.querySelector("[data-rv-form]");
        const reasonEl = form && form.querySelector("[data-rv-reason]");
        const reason = reasonEl ? reasonEl.value.trim() : "";
        if (!reason) {
          gt.passError = "恢复理由必填（不可审计的恢复不成恢复）";
          renderBidGatesPanel(host);
          return;
        }
        ui.recoverBidState(reason);
      });
    });
    // ---- #603 批 C：补遗豁免交互（逐件/全局——域层裁决，#379 语义分账）
    const awToggle = panel.querySelector("[data-gt-aw-toggle]");
    if (awToggle)
      awToggle.addEventListener("click", () => {
        const awS = state.bidAddenda;
        awS.formOpen = !awS.formOpen;
        if (awS.formOpen && awS.status === "idle") ui.loadBidAddenda();
        renderBidGatesPanel(host);
      });
    const naToggle = panel.querySelector("[data-gt-na-toggle]");
    if (naToggle)
      naToggle.addEventListener("click", () => {
        state.bidAddenda.formGlobal = !state.bidAddenda.formGlobal;
        renderBidGatesPanel(host);
      });
    panel.querySelectorAll("[data-aw-cancel]").forEach((b) =>
      b.addEventListener("click", () => {
        state.bidAddenda.formOpen = false;
        renderBidGatesPanel(host);
      })
    );
    panel.querySelectorAll("[data-na-cancel]").forEach((b) =>
      b.addEventListener("click", () => {
        state.bidAddenda.formGlobal = false;
        renderBidGatesPanel(host);
      })
    );
    panel.querySelectorAll("[data-aw-confirm]").forEach((btn) =>
      btn.addEventListener("click", () => {
        const fid = btn.dataset.awConfirm;
        const input = panel.querySelector('[data-aw-reason="' + fid + '"]');
        const reason = input ? input.value.trim() : "";
        if (!reason) {
          state.bidAddenda.waiveError = "确认理由必填（不可审计的确认不成确认）";
          renderBidGatesPanel(host);
          return;
        }
        ui.waiveBidAddendum(fid, reason);
      })
    );
    const naConfirm = panel.querySelector("[data-na-confirm]");
    if (naConfirm)
      naConfirm.addEventListener("click", () => {
        const input = panel.querySelector("[data-na-reason]");
        const reason = input ? input.value.trim() : "";
        if (!reason) {
          state.bidAddenda.waiveError = "确认理由必填（不可审计的确认不成确认）";
          renderBidGatesPanel(host);
          return;
        }
        ui.confirmNoAddendum(reason);
      });
  }

  // ============ #313 批 B：合规矩阵面板（bid.matrix → 表格 + 筛选 + 分页 + 导出） ============
  // 数据来源：壳侧 bid.matrix（经 bid_mcp::dispatch_with 走 get_compliance_matrix
  // 真实工具面，壳内聚合 cursor 分页后的全量行）。行字段 = 工具输出原样透传；
  // 筛选（状态/类别/只看阻断）、分页、导出都在全量行上做——徽章计数与表格同一真源。
  var BID_MX_STATUS_ZH = {
    NOT_RESPONDED: "未响应",
    RESPONDED: "已响应",
    PARTIAL: "部分响应",
    PENDING_EVIDENCE: "待补证据",
    NOT_APPLICABLE: "不适用"
  };
  // chips 展示序（未响应前置——最需要用户处置的状态排最前）
  var BID_MX_STATUSES = ["NOT_RESPONDED", "RESPONDED", "PARTIAL", "PENDING_EVIDENCE", "NOT_APPLICABLE"];
  function bidMxStatusZh(s) {
    return BID_MX_STATUS_ZH[s] || s;
  }
  function bidMxRows() {
    const mx = state.bid.matrix;
    return mx && mx.data && Array.isArray(mx.data.rows) ? mx.data.rows : [];
  }
  function bidMxSectionTitle(id) {
    if (!id) return "";
    const n = bidOutlineNodes().find((x) => x.id === id);
    return n ? n.title : "";
  }
  /** 类别清单（首现序 + 计数）——工具面 rows 的 category 中文原名 */
  function bidMxCategories(rows) {
    const seen = {};
    const out = [];
    for (const r of rows) {
      const c = (r.requirement && r.requirement.category) || "";
      if (!c) continue;
      if (!seen[c]) {
        seen[c] = { name: c, count: 0 };
        out.push(seen[c]);
      }
      seen[c].count++;
    }
    return out;
  }
  /** 全量行 → 筛选行（状态 / 类别 / 只看阻断——面板本地态，不改壳侧过滤面） */
  function bidMxFiltered(rows) {
    const f = state.bid.mx;
    return rows.filter((r) => {
      if (f.blockingOnly && !r.blocking) return false;
      if (f.status && r.status !== f.status) return false;
      if (f.cat && (!r.requirement || r.requirement.category !== f.cat)) return false;
      return true;
    });
  }
  /** 当前活动页签（detail / matrix；批 C/D 接线时在此扩） */
  function bidPanelOf() {
    const tab = bidWorkbenchTab();
    return (tab && tab.meta && tab.meta.panel) || "detail";
  }
  /** 页签按钮态（aria-selected + active 类）随 meta.panel 同步 */
  function renderBidTabsState(host) {
    const cur = bidPanelOf();
    host.querySelectorAll(".bid-tabs .bid-tab[data-bid-panel]").forEach((btn) => {
      const on = btn.dataset.bidPanel === cur;
      btn.setAttribute("aria-selected", String(on));
      if (on) btn.classList.add("active");
      else btn.classList.remove("active");
    });
  }
  /** 右侧面板分发：matrix → 矩阵；coverage → 覆盖报告；否则章节详情（选中节点） */
  function renderBidActivePanel(host) {
    renderBidTabsState(host);
    const panel = host.querySelector("#bid-panel");
    if (!panel) return;
    if (bidPanelOf() === "matrix") {
      renderBidMatrixPanel(host, panel);
      return;
    }
    if (bidPanelOf() === "gates") {
      renderBidGatesPanel(host);
      return;
    }
    if (bidPanelOf() === "coverage") {
      renderBidCoveragePanel(host, panel);
      return;
    }
    const nodes = bidOutlineNodes();
    const byId = {};
    nodes.forEach((n) => {
      byId[n.id] = n;
    });
    const tab = bidWorkbenchTab();
    const selId = tab && tab.meta && tab.meta.selectedId;
    const node = (selId && byId[selId]) || nodes.find((n) => !nodes.some((m) => m.parent_id === n.id)) || nodes[0];
    if (node) renderBidDetail(host, node);
    else panel.innerHTML = "";
  }
  /** 矩阵行 → 展开详情（条款原文/锚点/证据/响应章节——「点未响应项看原文」） */
  function bidMxDetailRow(r) {
    const q = r.requirement || {};
    const a = q.source_anchor || {};
    const evs = r.evidence || [];
    const pends = r.pending_evidence_ids || [];
    const evHtml = evs.length
      ? evs
          .map((e) => '<div class="bid-mx-ev-line">' + esc(e.ev_id) + " · " + esc(e.title || "") + (e.verification_tier ? ' <span class="bid-mx-ev-tier">[' + esc(e.verification_tier) + "]</span>" : "") + "</div>")
          .join("")
      : '<div class="bid-mx-ev-line dim">无在绑证据' + (r.evidence_required ? "（本条款要求证明材料——#241 证据缺口面）" : "") + "</div>";
    const pendHtml = pends.length ? '<div class="bid-mx-ev-line pend">待补占位：' + esc(pends.join("、")) + "（#245 待补可追踪，不清阻塞）</div>" : "";
    // #20：人工裁定出口（#226 否决项死锁——理由必填 + receipt 壳签发）。
    // 死锁场景（必选条款无法响应且证据无法补）出在此行展开面；非死锁也能
    // 裁定（域层守门：状态机不允许时 E_STATE 响亮拒）。
    const f = state.bid.mx;
    let moHtml =
      '<div class="bid-mx-d-block"><div class="bid-mx-d-k">人工裁定（#226）</div>'
      + '<div class="bid-mx-d-v">'
      + '<button class="btn btn-sm" data-mo-open="' + esc(q.id) + '"' + (f.passing ? " disabled" : "") + ">"
      + (f.formReq === q.id ? "收起裁定表单" : "裁定响应状态")
      + "</button>"
      + (r.blocking ? ' <span class="bid-mx-block">阻断行——常见出口：招标人规则说明标「不适用」并附偏离依据</span>' : "")
      + "</div>";
    if (f.formReq === q.id) {
      moHtml +=
        '<div class="bid-gt-form" data-mo-form="' + esc(q.id) + '">'
        + '<div class="bid-gt-form-title">' + esc(q.id) + " → 人工裁定（审计留痕：操作者/理由/时间，不可抹除）</div>"
        + '<label class="bid-mx-check">目标状态'
        + '<select class="bid-gt-input" data-mo-status>'
        + '<option value="NOT_APPLICABLE">不适用（招标人规则说明——须填偏离依据）</option>'
        + '<option value="RESPONDED">已响应（补正文后人工改判）</option>'
        + '<option value="PARTIAL">部分响应</option>'
        + '<option value="NOT_RESPONDED">未响应（维持现状——仅改台账口径时用）</option>'
        + "</select></label>"
        + '<textarea class="bid-gt-input" data-mo-deviation rows="2" placeholder="偏离/不适用说明——NOT_APPLICABLE 必填（不可审计的豁免不算豁免）"></textarea>'
        + '<div class="bid-gt-form-actions">'
        + '<button class="btn btn-primary btn-sm" data-mo-confirm="' + esc(q.id) + '"' + (f.passing ? " disabled" : "") + ">" + (f.passing ? "裁定中…" : "确认裁定") + "</button>"
        + '<button class="btn btn-sm" data-mo-cancel>取消</button></div>'
        + (f.passError ? '<div class="bid-wiz-error">' + esc(f.passError) + "</div>" : "")
        + (f.passInfo ? '<div class="bid-wiz-info">' + esc(f.passInfo) + "</div>" : "")
        + "</div>";
    }
    moHtml += "</div>";
    return (
      '<tr class="bid-mx-detail"><td colspan="6">'
      + '<div class="bid-mx-d-grid">'
      + '<div class="bid-mx-d-block"><div class="bid-mx-d-k">条款原文</div><div class="bid-mx-d-v">' + esc(a.excerpt || q.statement || "（无摘录）") + "</div></div>"
      + '<div class="bid-mx-d-block"><div class="bid-mx-d-k">锚点</div><div class="bid-mx-d-v">' + esc(a.file || "（无锚点文件）") + (a.locator ? " · " + esc(a.locator) : "") + (a.file ? ' <button class="bid-mx-link" data-mx-src="' + esc(a.file) + '">打开原文文件</button>' : "") + "</div></div>"
      + '<div class="bid-mx-d-block"><div class="bid-mx-d-k">证据</div><div class="bid-mx-d-v">' + evHtml + pendHtml + "</div></div>"
      + '<div class="bid-mx-d-block"><div class="bid-mx-d-k">响应章节</div><div class="bid-mx-d-v">' + (r.draft_section_id
        ? '<button class="bid-mx-link" data-mx-sec="' + esc(r.draft_section_id) + '">跳转 ' + esc(bidMxSectionTitle(r.draft_section_id) || r.draft_section_id) + "</button>"
        : "未归属——大纲树尚无章节覆盖本条款") + "</div></div>"
      + moHtml
      + "</div></td></tr>"
    );
  }
  /** #20 分包面板（工作台右面板的 packages 页签——bid.packages 只读）
   *  多标段/多包识别（#316）：包清单 + 逐包条款数 + 选包状态 + 共用条款。
   *  只读面：选包动作不在本面板（选包 = build_outline 传 package 参数——
   *  管线动作，走 MCP；面板只呈现识别结果与 usage 提示，不伪装可写）。 */
  function renderBidPackagesPanel(host) {
    const panel = host.querySelector("#bid-panel");
    if (!panel) return;
    const pk = state.bidPackages;
    if (pk.status === "idle") ui.loadBidPackages();
    if (pk.status === "idle" || pk.status === "loading") {
      panel.innerHTML = '<div class="bid-gt"><div class="view-state"><div class="view-spinner"></div><div>正在读取分包清单…</div></div></div>';
      return;
    }
    if (pk.status === "error" || !pk.data) {
      panel.innerHTML =
        '<div class="bid-gt"><div class="view-state" data-kind="error"><div class="view-state-title">分包清单读取失败</div><div>'
        + esc(pk.error || "无数据")
        + '</div><div><button class="btn" data-pk-retry>重试</button></div></div></div>';
      const retry = panel.querySelector("[data-pk-retry]");
      if (retry) retry.addEventListener("click", () => ui.loadBidPackages(true));
      return;
    }
    const d = pk.data && pk.data.packages || {};
    const items = Array.isArray(d.items) ? d.items : [];
    const sel = d.selected_package;
    let html =
      '<div class="bid-gt">'
      + '<div class="bid-card"><div class="bid-card-title">分包清单（#316 识别面）</div>'
      + '<div class="bid-card-sub">识别 ' + fmtChars(d.detected) + " 包 · 共用条款 " + fmtChars(d.shared_req_count) + " · 条款总数 " + fmtChars(d.total_requirements) + "</div>";
    if (!items.length) {
      html += '<div class="bid-card-sub">未识别出多标段/多包结构——单包项目无需选包</div>';
    } else {
      html += '<div class="bid-gt-gates">';
      for (const it of items) {
        html +=
          '<div class="bid-gt-row" data-selected="' + (it.selected ? "true" : "false") + '">'
          + '<div class="bid-gt-main"><span class="bid-gt-name">' + esc(it.label || it.id) + "</span>"
          + '<span class="bid-gt-sub">' + esc(it.kind || "") + (it.number ? " · " + esc(it.number) : "") + " · 条款 " + fmtChars(it.req_count)
          + (Array.isArray(it.sources) && it.sources.length ? " · 来源 " + it.sources.length + " 件" : "")
          + "</span></div>"
          + '<span class="bid-badge" data-status="' + (it.selected ? "ok" : "") + '">' + (it.selected ? "已选包" : "未选") + "</span>"
          + "</div>";
      }
      html += "</div>";
    }
    html += '<div class="bid-card-sub">' + esc(d.usage || "") + "</div>";
    if (sel) html += '<div class="bid-card-sub">当前选包：' + esc(sel.label || sel.id) + "</div>";
    html += '</div><div class="bid-card-actions"><button class="btn btn-sm" data-pk-refresh>刷新</button></div></div>';
    panel.innerHTML = html;
    const rf = panel.querySelector("[data-pk-refresh]");
    if (rf) rf.addEventListener("click", () => ui.loadBidPackages(true));
  }
  /** 合规矩阵面板主体（工作台右面板的 matrix 页签） */
  function renderBidMatrixPanel(host, panel) {
    const mx = state.bid.matrix;
    // #20 顺手修：工作台路由经单参调用（panel 未传）——与 gates/quality
    // 面板同款防御取值，否则「合规矩阵」页签点击即 TypeError（运行时断链，
    // 静态断言拦不住——issue #21 的典型形态）。
    if (!panel) panel = host.querySelector("#bid-panel");
    if (!panel) return;
    // 矩阵面不选中大纲树节点（避免左树残留详情高亮）
    host.querySelectorAll("#bid-tree .bid-node").forEach((row) => {
      row.dataset.selected = "false";
    });
    if (mx.status === "idle") ui.loadBidMatrix();
    if (mx.status === "idle" || mx.status === "loading") {
      panel.innerHTML = '<div class="bid-mx"><div class="view-state"><div class="view-spinner"></div><div>正在读取合规矩阵…</div></div></div>';
      return;
    }
    if (mx.status === "error" && (mx.code === "not_found" || mx.code === "state")) {
      // R6（#47 / #19 任务 3）：E_NOTFOUND / E_STATE 引导卡（契约 §3.4）——
      // 矩阵未建对 DRAFT 项目是主路径不是故障，此前与真故障（io 等）一把
      // 抓成「矩阵读取失败」横幅。not_found → 去建项；state → 去导入（E_STATE
      // 原文进卡，含状态与前置说明）。
      renderBidEarlyGuide(host, panel, {
        code: mx.code,
        wrapClass: "bid-mx",
        title: mx.code === "not_found" ? "还没有标书项目" : "合规矩阵尚未开放",
        text: mx.code === "not_found"
          ? "当前工作区没有 db.json——新建标书项目并导入招标文件后，条款合规矩阵在这里逐条对照响应"
          : esc(mx.error || ""),
        next: mx.code === "not_found"
          ? "新建标书项目（向导第一步）——建项后导入招标文件、extract_requirements 抽取条款，矩阵在这里逐条对照"
          : "导入招标文件（向导第二步）——extract_requirements 抽取条款、build_outline 建纲之后，prepare_outline_and_matrix 建矩阵，矩阵在这里逐条对照响应",
        retry: () => ui.loadBidMatrix(true)
      });
      return;
    }
    if (mx.status === "error" || !mx.data) {
      panel.innerHTML =
        '<div class="bid-mx"><div class="view-state" data-kind="error"><div class="view-state-title">矩阵读取失败</div><div>'
        + esc(mx.error || "无数据")
        + '</div><div><button class="btn" data-mx-retry>重试</button></div></div></div>';
      const retry = panel.querySelector("[data-mx-retry]");
      if (retry) retry.addEventListener("click", () => ui.loadBidMatrix(true));
      return;
    }
    const d = mx.data;
    const rows = bidMxRows();
    const sum = d.summary || {};
    const byStatus = sum.by_status || {};
    const star = d.star_summary || {};
    const f = state.bid.mx;
    const cats = bidMxCategories(rows);
    const filtered = bidMxFiltered(rows);
    const totalPages = Math.max(1, Math.ceil(filtered.length / f.pageSize));
    if (f.page > totalPages) f.page = totalPages;
    if (f.page < 1) f.page = 1;
    const start = (f.page - 1) * f.pageSize;
    const pageRows = filtered.slice(start, start + f.pageSize);

    let chips = '<button class="bid-mx-chip" data-mx-status=""' + (!f.status ? ' data-on="true"' : "") + ">全部 " + fmtChars(d.total) + "</button>";
    for (const k of BID_MX_STATUSES) {
      chips += '<button class="bid-mx-chip" data-mx-status="' + esc(k) + '"' + (f.status === k ? ' data-on="true"' : "") + ">" + bidMxStatusZh(k) + " " + fmtChars(byStatus[k] || 0) + "</button>";
    }
    let catSel = '<select class="bid-mx-select" data-mx-cat title="按类别筛选"><option value="">全部类别</option>';
    for (const c of cats) {
      catSel += '<option value="' + esc(c.name) + '"' + (f.cat === c.name ? " selected" : "") + ">" + esc(c.name) + "（" + c.count + "）</option>";
    }
    catSel += "</select>";
    let sizeSel = '<select class="bid-mx-select" data-mx-size title="每页行数">';
    for (const n of [50, 100, 200]) {
      sizeSel += '<option value="' + n + '"' + (f.pageSize === n ? " selected" : "") + ">" + n + " 条/页</option>";
    }
    sizeSel += "</select>";

    let html =
      '<div class="bid-mx">'
      + '<div class="bid-mx-bar">'
      + '<div class="bid-mx-chips">' + chips + "</div>"
      + '<div class="bid-mx-tools">'
      + catSel
      + '<label class="bid-mx-check"><input type="checkbox" data-mx-blocking' + (f.blockingOnly ? " checked" : "") + ">只看阻断（" + fmtChars(sum.blocking || 0) + "）</label>"
      + sizeSel
      + '<button class="btn btn-sm" data-mx-export title="导出当前筛选下的全量行（UTF-8 BOM CSV，Excel 可直接打开）">导出 CSV</button>'
      + "</div></div>"
      + '<div class="bid-mx-sum">共 ' + fmtChars(d.total) + " 条 · 筛选后 " + fmtChars(filtered.length) + " 条 · 阻断 " + fmtChars(sum.blocking || 0) + " · ★实质性 " + fmtChars(star.total != null ? star.total : sum.substantive || 0) + (star.total > 0 ? "（已响应 " + fmtChars(star.responded || 0) + "/" + fmtChars(star.total) + "）" : "") + " · 缺证据 " + fmtChars(sum.evidence_missing || 0) + "</div>";
    if (!rows.length) {
      html +=
        '<div class="view-state"><div class="view-state-title">条款集为空</div><div>MCP 管线 extract_requirements 之后，这里显示 REQ × 响应状态 × 证据 × 章节的合规矩阵</div></div>';
    } else if (!filtered.length) {
      html += '<div class="view-state"><div class="view-state-title">当前筛选无匹配行</div><div>换个状态/类别，或取消「只看阻断」</div></div>';
    } else {
      html += '<div class="bid-mx-table-wrap"><table class="bid-mx-table"><thead><tr><th>条款</th><th>类别</th><th>响应状态</th><th>证据</th><th>响应章节</th><th>标记</th></tr></thead><tbody>';
      for (const r of pageRows) {
        const q = r.requirement || {};
        const evN = (r.evidence || []).length;
        const evPend = (r.pending_evidence_ids || []).length;
        const expanded = f.expandedId === q.id;
        html +=
          '<tr class="bid-mx-row' + (r.blocking ? " is-blocking" : "") + (expanded ? " expanded" : "") + '" data-req="' + esc(q.id) + '">'
          + '<td class="bid-mx-req"><span class="bid-mx-req-id">' + esc(q.id) + (q.clause_no ? " · " + esc(q.clause_no) : "") + '</span><span class="bid-mx-req-st" title="' + esc(q.statement || "") + '">' + esc(q.statement || "（无摘录）") + "</span></td>"
          + '<td class="bid-mx-cat">' + esc(q.category || "—") + (q.mandatory ? ' <span class="bid-mx-mand" title="资格条件/否决项或 Agent 标必选——未响应阻断导出">必选</span>' : "") + "</td>"
          + '<td><span class="bid-mx-badge" data-status="' + esc(r.status) + '">' + esc(bidMxStatusZh(r.status)) + "</span></td>"
          + "<td>"
          + (evN
            ? '<span class="bid-mx-ev ok" title="' + esc((r.evidence || []).map((e) => e.ev_id + (e.title ? "·" + e.title : "")).join("、")) + '">' + evN + " 件</span>"
            : evPend
              ? '<span class="bid-mx-ev pend" title="占位证据在绑（#245 待补面）">占位 ' + evPend + "</span>"
              : '<span class="bid-mx-ev none">—</span>')
          + (r.evidence_missing ? ' <span class="bid-mx-miss" title="要求证明材料但无有效证据在绑（#241 正交标记——与响应状态分账）">缺证据</span>' : "")
          + "</td>"
          + "<td>" + (r.draft_section_id
            ? '<button class="bid-mx-link" data-mx-sec="' + esc(r.draft_section_id) + '" title="跳转到大纲树对应章节">' + esc(bidMxSectionTitle(r.draft_section_id) || r.draft_section_id) + "</button>"
            : "—") + "</td>"
          + '<td class="bid-mx-marks">'
          + (r.substantive ? '<span class="bid-mx-star" title="★实质性条款——一条不响应即响应无效">★</span>' : "")
          + (r.blocking ? '<span class="bid-mx-block" title="必选未响应/待补——阻断导出（R-03/R-04 闸门）">阻断</span>' : "")
          + "</td></tr>";
        if (expanded) html += bidMxDetailRow(r);
      }
      html += "</tbody></table></div>";
      html +=
        '<div class="bid-mx-pager">'
        + '<button class="btn btn-sm" data-mx-page="prev"' + (f.page <= 1 ? " disabled" : "") + ">上一页</button>"
        + '<span class="bid-mx-page-info">第 ' + f.page + " / " + totalPages + " 页 · " + fmtChars(filtered.length) + " 条</span>"
        + '<button class="btn btn-sm" data-mx-page="next"' + (f.page >= totalPages ? " disabled" : "") + ">下一页</button>"
        + "</div>";
    }
    html += "</div>";
    panel.innerHTML = html;

    // ---- 交互接线（重渲染后重挂——与批 A 同款就地绑定纪律）
    panel.querySelectorAll("[data-mx-status]").forEach((c) =>
      c.addEventListener("click", () => {
        state.bid.mx.status = c.dataset.mxStatus || "";
        state.bid.mx.page = 1;
        renderBidMatrixPanel(host, panel);
      })
    );
    const catEl = panel.querySelector("[data-mx-cat]");
    if (catEl)
      catEl.addEventListener("change", () => {
        state.bid.mx.cat = catEl.value;
        state.bid.mx.page = 1;
        renderBidMatrixPanel(host, panel);
      });
    const sizeEl = panel.querySelector("[data-mx-size]");
    if (sizeEl)
      sizeEl.addEventListener("change", () => {
        state.bid.mx.pageSize = Number(sizeEl.value) || 50;
        state.bid.mx.page = 1;
        renderBidMatrixPanel(host, panel);
      });
    const blkEl = panel.querySelector("[data-mx-blocking]");
    if (blkEl)
      blkEl.addEventListener("change", () => {
        state.bid.mx.blockingOnly = blkEl.checked;
        state.bid.mx.page = 1;
        renderBidMatrixPanel(host, panel);
      });
    panel.querySelectorAll("[data-mx-page]").forEach((b) =>
      b.addEventListener("click", () => {
        if (b.disabled) return;
        if (b.dataset.mxPage === "prev") state.bid.mx.page = Math.max(1, f.page - 1);
        else state.bid.mx.page = Math.min(totalPages, f.page + 1);
        renderBidMatrixPanel(host, panel);
      })
    );
    panel.querySelectorAll(".bid-mx-row").forEach((tr) =>
      tr.addEventListener("click", (e) => {
        // #20：裁定表单内的点击不触发行折叠（表单在展开行内——防误触）
        if (e.target.closest("[data-mo-form]") || e.target.closest("[data-mo-open]")) return;
        const id = tr.dataset.req;
        state.bid.mx.expandedId = state.bid.mx.expandedId === id ? "" : id;
        renderBidMatrixPanel(host, panel);
      })
    );
    // ---- #20 人工裁定出口（data-mo-*——与审核门表单同款接线纪律）
    panel.querySelectorAll("[data-mo-open]").forEach((b) =>
      b.addEventListener("click", () => {
        const f2 = state.bid.mx;
        f2.formReq = f2.formReq === b.dataset.moOpen ? "" : b.dataset.moOpen;
        f2.passError = "";
        f2.expandedId = b.dataset.moOpen; // 保持展开（表单在展开行内）
        renderBidMatrixPanel(host, panel);
      })
    );
    panel.querySelectorAll("[data-mo-cancel]").forEach((b) =>
      b.addEventListener("click", () => {
        state.bid.mx.formReq = "";
        state.bid.mx.passError = "";
        renderBidMatrixPanel(host, panel);
      })
    );
    panel.querySelectorAll("[data-mo-confirm]").forEach((b) =>
      b.addEventListener("click", () => {
        const form = panel.querySelector('[data-mo-form="' + b.dataset.moConfirm + '"]');
        const statusEl = form && form.querySelector("[data-mo-status]");
        const devEl = form && form.querySelector("[data-mo-deviation]");
        const status = statusEl ? statusEl.value : "NOT_APPLICABLE";
        const deviation = devEl ? devEl.value.trim() : "";
        if (status === "NOT_APPLICABLE" && !deviation) {
          state.bid.mx.passError = "「不适用」必须填写偏离依据（不可审计的豁免不算豁免——域层同样会拒，前置拦截省一次往返）";
          renderBidMatrixPanel(host, panel);
          return;
        }
        ui.passMatrixOverride(b.dataset.moConfirm, status, deviation);
      })
    );
    panel.querySelectorAll("[data-mx-sec]").forEach((b) =>
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        const t = bidWorkbenchTab();
        if (t) {
          t.meta.panel = "detail";
          t.meta.selectedId = b.dataset.mxSec;
        }
        renderBidActivePanel(host);
      })
    );
    panel.querySelectorAll("[data-mx-src]").forEach((b) =>
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        ui.openPath(absPathOf(b.dataset.mxSrc));
      })
    );
    const expBtn = panel.querySelector("[data-mx-export]");
    if (expBtn) expBtn.addEventListener("click", () => bidMxExport(filtered));
  }
  /** 筛选行 → CSV（UTF-8 BOM——Excel 直开中文不乱码；引号转义双写） */
  function bidMxCsv(rows) {
    const cell = (v) => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
    const head = ["CMP序号", "条款ID", "条款编号", "类别", "条款摘录", "响应状态", "必选", "★实质性", "阻断", "证据要求", "证据缺口", "在绑证据", "待补证据", "响应章节", "锚点文件", "锚点位置"];
    const lines = [head.map(cell).join(",")];
    for (const r of rows) {
      const q = r.requirement || {};
      const a = q.source_anchor || {};
      lines.push(
        [
          r.cmp_id, q.id, q.clause_no || "", q.category || "", q.statement || "",
          bidMxStatusZh(r.status), q.mandatory ? "是" : "否", r.substantive ? "是" : "否",
          r.blocking ? "是" : "否", r.evidence_required ? "是" : "否", r.evidence_missing ? "是" : "否",
          (r.evidence || []).map((e) => e.ev_id + (e.title ? "·" + e.title : "")).join("; "),
          (r.pending_evidence_ids || []).join("; "),
          r.draft_section_id || "", a.file || "", a.locator || ""
        ].map(cell).join(",")
      );
    }
    return "\ufeff" + lines.join("\r\n");
  }
  function utf8ToB64(s) {
    const bytes = new TextEncoder().encode(s);
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  }
  /** 导出：fs.writeBytes 只允许写 .mang/（契约 §5）——落 .mang/exports/，不越权 */
  function bidMxExport(rows) {
    if (!rows.length) {
      ui.toast("error", "当前筛选下没有可导出的行");
      return;
    }
    const pad2 = (n) => (n < 10 ? "0" + n : String(n));
    const t = new Date();
    const name = "合规矩阵-" + t.getFullYear() + pad2(t.getMonth() + 1) + pad2(t.getDate()) + "-" + pad2(t.getHours()) + pad2(t.getMinutes()) + pad2(t.getSeconds()) + ".csv";
    const rel = ".mang/exports/" + name;
    ipc("fs.writeBytes", { path: rel, enc: "b64", data: utf8ToB64(bidMxCsv(rows)) }, 3e4)
      .then((r) => ui.toast("ok", "已导出 " + rows.length + " 条 → " + ((r && r.rel) || rel) + "（Excel 可直接打开）"))
      .catch((err) => ui.toast("error", "导出失败：" + ((err && err.message) || err)));
  }
  // ============ #313 批 B 矩阵面板 END ============

  // ============ #313 批 D：覆盖报告面板（bid.coverage → 三态分账 + ★条款覆盖 + 逐文件表） =====
  // 数据来源：壳侧 bid.coverage（经 bid_mcp::dispatch_with 走 get_coverage_report
  // 真实工具面，工具输出原样透传 + 壳侧三态分账 summary + 逐文件 get_star_coverage
  // 聚合 #285）。三态口径（#244——每块必居其一）：已判定（A：requirement /
  // review_table）/ 已排除（B：noise / rule，理由可追溯）/ 未判定（C：压根
  // 没标记——建纲门阻断面）。★条款覆盖 = 真值★已捕获 / 真值★（一条不响应
  // 即响应无效——面板规格「★条款覆盖 N/M」）。
  var BID_COV_VERDICT_ZH = {
    requirement: "条款",
    review_table: "审查表",
    noise: "噪音",
    rule: "规则"
  };
  function bidCovVerdictZh(v) {
    return BID_COV_VERDICT_ZH[v] || v;
  }
  function bidCovPct(n, total) {
    if (!total) return 0;
    return Math.round((n / total) * 1000) / 10;
  }
  /** 覆盖报告面板主体（工作台右面板的 coverage 页签） */
  function renderBidCoveragePanel(host, panel) {
    const cv = state.bid.coverage;
    // 覆盖面不选中大纲树节点（与矩阵面同款——避免左树残留详情高亮）
    host.querySelectorAll("#bid-tree .bid-node").forEach((row) => {
      row.dataset.selected = "false";
    });
    if (cv.status === "idle") ui.loadBidCoverage();
    if (cv.status === "idle" || cv.status === "loading") {
      panel.innerHTML = '<div class="bid-cov"><div class="view-state"><div class="view-spinner"></div><div>正在读取覆盖报告…</div></div></div>';
      return;
    }
    // R5（#47 / #19 任务 2）：早态引导卡对齐向导交互语言——主行动按钮
    // （去导入/去建项——切回 detail 页签，向导就在那）+ bid-cov-next
    // 「下一步」条 + 次行动「重新检查」。R6（#47 / #19 任务 3）：两分支
    // 收编共享工厂 renderBidEarlyGuide（契约 §3.4 引导卡约定——全部
    // bid.* 读面板同一套呈现与锚点 data-bid-guide-cta / -retry）。
    if (cv.status === "error" && cv.code === "not_found") {
      // R5（#47）：空工作区（无 db.json）不是错误——E_NOTFOUND 引导卡口径
      // （§109）：引导去建项（向导第一步在 detail 页签），不再走下面的
      // 错误横幅（正常空态渲染成故障违反引导卡约定）
      renderBidEarlyGuide(host, panel, {
        code: "not_found",
        wrapClass: "bid-cov",
        title: "还没有标书项目",
        text: "当前工作区没有 db.json——新建标书项目并导入招标文件后，覆盖报告在这里统计「哪些块没归属」",
        next: "新建标书项目（向导第一步）——建项后导入招标文件，覆盖报告自动可用",
        retry: () => ui.loadBidCoverage(true)
      });
      return;
    }
    if (cv.status === "error" && cv.code === "state") {
      // 工具面 E_STATE 透传（壳侧 state 码，契约 §3.3）——早态项目引导卡
      // 而非错误横幅（批 C 自评面同款纪律：单一真源在 code，不在文案）。
      // R5（#47 / #19 任务 2）：对齐向导交互语言——主行动「去导入」直通
      // 向导第二步（detail 页签），不再是只有「重新检查」的死文案。
      renderBidEarlyGuide(host, panel, {
        code: "state",
        wrapClass: "bid-cov",
        title: "覆盖报告尚未开放",
        text: "当前项目还没导入招标文件——覆盖报告统计「哪些块没归属」，导入后自动可用",
        next: "导入招标文件（向导第二步）——extract_requirements 抽取条款、build_outline 建纲之后，覆盖报告在这里给出三态分账",
        retry: () => ui.loadBidCoverage(true)
      });
      return;
    }
    if (cv.status === "error" || !cv.data) {
      panel.innerHTML =
        '<div class="bid-cov"><div class="view-state" data-kind="error"><div class="view-state-title">覆盖报告读取失败</div><div>'
        + esc(cv.error || "无数据")
        + '</div><div><button class="btn" data-cov-retry>重试</button></div></div></div>';
      const retry = panel.querySelector("[data-cov-retry]");
      if (retry) retry.addEventListener("click", () => ui.loadBidCoverage(true));
      return;
    }
    const d = cv.data;
    const s = d.summary || {};
    const cov = d.coverage || {};
    const star = d.star || {};
    const st = star.total || {};
    const files = (cov.files || []).slice();
    const starByName = {};
    (star.files || []).forEach((sf) => {
      starByName[sf.file_id] = sf;
    });
    const total = Number(s.total_blocks || 0);
    const judged = Number(s.judged_blocks || 0);
    const excluded = Number(s.excluded_blocks || 0);
    const unjudged = Number(s.unjudged_blocks || 0);
    const share = total ? Math.round(((judged + excluded) / total) * 1000) / 10 : 0;
    const truth = Number(st.star_truth || 0);
    const capt = Number(st.star_captured || 0);
    const miss = Number(st.star_missing || 0);

    // ---- 总览卡：三色环（conic-gradient 饼图，零依赖）+ 图例计数 + 分账条
    const pJ = total ? (judged / total) * 100 : 0;
    const pE = total ? (excluded / total) * 100 : 0;
    const donut =
      "conic-gradient(var(--ok) 0 " + pJ + "%, var(--fg-soft) " + pJ + "% " + (pJ + pE) +
      "%, var(--danger) " + (pJ + pE) + "% 100%)";
    let html =
      '<div class="bid-cov">'
      + '<div class="bid-cov-cards">'
      + '<div class="bid-cov-card">'
      + '<div class="bid-cov-card-title">块覆盖（#244 三态分账）</div>'
      + '<div class="bid-cov-donut-row">'
      + '<div class="bid-cov-donut"' + (total ? ' style="background:' + donut + '"' : "") + '><span class="bid-cov-donut-v">' + share + '%</span><span class="bid-cov-donut-k">已处置</span></div>'
      + '<div class="bid-cov-legend">'
      + '<div class="bid-cov-lg"><span class="bid-cov-dot ok"></span>已判定 <b>' + fmtChars(judged) + "</b><span>" + (total ? bidCovPct(judged, total) : 0) + "%</span></div>"
      + '<div class="bid-cov-lg"><span class="bid-cov-dot ex"></span>已排除 <b>' + fmtChars(excluded) + "</b><span>" + (total ? bidCovPct(excluded, total) : 0) + "%</span></div>"
      + '<div class="bid-cov-lg"><span class="bid-cov-dot un"></span>未判定 <b>' + fmtChars(unjudged) + "</b><span>" + (total ? bidCovPct(unjudged, total) : 0) + "%</span></div>"
      + '<div class="bid-cov-lg total">共 ' + fmtChars(total) + " 块 · 未判定区间 " + fmtChars(Number(s.uncovered_range_count || 0)) + " 段</div>"
      + "</div></div>"
      + '<div class="bid-cov-bar"><span class="ok" style="width:' + pJ + '%"></span><span class="ex" style="width:' + pE + '%"></span><span class="un" style="width:' + (total ? 100 - pJ - pE : 0) + '%"></span></div>'
      + "</div>"
      // ---- ★条款覆盖卡（#285：真值★已捕获/真值★——「一条不响应即响应无效」）
      + '<div class="bid-cov-card">'
      + '<div class="bid-cov-card-title">★条款覆盖（#285 漏标检测）</div>'
      + (truth > 0
        ? '<div class="bid-cov-star-row"><span class="bid-cov-star-big">' + fmtChars(capt) + '<i>/' + fmtChars(truth) + "</i></span>"
          + '<div class="bid-cov-star-meta">'
          + '<div class="bid-cov-lg"><span class="bid-cov-dot ok"></span>已捕获 <b>' + fmtChars(capt) + "</b></div>"
          + (miss > 0 ? '<div class="bid-cov-lg"><span class="bid-cov-dot un"></span>漏标 <b>' + fmtChars(miss) + "</b>（补标后重跑抽取生效）</div>" : '<div class="bid-cov-lg"><span class="bid-cov-dot ok"></span>无漏标</div>')
          + '<div class="bid-cov-lg total">样板句★ ' + fmtChars(Number(st.declarations || 0)) + " 处（声明不计条款）</div>"
          + "</div></div>"
        : '<div class="view-state"><div class="view-state-title">无★实质性条款</div><div>招标文件字面无真值★——无漏标检测面</div></div>')
      + "</div>"
      + "</div>";

    // ---- 逐文件覆盖表（行展开：by_verdict 分账 + 未判定区间明细 + ★引导）
    if (!files.length) {
      html +=
        '<div class="view-state"><div class="view-state-title">尚无已导入文件</div><div>'
        + esc(cov.next || "MCP 管线 import_tender_files 之后，这里显示逐文件块覆盖")
        + "</div></div>";
    } else {
      const f = state.bid.cov;
      html +=
        '<div class="bid-cov-files"><div class="bid-cov-files-title">逐文件覆盖</div>'
        + '<div class="bid-cov-table-wrap"><table class="bid-cov-table"><thead><tr><th>文件</th><th>块数</th><th>已判定</th><th>已排除</th><th>未判定</th><th>★捕获/真值</th><th>状态</th></tr></thead><tbody>';
      for (const fl of files) {
        const fid = fl.file_id || "";
        const sf = starByName[fid] || {};
        const fname = sf.file_name || fid;
        const ft = Number(fl.total_blocks || 0);
        const fc = Number(fl.covered_blocks || 0);
        const fe = Number(fl.excluded_blocks || 0);
        const fu = Number(fl.unjudged_blocks || 0);
        const fj = fc - fe;
        const expanded = f.expandedFile === fid;
        const ranges = fl.uncovered_ranges || [];
        const rangeCount = Number(fl.uncovered_range_count || ranges.length || 0);
        const bv = fl.by_verdict || {};
        html +=
          '<tr class="bid-cov-row' + (fu > 0 ? " has-unjudged" : "") + (expanded ? " expanded" : "") + '" data-cov-file="' + esc(fid) + '">'
          + '<td class="bid-cov-fname" title="' + esc(fname) + '">' + esc(fname) + "</td>"
          + "<td>" + fmtChars(ft) + "</td>"
          + '<td><span class="ok">' + fmtChars(fj) + "</span></td>"
          + '<td><span class="ex">' + fmtChars(fe) + "</span></td>"
          + '<td><span class="' + (fu > 0 ? "un" : "ok") + '">' + fmtChars(fu) + "</span></td>"
          + "<td>" + (Number(sf.star_truth || 0) > 0 ? fmtChars(Number(sf.star_captured || 0)) + "/" + fmtChars(Number(sf.star_truth || 0)) : "—") + "</td>"
          + "<td>" + (ft === 0
            ? '<span class="bid-cov-badge" data-state="empty">无块</span>'
            : fl.complete
              ? '<span class="bid-cov-badge" data-state="ok">全覆盖</span>'
              : fu > 0
                ? '<span class="bid-cov-badge" data-state="un">有未判定</span>'
                : '<span class="bid-cov-badge" data-state="ok">已判完</span>') + "</td></tr>";
        if (expanded) {
          let detail =
            '<tr class="bid-cov-detail"><td colspan="7"><div class="bid-cov-d-grid">'
            + '<div class="bid-cov-d-block"><div class="bid-cov-d-k">判定分账（by_verdict）</div><div class="bid-cov-d-v">'
            + (Object.keys(bv).length
              ? Object.keys(bv).map((k) => '<span class="bid-cov-chip">' + esc(bidCovVerdictZh(k)) + " " + fmtChars(bv[k]) + "</span>").join("")
              : '<span class="dim">无标记——零标记文件走正则兜底（#219 既有路径）</span>')
            + "</div></div>"
            + '<div class="bid-cov-d-block"><div class="bid-cov-d-k">未判定区间（C 态——块号含两端）</div><div class="bid-cov-d-v">'
            + (rangeCount
              ? ranges.map((r) => '<span class="bid-cov-chip un">块 ' + fmtChars(r[0]) + "–" + fmtChars(r[1]) + "（" + fmtChars(Number(r[1]) - Number(r[0]) + 1) + " 块）</span>").join("")
                + (rangeCount > ranges.length ? '<span class="dim">…共 ' + fmtChars(rangeCount) + " 段，只显示前 " + ranges.length + " 段</span>" : "")
              : '<span class="dim">无——本文件无 C 态块</span>')
            + "</div></div>"
            + '<div class="bid-cov-d-block"><div class="bid-cov-d-k">★漏标引导（#285）</div><div class="bid-cov-d-v">'
            + (sf.next ? esc(sf.next) : "—") + "</div></div>"
            + "</div></td></tr>";
          html += detail;
        }
      }
      html += "</tbody></table></div></div>";
    }

    // ---- 建纲门提示（工具面 next 原样——单一真源）
    if (cov.next) {
      html += '<div class="bid-cov-next"' + (total > 0 && !cov.complete ? ' data-state="warn"' : ' data-state="ok"') + "><span>下一步</span>" + esc(cov.next) + "</div>";
    }
    html += "</div>";
    panel.innerHTML = html;

    // ---- 交互接线（重渲染后重挂——与批 A/B 同款就地绑定纪律）
    panel.querySelectorAll(".bid-cov-row").forEach((tr) =>
      tr.addEventListener("click", () => {
        const id = tr.dataset.covFile;
        state.bid.cov.expandedFile = state.bid.cov.expandedFile === id ? "" : id;
        renderBidCoveragePanel(host, panel);
      })
    );
  }
  // ============ #313 批 D 覆盖报告面板 END ============



  // ============ #54 大纲面板：收集 / 树渲染 / 跳转 / 滚动高亮 / 折叠 ============
  /** 从已渲染的 tab 面板收集标题（docx: pStyle→h1-h6；md: mdToHtml→h1-h6）。 */
  function collectOutline(tab) {
    if (!tab) return [];
    const pane = document.getElementById("pane-" + tab.id);
    if (!pane) return [];
    const heads = pane.querySelectorAll("h1,h2,h3,h4,h5,h6");
    const out = [];
    for (let i = 0; i < heads.length; i++) {
      const h = heads[i];
      const text = (h.textContent || "").trim();
      if (!text) continue;
      out.push({ level: Number(h.tagName[1]), text: text.slice(0, 120), el: h, id: "ol-" + tab.id + "-" + i });
    }
    return out;
  }
  /** tab 大纲的失效检测：元素脱离 DOM（重渲染/关闭）时重新收集。 */
  function outlineOf(tab) {
    if (!tab) return [];
    if (!tab.outline || tab.outline.some(function (o) { return o.el && !o.el.isConnected; })) {
      tab.outline = collectOutline(tab);
    }
    return tab.outline || [];
  }
  /** 大纲面板渲染（VSCode 风格树：层级缩进 / 折叠箭头 / active 高亮）。 */
  function renderOutlineView(body) {
    const tab = activeTab();
    body.innerHTML = "";
    if (!tab || tab.state !== "ready") {
      body.innerHTML = '<div class="outline-empty">' + (tab ? "\u6B63\u5728\u52A0\u8F7D " + esc(tab.name) + "\u2026" : "\u6253\u5F00\u6587\u4EF6\u540E\u663E\u793A\u5927\u7EB2") + "</div>";
      return;
    }
    if (tab.kind !== "docx" && tab.kind !== "md") {
      body.innerHTML = '<div class="outline-empty">' + esc(tab.name) + "<br>" + (tab.kind === "pdf" ? "PDF \u65E0\u7ED3\u6784\u5316\u5927\u7EB2\uFF0C\u8BF7\u770B\u9875\u9762\u7F29\u7565\u56FE" : "\u8BE5\u6587\u4EF6\u7C7B\u578B\u65E0\u5927\u7EB2") + "</div>";
      return;
    }
    const items = outlineOf(tab);
    if (!items.length) {
      body.innerHTML = '<div class="outline-empty">\u672A\u627E\u5230\u6807\u9898\uFF08\u6587\u6863\u672A\u4F7F\u7528 Heading \u6837\u5F0F\uFF09</div>';
      return;
    }
    const tree = document.createElement("div");
    tree.className = "outline-tree";
    tree.innerHTML = items.map(function (o, i) {
      const hasKids = i + 1 < items.length && items[i + 1].level > o.level;
      return '<div class="outline-item" data-i="' + i + '" data-level="' + o.level + '" style="--ol-indent:' + (o.level - 1) + '"' + (hasKids ? "" : " data-leaf='1'") + ">" +
        '<button class="outline-twisty" data-twisty="' + i + '" aria-label="\u6298\u53E0">' + (hasKids ? '<svg viewBox="0 0 16 16"><path d="m6 4 4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : "") + "</button>" +
        '<span class="outline-text">' + esc(o.text) + "</span></div>";
    }).join("");
    body.appendChild(tree);
    // 折叠状态：tab.meta.olCollapsed = { [idx]: true }
    if (!tab.meta.olCollapsed) tab.meta.olCollapsed = {};
    const applyCollapsed = function () {
      const rows = tree.querySelectorAll(".outline-item");
      let hidden = false;
      rows.forEach(function (row) {
        const i = Number(row.dataset.i);
        if (hidden) {
          if (Number(row.dataset.level) > hidden) { row.hidden = true; return; }
          hidden = false;
        }
        row.hidden = false;
        if (tab.meta.olCollapsed[i]) hidden = Number(row.dataset.level);
        const tw = row.querySelector(".outline-twisty");
        if (tw) tw.dataset.collapsed = tab.meta.olCollapsed[i] ? "1" : "";
      });
    };
    applyCollapsed();
    tree.addEventListener("click", function (e) {
      const tw = e.target.closest("[data-twisty]");
      if (tw) {
        const i = Number(tw.dataset.twisty);
        tab.meta.olCollapsed[i] = !tab.meta.olCollapsed[i];
        applyCollapsed();
        return;
      }
      const item = e.target.closest(".outline-item");
      if (!item) return;
      const o = items[Number(item.dataset.i)];
      if (o && o.el && o.el.isConnected) {
        o.el.scrollIntoView({ behavior: "smooth", block: "start" });
        markOutlineActive(tree, Number(item.dataset.i));
      }
    });
    // 滚动高亮：对当前面板的滚动容器挂一次性监听（节流 120ms）
    attachOutlineScroll(tab, tree, items);
    syncOutlineOnScroll(tab, tree, items);
  }
  /** 大纲滚动高亮：挂监听（每 tab 一次——切换面板时用新的 tree 引用）。 */
  function attachOutlineScroll(tab, tree, items) {
    if (tab.meta._olScrollBound === tree) return;
    tab.meta._olScrollBound = tree;
    const pane = document.getElementById("pane-" + tab.id);
    if (!pane) return;
    const sc = pane.querySelector(".view-scroll") || pane.querySelector(".mang-pdf-scroll") || pane;
    let timer = 0;
    const onScroll = function () {
      clearTimeout(timer);
      timer = setTimeout(function () { syncOutlineOnScroll(tab, tree, items); }, 120);
    };
    sc.addEventListener("scroll", onScroll, { passive: true });
  }
  /** 视口顶部最近的标题 → 大纲高亮。 */
  function syncOutlineOnScroll(tab, tree, items) {
    if (!tree.isConnected) return;
    const pane = document.getElementById("pane-" + tab.id);
    if (!pane) return;
    const sc = pane.querySelector(".view-scroll") || pane.querySelector(".mang-pdf-scroll") || pane;
    // 标题文档流位置 = 视口相对位置 + 滚动偏移（offsetTop 相对
    // .mang-docx-page（position:relative）——页内偏移跨页重叠，不可用）
    const base = sc.getBoundingClientRect().top;
    const top = (sc.scrollTop || 0) + 60;
    let cur = -1;
    for (let i = 0; i < items.length; i++) {
      const el = items[i].el;
      if (!el || !el.isConnected) continue;
      const pos = el.getBoundingClientRect().top - base + (sc.scrollTop || 0);
      if (pos <= top) cur = i; else break;
    }
    // 滚动位置在第一个标题之前（文档顶部/封面区）→ 高亮第一项
    if (cur === -1 && items.length && items[0].el && items[0].el.isConnected) cur = 0;
    markOutlineActive(tree, cur);
  }
  function markOutlineActive(tree, idx) {
    tree.querySelectorAll(".outline-item.active").forEach(function (r) { r.classList.remove("active"); });
    if (idx >= 0) {
      const row = tree.querySelector('.outline-item[data-i="' + idx + '"]');
      if (row) {
        row.classList.add("active");
        if (row.hidden) return;
        const r = row.getBoundingClientRect();
        const t = tree.getBoundingClientRect();
        if (r.top < t.top || r.bottom > t.bottom) row.scrollIntoView({ block: "nearest" });
      }
    }
  }
  /** #54 大纲面板激活时刷新（docx 异步 mount / tab 就绪 / 切换 tab 后调用）。 */
  function refreshOutlineIfVisible() {
    if (settings.sidebarActive === "outline" && settings.sidebarVisible) renderSidebar();
  }
  /** #54 页码跳转：docx 滚到 .mang-docx-page[data-page=N]；pdf 走 goToPage API。 */
  function gotoPageOfActiveTab(n) {
    const tab = activeTab();
    if (!tab || tab.state !== "ready") return;
    const target = Math.max(1, Math.floor(Number(n) || 1));
    if (tab.kind === "pdf") {
      if (tab.meta.view && typeof tab.meta.view.goToPage === "function") tab.meta.view.goToPage(target);
      return;
    }
    if (tab.kind !== "docx") return;
    const pane = document.getElementById("pane-" + tab.id);
    if (!pane) return;
    const page = pane.querySelector('.mang-docx-page[data-page="' + target + '"]');
    if (page) page.scrollIntoView({ behavior: "smooth", block: "start" });
    else ui.toast("info", "\u9875\u7801\u8D85\u51FA\u8303\u56F4\uFF08\u6709\u6548\u9875\u89C1\u72B6\u6001\u680F\uFF09");
  }
  function renderHistoryViewIfVisible() {
    if (settings.sidebarActive === "history") renderSidebar();
    if (!state.tabs.length) renderEmpty();
  }
  function nodeKind(n) {
    return n.kind === "dir" ? "dir" : kindOf(n.name);
  }
  function absPathOf(rel) {
    if (!rel) return rel;
    if (/^[a-zA-Z]:[\\/]/.test(rel) || rel.charAt(0) === "/") return rel;
    const root = (state.workspace || "").replace(/[\\/]+$/, "");
    if (!root) return rel;
    return root + "\\" + rel.replace(/^[\\/]+/, "");
  }
  function fileIcon(n) {
    return ICON[KIND_ICON[nodeKind(n)] || "text"];
  }
  function childNodes(n) {
    if (!n) return [];
    if (Array.isArray(n.children)) return n.children;
    if (Array.isArray(n.nodes)) return n.nodes;
    if (Array.isArray(n.items)) return n.items;
    return [];
  }
  function childCount(n) {
    if (!n) return 0;
    if (typeof n.children === "number") return n.children;
    if (typeof n.childrenCount === "number") return n.childrenCount;
    if (Array.isArray(n.nodes)) return n.nodes.length;
    if (Array.isArray(n.children)) return n.children.length;
    return 0;
  }
  function renderTreeNodes(nodes, depth, out) {
    for (const n of nodes) {
      const rel = n.rel;
      const isDir = n.kind === "dir";
      const expanded = isDir && state.expanded.has(rel);
      const pad = 6 + depth * 12;
      const kids = isDir ? childNodes(n) : [];
      out.push(
        '<div class="tree-row" role="treeitem" data-rel="' + esc(rel) + '" data-kind="' + esc(nodeKind(n)) + '" data-depth="' + depth + '" data-selected="' + String(state.selectedRel === rel) + '" data-expanded="' + String(expanded) + '" tabindex="-1" title="' + esc(n.name) + '" aria-expanded="' + (isDir ? String(expanded) : "false") + '" style="padding-left:' + pad + 'px">' + (isDir ? '<span class="tree-caret">' + ICON.chevron + "</span>" : '<span class="tree-caret"></span>') + '<span class="tree-icon">' + (isDir ? expanded ? ICON.folderOpen : ICON.folder : fileIcon(n)) + '</span><span class="tree-label">' + esc(n.name) + "</span>" + (isDir && childCount(n) ? '<span class="tree-meta">' + childCount(n) + "</span>" : "") + "</div>"
      );
      if (isDir && expanded) renderTreeNodes(kids, depth + 1, out);
    }
    return out;
  }
  function renderFilesView(host) {
    if (state.treeBusy && !state.tree) {
      host.innerHTML = '<div class="panel-empty">\u6B63\u5728\u8BFB\u53D6\u5DE5\u4F5C\u533A\u2026</div>';
      return;
    }
    if (state.treeError) {
      host.innerHTML = '<div class="panel-empty">' + esc(state.treeError) + '<br><button class="btn" data-act="refresh">\u91CD\u8BD5</button></div>';
      bindFilesActions(host);
      return;
    }
    if (!state.tree || !Array.isArray(state.tree.nodes)) {
      host.innerHTML = '<div class="panel-empty">\u5C1A\u672A\u6253\u5F00\u5DE5\u4F5C\u533A<br>\u7528 <b>mang-app.exe --workspace D:\\\u9879\u76EE</b> \u542F\u52A8\uFF0C\u6216\u70B9\u51FB\u53F3\u4E0A\u89D2\u6253\u5F00\u6587\u4EF6\u5939</div>';
      bindFilesActions(host);
      return;
    }
    const rows = renderTreeNodes(state.tree.nodes, 0, []);
    if (!rows.length) {
      host.innerHTML = '<div class="panel-empty">\u5DE5\u4F5C\u533A\u662F\u7A7A\u7684</div>';
      return;
    }
    host.innerHTML = '<div class="tree" role="tree">' + rows.join("") + "</div>";
    const treeEl = host.querySelector(".tree");
    treeEl.addEventListener("click", (e) => {
      const row = e.target.closest("[data-rel]");
      if (!row) return;
      const rel = row.dataset.rel;
      const isDir = row.dataset.kind === "dir";
      state.selectedRel = rel;
      if (isDir) {
        if (state.expanded.has(rel)) state.expanded.delete(rel);
        else state.expanded.add(rel);
      }
      markTreeSelection(host);
      if (!isDir) ui.openPath(absPathOf(rel));
      else renderFilesView(host);
    });
    treeEl.addEventListener("dblclick", (e) => {
      const row = e.target.closest("[data-rel]");
      if (!row || row.dataset.kind !== "dir") return;
      const rel = row.dataset.rel;
      state.expanded.add(rel);
      renderFilesView(host);
    });
    treeEl.addEventListener("contextmenu", (e) => {
      const row = e.target.closest("[data-rel]");
      if (!row) return;
      e.preventDefault();
      state.selectedRel = row.dataset.rel;
      markTreeSelection(host);
      ui.fileContextMenu(absPathOf(row.dataset.rel), e.clientX, e.clientY);
    });
  }
  function markTreeSelection(host) {
    Array.prototype.forEach.call(host.querySelectorAll("[data-rel]"), (r) => {
      r.dataset.selected = String(r.dataset.rel === state.selectedRel);
    });
  }
  function bindFilesActions(host) {
    const btn = host.querySelector('[data-act="refresh"]');
    if (btn) btn.addEventListener("click", () => ui.refreshTree());
  }

  // ============ #42 阶段 7：版本快照（自动 30s 检查 + 改动面板 + 预览/回滚） ============
  /** 只有文本文件入快照（issue #42 §八：源头是 md，二进制不做） */
  function snapshotablePath(p) {
    return /\.(md|markdown|txt)$/i.test(p || "");
  }
  /** 绝对路径 → 工作区 rel（history.list 的 file 字段是 rel、正斜杠） */
  function relOfPath(p) {
    const ws = state.workspace || "";
    if (ws) {
      const np = String(p).replace(/\\/g, "/");
      const nw = ws.replace(/\\/g, "/").replace(/\/+$/, "") + "/";
      if (np.toLowerCase().startsWith(nw.toLowerCase())) return np.slice(nw.length);
    }
    return String(p).replace(/\\/g, "/");
  }

  // ============ #42 阶段 8：来源标注浮层（覆盖层，绝不修改文件） ============
  /** 给已渲染的 tab 挂标注层：.view-scroll 内绝对定位（随内容滚动），
   *  角标锚在目标块右下角；点角标开来源详情浮层（认校验三态可点）。 */
  function attachAnnotations(tab) {
    const pane = document.getElementById("pane-" + tab.id);
    if (!pane) return;
    detachAnnotations(pane);
    if (tab.kind !== "md" && tab.kind !== "docx") return;
    const sc = pane.querySelector(".view-scroll");
    if (!sc) return;
    const rel = relOfPath(tab.path || "");
    ipc("annotations.load", { path: rel }, 15e3).then((r) => {
      if (!r || !r.present || !Array.isArray(r.items) || !r.items.length) return;
      if (document.getElementById("pane-" + tab.id) !== pane) return; // tab 已关
      const layer = document.createElement("div");
      layer.className = "anno-layer";
      layer.dataset.for = tab.id;
      sc.appendChild(layer);
      const items = r.items;
      const render = () => {
        layer.innerHTML = "";
        layer.style.height = sc.scrollHeight + "px";
        const scRect = sc.getBoundingClientRect();
        let placed = 0;
        items.forEach((it, idx) => {
          const blk = sc.querySelector('[data-block-id="' + esc(it.block || "") + '"]');
          if (!blk) return;
          const bRect = blk.getBoundingClientRect();
          const mk = document.createElement("button");
          mk.className = "anno-mark st-" + (it.status || "pending");
          mk.textContent = String(idx + 1);
          const quote = (it.quote || "").slice(0, 60);
          mk.title = quote + "\uFF08\u70B9\u770B\u6765\u6E90\uFF09";
          // 相对滚动内容定位（层原点 = 内容顶部）
          mk.style.top = (bRect.bottom - scRect.top + sc.scrollTop - 11) + "px";
          mk.style.left = Math.min(bRect.right - scRect.left + sc.scrollLeft + 4, sc.clientWidth - 24) + "px";
          mk.addEventListener("click", (e) => {
            e.stopPropagation();
            showAnnotationDetail(tab, items, idx);
          });
          layer.appendChild(mk);
          placed++;
        });
        if (placed) {
          ui.setStatus({ annotations: "\u6807\u6CE8 " + placed + " \u6761" });
        }
      };
      render();
      // 内容尺寸变化（字体加载/图片展开/窗口缩放）重摆角标
      const ro = new ResizeObserver(() => render());
      ro.observe(sc.firstElementChild || sc);
      layer.__ro = ro;
    }).catch(() => {
      /* 标注加载失败不打扰正文（下次切回重试） */
    });
  }

  function detachAnnotations(pane) {
    const old = pane.querySelector(".anno-layer");
    if (old) {
      if (old.__ro) old.__ro.disconnect();
      old.remove();
      ui.setStatus({ annotations: "" });
    }
  }

  /** 来源详情浮层：认校验三态（✅已确认 / ⚠待确认 / ❌不符）+ 来源引用 */
  function showAnnotationDetail(tab, items, idx) {
    closeAnnotationDetail();
    const it = items[idx];
    if (!it) return;
    const src = it.source || {};
    const ov = document.createElement("div");
    ov.id = "anno-detail";
    const srcLine = [src.file, src.page ? "P" + src.page : "", src.section ? "\u00A7" + src.section : ""].filter(Boolean).join(" \u00B7 ");
    const st = it.status || "pending";
    const btn = (s, label) =>
      '<button class="anno-status" data-status="' + s + '"' + (st === s ? ' aria-pressed="true"' : "") + ">" + label + "</button>";
    ov.innerHTML =
      '<div class="anno-box">' +
      '<div class="anno-head"><span class="anno-title">\u6765\u6E90 [' + (idx + 1) + ']</span>' +
      '<button class="anno-close" title="\u5173\u95ED (Esc)">\u00D7</button></div>' +
      '<div class="anno-src">' + esc(srcLine || "\u672A\u77E5\u6765\u6E90") + "</div>" +
      (src.quote ? '<div class="anno-quote">\u300C' + esc(src.quote) + "\u300D</div>" : "") +
      (it.quote ? '<div class="anno-where">\u6B63\u6587\u4F4D\u7F6E\uFF1A' + esc(it.quote.slice(0, 80)) + "</div>" : "") +
      (it.note ? '<div class="anno-note">' + esc(it.note) + "</div>" : "") +
      '<div class="anno-verify"><span>\u8BA4\u6821\u9A8C</span>' +
      btn("confirmed", "\u2705 \u5DF2\u786E\u8BA4") +
      btn("pending", "\u26A0\uFE0F \u5F85\u786E\u8BA4") +
      btn("rejected", "\u274C \u4E0D\u7B26") +
      "</div>" +
      '<div class="anno-hint">\u6807\u6CE8\u5B58\u5728\u8FB9\u8F66\uFF08.mang/annotations\uFF09\uFF0C\u7EDD\u4E0D\u4FEE\u6539\u6587\u4EF6\u5185\u5BB9</div>' +
      "</div>";
    ov.addEventListener("mousedown", (e) => {
      if (e.target === ov) closeAnnotationDetail();
    });
    ov.querySelector(".anno-close").addEventListener("click", closeAnnotationDetail);
    ov.querySelectorAll(".anno-status").forEach((b) => {
      b.addEventListener("click", () => {
        const status = b.dataset.status;
        ipc("annotations.setStatus", { path: relOfPath(tab.path || ""), id: it.id, status }, 15e3).then(() => {
          it.status = status;
          ov.querySelectorAll(".anno-status").forEach((x) => x.removeAttribute("aria-pressed"));
          b.setAttribute("aria-pressed", "true");
          const layer = document.getElementById("pane-" + tab.id)?.querySelector(".anno-layer");
          const marks = layer ? Array.from(layer.children) : [];
          const mk = marks[idx];
          if (mk) mk.className = "anno-mark st-" + status;
          ui.toast("ok", "\u5DF2\u6807\u8BB0\uFF1A" + (status === "confirmed" ? "\u5DF2\u786E\u8BA4" : status === "pending" ? "\u5F85\u786E\u8BA4" : "\u4E0D\u7B26"));
        }).catch((e2) => ui.toast("error", "\u4FDD\u5B58\u5931\u8D25\uFF1A" + (e2.message || e2)));
      });
    });
    document.body.appendChild(ov);
    const onKey = (e) => {
      if (e.key === "Escape") {
        closeAnnotationDetail();
        document.removeEventListener("keydown", onKey);
      }
    };
    document.addEventListener("keydown", onKey);
  }

  function closeAnnotationDetail() {
    const ov = document.getElementById("anno-detail");
    if (ov) ov.remove();
  }

  /** 30s 一档：打开的文本文件内容有变 → 壳侧存快照（无变化自动跳过） */
  function snapshotTick() {
    if (!state.bridge || state.bridge.mode !== "host") return;
    const seen = /* @__PURE__ */ new Set();
    const paths = [];
    for (const t of state.tabs) {
      if (t.state === "ready" && snapshotablePath(t.path) && !seen.has(t.path)) {
        seen.add(t.path);
        paths.push(t.path);
      }
    }
    if (!paths.length) return;
    ipc("snapshots.check", { paths }, 3e4).then((r) => {
      const saved = (r && r.saved) || [];
      if (saved.length) {
        ui.toast("info", "已存版本快照：" + saved.map((s) => baseName(s.file)).join("、"));
        if (settings.sidebarActive === "changes") ui.loadSnapshots(state.snapshots.file);
      }
    }).catch(() => {
      /* 快照失败不打扰（下一轮再试） */
    });
  }
  /** 载入某文件的快照列表进改动面板（file 为空 = 清空） */
  function loadSnapshotsInto(file) {
    state.snapshots.file = file || "";
    state.snapshots.status = file ? "loading" : "idle";
    state.snapshots.entries = [];
    state.snapshots.error = "";
    if (!file) {
      renderSidebar();
      return Promise.resolve();
    }
    return ipc("history.list", { path: file, limit: 100 }, 15e3).then((r) => {
      state.snapshots.entries = (r && r.items) || [];
      state.snapshots.status = "ready";
      renderSidebar();
    }).catch((e) => {
      state.snapshots.status = "error";
      state.snapshots.error = e.message || String(e);
      renderSidebar();
    });
  }
  /**
   * #42 阶段 9：md 层逐行 diff（类 git diff）。
   * 返回 [{t: '='|'-'|'+', a?, b?, text}]；t 是操作，text 取对应侧的行。
   * 公共前后缀裁剪后对中段做 LCS（Uint32 DP，超过 16M 格退化为整块替换）。
   */
  function diffLines(aText, bText) {
    const a = String(aText == null ? "" : aText).split("\n");
    const b = String(bText == null ? "" : bText).split("\n");
    let p = 0;
    while (p < a.length && p < b.length && a[p] === b[p]) p++;
    let s = 0;
    while (s < a.length - p && s < b.length - p && a[a.length - 1 - s] === b[b.length - 1 - s]) s++;
    const am = a.slice(p, a.length - s);
    const bm = b.slice(p, b.length - s);
    const ops = [];
    for (let i = 0; i < p; i++) ops.push({ t: "=", text: a[i] });
    if (am.length * bm.length > 16e6) {
      // 超大变更块：不做精细对齐，诚实整块替换（防卡 UI）
      for (const line of am) ops.push({ t: "-", text: line });
      for (const line of bm) ops.push({ t: "+", text: line });
    } else if (am.length || bm.length) {
      const n = am.length, m = bm.length;
      const w = m + 1;
      const dp = new Uint32Array((n + 1) * (m + 1));
      for (let i = n - 1; i >= 0; i--) {
        for (let j = m - 1; j >= 0; j--) {
          dp[i * w + j] = am[i] === bm[j]
            ? dp[(i + 1) * w + (j + 1)] + 1
            : Math.max(dp[(i + 1) * w + j], dp[i * w + (j + 1)]);
        }
      }
      let i = 0, j = 0;
      while (i < n && j < m) {
        if (am[i] === bm[j]) {
          ops.push({ t: "=", text: am[i] });
          i++; j++;
        } else if (dp[(i + 1) * w + j] >= dp[i * w + (j + 1)]) {
          ops.push({ t: "-", text: am[i] });
          i++;
        } else {
          ops.push({ t: "+", text: bm[j] });
          j++;
        }
      }
      while (i < n) ops.push({ t: "-", text: am[i++] });
      while (j < m) ops.push({ t: "+", text: bm[j++] });
    }
    for (let k = a.length - s; k < a.length; k++) ops.push({ t: "=", text: a[k] });
    return ops;
  }

  /** diff 操作流 → git 风格 HTML（上下文 3 行，中间折叠「⋯ N 行未变」） */
  function renderDiffHtml(ops) {
    const CTX = 3;
    const keep = new Array(ops.length).fill(false);
    for (let i = 0; i < ops.length; i++) {
      if (ops[i].t !== "=") {
        for (let k = Math.max(0, i - CTX); k <= Math.min(ops.length - 1, i + CTX); k++) keep[k] = true;
      }
    }
    let add = 0, del = 0;
    for (const o of ops) {
      if (o.t === "+") add++;
      else if (o.t === "-") del++;
    }
    let html = '<div class="diff-summary">' +
      '<span class="diff-stat add">+' + add + " \u884C</span>" +
      '<span class="diff-stat del">\u2212' + del + " \u884C</span>" +
      (add + del === 0 ? '<span class="diff-stat same">\u65E0\u5DEE\u5F02</span>' : "") +
      "</div>";
    html += '<div class="diff-body">';
    let skip = 0;
    let started = false;
    for (let i = 0; i < ops.length; i++) {
      if (!keep[i]) {
        skip++;
        continue;
      }
      if (skip > 0) {
        const label = started ? "\u22EF " + skip + " \u884C\u672A\u53D8" : "\u22EF \uFF08\u524D\u9762 " + skip + " \u884C\u672A\u53D8\uFF09";
        html += '<div class="diff-line gap">' + label + "</div>";
        skip = 0;
      }
      started = true;
      const o = ops[i];
      const cls = o.t === "=" ? "ctx" : o.t === "-" ? "del" : "add";
      const mark = o.t === "=" ? " " : o.t;
      html += '<div class="diff-line ' + cls + '"><span class="diff-mark">' + mark + '</span><span class="diff-text">' + (esc(o.text) || "\u200B") + "</span></div>";
    }
    if (skip > 0) html += '<div class="diff-line gap">\u22EF \uFF08\u540E\u9762 ' + skip + " \u884C\u672A\u53D8\uFF09</div>";
    html += "</div>";
    return html;
  }

  /** 预览某版本（浮层，绝不改文件）；#42 阶段 9：可切换 diff 视图 */
  function showSnapshotPreview(entry, siblings) {
    closeSnapshotPreview();
    ipc("snapshots.read", { file: entry.file, snapshot: entry.snapshot }, 15e3).then((r) => {
      const ov = document.createElement("div");
      ov.id = "snap-preview";
      const when = new Date(entry.ts).toLocaleString();
      const badge = entry.kind === "ai" ? "AI 存版本" : entry.kind === "manual" ? "手动存版" : "自动快照";
      const msg = entry.message ? " · " + esc(entry.message) : "";
      const canRoll = true;
      const sibs = Array.isArray(siblings) ? siblings : [];
      const prev = sibs.filter((x) => x.ts < entry.ts && x.snapshot).sort((x, y) => y.ts - x.ts)[0] || null;
      ov.innerHTML =
        '<div class="snap-box">' +
        '<div class="snap-head"><span class="snap-title">\u7248\u672C\u9884\u89C8 \xB7 ' + esc(baseName(entry.file)) + '</span>' +
        '<span class="snap-meta">' + esc(badge + " \xB7 " + when) + msg + '</span>' +
        '<button class="snap-diff" data-diff="cur" title="\u5FEB\u7167 vs \u5F53\u524D\u6587\u4EF6\uFF08\u56DE\u6EDA\u4F1A\u6539\u52A8\u4EC0\u4E48\uFF09">\u4E0E\u5F53\u524D\u5BF9\u6BD4</button>' +
        '<button class="snap-diff" data-diff="prev" title="\u4E0A\u4E00\u4EFD\u5FEB\u7167 vs \u672C\u4EFD\uFF08\u8FD9\u4E00\u7248\u6539\u4E86\u4EC0\u4E48\uFF09"' + (prev ? "" : " disabled") + ">\u4E0E\u4E0A\u4E00\u7248\u5BF9\u6BD4</button>" +
        '<button class="snap-close" title="\u5173\u95ED (Esc)">\u00D7</button></div>' +
        '<div class="snap-bodywrap"><pre class="snap-body">' + esc((r && r.content) || "(\u7A7A)") + "</pre></div>" +
        '<div class="snap-foot">' +
        (canRoll ? '<button class="btn snap-rollback" data-ts="' + entry.ts + '">回滚到此版本</button>' : "") +
        '<span class="snap-hint">回滚会先把当前内容自动备份成新快照（可再回滚回来）</span>' +
        "</div></div>";
      ov.addEventListener("mousedown", (e) => {
        if (e.target === ov) closeSnapshotPreview();
      });
      ov.querySelector(".snap-close").addEventListener("click", closeSnapshotPreview);
      // #42 阶段 9：diff 视图切换（再点同按钮 = 返回正文预览）
      const bodyWrap = ov.querySelector(".snap-bodywrap");
      const curBtn = ov.querySelector('[data-diff=cur]');
      const prevBtn = ov.querySelector('[data-diff=prev]');
      const setDiffMode = (mode) => {
        const active = ov.dataset.diffMode === mode;
        ov.dataset.diffMode = active ? "" : mode;
        curBtn.classList.toggle("on", !active && mode === "cur");
        prevBtn.classList.toggle("on", !active && mode === "prev");
        if (active) {
          bodyWrap.innerHTML = '<pre class="snap-body">' + esc((r && r.content) || "(\u7A7A)") + "</pre>";
          return;
        }
        bodyWrap.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>\u6B63\u5728\u5BF9\u6BD4\u2026</div></div>';
        const other = mode === "cur"
          ? ipc("fs.read", { path: entry.file }, 15e3).then((x) => (x && x.text) || "")
          : prev
            ? ipc("snapshots.read", { file: prev.file, snapshot: prev.snapshot }, 15e3).then((x) => (x && x.content) || "")
            : Promise.resolve("");
        other.then((otherText) => {
          const ops = mode === "cur"
            ? diffLines((r && r.content) || "", otherText)
            : diffLines(prev ? (window.__snapPrevCache && window.__snapPrevCache) || "" : "", (r && r.content) || "");
          bodyWrap.innerHTML = '<div class="snap-body snap-body-diff">' + renderDiffHtml(ops) + "</div>";
        }).catch((e2) => {
          bodyWrap.innerHTML = '<div class="snap-body">\u5BF9\u6BD4\u5931\u8D25\uFF1A' + esc(e2.message || String(e2)) + "</div>";
        });
      };
      curBtn.addEventListener("click", () => setDiffMode("cur"));
      if (prevBtn) prevBtn.addEventListener("click", () => {
        if (prevBtn.disabled) return;
        // 与上一版对比需要上一版的正文：先取回来再进 diff（缓存避免重复拉）
        if (!window.__snapPrevCache) {
          ipc("snapshots.read", { file: prev.file, snapshot: prev.snapshot }, 15e3).then((x) => {
            window.__snapPrevCache = (x && x.content) || "";
            setDiffMode("prev");
          }).catch(() => setDiffMode("prev"));
        } else {
          setDiffMode("prev");
        }
      });
      const rb = ov.querySelector(".snap-rollback");
      if (rb) {
        rb.addEventListener("click", () => {
          if (rb.dataset.confirm !== "1") {
            rb.dataset.confirm = "1";
            rb.textContent = "确认回滚？（当前内容会先备份）";
            return;
          }
          rb.disabled = true;
          rb.textContent = "正在回滚…";
          ipc("snapshots.rollback", { file: entry.file, snapshot: entry.snapshot }, 3e4).then(() => {
            closeSnapshotPreview();
            ui.toast("ok", "已回滚：" + baseName(entry.file));
            for (const t of state.tabs) {
              if (t.path && (t.path === entry.file || relOfPath(t.path) === entry.file)) {
                ui.loadTab(t);
                break;
              }
            }
            ui.loadSnapshots(entry.file);
          }).catch((e2) => {
            rb.disabled = false;
            rb.textContent = "回滚到此版本";
            delete rb.dataset.confirm;
            ui.toast("error", "回滚失败：" + (e2.message || e2));
          });
        });
      }
      document.body.appendChild(ov);
      const onKey = (e) => {
        if (e.key === "Escape") {
          closeSnapshotPreview();
          document.removeEventListener("keydown", onKey);
        }
      };
      document.addEventListener("keydown", onKey);
    }).catch((e) => ui.toast("error", "读不到该快照：" + (e.message || e)));
  }
  function closeSnapshotPreview() {
    const ov = document.getElementById("snap-preview");
    if (ov) ov.remove();
    window.__snapPrevCache = null; // 上一版正文缓存随浮层失效
  }
  function renderHistoryView(host) {
    if (!state.recent.length) {
      host.innerHTML = '<div class="panel-empty">\u8FD8\u6CA1\u6709\u6253\u5F00\u8FC7\u6587\u4EF6<br>\u6253\u5F00\u7684\u6587\u4EF6\u4F1A\u51FA\u73B0\u5728\u8FD9\u91CC</div>';
      return;
    }
    host.innerHTML = state.recent.map((r) => {
      const kind = kindOf(r.path || r.name);
      return '<div class="list-item" data-path="' + esc(r.path) + '" title="' + esc(r.path) + '"><span class="tree-icon" style="width:16px;height:16px">' + ICON[KIND_ICON[kind] || "text"] + '</span><span class="list-main"><span class="list-title">' + esc(r.name || baseName(r.path)) + '</span><span class="list-sub">' + esc(dirName(r.path)) + '</span></span><span class="list-time">' + esc(timeAgo(r.openedAt)) + "</span></div>";
    }).join("");
    host.addEventListener("click", (e) => {
      const it = e.target.closest("[data-path]");
      if (it) ui.openPath(it.dataset.path);
    });
  }
  function renderChangesView(host) {
    const g = state.git;
    let html = "";
    // ── 版本快照段（#42 阶段 7）：独立于 git，当前文件是文本才显示 ──
    const tab = activeTab();
    const snapFile = state.snapshots.file || (tab && snapshotablePath(tab.path) ? relOfPath(tab.path) : "");
    if (snapFile) {
      const entries = state.snapshots.file === snapFile ? state.snapshots.entries : [];
      html += '<div class="panel-section">\u7248\u672C\u5FEB\u7167 \xB7 ' + esc(baseName(snapFile)) +
        (state.snapshots.file !== snapFile ? " \xB7 \u52A0\u8F7D\u4E2D" : entries.length ? " \xB7 " + entries.length + " \u4EFD" : "") + "</div>";
      if (state.snapshots.file !== snapFile) {
        setTimeout(() => ui.loadSnapshots(snapFile), 0);
      } else if (state.snapshots.status === "loading") {
        html += '<div class="panel-empty" style="padding:10px 14px">\u6B63\u5728\u8BFB\u53D6\u5FEB\u7167\u5217\u8868\u2026</div>';
      } else if (state.snapshots.status === "error") {
        html += '<div class="panel-empty" style="padding:10px 14px">' + esc(state.snapshots.error || "\u8BFB\u53D6\u5931\u8D25") + "</div>";
      } else if (!entries.length) {
        html += '<div class="panel-empty" style="padding:10px 14px">\u8FD8\u6CA1\u6709\u5FEB\u7167\uFF08\u6253\u5F00\u540E\u6BCF 30 \u79D2\u81EA\u52A8\u68C0\u67E5\u4E00\u6B21\uFF09</div>';
      } else {
        html += entries.map((e) => {
          const badge = e.kind === "ai" ? '<span class="snap-badge" data-kind="ai">AI</span>' : e.kind === "manual" ? '<span class="snap-badge" data-kind="manual">\u624B\u52A8</span>' : '<span class="snap-badge" data-kind="auto">\u81EA\u52A8</span>';
          return '<div class="list-item snap-item" data-snap="' + esc(String(e.ts)) + '" title="' + esc((e.message || "") + " " + new Date(e.ts).toLocaleString()) + '">' +
            badge +
            '<span class="list-main"><span class="list-title">' + esc(e.message || new Date(e.ts).toLocaleTimeString()) + '</span><span class="list-sub">' + esc(timeAgo(e.ts)) + "</span></span>" +
            '<button class="snap-save-now" data-act="save-version" title="\u7ACB\u5373\u5B58\u4E00\u4EFD\u5FEB\u7167">\u{1F4BE}</button>' +
            "</div>";
        }).join("");
      }
    }
    if (g.status === "loading") {
      host.innerHTML = html + '<div class="panel-empty">\u6B63\u5728\u8BFB\u53D6 git \u72B6\u6001\u2026</div>';
      bindSnapItems(host);
      return;
    }
    if (!g.available) {
      host.innerHTML = html + '<div class="panel-empty">' + esc(g.error || "\u672A\u63A5\u5165 git") + '<br><button class="btn" data-act="git-retry">\u91CD\u8BD5</button></div>';
      bindPanelActions(host);
      bindSnapItems(host);
      return;
    }
    const commits = g.log.slice(0, 12);
    html += '<div class="panel-section">\u5DE5\u4F5C\u533A\u6539\u52A8 \xB7 ' + g.items.length + " \u9879</div>";
    if (!g.items.length) {
      html += '<div class="panel-empty" style="padding:10px 14px">\u6CA1\u6709\u672A\u63D0\u4EA4\u7684\u6539\u52A8</div>';
    } else {
      html += g.items.map((c) => '<div class="list-item" data-git-path="' + esc(c.path) + '" title="' + esc(c.path) + '"><span class="git-code" data-state="' + esc(c.state) + '">' + esc(c.code || "\xB7") + '</span><span class="list-main"><span class="list-title">' + esc(baseName(c.path)) + '</span><span class="list-sub">' + esc(dirName(c.path)) + "</span></span></div>").join("");
    }
    html += '<div class="panel-section" data-branch="1">\u6700\u8FD1\u63D0\u4EA4' + (g.branch ? " \xB7 " + esc(g.branch) : "") + "</div>";
    if (!commits.length) {
      html += '<div class="panel-empty" style="padding:10px 14px">\u8FD8\u6CA1\u6709\u63D0\u4EA4\u8BB0\u5F55</div>';
    } else {
      html += commits.map((c) => '<div class="list-item" data-commit="' + esc(c.hash) + '" title="' + esc(c.hash + "  " + (c.author || "")) + '"><span class="list-main"><span class="list-title">' + esc(c.subject) + '</span><span class="list-sub">' + esc((c.author || "") + " \xB7 " + c.short) + '</span></span><span class="list-time">' + esc(timeAgo(c.ts)) + "</span></div>").join("");
    }
    host.innerHTML = html;
    bindPanelActions(host);
    bindSnapItems(host);
  }
  /** 快照条目事件：点条目 → 预览；💾 → 立即存一版 */
  function bindSnapItems(host) {
    host.querySelectorAll(".snap-item").forEach((el) => {
      el.addEventListener("click", (e) => {
        if (e.target.closest("[data-act=save-version]")) return;
        const ts = Number(el.dataset.snap);
        const entry = state.snapshots.entries.find((x) => x.ts === ts);
        if (entry) showSnapshotPreview(entry, state.snapshots.entries);
      });
    });
    host.querySelectorAll("[data-act=save-version]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const file = state.snapshots.file;
        if (!file) return;
        btn.disabled = true;
        ipc("snapshots.save", { path: file }, 2e4).then(() => {
          ui.toast("ok", "已存版本快照");
          ui.loadSnapshots(file);
        }).catch((err) => {
          btn.disabled = false;
          ui.toast("error", "存快照失败：" + (err.message || err));
        });
      });
    });
  }
  function bindPanelActions(host) {
    if (host.dataset.bound === "1") return;
    host.dataset.bound = "1";
    host.addEventListener("click", (e) => {
      const item = e.target.closest("[data-git-path]");
      if (item) return ui.openPath(absPathOf(item.dataset.gitPath));
      const commit = e.target.closest("[data-commit]");
      if (commit) return ui.showCommit(commit.dataset.commit);
      const act = e.target.closest("[data-act]");
      if (act && act.dataset.act === "git-retry") ui.loadGit();
    });
  }
  function renderStarView(host) {
    if (!state.favorites.length) {
      host.innerHTML = '<div class="panel-empty">\u6536\u85CF\u5939\u662F\u7A7A\u7684<br>\u5728\u6587\u4EF6\u6811\u91CC\u53F3\u952E\u53EF\u52A0\u5165\u6536\u85CF</div>';
      return;
    }
    host.innerHTML = state.favorites.map(
      (f) => '<div class="list-item" data-path="' + esc(f.path) + '"><span class="list-main"><span class="list-title">' + esc(baseName(f.path)) + '</span><span class="list-sub">' + esc(f.path) + "</span></span></div>"
    ).join("");
    host.addEventListener("click", (e) => {
      const it = e.target.closest("[data-path]");
      if (it) ui.openPath(it.dataset.path);
    });
  }
  // ============ #76 设置面板：诊断状态（MCP / LLM / 格式规范 / 关于） ============
  // DIAG 是设置视图的缓存态：renderSettingsView 先用缓存渲染（无则占位），
  // 再异步拉真实状态、视图仍在设置页时就地补齐。demo 模式拉不到就显示
  // 「演示模式」占位——不伪造宿主数据。
  var DIAG = { mcp: null, llm: null, fspec: null, llmTest: null, llmTestBusy: false, llmSaving: false };
  function diagIsHost() {
    return state.bridge && state.bridge.mode === "host";
  }
  function loadDiag() {
    if (!diagIsHost()) return;
    // 只拉还缺的项：三个响应到达时间不同，整组重拉会在渲染回调里互相触发重复请求
    if (!DIAG.mcp) {
      ipc("mcp.status", {}, 8e3).then((r) => {
        DIAG.mcp = r;
        if (settings.sidebarActive === "settings") renderSidebar();
      }).catch(() => {
        DIAG.mcp = { error: true };
        if (settings.sidebarActive === "settings") renderSidebar();
      });
    }
    if (!DIAG.llm) {
      ipc("llm.status", {}, 8e3).then((r) => {
        DIAG.llm = r;
        if (settings.sidebarActive === "settings") renderSidebar();
      }).catch(() => {
        DIAG.llm = { error: true };
        if (settings.sidebarActive === "settings") renderSidebar();
      });
    }
    if (!DIAG.fspec) {
      ipc("fspec.status", {}, 8e3).then((r) => {
        DIAG.fspec = r;
        if (settings.sidebarActive === "settings") renderSidebar();
      }).catch(() => {
        DIAG.fspec = { error: true };
        if (settings.sidebarActive === "settings") renderSidebar();
      });
    }
  }
  function dotHtml(ok, pending) {
    return '<span class="status-dot" data-state="' + (pending ? "busy" : ok ? "saved" : "error") + '"></span>';
  }
  function mcpGroupHtml() {
    const m = DIAG.mcp;
    if (!diagIsHost()) {
      return '<div class="settings-group"><div class="settings-group-title">MCP 连接</div><div class="setting-row"><div class="setting-label"><span class="setting-name">MCP 通道</span><span class="setting-desc">演示模式：无宿主，状态不可用</span></div></div></div>';
    }
    if (!m) return '<div class="settings-group"><div class="settings-group-title">MCP 连接</div><div class="setting-row"><span class="setting-desc">读取中…</span></div></div>';
    if (m.error) return '<div class="settings-group"><div class="settings-group-title">MCP 连接</div><div class="setting-row">' + dotHtml(false) + '<span class="setting-name">状态读取失败</span><button class="btn btn-sm" data-act="diag-refresh">重试</button></div></div>';
    const ready = !!m.ready;
    return '<div class="settings-group"><div class="settings-group-title">MCP 连接</div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">' + dotHtml(ready) + esc(m.server && m.server.indexOf("stdio") >= 0 ? "MCP 服务：已就绪（stdio）" : "MCP 服务：" + (ready ? "已就绪" : "未就绪")) + '</span><span class="setting-desc">通道 ' + esc(m.channel || "stdio") + " · 协议 " + esc(m.protocol || "JSONL over stdio") + '</span></div></div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">工具面：' + esc(String(m.tools || 0)) + ' 个（已实现 ' + esc(String(m.implemented || 0)) + '）</span><span class="setting-desc">由 MCP 客户端（AI 侧）拉起 bid-mcp-stdio 调用</span></div></div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">引擎直链</span><span class="setting-desc">' + esc(m.engine || "本壳直链 bidcore（方案 A）") + '</span></div></div>'
      + '<div class="setting-row"><button class="btn btn-sm" data-act="mcp-retest">测试连接</button><button class="btn btn-sm" data-act="reveal-mang">查看 .mang 目录</button></div></div>';
  }
  function llmGroupHtml() {
    const l = DIAG.llm;
    if (!diagIsHost()) {
      return '<div class="settings-group"><div class="settings-group-title">LLM 配置</div><div class="setting-row"><span class="setting-desc">演示模式：无宿主，配置不可用</span></div></div>';
    }
    if (!l) return '<div class="settings-group"><div class="settings-group-title">LLM 配置</div><div class="setting-row"><span class="setting-desc">读取中…</span></div></div>';
    const effOk = l.effective === "real";
    const eff = l.error ? "状态读取失败" : l.effective === "real" ? "real（真实生成）"
      : String(l.effective || "").indexOf("mock") === 0 ? "mock（降级）" : String(l.effective || "—");
    const usage = l.usage || {};
    const usageLine = (usage.calls || 0) > 0
      ? "本次工作区累计 " + usage.calls + " 次调用 · " + (usage.total_tokens || 0) + " tokens" + (usage.last_at ? " · 最近 " + timeAgo(usage.last_at * 1000) : "")
      : "尚无调用记录";
    const hint = l.api_key_hint ? "已存：" + esc(l.api_key_hint) : "未保存（留空 = 保持现状）";
    const html = ['<div class="settings-group"><div class="settings-group-title">LLM 配置</div>'];
    html.push('<div class="setting-row"><div class="setting-label"><span class="setting-name">' + dotHtml(l.error ? false : effOk) + '当前生效：' + esc(eff) + '</span><span class="setting-desc">' + (l.error ? "宿主命令不可用" : esc(l.resolve_error || usageLine)) + '</span></div></div>');
    if (!l.error) {
      html.push('<div class="setting-form">');
      html.push('<label class="setting-field"><span class="setting-name">API 地址（api_base）</span><input class="setting-input" id="llm-api-base" type="text" spellcheck="false" placeholder="https://api.deepseek.com/v1（OpenAI 兼容）" value="' + esc(l.api_base || "") + '"></label>');
      html.push('<label class="setting-field"><span class="setting-name">API Key' + (l.key_from_env ? '（环境变量已设）' : '') + '</span><input class="setting-input" id="llm-api-key" type="password" spellcheck="false" autocomplete="off" placeholder="' + hint + '"></label>');
      html.push('<label class="setting-field"><span class="setting-name">模型（model）</span><input class="setting-input" id="llm-model" type="text" spellcheck="false" list="llm-model-list" placeholder="deepseek-chat / glm-4 / gpt-4o" value="' + esc(l.model || "") + '"><datalist id="llm-model-list"><option value="deepseek-chat"></option><option value="glm-4"></option><option value="glm-4-plus"></option><option value="gpt-4o"></option></datalist></label>');
      html.push('<div class="setting-row setting-actions"><button class="btn btn-sm" data-act="llm-clear-key">清除已存 Key</button><span class="setting-desc">保存位置 ' + esc(l.file || ".mang/llm.json") + '</span></div>');
      html.push('<div class="setting-row setting-actions"><button class="btn btn-primary btn-sm" data-act="llm-save">保存配置</button><button class="btn btn-sm" data-act="llm-test">测试生成</button></div>');
      html.push('<div class="setting-test-result" id="llm-test-result" hidden></div>');
      html.push('</div>');
    }
    html.push('</div>');
    return html.join("");
  }
  function workspaceGroupHtml() {
    const snaps = [["15", "15 秒"], ["30", "30 秒"], ["60", "60 秒"], ["0", "关闭"]];
    return '<div class="settings-group"><div class="settings-group-title">工作区</div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">当前工作区</span><span class="setting-desc" style="word-break:break-all">' + esc(state.workspace || "未设置") + '</span></div></div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">运行模式</span><span class="setting-desc">' + esc(state.bridge && state.bridge.mode === "host" ? "桌面壳（Rust 壳 + WebView2）" : "演示模式（无宿主）") + '</span></div></div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">自动快照间隔</span><span class="setting-desc">打开中的文件内容变化时存版本</span></div><div class="seg" data-seg="snap">' + snaps.map(
        (s) => '<button data-snap-value="' + s[0] + '" aria-pressed="' + String(String(settings.snapshotIntervalSec) === s[0]) + '">' + s[1] + "</button>"
      ).join("") + '</div></div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">扫描排除目录</span><span class="setting-desc">.git / node_modules / target / .mang（文件树与快照固定规则）</span></div></div>'
      + '<div class="setting-row"><button class="btn" data-act="open-folder">更换工作区…</button></div></div>';
  }
  function fspecGroupHtml() {
    const f = DIAG.fspec;
    if (!diagIsHost()) {
      return '<div class="settings-group"><div class="settings-group-title">格式规范</div><div class="setting-row"><span class="setting-desc">演示模式：无宿主，规范不可用</span></div></div>';
    }
    if (!f) return '<div class="settings-group"><div class="settings-group-title">格式规范</div><div class="setting-row"><span class="setting-desc">读取中…</span></div></div>';
    if (f.error) return '<div class="settings-group"><div class="settings-group-title">格式规范</div><div class="setting-row">' + dotHtml(false) + '<span class="setting-name">状态读取失败</span><button class="btn btn-sm" data-act="diag-refresh">重试</button></div></div>';
    if (!f.present) {
      return '<div class="settings-group"><div class="settings-group-title">格式规范</div>'
        + '<div class="setting-row"><div class="setting-label">' + dotHtml(false) + '<span class="setting-name">尚未生成</span><span class="setting-desc">' + esc(f.hint || "由 MCP 管线从招标文件推导落盘") + '</span></div></div>'
        + '<div class="setting-row"><button class="btn btn-sm" data-act="fspec-refresh">重新检测</button></div></div>';
    }
    if (f.invalid) {
      return '<div class="settings-group"><div class="settings-group-title">格式规范</div>'
        + '<div class="setting-row"><div class="setting-label">' + dotHtml(false) + '<span class="setting-name">文件存在但解析失败</span><span class="setting-desc" style="word-break:break-all">' + esc(f.error || "") + '</span></div></div>'
        + '<div class="setting-row"><button class="btn btn-sm" data-act="fspec-refresh">重新检测</button></div></div>';
    }
    const mm = f.page && f.page.margin_mm || {};
    return '<div class="settings-group"><div class="settings-group-title">格式规范</div>'
      + '<div class="setting-row"><div class="setting-label">' + dotHtml(true) + '<span class="setting-name">' + esc(f.page && f.page.size || "?") + " · 边距 " + esc(String(mm.top || 0)) + "/" + esc(String(mm.bottom || 0)) + "/" + esc(String(mm.left || 0)) + "/" + esc(String(mm.right || 0)) + ' mm</span><span class="setting-desc">导出 docx 按此规格排版</span></div></div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">正文：' + esc(f.font && f.font.body || "?") + ' ' + esc(String(f.font && f.font.size_pt || "?")) + 'pt</span><span class="setting-desc">行距 ' + esc(String(f.font && f.font.line_height || "?")) + ' 倍 · 章节级覆盖 ' + esc(String(f.per_section_overrides || 0)) + ' 处</span></div></div>'
      + '<div class="setting-row"><button class="btn btn-sm" data-act="fspec-refresh">重新检测</button><button class="btn btn-sm" data-act="reveal-mang">查看来源文件</button></div></div>';
  }
  function aboutGroupHtml() {
    const info = state.appInfo || {};
    const build = info.build_epoch && Number(info.build_epoch) > 0
      ? new Date(Number(info.build_epoch) * 1000).toLocaleString() : "未知";
    return '<div class="settings-group"><div class="settings-group-title">关于</div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">mang ' + esc(info.version || "?") + '</span><span class="setting-desc">git ' + esc(info.git_rev || "unknown") + " · " + esc(build) + " · " + esc(info.profile || "?") + '</span></div></div>'
      + '<div class="setting-row"><div class="setting-label"><span class="setting-name">平台</span><span class="setting-desc">' + esc(info.platform || navigator.platform || "?") + ' · 协议 v' + esc(String(info.protocol || 1)) + '</span></div></div>'
      + '<div class="setting-row"><button class="btn btn-sm" data-act="copy-diag">复制诊断信息</button></div></div>';
  }
  function updateLlmTestResult() {
    const el = document.getElementById("llm-test-result");
    if (!el) return;
    const t = DIAG.llmTest;
    if (!t) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    el.setAttribute("data-ok", String(!!t.ok));
    el.innerHTML = '<span class="status-dot" data-state="' + (t.ok ? "saved" : "error") + '"></span><span>' + esc(t.message || (t.ok ? "成功" : "失败")) + (t.sample ? ' ——「' + esc(t.sample) + '」' : "") + '</span>';
  }
  function saveLlmConfig() {
    if (DIAG.llmSaving) return;
    const args = {};
    const base = document.getElementById("llm-api-base");
    const model = document.getElementById("llm-model");
    const key = document.getElementById("llm-api-key");
    if (base && base.value.trim() !== String(DIAG.llm && DIAG.llm.api_base || "")) args.apiBase = base.value.trim();
    if (model && model.value.trim() !== String(DIAG.llm && DIAG.llm.model || "")) args.model = model.value.trim();
    if (key && key.value.trim()) args.apiKey = key.value.trim();
    if (!Object.keys(args).length) {
      ui.toast("info", "没有改动需要保存");
      return;
    }
    DIAG.llmSaving = true;
    ipc("llm.save", args, 8e3).then((r) => {
      DIAG.llmSaving = false;
      ui.toast("ok", "已保存：" + (r.effective || ""));
      key && (key.value = "");
      return ipc("llm.status", {}, 8e3);
    }).then((r) => {
      DIAG.llm = r;
      if (settings.sidebarActive === "settings") renderSidebar();
    }).catch((e) => {
      DIAG.llmSaving = false;
      ui.toast("error", "保存失败：" + e.message);
    });
  }
  function runLlmTest() {
    if (DIAG.llmTestBusy) return;
    const el = document.getElementById("llm-test-result");
    if (el) {
      el.hidden = false;
      el.removeAttribute("data-ok");
      el.innerHTML = '<span class="status-dot" data-state="busy"></span><span>测试进行中（≤20 秒）…</span>';
    }
    DIAG.llmTestBusy = true;
    ipc("llm.test", {}, 5e3).then(() => {
      // 真实结果以 llm.test 事件送达（onBridgeEvent → updateLlmTestResult）
    }).catch((e) => {
      DIAG.llmTestBusy = false;
      DIAG.llmTest = { ok: false, message: "无法发起测试：" + e.message };
      updateLlmTestResult();
    });
  }
  function copyDiagnostics() {
    const info = state.appInfo || {};
    const m = DIAG.mcp || {}, l = DIAG.llm || {}, f = DIAG.fspec || {};
    const lines = [
      "mang 诊断信息",
      "版本: " + (info.version || "?") + " (git " + (info.git_rev || "unknown") + ", " + (info.profile || "?") + ")",
      "平台: " + (info.platform || navigator.platform || "?") + " · IPC 协议 v" + (info.protocol || 1),
      "工作区: " + (state.workspace || "未设置"),
      "运行模式: " + (diagIsHost() ? "桌面壳（Rust + WebView2）" : "演示模式"),
      "MCP: " + (m.error || !m.channel ? "读取失败" : m.channel + " · " + (m.tools || 0) + " 工具 · ready=" + String(!!m.ready)),
      "LLM: " + (l.error || !l.effective ? "读取失败" : l.effective + " · model=" + (l.model || "—") + " · key=" + (l.has_api_key ? "已配置" + (l.key_from_env ? "（env）" : "") : "未配置")),
      "LLM 用量: " + ((l.usage && l.usage.calls) || 0) + " 次 / " + ((l.usage && l.usage.total_tokens) || 0) + " tokens",
      "格式规范: " + (f.error ? "读取失败" : f.present ? (f.invalid ? "存在但无效" : (f.page && f.page.size) + " / " + (f.font && f.font.body)) : "未生成"),
      "生成时间: " + new Date().toLocaleString()
    ];
    const text = lines.join("\n");
    const done = () => ui.toast("ok", "诊断信息已复制到剪贴板");
    const fail = () => ui.toast("error", "复制失败，请手动选择状态栏文本");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fail);
    } else {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        done();
      } catch (e) {
        fail();
      }
    }
  }
  function renderSettingsView(host) {
    const themes = [
      ["system", "跟随系统"],
      ["light", "浅色"],
      ["dark", "深色"]
    ];
    host.innerHTML = '<div class="settings-group"><div class="settings-group-title">外观</div><div class="setting-row"><div class="setting-label"><span class="setting-name">主题</span><span class="setting-desc">界面配色</span></div><div class="seg" data-seg="theme">' + themes.map(
      (t) => '<button data-theme-value="' + t[0] + '" aria-pressed="' + String(settings.theme === t[0]) + '">' + t[1] + "</button>"
    ).join("") + '</div></div><div class="setting-row"><div class="setting-label"><span class="setting-name">状态栏</span><span class="setting-desc">显示底部状态栏</span></div><button class="switch" role="switch" data-switch="statusbarVisible" aria-checked="' + String(settings.statusbarVisible) + '"></button></div></div>'
      + '<div class="settings-group"><div class="settings-group-title">编辑器</div><div class="setting-row"><div class="setting-label"><span class="setting-name">自动换行</span><span class="setting-desc">文本与 Markdown 源码视图</span></div><button class="switch" role="switch" data-switch="wordWrap" aria-checked="' + String(settings.wordWrap) + '"></button></div><div class="setting-row"><div class="setting-label"><span class="setting-name">行号</span><span class="setting-desc">文本视图左侧行号</span></div><button class="switch" role="switch" data-switch="showLineNumbers" aria-checked="' + String(settings.showLineNumbers) + '"></button></div></div>'
      + mcpGroupHtml()
      + llmGroupHtml()
      + workspaceGroupHtml()
      + fspecGroupHtml()
      + aboutGroupHtml();
    Array.prototype.forEach.call(host.querySelectorAll("[data-theme-value]"), (b) => {
      b.addEventListener("click", () => ui.setTheme(b.dataset.themeValue));
    });
    Array.prototype.forEach.call(host.querySelectorAll("[data-switch]"), (b) => {
      b.addEventListener("click", () => {
        const key = b.dataset.switch;
        settings[key] = !settings[key];
        b.setAttribute("aria-checked", String(settings[key]));
        saveSettings();
        applyLayoutSettings();
        renderStatusBar();
        if (key === "wordWrap" || key === "showLineNumbers") ui.refreshActiveView();
      });
    });
    Array.prototype.forEach.call(host.querySelectorAll("[data-snap-value]"), (b) => {
      b.addEventListener("click", () => {
        settings.snapshotIntervalSec = Number(b.dataset.snapValue);
        saveSettings();
        armSnapshotTimer();
        Array.prototype.forEach.call(host.querySelectorAll("[data-snap-value]"), (x) => {
          x.setAttribute("aria-pressed", String(Number(x.dataset.snapValue) === settings.snapshotIntervalSec));
        });
      });
    });
    Array.prototype.forEach.call(host.querySelectorAll("[data-act]"), (b) => {
      b.addEventListener("click", () => {
        const act = b.dataset.act;
        if (act === "open-folder") ui.openFolderDialog();
        else if (act === "mcp-retest" || act === "diag-refresh") {
          DIAG.mcp = null;
          renderSidebar();
          loadDiag();
        } else if (act === "fspec-refresh") {
          DIAG.fspec = null;
          renderSidebar();
          if (diagIsHost()) ipc("fspec.status", {}, 8e3).then((r) => {
            DIAG.fspec = r;
            if (settings.sidebarActive === "settings") renderSidebar();
          }).catch(() => {
            DIAG.fspec = { error: true };
            if (settings.sidebarActive === "settings") renderSidebar();
          });
        } else if (act === "reveal-mang") {
          ipc("explorer.reveal", { path: ".mang" }, 8e3).catch((e) => ui.toast("error", "无法打开目录：" + e.message));
        } else if (act === "llm-save") saveLlmConfig();
        else if (act === "llm-test") runLlmTest();
        else if (act === "llm-clear-key") {
          ipc("llm.save", { clearApiKey: true }, 8e3).then(() => {
            ui.toast("ok", "已清除已存 API Key（auto 将降级 mock）");
            return ipc("llm.status", {}, 8e3);
          }).then((r) => {
            DIAG.llm = r;
            if (settings.sidebarActive === "settings") renderSidebar();
          }).catch((e) => ui.toast("error", "清除失败：" + e.message));
        } else if (act === "copy-diag") copyDiagnostics();
      });
    });
    updateLlmTestResult();
    if (diagIsHost() && (!DIAG.mcp || !DIAG.llm || !DIAG.fspec)) loadDiag();
  }
  function recentRowsHtml(limit) {
    if (!state.recent.length) return '<div class="recent-empty">\u8FD8\u6CA1\u6709\u6700\u8FD1\u6253\u5F00\u7684\u6587\u4EF6</div>';
    return state.recent.slice(0, limit).map((r) => {
      // #194：工作区条目（kind=dir）按目录图标呈现（kindOf 只认文件扩展名）
      const kind = r.kind === "dir" ? "dir" : kindOf(r.path || r.name);
      return '<button class="recent-item" data-path="' + esc(r.path) + '" title="' + esc(r.path) + '"><span class="tree-icon" style="width:16px;height:16px;color:var(--fg-muted)">' + ICON[KIND_ICON[kind] || "text"] + '</span><span class="recent-name">' + esc(r.name || baseName(r.path)) + '</span><span class="recent-path">' + esc(dirName(r.path)) + '</span><span class="recent-time">' + esc(timeAgo(r.openedAt)) + "</span></button>";
    }).join("");
  }
  function renderEmptyState(host) {
    host.innerHTML = '<div class="empty-card"><div><h1 class="empty-hero">mang \u2014 \u6807\u4E66\u5DE5\u4F5C\u53F0</h1><p class="empty-hero-sub">' + (state.workspace ? "\u5DE5\u4F5C\u533A\uFF1A" + esc(state.workspace) : "\u5C1A\u672A\u6253\u5F00\u5DE5\u4F5C\u533A") + '</p></div><div class="empty-section-title">\u6700\u8FD1\u6253\u5F00</div><div class="recent-list">' + recentRowsHtml(8) + '</div><div class="empty-actions"><button class="btn btn-primary" data-act="open-file">' + ICON.text + '\u6253\u5F00\u6587\u4EF6</button><button class="btn" data-act="open-folder">' + ICON.folder + '\u6253\u5F00\u5DE5\u4F5C\u533A</button></div><div class="empty-section-title">\u5FEB\u6377\u952E</div><div class="empty-hints"><span><span class="kbd">Ctrl+O</span></span><span>\u6253\u5F00\u6587\u4EF6</span><span><span class="kbd">Ctrl+B</span></span><span>\u663E\u793A / \u9690\u85CF\u4FA7\u680F</span><span><span class="kbd">Ctrl+W</span></span><span>\u5173\u95ED\u5F53\u524D Tab</span><span><span class="kbd">Ctrl+Tab</span></span><span>\u5207\u6362 Tab</span></div></div>';
  }
  function renderEmpty() {
    const host = $("#empty");
    const has = state.tabs.length > 0;
    host.hidden = has;
    if (!has) {
      renderEmptyState(host);
      bindEmptyActions(host);
    }
  }
  function bindEmptyActions(host) {
    if (host.dataset.bound === "1") return;
    host.dataset.bound = "1";
    host.addEventListener("click", (e) => {
      const item = e.target.closest(".recent-item[data-path]");
      if (item) {
        // #194：最近列表的工作区条目（kind=dir）→ 切工作区；文件照旧打开
        const rec = state.recent.find((r) => r.path === item.dataset.path);
        if (rec && rec.kind === "dir") ui.switchWorkspace(item.dataset.path);
        else ui.openPath(item.dataset.path);
        return;
      }
      const act = e.target.closest("[data-act]");
      if (!act) return;
      if (act.dataset.act === "open-file") ui.openFileDialog();
      else if (act.dataset.act === "open-folder") ui.openFolderDialog();
      else if (act.dataset.act === "retry-tree") ui.refreshTree();
    });
  }
  function renderTabs() {
    const host = $("#tabs");
    if (!state.tabs.length) {
      host.innerHTML = "";
      return;
    }
    host.innerHTML = state.tabs.map((t) => {
      const icon = ICON[KIND_ICON[t.kind] || "text"];
      const selected = t.id === state.activeTabId;
      return '<div class="tab" role="tab" data-id="' + esc(t.id) + '" data-kind="' + esc(t.kind) + '" data-dirty="' + String(!!t.dirty) + '" aria-selected="' + String(selected) + '" title="' + esc(t.path) + '" tabindex="' + (selected ? "0" : "-1") + '"><span class="tab-icon">' + icon + '</span><span class="tab-label">' + esc(t.name) + '</span><span class="tab-dot" aria-hidden="true"></span><button class="tab-close" title="\u5173\u95ED (Ctrl+W)" aria-label="\u5173\u95ED">' + ICON.close + "</button></div>";
    }).join("");
    const act = host.querySelector('[aria-selected="true"]');
    if (act && act.scrollIntoView) act.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  function renderStatusBar() {
    const sb = $("#statusbar");
    if (!settings.statusbarVisible) {
      sb.hidden = true;
      return;
    }
    sb.hidden = false;
    const t = activeTab();
    const left = [];
    if (t) {
      if (state.statusBar.cursor) {
        // #54 页码跳转：docx/pdf 的页码项可点击输入页码
        const isPager = t && (t.kind === "docx" || t.kind === "pdf") && t.state === "ready";
        left.push(isPager
          ? '<button class="status-item status-pager" data-status-act="goto-page" title="\u8F93\u5165\u9875\u7801\u8DF3\u8F6C">' + esc(state.statusBar.cursor) + "</button>"
          : '<span class="status-item">' + esc(state.statusBar.cursor) + "</span>");
      }
      left.push('<span class="status-item" data-strong="true" title="' + esc(t.path) + '">' + esc(t.name) + "</span>");
      const st = state.statusBar.saved;
      const dotState = st === "dirty" ? "dirty" : st === "busy" ? "busy" : st === "error" ? "error" : "saved";
      const label = st === "dirty" ? "\u672A\u4FDD\u5B58" : st === "busy" ? "\u8BFB\u53D6\u4E2D" : st === "error" ? "\u52A0\u8F7D\u5931\u8D25" : state.statusBar.savedText || "\u5DF2\u4FDD\u5B58";
      left.push('<span class="status-item"><span class="status-dot" data-state="' + dotState + '"></span>' + esc(label) + "</span>");
    } else {
      left.push('<span class="status-item">\u5C31\u7EEA</span>');
    }
    $("#status-left").innerHTML = left.join('<span class="status-sep"></span>');
    const right = [];
    if (state.statusBar.message) right.push('<span class="status-item">' + esc(state.statusBar.message) + "</span>");
    if (state.statusBar.annotations) right.push('<span class="status-item">' + esc(state.statusBar.annotations) + "</span>");
    right.push('<button class="status-item" data-status-act="theme" title="\u5207\u6362\u4E3B\u9898\uFF08\u70B9\u51FB\u5FAA\u73AF\uFF09">' + esc(state.theme === "dark" ? "\u6DF1\u8272" : "\u6D45\u8272") + "</button>");
    right.push('<span class="status-item">' + esc(state.bridge ? state.bridge.mode === "host" ? "\u684C\u9762\u58F3" : "\u6F14\u793A\u6A21\u5F0F" : "\u2014") + "</span>");
    $("#status-right").innerHTML = right.join('<span class="status-sep"></span>');
  }
  function applyLayoutSettings() {
    $("#sidebar").hidden = !settings.sidebarVisible;
    document.documentElement.style.setProperty("--w-sidebar", settings.sidebarWidth + "px");
    if (!settings.statusbarVisible) $("#statusbar").hidden = true;
    else $("#statusbar").hidden = false;
  }
  function closeOverlays() {
    const root = $("#overlay-root");
    root.innerHTML = "";
    Array.prototype.forEach.call(document.querySelectorAll('.menu-btn[aria-expanded="true"]'), (b) => {
      b.setAttribute("aria-expanded", "false");
    });
  }
  function openMenu(def, at, mode) {
    if (!def) return;
    const root = $("#overlay-root");
    const layer = document.createElement("div");
    layer.className = "overlay-layer";
    layer.innerHTML = '<div class="overlay-scrim" data-scrim="1"></div>';
    const pop = document.createElement("div");
    pop.className = "menu-popup";
    pop.setAttribute("role", "menu");
    if (def.label) pop.setAttribute("aria-label", def.label);
    const items = def.items || [];
    const buttons = [];
    items.forEach((it) => {
      if (it.sep) {
        const sep = document.createElement("div");
        sep.className = "menu-separator";
        pop.appendChild(sep);
        return;
      }
      if (it.group) {
        const g = document.createElement("div");
        g.className = "menu-group-label";
        g.textContent = it.group;
        pop.appendChild(g);
        return;
      }
      const b = document.createElement("button");
      b.type = "button";
      b.className = "menu-item";
      b.setAttribute("role", "menuitem");
      const enabled = it.disabled ? false : typeof it.enabled === "function" ? !!it.enabled() : true;
      if (!enabled) b.setAttribute("disabled", "");
      const check = typeof it.checked === "function" && it.checked();
      b.innerHTML = '<span class="menu-item-icon">' + (check ? ICON.check : it.icon ? ICON[it.icon] : "") + '</span><span class="menu-item-label">' + esc(it.label) + "</span>" + (it.key ? '<span class="menu-item-shortcut">' + esc(it.key) + "</span>" : "");
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        if (!enabled) return;
        closeOverlays();
        try {
          it.act && it.act();
        } catch (err) {
          console.error("[mang] \u83DC\u5355\u52A8\u4F5C\u5931\u8D25", err);
          ui.toast("error", "\u64CD\u4F5C\u5931\u8D25\uFF1A" + (err && err.message ? err.message : String(err)));
        }
      });
      pop.appendChild(b);
      buttons.push(b);
    });
    layer.appendChild(pop);
    root.appendChild(layer);
    const rect = pop.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let x = mode === "context" ? at.x : at.x;
    let y = at.y;
    if (x + rect.width > vw - 6) x = Math.max(6, vw - rect.width - 6);
    if (y + rect.height > vh - 6) {
      y = mode === "context" ? Math.max(6, at.y - rect.height) : Math.max(6, vh - rect.height - 6);
    }
    pop.style.left = Math.round(x) + "px";
    pop.style.top = Math.round(y) + "px";
    layer.addEventListener("mousedown", (e) => {
      if (e.target.closest("[data-scrim]")) closeOverlays();
    });
    layer.addEventListener("contextmenu", (e) => {
      if (e.target.closest("[data-scrim]")) {
        e.preventDefault();
        closeOverlays();
      }
    });
    let focusIdx = -1;
    const focusItem = (i) => {
      if (!buttons.length) return;
      focusIdx = (i + buttons.length) % buttons.length;
      buttons.forEach((b, k) => b.setAttribute("data-focused", String(k === focusIdx)));
      if (buttons[focusIdx]) buttons[focusIdx].focus();
    };
    layer.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        closeOverlays();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        focusItem(focusIdx + 1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        focusItem(focusIdx - 1);
      } else if (e.key === "Enter" && focusIdx >= 0) {
        e.preventDefault();
        buttons[focusIdx].click();
      }
    });
    pop.setAttribute("tabindex", "-1");
    setTimeout(() => {
      try {
        pop.focus({ preventScroll: true });
      } catch (err) {
      }
    }, 0);
  }
  function openContextMenu(items, x, y) {
    closeOverlays();
    openMenu({ items }, { x, y }, "context");
  }
  function toast(kind, message, opts) {
    const box = $("#toasts");
    const el = document.createElement("div");
    el.className = "toast";
    el.dataset.kind = kind;
    const icons = { error: "warning", warn: "warning", ok: "check", info: "info" };
    el.innerHTML = '<span class="toast-icon">' + ICON[icons[kind] || "info"] + '</span><span class="toast-body"></span><button class="toast-close" aria-label="\u5173\u95ED">' + ICON.close + "</button>";
    el.querySelector(".toast-body").textContent = message;
    const close = () => {
      if (el.parentNode) el.parentNode.removeChild(el);
    };
    el.querySelector(".toast-close").addEventListener("click", close);
    box.appendChild(el);
    const ttl = opts && opts.ttl || (kind === "error" ? 7e3 : 3600);
    window.setTimeout(close, ttl);
    return close;
  }
  function openModal(title, bodyEl, footerEl) {
    const scrim = document.createElement("div");
    scrim.className = "modal-scrim";
    const modal = document.createElement("div");
    modal.className = "modal";
    const head = document.createElement("div");
    head.className = "modal-header";
    head.innerHTML = "<span>" + esc(title) + '</span><button class="tab-action" data-close aria-label="\u5173\u95ED">' + ICON.close + "</button>";
    const body = document.createElement("div");
    body.className = "modal-body";
    if (typeof bodyEl === "string") body.innerHTML = bodyEl;
    else if (bodyEl) body.appendChild(bodyEl);
    modal.appendChild(head);
    modal.appendChild(body);
    if (footerEl) {
      const f = document.createElement("div");
      f.className = "modal-footer";
      if (typeof footerEl === "string") f.innerHTML = footerEl;
      else f.appendChild(footerEl);
      modal.appendChild(f);
    }
    scrim.appendChild(modal);
    document.body.appendChild(scrim);
    const close = () => {
      if (scrim.parentNode) scrim.parentNode.removeChild(scrim);
      document.removeEventListener("keydown", onKey, true);
    };
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close();
      }
    };
    document.addEventListener("keydown", onKey, true);
    head.querySelector("[data-close]").addEventListener("click", close);
    scrim.addEventListener("mousedown", (e) => {
      if (e.target === scrim) close();
    });
    return { close, body, modal };
  }
  function bindShellEvents() {
    const tabs = $("#tabs");
    tabs.addEventListener("click", (e) => {
      const closeBtn = e.target.closest(".tab-close");
      const tab = e.target.closest(".tab");
      if (!tab) return;
      if (closeBtn) {
        e.stopPropagation();
        ui.closeTab(tab.dataset.id);
        return;
      }
      ui.activateTab(tab.dataset.id);
    });
    tabs.addEventListener("mousedown", (e) => {
      if (e.button === 1) {
        const tab = e.target.closest(".tab");
        if (tab) {
          e.preventDefault();
          ui.closeTab(tab.dataset.id);
        }
      }
    });
    tabs.addEventListener("contextmenu", (e) => {
      const tab = e.target.closest(".tab");
      if (!tab) return;
      e.preventDefault();
      ui.tabContextMenu(tab.dataset.id, e.clientX, e.clientY);
    });
    tabs.addEventListener("wheel", (e) => {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        tabs.scrollLeft += e.deltaY;
        e.preventDefault();
      }
    }, { passive: false });
    $("#btn-tab-overflow").addEventListener("click", (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      openContextMenu([
        { label: "\u5173\u95ED\u5168\u90E8", act: () => ui.closeAllTabs(), enabled: () => state.tabs.length > 0 },
        { label: "\u5173\u95ED\u5176\u4ED6", act: () => ui.closeOtherTabs(), enabled: () => state.tabs.length > 1 },
        { sep: true },
        { label: "\u6253\u5F00\u6587\u4EF6\u2026", key: "Ctrl+O", act: () => ui.openFileDialog() }
      ], r.left - 120, r.bottom + 4);
    });
    const refreshBtn = $("#btn-refresh-tree");
    if (refreshBtn) refreshBtn.addEventListener("click", () => ui.refreshTree());
    const wsRow = $("#sidebar-workspace");
    if (wsRow) wsRow.addEventListener("click", () => ui.openFolderDialog());
  // ── 标题栏拖动 / 双击最大化 ───────────────────────────────────────
  // 为什么必须走 JS 发起：鼠标永远落在 WebView 子窗口上（它铺满整个客户区），
  // 父窗口的 WM_NCHITTEST 拿不到这次点击，所以壳里 hit_test 的 HTCAPTION
  // 对该区域形同虚设。UI 侧知道哪里是「标题栏空白处」（菜单栏的 gap/spacer、
  // 品牌区、按钮之间的空隙），由它调 window.action=\"drag\" 让壳执行
  // ReleaseCapture + SendMessage(WM_NCLBUTTONDOWN, HTCAPTION) 进系统拖动循环。
  //
  // 注：早先那版是「每次 mousedown 都上报 window.caption 改壳的命中状态」，
  // 在按下与拖动循环之间把状态改掉，反而让窗口彻底拖不动——已废弃。
  // 现在的做法不改任何状态，只在确认是标题栏空白处时直接请求拖动。
  const isTitlebarBlank = (target) => {
    if (!target || !target.closest) return false;
    // 落在可交互元素上（菜单按钮 / 窗口按钮 / 品牌链接等）不算空白
    if (target.closest("button, a, input, select, textarea, [role=\"menuitem\"], [contenteditable]")) {
      return false;
    }
    // 必须在两个标题栏容器内
    const bar = target.closest("#menubar, #titlebar");
    if (!bar) return false;
    // 不许跨到菜单下拉里
    if (target.closest(".menu-pop, .dropdown, [data-popover]")) return false;
    return true;
  };

  const startCaptionDrag = () => {
    ipc("window.action", { action: "drag" }, 5e3).catch(() => {});
  };

  const onTitlebarMouseDown = (e) => {
    if (e.button !== 0) return;                     // 只处理左键
    if (!isTitlebarBlank(e.target)) return;
    // 双击交给下面的 dblclick（避免第一下就被拖动循环吃掉）
    if (e.detail > 1) return;
    e.preventDefault();
    startCaptionDrag();
  };

  const onTitlebarDblClick = (e) => {
    if (!isTitlebarBlank(e.target)) return;
    e.preventDefault();
    ipc("window.action", { action: "toggleMaximize" }, 5e3).then((r) => {
      if (r && typeof r.maximized === "boolean") ui.setMaximized(r.maximized);
    }).catch(() => {});
  };

  const menubarEl = document.getElementById("menubar");
  if (menubarEl) {
    menubarEl.addEventListener("mousedown", onTitlebarMouseDown);
    menubarEl.addEventListener("dblclick", onTitlebarDblClick);
  }
  const titlebarEl = document.getElementById("titlebar");
  if (titlebarEl && titlebarEl !== menubarEl) {
    titlebarEl.addEventListener("mousedown", onTitlebarMouseDown);
    titlebarEl.addEventListener("dblclick", onTitlebarDblClick);
  }
    $("#statusbar").addEventListener("click", (e) => {
      const b = e.target.closest("[data-status-act]");
      if (!b) return;
      if (b.dataset.statusAct === "theme") {
        const order = ["system", "light", "dark"];
        const i = order.indexOf(settings.theme);
        ui.setTheme(order[(i + 1) % order.length]);
      } else if (b.dataset.statusAct === "goto-page") {
        // #54 页码跳转：输入页码（docx 滚动到对应 .mang-docx-page / pdf goToPage）
        const cur = String(state.statusBar.cursor || "");
        const m = /第\s*(\d+)\s*\/\s*(\d+)/.exec(cur);
        const maxPage = m ? Number(m[2]) : 0;
        const input = window.prompt(maxPage ? "跳转到页码（1 - " + maxPage + "）：" : "跳转到页码：", m ? m[1] : "1");
        if (input === null) return;
        gotoPageOfActiveTab(input);
      }
    });
    bindSidebarResize();
    document.addEventListener("keydown", onGlobalKeydown);
    window.addEventListener("dragover", (e) => {
      if (e.dataTransfer && Array.from(e.dataTransfer.types || []).indexOf("Files") >= 0) {
        e.preventDefault();
        document.body.dataset.dragover = "1";
      }
    });
    window.addEventListener("dragleave", (e) => {
      if (!e.relatedTarget) delete document.body.dataset.dragover;
    });
    window.addEventListener("drop", (e) => {
      delete document.body.dataset.dragover;
      if (!e.dataTransfer || !e.dataTransfer.files || !e.dataTransfer.files.length) return;
      e.preventDefault();
      ui.onDroppedFiles(Array.from(e.dataTransfer.files));
    });
    window.addEventListener("wheel", (e) => {
      if (e.defaultPrevented) return;
      // 白名单：能滚的元素。漏掉任何一个，滚轮就会被 preventDefault 吞掉。
      // 曾经漏了 .menu-popup —— 菜单项一多滚轮就失效（滚的是背景，菜单不动）。
      const sel = [
        ".sidebar-body", ".view-scroll", ".text-scroll", ".md-view", ".empty", ".tabs",
        ".modal-body", ".mang-pdf-scroll", ".mxvp", ".mang-docx", ".mang-docx-page",
        ".mang-xlsx", ".menu-popup", ".menu-pop", ".dropdown", ".cmd-palette-list",
        ".xlsx-grid-wrap", ".canvas-wrap"
      ].join(", ");
      const inScrollable = e.target.closest && e.target.closest(sel);
      // 也放行「自身可滚动」的元素，避免以后新增滚动容器又漏配
      const selfScrollable = (() => {
        let n = e.target;
        while (n && n.nodeType === 1) {
          const st = getComputedStyle(n);
          if (/(auto|scroll)/.test(st.overflowY) && n.scrollHeight > n.clientHeight) return true;
          n = n.parentElement;
        }
        return false;
      })();
      if (!inScrollable && !selfScrollable) e.preventDefault();
    }, { passive: false });
  }
  function bindSidebarResize() {
    const handle = $("#sidebar-resize");
    const sidebarEl = $("#sidebar");
    if (!handle) return;
    handle.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      handle.dataset.dragging = "true";
      // #76 问题1：拖拽期间禁用文本选择——否则 mousemove 被浏览器当
      // 「划选文本」，侧栏/正文出现选中高亮块（浅色主题下即「黑边」），
      // 松手后仍保持。user-select 一关，拖全程干净。
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
      const startX = e.clientX;
      const startW = sidebarEl.getBoundingClientRect().width;
      const onMove = (m) => {
        const w = Math.max(170, Math.min(520, startW + (m.clientX - startX)));
        settings.sidebarWidth = Math.round(w);
        document.documentElement.style.setProperty("--w-sidebar", settings.sidebarWidth + "px");
      };
      const onUp = () => {
        delete handle.dataset.dragging;
        document.body.style.userSelect = "";
        document.body.style.cursor = "";
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        saveSettings();
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
    handle.addEventListener("dblclick", () => {
      settings.sidebarWidth = 260;
      document.documentElement.style.setProperty("--w-sidebar", "260px");
      saveSettings();
    });
  }
  var chordTimer = 0;
  function chordActive() {
    return chordTimer !== 0;
  }
  function armChord() {
    clearTimeout(chordTimer);
    chordTimer = window.setTimeout(() => {
      chordTimer = 0;
    }, 2500);
  }
  function consumeChord() {
    clearTimeout(chordTimer);
    chordTimer = 0;
  }
  function onGlobalKeydown(e) {
    const ctrl = e.ctrlKey || e.metaKey;
    const key = (e.key || "").toLowerCase();
    if (e.defaultPrevented) return;
    if (ctrl && !e.shiftKey && !e.altKey && key === "k") {
      e.preventDefault();
      armChord();
      ui.setStatus({ message: "Ctrl+K \u5DF2\u6309\u4E0B\uFF1A\u518D\u6309 O \u6253\u5F00\u6587\u4EF6\u5939\uFF0C\u6309 S \u67E5\u770B\u5FEB\u6377\u952E" });
      return;
    }
    if (chordActive() && !ctrl) {
      if (key === "o") {
        consumeChord();
        e.preventDefault();
        ui.setStatus({ message: "" });
        ui.openFolderDialog();
        return;
      }
      if (key === "s") {
        consumeChord();
        e.preventDefault();
        ui.setStatus({ message: "" });
        ui.showShortcuts();
        return;
      }
    }
    if (ctrl && !e.altKey && !e.shiftKey && key === "o") {
      e.preventDefault();
      ui.openFileDialog();
    } else if (ctrl && e.shiftKey && key === "o") {
      e.preventDefault();
      ui.openFolderDialog();
    } else if (ctrl && key === "w") {
      e.preventDefault();
      ui.closeActiveTab();
    } else if (ctrl && key === "b") {
      e.preventDefault();
      ui.toggleSidebar();
    } else if (ctrl && !e.shiftKey && key === "s") {
      e.preventDefault();
      ui.saveActive();
    } else if (ctrl && key === "tab") {
      e.preventDefault();
      ui.cycleTab(e.shiftKey ? -1 : 1);
    } else if (ctrl && e.shiftKey && key === "e") {
      e.preventDefault();
      ui.showSidebar("files");
    } else if (ctrl && e.shiftKey && key === "b") {
      e.preventDefault();
      ui.showSidebar("bid");
    } else if (ctrl && e.shiftKey && key === "u") {
      e.preventDefault();
      ui.showSidebar("outline");
    } else if (ctrl && e.shiftKey && key === "h") {
      e.preventDefault();
      ui.showSidebar("history");
    } else if (ctrl && e.shiftKey && key === "g") {
      e.preventDefault();
      ui.showSidebar("changes");
    } else if (ctrl && key === ",") {
      e.preventDefault();
      ui.showSidebar("settings");
    } else if (ctrl && !e.shiftKey && key === "r") {
      e.preventDefault();
      location.reload();
    } else if (e.key === "F5") {
      e.preventDefault();
      ui.refreshTree();
    } else if (ctrl && !e.shiftKey && !e.altKey && /^[1-9]$/.test(key)) {
      e.preventDefault();
      const i0 = parseInt(key, 10) - 1;
      if (state.tabs[i0]) ui.activateTab(state.tabs[i0].id);
    } else if (e.key === "Escape") {
      closeOverlays();
    }
  }
  var tabSeq = 0;
  function tabById(id) {
    for (const t of state.tabs) if (t.id === id) return t;
    return null;
  }
  var ui = {
    showSidebar(id) {
      if (settings.sidebarVisible && settings.sidebarActive === id) settings.sidebarVisible = false;
      else {
        settings.sidebarVisible = true;
        settings.sidebarActive = id;
      }
      saveSettings();
      applyLayoutSettings();
      syncActivitySelection();
      renderSidebar();
    },
    toggleSidebar() {
      settings.sidebarVisible = !settings.sidebarVisible;
      saveSettings();
      applyLayoutSettings();
      syncActivitySelection();
      if (settings.sidebarVisible) renderSidebar();
      renderStatusBar();
    },
    toggleStatusBar() {
      settings.statusbarVisible = !settings.statusbarVisible;
      saveSettings();
      applyLayoutSettings();
      renderStatusBar();
    },
    setTheme(theme) {
      settings.theme = theme;
      saveSettings();
      applyTheme();
      renderStatusBar();
      if (settings.sidebarActive === "settings") renderSidebar();
    },
    async refreshTree() {
      if (!state.bridge) return;
      state.treeBusy = true;
      if (settings.sidebarActive === "files") renderSidebar();
      try {
        const tree = await ipc("fs.tree", { depth: 6 }, 15e3);
        state.tree = tree;
        state.treeError = "";
        if (tree && tree.root) {
          state.workspace = tree.root;
          setWorkspaceLabel(tree.root);
        }
        if (tree && Array.isArray(tree.nodes)) {
          for (const n of tree.nodes) if (n.kind === "dir" && state.expanded.size < 2) state.expanded.add(n.rel);
        }
      } catch (err) {
        state.treeError = "\u8BFB\u53D6\u5DE5\u4F5C\u533A\u5931\u8D25\uFF1A" + (err.message || err.code || String(err));
        state.tree = null;
      } finally {
        state.treeBusy = false;
        if (settings.sidebarActive === "files") renderSidebar();
        if (!state.tabs.length) renderEmpty();
      }
    },
    async openFolderDialog() {
      try {
        const r = await ipc("dialog.openFolder", {}, 12e4);
        const p0 = r && r.paths && r.paths[0];
        if (!p0) return;
        await ui.switchWorkspace(p0);
      } catch (err) {
        ui.toast("error", "\u6253\u5F00\u5DE5\u4F5C\u533A\u5931\u8D25\uFF1A" + err.message);
      }
    },
    /**
     * #194：切换工作区（= 切换标书项目——.mang/ 与 db.json 都在工作区根下）。
     * 壳侧 workspace.open 换根（校验 + 记忆，重启停在上次的工作区）；
     * UI 侧随之刷新：文件树 / 最近列表 / 状态栏 / git 面板，编辑器全关
     * （旧工作区的文件句柄不再有效——防读写落到围栏外）。
     */
    async switchWorkspace(p0) {
      if (!p0) return;
      const info = await ipc("workspace.open", { path: p0 }, 15e3);
      const root = info && info.root || p0;
      state.workspace = root;
      setWorkspaceLabel(root);
      // 工作区进最近列表（kind=dir——下次可从欢迎页一键切回）
      touchRecentWorkspace(root);
      // 清空编辑器（Tab dispose 走 closeTab 的完整清理链）
      ui.closeAllTabs();
      // 旧工作区的会话态全部失效：展开目录/选中项/git 数据/快照面板
      state.expanded = new Set();
      state.selectedRel = "";
      state.git = { status: "idle", available: false, branch: "", items: [], log: [], error: "" };
      state.snapshots = { status: "idle", file: "", entries: [], error: "" };
      // #313 批 A/B/D：标书数据面随根失效（壳侧服务缓存也会按 db.json 指纹重开）
      state.bid = {
        status: "idle", present: false, data: null, outline: null, error: "", ts: 0,
        matrix: { status: "idle", data: null, error: "", code: "" },
        mx: { status: "", cat: "", blockingOnly: false, page: 1, pageSize: 50, expandedId: "", formReq: "", passing: false, passError: "", passInfo: "" },
        coverage: { status: "idle", data: null, error: "", code: "" },
        cov: { expandedFile: "" }
      };
      state.bidCollapsed = new Set();
      // #313 批 C：自评数据面同理随根失效
      state.bidQuality = { status: "idle", quality: null, score: null, error: "", code: "", scoreError: "", ts: 0 };
      // #603 批 A：治理面同理随根失效（门台账/表单态/写面消息全清）
      state.bidGates = { status: "idle", data: null, error: "", code: "", ts: 0, passing: false, passError: "", passInfo: "", formGate: "", formMode: "" };
      // R4（#47）：向导会话态同理随根失效——result/sel/files 是旧工作区的
      // 导入现场，泄漏到新工作区会把「文件已入库」+ 旧结果表错挂到新项目
      // （与上面 bid/bidQuality/bidGates 同列，漏列即跨根泄漏）
      state.bidWizard = {
        createBusy: false, createError: "",
        treeStatus: "idle", treeError: "", files: [], sel: {},
        importBusy: false, importError: "", result: null
      };
      // #603 批 C：补遗面同理随根失效（不留旧项目数据）
      state.bidAddenda = { status: "idle", data: null, error: "", ts: 0, waiving: false, waiveError: "", waiveInfo: "", formOpen: false, formGlobal: false };
      // 重载：文件树（新根）+ 空态/侧栏/状态栏
      await ui.refreshTree();
      loadRecent().then(() => {
        renderEmpty();
        renderHistoryViewIfVisible();
      });
      renderSidebar();
      renderStatusBar();
      // git 面板当前可见才立刻拉新工作区的数据（不可见时等打开再拉）
      if (settings.sidebarActive === "changes") ui.loadGit();
      // #313 批 A：标书面板同理——可见即拉新根的标书数据
      if (settings.sidebarActive === "bid") ui.loadBid();
      if (info && info.changed) {
        ui.toast("ok", "\u5DF2\u5207\u6362\u5DE5\u4F5C\u533A\uFF1A" + (baseName(root) || root));
      }
    },
    async openFileDialog() {
      try {
        const r = await ipc("dialog.openFile", {}, 12e4);
        const ps = r && r.paths || [];
        for (const p0 of ps) await ui.openPath(p0);
      } catch (err) {
        ui.toast("error", "\u6253\u5F00\u6587\u4EF6\u5931\u8D25\uFF1A" + err.message);
      }
    },
    /** #313 批 A/B：拉取标书数据面（bid.state + bid.outline 并行；矩阵已加载过则一并刷新）——侧栏与工作台共用 */
    async loadBid(force) {
      if (!state.bridge) return;
      if (state.bid.status === "loading" && !force) return;
      state.bid.status = "loading";
      state.bid.error = "";
      renderBidViewIfVisible();
      renderBidWorkbenchIfOpen();
      // #313 批 B：矩阵面已被看过（ready/error）→ 刷新时一并重拉，保持两数据面同源
      const mxTouched = state.bid.matrix.status === "ready" || state.bid.matrix.status === "error";
      if (mxTouched) ui.loadBidMatrix(true);
      // #313 批 D：覆盖面同理（ready/error → 一并重拉，三数据面同源）
      const covTouched = state.bid.coverage.status === "ready" || state.bid.coverage.status === "error";
      if (covTouched) ui.loadBidCoverage(true);
      const settled = await Promise.allSettled([
        ipc("bid.state", {}, 15e3),
        ipc("bid.outline", {}, 15e3)
      ]);
      const st = settled[0];
      const ol = settled[1];
      if (st.status === "fulfilled" && st.value && st.value.present) {
        state.bid.present = true;
        state.bid.data = st.value;
      } else {
        state.bid.present = false;
        state.bid.data = null;
        state.bid.error = st.reason && (st.reason.message || st.reason.code) || "bid.state 读取失败";
        // 项目面已失（切工作区/项目被移）——矩阵缓存一并失效，不留旧项目数据
        state.bid.matrix = { status: "idle", data: null, error: "" };
        state.bid.mx = { status: "", cat: "", blockingOnly: false, page: 1, pageSize: state.bid.mx.pageSize || 50, expandedId: "" };
        // 覆盖缓存一并失效（批 D——不留旧项目数据）
        state.bid.coverage = { status: "idle", data: null, error: "", code: "" };
        state.bid.cov = { expandedFile: "" };
      }
      state.bid.outline = ol.status === "fulfilled" ? ol.value : null;
      state.bid.status = "ready";
      state.bid.ts = Date.now();
      renderBidViewIfVisible();
      renderBidWorkbenchIfOpen();
    },
    /** #313 批 B：拉取合规矩阵（bid.matrix——壳内聚合工具面分页后的全量行） */
    async loadBidMatrix(force) {
      if (!state.bridge) return;
      if (state.bid.matrix.status === "loading" && !force) return;
      state.bid.matrix.status = "loading";
      state.bid.matrix.error = "";
      // R6（#47 / #19 任务 3）：记错误码（对齐 coverage / gates）——矩阵
      // 面板按 not_found / state 分支引导卡（契约 §3.4），此前只记 message
      // 一把抓成故障横幅。
      state.bid.matrix.code = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.matrix", {}, 6e4);
        if (r && r.present) {
          state.bid.matrix.data = r;
        } else {
          state.bid.matrix.data = null;
          state.bid.matrix.error = "当前工作区无矩阵数据";
        }
        state.bid.matrix.status = "ready";
      } catch (err) {
        state.bid.matrix.data = null;
        state.bid.matrix.status = "error";
        state.bid.matrix.code = (err && err.code) || "";
        state.bid.matrix.error = err && (err.message || err.code) || "bid.matrix 读取失败";
      }
      renderBidWorkbenchIfOpen();
    },
    /** #313 批 A/B：「标书工作台」伪标签页（不占 recent、不碰文件系统）；
     *  panel（"detail" | "matrix" | "quality"）——面板直开（侧栏面板入口用） */
    /** #313 批 D：拉取覆盖报告（bid.coverage——工具面 get_coverage_report
     *  + 逐文件 get_star_coverage 聚合；工具面 E_STATE 透传为壳侧 state 码，
     *  面板按 code 分支出「尚未开放」引导卡） */
    async loadBidCoverage(force) {
      if (!state.bridge) return;
      if (state.bid.coverage.status === "loading" && !force) return;
      state.bid.coverage.status = "loading";
      state.bid.coverage.error = "";
      state.bid.coverage.code = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.coverage", {}, 6e4);
        if (r && r.present) {
          state.bid.coverage.data = r;
        } else {
          state.bid.coverage.data = null;
          state.bid.coverage.error = "当前工作区无覆盖数据";
        }
        state.bid.coverage.status = "ready";
      } catch (err) {
        state.bid.coverage.data = null;
        state.bid.coverage.status = "error";
        state.bid.coverage.code = (err && err.code) || "";
        state.bid.coverage.error = err && (err.message || err.code) || "bid.coverage 读取失败";
      }
      renderBidWorkbenchIfOpen();
    },
    /** #313 批 A/B/D：「标书工作台」伪标签页（不占 recent、不碰文件系统）；
     *  panel（"detail" | "matrix" | "coverage"）——面板直开（侧栏面板入口用） */

    /** #19：向导文件面——fs.tree 拉工作区文件（白名单过滤 + 勾选集清洗） */
    async loadBidWizardTree(force) {
      if (!state.bridge) return;
      if (state.bidWizard.treeStatus === "loading" && !force) return;
      state.bidWizard.treeStatus = "loading";
      state.bidWizard.treeError = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("fs.tree", { depth: 8 }, 3e4);
        const files = [];
        const walk = (nodes) => {
          (nodes || []).forEach((n) => {
            if (n.kind === "dir") { walk(n.nodes); return; }
            // 排除项目库件（db.json / chapters/）——它们是产物不是招标输入
            if (/^db\.json$/i.test(n.name)) return;
            if (/^chapters\//i.test(n.rel)) return;
            if (!BID_IMPORT_EXTS.test(n.name)) return;
            files.push({ rel: n.rel, name: n.name, size: n.size });
          });
        };
        walk(r && r.nodes);
        files.sort((a, b) => a.rel.localeCompare(b.rel, "zh-Hans-CN"));
        state.bidWizard.files = files;
        const relSet = new Set(files.map((f) => f.rel));
        Object.keys(state.bidWizard.sel).forEach((rel) => { if (!relSet.has(rel)) delete state.bidWizard.sel[rel]; });
        state.bidWizard.treeStatus = "ready";
      } catch (err) {
        state.bidWizard.treeStatus = "error";
        state.bidWizard.treeError = err && (err.message || err.code) || "fs.tree 读取失败";
      }
      renderBidWorkbenchIfOpen();
    },
    /** #19：向导第一步提交——bid.create_project（壳侧隐式幂等键 = 工作区
     *  路径；重复提交不建第二个项目，UI 侧不再另造 external_key） */
    async submitBidWizardCreate(form) {
      if (!state.bridge || state.bidWizard.createBusy) return;
      const fd = new FormData(form);
      const name = String(fd.get("name") || "").trim();
      const mode = String(fd.get("mode") || "明标");
      const deadline = String(fd.get("bid_deadline") || "").trim();
      const notice = String(fd.get("tender_notice_ref") || "").trim();
      if (!name) { state.bidWizard.createError = "项目名称必填"; renderBidWorkbenchIfOpen(); return; }
      if (!/^\d{4}-\d{2}-\d{2}$/.test(deadline)) { state.bidWizard.createError = "投标截止须为日期（YYYY-MM-DD）"; renderBidWorkbenchIfOpen(); return; }
      state.bidWizard.createBusy = true;
      state.bidWizard.createError = "";
      renderBidWorkbenchIfOpen();
      try {
        await ipc("bid.create_project", {
          name: name, mode: mode, bid_deadline: deadline,
          ...(notice ? { tender_notice_ref: notice } : {})
        }, 3e4);
        state.bidWizard.createBusy = false;
        state.bidWizard.result = null;        // 新项目 → 上次导入结果作废
        state.bidWizard.sel = {};
        state.bidWizard.treeStatus = "idle";  // 进入第二步时重拉文件列表
        await ui.loadBid(true);               // present → DRAFT → 导入卡接管
      } catch (err) {
        state.bidWizard.createBusy = false;
        state.bidWizard.createError = err && (err.message || err.code) || "创建失败";
        renderBidWorkbenchIfOpen();
      }
    },
    /** #19：向导第二步提交——bid.import_files（upload_ref = 工作区相对
     *  路径；project_id 由壳侧注入真源，UI 不自报） */
    async submitBidWizardImport() {
      if (!state.bridge || state.bidWizard.importBusy) return;
      const sel = state.bidWizard.sel || {};
      const rels = Object.keys(sel);
      if (!rels.length) return;
      state.bidWizard.importBusy = true;
      state.bidWizard.importError = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.import_files", {
          files: rels.map((rel) => {
            const f = state.bidWizard.files.find((x) => x.rel === rel) || { name: rel.split("/").pop() };
            return { upload_ref: rel, filename: f.name, kind: sel[rel] };
          })
        }, 6e5);
        state.bidWizard.importBusy = false;
        state.bidWizard.result = r || null;
        await ui.loadBid(true); // FILES_IMPORTED → 树区转「下一步」引导，右面板留结果
      } catch (err) {
        state.bidWizard.importBusy = false;
        state.bidWizard.importError = err && (err.message || err.code) || "导入失败";
        renderBidWorkbenchIfOpen();
      }
    },
    async loadBidQuality(force) {
      if (!state.bridge) return;
      if (state.bidQuality.status === "loading" && !force) return;
      state.bidQuality.status = "loading";
      state.bidQuality.error = "";
      state.bidQuality.code = "";
      state.bidQuality.scoreError = "";
      renderBidWorkbenchIfOpen();
      const settled = await Promise.allSettled([
        ipc("bid.quality", {}, 3e4),
        ipc("bid.score", {}, 3e4)
      ]);
      const q = settled[0];
      const s = settled[1];
      if (q.status === "fulfilled" && q.value) {
        state.bidQuality.quality = q.value.quality || null;
      } else {
        state.bidQuality.quality = null;
        const reason = q.reason || {};
        state.bidQuality.code = reason.code || "";
        state.bidQuality.error = reason.message || reason.code || "bid.quality 读取失败";
      }
      if (s.status === "fulfilled" && s.value) {
        state.bidQuality.score = s.value.score || null;
        state.bidQuality.scoreError = "";
      } else {
        state.bidQuality.score = null;
        const reason = s.reason || {};
        // 同源 state 拒绝已在 quality 面呈现——不重复报；其它失败如实记
        state.bidQuality.scoreError = reason.code === "state" ? "" : reason.message || reason.code || "bid.score 读取失败";
      }
      state.bidQuality.status = "ready";
      state.bidQuality.ts = Date.now();
      renderBidWorkbenchIfOpen();
    },
    /** #603 批 A：拉取审核门台账（bid.gates——DomainStore 直读五门状态/
     *  最新过门/agent 豁免清单/裁决历史）。读面无状态窗：早期态「三门全
     *  未过」也是有效数据（与 quality 的 state 码引导不同，这里只在无
     *  db.json 时分支引导）。 */
    async loadBidGates(force) {
      if (!state.bridge) return;
      if (state.bidGates.status === "loading" && !force) return;
      state.bidGates.status = "loading";
      state.bidGates.error = "";
      state.bidGates.code = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.gates", {}, 15e3);
        if (r && r.present) {
          state.bidGates.data = r;
        } else {
          state.bidGates.data = null;
          state.bidGates.error = "当前工作区无审核门数据";
        }
        state.bidGates.status = "ready";
      } catch (err) {
        state.bidGates.data = null;
        state.bidGates.status = "error";
        state.bidGates.code = (err && err.code) || "";
        state.bidGates.error = err && (err.message || err.code) || "bid.gates 读取失败";
      }
      state.bidGates.ts = Date.now();
      renderBidWorkbenchIfOpen();
    },
    /** #603 批 A：人工过门/追认/拒审（bid.gate_pass——宿主签发 receipt（#182）
     *  后经真实工具面 record_review_gate 落账）。壳侧不校验门序/状态窗——
     *  域层裁决原样透传（state/bad_args 码 → 引导文案，不假成功）。 */
    async passBidGate(gate, decision, opts) {
      if (!state.bridge || state.bidGates.passing) return;
      const o = opts || {};
      state.bidGates.passing = true;
      state.bidGates.passError = "";
      state.bidGates.passInfo = "";
      renderBidWorkbenchIfOpen();
      try {
        const body = { gate: gate, decision: decision };
        if (o.reason) body.reason = o.reason;
        if (o.actorId) body.actor_id = o.actorId;
        if (decision === "REJECTED" && o.blockerMessage) {
          body.findings = [{ severity: "BLOCKER", code: o.blockerCode || "SHELL-REJECT", message: o.blockerMessage }];
        }
        const r = await ipc("bid.gate_pass", body, 3e4);
        const gp = r && r.gate_pass;
        if (gp && gp.receipt) {
          state.bidGates.passInfo = (decision === "APPROVED" ? "已过门：" : "已拒审：") + gp.receipt.gate
            + (Array.isArray(gp.receipt.spawned_rt_ids) && gp.receipt.spawned_rt_ids.length ? "（派生 RT " + gp.receipt.spawned_rt_ids.join("、") + "）" : "");
        } else {
          state.bidGates.passInfo = decision === "APPROVED" ? "已过门" : "已拒审";
        }
        state.bidGates.formGate = "";
        state.bidGates.formMode = "";
      } catch (err) {
        state.bidGates.passError = err && (err.message || err.code) || "bid.gate_pass 失败";
      }
      state.bidGates.passing = false;
      // 台账 + 侧栏门审摘要同源刷新（agent_waivers/human_review_complete 两处都消费）
      ui.loadBidGates(true);
      ui.loadBid(true);
    },
    /** #18：跑校验报告（bid.validate → validate_bid_document 真实工具面）。
     *  会推进项目至 VALIDATING（域层语义）；E_STATE 透传 state 码 → 引导卡。 */
    async loadBidValidate(force) {
      if (!state.bridge) return;
      if (state.bidExport.status === "loading" && !force) return;
      state.bidExport.status = "loading";
      state.bidExport.error = "";
      state.bidExport.code = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.validate", {}, 12e4);
        state.bidExport.report = (r && r.report) || null;
      } catch (err) {
        state.bidExport.report = null;
        state.bidExport.code = (err && err.code) || "";
        state.bidExport.error = err && (err.message || err.code) || "bid.validate 失败";
      }
      state.bidExport.status = "ready";
      state.bidExport.ts = Date.now();
      renderBidWorkbenchIfOpen();
    },
    /** #18：确认导出（bid.export → export_bid_document 真实工具面）。
     *  双前置门由工具面裁决：E_STATE（未校验/未过门）原文进引导卡；
     *  成功则回显产物（artifact.url/sha256/size）并触发 explorer.reveal。 */
    async runBidExport() {
      const x = state.bidExport;
      if (!state.bridge || x.exporting) return;
      const path = (x.path || "").trim();
      if (!path) {
        x.doneError = "输出路径不能为空（工作区相对路径，如 export/标书.docx）";
        x.doneCode = "";
        renderBidWorkbenchIfOpen();
        return;
      }
      x.exporting = true;
      x.doneError = "";
      x.doneCode = "";
      x.done = null;
      renderBidWorkbenchIfOpen();
      try {
        const body = { format: x.format, output_path: path, dark_bid: !!x.darkBid };
        if (x.darkBid && x.bidderName) body.bidder_name = x.bidderName;
        const r = await ipc("bid.export", body, 3e5);
        x.done = (r && r.export) || null;
        if (!x.done) throw Object.assign(new Error("bid.export 应答缺少 export 载荷"), { code: "ipc" });
        // 导出成功即重拉项目面（状态推进 EXPORTED、门台账可能翻新）
        ui.loadBid(true);
        if (state.bidGates.status !== "idle") ui.loadBidGates(true);
      } catch (err) {
        x.done = null;
        x.doneCode = (err && err.code) || "";
        x.doneError = err && (err.message || err.code) || "bid.export 失败";
      }
      x.exporting = false;
      renderBidWorkbenchIfOpen();
    },
    /** #18：产物定位（explorer.reveal——工作区内绝对路径放行）。 */
    async revealBidArtifact() {
      const x = state.bidExport;
      const url = x.done && x.done.artifact && x.done.artifact.url;
      if (!state.bridge || !url) return;
      try {
        await ipc("explorer.reveal", { path: url }, 15e3);
      } catch (err) {
        ui.setStatus({ message: "定位产物失败：" + ((err && err.message) || "未知") });
      }
    },
    /** #20：拉取分包清单（bid.packages 只读——工作台「分包」页签）。 */
    async loadBidPackages(force) {
      if (!state.bridge) return;
      if (state.bidPackages.status === "loading" && !force) return;
      state.bidPackages.status = "loading";
      state.bidPackages.error = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.packages", {}, 15e3);
        if (r && r.present) {
          state.bidPackages.data = r;
          state.bidPackages.status = "ready";
        } else {
          state.bidPackages.data = null;
          state.bidPackages.status = "error";
          state.bidPackages.error = "当前工作区无分包数据";
        }
      } catch (err) {
        state.bidPackages.data = null;
        state.bidPackages.status = "error";
        state.bidPackages.error = err && (err.message || err.code) || "bid.packages 读取失败";
      }
      renderBidWorkbenchIfOpen();
    },
    /** #20：否决项死锁人工裁定（bid.matrix_override → 工具面
     *  set_matrix_override；receipt 由壳签发——UI 只传 行/状态/偏离说明）。
     *  成功 → 矩阵重拉（blocking 重算）；失败 → 表单内反馈（E_STATE 引导）。 */
    async passMatrixOverride(reqId, status, deviation) {
      const f = state.bid.mx;
      f.passing = true;
      f.passError = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.matrix_override", {
          requirement_id: reqId,
          status: status,
          deviation: deviation || ""
        }, 3e4);
        f.passing = false;
        f.formReq = "";
        const ov = r && r.override || {};
        const from = ov.from_status || "";
        const blocking = ov.blocking_after != null ? " · 剩余阻断 " + ov.blocking_after : "";
        f.passInfo = "已裁定 " + reqId + " → " + esc(ov.status || status) + blocking;
        ui.loadBidMatrix(true); // 覆写后矩阵立即重算（blocking 口径同源）
      } catch (err) {
        f.passing = false;
        f.passError = err && err.message || "bid.matrix_override 失败";
        renderBidWorkbenchIfOpen();
      }
    },
    /** #20：VALIDATING+缺章异常态恢复（bid.recover_state → 工具面
     *  recover_validating_state——域层三重约束守门，非死锁态 E_STATE 响亮拒）。 */
    async recoverBidState(reason) {
      const gt = state.bidGates;
      gt.passing = true;
      gt.passError = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.recover_state", { reason: reason }, 3e4);
        gt.passing = false;
        gt.formGate = "";
        gt.formMode = "";
        const rc = r && r.recover || {};
        gt.passInfo = "已恢复到 " + esc(rc.to_status || "DRAFTING") + "（缺章解锁起草面）";
        // 项目状态/门台账/大纲三面同源刷新
        ui.loadBidGates(true);
        ui.loadBid(true);
      } catch (err) {
        gt.passing = false;
        gt.passError = err && err.message || "bid.recover_state 失败";
        renderBidWorkbenchIfOpen();
      }
    },
    /** #603 批 C：补遗件台账（bid.addenda——DomainStore+readiness 直读面） */
    async loadBidAddenda(force) {
      if (!state.bridge) return;
      if (state.bidAddenda.status === "loading" && !force) return;
      state.bidAddenda.status = "loading";
      state.bidAddenda.error = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.addenda", {}, 15e3);
        if (r && r.present) {
          state.bidAddenda.data = r;
        } else {
          state.bidAddenda.data = null;
          state.bidAddenda.error = "当前工作区无补遗台账";
        }
        state.bidAddenda.status = "ready";
      } catch (err) {
        state.bidAddenda.data = null;
        state.bidAddenda.status = "error";
        state.bidAddenda.error = err && (err.message || err.code) || "bid.addenda 读取失败";
      }
      state.bidAddenda.ts = Date.now();
      renderBidWorkbenchIfOpen();
    },
    /** #603 批 C：补遗逐件确认（bid.addendum_waiver——宿主签发 receipt
     * （#182 签域绑本件）后经真实工具面 record_addendum_waiver 落账）。
     * 壳侧不校验幽灵件/状态窗——域层裁决原样透传，不假成功。 */
    async waiveBidAddendum(fileId, reason) {
      if (!state.bridge || state.bidAddenda.waiving) return;
      state.bidAddenda.waiving = true;
      state.bidAddenda.waiveError = "";
      state.bidAddenda.waiveInfo = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.addendum_waiver", { file_id: fileId, reason: reason }, 3e4);
        const awo = r && r.addendum_waiver;
        state.bidAddenda.waiveInfo = "已确认放行 " + fileId + (awo && awo.recorded ? "（起草将标 RESTRICTED——不静默当完整输入）" : "");
      } catch (err) {
        state.bidAddenda.waiveError = err && (err.message || err.code) || "bid.addendum_waiver 失败";
      }
      state.bidAddenda.waiving = false;
      // 补遗台账 + 门台账 + 侧栏同源刷新（三处都消费）
      ui.loadBidAddenda(true);
      ui.loadBidGates(true);
      ui.loadBid(true);
    },
    /** #603 批 C：全局无补遗确认（bid.no_addendum_confirm——#379 拆门，
     * 独立签域 no_addendum_confirmed；项目已有补遗件时域层响亮拒） */
    async confirmNoAddendum(reason) {
      if (!state.bridge || state.bidAddenda.waiving) return;
      state.bidAddenda.waiving = true;
      state.bidAddenda.waiveError = "";
      state.bidAddenda.waiveInfo = "";
      renderBidWorkbenchIfOpen();
      try {
        const r = await ipc("bid.no_addendum_confirm", { reason: reason }, 3e4);
        const nc = r && r.no_addendum_confirm;
        state.bidAddenda.waiveInfo = nc && nc.confirmed_no_addendum ? "已确认本项目无补遗（过门 + 审计留痕）" : "已确认";
        state.bidAddenda.formGlobal = false;
      } catch (err) {
        state.bidAddenda.waiveError = err && (err.message || err.code) || "bid.no_addendum_confirm 失败";
      }
      state.bidAddenda.waiving = false;
      ui.loadBidAddenda(true);
      ui.loadBidGates(true);
      ui.loadBid(true);
    },
    /** #313 批 A：「标书工作台」伪标签页（不占 recent、不碰文件系统）；
     *  批 C：panel 入参直达指定页签（"quality" = 自评——侧栏面板入口用） */
    async openBidWorkbench(panel) {

      const existing = bidWorkbenchTab();
      if (existing) {
        if (panel && existing.meta.panel !== panel) existing.meta.panel = panel;
        // R7（#47）：向导重入新鲜度——半完成态（DRAFT 0 文件）重开工作台时
        // 两源重拉：bid.state 强制刷新（quick_stats 判据可能过期——壳外
        // Agent 已导过文件的话判据翻转，向导该让位完成态）+ 文件列表重置
        // idle（渲染时自动 loadBidWizardTree——用户在壳外放的招标文件
        // 立即可见，不靠手点刷新）。只重置 ready 态（loading/error 不打断）
        const bR7 = state.bid;
        const pR7 = (bR7.data && bR7.data.project) || {};
        const qR7 = (bR7.data && bR7.data.quick_stats) || {};
        if (bR7.status === "ready" && pR7.status === "DRAFT" && !(qR7.files > 0)) {
          if (state.bidWizard.treeStatus === "ready") state.bidWizard.treeStatus = "idle";
          ui.loadBid(true);
        }
        await ui.activateTab(existing.id);
        renderBidWorkbenchIfOpen();
        return;
      }

      const tab = {
        id: "t" + ++tabSeq,
        path: "mang://bid-workbench",
        name: "标书工作台",
        kind: "bidwork",
        dirty: false,
        state: "loading",
        error: "",
        meta: { selectedId: "", panel: panel || "detail" },
        dispose: null
      };
      state.tabs.push(tab);
      state.activeTabId = tab.id;
      renderTabs();
      renderEmpty();
      renderStatusBar();
      await ui.loadTab(tab);
    },
    async openPath(p0) {
      if (!p0) return;
      const existing = state.tabs.find((t) => t.path === p0);
      if (existing) return ui.activateTab(existing.id);
      const name = baseName(p0);
      const tab = {
        id: "t" + ++tabSeq,
        path: p0,
        name,
        kind: kindOf(name),
        dirty: false,
        state: "loading",
        error: "",
        meta: {},
        dispose: null
      };
      state.tabs.push(tab);
      state.activeTabId = tab.id;
      renderTabs();
      renderEmpty();
      renderStatusBar();
      touchRecent(p0);
      renderHistoryViewIfVisible();
      await ui.loadTab(tab);
    },
    async loadTab(tab) {
      tab.state = "loading";
      tab.error = "";
      ui.setStatus({ saved: "busy" });
      const host = ui.ensurePane(tab);
      // 渲染性能修复（切换/重载累积卡顿）：抹除 pane 前必须先释放上一个
      // 渲染器。旧实现在「重新加载 / 加载失败重试 / 重开同一标签」时直接
      // innerHTML 抹除——旧渲染器的清理永远不会执行：
      //   * docx：window/scroller 滚动监听器残留（window 级的每次滚动都跑
      //     旧闭包的 querySelectorAll——滚动越用越卡）；媒体 blob URL
      //     永不 revoke（内存单调涨）
      //   * pdf：ResizeObserver/IntersectionObserver 不断开（挂着的元素与
      //     渲染器整棵被观察器引用——无法 GC）；pdf.js 文档/worker 内存
      //     常驻；canvas 后备存储不释放
      // 实测（web-ui/scripts/perf-reload-leak.mjs，Chromium 2048px）：
      // 6 轮 docx↔pdf 重开——现状监听器 remove 恒 0、堆爬到 16MB 不回落；
      // 先 dispose 后 remove 正常累积、堆稳定 12MB。
      try {
        if (tab.dispose) tab.dispose();
      } catch (err) {
        console.warn("ang] dispose", err);
      }
      tab.dispose = null;
      host.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>\u6B63\u5728\u8BFB\u53D6 ' + esc(tab.name) + "\u2026</div></div>";
      try {
        if (tab.kind === "bidwork") {
          // #313 批 A：标书工作台伪标签页——不读文件系统，数据面 bid.state/bid.outline
          renderBidWorkbenchView(tab, host);
        } else if (tab.kind === "text" || tab.kind === "md") {
          const r = await ipc("fs.read", { path: tab.path }, 3e4);
          tab.meta.text = r && typeof r.text === "string" ? r.text : "";
          tab.meta.bytes = r && r.bytes || 0;
          tab.meta.mtimeMs = r && r.mtimeMs || 0;
          if (tab.kind === "md") renderMarkdownView(tab, host);
          else renderTextView(tab, host);
        } else {
          const r = await ipc("fs.readBytes", { path: tab.path }, 9e4);
          tab.meta.bytes = r && r.bytes || 0;
          tab.meta.data = r && r.data || "";
          await renderBinaryView(tab, host);
        }
        tab.state = "ready";
        ui.setStatus({
          saved: "saved",
          savedText: tab.meta.bytes ? fmtBytes(tab.meta.bytes) : "\u5DF2\u4FDD\u5B58",
          message: tab.meta.mtimeMs ? timeAgo(tab.meta.mtimeMs) + "\u66F4\u65B0" : ""
        });
        refreshOutlineIfVisible(); // #54：视图就绪后刷新大纲（md 同步渲染完成面）
        attachAnnotations(tab); // #42 阶段 8：来源标注角标（有边车才有）
      } catch (err) {
        tab.state = "error";
        tab.error = err.message || String(err);
        host.innerHTML = '<div class="view-state" data-kind="error"><div class="view-state-title">\u65E0\u6CD5\u6253\u5F00 ' + esc(tab.name) + "</div><div>" + esc(tab.error) + (err.code ? "\uFF08" + esc(err.code) + "\uFF09" : "") + '</div><button class="btn" data-act="retry">\u91CD\u8BD5</button></div>';
        const rb = host.querySelector('[data-act="retry"]');
        if (rb) rb.addEventListener("click", () => ui.loadTab(tab));
        ui.setStatus({ saved: "error", savedText: "\u52A0\u8F7D\u5931\u8D25", message: "" });
      }
    },
    /**
     * 取/建 Tab 面板。编辑器区是绝对定位的 panes，新建面板后必须立刻隐藏其余
     * 面板，否则两份内容会叠在一起（旧内容的穿透）。
     */
    ensurePane(tab) {
      let pane = document.getElementById("pane-" + tab.id);
      if (!pane) {
        pane = document.createElement("div");
        pane.className = "pane";
        pane.id = "pane-" + tab.id;
        $("#panes").appendChild(pane);
      }
      Array.prototype.forEach.call(document.querySelectorAll("#panes .pane"), (p) => {
        p.hidden = p.id !== "pane-" + tab.id;
      });
      return pane;
    },
    activateTab(id) {
      if (!tabById(id)) return;
      state.activeTabId = id;
      Array.prototype.forEach.call(document.querySelectorAll("#panes .pane"), (p) => {
        p.hidden = p.id !== "pane-" + id;
      });
      renderTabs();
      const tab = tabById(id);
      ui.setStatus({
        cursor: "",
        saved: tab && tab.state === "error" ? "error" : tab && tab.state === "loading" ? "busy" : "saved",
        savedText: tab && tab.meta && tab.meta.bytes ? fmtBytes(tab.meta.bytes) : "\u5DF2\u4FDD\u5B58",
        message: tab && tab.meta && tab.meta.mtimeMs ? timeAgo(tab.meta.mtimeMs) + "\u66F4\u65B0" : ""
      });
    },
    closeTab(id) {
      const tab = tabById(id);
      if (!tab) return;
      try {
        if (tab.dispose) tab.dispose();
      } catch (err) {
        console.warn("[mang] dispose", err);
      }
      const i0 = state.tabs.findIndex((t) => t.id === id);
      state.tabs = state.tabs.filter((t) => t.id !== id);
      const pane = document.getElementById("pane-" + id);
      if (pane && pane.parentNode) pane.parentNode.removeChild(pane);
      if (state.activeTabId === id) {
        const next = state.tabs[i0] || state.tabs[i0 - 1];
        state.activeTabId = next ? next.id : "";
        if (next) {
          Array.prototype.forEach.call(document.querySelectorAll("#panes .pane"), (p) => {
            p.hidden = p.id !== "pane-" + next.id;
          });
        }
      }
      renderTabs();
      renderEmpty();
      renderStatusBar();
    },
    closeActiveTab() {
      if (state.activeTabId) ui.closeTab(state.activeTabId);
    },
    closeOtherTabs() {
      const keep = state.activeTabId;
      state.tabs.filter((t) => t.id !== keep).forEach((t) => ui.closeTab(t.id));
    },
    closeAllTabs() {
      state.tabs.slice().forEach((t) => ui.closeTab(t.id));
    },
    cycleTab(delta) {
      if (state.tabs.length < 2) return;
      const i0 = state.tabs.findIndex((t) => t.id === state.activeTabId);
      const next = (i0 + delta + state.tabs.length) % state.tabs.length;
      ui.activateTab(state.tabs[next].id);
    },
    tabContextMenu(id, x, y) {
      const tab = tabById(id);
      if (!tab) return;
      openContextMenu([
        { label: "\u5173\u95ED", key: "Ctrl+W", act: () => ui.closeTab(id) },
        { label: "\u5173\u95ED\u5176\u4ED6", act: () => {
          state.activeTabId = id;
          ui.closeOtherTabs();
        } },
        { label: "\u5173\u95ED\u5168\u90E8", act: () => ui.closeAllTabs() },
        { sep: true },
        { label: "\u590D\u5236\u8DEF\u5F84", act: () => copyText(tab.path) },
        { sep: true },
        { label: "\u5728\u8D44\u6E90\u7BA1\u7406\u5668\u4E2D\u663E\u793A", act: () => ui.revealPath(tab.path) },
        { label: "\u91CD\u65B0\u52A0\u8F7D", act: () => ui.loadTab(tab) }
      ], x, y);
    },
    fileContextMenu(absPath, x, y) {
      const isMd = /\.(md|markdown)$/i.test(absPath || "");
      const notYet = (what) => () => ui.toast("info", what + "\uFF1A\u7B49\u6D41\u6C34\u7EBF/\u7248\u672C\u5386\u53F2\u63A5\u5165\u540E\u53EF\u7528\uFF08\u6570\u636E\u9762\u5DF2\u5C31\u7EEA\uFF09");
      openContextMenu([
        { label: "\u6253\u5F00", act: () => ui.openPath(absPath) },
        { sep: true },
        { label: "\u751F\u6210 docx", enabled: () => isMd, act: notYet("\u751F\u6210 docx") },
        { label: "\u751F\u6210 PDF", enabled: () => isMd, act: notYet("\u751F\u6210 PDF") },
        { sep: true },
        { label: "\u4FDD\u5B58\u7248\u672C\u5FEB\u7167", enabled: () => snapshotablePath(absPath), act: () => {
          ipc("snapshots.save", { path: absPath }, 2e4).then(() => {
            ui.toast("ok", "\u5DF2\u5B58\u7248\u672C\u5FEB\u7167\uFF1A" + baseName(absPath));
            if (settings.sidebarActive === "changes") ui.loadSnapshots(relOfPath(absPath));
          }).catch((err) => ui.toast("error", "\u5B58\u5FEB\u7167\u5931\u8D25\uFF1A" + (err.message || err)));
        } },
        { label: "\u67E5\u770B\u5386\u53F2", act: () => ui.showHistoryFor(absPath) },
        { sep: true },
        { label: "\u590D\u5236\u8DEF\u5F84", act: () => copyText(absPath) },
        { label: "\u5728\u8D44\u6E90\u7BA1\u7406\u5668\u4E2D\u663E\u793A", act: () => ui.revealPath(absPath) },
        { sep: true },
        { label: "\u5237\u65B0", key: "F5", act: () => ui.refreshTree() }
      ], x, y);
    },
    /** 文件树「查看历史」：切到「改动」面板并列出该文件的版本快照（#42 阶段 7） */
    showHistoryFor(absPath) {
      if (!snapshotablePath(absPath)) {
        ui.toast("info", "\u53EA\u6709\u6587\u672C\u6587\u4EF6\uFF08.md/.txt\uFF09\u6709\u7248\u672C\u5FEB\u7167");
        return;
      }
      settings.sidebarVisible = true;
      settings.sidebarActive = "changes";
      saveSettings();
      applyLayoutSettings();
      syncActivitySelection();
      ui.loadSnapshots(relOfPath(absPath));
    },
    /** 载入某文件的快照列表（改动面板数据源）；file 为空 = 重置 */
    loadSnapshots(file) {
      return loadSnapshotsInto(file);
    },
    // #76 顺手修复：ui.loadGit 自 #42 起被 3 处调用但从未定义——真机壳里
    // 启动 800ms 后必抛 TypeError（console 可见），「改动」面板 git 区永远不加载。
    loadGit() {
      if (!state.bridge || state.bridge.mode !== "host") {
        state.git.available = false;
        state.git.error = "演示模式：无宿主，git 不可用";
        state.git.status = "ready";
        if (settings.sidebarActive === "changes") renderSidebar();
        return;
      }
      if (state.git.status === "loading") return;
      state.git.status = "loading";
      if (settings.sidebarActive === "changes") renderSidebar();
      Promise.all([
        ipc("git.status", {}, 8e3),
        ipc("git.log", { limit: 12 }, 8e3)
      ]).then((r) => {
        const st = r[0] || {}, lg = r[1] || {};
        state.git.available = !!st.available;
        state.git.items = st.items || [];
        state.git.error = st.error || lg.error || "";
        state.git.branch = lg.branch || "";
        state.git.log = lg.items || [];
        state.git.status = "ready";
        if (settings.sidebarActive === "changes") renderSidebar();
      }).catch((e) => {
        state.git.status = "ready";
        state.git.available = false;
        state.git.error = e && e.message || "git 读取失败";
        if (settings.sidebarActive === "changes") renderSidebar();
      });
    },
    revealPath(p0) {
      ipc("explorer.reveal", { path: p0 }, 8e3).catch((err) => ui.toast("error", "\u65E0\u6CD5\u5728\u8D44\u6E90\u7BA1\u7406\u5668\u4E2D\u663E\u793A\uFF1A" + err.message));
    },
    setStatus(patch) {
      Object.assign(state.statusBar, patch);
      renderStatusBar();
    },
    toast(kind, message) {
      return toast(kind, message);
    },
    copyActivePath() {
      const t = activeTab();
      if (t) copyText(t.path);
    },
    saveActive() {
      ui.toast("info", "\u5F53\u524D\u7248\u672C\u4E3A\u53EA\u8BFB\u9884\u89C8\uFF0C\u4FDD\u5B58\u5C06\u5728\u201C\u6587\u6863\u7F16\u8F91\u201D\u9636\u6BB5\u63A5\u5165");
    },
    saveActiveAs() {
      ui.toast("info", "\u53E6\u5B58\u4E3A\u5C06\u5728\u201C\u6587\u6863\u7F16\u8F91\u201D\u9636\u6BB5\u63A5\u5165");
    },
    findInDocument() {
      ui.toast("info", "\u67E5\u627E\uFF1A\u5373\u5C06\u5728\u5F53\u524D\u89C6\u56FE\u91CC\u63D0\u4F9B\uFF08\u4E0B\u4E00\u9636\u6BB5\uFF09");
    },
    quit() {
      // 桌面壳里 window.close() 关不掉宿主窗口（页面不是它自己开的），
      // 必须走壳的 window.action=close；浏览器预览则明确提示，不要静默失败。
      if (state.nativeChrome) {
        ui.winAction("close");
        return;
      }
      window.close();
      ui.toast("info", "\u6D4F\u89C8\u5668\u9884\u89C8\u6A21\u5F0F\u4E0B\u8BF7\u76F4\u63A5\u5173\u95ED\u6807\u7B7E\u9875");
    },
    clearRecent() {
      state.recent = [];
      saveRecent();
      renderHistoryViewIfVisible();
    },
    /** 窗口按钮（最小化 / 最大化还原 / 关闭）——由自绘标题栏调用 */
    winAction(action) {
      ipc("window.action", { action }, 5e3).then((r) => {
        if (r && typeof r.maximized === "boolean") ui.setMaximized(r.maximized);
      }).catch(() => {
        if (action === "close") ui.toast("info", "\u6D4F\u89C8\u5668\u9884\u89C8\u6A21\u5F0F\u4E0B\u4E0D\u5173\u95ED\u7A97\u53E3");
      });
    },
    setMaximized(on) {
      document.documentElement.dataset.maximized = on ? "1" : "0";
      const btn = document.getElementById("btn-win-max");
      if (btn) {
        btn.title = on ? "\u5411\u4E0B\u8FD8\u539F" : "\u6700\u5927\u5316";
        btn.setAttribute("aria-label", on ? "\u5411\u4E0B\u8FD8\u539F" : "\u6700\u5927\u5316");
      }
    },
    /**
     * 标题栏拖动。壳侧默认就把顶部那条高度带当标题栏（WM_NCHITTEST → HTCAPTION），
     * 不依赖 JS 先布防 —— 否则 JS 一出错窗口就拖不动。
     * 这里只在按下位置【不在】菜单栏空白区时临时关掉，避免把侧栏/正文的空白当成拖动。
     */
    onDrop(paths) {
      // R8（#47 / #19 拖拽导入）：向导半完成态（DRAFT 0 文件）接住壳拖入的
      // 招标文件——bid.ingest_drop 复制进工作区根（不导入——导入仍走向导
      // 第二步，用户确认 kind）；非白名单路径照旧 openPath
      const bR8 = state.bid;
      const pR8 = (bR8.data && bR8.data.project) || {};
      const qR8 = (bR8.data && bR8.data.quick_stats) || {};
      if (bR8.status === "ready" && pR8.status === "DRAFT" && !(qR8.files > 0)) {
        const base = (x) => String(x).split(/[\\/]/).pop() || "";
        const bidPaths = paths.filter((x) => BID_IMPORT_EXTS.test(base(x)));
        const others = paths.filter((x) => !bidPaths.includes(x));
        others.forEach((p0) => ui.openPath(p0));
        if (bidPaths.length) ui.ingestDroppedBidFiles(bidPaths);
        return;
      }
      paths.forEach((p0) => ui.openPath(p0));
    },
    /** R8（#47 / #19）：拖入的招标文件落位工作区——bid.ingest_drop（壳侧
     *  复制 + 同名幂等 + 白名单裁决）→ 重拉文件列表 + 新落位件自动勾选
     *  （kind 走启发式预选，用户可改）+ toast 分账（copied/skipped 原因
     *  透传——不静默吞 skipped）。 */
    async ingestDroppedBidFiles(paths) {
      if (!state.bridge || !paths.length) return;
      try {
        const r = await ipc("bid.ingest_drop", { paths: paths }, 6e4);
        const copied = (r && r.copied) || [];
        const skipped = (r && r.skipped) || [];
        // 新落位件自动勾选（rel 即文件名——根下复制）——kind 启发式在
        // renderBidWizardImport 的勾选回调里已同款处理
        for (const c of copied) {
          if (c && c.rel) state.bidWizard.sel[c.rel] = guessBidFileKind(c.rel);
        }
        // 重拉文件列表（treeStatus 重置 idle → 渲染时自动 loadBidWizardTree）
        if (state.bidWizard.treeStatus === "ready") state.bidWizard.treeStatus = "idle";
        if (copied.length) {
          ui.toast("ok", "已落位 " + copied.length + " 件到工作区——请在向导第二步确认 kind 后导入");
        }
        if (skipped.length) {
          ui.toast("warn", "拖入分账：" + skipped.map((s) => (s.detail || s.reason || "")).join("；"));
        }
        renderBidWorkbenchIfOpen();
      } catch (err) {
        ui.toast("warn", "拖入落位失败：" + ((err && (err.message || err.code)) || "bid.ingest_drop 失败"));
      }
    },
    onDroppedFiles(files) {
      files.forEach((f) => {
        const k = kindOf(f.name);
        // R8（#47 / #19 拖拽导入）：向导半完成态 + 招标后缀 → 诚实引导
        // （浏览器 drop 的 File 对象拿不到源路径——落位复制只能在壳侧做，
        // 不静默装作导入成功）
        const bR8w = state.bid;
        const pR8w = (bR8w.data && bR8w.data.project) || {};
        const qR8w = (bR8w.data && bR8w.data.quick_stats) || {};
        if (bR8w.status === "ready" && pR8w.status === "DRAFT" && !(qR8w.files > 0) && BID_IMPORT_EXTS.test(f.name)) {
          ui.toast("warn", "浏览器拖放拿不到文件源路径——把 " + f.name + " 复制进当前工作区目录后点「刷新文件列表」，或用桌面壳直接拖入窗口（自动落位）");
          return;
        }
        if (k !== "text" && k !== "md") {
          ui.toast("warn", "\u6D4F\u89C8\u5668\u5185\u62D6\u653E\u4EC5\u652F\u6301\u6587\u672C\u6587\u4EF6\uFF1B\u684C\u9762\u58F3\u91CC\u53EF\u76F4\u63A5\u62D6\u5165 " + f.name);
          return;
        }
        const rd = new FileReader();
        rd.onload = () => {
          const tab = {
            id: "t" + ++tabSeq,
            path: f.name,
            name: f.name,
            kind: k,
            dirty: false,
            state: "ready",
            error: "",
            meta: { text: String(rd.result || ""), bytes: f.size, mtimeMs: f.lastModified },
            dispose: null
          };
          state.tabs.push(tab);
          state.activeTabId = tab.id;
          renderTabs();
          renderEmpty();
          ui.loadTab(tab);
        };
        rd.readAsText(f, "utf-8");
      });
    },
    showShortcuts() {
      const rows = [
        ["Ctrl+O", "\u6253\u5F00\u6587\u4EF6"],
        ["Ctrl+K Ctrl+O", "\u6253\u5F00\u6587\u4EF6\u5939"],
        ["Ctrl+W", "\u5173\u95ED\u5F53\u524D Tab"],
        ["Ctrl+Tab", "\u4E0B\u4E00\u4E2A Tab\uFF08Shift \u53CD\u5411\uFF09"],
        ["Ctrl+1\u20269", "\u8DF3\u5230\u7B2C N \u4E2A Tab"],
        ["Ctrl+B", "\u663E\u793A / \u9690\u85CF\u4FA7\u680F"],
        ["Ctrl+Shift+E", "\u8D44\u6E90\u7BA1\u7406\u5668"],
        ["Ctrl+Shift+B", "标书面板"],
        ["Ctrl+Shift+H", "\u5386\u53F2"],
        ["Ctrl+Shift+G", "\u6539\u52A8"],
        ["Ctrl+,", "\u8BBE\u7F6E"],
        ["Ctrl+R", "\u91CD\u65B0\u52A0\u8F7D\u754C\u9762"],
        ["F5", "\u5237\u65B0\u6587\u4EF6\u6811"],
        ["Ctrl+F", "\u67E5\u627E"]
      ];
      let table = '<table class="kbd-table">';
      for (const r of rows) table += '<tr><td><span class="kbd">' + esc(r[0]) + "</span></td><td>" + esc(r[1]) + "</td></tr>";
      table += "</table>";
      openModal("\u5FEB\u6377\u952E\u901F\u67E5", table);
    },
    showAbout() {
      const info = state.appInfo || {};
      let html = '<p style="margin:0 0 10px;font-size:13px"><b>mang \u2014 \u6807\u4E66\u5DE5\u4F5C\u53F0</b></p>';
      html += '<table class="kbd-table">';
      html += "<tr><td>\u7248\u672C</td><td>" + esc(info.version || "0.1.0") + "</td></tr>";
      html += '<tr><td>\u5DE5\u4F5C\u533A</td><td style="word-break:break-all">' + esc(state.workspace || "\u2014") + "</td></tr>";
      html += '<tr><td>UI \u76EE\u5F55</td><td style="word-break:break-all">' + esc(info.ui_dir || "\u2014") + "</td></tr>";
      html += "<tr><td>\u8FD0\u884C\u6A21\u5F0F</td><td>" + esc(state.bridge && state.bridge.mode === "host" ? "\u684C\u9762\u58F3\uFF08tao + wry / WebView2\uFF09" : "\u6F14\u793A\u6A21\u5F0F") + "</td></tr>";
      html += "</table>";
      openModal("\u5173\u4E8E mang", html);
    }
  };
  function copyText(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          () => toast("ok", "\u5DF2\u590D\u5236\u8DEF\u5F84"),
          () => toast("error", "\u590D\u5236\u5931\u8D25")
        );
        return;
      }
    } catch (err) {
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      toast("ok", "\u5DF2\u590D\u5236\u8DEF\u5F84");
    } catch (err2) {
      toast("error", "\u590D\u5236\u5931\u8D25");
    }
    document.body.removeChild(ta);
  }
  // #326（R-30/D-01）：链接 URL 协议白名单。
  // esc() 已挡属性级引号/尖括号逃逸，但挡不住 javascript:/data:/vbscript: 协议本身；
  // 大小写不敏感（JaVaScRiPt:），且 URL 规范会剥离首部 C0 控制符与空白
  // （如 "\x01javascript:" 会被浏览器剥成 "javascript:"），所以必须锚定串首逐字符
  // 白名单匹配，黑名单/前缀包含式判断均不可靠。仅放行 http:/https:/mailto:，
  // 其余一律不产出 <a>，降级为纯文本链接文字。
  var SAFE_LINK_SCHEME = /^(?:https?|mailto):/i;
  function mdToHtml(src) {
    const ls = String(src || "").replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let i = 0;
    const inline = (s) => {
      let x = esc(s);
      x = x.replace(/\x60([^\x60]+)\x60/g, "<code>$1</code>");
      x = x.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      x = x.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
      x = x.replace(/~~([^~]+)~~/g, "<del>$1</del>");
      x = x.replace(
        /\[([^\]]+)\]\(([^)\s]+)\)/g,
        (m, txt, url) =>
          SAFE_LINK_SCHEME.test(url)
            ? '<a href="' + url + '" target="_blank" rel="noreferrer">' + txt + "</a>"
            : txt
      );
      return x;
    };
    while (i < ls.length) {
      const line = ls[i];
      const fence = /^\s*(\x60\x60\x60+|~~~+)\s*([\w+-]*)\s*$/.exec(line);
      if (fence) {
        const marker = fence[1].slice(0, 3);
        const body = [];
        i++;
        while (i < ls.length && ls[i].trim().indexOf(marker) !== 0) {
          body.push(ls[i]);
          i++;
        }
        i++;
        out.push("<pre><code>" + esc(body.join("\n")) + "</code></pre>");
        continue;
      }
      const h = /^(#{1,6})\s+(.*)$/.exec(line);
      if (h) {
        const lv = h[1].length;
        out.push("<h" + lv + ">" + inline(h[2]) + "</h" + lv + ">");
        i++;
        continue;
      }
      if (/^\s{0,3}([-*_])(\s*\1){2,}\s*$/.test(line)) {
        out.push("<hr>");
        i++;
        continue;
      }
      if (/^\s*\|/.test(line) && i + 1 < ls.length && /^\s*\|[\s:|-]+\|\s*$/.test(ls[i + 1])) {
        const row = (s) => s.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
        const head = row(line);
        i += 2;
        let th = "";
        let tb = "";
        for (const c of head) th += "<th>" + inline(c) + "</th>";
        while (i < ls.length && /^\s*\|/.test(ls[i])) {
          tb += "<tr>";
          for (const c of row(ls[i])) tb += "<td>" + inline(c) + "</td>";
          tb += "</tr>";
          i++;
        }
        out.push("<table><thead><tr>" + th + "</tr></thead><tbody>" + tb + "</tbody></table>");
        continue;
      }
      if (/^\s*>/.test(line)) {
        let b = "<blockquote>";
        while (i < ls.length && /^\s*>/.test(ls[i])) {
          b += "<p>" + inline(ls[i].replace(/^\s*>\s?/, "")) + "</p>";
          i++;
        }
        b += "</blockquote>";
        out.push(b);
        continue;
      }
      const li = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(line);
      if (li) {
        const ordered = /\d/.test(li[2]);
        const items = [];
        while (i < ls.length) {
          const m = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(ls[i]);
          if (!m) break;
          let text = m[3];
          let cls = "";
          const task = /^\[( |x|X)\]\s+(.*)$/.exec(text);
          if (task) {
            text = '<input type="checkbox" disabled' + (task[1].toLowerCase() === "x" ? " checked" : "") + "> " + esc(task[2]);
            cls = ' class="md-task"';
          } else {
            text = inline(text);
          }
          items.push("<li" + cls + ">" + text + "</li>");
          i++;
        }
        out.push(ordered ? "<ol>" + items.join("") + "</ol>" : "<ul>" + items.join("") + "</ul>");
        continue;
      }
      if (line.trim() === "") {
        i++;
        continue;
      }
      const para = [line];
      i++;
      while (i < ls.length && ls[i].trim() !== "" && !/^(#{1,6})\s|^>|^\||^```|^[-*+]\s|^\d+[.)]\s/.test(ls[i])) {
        para.push(ls[i]);
        i++;
      }
      out.push("<p>" + para.map(inline).join("<br>") + "</p>");
    }
    // #42 阶段 8：顶层块编号（data-block-id=b1..bN）——docx 渲染器同款钩子，
    // 证据角标按块定位。out 的每项都是一个完整顶层元素，往首标签注入属性即可。
    for (let k = 0; k < out.length; k++) {
      const m = /^<([a-zA-Z][a-zA-Z0-9]*)([^>]*)>/.exec(out[k]);
      if (!m) continue;
      out[k] = "<" + m[1] + ' data-block-id="b' + (k + 1) + '"' + m[2] + ">" + out[k].slice(m[0].length);
    }
    return out.join("\n");
  }
  function renderMarkdownView(tab, host) {
    const text = tab.meta && typeof tab.meta.text === "string" ? tab.meta.text : "";
    const mode = tab.meta.viewMode || "preview";
    host.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = mode === "preview" ? "md-view" : "text-view";
    const bar = document.createElement("div");
    bar.className = "view-toolbar";
    bar.innerHTML = '<div class="seg"><button data-mode="preview" aria-pressed="' + String(mode === "preview") + '">\u9884\u89C8</button><button data-mode="source" aria-pressed="' + String(mode === "source") + '">\u6E90\u7801</button></div><span class="view-toolbar-info">Markdown \xB7 ' + esc(fmtBytes(tab.meta.bytes || text.length)) + "</span>";
    wrap.appendChild(bar);
    bar.addEventListener("click", (e) => {
      const b = e.target.closest("[data-mode]");
      if (!b) return;
      tab.meta.viewMode = b.dataset.mode;
      renderMarkdownView(tab, host);
    });
    if (mode === "preview") {
      const scroll = document.createElement("div");
      scroll.className = "view-scroll";
      const doc = document.createElement("div");
      doc.className = "md-doc";
      doc.innerHTML = mdToHtml(text);
      scroll.appendChild(doc);
      wrap.appendChild(scroll);
      doc.addEventListener("click", (e) => {
        const a = e.target.closest("a");
        if (a) {
          e.preventDefault();
          ui.toast("info", "\u5916\u90E8\u94FE\u63A5\uFF1A" + a.getAttribute("href"));
        }
      });
    } else {
      const scroll = document.createElement("div");
      scroll.className = "text-scroll";
      const body = document.createElement("div");
      body.className = "text-body";
      const ls = text.split("\n");
      if (settings.showLineNumbers) {
        const gutter = document.createElement("div");
        gutter.className = "text-gutter";
        const nums = [];
        for (let n = 1; n <= ls.length; n++) nums.push(n);
        gutter.textContent = nums.join("\n");
        body.appendChild(gutter);
      }
      const linesEl = document.createElement("div");
      linesEl.className = "text-lines";
      ls.forEach((ln, idx) => {
        const div = document.createElement("div");
        div.className = "text-line";
        div.dataset.line = String(idx + 1);
        div.textContent = ln === "" ? "\u200B" : ln;
        linesEl.appendChild(div);
      });
      body.appendChild(linesEl);
      scroll.appendChild(body);
      wrap.appendChild(scroll);
    }
    host.appendChild(wrap);
  }
  var RENDERER_MODULES = ["docx_view", "xlsx_view", "pdf_view"];
  var rendererPromises = /* @__PURE__ */ Object.create(null);
  function loadRenderer(name) {
    if (rendererPromises[name]) return rendererPromises[name];
    if (RENDERER_MODULES.indexOf(name) < 0) {
      return Promise.reject(Object.assign(new Error("\u672A\u77E5\u6E32\u67D3\u5668\uFF1A" + name), { code: "renderer_missing" }));
    }
    const ready = window.__mangRenderers && window.__mangRenderers[name];
    if (ready) return Promise.resolve(ready);
    rendererPromises[name] = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = name + ".js";
      script.charset = "utf-8";
      script.onload = () => {
        const api = window.__mangRenderers && window.__mangRenderers[name];
        if (api) return resolve(api);
        delete rendererPromises[name];
        reject(Object.assign(new Error("\u6E32\u67D3\u5668 " + name + ".js \u6CA1\u6709\u5BFC\u51FA\u63A5\u53E3"), { code: "renderer_missing" }));
      };
      script.onerror = () => {
        delete rendererPromises[name];
        reject(Object.assign(new Error("\u6E32\u67D3\u5668\u6A21\u5757 " + name + ".js \u52A0\u8F7D\u5931\u8D25"), { code: "renderer_missing" }));
      };
      document.head.appendChild(script);
    });
    return rendererPromises[name];
  }
  function decodeB64ToBytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function renderTextView(tab, host) {
    const text = tab.meta && typeof tab.meta.text === "string" ? tab.meta.text : "";
    host.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "text-view";
    const ls = text.split("\n");
    const bar = document.createElement("div");
    bar.className = "view-toolbar";
    bar.innerHTML = '<span class="view-toolbar-info" style="margin-left:0">' + esc(tab.name) + " \xB7 " + esc(fmtBytes(tab.meta.bytes || text.length)) + " \xB7 " + ls.length + " \u884C</span>";
    const scroll = document.createElement("div");
    scroll.className = "text-scroll";
    const body = document.createElement("div");
    body.className = "text-body";
    if (settings.showLineNumbers) {
      const gutter = document.createElement("div");
      gutter.className = "text-gutter";
      const nums = [];
      for (let n = 1; n <= ls.length; n++) nums.push(n);
      gutter.textContent = nums.join("\n");
      body.appendChild(gutter);
    }
    const linesEl = document.createElement("div");
    linesEl.className = "text-lines";
    linesEl.style.whiteSpace = settings.wordWrap ? "pre-wrap" : "pre";
    ls.forEach((ln, idx) => {
      const div = document.createElement("div");
      div.className = "text-line";
      div.dataset.line = String(idx + 1);
      div.textContent = ln === "" ? "\u200B" : ln;
      linesEl.appendChild(div);
    });
    body.appendChild(linesEl);
    scroll.appendChild(body);
    wrap.appendChild(bar);
    wrap.appendChild(scroll);
    scroll.addEventListener("mousedown", (e) => {
      const ln = e.target.closest(".text-line");
      if (!ln) return;
      const rect = ln.getBoundingClientRect();
      const ch = Math.max(1, Math.round((e.clientX - rect.left) / 7.8));
      ui.setStatus({ cursor: "\u884C " + ln.dataset.line + ", \u5217 " + ch });
    });
    host.appendChild(wrap);
  }
  var RENDERER_HINT = { docx: "docx_view.js", xlsx: "xlsx_view.js", pdf: "pdf_view.js" };
  async function renderBinaryView(tab, host) {
    const bytes = decodeB64ToBytes(tab.meta.data || "");
    host.innerHTML = '<div class="view-state"><div class="view-spinner"></div><div>\u6B63\u5728\u6E32\u67D3 ' + esc(tab.name) + "\u2026</div></div>";
    try {
      if (tab.kind === "docx") {
        const mod = await loadRenderer("docx_view");
        if (typeof mod.renderDocx !== "function") throw new Error("docx_view \u7F3A\u5C11 renderDocx \u5BFC\u51FA");
        host.innerHTML = "";
        // #54：docx 滚动容器（docx_view 自述「滚动归宿主外层滚动器」——
        // 修复「docx 滚不动」）。注意分层：scroll 是宿主建的外层滚动器，
        // hostEl 是渲染根（renderDocx 会给它加 [data-mang-renderer] 并注入
        // overflow:visible——不能让滚动容器本身当 host，否则 auto 被覆盖）。
        const scroll = document.createElement("div");
        scroll.className = "view-scroll";
        const hostEl = document.createElement("div");
        scroll.appendChild(hostEl);
        host.appendChild(scroll);
        // 页码状态：构建完成报首页，滚动实时报当前页（对齐 PDF 口径）；
        // mount 完成时同步刷新大纲（docx DOM 异步构建——此时标题才可收集）
        const r = mod.renderDocx(bytes, hostEl, {
          theme: state.theme,
          onStatus: (s) => {
            ui.setStatus({ cursor: "\u7B2C " + s.page + " / " + s.pages + " \u9875" });
            if (s.page === 1) refreshOutlineIfVisible();
          }
        });
        tab.dispose = () => r && r.dispose && r.dispose();
        tab.meta.view = null; // docx 页跳转走 DOM 查询（.mang-docx-page[data-page]）
        const w = r && r.stats && r.stats.warnings;
        if (w && w.length) ui.toast("warn", "Word \u6E32\u67D3\u63D0\u793A\uFF1A" + w.slice(0, 3).join("\uFF1B"));
        return;
      }
      if (tab.kind === "xlsx") {
        const mod = await loadRenderer("xlsx_view");
        if (typeof mod.createXlsxView !== "function") throw new Error("xlsx_view \u7F3A\u5C11 createXlsxView \u5BFC\u51FA");
        host.innerHTML = "";
        const r = mod.createXlsxView(host, bytes, {
          theme: state.theme,
          onStatus: (s) => ui.setStatus({ cursor: (s.sheet || "") + "  " + (s.row || 0) + ":" + (s.col || 0) + (s.cell ? "  " + s.cell : "") })
        });
        tab.dispose = () => r && r.dispose && r.dispose();
        return;
      }
      if (tab.kind === "pdf") {
        const mod = await loadRenderer("pdf_view");
        if (typeof mod.createPdfView !== "function") throw new Error("pdf_view \u7F3A\u5C11 createPdfView \u5BFC\u51FA");
        host.innerHTML = "";
        const r = await mod.createPdfView(host, bytes, {
          theme: state.theme,
          onStatus: (s) => ui.setStatus({ cursor: "\u7B2C " + s.page + " / " + s.pages + " \u9875 \xB7 " + Math.round((s.zoom || 1) * 100) + "%" })
        });
        tab.dispose = () => r && r.dispose && r.dispose();
        tab.meta.view = r; // #54 页码跳转：goToPage API
        return;
      }
      throw new Error("\u672A\u77E5\u7684\u6587\u4EF6\u7C7B\u578B\uFF1A" + tab.kind);
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      const missing = e && e.code === "renderer_missing" || /加载失败|Cannot find module|404/i.test(msg);
      host.innerHTML = '<div class="view-state" data-kind="error"><div class="view-state-title">\u65E0\u6CD5\u6E32\u67D3 ' + esc(tab.name) + "</div><div>" + esc(missing ? "\u6E32\u67D3\u5668\u6A21\u5757 " + (RENDERER_HINT[tab.kind] || "") + " \u672A\u627E\u5230\uFF08\u8BF7\u91CD\u65B0\u6784\u5EFA dist\uFF09" : msg) + "</div></div>";
    }
  }
  try {
    boot();
  } catch (err) {
    console.error("[mang] \u542F\u52A8\u5931\u8D25", err);
    const box = document.getElementById("empty");
    if (box) {
      box.hidden = false;
      box.innerHTML = '<div class="view-state" data-kind="error" style="position:relative"><div class="view-state-title">\u754C\u9762\u542F\u52A8\u5931\u8D25</div><div>' + String(err && err.message ? err.message : err) + "</div></div>";
    }
  }
  setTimeout(function() {
    if (state.bridge && state.bridge.mode === "host") ui.loadGit();
  }, 800);
  // #42 阶段 7：版本快照——按设置间隔检查打开的文本文件（内容有变才存），开场 6s 先来一版
  setTimeout(snapshotTick, 6e3);
  armSnapshotTimer();
  window.__mang = { state, ui, settings, ipc };
})();
