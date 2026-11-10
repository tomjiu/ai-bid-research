# mang IPC 契约 v1

> 实现：`bidcore/crates/mang-app/`（tao + wry / WebView2）
> 本文是**唯一权威**：字段名、单位、错误码以这里为准。改了代码要同步改这里。

---

## 0. 一句话

UI 页（`dist/mang/index.html`）通过 `window.ipc.postMessage(JSON.stringify(req))` 发请求；壳把结果以**注入脚本**的形式注入回页面：`window.__ipcResolve(id, resp, ok)`；事件走 `window.__ipcEvent(ev)`。

```
UI 页 (mang://localhost/mang/index.html)
   │  window.ipc.postMessage('{"id":"r1","cmd":"fs.read","path":"a.md"}')
   ▼
wry with_ipc_handler  ──►  ipc::parse → Ctx::dispatch → 响应帧 JSON
   │
   ▼  evaluate_script
try{window.__ipcResolve&&window.__ipcResolve("r1", {…}, true);}catch(e){}
```

---

## 1. 加载与 URL

壳用 `WebViewBuilder::with_url("mang://localhost/mang/index.html")`，custom protocol `mang` 的根是 **UI 目录**（默认 `web-ui/dist`）。

| 请求路径 | 文件 |
|---|---|
| `mang://localhost/mang/index.html` | `<ui>/mang/index.html` |
| `mang://localhost/mang/app.js` | `<ui>/mang/app.js` |
| `mang://localhost/mang/pdf.worker.min.mjs` | `<ui>/mang/pdf.worker.min.mjs` |
| `mang://localhost/__ipc/<id>.json` | 大响应临时文件（见 §4） |

### ⚠ Windows 上的协议改写（**最容易踩的坑**）

wry 在 Windows 上把自定义协议改写成 http 形式（WebView2 限制）：

```
mang://localhost/mang/index.html  →  http://mang.localhost/mang/index.html
```

所以页面里 **`location.origin === "http://mang.localhost"`**。由此两条规则：

1. **页面内 fetch 大响应必须用相对路径**：`fetch('/__ipc/' + file)`。
   `fetch('mang://localhost/__ipc/…')` 会 `TypeError: Failed to fetch`（不会被拦截）。
2. **导航白名单必须同时放行两种形态**，否则主页面会被自己拦掉、WebView 停在 `about:blank`：
   `mang://localhost…`、`mang.localhost…`、`http://mang.localhost…`、`https://mang.localhost…`

壳内部按 `req.uri().path()` 匹配，改写前后都能命中。

### MIME

`.html` → `text/html; charset=utf-8`；`.js/.mjs` → `text/javascript; charset=utf-8`；`.css`；`.json/.map`；`.wasm` → `application/wasm`；`.svg/.png/.jpg/.gif/.webp/.ico`；`.woff/.woff2/.ttf/.otf`；`.pdf`；`.md/.txt`。**其它一律 `application/octet-stream`**（`.bcmap`、`.pfb` 走这条）。

目录穿越（解析后不在 UI 根下）→ `403`；找不到 → 回退 `index.html`（前端路由友好）。

---

## 2. 请求

```jsonc
{ "id": "r1", "cmd": "fs.read", "path": "技术标.md" }
```

- `id`：字符串（建议 `"r" + ++seq`）。缺省为 `null`（仍会回帧，`id:null`）。
- `cmd`：见 §6 命令表。
- 其余字段：命令参数，**平铺在顶层**（不嵌套）。
- 多余字段被忽略（永不因多余参数报错）。
- **壳永不 panic**：坏 JSON → `bad_json`；参数类型不对 → `bad_args`；未知命令 → `unknown_cmd`。

---

## 3. 响应

### 3.1 成功

```js
try{window.__ipcResolve&&window.__ipcResolve("r1", {"id":"r1","ok":true,"result":{…},"data":{…}}, true);}catch(e){}
```

帧体：`{"id", "ok":true, "result":{…}, "data":{…}}`

`result` 与 `data` **内容相同**（兼容两种读法）。`ok` 在函数第三个参数上再给一遍。

### 3.2 失败

```jsonc
{ "id": "r2", "ok": false,
  "code": "outside_workspace", "message": "路径越界：…",
  "error": { "code": "outside_workspace", "message": "路径越界：…" } }
```

错误帧**同时**给顶层 `code`/`message` 和嵌套 `error:{code,message}`。

### 3.3 错误码

| code | 含义 | 典型触发 |
|---|---|---|
| `bad_json` | 请求不是合法 JSON / 不是对象 | 手抖拼错 |
| `bad_args` | 参数缺失或类型不对 | `fs.read` 无 `path` |
| `unknown_cmd` | 没有这个命令 | `nope.cmd` |
| `not_found` | 路径不存在 | 文件被删/改名 |
| `state` | bid 项目未到该命令的状态窗（工具面 E_STATE 透传） | 矩阵未建时 `bid.quality` / `bid.score` |
| `denied` | 存在但越权（写工作区非 `.mang/`、拒绝访问） | `fs.writeBytes` 写正文 |
| `outside_workspace` | 解析后不在工作区内（`../` 穿越、盘符外绝对路径） | 安全拦截 |
| `too_large` | 超过该命令的体积上限 | 50MB 的 pdf 用 `fs.read` |
| `io` | 其它系统 IO 失败 | 磁盘满、权限 |
| `state` | 工具面 E_STATE 透传：当前项目状态不允许该操作（#313 批 C/D）——UI 应分支「尚未开放」引导卡而非错误横幅 | DRAFT 态项目调 `bid.coverage`（未导入文件） |

---

## 4. 大响应（> 1.5 MB）

阈值 `INLINE_LIMIT = 1_500_000` 字节（按响应体 JSON 序列化后计）。

1. 壳把**完整响应帧**写到 `%TEMP%\mang-ipc\<safe_id>.json`（UTF-8，就是那个响应帧本身）。
2. 内联帧变成：

```json
{ "id": "r7", "ok": true, "result": { "file": "r7.json", "bytes": 2796354, "inline": false }, "data": { …同上… } }
```

