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
| `conflict` | 乐观并发 CAS 过期（工具面 E_CONFLICT 透传——#89 批 2 起；此前落 `io` 码）——重读后重试，不是故障 | `bid.segment` rewrite 的 `expected_version` / `project_version` 落后 |
| `denied` | 存在但越权（写工作区非 `.mang/`、拒绝访问） | `fs.writeBytes` 写正文 |
| `outside_workspace` | 解析后不在工作区内（`../` 穿越、盘符外绝对路径） | 安全拦截 |
| `too_large` | 超过该命令的体积上限 | 50MB 的 pdf 用 `fs.read` |
| `io` | 其它系统 IO 失败 | 磁盘满、权限 |
| `state` | 工具面 E_STATE 透传：当前项目状态不允许该操作（#313 批 C/D）——UI 应分支「尚未开放」引导卡而非错误横幅 | DRAFT 态项目调 `bid.coverage`（未导入文件） |

### 3.4 引导卡约定（E_NOTFOUND / E_STATE 的 UI 呈现规范；#47 R6 / #19 任务 3）

全部 `bid.*` 读面板（detail / matrix / quality / gates / coverage / export）收到壳侧 `not_found` / `state` 码时，**渲染引导卡而非错误横幅**——空态与早态是用户主路径不是故障，`data-kind="error"` 横幅只留给真故障（`io` / `bad_json` 等）。

| 码 | 卡面标题 | 主行动（`data-bid-guide-cta`） | 次行动（`data-bid-guide-retry`） |
|---|---|---|---|
| `not_found`（无 db.json） | 还没有标书项目 | 去新建标书项目 → 切 detail 页签（向导第一步） | 重新检查（重发原命令） |
| `state`（状态窗未到） | XX 尚未开放（XX = 面板名） | 去导入招标文件 → 切 detail 页签（向导第二步） | 重新检查（重发原命令） |

- 卡尾一律带 `bid-cov-next`（`data-state="ok"`）「下一步」条：写明到达状态窗的后继管线动作（extract_requirements → build_outline → prepare_outline_and_matrix 等）。
- 单一真源在 `code` 不在文案：`state` 码时 E_STATE 原文（含状态与前置说明）原样进卡，不吞不译。
- 实现锚点：`renderBidEarlyGuide`（`web-ui/mang/app.js` 共享工厂——coverage R5 首创，R6 收编 matrix / quality / gates 并统一锚点）。

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

**绝对路径的判定是平台语义**（R2，#47 平台区分①）：盘符形态 `C:/…` 在 Windows 是绝对路径（→ 越界 `outside_workspace`）；在 Unix 是**合法相对路径**（`C:` 只是普通目录名，围栏内解析，目标不存在 → `not_found`）。两端行为不同且**都正确**——前端不要在 Unix 上把 `C:/` 形态当越界报错渲染，也不要在 Windows 上把它当相对路径拼接。

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
- **深度截断也亮旗（R18，#47 截断诚实面）**：到达 `depth` 上限的目录若
  实际有**可收录**条目（按同一套过滤口径：隐藏/SKIP_DIRS/非常规文件不
  算），同样置 `truncated:true`——旧实现静默空导致消费方把「看不见」当
  「没有」（向导宣称「工作区里没有可导入的文件」/侧栏宣称「工作区是空
  的」）。探测只看一层、不耗节点预算、不建节点（深度上限语义不变）。
  消费方契约：`truncated:true` 时**不得宣称「空」/「全部」**（向导与
  侧栏已接警示横幅——`bidWizTruncBanner` / `tree-trunc-warn`）。

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
      "files": 4,                        // #19：导入文件计数（向导判「DRAFT 且未导入」用）
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

### bid.price —— 评分推演（score_price 试算/反推 + score_section 章节细查；#89 R30）
两动作面（`action`，缺省 `trial`）：
- **`trial`**：`bid_mcp::dispatch_with(score_price)` 纯计算器——method /
  coefficient / max_score / budget / deviation / bid_price / others **原样透传**
  （值域与裁决全在 B1 解析/validate 层，壳不重复）。试算（「这么报得几分」）
  + 反推（「最优报多少」）可同场；纯推荐无竞争报价 → B1 响亮拒（不给半答案）。
- **`section`**：`bid_mcp::dispatch_with(score_section)` 章节响应诊断——
  `section_id` 必填（壳侧早拒 `bad_args`，不进工具面），`project_version`
  （CAS）可选透传；未起草叶 / 结构节点 / 幽灵章节由工具面拒。
与 `bid.score` 的分界：那是整卷体检（score_document），本命令是报价决策 +
单章推演（决策发生在起草前后都成立——trial 无状态门）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "action": "trial",
    "price": { …score_price 工具输出原样（score / max_score / optimal_price /
             expected_score_at_optimal / detail.benchmark_price / analysis /
             warnings）… } }
