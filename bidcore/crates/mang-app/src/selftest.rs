//! `--selftest`：无窗口把 IPC 全链路跑一遍（CI/冒烟用）。
//!
//! 覆盖：ping / app.info / fs.tree / fs.read / fs.readBytes / fs.writeBytes(happy+denied)
//!       / fs.stat / fs.mkdir / path-guard(../ 与绝对越界) / 大响应落盘与取回 / recent 往返
//!       / history.list / unknown_cmd / bad_json
//!       / mcp.status / llm.status+save 往返（#76）/ fspec.status（#76）
//!       / bid.state+bid.outline（#313 批 A：无 db.json 干净 not_found / 真实项目读取 / db.json 外部变更后缓存重开）
//!       / bid.quality+bid.score（#313 批 C：早态 E_STATE→state 码 / MATRIX_READY 后真实读取）
//!       / bid.gates+bid.gate_pass（#603 批 A：五门台账 / 人工过门宿主签发 receipt / 门序跳跃拒 / 非法门早拒）
//!       / bid.matrix（#313 批 B：无 db.json not_found / 真实项目 / db.json 变更重开）
//!       / bid.coverage（#313 批 D：未导入件诚实口径 total_blocks=0 + next 引导）
//!       / workspace.open+current（#194：切换/新根命令面/幂等/记忆/失败不换根）
//! 输出形如 `PASS  <name>：<detail>` / `FAIL  <name>：<detail>`，最后一行汇总 + 退出码。

use serde_json::{json, Value};

use crate::b64;
use crate::ipc::{self, Ctx};
use crate::paths::{display, Workspace};
use crate::recent;

struct Report {
    pass: usize,
    fail: usize,
}

impl Report {
    fn ok(&mut self, name: &str, detail: impl AsRef<str>) {
        self.pass += 1;
        println!("PASS  {name}：{}", detail.as_ref());
    }
    fn bad(&mut self, name: &str, detail: impl AsRef<str>) {
        self.fail += 1;
        println!("FAIL  {name}：{}", detail.as_ref());
    }
    fn check(&mut self, name: &str, cond: bool, detail: impl AsRef<str>) {
        if cond {
            self.ok(name, detail)
        } else {
            self.bad(name, detail)
        }
    }
}

fn scratch_dir() -> std::path::PathBuf {
    let d = std::env::temp_dir().join(format!(
        "mang-selftest-{}-{}",
        std::process::id(),
        ipc::now_ms()
    ));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(d.join("sub/deep")).unwrap();
    std::fs::create_dir_all(d.join("node_modules/pkg")).unwrap();
    std::fs::create_dir_all(d.join(".mang/history")).unwrap();
    std::fs::write(d.join("技术标.md"), "# 第一章 概述\n\n正文。\n").unwrap();
    std::fs::write(d.join("第10章.md"), "10").unwrap();
    std::fs::write(d.join("第2章.md"), "2").unwrap();
    std::fs::write(d.join("sub/deep/note.txt"), "note").unwrap();
    std::fs::write(d.join("node_modules/pkg/index.js"), "x").unwrap();
    // 2MB 假 docx：验证大响应落盘
    let big: Vec<u8> = (0..2 * 1024 * 1024u32).map(|i| (i % 251) as u8).collect();
    std::fs::write(d.join("大文件.bin"), &big).unwrap();
    std::fs::write(
        d.join(".mang/history/index.json"),
        r#"{"技术标.md":[{"ts":1700000000000,"kind":"manual","message":"第1章 概述完成","snapshot":".mang/history/技术标.md/1700000000000.md"},{"ts":1699999990000,"kind":"auto","message":""}]}"#,
    )
    .unwrap();
    d
}

fn call(ctx: &Ctx, body: Value) -> Value {
    let text = serde_json::to_string(&body).unwrap();
    match ipc::parse(&text) {
        Ok(req) => ctx.dispatch(&req),
        Err(e) => ipc::err_frame(&Value::Null, &e),
    }
}

fn err_code(resp: &Value) -> String {
    resp.get("code").and_then(|c| c.as_str()).unwrap_or("").to_string()
}

fn result(resp: &Value) -> &Value {
    resp.get("result").unwrap_or(&Value::Null)
}