> `result.bytes` = 整个响应帧 JSON 序列化后的字节数（**不是**原文件大小）。判断是否走了落盘请认 `result.inline === false`
> 且 `result.file` 是**纯文件名**（不含 `:`、`/`）。`recent.load` 的 `file` 是磁盘路径，**不要**拿去 fetch。

3. UI 用**相对路径**取回（同一 origin，只服务一次）：

```js
const url = '/__ipc/' + resp.result.file;      // → http://mang.localhost/__ipc/r7.json
const full = await (await fetch(url)).json();  // 与内联时那个帧完全一致：{id, ok, result, data}
```

4. 壳**读一次即删**；第二次取回 `404`，body 为 `gone`。
5. 启动时清理上一轮遗留的 `%TEMP%\mang-ipc\*.json`；退出前也清。
6. `safe_id` 只保留 `[A-Za-z0-9_-]`（其它字符换 `_`），最长 120；服务端只接受纯文件名，`../` 与分隔符一律拒绝。

> 判定依据是**实际写盘的字节数**，不是预估：小响应永远内联。

实测：2 MB 文件 → 响应 2,796,354 B → 落盘 → fetch#1 200 解码 2,097,153 B → fetch#2 404 `gone`。

---
## 5. 路径与安全围栏

解析顺序（`paths::Workspace::resolve`）：

1. 空串 → 工作区根。
2. 相对路径 → 以工作区根为基准（`/` 与 `\` 都当分隔符；`.` 忽略，`..` 逐段回退）。
3. 绝对路径 → 原样使用（对话框/拖拽/最近打开来的）。
4. `canonicalize`；**目标不存在时** canonicalize 最近的存在祖先，再拼回剩余段（支持“新建文件”路径）。
5. 结果必须位于 canonical 工作区根之下 → 否则 `outside_workspace`。

**比较按路径组件、大小写不敏感**（Windows 语义）：`C:\ws2` 不会被当成 `C:\ws` 的子目录；`C:\WS\x` 在 `C:\ws` 内。

写权限：`fs.writeBytes` **只允许写工作区内的 `.mang/`**（历史快照/导出中间件）。正文保存要另开命令并带显式授权——不要顺手放宽这条。

**`.mang/` 懒创建**：启动时**不**建 `<ws>/.mang`；只有真正写历史时才创建目录（工作区常是 git 跟踪的 fixture 目录）。

---

## 6. 命令表

单位约定：`size`/`bytes` = 字节；`mtimeMs`/`ts`/`openedAt` = **Unix 毫秒**（UTC）；`rel` = 相对工作区、**`/` 分隔**；绝对路径用 `\`。

### ping
```jsonc
→ { "pong": true, "t": 1793260341382 }
```

### app.info
```jsonc
→ {
  "version": "0.1.0",
  "workspace": "E:\\Code\\ai\\md\\audit\\ai-bid-research\\fixtures\\corpus-A",
  "ui_dir": "E:\\Code\\ai\\md\\audit\\ai-bid-research\\web-ui\\dist",
  "exe": "E:\\…\\bidcore\\target\\release\\mang-app.exe",
  "pid": 4236,
  "platform": "windows",
  "protocol": 1,
  "git_rev": "73e2697",          // #76：build.rs 注入（git 不可用时 "unknown"）
  "build_epoch": 1793260341,      // #76：构建 Unix 秒（前端 Date 渲染本地时区）
  "profile": "release"           // #76：debug | release
}
```

### fs.tree  `{ path?, depth?=8, includeHidden?=false }`

- `depth`：1~32（默认 8）。
- 排序：**目录在前**，同类**自然排序**（`第2章` 在 `第10章` 前、`a2` 在 `a10` 前）。
- 永远跳过：`.git` / `node_modules` / `target` / `.mang` / `$recycle.bin`。
- `includeHidden=false`（默认）时跳过所有以 `.` 开头的条目。
- 单目录读失败（权限）只跳过该目录，不失败整棵树。
- 节点上限 4000：超出置 `truncated:true`（先序遍历，先满足目录）。

```jsonc
→ {
  "root": "E:\\…\\fixtures\\corpus-A",
  "path": "",                       // 入参 path 原样回显，根目录为 ""
  "nodes": [
    { "name": "files", "rel": "files", "kind": "dir", "mtimeMs": 1793015364734,
      "children": 1,                 // = 子节点个数（number）
      "nodes": [                     // = 子节点数组（真正的 children）
        { "name": "B3-图纸目录.xlsx", "rel": "files/B3-图纸目录.xlsx", "kind": "file",
          "size": 6168, "mtimeMs": 1793015364738 }
      ] },
    { "name": "manifest.json", "rel": "manifest.json", "kind": "file", "size": 10794, "mtimeMs": 1793015364734 }
  ],
  "nodeCount": 29,
  "nodeCap": 4000,
  "truncated": false
}
```

> 目录节点：`children`=个数（number）、`nodes`=子数组；文件节点没有这两个键。

### workspace.current / workspace.open  `{ path }`  （#194）

运行期切换工作区（= 切换标书项目：`.mang/llm.json`、`.mang/history/`、`db.json`
都在工作区根下，换根即换项目）。此前 `Ctx.workspace` 不可变，只能退出重开。

```jsonc
← { "cmd": "workspace.current" }
→ { "root": "D:\\项目B", "canonical": "\\\\?\\D:\\项目B" }

← { "cmd": "workspace.open", "path": "D:\\项目B" }
→ { "root": "D:\\项目B", "previous": "D:\\项目A", "changed": true }
```

- 校验复用启动同一套（`Workspace::new`：canonicalize + is_dir）——目录不存在
  `not_found`、给的是文件 `bad_args`，**失败不换根**（现工作区不受影响）。
- 成功即换根 + 落盘 `%APPDATA%\mang\last-workspace.json`（重启无参启动时
  停在上次的工作区；CLI 显式参数仍最高优先）。记忆失败不阻断切换。
- `changed=false` 表示重复打开当前工作区（幂等，UI 不弹提示）。
- 切换后 UI 侧应：关全部 Tab（旧文件句柄失效）→ 重拉 `fs.tree` / `recent.load`
  → 清 git/快照会话态 → 刷新状态栏（`app.info` 的 `workspace` 字段随新根）。

### fs.read  `{ path }` — 文本
上限 **8 MB**（超了 `too_large`）。UTF-8 **lossy** 解码（坏字节换成 U+FFFD，不报错）。

```jsonc
→ { "path": "E:\\…\\技术标.md", "rel": "技术标.md", "bytes": 1620,
    "text": "# 第一章 概述\n\n正文。\n", "mtimeMs": 1793015364726 }
