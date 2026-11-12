//! `--selftest`：无窗口把 IPC 全链路跑一遍（CI/冒烟用）。
//!
//! 覆盖：ping / app.info / fs.tree / fs.read / fs.readBytes / fs.writeBytes(happy+denied)
//!       / fs.stat / fs.mkdir / path-guard(../ 与绝对越界) / 大响应落盘与取回 / recent 往返
//!       / history.list / unknown_cmd / bad_json
//!       / mcp.status / llm.status+save 往返（#76）/ fspec.status（#76）
//!       / bid.state+bid.outline（#313 批 A：无 db.json 干净 not_found / 真实项目读取 / db.json 外部变更后缓存重开）
//!       / bid.quality+bid.score（#313 批 C：早态 E_STATE→state 码 / MATRIX_READY 后真实读取）
//!       / bid.gates+bid.gate_pass（#603 批 A：五门台账 / 人工过门宿主签发 receipt / 门序跳跃拒 / 非法门早拒）
//!       / bid.matrix（#603 批 B overrides 读面）+ bid.matrix_override（无理由拒）
//!       / bid.addenda+bid.addendum_waiver+bid.no_addendum_confirm（#603 批 C：补遗台账 / 全局确认 / 幽灵件拒 / 空白理由早拒）
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
    /// 平台/环境门跳过的项（AGENTS.md §13.2：SKIP 显式可见，不入通过也不入失败——
    /// 汇总行单独报，避免「假绿」或「静默吞」两端）
    skip: usize,
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
    /// 环境门跳过（缺件/平台不可种）——显式横幅 + 独立计数，不冒充通过
    fn skip(&mut self, name: &str, why: &str) {
        self.skip += 1;
        println!("SKIP  {name}：{why}");
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
    let mut r = Report { pass: 0, fail: 0, skip: 0 };
    println!("== mang-app --selftest ==");
    println!("version = {}", env!("CARGO_PKG_VERSION"));
    println!("temp    = {}", display(&std::env::temp_dir()));

    let root = scratch_dir();
    // #89 批 2：业绩库隔离——selftest 进程级 BID_PERF_LIB 指向 scratch。
    // 否则 resolve_library_path 落 ~/.mang/performance-library.json（用户
    // 真实库），selftest 的登记条目会污染用户数据。本进程首个 BidService
    // 创建前设置即可（ensure_locked 惰性建服务，逐次读 env）。
    std::env::set_var("BID_PERF_LIB", root.join("perf-lib.json"));
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
    // ---- #47 R18：fs.tree 截断诚实面——深度上限截到有内容的目录必须
    //      亮 truncated 旗（旧实现静默空——消费方把「看不见」当「没有」：
    //      向导宣称「工作区里没有可导入的文件」）；全量可见时不虚报。
    //      自检工作区 sub/deep/note.txt 三层：depth=1 截断 sub 展开 → 亮旗。
    let resp18 = call(&ctx, json!({"id":"t-tree18","cmd":"fs.tree","depth":1}));
    let tree18 = result(&resp18);
    r.check(
        "fs.tree 深度截断亮旗",
        tree18["truncated"] == json!(true),
        format!("truncated={}", tree18["truncated"]),
    );
    r.check(
        "fs.tree 全量不虚报截断",
        tree["truncated"] == json!(false),
        format!("truncated={}", tree["truncated"]),
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
    // #47 R25：无 db.json → 证据读面同样干净拒绝（不落副作用）
    let resp = call(&ctx, json!({"id":"t-bid-ev0","cmd":"bid.evidence"}));
    r.check(
        "bid.evidence(无db.json)",
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
    // #47 R25：真实项目的证据台账读面（list 过滤 + search 检索真链路往返）
    let resp = call(&ctx, json!({"id":"t-bid-ev1","cmd":"bid.evidence","filters":{"kind":"qualification"}}));
    let bev = result(&resp);
    r.check(
        "bid.evidence(真实项目·kind过滤)",
        resp["ok"] == json!(true)
            && bev["present"] == json!(true)
            && bev["evidence"]["items"].is_array()
            && bev["evidence"]["total"].is_u64(),
        format!("total={}", bev["evidence"]["total"]),
    );
    let resp = call(&ctx, json!({"id":"t-bid-ev2","cmd":"bid.evidence_search","query":"selftest"}));
    let bes = result(&resp);
    r.check(
        "bid.evidence_search(真实项目·检索)",
        resp["ok"] == json!(true)
            && bes["present"] == json!(true)
            && bes["search"]["hits"].is_array()
            && bes["search"]["total"].is_u64(),
        format!("hits_total={}", bes["search"]["total"]),
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

    // #47 R27（#88 Q2）：★漏标明细读面（与 coverage 同种子——files 空的
    // 诚实口径：checked=0 + all_clear + gaps 空，不是错误；真件 8★ 明细
    // 链在 bid.rs 单测 star_gaps_reads_real_missing_detail 双保险）
    let resp = call(&ctx, json!({"id":"t-bid-sg1","cmd":"bid.star_gaps"}));
    let bsg = result(&resp);
    r.check(
        "bid.star_gaps(未导入件空态)",
        resp["ok"] == json!(true)
            && bsg["present"] == json!(true)
            && bsg["project"]["name"] == json!("selftest 项目")
            && bsg["star_gaps"]["files"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && bsg["star_gaps"]["checked_files"] == json!(0)
            && bsg["star_gaps"]["all_clear"] == json!(true)
            && bsg["star_gaps"]["total"]["star_missing"] == json!(0),
        format!(
            "checked={} miss={}",
            bsg["star_gaps"]["checked_files"],
            bsg["star_gaps"]["total"]["star_missing"]
        ),
    );

    // #47 R28（#88 Q3）：★补标直通——参数早拒面（负 block_idx / 空
    // file_id：bad_args 零副作用不进工具面；真件受理链在 bid.rs 单测
    // star_mark_captures_missing_star——含 submitted 旁路账本落库对账）
    let resp = call(&ctx, json!({"id":"t-bid-sm1","cmd":"bid.star_mark","file_id":"TF-0001","block_idx":-1,"statement":"x"}));
    r.check(
        "bid.star_mark(负块号早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );
    let resp = call(&ctx, json!({"id":"t-bid-sm2","cmd":"bid.star_mark","file_id":"","block_idx":3,"statement":"x"}));
    r.check(
        "bid.star_mark(空文件号早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
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

    // ---- #89 R30：评分推演面（bid.price——score_price 试算/反推 + score_section 章节细查）
    // 试算面是纯计算器（无状态门——报价决策发生在起草之前也成立）；
    // 章节细查走 route_guard + 已起草叶前置。工具面零重实现：B1/B2
    // (#100) 的裁决全在工具层，壳只做聚合 + 参数透传。
    // ① 纯推荐模式无竞争报价 → B1 响亮拒（最优价无界——不能静默给半答案；
    //    E_UNPROCESSABLE 透传为壳侧 bad_args 码）
    let resp = call(&ctx, json!({"id":"t-bid-pr0","cmd":"bid.price"}));
    r.check(
        "bid.price(纯推荐无竞争拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );
    // ② 试算 + 反推同场（bid_price + others → score/detail + optimal + analysis）
    let resp = call(&ctx, json!({
        "id":"t-bid-pr1","cmd":"bid.price",
        "method":"average", "coefficient":0.95, "max_score":30,
        "bid_price":950.0, "others":[1000.0, 900.0],
    }));
    let bpr = result(&resp);
    r.check(
        "bid.price(试算+反推)",
        resp["ok"] == json!(true)
            && bpr["present"] == json!(true)
            && bpr["action"] == json!("trial")
            && bpr["price"]["score"].is_number()
            && bpr["price"]["optimal_price"].is_number()
            && bpr["price"]["expected_score_at_optimal"].is_number()
            && bpr["price"]["analysis"].is_string(),
        format!(
            "score={:?} optimal={:?}",
            bpr["price"]["score"], bpr["price"]["optimal_price"]
        ),
    );
    // ③ 基准价法（budget 必需——B1 validate 裁决单义性）
    let resp = call(&ctx, json!({
        "id":"t-bid-pr2","cmd":"bid.price",
        "method":"benchmark", "coefficient":0.9, "budget":1200.0, "max_score":40,
        "bid_price":1080.0, "others":[1100.0],
    }));
    let bpr2 = result(&resp);
    r.check(
        "bid.price(基准价法)",
        resp["ok"] == json!(true) && bpr2["price"]["score"].is_number(),
        format!("score={:?}", bpr2["price"]["score"]),
    );
    // ④ 非法方法串 → 工具面 E_UNPROCESSABLE 透传（值域裁决在 B1 解析层，
    //    壳侧映射 bad_args）
    let resp = call(&ctx, json!({"id":"t-bid-pr3","cmd":"bid.price","method":"满脑门定价"}));
    r.check(
        "bid.price(非法方法拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );
    // ⑤ 章节细查缺 section_id → 壳侧入参早拒（不进工具面）
    let resp = call(&ctx, json!({"id":"t-bid-pr4","cmd":"bid.price","action":"section"}));
    r.check(
        "bid.price(section缺参早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );
    // ⑥ 幽灵章节 → not_found 透传
    let resp = call(&ctx, json!({"id":"t-bid-pr5","cmd":"bid.price","action":"section","section_id":"SEC-GHOST"}));
    r.check(
        "bid.price(幽灵章节拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "not_found",
        format!("{}", err_code(&resp)),
    );
    // ⑦ 真实叶（服务层 set_section_content 直写——complete_revision 同款
    //    真源面，绕开 draft readiness 闸使本测聚焦壳聚合）→ diagnostic_only
    //    + 章节回执
    {
        let mut svc = bid_tools::service::BidService::open(&root).unwrap();
        let sid = svc
            .store()
            .sections()
            .iter()
            .find(|n| n.parent_id.is_some() && n.content.is_none())
            .map(|n| n.id.clone())
            .expect("selftest 大纲应有未起草叶");
        let _ = svc
            .store_mut()
            .set_section_content(&sid, "评分推演自测正文：本章对招标要求逐条响应，参数达标，工艺成熟，人员配置齐全。".to_string())
            .unwrap();
        svc.checkpoint().unwrap();
        let resp = call(&ctx, json!({
            "id":"t-bid-pr6","cmd":"bid.price","action":"section","section_id":sid,
        }));
        let bps = result(&resp);
        r.check(
            "bid.price(章节细查)",
            resp["ok"] == json!(true)
                && bps["action"] == json!("section")
                && bps["section"]["diagnostic_only"] == json!(true)
                && bps["section"]["section_id"].is_string(),
            format!("section_id={:?}", bps["section"]["section_id"]),
        );
    }

    // ---- #89 批 2：业绩库面（bid.performance——#315 四工具的壳聚合）
    // 壳面与工具面的路由差异（见 bid.rs 文档注释）：库操作无项目路由但
    // 壳恒在已打开项目上下文（ensure_locked 要 db.json）；库隔离走进程级
    // BID_PERF_LIB（run() 入口已设）。真件全链（材料匹配→证据登记→绑定→
    // 写入→幂等）在 bid-mcp perf_tools_tool.rs write_section_full_flow——
    // 本面聚焦壳聚合/参数早拒/拒绝码透传。
    // 复用 price 批刚写入正文的叶（quality 批 prepare_outline_and_matrix 已
    // 重建大纲——章节 ID 动态取，不硬编码）
    let drafted_sid = {
        let svc0 = bid_tools::service::BidService::open(&root).unwrap();
        svc0
            .store()
            .sections()
            .iter()
            .find(|n| n.parent_id.is_some() && n.content.is_some())
            .map(|n| n.id.clone())
            .expect("price 批应已写入一叶正文")
    };
    // ① list：新库首读（BID_PERF_LIB 指向 scratch 新路径→ load 缺文件=空库）
    // owner_name=null（未登记库主）/ persisted=true（路径已钉）——真读工具面
    let resp = call(&ctx, json!({"id":"t-bid-pf0","cmd":"bid.performance"}));
    let bpf0 = result(&resp);
    r.check(
        "bid.performance(库清单读面)",
        resp["ok"] == json!(true)
            && bpf0["action"] == json!("list")
            && bpf0["library"]["entries"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && bpf0["library"]["library_persisted"] == json!(true)
            && bpf0["library"]["owner_name"].is_null(),
        format!("entries={:?}", bpf0["library"]["entries"].as_array().map(|a| a.len())),
    );
    // ② register：一条登记（owner_name + entries）→ added_count=1 + 落盘
    let resp = call(&ctx, json!({
        "id":"t-bid-pf1","cmd":"bid.performance","action":"register",
        "owner_name":"自测科技有限公司",
        "entries":[{
            "name":"智慧园区弱电工程合同","client":"示例产业园运营有限公司",
            "amount_wan":640.0,"completed_on":"2025-05-20",
            "categories":["弱电工程"],
            "materials":["材料/EV-03-类似业绩合同.pdf"],
            "key_points":["一次验收通过"],
        }],
    }));
    let bpf1 = result(&resp);
    let perf_id = bpf1["register"]["added"][0].as_str().unwrap_or("").to_string();
    r.check(
        "bid.performance(登记一条)",
        resp["ok"] == json!(true)
            && bpf1["register"]["added_count"] == json!(1)
            && bpf1["register"]["total_entries"] == json!(1)
            && !perf_id.is_empty()
            && bpf1["register"]["library_persisted"] == json!(true),
        format!("added={:?} id={perf_id:?}", bpf1["register"]["added_count"]),
    );
    // ③ 幂等重放：同语义四元组 → deduplicated 回显既有 id（不重复登记）
    let resp = call(&ctx, json!({
        "id":"t-bid-pf2","cmd":"bid.performance","action":"register",
        "entries":[{
            "name":"智慧园区弱电工程合同","client":"示例产业园运营有限公司",
            "amount_wan":640.0,"completed_on":"2025-05-20",
        }],
    }));
    let bpf2 = result(&resp);
    r.check(
        "bid.performance(幂等重放)",
        resp["ok"] == json!(true)
            && bpf2["register"]["added_count"] == json!(0)
            && bpf2["register"]["deduplicated"].as_array().map(|a| a.len() == 1).unwrap_or(false)
            && bpf2["register"]["total_entries"] == json!(1),
        format!("dedup={:?}", bpf2["register"]["deduplicated"]),
    );
    // ④ list 过滤：keyword 命中 1 条 / 不命中 0 条（值域裁决在工具面）
    let resp = call(&ctx, json!({
        "id":"t-bid-pf3","cmd":"bid.performance",
        "filters":{"keyword":"弱电"},
    }));
    let bpf3 = result(&resp);
    r.check(
        "bid.performance(过滤命中)",
        resp["ok"] == json!(true)
            && bpf3["library"]["returned"] == json!(1)
            && bpf3["library"]["entries"][0]["perf_id"].is_string(),
        format!("returned={:?}", bpf3["library"]["returned"]),
    );
    let resp = call(&ctx, json!({
        "id":"t-bid-pf4","cmd":"bid.performance",
        "filters":{"keyword":"不存在的关键词"},
    }));
    let bpf4 = result(&resp);
    r.check(
        "bid.performance(过滤不命中)",
        resp["ok"] == json!(true) && bpf4["library"]["returned"] == json!(0),
        format!("returned={:?}", bpf4["library"]["returned"]),
    );
    // ⑤ recommend：只读匹配推荐（项目语料 + 弃权因子；本种子无业绩章 →
    // suggested_section=null + next 引导，诚实面不伪造建议位）
    let resp = call(&ctx, json!({
        "id":"t-bid-pf5","cmd":"bid.performance","action":"recommend","budget_wan":700.0,
    }));
    let bpf5 = result(&resp);
    r.check(
        "bid.performance(匹配推荐)",
        resp["ok"] == json!(true)
            && bpf5["recommend"]["recommendations"].is_array()
            && bpf5["recommend"]["library_total"] == json!(1)
            && bpf5["recommend"]["signals"].is_object()
            && bpf5["recommend"]["suggested_section"].is_null()
            && bpf5["recommend"]["next"].is_string(),
        format!("lib={:?} signals 有场", bpf5["recommend"]["library_total"]),
    );
    // ⑥ write：缺 section_id → 壳侧早拒（不进工具面）
    let resp = call(&ctx, json!({
        "id":"t-bid-pf6","cmd":"bid.performance","action":"write",
        "perf_ids":["PERF-0001"],
    }));
    r.check(
        "bid.performance(write缺参早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );
    // ⑦ write 到真实叶（price 批已写入正文的叶）→ readiness 门拦（本种子
    // 无导入件/无证据——工具面 E_UNPROCESSABLE 透传为 bad_args，文案带
    // 指引；零副作用）
    let resp = call(&ctx, json!({
        "id":"t-bid-pf7","cmd":"bid.performance","action":"write",
        "section_id":drafted_sid,"perf_ids":[perf_id],
    }));
    r.check(
        "bid.performance(readiness门拦)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args"
            && resp["message"].as_str().unwrap_or("").contains(&format!("章节 {drafted_sid}")),
        format!("{}", resp["message"].as_str().unwrap_or("")),
    );

    // ---- #89 批 2：分段改写面（bid.segment——#254 段账本的壳聚合）
    // 真链覆盖：域层 append_section_segment 直种一段（绕开 readiness 闸
    // ——与 price 批 set_section_content 同款真源面策略），壳侧 list/rewrite
    // 走真工具面。readiness 门在工具面单测（segments/readiness 系）。
    // ① list 缺 section_id → 壳侧早拒
    let resp = call(&ctx, json!({"id":"t-bid-sg0","cmd":"bid.segment"}));
    r.check(
        "bid.segment(缺参早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );
    // ② 幽灵章节 → not_found 透传
    let resp = call(&ctx, json!({
        "id":"t-bid-sg1","cmd":"bid.segment","action":"list","section_id":"SEC-GHOST",
    }));
    r.check(
        "bid.segment(幽灵章节拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "not_found",
        format!("{}", err_code(&resp)),
    );
    // ③ 种段 + list 真数据（段清单 + 合稿统计）。域层种子面：目标叶已有
    // 正文（price 批 set_section_content）→ 首次入账本时既有正文自动入册
    // 为第 1 段（idem=seed:existing-content），本批种段为第 2 段——清单 2 条
    {
        let mut svc = bid_tools::service::BidService::open(&root).unwrap();
        let _seg = svc
            .store_mut()
            .append_section_segment(
                &drafted_sid,
                "分段改写自测段：本章对招标要求逐条响应，工艺成熟可靠。".to_string(),
                "selftest-seg-1",
            )
            .expect("域层种段应成功（无 readiness 闸）");
        svc.checkpoint().unwrap();
    }
    let resp = call(&ctx, json!({
        "id":"t-bid-sg2","cmd":"bid.segment","action":"list","section_id":drafted_sid,
    }));
    let bsg2 = result(&resp);
    let segs_arr = bsg2["segments"]["segments"].as_array().cloned().unwrap_or_default();
    let mine = segs_arr
        .iter()
        .find(|s| s["idem_key"].as_str() == Some("selftest-seg-1"))
        .cloned()
        .unwrap_or(Value::Null);
    r.check(
        "bid.segment(段账本读面)",
        resp["ok"] == json!(true)
            && bsg2["action"] == json!("list")
            && segs_arr.len() == 2
            && mine["version"] == json!(1)
            && mine["chars"].is_number()
            && bsg2["segments"]["assembled_chars"].is_number()
            && bsg2["segments"]["target_chars"].is_number(),
        format!(
            "segs={} assembled={:?}",
            segs_arr.len(),
            bsg2["segments"]["assembled_chars"]
        ),
    );
    // ④ rewrite 缺参早拒（segment_id / content 两面）
    let resp = call(&ctx, json!({"id":"t-bid-sg3","cmd":"bid.segment","action":"rewrite","content":"新内容"}));
    r.check(
        "bid.segment(rewrite缺段号早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );
    let resp = call(&ctx, json!({"id":"t-bid-sg4","cmd":"bid.segment","action":"rewrite","segment_id":"SEG-0001"}));
    r.check(
        "bid.segment(rewrite缺内容早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );
    // ⑤ rewrite 真段：改内容 → changed + version 递增 + 合稿统计回显
    let seg_id = mine["id"].as_str().unwrap_or("").to_string();
    let resp = call(&ctx, json!({
        "id":"t-bid-sg5","cmd":"bid.segment","action":"rewrite",
        "segment_id":seg_id,
        "content":"分段改写自测段（修订后）：响应升级，新增运维承诺与人员配置。",
    }));
    let bsg5 = result(&resp);
    r.check(
        "bid.segment(局部改写)",
        resp["ok"] == json!(true)
            && bsg5["action"] == json!("rewrite")
            && bsg5["rewrite"]["changed"] == json!(true)
            && bsg5["rewrite"]["segment"]["version"].as_u64().unwrap_or(0) >= 2
            && bsg5["rewrite"]["assembled_chars"].is_number(),
        format!("ver={:?} changed={:?}", bsg5["rewrite"]["segment"]["version"], bsg5["rewrite"]["changed"]),
    );
    // ⑥ 幽灵段 → not_found 透传
    let resp = call(&ctx, json!({
        "id":"t-bid-sg6","cmd":"bid.segment","action":"rewrite",
        "segment_id":"SEG-GHOST","content":"内容",
    }));
    r.check(
        "bid.segment(幽灵段拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "not_found",
        format!("{}", err_code(&resp)),
    );
    // ⑦ 段级 CAS 过期 → conflict 码（#89 批 2 新映射——重读后重试，非故障）
    let resp = call(&ctx, json!({
        "id":"t-bid-sg7","cmd":"bid.segment","action":"rewrite",
        "segment_id":seg_id,"content":"过期版本的改写内容","expected_version":999,
    }));
    r.check(
        "bid.segment(CAS过期conflict)",
        resp["ok"] == json!(false) && err_code(&resp) == "conflict",
        format!("{}", err_code(&resp)),
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

    // ---- #47 R26（递归目录拖入）：目录落位按原结构（rel 携带层级前缀）+
    //      白名单分账 + 截断旗不亮（预算内）+ 幂等重放零复制
    let dir_src = scratch_dir().join("R26材料包");
    std::fs::create_dir_all(dir_src.join("正文")).unwrap();
    std::fs::write(dir_src.join("正文").join("技术标.docx"), b"PK\x03\x04r26-dir-payload").unwrap();
    std::fs::write(dir_src.join("说明书.txt"), b"not importable").unwrap();
    let resp = call(
        &ctx,
        json!({"id":"t-bid-ing26","cmd":"bid.ingest_drop","paths":[dir_src.to_string_lossy()]}),
    );
    let ing26 = result(&resp);
    r.check(
        "bid.ingest_drop(目录递归落位)",
        resp["ok"] == json!(true)
            && ing26["copied"].as_array().map(|a| a.len() == 1).unwrap_or(false)
            && ing26["copied"][0]["rel"].as_str()
                == Some("R26材料包/正文/技术标.docx")
            && ing26["skipped"]
                .as_array()
                .map(|a| a.iter().any(|s| s["reason"] == json!("ext_blocked")))
                .unwrap_or(false)
            && ing26["truncated"] == json!(false),
        format!(
            "rel={:?} truncated={}",
            ing26["copied"][0]["rel"].as_str(),
            ing26["truncated"]
        ),
    );
    let resp = call(
        &ctx,
        json!({"id":"t-bid-ing26b","cmd":"bid.ingest_drop","paths":[dir_src.to_string_lossy()]}),
    );
    let ing26b = result(&resp);
    r.check(
        "bid.ingest_drop(目录重拖幂等)",
        resp["ok"] == json!(true)
            && ing26b["copied"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && ing26b["skipped"]
                .as_array()
                .map(|a| a.iter().any(|s| s["reason"] == json!("already_present")))
                .unwrap_or(false),
        format!(
            "copied={} skipped={}",
            ing26b["copied"].as_array().map(|a| a.len()).unwrap_or(0),
            ing26b["skipped"].as_array().map(|a| a.len()).unwrap_or(0)
        ),
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
    // ---- #47 R17：拖拽白名单与解析面对齐——.ods 摘除。解析路由（bid-tools
    //      service.rs）只认 docx/xlsx/pdf/doc 四类，.ods 落位后导入必失败
    //      （「不支持的文件类型」）——白名单在壳侧拒落位（ext_blocked 分账，
    //      不按错误回），用户得到明确的合法四类指引而不是白跑一趟。
    let ods_src = scratch_dir().join("报价清单.ods");
    std::fs::write(&ods_src, b"PK\x03\x04selftest-ods-zip-payload").unwrap();
    let resp = call(&ctx, json!({"id":"t-bid-ingods","cmd":"bid.ingest_drop","paths":[ods_src.to_string_lossy()]}));
    let ing_ods = result(&resp);
    r.check(
        "bid.ingest_drop(.ods 摘除对齐解析面)",
        resp["ok"] == json!(true)
            && ing_ods["copied"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && ing_ods["skipped"][0]["reason"].as_str() == Some("ext_blocked")
            && ing_ods["skipped"][0]["detail"]
                .as_str()
                .map(|d| d.contains("docx/xlsx/pdf/doc"))
                .unwrap_or(false),
        format!(
            "copied={} detail={}",
            ing_ods["copied"].as_array().map(|a| a.len()).unwrap_or(0),
            ing_ods["skipped"][0]["detail"].as_str().unwrap_or("?"),
        ),
    );
    // ---- #47 R10（平台区分③）：基名跨平台守卫——CON.docx 在 Linux 真实
    //      可创建（文件在场、后缀过白名单），但落位被守卫分账拒绝
    // 平台门（AGENTS.md §13.1）：CON.docx 在 Windows 上映射控制台设备——
    // 种不出真文件（is_file 探测揭穿）。Linux 上真文件在场才跑落位守卫
    // 断言；Windows 侧 SKIP 显式可见（import_files 的纯字符串守卫项
    // 不依赖文件，照跑）。
    let con_src = scratch_dir().join("CON.docx");
    let con_seeded = std::fs::write(&con_src, b"PK\x03\x04selftest-reserved")
        .map(|_| con_src.is_file())
        .unwrap_or(false);
    if con_seeded {
        let resp = call(&ctx, json!({"id":"t-bid-ing3","cmd":"bid.ingest_drop","paths":[con_src.to_string_lossy()]}));
        let ing3 = result(&resp);
        r.check(
            "bid.ingest_drop(保留名守卫)",
            resp["ok"] == json!(true)
                && ing3["copied"].as_array().map(|a| a.is_empty()).unwrap_or(false)
                && ing3["skipped"][0]["reason"].as_str() == Some("name_not_portable"),
            format!("skipped={}", ing3["skipped"][0]["reason"].as_str().unwrap_or("?")),
        );
    } else {
        r.skip("bid.ingest_drop(保留名守卫)", "本平台种不出真 CON.docx 源文件（Windows 设备名映射）——Linux 断言面");
    }
    let resp = call(&ctx, json!({"id":"t-bid-impnp","cmd":"bid.import_files","files":[{"upload_ref":"CON.docx","kind":"招标文件"}]}));
    r.check(
        "bid.import_files(保留名基 bad_args)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("code={}", err_code(&resp)),
    );
    // ---- #47 R11（平台区分④）：大小写不敏感同名去重——Windows FS 占位
    //      语义预演（招标文件.docx 在场，拖 招标文件.DOCX 同内容 →
    //      CI 占位幂等，不放行第二份——拷到 Windows 不互覆）
    let ci_src = scratch_dir().join("招标文件.docx");
    std::fs::write(&ci_src, b"PK\x03\x04selftest-ci-same").unwrap();
    let ci_var = scratch_dir().join("招标文件.DOCX");
    std::fs::copy(&ci_src, &ci_var).unwrap();
    let resp = call(&ctx, json!({"id":"t-bid-ci1","cmd":"bid.ingest_drop","paths":[ci_src.to_string_lossy()]}));
    let resp = call(&ctx, json!({"id":"t-bid-ci2","cmd":"bid.ingest_drop","paths":[ci_var.to_string_lossy()]}));
    let ci2 = result(&resp);
    r.check(
        "bid.ingest_drop(大小写变体幂等)",
        resp["ok"] == json!(true)
            && ci2["copied"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && ci2["skipped"][0]["reason"].as_str() == Some("already_present")
            && ci2["skipped"][0]["detail"].as_str().unwrap_or("").contains("招标文件"),
        format!("detail={}", ci2["skipped"][0]["detail"].as_str().unwrap_or("?")),
    );
    // ---- #47 R12（平台区分⑤）：MAX_PATH 预检——深目录工作区（40 层真
    //      目录 ~280 字符根）+ 合法基名 → 落位总长 > 259 → path_too_long
    //      分账（Linux 能落但拷 Windows 创建即失败，预演同拒）。测完切回
    //      原工作区（后续 #603 段依赖本 scratch 的 db.json）。
    let deep_ws = scratch_dir();
    let mut deep_cur = deep_ws.clone();
    for i in 0..40 {
        deep_cur = deep_cur.join(format!("d{i:02}xx"));
    }
    std::fs::create_dir_all(&deep_cur).unwrap();
    let mp_src = scratch_dir().join("标书.docx");
    std::fs::write(&mp_src, b"PK\x03\x04selftest-maxpath").unwrap();
    let resp = call(&ctx, json!({"id":"t-ws-deep","cmd":"workspace.open","path": deep_cur.to_string_lossy()}));
    let resp = call(&ctx, json!({"id":"t-bid-mp","cmd":"bid.ingest_drop","paths":[mp_src.to_string_lossy()]}));
    let mp = result(&resp);
    r.check(
        "bid.ingest_drop(MAX_PATH 预检)",
        resp["ok"] == json!(true)
            && mp["copied"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && mp["skipped"][0]["reason"].as_str() == Some("path_too_long"),
        format!("skipped={}", mp["skipped"][0]["reason"].as_str().unwrap_or("?")),
    );
    // 切回原工作区（#603 段的 db.json 在这）
    let resp = call(&ctx, json!({"id":"t-ws-back","cmd":"workspace.open","path": ws.root_display()}));
    r.check(
        "workspace.open(切回原根)",
        resp["ok"] == json!(true),
        format!("{}", ws.root_display()),
    );
    // ---- #47 R13（平台区分⑥）：NFC 归一——NFD 源（é = e + U+0301）
    //      拖入落位为 NFC；NFC 重拖同内容占位幂等（双形态同键）
    let nfd_src = scratch_dir().join("cafe\u{0301}招标.docx");
    std::fs::write(&nfd_src, b"PK\x03\x04selftest-nfc").unwrap();
    let resp = call(&ctx, json!({"id":"t-bid-nfc1","cmd":"bid.ingest_drop","paths":[nfd_src.to_string_lossy()]}));
    let n1 = result(&resp);
    let nfc_rel = n1["copied"][0]["rel"].as_str().unwrap_or("?").to_string();
    r.check(
        "bid.ingest_drop(NFD 落位归一 NFC)",
        resp["ok"] == json!(true)
            && nfc_rel == "caf\u{00e9}招标.docx"
            && !nfc_rel.contains('\u{0301}'),
        format!("rel={nfc_rel}"),
    );
    let nfc_src = scratch_dir().join("caf\u{00e9}招标.docx");
    std::fs::write(&nfc_src, b"PK\x03\x04selftest-nfc").unwrap();
    let resp = call(&ctx, json!({"id":"t-bid-nfc2","cmd":"bid.ingest_drop","paths":[nfc_src.to_string_lossy()]}));
    let n2 = result(&resp);
    r.check(
        "bid.ingest_drop(NFC 重拖占位幂等)",
        resp["ok"] == json!(true)
            && n2["copied"].as_array().map(|a| a.is_empty()).unwrap_or(false)
            && n2["skipped"][0]["reason"].as_str() == Some("already_present"),
        format!("skipped={}", n2["skipped"][0]["reason"].as_str().unwrap_or("?")),
    );
    // ---- #603 批 B：否决死锁人工豁免（bid.matrix_override + overrides 读面）
    // 读面：overrides 空对象恒在（UI 不赌键在场）
    let resp = call(&ctx, json!({"id":"t-bid-mo0","cmd":"bid.matrix"}));
    let bm = result(&resp);
    r.check(
        "bid.matrix(overrides 读面)",
        resp["ok"] == json!(true)
            && bm["overrides"].as_object().is_some(),
        format!("overrides={}", bm["overrides"].as_object().map(|o| o.len()).unwrap_or(0)),
    );
    // 写面：NOT_APPLICABLE + 理由 → 行翻不适用、human 回执（#182）
    let resp = call(&ctx, json!({"id":"t-bid-mo1","cmd":"bid.matrix_override","requirement_id":"REQ-0001","status":"NOT_APPLICABLE","deviation":"规则说明性条款，无可响应正文","actor_id":"selftest-operator"}));
    let bmo = result(&resp);
    r.check(
        "bid.matrix_override(人工豁免)",
        resp["ok"] == json!(true)
            && bmo["override"]["row"]["status"] == json!("NOT_APPLICABLE")
            && bmo["override"]["actor"]["actor_type"] == json!("human"),
        format!("row_status={:?}", bmo["override"]["row"]["status"].as_str()),
    );
    // 读面对账：overrides 面含本行（谁/何时/为何——回溯可查）
    let resp = call(&ctx, json!({"id":"t-bid-mo2","cmd":"bid.matrix"}));
    let bm2 = result(&resp);
    r.check(
        "bid.matrix(豁免后对账)",
        resp["ok"] == json!(true)
            && bm2["overrides"]["REQ-0001"]["status"] == json!("NOT_APPLICABLE")
            && bm2["overrides"]["REQ-0001"]["actor"]["actor_id"] == json!("selftest-operator"),
        format!("deviation={:?}", bm2["overrides"]["REQ-0001"]["deviation"].as_str().map(|s| s.chars().take(12).collect::<String>())),
    );
    // 写面：NOT_APPLICABLE 无理由 → 工具面拒（不可审计的豁免不算豁免）
    let resp = call(&ctx, json!({"id":"t-bid-mo3","cmd":"bid.matrix_override","requirement_id":"REQ-0001","status":"NOT_APPLICABLE"}));
    r.check(
        "bid.matrix_override(无理由拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
    );

    // ---- #603 批 C：补遗豁免（bid.addenda / bid.addendum_waiver / bid.no_addendum_confirm）
    // 读面：无补遗件台账（total=0——NotProvided 素材，不是故障）
    let resp = call(&ctx, json!({"id":"t-bid-ad0","cmd":"bid.addenda"}));
    let bad0 = result(&resp);
    r.check(
        "bid.addenda(补遗台账)",
        resp["ok"] == json!(true)
            && bad0["readiness"]["total"] == json!(0)
            && bad0["waivers"].as_array().map(|a| a.is_empty()).unwrap_or(false),
        format!("total={}", bad0["readiness"]["total"]),
    );
    // 写面：全局无补遗确认（宿主签发 receipt——human 路径）
    let resp = call(&ctx, json!({"id":"t-bid-ad1","cmd":"bid.no_addendum_confirm","reason":"已核对招标文件全册，本项目无补遗/澄清件","actor_id":"selftest-operator"}));
    let bad1 = result(&resp);
    r.check(
        "bid.no_addendum_confirm(全局确认)",
        resp["ok"] == json!(true)
            && bad1["no_addendum_confirm"]["confirmed_no_addendum"]["gate"] == json!("no_addendum_confirmed")
            && bad1["no_addendum_confirm"]["confirmed_no_addendum"]["actor"]["actor_type"] == json!("human"),
        format!("human_confirmed={:?}", bad1["no_addendum_confirm"]["confirmed_no_addendum"]["human_confirmed"]),
    );
    // 读面对账：no_addendum_confirmed 门已过（gates 同源）
    let resp = call(&ctx, json!({"id":"t-bid-ad2","cmd":"bid.gates"}));
    let bad2 = result(&resp);
    r.check(
        "bid.gates(全局确认后对账)",
        resp["ok"] == json!(true)
            && bad2["gates"][4]["gate"] == json!("no_addendum_confirmed")
            && bad2["gates"][4]["approved"] == json!(true),
        format!("latest={:?}", bad2["gates"][4]["latest_pass"]["actor"]),
    );
    // 写面：幽灵件 → 域层 ENotFound（凭空免责拒）
    let resp = call(&ctx, json!({"id":"t-bid-ad3","cmd":"bid.addendum_waiver","file_id":"TF-9999","reason":"x"}));
    r.check(
        "bid.addendum_waiver(幽灵件拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "not_found",
        format!("{}", err_code(&resp)),
    );
    // 写面：空白理由 → 壳侧早拒（不可审计的确认不成确认）
    let resp = call(&ctx, json!({"id":"t-bid-ad4","cmd":"bid.no_addendum_confirm","reason":"  "}));
    r.check(
        "bid.no_addendum_confirm(空白理由早拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("{}", err_code(&resp)),
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

    // ---- #47 R14（平台区分⑦）：混合分隔符矩阵 E2E——全新 DRAFT 工作区，
    //      Windows 形态 upload_ref（资料\技术标.docx）导入成功，且与正斜杠
    //      形态同 file_id（R9 归一 + sha 幂等的 selftest 面锁定）。状态窗
    //      走全新工作区——不为 MATRIX_READY 主线项目放宽状态窗（同 R10 纪律）
    let ws_r14 = scratch_dir();
    std::fs::create_dir_all(ws_r14.join("资料")).unwrap();
    std::fs::write(
        ws_r14.join("资料").join("技术标.docx"),
        include_bytes!("../../../tests/fixtures/wizard19-min.docx"),
    )
    .unwrap();
    let resp = call(&ctx, json!({"id":"t-ws-r14","cmd":"workspace.open","path": ws_r14.to_string_lossy()}));
    r.check(
        "workspace.open(R14 矩阵工作区)",
        resp["ok"] == json!(true),
        format!("{resp}"),
    );
    let resp = call(&ctx, json!({"id":"t-bid-cp14","cmd":"bid.create_project","name":"R14 混合分隔符","bid_deadline":"2026-12-31","mode":"明标"}));
    r.check(
        "bid.create_project(R14 起步)",
        resp["ok"] == json!(true),
        format!("{resp}"),
    );
    // Windows 形态：`资料\技术标.docx` ——归一成 `/` 找到同一文件
    let resp = call(&ctx, json!({"id":"t-bid-im14a","cmd":"bid.import_files","files":[{"upload_ref":"资料\\技术标.docx","kind":"招标文件"}]}));
    let im14a = result(&resp);
    let id14 = im14a["file_ids"][0].clone();
    r.check(
        "bid.import_files(Windows 形态归一导入)",
        resp["ok"] == json!(true) && im14a["totals"]["files"] == json!(1),
        format!("totals={:?}", im14a["totals"]["files"]),
    );
    // ---- #47 R24：per_file.upload_ref 回显调用方归一形态——结果面深层件
    //      消歧（结果表只有 filename 时「资料/技术标.docx」与根下同名件
    //      不可分，rel 才是定位键）。壳侧 R9 归一先行，工具面收到与回显
    //      的是 `/` 形态。
    r.check(
        "bid.import_files(per_file upload_ref 回显)",
        im14a["per_file"][0]["upload_ref"] == json!("资料/技术标.docx"),
        format!("upload_ref={:?}", im14a["per_file"][0]["upload_ref"].as_str()),
    );
    // 正斜杠形态重导 → 同 file_id + deduplicated（两形态一文件，不双入库）
    let resp = call(&ctx, json!({"id":"t-bid-im14b","cmd":"bid.import_files","files":[{"upload_ref":"资料/技术标.docx","kind":"招标文件"}]}));
    let im14b = result(&resp);
    r.check(
        "bid.import_files(两形态同件幂等)",
        resp["ok"] == json!(true)
            && im14b["file_ids"][0] == id14
            && im14b["per_file"][0]["deduplicated"] == json!(true),
        format!("id14={id14} 重放={}", im14b["file_ids"][0]),
    );
    // ---- #47 R26：证据登记写面真链路（状态窗 EState 探针 + MatrixReady 后 成功/幂等）
    // 窗口前置：register_evidence 契约 §11-A = MATRIX_READY+（G2）。先在当前
    // 状态上探 EState（不为测试放宽状态窗——R10 纪律）；随后外部写者推进
    // （与「db.json 被外部进程改写」块同款真服务面：set_requirements +
    // prepare_outline_and_matrix——661 段同款，MCP 同源面）
    let resp = call(&ctx, json!({"id":"t-bid-eva0","cmd":"bid.evidence_register","kind":"qualification","title":"R26 登记测试资质","source_file_id":id14,"subject_name":"selftest","valid_until":"2030-01-01"}));
    r.check(
        "bid.evidence_register(早态 EState 拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "state",
        format!("{}", err_code(&resp)),
    );
    {
        use bid_domain::Requirement;
        use std::collections::HashMap;
        // 注意：开当前 R14 工作区（ws_r14）——ctx 此刻在 ws_r14，不是旧 root
        let mut svc = bid_tools::service::BidService::open(&ws_r14).unwrap();
        let st = svc.store_mut();
        st.set_requirements(vec![Requirement {
            id: "REQ-0001".into(),
            category: "技术参数".into(),
            clause_no: None,
            anchors: vec![bid_domain::Anchor {
                file: "技术标.docx".into(),
                kind: "para".into(),
                locator: "第三章 3.2/REQ-0001".into(),
                excerpt: "投标人须提供 2000 路并发能力".into(),
                ..bid_domain::Anchor::default()
            }],
            params: HashMap::new(),
            source_file: "技术标.docx".into(),
        }])
        .unwrap();
        // 状态窗推进（外部写者；容错逐级——不后向、不重复，幂等对齐）
        let _ = st.advance_project_status(bid_domain::ProjectStatus::RequirementsExtracted);
        let _ = st.advance_project_status(bid_domain::ProjectStatus::MatrixReady);
        svc.checkpoint().unwrap(); // 持久化（seed/585 块同款——store_mut 变更须显式落盘）
    }
    let resp = call(&ctx, json!({"id":"t-bid-eva1","cmd":"bid.evidence_register","kind":"qualification","title":"R26 登记测试资质","source_file_id":id14,"subject_name":"selftest","valid_until":"2030-01-01"}));
    let bra1 = result(&resp);
    r.check(
        "bid.evidence_register(新登记)",
        resp["ok"] == json!(true)
            && bra1["register"]["ev_id"].is_string()
            && bra1["register"]["deduplicated"] == json!(false)
            && bra1["register"]["status"] == json!("ACTIVE"),
        format!("ev={} detail={}", bra1["register"]["ev_id"], resp.get("error").cloned().unwrap_or(json!(null))),
    );
    let resp = call(&ctx, json!({"id":"t-bid-eva2","cmd":"bid.evidence_register","kind":"qualification","title":"R26 登记测试资质","source_file_id":id14,"subject_name":"selftest","valid_until":"2030-01-01"}));
    let bra2 = result(&resp);
    r.check(
        "bid.evidence_register(幂等重放)",
        resp["ok"] == json!(true)
            && bra2["register"]["ev_id"] == bra1["register"]["ev_id"]
            && bra2["register"]["deduplicated"] == json!(true),
        format!("ev1={} ev2={}", bra1["register"]["ev_id"], bra2["register"]["ev_id"]),
    );
    let _ = std::fs::remove_dir_all(&ws_r14);

    // ---- #47 R15（平台区分⑧）：日期时区口径——严格公历（不存在的日历日
    //      拒在工具面单一真源）+ 截止日过去的警告（today 换本地日历日——
    //      旧 UTC 口径在东八区 0-8 点取昨天，刚过截止的警告漏报一天）
    let ws_r15 = scratch_dir();
    let resp = call(&ctx, json!({"id":"t-ws-r15","cmd":"workspace.open","path": ws_r15.to_string_lossy()}));
    r.check(
        "workspace.open(R15 工作区)",
        resp["ok"] == json!(true),
        format!("{resp}"),
    );
    // 不存在的日历日：壳形态检查（10 字符数字）通过、工具面严格公历拒
    let resp = call(&ctx, json!({"id":"t-bad-date","cmd":"bid.create_project","name":"坏日期","bid_deadline":"2026-02-30","mode":"明标"}));
    r.check(
        "bid.create_project(不存在的日历日拒)",
        resp["ok"] == json!(false) && err_code(&resp) == "bad_args",
        format!("err={}", err_code(&resp)),
    );
    // 已过截止日：创建即警告 BID_DEADLINE_PAST（本地日历日口径），不阻断
    let resp = call(&ctx, json!({"id":"t-past-dl","cmd":"bid.create_project","name":"过期项目R15","bid_deadline":"2020-01-01","mode":"明标"}));
    let cp15 = result(&resp);
    let warned = cp15["warnings"]
        .as_array()
        .map(|w| w.iter().any(|x| x.as_str().unwrap_or("").contains("BID_DEADLINE_PAST")))
        .unwrap_or(false);
    r.check(
        "bid.create_project(过期截止警告)",
        resp["ok"] == json!(true) && cp15["status"] == json!("DRAFT") && warned,
        format!("warns={:?}", cp15["warnings"]),
    );
    let _ = std::fs::remove_dir_all(&ws_r15);

    // ---- #47 R25（向导深水区）：建纲流全链——全新 DRAFT 工作区，导入 →
    //      抽取（bid.extract，确定性规则）→ 推荐（bid.length_profile，四档
    //      alternatives + 信号面）→ 建纲（bid.build_outline，practical 档）→
    //      bid.outline 章节树呈现。UI 断档收口的自测面锁定——此前这三步
    //      只能走 MCP 管线（树区空态明文「由 Agent 走」）。
    let ws_r25 = scratch_dir();
    std::fs::create_dir_all(ws_r25.join("files")).unwrap();
    std::fs::write(
        ws_r25.join("files").join("A-招标文件.docx"),
        include_bytes!("../../../tests/fixtures/wizard19-min.docx"),
    )
    .unwrap();
    let resp = call(&ctx, json!({"id":"t-ws-r25","cmd":"workspace.open","path": ws_r25.to_string_lossy()}));
    r.check(
        "workspace.open(R25 建纲流工作区)",
        resp["ok"] == json!(true),
        format!("{resp}"),
    );
    let resp = call(&ctx, json!({"id":"t-bid-cp25","cmd":"bid.create_project","name":"R25 建纲流","bid_deadline":"2026-12-31","mode":"明标"}));
    r.check(
        "bid.create_project(R25 起步)",
        resp["ok"] == json!(true),
        format!("{resp}"),
    );
    let resp = call(&ctx, json!({"id":"t-bid-im25","cmd":"bid.import_files","files":[{"upload_ref":"files/A-招标文件.docx","kind":"招标文件"}]}));
    let im25 = result(&resp);
    r.check(
        "bid.import_files(R25 入库)",
        resp["ok"] == json!(true) && im25["totals"]["files"] == json!(1),
        format!("totals={:?}", im25["totals"]["files"]),
    );
    // 抽取：确定性规则 → REQ 面 + 状态推进（零抽取是警告不是错误；夹具实测 >0）
    let resp = call(&ctx, json!({"id":"t-bid-ex25","cmd":"bid.extract"}));
    let ex25 = result(&resp);
    let ex_total = ex25["extract"]["counts"]["total"].as_u64().unwrap_or(0);
    r.check(
        "bid.extract(确定性抽取)",
        resp["ok"] == json!(true)
            && ex_total >= 1
            && ex25["extract"]["status"] == json!("REQUIREMENTS_EXTRACTED"),
        format!("total={ex_total}"),
    );
    // 状态对账：quick_stats.requirements 同源可见（树区空态卡的两相位判据）
    let resp = call(&ctx, json!({"id":"t-bid-st25","cmd":"bid.state"}));
    let st25 = result(&resp);
    r.check(
        "bid.state(抽取后对账)",
        resp["ok"] == json!(true)
            && st25["project"]["status"] == json!("REQUIREMENTS_EXTRACTED")
            && st25["quick_stats"]["requirements"].as_u64() == Some(ex_total),
        format!("reqs={:?}", st25["quick_stats"]["requirements"]),
    );
    // 推荐：四档 alternatives + 信号面（#287 呈现义务的壳面直通）
    let resp = call(&ctx, json!({"id":"t-bid-lp25","cmd":"bid.length_profile"}));
    let lp25 = result(&resp);
    let alts25 = lp25["recommendation"]["alternatives"].as_array().map(|a| a.len()).unwrap_or(0);
    r.check(
        "bid.length_profile(推荐+四档)",
        resp["ok"] == json!(true)
            && lp25["recommendation"]["recommended_profile"].is_string()
            && alts25 == 4
            && lp25["recommendation"]["signals"]["scoring_detail_count"].is_u64(),
        format!("alts={alts25}"),
    );
    // 建纲：practical 档 → 章节树 + 矩阵一体（prepare_outline_and_matrix）
    let resp = call(&ctx, json!({"id":"t-bid-bo25","cmd":"bid.build_outline","length_profile":"practical"}));
    let bo25 = result(&resp);
    r.check(
        "bid.build_outline(建纲+矩阵一体)",
        resp["ok"] == json!(true)
            && bo25["outline_build"]["counts"]["sections"].as_u64().unwrap_or(0) >= 1
            && bo25["outline_build"]["counts"]["matrix_rows"].as_u64().unwrap_or(0) >= 1
            && bo25["outline_build"]["status"] == json!("MATRIX_READY"),
        format!(
            "sections={:?} matrix={:?}",
            bo25["outline_build"]["counts"]["sections"],
            bo25["outline_build"]["counts"]["matrix_rows"]
        ),
    );
    // 大纲呈现：节点非空（UI 章节树数据源——建纲流卡的退场条件）
    let resp = call(&ctx, json!({"id":"t-bid-ol25","cmd":"bid.outline"}));
    let ol25 = result(&resp);
    let nodes25 = ol25["nodes"].as_array().map(|a| a.len()).unwrap_or(0);
    r.check(
        "bid.outline(章节树呈现)",
        resp["ok"] == json!(true) && nodes25 >= 1,
        format!("nodes={nodes25}"),
    );
    let _ = std::fs::remove_dir_all(&ws_r25);

    println!();
    println!(
        "== {} passed, {} failed, {} skipped ==",
        r.pass,
        r.fail,
        r.skip
    );
    let _ = std::fs::remove_dir_all(&root);
    if r.fail == 0 {
        0
    } else {
        1
    }
}