→ { "action": "section", "section": { …score_section 工具输出原样
    （diagnostic_only=true / tier / score / target / hits /
     unmapped_scoring_items【#224 文档级缺口单章也可见】）… } }
```
拒绝面：`bad_args`（action/入参/值域——E_UNPROCESSABLE 透射）/
`not_found`（无 db.json / 幽灵章节）。

### bid.performance —— 业绩材料库（list / register / recommend / write；#89 批 2）
四动作面（`action`，缺省 `list`）——#315 四工具的壳聚合：
- **`list`**：`bid_mcp::dispatch_with(list_performance)` 库清单只读——
  `filters`（category/keyword/min_amount_wan/max_amount_wan/since）+ `limit`
  **原样透传**（值域与非法值拒绝在工具面单一真源）。
- **`register`**：`bid_mcp::dispatch_with(register_performance)` 批量登记——
  `entries`（1..=200 条对象数组）+ `owner_name`（库主/证据主体名）透传；
  语义四元组（名称+客户+金额+竣工日期）幂等，重放回显既有 id；一条非法
  整批拒（零副作用）。
- **`recommend`**：`bid_mcp::dispatch_with(recommend_performance)` 只读匹配
  推荐——`budget_wan`/`base_date`/`client_type`/`focus`/`top_k` 透传（全
  可选：缺的因子弃权重归一），`project_id` 恒壳侧覆写；语料 = 项目名 +
  REQ 陈述 + 评分项原文，响应带 `suggested_section`（大纲含业绩/类似项目
  标题的叶；无则 null + `next` 引导）。
- **`write`**：`bid_mcp::dispatch_with(write_performance_section)` 一键写入
  业绩章节——`section_id` **必填**（壳侧早拒 `bad_args`），`perf_ids` /
  `bid_open_date` / `project_version` 透传。证据自动登记绑定（材料文件名
  命中已导入件）+ 业绩表/描述段单段写入（幂等键 `perf-section:<sid>`）；
  readiness 门（可用业绩证据 < 3）拦写入并把材料指引带全（诚实面）。

**壳面与工具面的路由差异（诚实登记）**：工具面 register/list 无项目路由
（库是跨项目资产，建项目前可维护）；壳面恒在已打开项目的工作区上下文
（`ensure_locked` 要求 db.json——与其他 bid.* 同轨），但**库本身跨项目**
（BID_PERF_LIB → 用户级库位 `~/.mang/performance-library.json`，与项目
db.json 无关——换项目不换库）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "action": "list",
    "library": { …list_performance 工具输出原样（entries[] / returned /
                owner_name / library_persisted）… } }
→ { "action": "register", "register": { …added / added_count / deduplicated /
    total_entries / library_persisted / next… } }
→ { "action": "recommend", "recommend": { …recommendations[]（perf_id/score/
    factors/reasons）/ library_total / signals / suggested_section / next… } }
→ { "action": "write", "write": { …section_id / segment_id / changed /
    evidence_registered[] / materials_pending[] / bindings[] / warnings… } }
```
拒绝面：`bad_args`（action/入参/值域/空调用——E_UNPROCESSABLE 透射）/
`not_found`（无 db.json）/ `state`（recommend 需 REQUIREMENTS_EXTRACTED+，
write 需 MATRIX_READY+——E_STATE 透射）。

### bid.segment —— 分段改写（list 段账本 / rewrite 局部修订；#89 批 2）
两动作面（`action`，缺省 `list`）——#254 段账本工具面的壳聚合：
- **`list`**：`bid_mcp::dispatch_with(list_section_segments)` 段账本发现面
  （只读）——`section_id` **必填**（壳侧早拒 `bad_args`），`project_version`
  可选透传。段清单（id/seq/version/chars/idem_key/preview）+ 合稿统计
  （assembled/target/remaining/over_target——续写前「已写到哪」的对账）。
- **`rewrite`**：`bid_mcp::dispatch_with(rewrite_section_segment)` 局部修订
  ——`segment_id` + `content` **必填**（壳侧早拒；空白 content 同拒），
  `expected_version`（段级 CAS，可选）+ `project_version`（项目级 CAS，
  可选）透传。改指定段不动兄弟段（**整段替换语义**）；同内容重写账面
  零变动（`changed=false`）。

与整稿起草（draft_response_section / 章节详情）的分界：那是「从无到有写
整章」，本命令是「已起草章节的局部迭代」——长章节续写改写的主工作面。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "action": "list",
    "segments": { …list_section_segments 工具输出原样（section_id /
                 segments[] / assembled_chars / target_chars /
                 remaining_chars / over_target）… } }
→ { "action": "rewrite", "rewrite": { …section_id / segment{id,seq,version,
    chars} / changed / deduplicated / assembled_chars / citations /
    unanchored_claims / warnings… } }
```
拒绝面：`bad_args`（action/缺参/空白 content）/ `not_found`（无 db.json /
幽灵章节/幽灵段）/ **`conflict`**（CAS 过期——expected_version 或
project_version 落后；重读后重试，不是故障）/ `state`（需 MATRIX_READY+）。

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

### bid.star_gaps —— ★漏标明细（只读；#47 R27 / #88 Q2 兜底数据源）
逐文件循 `get_star_coverage`（#285）真实工具面（与 `bid.coverage` 的 `star`
计数面同源单真源），**只含有漏标的文件**进 `star_gaps.files[]`——每件含
`missing[]` 明细（工具面 MAX_STAR_DETAIL=100 条封顶 + `missing_truncated` 旗
原样透传；每条 block_idx / locator / page / line / stars / text / reason）、
`warnings`（REQ 空引导「先抽取再查」/ 表格行装配提示）、`next`（补标引导）。
壳侧每条 `text` 截断 120 chars（chars 计，截断追加「…」——防 IPC 膨胀）。
汇总 `total`（star_truth / star_captured / star_missing / files_with_gaps，
与 coverage().star.total 同口径可对账）；`checked_files` 已检文件数**含无漏标
件**（分母诚实）；`all_clear` = 全部已检文件无漏标（导出兜底 UI 直通行据）。
无 db.json → `not_found`；DRAFT 态（未导入）工具面 get_coverage_report
E_STATE 透传为 `state` 码（§3.3——UI 分支「尚未开放」卡）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "star_gaps": { "files": [ { "file_id": "TF-0001", "file_name": "A-招标文件.docx",
                                 "star_truth": 48, "star_captured": 45, "star_missing": 3,
                                 "missing": [ { "block_idx": 207, "locator": "第19页 行6",
                                                 "page": 19, "line": 6, "stars": 1,
                                                 "text": "★网络直连功能：可通过网线传输…",
                                                 "reason": "该块未产生任何 REQ" } ],
                                 "missing_truncated": false,
                                 "warnings": [], "next": "有★漏标——用 missing[].block_idx 定位后 submit_block_marks 补标…" } ],
                   "total": { "star_truth": 48, "star_captured": 45, "star_missing": 3,
                              "files_with_gaps": 1 },
                   "checked_files": 2, "all_clear": false } }
```

### bid.star_mark `{ file_id, block_idx, statement, reason?, mandatory? }`  （写面；#47 R28 / #88 Q3）
★漏标单块补标直通——`dispatch_with(submit_block_marks)` 真实工具面，壳侧只组装
参数：`marks=[{from:to:block_idx, verdict:"requirement"}]` +
`requirements=[{block_idx, statement, substantive:true}]`（**纯 mark 不产生 REQ——
锚定必须走 requirements**）。工具面单真源裁决：区间校验 / 原子落库 / #219 二步
（submitted 落**旁路账本**——`submitted_requirements`，重跑 `extract_requirements`
才并入主 REQ 账本，★captured 生效链即此；`next` 原样透传）+ #244 标满义务
（已开始标记的文件必须标满才能建纲——UI 诚实提示）。
壳侧前置早拒（零副作用）：`file_id` 空 / `block_idx` 负 / `statement` 空。
无 db.json → `not_found`；工具面 E_STATE 透传 `state` 码（§3.3）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "REQUIREMENTS_EXTRACTED" },
    "star_mark": { …submit_block_marks 工具输出原样（marks_accepted:1 /
                    requirements_accepted:1 / total_blocks / coverage / next）… } }