```

### fs.readBytes  `{ path }` — 二进制
上限 **48 MB**。`data` 为标准 base64（带 `=` 填充）。

```jsonc
→ { "path": "E:\\…\\B3-图纸目录.xlsx", "rel": "files/B3-图纸目录.xlsx",
    "bytes": 6168, "enc": "b64", "data": "UEsDBBQ…", "mtimeMs": 1793015364738 }
```

> >1.5 MB 时走 §4：`result = {file, bytes, inline:false}`。

### fs.writeBytes  `{ path, enc:"b64", data }` — 只写 `.mang/`
```jsonc
→ { "path": "E:\\…\\.mang\\history\\技术标.md\\1.md", "rel": ".mang/history/技术标.md/1.md", "bytes": 13 }
```
非 `.mang/` → `denied`；越界 → `outside_workspace`；坏 b64 → `bad_args`；上限 64 MB。落盘**先写 `.tmp` 再 rename**。

### fs.stat  `{ path }`
不存在**不报错**，返回 `exists:false`。
```jsonc
→ { "path": "E:\\…\\files", "rel": "files", "size": 0, "mtimeMs": 1793015364734, "isDir": true, "exists": true }
```

### fs.mkdir  `{ path }`
`create_dir_all`，父目录一起建。→ `{ "ok": true, "path": "…", "rel": "新目录/子" }`

### file.fromPath  `{ path }` — 绝对路径归一
拖拽 / 对话框 / 最近打开给的绝对路径 → 统一描述。会展开 `%VAR%` 与开头 `~`。不在工作区时 `rel:null、insideWorkspace:false`（**不报错**）。
```jsonc
→ { "path": "D:\\项目A\\技术标.md", "rel": "技术标.md", "kind": "file",
    "size": 1620, "mtimeMs": 1793015364726, "insideWorkspace": true }
```

### dialog.openFile  `{ filters?, title?, multiple?=true, directory? }`
`filters: [{"name":"Word","extensions":["docx","md"]}]`（扩展名带不带点都行，`*` 忽略）。**主线程同步弹模态**（Win32 `IFileOpenDialog`，rfd）。
```jsonc
→ { "paths": ["D:\\项目A\\技术标.md"], "canceled": false }
```

### dialog.openFolder  `{ title?, directory? }`
```jsonc
→ { "paths": ["D:\\项目A"], "canceled": false }
```
取消时 `{"paths":[],"canceled":true}`（不是错误）。

> **阻塞语义**：这两个命令在主线程同步弹模态，会阻塞 UI 线程直到用户选完/取消（浏览器模态同理）。
> IPC 线程永不阻塞；对话框任务通过主线程队列串行执行。
> 无头环境设 `MANG_DIALOG_MOCK=1` 可让它们立即返回取消。

### explorer.reveal  `{ path }`
`explorer /select,"<path>"`（`CREATE_NO_WINDOW`）；目录则直接打开；路径不存在则打开最近的存在的父目录。→ `{ "ok": true, "path": "…" }`

### mcp.status  —— MCP 通道自检（#76 设置面板）
只读，无参数。bid-mcp 是 **stdio 传输**（AI 客户端拉起 `bid-mcp-stdio` 子进程），本壳不监听端口，无地址/端口面；`ready` 是本壳内嵌引擎（直链 bidcore，方案 A）的 dispatch 自检——未知工具探测必须应答 `E_NOTFOUND` JSON 帧（#325：线格式钉回契约字面量）。
```jsonc
→ { "channel": "stdio",
    "server": "bid-mcp-stdio（由 MCP 客户端拉起；本壳不监听端口）",
    "protocol": "JSONL over stdio",
    "tools": 13, "implemented": 11,
    "ready": true, "probe": "dispatch 应答正常",
    "engine": "本壳直链 bidcore（方案 A），与 bid-mcp 同源" }
```

### llm.status  —— LLM 配置 + 用量（只读；#76）
读 `<workspace>/.mang/llm.json` + `.mang/llm-usage.json`，按引擎同一套 resolve 规则（env 覆盖文件）报告**生效模式**。文件缺失不是错误。**api_key 只出掩码，绝不回明文**（对面是 WebView）。
```jsonc
→ { "file": "E:\\…\\.mang\\llm.json", "file_present": true,
    "api_base": "https://api.deepseek.com/v1", "model": "deepseek-chat",
    "timeout_secs": 60, "temperature": 0.3, "max_tokens_cap": 8192,
    "has_api_key": true, "api_key_hint": "sk-***cdef", "key_from_env": false,
    "effective": "real",            // "real" | "mock（未配置 api_key，自动降级）" | "配置错误"
    "resolve_error": null,
    "usage_file": "E:\\…\\.mang\\llm-usage.json",
    "usage": { "calls": 3, "prompt_tokens": 1200, "completion_tokens": 800,
               "total_tokens": 2000, "last_at": 1793260341 } }