/// #313 批 A：在目录里种一个最小真实项目（bid-tools 服务面，与 MCP 写路径
/// 同源）——1 章 + 1 叶，外加 chapters/SEC-S2.json（chapter_file 检测面）。
fn seed_bid_project(dir: &std::path::Path) {
    use bid_domain::outline::{OutlineNode, SectionStatus};
    use bid_domain::{ProjectStatus, Requirement};
    use std::collections::HashMap;
    // 独立锚点：requirement_hash = sha256(file|locator|excerpt)——空锚点
    // 同哈希会被 set_requirements「同位覆盖」（见 bid.rs 测试同款注记）
    let mk_req = |id: &str, category: &str, excerpt: &str| Requirement {
        id: id.into(),
        category: category.into(),
        clause_no: None,
        anchors: vec![bid_domain::Anchor {
            file: "A-招标文件.docx".into(),
            kind: "para".into(),
            locator: format!("第三章 3.2/{id}"),
            excerpt: excerpt.into(),
            ..bid_domain::Anchor::default()
        }],
        params: HashMap::new(),
        source_file: "A-招标文件.docx".into(),
    };
    let mut svc = bid_tools::service::BidService::open(dir).unwrap();
    svc.create_project("selftest 项目", "PRJ-ST", "明标", "ext-st-313").unwrap();
    let st = svc.store_mut();
    st.advance_project_status(ProjectStatus::FilesImported).unwrap();
    st.set_requirements(vec![mk_req("REQ-0001", "技术参数", "投标人须提供 2000 路并发能力")])
        .unwrap();
    st.set_outline(vec![
        OutlineNode {
            id: "SEC-S1".into(),
            parent_id: None,
            title: "第一章 技术方案".into(),
            level: 1,
            order: 1,
            // 父节点 requirement_ids = 子并集（validate_outline 要求每节点 ≥1）
            requirement_ids: vec!["REQ-0001".into()],
            target_chars: 15_000,
            status: SectionStatus::Pending,
            dirty: false,
            content: None,
            content_attempt: 0,
        },
        OutlineNode {
            id: "SEC-S2".into(),
            parent_id: Some("SEC-S1".into()),
            title: "1.1 参数响应".into(),
            level: 2,
            order: 2,
            requirement_ids: vec!["REQ-0001".into()],
            target_chars: 15_000,
            status: SectionStatus::Pending,
            dirty: false,
            content: None,
            content_attempt: 0,
        },
    ])
    .unwrap();
    svc.checkpoint().unwrap();
    std::fs::create_dir_all(dir.join("chapters")).unwrap();
    std::fs::write(
        dir.join("chapters").join("SEC-S2.json"),
        r#"{"section_id":"SEC-S2","content":"占位正文","char_count":4,"attempt":1,"citations":[],"updated_at":1793000000}"#,
    )
    .unwrap();
}