```

### bid.create_project `{ name, bid_deadline, mode, tender_notice_ref? }`  （写面；#19 导入向导第一步）

空工作区起步（无 db.json 不再 `not_found`——`ensure_or_open` 空态 + `.mang/approval.key`，
副作用即目的）；经 `bid_mcp::dispatch_with(create_bid_project)` 真实工具面，幂等/越级裁决
在工具面（同 key 重放 → 静默幂等；异 key 再建 → `state` 码，UI 分支引导卡，§109 同口径）。
`external_key` **壳侧隐式注入 = 工作区 canonical 路径**（一个工作区一个项目——UI 重试/
重复提交不建第二个项目）；`mode`（明标|暗标）与 `bid_deadline`（YYYY-MM-DD 粗形）壳侧
前置校验（校验失败零副作用）。

**日期时区口径（R15，#47 平台区分⑧——bid_deadline 双缺陷收口）**：① **严格公历
校验单一真源**——`bid_domain::dates::parse_ymd`（#375 A-16 月长收紧：`2026-02-30` 拒）；
MCP 面私有宽松拷贝（日域 1..=31）已删，`create_bid_project` 对不存在的日历日
E_UNPROCESSABLE（壳侧仍是形态检查先行——10 字符数字，分层不重复）。② **「今天」
换本地日历日**——`today_ymd` 旧口径 epoch 直除 86400 = UTC 日，东八区本地 00:00-
07:59 取到昨天：`BID_DEADLINE_PAST` 漏报一天、性能台账 created_at / 评标基准日 /
开标日缺省整体前置一档。现口径：chrono `Local` 只供 UTC 偏移秒（Unix TZ 环境
变量//etc/localtime、Windows 注册表——iana-time-zone 标准路径，已在锁内零新增包），
日期换算仍走 `civil_from_days` 单一算术真源（`ymd_at_utc_offset` 纯函数锁边界瞬点，
本地/UTC 至多差 1 天健全性）。ISO 定宽字典序 == 时间序（截止日比较仍是字符串比较）。

> **平台区分全矩阵**：R2/R9-R15 各面的行为口径、实现真源、测试锚与平台运行面，
> 见 `docs/mang/PLATFORM-MATRIX.md`（#47 R16 收口）——防漂移契约门
> `web-ui/tests/platform-matrix.test.mjs` 保证清单与实现/测试不脱钩。

```jsonc
→ { "present": true, "workspace": "D:\\项目B", "db": "D:\\项目B\\db.json",
    "project_id": "PRJ-0001", "status": "DRAFT", "warnings": [] }