```

### llm.save  `{ apiBase?, apiKey?, model?, timeoutSecs?, temperature?, maxTokensCap?, clearApiKey? }`（#76）
合并写 `.mang/llm.json`：**省略 = 保持原值**；`clearApiKey:true` = 移除 key；`apiKey:""` = 清空 key。写后 resolve 验证（有 key 缺 model → `bad_args` 且**回滚到写前文件**）。成功响应不含 key。
```jsonc
→ { "ok": true, "file": "E:\\…\\.mang\\llm.json", "effective": "real", "saved_key": true }
```

### llm.test  —— 连接测试（异步事件回执；#76）
**不在 IPC 线程同步跑**（HTTP 最长 20s）：立即回 `{ "started": true, "note": "…" }`，真实结果以 `llm.test` **事件**送达（见 §7）。超时上限压到 20s（配置的 60s 是给整章生成的余量）。最小请求：`max_tokens=16`，提示「请只回复 OK」。

### fspec.status  —— 格式规范只读摘要（#76）
读 `<workspace>/.mang/format-spec.json`（引擎同源 serde 面）。缺失/坏 JSON 都不是错误（缺失本身就是要显示的状态）。
```jsonc
→ { "present": true, "invalid": false, "bytes": 402,
    "page": { "size": "A4", "margin_mm": { "top": 25, "bottom": 25, "left": 28, "right": 26 } },
    "font": { "body": "仿宋_GB2312", "size_pt": 12.0, "line_height": 1.5 },
    "per_section_overrides": 1,
    "path": "E:\\…\\.mang\\format-spec.json",
    "hint": "由 MCP 管线（import_tender_files → extract）从招标文件推导落盘" }
// 缺失：{ "present": false, "path": …, "hint": … }；坏 JSON：{ "present": true, "invalid": true, "error": "…" }
```

### bid.state —— 标书项目状态 / 门审 / 快速统计（只读；#313 批 A）
读当前工作区 `db.json` 的真实项目态。主体经 `bid_mcp::dispatch_with(get_bid_project_state)`
走真实工具面（与 bid-mcp-stdio 同源裁决，方案 A 直链），工具输出原样放 `state` 键。
**无 db.json → `not_found`（干净拒绝，不在工作区落任何副作用）**；db.json 损坏 → `bad_json`。
```jsonc
→ { "present": true,
    "workspace": "D:\\项目A", "db": "D:\\项目A\\db.json",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "code": "", "mode": "明标",
                  "status": "DRAFTING" },
    "state": { …get_bid_project_state 工具输出原样（status / allowed_next_tools /
               terminal / dirty_sections / pending_rewrite_directives / content_binding /
               agent_waivers / human_review_complete）… },
    "quick_stats": {
      "requirements": 1120, "evidence": 13, "evidence_bindings": 46,
      "sections": 26, "sections_leaf": 20, "sections_drafted": 12,
      "sections_accepted": 3, "sections_failed": 1, "sections_dirty": 2,
      "target_total_chars": 150000, "actual_total_chars": 81200,
      "pages_estimate": 97 } }   // 页数 = ceil(实际字数 / 844)——域层 CHARS_PER_PAGE
```

### bid.outline —— 标书章节树（只读；#313 批 A）
DomainStore 直读章节树（MCP 工具面无此视图）。节点按 `order` 升序；
`actual_chars`：叶 = 正文字符数、结构节点 = 后代叶之和（与 target_chars
「父 = 子配额和」同口径）；`chapter_file`（相对工作区、`/` 分隔）仅在
`chapters/{id}.json` 真实存在时给出——UI 用它 `fs.read` 跳转章节详情。
无 db.json / 无项目 → `not_found`；有项目无大纲 → `nodes: []`（不是错误）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "nodes": [
      { "id": "SEC-0001", "parent_id": null, "title": "第一章 技术方案", "level": 1,
        "order": 1, "status": "DRAFTING", "dirty": false, "target_chars": 15000,
        "actual_chars": 12000, "req_count": 8, "is_leaf": false, "has_content": false,
        "content_attempt": 0, "chapter_file": null },
      { "id": "SEC-0002", "parent_id": "SEC-0001", "title": "1.1 技术参数", "level": 2,
        "order": 2, "status": "DRAFTED", "dirty": true, "target_chars": 6000,
        "actual_chars": 5000, "req_count": 5, "is_leaf": true, "has_content": true,
        "content_attempt": 2, "chapter_file": "chapters/SEC-0002.json" } ],
    "stats": { …同 bid.state.quick_stats 的章节面字段（不含 requirements/evidence）… } }
```

> 服务缓存（壳内）：按「工作区根 + db.json 指纹（mtime+size）」绑定——
> `workspace.open` 切根或外部进程（bid-mcp-stdio / Agent）改写 db.json 后，
> 下一条 bid.* 命令自动重开，无需重启。

### bid.matrix —— 合规矩阵全量（只读；#313 批 B）
经 `bid_mcp::dispatch_with(get_compliance_matrix)` 走真实工具面（与
bid-mcp-stdio 同源裁决，方案 A 直链）。工具面按 S-4 游标分页（limit ≤1000、
游标绑过滤器指纹与数据版本）——壳内循 `next_cursor` 聚合**全量行**后一次
返回（聚合护栏 200 页；行形状 = 工具输出原样透传，见契约 §4
`get_compliance_matrix` 的 rows 元素），UI 面的 blocking/状态/类别筛选、
分页、导出都在全量行上做（计数与表格同一真源）。无 db.json → `not_found`。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "rows": [
      { "cmp_id": "CMP-0001",
        "requirement": { "id": "REQ-0001", "clause_no": "3.2.1", "category": "技术参数",
                         "category_key": "tech_param", "statement": "投标人须提供…",
                         "mandatory": false,
                         "source_anchor": { "file": "A-招标文件.docx", "kind": "para",
                                            "locator": "第三章 3.2/REQ-0001", "excerpt": "…" },
                         "params": { } },
        "status": "NOT_RESPONDED",            // RESPONDED|NOT_RESPONDED|PARTIAL|NOT_APPLICABLE|PENDING_EVIDENCE
        "evidence": [ { "ev_id": "EV-0001", "title": "…", "status": "ACTIVE",
                        "valid_until": "2027-06-30", "verification_tier": "SELF_TEST" } ],
        "pending_evidence_ids": [ ],          // #245 占位/待核验证据（待补可追踪）
        "evidence_required": false,           // #241 证据要求面（类别 ∪ 原文要求词）
        "evidence_missing": false,            // #241 证据缺口（正交于 status）
        "substantive": false,                 // #276 ★实质性条款识别列
        "gap": null, "response_policy": "default",
        "draft_section_id": "SEC-0002",       // 响应章节（大纲树 requirement_ids 反查，最深层优先）
        "blocking": true } ],                 // 必选未响应/待补 → 阻断导出（R-03/R-04 + #245）
    "total": 1120,
    "summary": { "by_status": { "NOT_RESPONDED": 80, "RESPONDED": 1000, "PARTIAL": 12,
                                "NOT_APPLICABLE": 8, "PENDING_EVIDENCE": 20 }, // 五态恒在（0 兜底）
                 "blocking": 21, "mandatory": 30, "substantive": 48, "evidence_missing": 40 },
    "star_summary": { …工具面原样（total/responded/partial/not_responded/
                      not_applicable/responded_share/note——#276 ★统计口）… },
    "warnings": [ ],                          // 如 EMPTY_MATRIX: 条款集为空
    "project_version": 12, "fetched_pages": 2 }