pub fn run(ui_dir: Option<&std::path::Path>) -> i32 {
    let mut r = Report { pass: 0, fail: 0 };
    println!("== mang-app --selftest ==");
    println!("version = {}", env!("CARGO_PKG_VERSION"));
    println!("temp    = {}", display(&std::env::temp_dir()));

    let root = scratch_dir();
    let ws = match Workspace::new(&root) {
        Ok(w) => w,
        Err(e) => {
            println!("FAIL  工作区初始化：{e}");
            return 1;
        }
    };
    println!("scratch = {}", ws.root_display());
    let empty_ui = std::path::PathBuf::from(&root);
    let ctx = Ctx::new(ws.clone(), ui_dir.map(|p| p.to_path_buf()).unwrap_or(empty_ui));

    // 清理上一轮遗留的 IPC 临时文件，验证 purge
    std::fs::write(ipc::pending_dir().join("stale-test.json"), "{}").unwrap();
    ipc::purge_pending();
    r.check(
        "purge_pending",
        !ipc::pending_dir().join("stale-test.json").exists(),
        "启动清理 %TEMP%\\mang-ipc 里的旧 .json",
    );

    // ---- ping / app.info
    let resp = call(&ctx, json!({"id":"t-ping","cmd":"ping"}));
    r.check(
        "ping",
        resp["ok"] == json!(true) && result(&resp)["pong"] == json!(true) && result(&resp)["t"].as_u64().unwrap_or(0) > 0,
        format!("{resp}"),
    );
    let resp = call(&ctx, json!({"id":"t-info","cmd":"app.info"}));
    let info = result(&resp);
    r.check(
        "app.info",
        info["version"].is_string()
            && info["workspace"].as_str() == Some(ws.root_display().as_str())
            && info["exe"].as_str().map(|s| !s.is_empty()).unwrap_or(false),
        format!("version={} ui_dir={}", info["version"], info["ui_dir"]),
    );

    // ---- fs.tree
    let resp = call(&ctx, json!({"id":"t-tree","cmd":"fs.tree"}));
    let tree = result(&resp);
    let names: Vec<String> = tree["nodes"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .map(|n| n["name"].as_str().unwrap_or("").to_string())
        .collect();
    let dirs_first = names.first().map(|s| s == "sub").unwrap_or(false);
    let natural = names
        .iter()
        .position(|n| n == "第2章.md")
        .zip(names.iter().position(|n| n == "第10章.md"))
        .map(|(a, b)| a < b)
        .unwrap_or(false);
    r.check(
        "fs.tree shape/sort",
        tree["root"].is_string() && dirs_first && natural && !names.iter().any(|n| n == "node_modules" || n == ".mang"),
        format!("顶层 {} 项：{:?}", names.len(), names),
    );
    r.check(
        "fs.tree depth/子节点",
        tree["nodes"][0]["nodes"].as_array().map(|a| !a.is_empty()).unwrap_or(false),
        "sub 下带 nodes",
    );
    let resp = call(&ctx, json!({"id":"t-tree2","cmd":"fs.tree","path":"sub","depth":1}));
    r.check(
        "fs.tree sub+depth",
        result(&resp)["path"] == json!("sub") && result(&resp)["nodes"].as_array().unwrap().iter().all(|n| n["name"] == "deep"),
        format!("{}", result(&resp)["path"]),
    );

    // ---- fs.read
    let resp = call(&ctx, json!({"id":"t-read","cmd":"fs.read","path":"技术标.md"}));
    let rd = result(&resp);
    r.check(
        "fs.read",
        rd["text"].as_str().map(|s| s.contains("第一章")).unwrap_or(false) && rd["bytes"].as_u64().unwrap_or(0) > 0,
        format!("bytes={}", rd["bytes"]),
    );

    // ---- fs.readBytes + 大响应落盘
    let raw = std::fs::read(ws.sub("大文件.bin")).unwrap();
    let resp = call(&ctx, json!({"id":"t-bytes","cmd":"fs.readBytes","path":"大文件.bin"}));
    let small = serde_json::to_string(&resp).map(|s| s.len()).unwrap_or(0);
    // 直接走主循环那一步（落盘）
    r.check(
        "fs.readBytes",
        result(&resp)["bytes"].as_u64() == Some(raw.len() as u64) && result(&resp)["enc"] == json!("b64"),
        format!("{} 字节 → 响应 {} 字节（未落盘阈值 {}）", raw.len(), small, ipc::INLINE_LIMIT),
    );
    for attempt in 0..5 {
        let id = json!(format!("t-big-{attempt}"));
        let payload = json!({"id": id, "ok": true, "result": {"data": b64::encode(&raw)}});
        let out = ipc::spill_if_large(&id, payload);
        if out["result"]["file"].is_string() {
            let name = out["result"]["file"].as_str().unwrap();
            let bytes = ipc::take_pending(name);
            let decoded_ok = bytes
                .as_ref()
                .and_then(|b| serde_json::from_slice::<Value>(b).ok())
                .and_then(|v| v["result"]["data"].as_str().and_then(|s| b64::decode(s).ok()))
                .map(|d| d == raw)
                .unwrap_or(false);
            let deleted = ipc::take_pending(name).is_none();
            r.check(
                "大响应落盘+取回+删除",
                decoded_ok && deleted,
                format!("{name} 读一次后删除={deleted}"),
            );
            break;
        }
        if attempt == 4 {
            r.bad("大响应落盘+取回+删除", format!("5 次都没触发落盘（响应 {} 字节）", small));
        }
    }

    // ---- fs.writeBytes（.mang 内 ok / 其他 denied）
    let payload = b64::encode(b"snapshot-body");
    let resp = call(&ctx, json!({"id":"t-w1","cmd":"fs.writeBytes","path":".mang/history/probe/1.md","enc":"b64","data":payload}));
    let wrote = std::fs::read(ws.sub(".mang/history/probe/1.md")).unwrap_or_default();
    r.check(
        "fs.writeBytes(.mang ok)",
        resp["ok"] == json!(true) && wrote == b"snapshot-body",
        format!("{wrote:?}"),
    );
    let resp = call(&ctx, json!({"id":"t-w2","cmd":"fs.writeBytes","path":"技术标.md","enc":"b64","data":payload}));
    r.check("fs.writeBytes(非 .mang denied)", err_code(&resp) == "denied", format!("{resp}"));
    let resp = call(&ctx, json!({"id":"t-w3","cmd":"fs.writeBytes","path":".mang/x.md","enc":"b64","data":"!!!not-b64"}));
    r.check("fs.writeBytes(坏 b64 bad_args)", err_code(&resp) == "bad_args", format!("{resp}"));

    // ---- fs.stat / fs.mkdir
    let resp = call(&ctx, json!({"id":"t-s1","cmd":"fs.stat","path":"sub"}));
    r.check("fs.stat dir", result(&resp)["isDir"] == json!(true), format!("{}", result(&resp)));
    let resp = call(&ctx, json!({"id":"t-s2","cmd":"fs.stat","path":"nope.md"}));
    r.check("fs.stat missing", result(&resp)["exists"] == json!(false), format!("{}", result(&resp)));
    let resp = call(&ctx, json!({"id":"t-mk","cmd":"fs.mkdir","path":"新目录/子"}));
    r.check(
        "fs.mkdir",
        ws.sub("新目录/子").is_dir() && resp["ok"] == json!(true),
        format!("{resp}"),
    );

    // ---- 路径围栏
    // R2（#47 平台区分①）：绝对越界样本平台自适应——Windows 用盘符正斜杠
    // 形态（C:/…，顺带覆盖混合分隔符的绝对形态），Unix 用根路径形态。
    // 历史写死 C:/Windows/win.ini：在 Linux 上是合法相对路径（C: 只是
    // 普通目录名），围栏正确地按相对路径解析成 not_found，用例却期望
    // outside_workspace——此前 mang-app 在 Linux 不可构建，从未真跑
    // 暴露（假绿）。AGENTS.md 13.1：平台特定样本必须 cfg 分支。
    let outside_abs = std::env::temp_dir().join("mang-selftest-outside.txt");
    std::fs::write(&outside_abs, "outside").unwrap();
    let abs_escape: &str = if cfg!(windows) {
        "C:/Windows/win.ini"
    } else {
        "/etc/passwd"
    };
    let cases = [
        ("fs.read ../", json!({"id":"g1","cmd":"fs.read","path":"../mang-selftest-outside.txt"})),
        ("fs.readBytes ../", json!({"id":"g2","cmd":"fs.readBytes","path":"sub/../../mang-selftest-outside.txt"})),
        ("fs.tree ../", json!({"id":"g3","cmd":"fs.tree","path":".."})),
        ("fs.stat 绝对越界", json!({"id":"g4","cmd":"fs.stat","path": display(&outside_abs)})),
        ("fs.read 绝对越界", json!({"id":"g5","cmd":"fs.read","path": abs_escape})),
    ];
    let mut all_blocked = true;
    let mut detail = Vec::new();
    for (name, body) in cases {
        let resp = call(&ctx, body);
        let code = err_code(&resp);
        detail.push(format!("{name}→{code}"));
        if code != "outside_workspace" {
            all_blocked = false;
        }
    }
    r.check("path-guard 越界全拦", all_blocked, detail.join("，"));
    let _ = std::fs::remove_file(&outside_abs);

    // R2（#47 平台区分①）：盘符形态的平台归类对照——两侧都断言「本平台
    // 的正确语义」，不是把一侧改成另一侧的期望：Windows 上 C:/… 是
    // 绝对路径 → 越界拦；Unix 上 C: 是普通目录名 → 围栏内相对解析，
    // 目标不存在 → not_found（同样是围栏在工作，只是走了相对分支）。
    let resp = call(&ctx, json!({"id":"g6","cmd":"fs.read","path":"C:/Windows/win.ini"}));
    let drive_code = err_code(&resp);
    let (drive_expect, drive_why) = if cfg!(windows) {
        ("outside_workspace", "Windows：盘符=绝对路径，越界拦")
    } else {
        ("not_found", "Unix：C: 是普通目录名，围栏内相对解析后目标不存在")
    };
    r.check(
        "path-guard 盘符形态平台语义",
        drive_code == drive_expect,
        format!("C:/Windows/win.ini → {drive_code}（{drive_why}）"),
    );

    // ---- 大文件拒绝
    // (不真的造 50MB，只验证 too_large 的判定入口存在：用超长 name 触发 bad_args 说明参数校验生效)
    let resp = call(&ctx, json!({"id":"t-bad1","cmd":"fs.read","path":"技术标.md","depth":"x"}));
    r.check("未知参数不影响", resp["ok"] == json!(true), "多余参数被忽略");
    let resp = call(&ctx, json!({"id":"t-bad2","cmd":"fs.read","path":123}));
    r.check("bad_args(path 非字符串)", err_code(&resp) == "bad_args", format!("{resp}"));

    // ---- recent 往返
    let resp = call(&ctx, json!({"id":"t-rec","cmd":"recent.save","items":[
        {"path": display(&ws.sub("技术标.md")), "name":"技术标.md", "kind":"file", "openedAt": 1699999999000i64},
        {"path": "C:/不存在的/x.docx", "kind":"file", "openedAt": 1699999998000i64}
    ]}));
    let recent_count = result(&resp)["count"].as_u64().unwrap_or(99);
    let resp = call(&ctx, json!({"id":"t-rec2","cmd":"recent.load"}));
    let items = result(&resp)["items"].as_array().cloned().unwrap_or_default();
    r.check(
        "recent.save/load",
        recent_count <= 50 && !items.is_empty() && items[0]["path"].is_string(),
        format!("{} 条，文件 {}", items.len(), result(&resp)["file"]),
    );

    // ---- history.list
    let resp = call(&ctx, json!({"id":"t-hist","cmd":"history.list"}));
    let hist = result(&resp)["items"].as_array().cloned().unwrap_or_default();
    r.check(
        "history.list",
        result(&resp)["present"] == json!(true) && hist.len() == 2 && hist[0]["kind"] == json!("manual"),
        format!("{} 条，首条 {}", hist.len(), hist.first().cloned().unwrap_or(Value::Null)["message"]),
    );
    let resp = call(&ctx, json!({"id":"t-hist2","cmd":"history.list","path":"不存在.md"}));
    r.check("history.list(过滤空)", result(&resp)["items"].as_array().map(|a| a.is_empty()).unwrap_or(false), "无匹配");

    // ---- 错误协议
    let resp = call(&ctx, json!({"id":"t-unk","cmd":"nope.cmd"}));
    r.check("unknown_cmd", err_code(&resp) == "unknown_cmd" && resp["ok"] == json!(false), format!("{resp}"));
    let req = ipc::parse("{{{").err().map(|e| e.code);
    r.check("bad_json", req == Some("bad_json"), "魔改 JSON → bad_json");

    // ---- #76 设置面板：mcp.status / llm.status→save→status 往返 / fspec.status
    // mcp.status 的 tools==13 腐烂断言归 PR #543（fix/542）修——本 PR 不重复
    // 动同一行（反重复 PR 纪律），此处保持 main 原样。
    let resp = call(&ctx, json!({"id":"t-mcp","cmd":"mcp.status"}));
    let mcp = result(&resp);
    // FG-01（#303）教训：本断言曾把工具面钉死 13（#68 阶段 2 的字面量），
    // diag.rs 单测面已改为对 TOOL_NAMES 的动态断言，此处漏改——同一事实
    // 两副本漂移，工具面涨到 44 后健康系统上 --selftest 必红（#542）。
    // 与 diag.rs mcp_status_is_stdio_and_ready 同口径：以 TOOL_NAMES 为
    // 单一真源，工具面涨多少都不用改这里。
    r.check(
        "mcp.status",
        resp["ok"] == json!(true)
            && mcp["channel"].as_str() == Some("stdio")
            && mcp["ready"] == json!(true)
            && mcp["tools"].as_u64().unwrap_or(0) == bid_mcp::TOOL_NAMES.len() as u64,
        format!(
            "channel={} tools={} ready={} (TOOL_NAMES={})",
            mcp["channel"],
            mcp["tools"],
            mcp["ready"],
            bid_mcp::TOOL_NAMES.len()
        ),
    );

    let resp = call(&ctx, json!({"id":"t-llm0","cmd":"llm.status"}));
    let llm0 = result(&resp);
    r.check(
        "llm.status(未配置)",
        resp["ok"] == json!(true)
            && llm0["file_present"] == json!(false)
            && llm0["effective"].as_str().unwrap_or("").starts_with("mock"),
        format!("effective={}", llm0["effective"]),
    );
    // 保存→状态往返（key 掩码 + 合并语义）
    let resp = call(&ctx, json!({
        "id":"t-llm-save","cmd":"llm.save",
        "apiKey":"sk-selftest-0123456789abcdef","model":"selftest-model","apiBase":"https://selftest.invalid/v1"
    }));
    r.check("llm.save", resp["ok"] == json!(true) && result(&resp)["effective"] == json!("real"), format!("{resp}"));
    let resp = call(&ctx, json!({"id":"t-llm1","cmd":"llm.status"}));
    let llm1 = result(&resp);
    r.check(
        "llm.status(已配置)",
        llm1["file_present"] == json!(true)
            && llm1["has_api_key"] == json!(true)
            && llm1["model"].as_str() == Some("selftest-model")
            && llm1["api_key_hint"].as_str().map(|h| h.contains("***") && !h.contains("0123456789abcdef")).unwrap_or(false)
            && llm1["effective"] == json!("real"),
        format!("model={} hint={}", llm1["model"], llm1["api_key_hint"]),
    );
    // 拒绝面：有 key 无 model（保存时就拦，不留到生成时）
    let resp = call(&ctx, json!({"id":"t-llm-bad","cmd":"llm.save","apiKey":"sk-selftest-xxxxxxxxxxxx","model":""}));
    r.check("llm.save(有key无model拒绝)", resp["ok"] == json!(false) && err_code(&resp) == "bad_args", format!("{resp}"));
    // 清 key 回到 mock
    let resp = call(&ctx, json!({"id":"t-llm-clr","cmd":"llm.save","clearApiKey":true}));
    r.check("llm.save(清key)", resp["ok"] == json!(true) && result(&resp)["effective"].as_str().unwrap_or("").starts_with("mock"), format!("{resp}"));

    let resp = call(&ctx, json!({"id":"t-fspec0","cmd":"fspec.status"}));
    r.check(
        "fspec.status(缺文件)",
        resp["ok"] == json!(true) && result(&resp)["present"] == json!(false),
        format!("{}", result(&resp)["path"]),
    );
    std::fs::write(
        root.join(".mang/format-spec.json"),
        r#"{"global":{"page":{"size":"A4","margin":{"top":25,"bottom":25,"left":28,"right":26}},"font":{"body":"仿宋_GB2312","size":12,"lineHeight":1.5},"header":{"enabled":false,"content":""},"footer":{"enabled":true,"content":"第 {page} 页"}},"per_section":{}}"#,
    )
    .unwrap();
    let resp = call(&ctx, json!({"id":"t-fspec1","cmd":"fspec.status"}));
    let fs1 = result(&resp);
    r.check(
        "fspec.status(在场)",
        fs1["present"] == json!(true) && fs1["invalid"] == json!(false) && fs1["page"]["size"] == json!("A4") && fs1["font"]["body"] == json!("仿宋_GB2312"),
        format!("{} {}pt", fs1["page"]["size"], fs1["font"]["size_pt"]),
    );

    // ---- #313 批 A：标书数据面（bid.state / bid.outline）
    // 无 db.json → 干净的 not_found（不落副作用）
    let resp = call(&ctx, json!({"id":"t-bid-s0","cmd":"bid.state"}));
    r.check(
        "bid.state(无db.json)",
        resp["ok"] == json!(false) && err_code(&resp) == "not_found",
        format!("{}", err_code(&resp)),
    );
    let resp = call(&ctx, json!({"id":"t-bid-o0","cmd":"bid.outline"}));
    r.check(
        "bid.outline(无db.json)",
        resp["ok"] == json!(false) && err_code(&resp) == "not_found",
        format!("{}", err_code(&resp)),
    );
    // #313 批 B：矩阵同样干净拒绝（不落副作用）
    let resp = call(&ctx, json!({"id":"t-bid-m0","cmd":"bid.matrix"}));
    r.check(
        "bid.matrix(无db.json)",
        resp["ok"] == json!(false) && err_code(&resp) == "not_found",
        format!("{}", err_code(&resp)),
    );
    // 种一个真实项目（bid-tools 服务面——与 MCP 写路径同源）
    seed_bid_project(&root);
    let resp = call(&ctx, json!({"id":"t-bid-s1","cmd":"bid.state"}));
    let bs = result(&resp);
    r.check(
        "bid.state(真实项目)",
        resp["ok"] == json!(true)
            && bs["present"] == json!(true)
            && bs["project"]["name"] == json!("selftest 项目")
            && bs["state"]["status"].is_string()
            && bs["quick_stats"]["requirements"] == json!(1)
            && bs["quick_stats"]["sections_leaf"] == json!(1),
        format!("status={} reqs={}", bs["state"]["status"], bs["quick_stats"]["requirements"]),
    );
    let resp = call(&ctx, json!({"id":"t-bid-o1","cmd":"bid.outline"}));
    let bo = result(&resp);
    r.check(
        "bid.outline(章节树)",
        bo["present"] == json!(true)
            && bo["nodes"].as_array().map(|a| a.len() == 2).unwrap_or(false)
            && bo["nodes"][1]["chapter_file"] == json!("chapters/SEC-S2.json")
            && bo["stats"]["sections"] == json!(2),
        format!("nodes={}", bo["nodes"].as_array().map(|a| a.len()).unwrap_or(0)),
    );
    // #313 批 B：真实项目的矩阵面（种子面：1 条技术参数，无大纲响应 →
    // NOT_RESPONDED 非阻断；行形状/统计摘要/★统计口在场）
    let resp = call(&ctx, json!({"id":"t-bid-m1","cmd":"bid.matrix"}));
    let bm = result(&resp);
    r.check(
        "bid.matrix(真实项目)",
        resp["ok"] == json!(true)
            && bm["present"] == json!(true)
            && bm["rows"].as_array().map(|a| a.len() == 1).unwrap_or(false)
            && bm["rows"][0]["requirement"]["id"] == json!("REQ-0001")
            && bm["rows"][0]["status"] == json!("NOT_RESPONDED")
            && bm["summary"]["by_status"]["NOT_RESPONDED"] == json!(1)
            && bm["summary"]["blocking"] == json!(0)
            && bm["star_summary"]["total"] == json!(0)
            && bm["fetched_pages"] == json!(1),
        format!("rows={} status={}", bm["rows"].as_array().map(|a| a.len()).unwrap_or(0), bm["rows"][0]["status"]),
    );
    // db.json 被外部进程改写（bid-mcp-stdio / Agent）→ 服务缓存按指纹重开
    {
        let mut svc = bid_tools::service::BidService::open(&root).unwrap();
        let st = svc.store_mut();
        st.set_requirements(vec![bid_domain::Requirement {
            id: "REQ-0002".into(),
            category: "资格条件".into(),
            clause_no: None,
            anchors: vec![bid_domain::Anchor {
                file: "A-招标文件.docx".into(),
                kind: "para".into(),
                locator: "第一章 1.4/REQ-0002".into(),
                excerpt: "投标人须具备电子与智能化专业承包二级资质".into(),
                ..bid_domain::Anchor::default()
            }],
            params: std::collections::HashMap::new(),
            source_file: "A-招标文件.docx".into(),
        }])
        .unwrap();
            svc.checkpoint().unwrap();
    }
    let resp = call(&ctx, json!({"id":"t-bid-s2","cmd":"bid.state"}));
    r.check(
        "bid.state(db变更重开)",
        resp["ok"] == json!(true) && result(&resp)["quick_stats"]["requirements"] == json!(2),
        format!("reqs={}", result(&resp)["quick_stats"]["requirements"]),
    );
    // #313 批 B：db.json 变更后矩阵缓存同样重开——新 REQ-0002（资格条件）
    // 是必选未响应 → 阻断计数 = 1（旧缓存会只看到 1 条 REQ）
    let resp = call(&ctx, json!({"id":"t-bid-m2","cmd":"bid.matrix"}));
    let bm2 = result(&resp);
    r.check(
        "bid.matrix(db变更重开)",
        resp["ok"] == json!(true)
            && bm2["rows"].as_array().map(|a| a.len() == 2).unwrap_or(false)
            && bm2["summary"]["blocking"] == json!(1)
            && bm2["rows"].as_array()
                .map(|a| a.iter().any(|row| row["requirement"]["id"] == json!("REQ-0002")
                    && row["blocking"] == json!(true)))
                .unwrap_or(false),
        format!("rows={} blocking={}", bm2["rows"].as_array().map(|a| a.len()).unwrap_or(0), bm2["summary"]["blocking"]),
    );
    // #313 批 D：覆盖报告面（同一种子项目——未导入文件的工具面诚实口径：
    // total_blocks=0 + next 引导导入，不是错误）；三态分账 / ★聚合恒零
    let resp = call(&ctx, json!({"id":"t-bid-c1","cmd":"bid.coverage"}));
    let bc = result(&resp);
    r.check(
        "bid.coverage(未导入件)",
        resp["ok"] == json!(true)
            && bc["present"] == json!(true)
            && bc["project"]["name"] == json!("selftest 项目")
            && bc["coverage"]["total_blocks"] == json!(0)
            && bc["coverage"]["files"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && bc["coverage"]["next"].as_str().map(|s| s.contains("import_tender_files")).unwrap_or(false)
            && bc["summary"]["judged_blocks"] == json!(0)
            && bc["summary"]["excluded_blocks"] == json!(0)
            && bc["summary"]["unjudged_blocks"] == json!(0)
            && bc["star"]["total"]["star_truth"] == json!(0),
        format!("total={} next={}", bc["coverage"]["total_blocks"], bc["coverage"]["next"]),
    );

    // ---- #313 批 C：自评数据面（bid.quality / bid.score）
    // 早态（REQUIREMENTS_EXTRACTED，矩阵未建）→ 工具面 E_STATE 透传为
    // 壳侧 `state` 码（UI 据此分支「尚未开放」引导卡，不是故障）
    let resp = call(&ctx, json!({"id":"t-bid-q0","cmd":"bid.quality"}));
    r.check(
        "bid.quality(早态拒绝)",
        resp["ok"] == json!(false) && err_code(&resp) == "state",
        format!("{}", err_code(&resp)),
    );
    let resp = call(&ctx, json!({"id":"t-bid-sc0","cmd":"bid.score"}));
    r.check(
        "bid.score(早态拒绝)",
        resp["ok"] == json!(false) && err_code(&resp) == "state",
        format!("{}", err_code(&resp)),
    );
    // 服务层重建大纲+矩阵（与 MCP 工具同源面）→ MATRIX_READY 后两命令真读
    {
        let mut svc = bid_tools::service::BidService::open(&root).unwrap();
        svc.prepare_outline_and_matrix(bid_domain::outline::OutlineSpec {
            target_total_chars: 400,
            max_reqs_per_leaf: 2,
        })
        .unwrap();
    }
    let resp = call(&ctx, json!({"id":"t-bid-q1","cmd":"bid.quality"}));
    let bq = result(&resp);
    r.check(
        "bid.quality(矩阵就绪)",
        resp["ok"] == json!(true)
            && bq["present"] == json!(true)
            && bq["quality"]["summary"]["total"].as_u64().unwrap_or(0) >= 1
            && bq["quality"]["submission_readiness"].is_object(),
        format!(
            "sections={} drafted={}",
            bq["quality"]["summary"]["total"],
            bq["quality"]["summary"]["drafted"]
        ),
    );
    let resp = call(&ctx, json!({"id":"t-bid-sc1","cmd":"bid.score"}));
    let bsc = result(&resp);
    r.check(
        "bid.score(矩阵就绪)",
        resp["ok"] == json!(true)
            && bsc["score"]["diagnostic_only"] == json!(true)
            && bsc["score"]["price"].is_null()
            && bsc["score"]["by_item"].is_array(),
        format!(
            "total={} target={}",
            bsc["score"]["total"],
            bsc["score"]["target"]
        ),
    );

    // ---- #603 批 A：治理面（bid.gates / bid.gate_pass）
    // 读面：五门台账 + 空账本警告位（此时三门全未过）
    let resp = call(&ctx, json!({"id":"t-bid-g0","cmd":"bid.gates"}));
    let bg = result(&resp);
    r.check(
        "bid.gates(五门台账)",
        resp["ok"] == json!(true)
            && bg["present"] == json!(true)
            && bg["gates"].as_array().map(|a| a.len() == 5).unwrap_or(false)
            && bg["gates"][0]["gate"] == json!("matrix_approval")
            && bg["gates"][0]["approved"] == json!(false)
            && bg["human_review_complete"] == json!(true)
            && bg["reviews"].as_array().map(|a| a.is_empty()).unwrap_or(false),
        format!("gates={}", bg["gates"].as_array().map(|a| a.len()).unwrap_or(0)),
    );
    // 写面：门序跳跃 → 域层 E_STATE 透传为壳侧 state 码
    let resp = call(&ctx, json!({"id":"t-bid-gp0","cmd":"bid.gate_pass","gate":"pre_export_confirm","decision":"APPROVED"}));
    r.check(
        "bid.gate_pass(门序跳跃拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "state",
        format!("{}", err_code(&resp)),
    );
    // 写面：宿主签发 receipt（#182）→ matrix 门过（human_receipt 路径）
    let resp = call(&ctx, json!({"id":"t-bid-gp1","cmd":"bid.gate_pass","gate":"matrix_approval","decision":"APPROVED","actor_id":"selftest-reviewer"}));
    let bgp = result(&resp);
    r.check(
        "bid.gate_pass(人工过门)",
        resp["ok"] == json!(true)
            && bgp["gate_pass"]["receipt"]["actor"]["actor_type"] == json!("human")
            && bgp["gate_pass"]["receipt"]["method"] == json!("human_receipt")
            && bgp["gate_pass"]["receipt"]["human_confirmed"] == json!(true)
            && bgp["gate_pass"]["receipt"]["finding_ids"].as_array()
                .map(|a| a.is_empty()).unwrap_or(false),
        format!("actor={:?}", bgp["gate_pass"]["receipt"]["actor"]),
    );
    // 读面对账：matrix 门已过 + latest_pass 审计在场
    let resp = call(&ctx, json!({"id":"t-bid-g1","cmd":"bid.gates"}));
    let bg2 = result(&resp);
    r.check(
        "bid.gates(过门后对账)",
        resp["ok"] == json!(true)
            && bg2["gates"][0]["approved"] == json!(true)
            && bg2["gates"][0]["latest_pass"]["actor"] == json!("selftest-reviewer")
            && bg2["reviews"].as_array().map(|a| a.len() == 1).unwrap_or(false),
        format!("reviews={}", bg2["reviews"].as_array().map(|a| a.len()).unwrap_or(0)),
    );
    // 写面：非法门名 → 壳侧入参早拒（不进工具面）
    let resp = call(&ctx, json!({"id":"t-bid-gp2","cmd":"bid.gate_pass","gate":"no_addendum_confirmed","decision":"APPROVED"}));
    r.check(
        "bid.gate_pass(非法门早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );

    // ---- #47 R8（#19 拖拽导入）：ingest_drop 落位（壳拖入路径 → 复制进工作区根；
    //      不依赖 db.json——先拖文件再建项合法；导入仍走 bid.import_files 向导确认）
    let drop_src = scratch_dir().join("招标文件.docx");
    std::fs::write(&drop_src, b"PK\x03\x04selftest-drop-payload").unwrap();
    let resp = call(&ctx, json!({"id":"t-bid-ing","cmd":"bid.ingest_drop","paths":[drop_src.to_string_lossy()]}));
    let ing = result(&resp);
    r.check(
        "bid.ingest_drop(拖入落位)",
        resp["ok"] == json!(true)
            && ing["copied"].as_array().map(|a| a.len() == 1).unwrap_or(false)
            && ing["copied"][0]["rel"].as_str() == Some("招标文件.docx"),
        format!("copied={}", ing["copied"].as_array().map(|a| a.len()).unwrap_or(0)),
    );
    // 幂等重放：同名同内容 → already_present（不按错误回）
    let resp = call(&ctx, json!({"id":"t-bid-ing2","cmd":"bid.ingest_drop","paths":[drop_src.to_string_lossy()]}));
    let ing2 = result(&resp);
    r.check(
        "bid.ingest_drop(幂等重放)",
        resp["ok"] == json!(true)
            && ing2["copied"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && ing2["skipped"][0]["reason"].as_str() == Some("already_present"),
        format!("{}", ing2["skipped"][0]["reason"].as_str().unwrap_or("?")),
    );

    // ---- #194：工作区切换（workspace.open / workspace.current）
    let ws_b = scratch_dir();
    let ws_b_display = Workspace::new(&ws_b).unwrap().root_display();
    let resp = call(&ctx, json!({"id":"t-ws-open","cmd":"workspace.open","path": ws_b.to_string_lossy()}));
    let opened = result(&resp);
    r.check(
        "workspace.open",
        resp["ok"] == json!(true)
            && opened["root"].as_str() == Some(ws_b_display.as_str())
            && opened["changed"] == json!(true),
        format!("{} → {}", opened["previous"], opened["root"]),
    );
    // 切换后的命令面全走新根（fs.tree / app.info 一致）
    let resp = call(&ctx, json!({"id":"t-ws-tree","cmd":"fs.tree"}));
    r.check(
        "fs.tree(切换后新根)",
        result(&resp)["root"].as_str() == Some(ws_b_display.as_str()),
        format!("{}", result(&resp)["root"]),
    );
    let resp = call(&ctx, json!({"id":"t-ws-cur","cmd":"workspace.current"}));
    r.check(
        "workspace.current",
        result(&resp)["root"].as_str() == Some(ws_b_display.as_str()),
        format!("{}", result(&resp)["root"]),
    );
    // 幂等：重复打开同一工作区 changed=false
    let resp = call(&ctx, json!({"id":"t-ws-again","cmd":"workspace.open","path": ws_b.to_string_lossy()}));
    r.check(
        "workspace.open(幂等)",
        resp["ok"] == json!(true) && result(&resp)["changed"] == json!(false),
        format!("{resp}"),
    );
    // 记忆落盘（重启停留口径）+ 读回一致
    r.check(
        "last-workspace 记忆",
        recent::last_workspace().map(|p| p.ends_with(ws_b.file_name().unwrap_or_default())).unwrap_or(false),
        format!("{:?}", recent::last_workspace_path()),
    );
    // 失败不换根：不存在的目录 → not_found 且现工作区不变
    let ghost = root.join("no-such-dir");
    let resp = call(&ctx, json!({"id":"t-ws-ghost","cmd":"workspace.open","path": ghost.to_string_lossy()}));
    let resp2 = call(&ctx, json!({"id":"t-ws-after","cmd":"workspace.current"}));
    r.check(
        "workspace.open(失败不换根)",
        resp["ok"] == json!(false) && err_code(&resp) == "not_found"
            && result(&resp2)["root"].as_str() == Some(ws_b_display.as_str()),
        format!("err={} cur={}", err_code(&resp), result(&resp2)["root"]),
    );
    let _ = std::fs::remove_dir_all(&ws_b);

    println!();
    println!("== {} passed, {} failed ==", r.pass, r.fail);
    let _ = std::fs::remove_dir_all(&root);
    if r.fail == 0 {
        0
    } else {
        1
    }
}