// 幂等重放 → deduplicated:true + 原 project_id（#19：向导重复提交的主路径）
```

### bid.import_files `{ files:[{ upload_ref, filename?, kind? }] }`  （写面；#19 导入向导第二步）

`project_id` **壳侧注入服务态真源**（UI 不自报，防串项目）；`upload_ref` = 工作区相对
路径（fs.tree 的 rel）或围栏内绝对路径（围栏锚定在工具面 `fs_fence::resolve_read`）；
**分隔符归一（#47 R9 跨平台硬化①，壳侧入口单一真源）**：`\` → `/`、压缩空段与 `.` 段
（`a//b`、`a/./b` → `a/b`）；`..` 段原样保留（穿越裁决在域层围栏——归一不吞 `..`）；
绝对路径只换分隔符不压缩；
`filename` 缺省取基名、`kind` 缺省「附件」（契约 §2 同款）。**E_PARTIAL 不按错误回**：
壳侧组装 `partial:true` + `item_errors` 的成功响应（工具面 `data` 携带成功面——失败件
禁引、成功件照常入库不回滚），向导同屏分账呈现。

```jsonc
→ { "present": true, "file_ids": ["TF-0001"], "per_file": [ … 契约 §2 同形 … ],
    "totals": { "files": 1, "chunks": 48, "parse_failed": 0, "partial": 0 },
    "addendum_readiness": { … }, "input_integrity": { … },
    "status": "FILES_IMPORTED", "warnings": [] }
// 部分失败 → 顶层加 "partial": true, "partial_what": "…", "item_errors": [ … ]
```

### bid.ingest_drop  `{ paths:[绝对路径…] }` （写面：复制进工作区；#47 R8 / #19 拖拽导入）

壳 drop 事件（`WM_DROPFILES` / webview `drop`）的绝对路径**复制进工作区根**——只复制不
导入（导入仍走 `bid.import_files`，向导第二步用户确认 kind）。**不依赖 db.json**（先拖
文件再建项合法——不碰 DomainStore）。落位规则：同名且 sha256 相同 → `skipped:
already_present`（幂等）；同名不同内容 → `{stem}-2/-3/…{ext}` 找空位。白名单与
`BID_IMPORT_EXTS` 同源（**docx/xlsx/pdf/doc**——R17 与解析面对齐：bid-tools `service.rs`
导入路由只认这四类，其余扩展名（含旧表的 `.ods`）落 `parse_file`「不支持的文件类型」
显式拒；能落位但导入必失败的件在壳侧就拒，分账 `ext_blocked` + detail 指明合法四类）；
目录拖入明拒（`is_dir`——后续硬化轮可做递归导入）；不存在的路径 `not_found`。