```
### bid.quality —— 质量覆盖度检查（只读；#313 批 C）
主体经 `bid_mcp::dispatch_with(check_bid_quality)` 走真实工具面（与 bid-mcp-stdio
同源裁决），工具输出原样放 `quality` 键（summary 起草/失败/未覆盖/带外/无锚/查重/
字数偏离、needs_human、submission_readiness【#241 两分账：导出可过而提交未就绪
是合法状态】、sections 逐章明细、global_conflicts【#423 金额/工期/术语/承诺跨章
冲突】、negative_deviations【A-07 负偏离】、artifact 报告落盘位置、warnings）。
服务缓存与批 A 同款（工作区根 + db.json 指纹）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "quality": { …check_bid_quality 工具输出原样（project_id / summary /
               needs_human / submission_readiness / sections / global_conflicts /
               negative_deviations / artifact / warnings / request_id）… } }
```
拒绝面：无 db.json → `not_found`；项目未到 MatrixReady+ 或无章节树 →
**`state`**（工具面 E_STATE 原文透传，如
「REQUIREMENTS_EXTRACTED 态无章节树——先建纲再查质量」——UI 据此分支成
「尚未开放」引导卡，不是故障）。

### bid.score —— 全文档规则自评（只读；#313 批 C）
主体经 `bid_mcp::dispatch_with(score_document)` 走真实工具面，工具输出原样放
`score` 键（`diagnostic_only`/`result_kind`【#186 语义降级：规则诊断非评标模拟——
UI 必须原样展示徽章】、technical / commercial / price / total / target / gap、
by_item 逐项明细【estimated / tier / coverage / contributions / rule_checkpoints】、
mappings【#224 双向追溯】、unmapped_scoring_items、notes、sections_scored）。
**范围纪律：本命令不带价格推演入参**（bid_price / method 等——报价试算走既有
`score_price` 工具）；未报价时 `score.price` 为 **null**（诚实显示「价格分不计」，
不伪缺 0）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "score": { …score_document 工具输出原样（diagnostic_only=true /
             result_kind="rule_heuristic" / technical / commercial / price /
             total / target / gap / by_item / breakdown / mappings /
             unmapped_scoring_items / notes / price_input / sections_scored）… } }
```
拒绝面与 `bid.quality` 同：`not_found` / `state`。

### bid.gates —— 审核门台账（只读；#603 批 A——治理面）
DomainStore 直读（`bid.outline` 先例——MCP 工具面无此整面视图，单一真源
`gate_approved` / `latest_gate_pass` / `agent_gate_passes` /
`human_review_complete` / `reviews`）：五门（matrix_approval / outline_approval /
pre_export_confirm / addendum_waiver / no_addendum_confirmed）approved 状态、
每门最新过门记录（method=human_receipt|agent_declared、human_confirmed——追认后
最新条翻 human 的判据位）、agent 豁免清单（human_confirmed=false 的门——导出
警告与追认清单素材）、human_review_complete（空账本或全 human → true）、
reviews 裁决历史（倒序，REV 记录含 #182 可信身份回显与 #180 内容绑定摘要）。
**读面无状态窗**：早期态「三门全未过」也是有效数据（写面才有域层状态窗裁决）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "gates": [ { "gate": "matrix_approval", "title": "矩阵定稿门",
                 "note": "门序第一：…", "approved": true,
                 "latest_pass": { "gate": "matrix_approval", "actor": "agent-01",
                                  "actor_type": "agent", "method": "agent_declared",
                                  "human_confirmed": false, "at": 1790000000,
                                  "reason": "…" } }, … 共 5 门 … ],
    "human_review_complete": false,
    "agent_waivers": [ …每门最新一条 human_confirmed=false 的过门记录… ],
    "reviews": [ { "id": "REV-0002", "gate": "outline_approval", "decision": "APPROVED",
                   "reviewer": "agent:agent-01",
                   "actor": { "actor_id": "agent-01", "actor_type": "agent",
                              "authentication_method": "hmac_receipt_v2" },
                   "findings": [], "at": 1790000000,
                   "reviewed_content_digest": "…" } ] }
```
拒绝面：无 db.json → `not_found`（不落副作用）。

### bid.gate_pass —— 人工过门（写面；#603 批 A——治理面写面首发）
`{ gate, decision, findings?, reason?, actor_id?, project_version? }`

流程（#182 宿主签发面——**不进 MCP 工具表，Agent 拿不到**）：壳内真人经 UI
确认后，壳用服务态密钥签 receipt（scope 绑本门——A 门 receipt 过不了 B 门；
#323 内容绑定当前章节树摘要——签发后章节被改 → 域层 ContentDrifted 拒），
经 `bid_mcp::dispatch_with(record_review_gate)` 走真实工具面落账，工具输出
原样放 `gate_pass` 键（receipt 回执 / gates_approved / agent_waivers /
human_review_complete / status）。门序（矩阵→大纲→导出确认）/ 状态窗
（matrix 门 MATRIX_READY+）/ 幂等 / 追认 / BLOCKER 强制派生 RT 全在域层裁决
——壳侧零重实现，拒绝文案原样透传（不假成功）。

参数：`gate` = matrix_approval|outline_approval|pre_export_confirm|addendum_waiver
（no_addendum_confirmed 走 record_addendum_waiver 的 confirm_no_addendum 路径，
#603 批 C 接线）；`decision` = APPROVED|REJECTED；`findings` =
`[{severity, code, message, section_id?}]`（Rejected 必须含 ≥1 BLOCKER）；
`reason`（human 路径可空）；`actor_id`（宿主身份命名，缺省 `shell-operator`）；
`project_version`（可选 CAS）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "gate_pass": { "receipt": { "review_id": "REV-0003", "gate": "matrix_approval",
                    "decision": "APPROVED", "reviewer": "human:shell-operator",
                    "actor": { "actor_id": "shell-operator", "actor_type": "human",
                               "authentication_method": "hmac_receipt_v2" },
                    "method": "human_receipt", "human_confirmed": true,
                    "finding_ids": [], "spawned_rt_ids": [],
                    "reviewed_content_digest": "…" },
                   "gates_approved": ["matrix_approval"],
                   "agent_waivers": [], "human_review_complete": true,
                   "status": "MATRIX_READY", "project_version": 4 } }
```
拒绝面：无 db.json → `not_found`；状态窗未到 / 门序未满足 → **`state`**（域层
E_STATE 原文，如「当前状态 REQUIREMENTS_EXTRACTED 不允许调用
record_review(matrix_approval)」）；Rejected 无 BLOCKER / 非法门名 / receipt
过期漂移 → **`bad_args`**（E_UNPROCESSABLE 原文）。


### bid.coverage —— 覆盖报告 + ★条款覆盖（只读；#313 批 D）
主体经 `bid_mcp::dispatch_with(get_coverage_report)` 走真实工具面（与
bid-mcp-stdio 同源裁决，方案 A 直链），工具输出原样放 `coverage` 键（字段见
契约 §19：complete / total_blocks / covered_blocks / uncovered_range_count /
unjudged_blocks / files[]（含逐文件 uncovered_ranges——每文件至多 50 段）/
next——建纲门引导）。壳侧 `summary` 在工具输出上现算**三态分账**（#244——
每块必居其一）：`judged_blocks`（A 已判定 = covered − Σ excluded；
covered 是 A+B 合计）、`excluded_blocks`（B 已排除 = Σ files[].excluded_blocks）、
`unjudged_blocks`（C 未判定，原样）——三者和恒等于 total_blocks；
`by_verdict` 逐文件聚合（requirement / review_table / noise / rule）。
★条款覆盖循 `get_star_coverage`（#285 逐文件只读面）对 `coverage.files[]`
聚合进 `star`——**只取计数**（star_truth / star_captured / star_missing /
declarations；口径恒等式 truth = captured + missing），逐块明细走 bid-mcp
工具面不进本响应。无 db.json → `not_found`；DRAFT 态（未导入文件）工具面
E_STATE 透传为 `state` 错误码（§3.3——UI 分支「尚未开放」卡）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "coverage": { …get_coverage_report 工具输出原样（complete/total_blocks/
                  covered_blocks/uncovered_range_count/unjudged_blocks/
                  files[]{file_id,total_blocks,covered_blocks,complete,
                  uncovered_ranges[](≤50 段),uncovered_range_count,
                  excluded_blocks,unjudged_blocks,by_verdict}/next… },
    "summary": { "total_blocks": 1240, "judged_blocks": 1120,        // A：已判定为要求
                 "excluded_blocks": 40,                              // B：noise/rule 排除
                 "unjudged_blocks": 80,                              // C：没标记——建纲门阻断
                 "uncovered_range_count": 2, "complete": false,
                 "by_verdict": { "requirement": 1080, "review_table": 40, "noise": 40 } },
    "star": { "files": [ { "file_id": "TF-0001", "file_name": "A-招标文件.docx",
                            "star_total": 50, "declarations": 2,    // 样板句★（声明不计条款）
                            "star_truth": 48, "star_captured": 45, "star_missing": 3,
                            "next": "有★漏标——…" } ],
              "total": { "star_total": 50, "declarations": 2,
                         "star_truth": 48, "star_captured": 45, "star_missing": 3 } } }
```

### recent.load / recent.save `{ items }`
文件 `%APPDATA%\mang\recent.json`（缺失退回 LOCALAPPDATA → TEMP），最多 50 条，按 `openedAt` 倒序。同一 `path` 只留最新一条。写盘先 `.tmp` 再 rename。
```jsonc
recent.load → { "items": [ { "path":"D:\\项目A\\技术标.md", "name":"技术标.md",
                            "kind":"file", "openedAt":1699999999000, "exists":true } ],
                "file": "C:\\Users\\…\\AppData\\Roaming\\mang\\recent.json" }
recent.save → { "ok": true, "count": 1, "file": "…\\recent.json" }
```

### history.list  `{ path?, limit?=200 }`
读 `<workspace>/.mang/history/index.json`，容忍三种形态：数组 `[entry]`、`{"items":[entry]}`、**按文件分组** `{"技术标.md":[entry]}`。`kind`：`"manual"`（AI 主动存，也接受 `"ai"`）或 `"auto"`。
```jsonc
→ { "items": [ { "ts": 1699999999000, "kind": "manual", "message": "第1章 概述完成",
                 "file": "技术标.md", "snapshot": ".mang/history/技术标.md/1699999999000.md" } ],
    "file": "E:\\…\\.mang\\history\\index.json", "present": true }
```
文件不存在：`{items:[], present:false}`；坏 JSON：`{items:[], present:true, error:"…"}`（都不报错）。

### preview.write  `{ name, enc:"b64", data }`
写 `%TEMP%\mang-preview\<uuid>-<name>`，给大文件在页面里预览（不碰工作区）。文件名清洗掉 `/ \ : * ? " < > |` 与控制字符。上限 48 MB。
```jsonc
→ { "path": "C:\\temp\\mang-preview\\3f2a…-报价单.xlsx", "bytes": 18320, "name": "报价单.xlsx" }
```