**基名跨平台守卫（R10，#47 平台区分③——R8 注释预留硬化项落地）**：`paths::guard_portable_basename`
在壳侧入口拦截不可跨 Windows 迁移的基名，**双平台同拒**（不是 cfg 分支）——
① Windows 保留设备名（`CON/PRN/AUX/NUL/COM1-9/LPT1-9`，不分大小写、带扩展同样保留：
Linux 合法的 `CON.docx` 落库后拷到 Windows 即失效）；② 非法字符 `<>:"|?*/\` 与控制符；
③ 尾部空格/点（Windows 剥掉后落位名与记录键错位）。`bid.ingest_drop` 按**批次分账**
（`skipped: name_not_portable`，一件非法不毁整批——与 `ext_blocked` 同口径）；
`bid.import_files` 对 `upload_ref` 基名与显式 `filename` **双查、请求级 `bad_args`**
（输入规范错误与 mode 校验同款先例：零副作用早拒，改名重试）。

**大小写不敏感占位（R11，#47 平台区分④）**：落位判定按 Windows FS 占位语义预演——
`A.docx` 在场时 `a.docx`/`A.DOCX` 视作**同一占位**（NTFS upcase 折叠；Linux 精确名匹配
会放走变体，两文件共存拷到 Windows 互覆）。同内容变体 → `already_present`（detail
指明实际在场的占位名——用户拖 `a.docx` 而在场的是 `A.docx` 时说清楚）；异内容变体 →
走 `-2` 后缀占位，**后缀空位同样 CI 判定**。

**MAX_PATH 预检（R12，#47 平台区分⑤）**：`paths::guard_windows_max_path`——传统 Win32
路径上限 260 字符（含 NUL，字符串本体 259）。`bid.ingest_drop` 落位路径（根 + 分隔符 +
基名）超 259 → 批次分账 `path_too_long`（缩短文件名/层级，或 Windows 启用
`LongPathsEnabled`）；`bid.import_files` 的 `upload_ref` 估算长度超 259 → 请求级 `bad_args`
（绝对形态取本体、相对形态取 根+1+rel）。双平台同拒（Linux 能落但项目库拷 Windows 创建
即失败——与 R10 保留名同一可迁移性口径）。

**NFC 归一（R13，#47 平台区分⑥——macOS NFD 互操作）**：`paths::nfc`——macOS（HFS+/
Finder）文件名是 **NFD 分解形态**（é = e + U+0301），与 NFC 合成形态是不同字节串（NTFS/
ext4 字节精确）——不归一会「视觉同名两份」且占位/幂等键错位。口径：**落位名与占位键
统一 NFC**（占位键 = `nfc(name).to_lowercase()`——归一先于大小写折叠，双形态同占位；
CJK/ASCII 两形态字节相同零影响）；`bid.import_files` 的 `filename`（显示名/元数据）归一
NFC，**`upload_ref`（定位键）原样保留**——必须与磁盘真实文件名逐字节匹配，归一反而找
不到文件。

**混合分隔符矩阵（R14，#47 平台区分⑦——跨平台字符串基名）**：`paths::str_basename`
（双分隔符 `/`+`\` 取最后非空段；尾分隔符取最后非空段、全分隔符回退原样）——std
`Path::file_name` 按**本平台**分隔符解析（Unix 把 `C:\a\b.md` 整串当基名），**存库/传输
字符串**（recent 台账 path 的 name 回退、`bid.import_files` 的 filename 回退）两侧平台
必须同答（与 web-ui `baseName` 同口径）；真实本机路径仍用 `Path::file_name`（平台原生
形态天然正确）。守卫口径分野：R10 守卫取最后一段**字面值**（尾分隔符得空串 → 拒
「基名为空」，严格面），本助手是显示回退面（宽松面）——两者刻意不同。归一函数
`normalize_upload_ref` 深度矩阵锁定三不变量（相对形态输出不含 `\`；幂等；`..` 段数
不变）；fs_fence 混合形态**共享不变量**（Ok 必在根内 / Err 必 EUnprocessable——任何
平台不逃逸）+ cfg 双分支对照（Unix 把 `\` 当字面字符、Windows 当分隔词）。

```jsonc
→ { "present": true,
    "copied":  [ { "rel": "招标文件.docx", "name": "招标文件.docx", "size": 12345 } ],
    "skipped": [ { "path": "/home/u/笔记.txt", "reason": "ext_blocked", "detail": "…" } ] }
```

### bid.extract `{}` （写面：条款抽取；#47 R25——向导深水区·建纲流①）

无参数（工具面 `scope=all` 是唯一支持值——文件子集过滤属 M2 扩展）。经
`bid_mcp::dispatch_with(extract_requirements)` 走真实工具面——**确定性规则抽取**
（无 LLM）：评分细则 / 资格条件 / 技术参数 / ★标记正则面 + #219 标记合并（Agent
标记优先 + 正则兜底）。状态机：FILES_IMPORTED → REQUIREMENTS_EXTRACTED。
**零抽取是响亮警告而非错误**（#196 纪律——`warnings.ZERO_REQUIREMENTS` 逐条透出，
不伪装成功）。UI 消费（树区空态卡）：files>0 且 requirements==0 时给「抽取条款」
入口；成功后 `loadBid(true)` 重载——推荐卡自然接续。

```jsonc
→ { "present": true, "workspace": "…", "project": { "id", "name", "status" },
    "extract": { "counts": { "total", "added", "by_category" }, "merge": { … },
                 "star_summary": { … }, "conflicts": [], "missing_sequence": [],
                 "packages": { "detected", "items", "shared_req_count" },
                 "warnings": [ … ], "status": "REQUIREMENTS_EXTRACTED",
                 "project_version": n } }