---
### git.log  `{ path?, limit?=80 }` —— 提交列表（只读，「改动/历史」面板）
系统 `git` 子进程实现（不引 libgit2）；`core.quotepath=off` 保证中文路径原样；输出用 RS(0x1e)/US(0x1f) 分隔符解析，永不 panic。`limit` 夹取 1..=200。
```jsonc
→ { "available": true, "branch": "main",
    "items": [ { "hash": "…", "short": "a1b2c3d", "author": "张三",
                 "ts": 1699999999000, "subject": "fix: 报价表公式" } ] }
```
非 git 仓库 / git 不在 PATH：`{ "available": false, "items": [], "error": "…" }`——**不报错**（面板显示提示）。`path` 过路径围栏（必须在围栏内，`E_FENCE`）。

### git.show  `{ hash, path? }` —— 单提交 diff（只读）
`hash` 须 ≥4 位十六进制（否则 `bad_args`）；`--stat` 摘要 + patch 全文。
```jsonc
→ { "hash": "a1b2c3d…", "patch": "commit a1b2c3d…\nAuthor: …\n\n 1 file changed, 2 insertions(+)" }
```

### git.status  `{ path? }` —— 工作区未提交改动（只读）
`--porcelain=v1 --untracked-files=normal`；逐行 XY 码 + 路径。
```jsonc
→ { "available": true, "items": [ { "code": " M", "path": "技术标.md" },
                                   { "code": "??", "path": "新资料/" } ] }
```
失败面同 git.log（`available:false + error`，不报错）。

### snapshots.check  `{ paths: […] }` —— 批量自动快照探测（#42 阶段 7）
对每个文件问 mang-snap「该存吗」（内容指纹没变 → Skipped）。整批围栏失败报错；单条结果分双列：
```jsonc
→ { "saved":   [ { "file": "技术标.md", "ts": 1699999999000 } ],
    "skipped": [ { "file": "README.md", "reason": "内容未变化" } ] }
```

### snapshots.save  `{ path, message?, kind? }` —— 手动/AI 存版本
与 bid-mcp `save_version` **同一真源**（mang-snap）。`kind`：`"manual"`（缺省）/ `"ai"`；`message` 缺省空串。
```jsonc
→ { "ok": true, "file": "技术标.md", "ts": 1699999999000,
    "snapshot": ".mang/history/技术标.md/1699999999000.md" }
```

### snapshots.read  `{ file, snapshot }` —— 版本预览（只读）
```jsonc
→ { "file": "技术标.md", "snapshot": "1699999999000", "content": "…全文…", "bytes": 12345 }
```

### snapshots.rollback  `{ file, snapshot }` —— 回滚（安全序）
**先把当前内容存成回滚前备份**（backupTs——回错了还能再滚回来），再覆盖目标文件：
```jsonc
→ { "ok": true, "file": "技术标.md", "snapshot": "1699999999000",
    "bytes": 12345, "backupTs": 1700000000000 }
```

### annotations.load  `{ path }` —— 来源标注浮层数据（只读，#42 阶段 8）
边车 `.mang/annotations/<file_key>.json`——**浮层是覆盖层，绝不修改文件正文**。
```jsonc
→ { "file": "技术标.md", "present": true,
    "items": [ { "id": "1", "block": "b3", "quote": "本次方案采用分布式架构",
                 "source": { "file": "招标文件.docx", "page": 12, "section": "3.2",
                             "quote": "投标人须提供分布式架构方案" },
                 "status": "confirmed", "note": "" } ] }
```

### annotations.setStatus  `{ path, id, status }` —— 标注认校验三态落盘
`status`：`"confirmed" | "pending" | "rejected"`（三态枚举外拒）；原子读-改-写。
```jsonc
→ { "ok": true }
```

### window.info  `{}` —— 窗口状态（自绘标题栏）
```jsonc
→ { "maximized": false, "captionHeight": 32, "native": true }
```

### window.action  `{ action }` —— 窗口动作（七动作枚举）
`action`：`minimize | maximize | restore | toggle | close | drag | toggleMaximize`（枚举外 `bad_args`）。直接在 UI 线程操作 HWND（不走事件循环 recv——历史教训：同线程等自己 = 每次点击卡 1.5s）。状态即时回推，UI 图标随之切换（不读 window.info 避免旧值）：
```jsonc
→ { "action": "maximize", "applied": true, "maximized": true }
```

### window.buttons  `{ width }` —— 窗口按钮区宽度上报
UI 上报右上角三按钮占宽；标题栏右端这一段必须让位（不能返回 HTCAPTION，否则点最大化会变成拖窗口）：
```jsonc
→ { "width": 138 }
```

### bid.validate  `{}` —— 标书校验报告（写面：推进 VALIDATING；#18 出口闭环）
主体经 `bid_mcp::dispatch_with(validate_bid_document)` 走真实工具面（与
bid-mcp-stdio 同源裁决），UI 入口固定 `scope=all`（sections 细分是代理高级面）。
工具面**会推进项目至 VALIDATING**（域层语义，壳不拦截）。无章节树 → E_STATE
透传 `state` 码（§3.3——UI「校验尚未开放」引导卡）；无 db.json → `not_found`。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "VALIDATING" },
    "report": { …validate_bid_document 工具输出原样（ok / errors[]（BLOCKER+MAJOR）/
                warnings[]（MINOR）/ findings[] / counts{blocker,major,minor,
                deterministic,model} / rules_profile…） } }
```

### bid.export  `{ format, output_path, dark_bid?, bidder_name? }` —— 标书导出落盘（写面；#18 出口闭环）
主体经 `bid_mcp::dispatch_with(export_bid_document)` 走真实工具面：双前置门
（校验通过 + pre_export_confirm 过门确认）由工具面裁决，E_STATE 原文含状态与
前置说明，透传 `state` 码（UI「导出被前置门拦截」引导卡）。`format` 限
`docx | pdf`（pdf 需 Word/LibreOffice 转换通道，环境缺失 → `bad_args` 响亮拒）；
`output_path` 必须是**工作区相对路径**（绝对路径 / 含 `..` → 工具面 `bad_args`，
防导出产物写任意盘位）。幂等：同 (项目, 内容版本, 格式, 路径, 报价决策) 重放
直返首次结果（`deduplicated:true`，零 IO）。产物定位：前端拿
`export.artifact.url`（工作区内绝对路径，`explorer.reveal` 放行）调
`explorer.reveal`。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "EXPORTED" },
    "export": { …export_bid_document 工具输出原样（artifact{url,sha256,size} /
                chapters_written / total_chars / dark_bid? / warnings[] /
                deduplicated?…） } }
```
拒绝面：未过双前置门 → `state`（E_STATE 原文）；format/output_path 非法 →
`bad_args`；无 db.json → `not_found`。