```

### bid.length_profile `{}` （只读：篇幅档位推荐；#287 → UI 面 #47 R25——建纲流②）

经 `bid_mcp::dispatch_with(recommend_length_profile)` 走真实工具面。信号面
（评分细则条数 / ★数 / 预算 / 项目类型 / 明写限值）→ 推荐档 + 理由 + **四档
alternatives**（label/chars/pages/when 全量）。**呈现义务**（工具面 `next` 字段
自述）：把建议 + 理由 + alternatives 呈现给用户确认后 `build_outline(length_profile=…)`
——决策权在用户，推荐可被覆盖。明写限值在场时 `from_tender_spec` 非空（档位选择
让位明写值——UI 显示「直接采用」提示，不设单选）。

```jsonc
→ { "present": true, "workspace": "…", "project": { … },
    "recommendation": { "recommended_profile": "standard", "profile_label": "…",
                        "target_chars": n, "approx_pages": n, "confidence": "…",
                        "reasons": [ … ], "from_tender_spec": null,
                        "alternatives": [ { "profile", "label", "chars", "pages", "when" } ×4 ],
                        "signals": { "scoring_detail_count", "star_count",
                                     "budget_yuan", "tender_type", "explicit_limit_chars" },
                        "next": "…" } }
```

### bid.build_outline `{ length_profile?, target_total_chars?, max_reqs_per_leaf?, package?, project_version? }` （写面：建纲；#47 R25——建纲流③）

经 `bid_mcp::dispatch_with(build_outline)` 走真实工具面（章节树 + 合规矩阵一体
生成——`prepare_outline_and_matrix`）。可选参数与工具面同名同义；**壳侧只做形态级
早拒**（package 纯空白 → `bad_args`，与 no_addendum_confirm 的 reason 早拒同构），
四档值域 / 字数值域 / 分包命中 / 状态窗全在域层单一真源（E_STATE → `state` 码、
EUnprocessable → `bad_args` 码透传——工具面文案自带合法值清单与下一步指引）。
状态机：REQUIREMENTS_EXTRACTED → MATRIX_READY。UI 消费口径：明写限值在场时发
`target_total_chars`（明写值），否则发用户选档（默认推荐档）；分包 `detected ≥2`
时 `package` 必选（单包自动选定、零包不传）；成功后 `loadBid(true)` 重载——
章节树呈现，建纲流卡自然退场。

```jsonc
→ { "present": true, "workspace": "…", "project": { … },
    "outline_build": { "counts": { "sections", "leaves", "requirements",
                                   "total_requirements", "total_target_chars",
                                   "matrix_rows", "matrix_blocking" },
                       "package": { "selected": { … }, "auto_selected": bool, "shared_req_count": n },
                       "leaf_quotas": [ … ], "warnings": [ … ],
                       "effective_profile": "…", "status": "MATRIX_READY",
                       "project_version": n } }
```

### bid.packages —— 分包清单（只读；#20/#316——多标段/多包识别面）
`{}`（project_id 由壳从当前项目路由）

经 `bid_mcp::dispatch_with(list_packages)` 走真实工具面（#316 识别结果
+ 逐包条款数 + 选包状态 + 共用条款），只读不裁决。**选包动作不在本
命令**——选包 = `build_outline` 传 package 参数（R25 起入口在树区建纲
流卡的分包选择器；本面板保持只读呈现）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "packages": { "detected": 2,
                  "items": [ { "id": "PKG-A", "label": "一标段：设备采购", "kind": "标段",
                               "number": "1", "req_count": 42, "sources": ["A-招标文件.docx"],
                               "selected": true } ],
                  "shared_req_count": 6, "total_requirements": 60,
                  "selected_package": { "id": "PKG-A", "label": "一标段：设备采购" },
                  "usage": "build_outline 传 package=<id|label|number> 选定投哪个包…" } }
```

### bid.evidence —— 证据台账列表（只读；#47 R25——缺口-4 读半边）
`{ filters?: { kind?, status? }, limit?, cursor? }`（project_id 由壳从当前项目路由——恒覆写，不接受调用方伪造）

经 `bid_mcp::dispatch_with(list_evidence)` 走真实工具面：kind 七值
snake_case（qualification|performance|personnel|certificate|product_doc|
solution_module|contract）/ status 四值大写（ACTIVE|EXPIRING|EXPIRED|
SUPERSEDED）——值域校验与非法值拒绝在工具面单一真源（壳不重复实现）；
id 字典序 + 游标分页。**读面任何项目阶段可调**（无 E_STATE）；
E_NOTFOUND（无 db.json）走引导卡（§3.4）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "evidence": { "items": [ { "id": "EV-0001", "kind": "product_doc",
                                "title": "并发压测报告", "status": "ACTIVE",
                                "subject_name": "演示科技", "valid_until": "2027-06-30",
                                "verification_tier": "SELF_TEST" } ],
                  "total": 13, "limit": 50, "cursor": null, "next_cursor": null,
                  "project_version": 12 } }
```

### bid.evidence_search —— 证据检索（只读；#47 R25）
`{ query, mode?: "hybrid"|"semantic"|"exact"（缺省 hybrid）, top_k?, threshold? }`

经 `bid_mcp::dispatch_with(search_evidence)`：query 必填（空 query 由工具面
显式拒绝）；检索面 = 标题+范围+主体+客户+正文摘录（#217）；时间面降权
（filters.valid_at 给定才启用）产生 warnings 原样透传；**SUPERSEDED 不进
检索池**（工具面口径）。hits 行含 score / match_type（exact|semantic|both）/
excerpt / verification_tier。值域（mode/top_k 1..=20/threshold 0..=1）在
工具面单一真源。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "search": { "hits": [ { "id": "EV-0001", "title": "并发压测报告", "score": 1.0,
                             "match_type": "both", "kind": "product_doc", "status": "ACTIVE",
                             "valid_until": "2027-06-30", "excerpt": "2000 路并发压测全通过…" } ],
                "total": 1, "top_k": 10, "warnings": [],
                "trace": { "engine": "naive-token-v1（pre-M2-b）", "content_face": "title+scope+subject+client+excerpt" },
                "project_version": 12 } }
```

### bid.evidence_register —— 证据登记（写面；#47 R26——缺口-4 写半边之登记）
`{ kind, title, source_file_id, subject_name, scope?, valid_from?, valid_until?, client?, amount_wan?, completed_on?, placeholder?, locator?, fields?, project_version? }`（project_id 由壳从当前项目路由——恒覆写）

经 `bid_mcp::dispatch_with(register_evidence)`：source_file_id **锚定已导入
件**（import 回执 per_file[].file_id，#185——sha256/指纹由服务端从库内生成，
不接受自报）；verification_tier 由服务端裁决（#245 自报显式拒）；
旧来源参数 source_file/source_sha256/fingerprint 显式拒（防假成功）。
返回 (ev_id, deduplicated)：同 key 同指纹同验证态 → **幂等重放**（原
EV-id 直返不换版）；同 key 换版 → 旧记录单向降级 SUPERSEDED 且既有绑定
迁移到新记录。E_UNPROCESSABLE → bad_args（表单内反馈，不走横幅）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "register": { "ev_id": "EV-0014", "deduplicated": false, "kind": "qualification",
                  "status": "ACTIVE", "verification_tier": "VERIFIED", "placeholder": false,
                  "excerpt": "…正文摘录", "hint": "新 EV 已签发…",
                  "project_version": 12 } }
```

### bid.matrix_override —— 否决项死锁人工裁定（写面；#20/#226）
`{ requirement_id, status, deviation?, actor_id?, project_version? }`

#182 宿主签发面（**不进 MCP 工具表，Agent 拿不到**）：壳用服务态密钥对
`matrix_override:<project_id>:<requirement_id>:<status>:<sha256(deviation)>`
四重绑定签域签 receipt（换任何一项都要换签），经
`bid_mcp::dispatch_with(set_matrix_override)` 走真实工具面——覆写后矩阵
立即重算。status ∈ RESPONDED|NOT_APPLICABLE|NOT_RESPONDED|PARTIAL；
NOT_APPLICABLE 的 deviation 必填（不可审计的豁免不算豁免——壳透传空串
会被域层响亮拒）。每次裁定落审计记录（操作者/理由/时间，不可抹除）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "override": { "requirement_id": "REQ-0003", "status": "NOT_APPLICABLE",
                  "from_status": "NOT_RESPONDED", "blocking_after": 2,
                  "audit": { "actor_id": "shell-operator", "method": "human_receipt" } } }
```

### bid.recover_state —— VALIDATING+缺章异常态恢复（写面；#20/#243）
`{ reason, project_version? }`

经 `bid_mcp::dispatch_with(recover_validating_state)` 走真实工具面——
三重域层约束（仅 VALIDATING / 仅缺章 / 理由非空白）+ 审计账（何时/为何/
从哪到哪/缺哪些章）。**不是任意状态写入**：非死锁态按「恢复」会被
E_STATE 响亮拒（UI 引导卡语义）。恢复后携带新 project_version。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "智慧园区弱电工程", "status": "DRAFTING" },
    "recover": { "from_status": "VALIDATING", "to_status": "DRAFTING",
                 "recovered_sections": ["SEC-T03"], "audit_reason": "旧版校验误推进" } }