## 7. 事件（无 id）

```js
try{window.__ipcEvent&&window.__ipcEvent({…});}catch(e){}
```

### drop —— Windows 拖放（`WM_DROPFILES` + `SetWindowSubclass`）
```jsonc
{ "ev": "drop",
  "paths": ["D:\\项目A\\技术标.md", "C:\\Users\\x\\桌面\\a.pdf"],      // 绝对路径，已去掉 \\?\ 前缀
  "within": [ { "path": "D:\\项目A\\技术标.md", "rel": "技术标.md" } ],  // 仅工作区内的
  "ts": 1793260341382 }
```
- 工作区内的文件才出现在 `within`；外部的只进 `paths`（UI 用 `file.fromPath` 归一）。
- 必须 `DragFinish`（已做），否则系统资源泄漏。
- 回调在 UI 线程，只做“入队 + 唤醒”，真正注入由事件循环统一做。
- 自测：`mang-app.exe --inject-drop "D:\a.docx;D:\b.xlsx"` 会在启动 1.5s 后推一条同样的 drop 事件（已验证能直接开出两个 Tab）。

### llm.test —— LLM 连接测试结果（#76，后台线程发出）
`llm.test` 命令的异步回执（命令本身只回「已启动」）。
```jsonc
{ "ev": "llm.test", "ok": true, "stage": "http",        // stage: config | network | http
  "message": "模型 deepseek-chat 应答正常", "sample": "OK" }
// 失败：{ "ev": "llm.test", "ok": false, "stage": "config", "message": "未配置 api_key（auto 模式将降级 mock）…" }
```

---

## 8. 页面侧需要提供的两个函数

```js
window.__ipcResolve = function (id, resp, ok) { /* resp 是完整帧；ok 是布尔副本 */ };
window.__ipcEvent   = function (ev) { /* drop / theme … */ };
```
壳的注入**永远**带 `window.__ipcResolve&&` 守卫 + `try/catch`：函数没定义就静默跳过，抛异常也只吞掉，绝不影响页面。

壳另外在文档创建时设置 `window.__mangShell = {version:1, protocol:1}`（仅用于“我跑在壳里”检测）。

---

## 9. 命令行

```
mang-app.exe [DIR] [选项]

  -w, --workspace <DIR>   工作区目录（默认当前目录）。也可直接 mang-app.exe DIR
      --ui <DIR>          UI 目录（默认：<exe>/ui → <exe>/../../../web-ui/dist → ./web-ui/dist → ./dist）
      --devtools          启用 DevTools
      --selftest          不开窗口跑 IPC 自检，打印 PASS/FAIL，退出码 0=全过
      --ls-ui             只打印解析出的 UI 目录然后退出
      --inject-drop <P1;P2> 启动 1.5s 后模拟一次拖放（无鼠标环境验证 DnD）
  -h, --help              帮助
```

环境变量：
- `MANG_DIALOG_MOCK=1`：不弹真实系统对话框，`dialog.*` 直接返回 `{paths:[], canceled:true, mock:true}`（无头自检/CI）。
- `MANG_DEVTOOLS=1`：等价于 `--devtools`。
- `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=<N>`：打开 WebView2 CDP（冒烟脚本用）。

- 位置参数与 `--workspace` 同给时 **`--workspace` 优先**。
- 未知选项 → 打印用法 + 退出码 **2**；工作区不存在 → 退出码 **1**。
- 窗口：标题 `mang — 标书工作台`，初始 1440×900，**最小 1024×640**。

---

## 10. 自检

```
bidcore\target\release\mang-app.exe --selftest
```

无窗口跑：ping / app.info / fs.tree / fs.read / fs.readBytes / 大响应落盘取回删除 / fs.writeBytes(允许+拒绝) / fs.stat / fs.mkdir / 路径围栏 5 例 / recent 往返 / history.list / unknown_cmd / bad_json / 启动清理 / mcp.status / llm.status→save→status 往返（掩码+拒绝+清 key）/ fspec.status（缺文件/在场）/ bid.state+bid.outline（#313 批 A：无 db.json→not_found / 真实项目 / db.json 外部变更后缓存重开）/ bid.matrix（#313 批 B：无 db.json→not_found / 真实项目 / db.json 变更后缓存重开与阻断计数）/ bid.coverage（#313 批 D：无 db.json→not_found / 未导入件诚实口径 total_blocks=0+next 引导）/ workspace.open+current（#194：切换/新根命令面/幂等/记忆/失败不换根）。输出 `PASS <name>：<detail>` / `FAIL …`，最后 `== N passed, M failed ==`。

窗口内 IPC 冒烟（真实 WebView2，走 CDP）：
```
node scripts/mang-dev/mang_ipc_smoke.mjs
```

---

## 11. 开发脚本

| 脚本 | 作用 |
|---|---|
| `scripts/mang-dev/mang_dev.ps1 build` | 结束占用进程 + `cargo build --release -p mang-app` |
| `scripts/mang-dev/mang_dev.ps1 selftest` | 跑 `--selftest` |
| `scripts/mang-dev/mang_dev.ps1 ui` | 打印解析出的 UI 目录 |
| `scripts/mang-dev/mang_dev.ps1 run [工作区]` | 启动 |
| `scripts/mang-dev/mang_ipc_smoke.mjs` | 真实窗口 IPC 冒烟（造临时工作区 + 探针 UI，CDP 驱动） |
| `scripts/mang-dev/mang_ipc_probe.js` | 冒烟用页面探针（被 smoke.mjs 拷进临时 UI） |

退出码：`0` 全过 / `1` 有失败 / `2` 环境问题（找不到 exe 或页面）。

用法：`node scripts/mang-dev/mang_ipc_smoke.mjs [--ui DIR] [--workspace DIR] [--port N] [--keep]`