```

### bid.addenda —— 补遗件台账（只读；#603 批 C——治理面）
DomainStore + readiness 直读（`bid.gates` 同款纪律——MCP 工具面无此整面
视图，`addendum_statuses` / `addendum_waivers` 同源）：补遗就绪度
（`readiness::{total, ready, not_ready[]}`——not_ready 元素
`{file_id, name, readiness, waived, reason}`，**已确认件保留在场**
（waived=true——审计面不因放行而消失））+ 逐件确认台账（`waivers[]`：
file_id/reason/at/principal）。读面无状态窗：total=0（未发现补遗）是
NotProvided 阻塞的素材，不是故障。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "…", "status": "DRAFTING" },
    "readiness": { "total": 2, "ready": 1,
                   "not_ready": [ { "file_id": "TF-0003", "name": "补遗-01（扫描件）",
                                    "readiness": "OCR_PENDING", "waived": false,
                                    "reason": "OCR 未完成…" } ] },
    "waivers": [ { "file_id": "TF-0004", "reason": "…", "at": 1790000000,
                   "principal": "human:operator-li" } ] }
```
拒绝面：无 db.json → `not_found`。

### bid.addendum_waiver —— 补遗逐件确认（写面；#603 批 C）
`{ file_id, reason, actor_id?, project_version? }`

#184 补遗分级阻塞的人工出口（UI 接线）：某补遗/输入件不处 READY
（FAILED/OCR_PENDING）时起草被拒——人工逐件免责（file_id 级绑定）后放行，
起草标 RESTRICTED（受限起草，不静默当完整输入）。流程（#182 宿主签发面，
与 bid.gate_pass 同款）：壳签 receipt（签域 `addendum_waiver:{file_id}`——
TF-0003 的 receipt 免不了 TF-0004）→ 经
`dispatch_with(record_addendum_waiver)` 走真实工具面（状态窗 FILES_IMPORTED+ /
幽灵件拒 / 空白理由拒全在域层裁决）→ 工具输出原样放 `addendum_waiver` 键
（recorded 回执 / actor / addendum_waivers / addendum_readiness /
agent_waivers / human_review_complete）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "…", "status": "DRAFTING" },
    "addendum_waiver": { "recorded": { "file_id": "TF-0003", "reason": "…",
                             "at": 1790000000, "principal": "human:operator-li",
                             "actor": { "actor_id": "operator-li", "actor_type": "human",
                                        "authentication_method": "hmac_receipt_v2" } },
                    "addendum_waivers": [ …逐件台账… ],
                    "addendum_readiness": { "total": 2, "ready": 1, "not_ready": [ … ] },
                    "agent_waivers": [ … ], "human_review_complete": true,
                    "status": "DRAFTING", "project_version": 6 } }
```
拒绝面：无 db.json → `not_found`；幽灵 file_id → **`not_found`**（对不存在
的件做确认 = 凭空免责）；空白理由 → **`bad_args`**（壳侧早拒 + 域层兜底）。

### bid.no_addendum_confirm —— 「本项目无补遗」全局确认（写面；#603 批 C）
`{ reason, actor_id?, project_version? }`

#379 拆门的独立写面：NotProvided 阻塞（未发现补遗/澄清件）的唯一人工
出口。与逐件免责是**两种语义**——壳层结构性隔离为两条命令（互斥校验在
工具面：confirm_no_addendum=true 时携带 file_id 响亮拒）。流程（#182 宿主
签发面）：壳签 receipt（独立签域 `no_addendum_confirmed`——A 门 receipt
免不了 B 门）→ 经 `dispatch_with(record_addendum_waiver,
confirm_no_addendum=true)` 走真实工具面（域前置裁决：项目已有补遗件时
响亮拒——「确认无补遗」与事实矛盾，正确出口是逐件确认或修复重传）→
工具输出原样放 `no_addendum_confirm` 键（confirmed_no_addendum 回执（含
#277 过门方式 method 与 human_confirmed）/ addendum_waivers /
addendum_readiness / agent_waivers / human_review_complete）。确认即过
no_addendum_confirmed 门 + 审计留痕（REV 记录）。
```jsonc
→ { "present": true, "workspace": "D:\\项目A",
    "project": { "id": "PRJ-0001", "name": "…", "status": "DRAFTING" },
    "no_addendum_confirm": {
                    "confirmed_no_addendum": { "review_id": "REV-0004",
                             "gate": "no_addendum_confirmed", "reason": "…",
                             "at": 1790000000,
                             "actor": { "actor_id": "operator-zhao", "actor_type": "human",
                                        "authentication_method": "hmac_receipt_v2" },
                             "method": "human_receipt", "human_confirmed": true },
                    "addendum_waivers": [], "addendum_readiness": { "total": 0, "ready": 0, "not_ready": [] },
                    "agent_waivers": [], "human_review_complete": true,
                    "status": "DRAFTING", "project_version": 6 } }
```
拒绝面：无 db.json → `not_found`；项目已有补遗件 / 空白理由 →
**`bad_args`**（域层 E_UNPROCESSABLE 原文——给出正确出口指引）。

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
