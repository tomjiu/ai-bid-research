#!/usr/bin/env python3
"""run_real_llm_path.py —— #113 真实 Agent 标书起草验收的机器面（真实 LLM 通路）。

口径（issue #113 验收原文）：
  - 按 sdk/skill/bid-response-pipeline 的实际 MCP tools 调用（纯 MCP 面）
  - 真实模型起草：draft_response_section generator="real"（RealGenerator →
    OpenAI 兼容 HTTP → 本地桥 scripts/zai-llm-bridge.mjs → z-ai glm-4-plus；
    桥由本脚本托管生命周期）
  - 证据 = 仓内 corpus-A 合成 fixture（FILE_EXISTS 文件级锚 + 主体名标注合成）
  - 审核门 = #277 agent 声明过门（require_human_receipt=false 显式开，
    human_confirmed=false——不冒充人工批准；人工追认 = NOT_RUN）
  - 评分项显式映射 MCP 写面未提供 → waive_unmapped_scoring 豁免（如实登记）
  - ★漏标 2 块（章标题装饰）→ 零标记正则兜底 + 导出豁免（收官 R27 判读同款）
  - 断点续跑：OUT/driver-state.json 在场 → 跳过 P1-P4 直入未完成叶起草
    （沙箱限流窗口 ~5 分钟/轮——多轮跑齐 47 叶）
  - 优雅退出：起草面若因 429 耗尽重试失败 → 保存进度退出码 2（重跑续推），
    不留 traceback 假象

用法: python3 scripts/run_real_llm_path.py <ws_dir> <out_dir> [--api-base URL]
退出码: 0=全链完成  2=限流中断待续跑  1=其它错误
"""
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "bidcore/target/debug/bid-mcp-stdio")
MAIN = os.path.join(REPO, "real-corpus/telecom/parse-input/A-telecom-huaian-主文件.docx")
EV_DIR = os.path.join(REPO, "fixtures/corpus-A/files/evidence")
BRIDGE = os.path.join(REPO, "scripts/zai-llm-bridge.mjs")

EVIDENCE = [
    ("qualification", "电子与智能化工程专业承包二级资质证书",
     "EV-02-电子与智能化工程专业承包二级资质证书.pdf"),
    ("qualification", "营业执照", "EV-01-营业执照.pdf"),
    ("performance", "类似业绩合同-智慧园区弱电工程",
     "EV-03-类似业绩合同-智慧园区弱电工程.pdf"),
]
PROFILE = {
    "duration_days": 37, "validity_days": 90,
    "bid_amount": 4_800_000.0, "project_no": "HA-2026-BID-001",
    "legal_rep_gender": "男",
}
TARGET_TOTAL_CHARS = 48_000
ACTOR = "agent-zai"
DRAFT_GAP_S = 15  # 限速：叶间间隔（429 窗口 ~28 次/5min 的安全节流）

WS, OUT = sys.argv[1], sys.argv[2]
API_BASE = "http://127.0.0.1:8787/v1"
if "--api-base" in sys.argv:
    API_BASE = sys.argv[sys.argv.index("--api-base") + 1]
API_PORT = API_BASE.rsplit(":", 1)[1].split("/")[0] if ":" in API_BASE else "8787"

os.makedirs(WS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
mang = os.path.join(WS, ".mang")
os.makedirs(mang, exist_ok=True)
with open(os.path.join(mang, "config.json"), "w") as f:
    json.dump({"require_human_receipt": False}, f)
with open(os.path.join(mang, "llm.json"), "w") as f:
    json.dump({
        "api_base": API_BASE, "api_key": "bridge-local", "model": "glm-4-plus",
        "timeout_secs": 230, "temperature": 0.3, "max_tokens_cap": 8192,
    }, f)

env = dict(os.environ, BID_WS=WS, BID_FS_ROOT=REPO)
calls = []
STATE_FILE = os.path.join(OUT, "driver-state.json")


def call(tool, args, timeout=600):
    line = json.dumps({"tool": tool, "args": args}, ensure_ascii=False)
    t0 = time.time()
    r = subprocess.run([BIN], input=line + "\n", capture_output=True, text=True,
                       env=env, timeout=timeout)
    ms = int((time.time() - t0) * 1000)
    out = r.stdout.strip().splitlines()
    reply = json.loads(out[-1]) if out else {"ok": False, "error": {"what": "no output"}}
    entry = {"tool": tool, "ok": bool(reply.get("ok")), "ms": ms}
    if not reply.get("ok"):
        entry["error"] = reply.get("error")
    calls.append(entry)
    return reply


def must(tool, args, ctx, timeout=600):
    r = call(tool, args, timeout)
    assert r.get("ok"), f"[{ctx}] {tool} 失败: {json.dumps(r.get('error', {}), ensure_ascii=False)[:500]}"
    return r.get("data", {})


def approval_key():
    with open(os.path.join(WS, ".mang/approval.key"), "rb") as f:
        return f.read()


def agent_receipt(scope, digest, key):
    ts = int(time.time())
    msg = f"v2|{ACTOR}|agent|{scope}|{ts}|{digest}"
    mac = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
    return f"v2.{ACTOR}.agent.{scope}.{ts}.{digest}.{mac}"


def pass_gate(gate, reason):
    key = approval_key()
    d = must("get_bid_project_state", {"project_id": PID}, "digest")
    dg = d["content_binding"]["sections_digest"]
    rc = agent_receipt(f"review_gate:{gate}:agent", dg, key)
    return must("record_review_gate", {
        "project_id": PID, "gate": gate, "decision": "APPROVED",
        "receipt": rc, "reason": reason, "project_version": "latest",
    }, f"gate:{gate}")


def matrix_rows():
    d = must("get_compliance_matrix", {"project_id": PID, "limit": 200}, "matrix")
    rows = list(d["rows"])
    cur = d.get("next_cursor")
    while cur:
        d = must("get_compliance_matrix", {"project_id": PID, "limit": 200, "cursor": cur}, "matrix")
        rows.extend(d["rows"])
        cur = d.get("next_cursor")
    return rows


def save_state(extra=None):
    st = {
        "project_id": PID, "actor": ACTOR,
        "main_file": os.path.basename(MAIN),
        "main_sha256": hashlib.sha256(open(MAIN, "rb").read()).hexdigest(),
        "star_missing": {"count": star_missing_n, "detail": star_missing_detail,
                         "handling": "零标记正则兜底 + 导出豁免（章标题装饰，设计内）"},
        "evidence": [{"ev_id": e, "kind": k, "title": t, "synthetic": True,
                      "provenance": "fixtures/corpus-A/files/evidence（仓内合成 fixture）"}
                     for e, k, t in ev_ids],
        "req_total": req_total,
    }
    if extra:
        st.update(extra)
    json.dump(st, open(STATE_FILE, "w"), ensure_ascii=False, indent=1)


# ---- 桥生命周期 ----
bridge_log = open(os.path.join(OUT, "bridge.log"), "a")
bridge = subprocess.Popen(["node", BRIDGE, API_PORT], stdout=bridge_log,
                          stderr=bridge_log, start_new_session=True)
time.sleep(1.2)
probe = json.loads(urllib.request.urlopen(urllib.request.Request(
    f"http://127.0.0.1:{API_PORT}/v1/chat/completions",
    data=json.dumps({"model": "glm-4-plus",
                     "messages": [{"role": "user", "content": "回复两个字：就绪"}]}).encode(),
    headers={"Content-Type": "application/json"}), timeout=120).read())
print(f"[bridge] 自检: {probe['choices'][0]['message']['content']}")

t_all = time.time()
exit_code = 0
PID = None
star_missing_n, star_missing_detail = 0, []
req_total, ev_ids, draft_stats = 0, [], []
leaves = []
resume = os.path.exists(STATE_FILE)

try:
    if resume:
        sv = json.load(open(STATE_FILE))
        PID = sv["project_id"]
        star_missing_n = sv.get("star_missing", {}).get("count", 0)
        star_missing_detail = sv.get("star_missing", {}).get("detail", [])
        req_total = sv.get("req_total", 0)
        ev_ids = [(e["ev_id"], e["kind"], e["title"]) for e in sv.get("evidence", [])]
        draft_stats = sv.get("draft", {}).get("stats", [])
        print(f"[resume] 续跑 {PID}（P1-P4 已完成，已起草 {len(draft_stats)} 叶）")
    else:
        # ---- P1-P2 ----
        d = must("create_bid_project", {
            "name": "验收#113-真实LLM起草", "bid_deadline": "2026-12-31",
            "mode": "明标", "external_key": "realagent-113",
        }, "create")
        PID = d["project_id"]
        print(f"[P1] project {PID}")
        files = [{"upload_ref": MAIN, "filename": os.path.basename(MAIN), "kind": "招标文件"}]
        for _, _, fn in EVIDENCE:
            files.append({"upload_ref": os.path.join(EV_DIR, fn), "filename": fn, "kind": "附件"})
        d = must("import_tender_files", {"project_id": PID, "files": files}, "import")
        file_ids = {p["filename"]: p["file_id"] for p in d.get("per_file", [])}
        print(f"[P1] 导入 {len(file_ids)} 件")
        must("extract_requirements", {"project_id": PID}, "extract")
        print("[P2] 抽取完成（计数在建纲回执口径）")

        # ★门：只报不标（#244 覆盖闭环门——补标即须全块三态判定）
        main_fid = file_ids[os.path.basename(MAIN)]
        d = must("get_star_coverage", {"project_id": PID, "file_id": main_fid}, "star")
        star_missing_n = d.get("star_missing", 0)
        star_missing_detail = [
            {"block_idx": m.get("block_idx"), "page": m.get("page"),
             "text": (m.get("text") or "")[:60]} for m in d.get("missing", [])]
        print(f"[P2'] ★漏标 {star_missing_n} 块（零标记保正则兜底）："
              f"{[s['text'][:20] for s in star_missing_detail]}")

        # ---- P3 建纲 ----
        d = must("build_outline", {
            "project_id": PID, "target_total_chars": TARGET_TOTAL_CHARS,
            "max_reqs_per_leaf": 8, "project_version": "latest",
        }, "outline")
        print(f"[P3] 大纲 counts: {d['counts']}")
        req_total = d["counts"]["requirements"]

        # ---- P4 证据登记 + 批量绑定 ----
        for kind, title, fn in EVIDENCE:
            d = must("register_evidence", {
                "project_id": PID, "kind": kind, "title": title,
                "source_file_id": file_ids[fn],
                "subject_name": "验收测试通信工程有限公司（合成素材——正式投标须替换为真实企业材料）",
                "scope": "通信工程建设", "project_version": "latest",
            }, f"ev:{title}")
            ev_ids.append((d["ev_id"], kind, title))
            print(f"[P4] {d['ev_id']} tier={d.get('verification_tier')}「{title}」")
        rows = matrix_rows()
        n_blocking = sum(1 for r in rows if r.get("blocking"))
        print(f"[P4] 矩阵 {len(rows)} 行，阻断 {n_blocking}")
        quals = [e for e, k, _ in ev_ids if k == "qualification"]
        perfs = [e for e, k, _ in ev_ids if k == "performance"]
        groups = {"qual": [], "perf": [], "other": []}
        for r in rows:
            if not r.get("blocking"):
                continue
            cat = (r["requirement"].get("category") or "")
            key = "qual" if cat == "资格条件" else ("perf" if cat in ("商务要求", "技术参数") else "other")
            groups[key].append(r["requirement"]["id"])
        for ev, key in [(quals[0] if quals else ev_ids[0][0], "qual"),
                        (perfs[0] if perfs else ev_ids[0][0], "perf"),
                        (ev_ids[0][0], "other")]:
            if groups[key]:
                must("bind_evidence", {
                    "project_id": PID, "ev_id": ev, "requirement_ids": groups[key],
                    "bid_open_date": "2026-12-31", "project_version": "latest",
                }, f"bind:{key}")
        n_after = sum(1 for r in matrix_rows() if r.get("blocking"))
        print(f"[P4] 绑定完成，阻断 {n_blocking}→{n_after}")

        # ---- 审核门 + 补遗门（agent 声明——#277 留痕）----
        g1 = pass_gate("matrix_approval", "#113 验收跑批：矩阵面核对后放行（agent 声明——留痕待人工追认）")
        g2 = pass_gate("outline_approval", "#113 验收跑批：大纲 48k 档同收官 mock 口径（agent 声明——留痕待人工追认）")
        key = approval_key()
        d = must("get_bid_project_state", {"project_id": PID}, "digest")
        dg = d["content_binding"]["sections_digest"]
        rc = agent_receipt("no_addendum_confirmed:agent", dg, key)
        d = must("record_addendum_waiver", {
            "project_id": PID, "confirm_no_addendum": True,
            "reason": "#113 验收跑批：语料仅主件+附件，无补遗/澄清件（agent 声明——留痕待人工追认；如获澄清件须重抽增量）",
            "receipt": rc, "project_version": "latest",
        }, "addendum")
        print(f"[P4'] 门: matrix={g1['receipt']['method']} outline={g2['receipt']['method']} "
              f"addendum={d['confirmed_no_addendum'].get('method')} human_confirmed=False")
        save_state()

    # ---- 叶清单（resume 与首跑同口径：PENDING 者待起草）----
    q = must("check_bid_quality", {"project_id": PID, "project_version": "latest"}, "leaves")
    leaves = [s["section_id"] for s in q["sections"]]
    done = {s["section_id"] for s in q["sections"] if s.get("status") not in (None, "PENDING")}
    pending = [s for s in leaves if s not in done]
    print(f"[P3] 起草叶 {len(leaves)}（已完成 {len(done)}，待起草 {len(pending)}）")

    # ---- P5b 逐叶真实起草（限速 + 429 优雅退出）----
    t_draft = time.time()
    for i, sid in enumerate(pending, 1):
        r = call("draft_response_section", {
            "project_id": PID, "section_id": sid,
            "instructions": "按招标文件逐项响应，突出同类业绩与实施方案；引用只准用列出的 REQ/EV 编号",
            "generator": "real", "project_version": "latest",
        }, timeout=620)
        if not r.get("ok"):
            err = json.dumps(r.get("error", {}), ensure_ascii=False)
            if "429" in err or "Too many requests" in err or "LLM" in err:
                print(f"[P5b] {sid} 生成失败（限流/LLM 面）——保存进度优雅退出（重跑续推）: {err[:200]}")
                exit_code = 2
                break
            raise AssertionError(f"[draft:{sid}] {err[:500]}")
        d = r["data"]
        st = d.get("stats", {})
        draft_stats.append({"sid": sid, "words": st.get("words"),
                            "citations": st.get("citations")})
        print(f"[P5b] ({len(done) + i}/{len(leaves)}) {sid} words={st.get('words')} "
              f"cites={st.get('citations')} ({int(time.time() - t_draft)}s)", flush=True)
        save_state({"draft": {"stats": draft_stats}})
        if i < len(pending):
            time.sleep(DRAFT_GAP_S)

    if exit_code == 2:
        sys.exit(2)

    total_words = sum(s["words"] or 0 for s in draft_stats)
    print(f"[P5b] 起草面收口: {len(done) + len([s for s in draft_stats if s['sid'] not in done])}"
          f"/{len(leaves)} 叶 / 累计 {total_words} 字")

    # ---- P6 校验 ----
    d = must("validate_bid_document", {"project_id": PID, "scope": "all",
                                       "project_version": "latest"}, "validate")
    print(f"[P6] 校验: ok={d.get('ok')} counts={d.get('counts')}")

    # ---- P7' 导出前门 ----
    pass_gate("pre_export_confirm", "#113 验收跑批：定稿内容过门（agent 声明——留痕待人工追认）")

    # ---- P8 导出（output_path 须工作区相对路径）----
    rel_out = "out/投标文件-realagent-113.docx"
    export_args = {
        "project_id": PID, "format": "docx", "output_path": rel_out,
        "profile": PROFILE, "max_overrun_pct": 10000,
        "waive_unmapped_scoring": "#113 验收如实登记：评分项显式映射的 MCP 写面未提供"
                                  "（契约门1h 注记『后续 issue』）——按最小改动豁免，"
                                  "映射面缺口在验收报告登记",
        "project_version": "latest",
    }
    if star_missing_n:
        export_args["waive_star_missing"] = (
            f"#113 验收如实登记：★漏标 {star_missing_n} 块为章节标题装饰"
            f"（{'；'.join(s['text'] for s in star_missing_detail)}）——抽取器不产标题"
            " REQ 属设计内（收官真测 R27 判读同款）；零标记正则兜底口径下未补标")
    d = must("export_bid_document", export_args, "export")
    # 成品复制到 OUT（工作区内产物 → 验收目录）
    import shutil
    ws_out = os.path.join(WS, rel_out)
    out_path = os.path.join(OUT, "投标文件-realagent-113.docx")
    if os.path.exists(ws_out):
        shutil.copyfile(ws_out, out_path)
    export_meta = {
        "size": d["artifact"]["size"], "sha256": d["artifact"]["sha256"],
        "chapters_written": d["chapters_written"], "total_chars": d.get("total_chars"),
        "generator_summary": d.get("generator_summary"),
        "evidence_validity": d.get("evidence_validity"),
        "warnings_count": len(d.get("warnings", [])),
    }
    print(f"[P8] 导出: {export_meta['size']}B / {export_meta['chapters_written']} 章 "
          f"sha256={export_meta['sha256'][:16]}…")
    print(f"[P8] generator_summary: {export_meta['generator_summary']}")

    # ---- 质量面 + 台账 ----
    d = must("check_bid_quality", {"project_id": PID, "project_version": "latest"}, "quality")
    llm_usage = None
    up = os.path.join(WS, ".mang/llm-usage.json")
    if os.path.exists(up):
        llm_usage = json.load(open(up))
    result = {
        "project_id": PID, "actor": ACTOR,
        "main_file": os.path.basename(MAIN),
        "star_missing": {"count": star_missing_n, "detail": star_missing_detail},
        "evidence": [{"ev_id": e, "kind": k, "title": t, "synthetic": True} for e, k, t in ev_ids],
        "req_total": req_total, "leaves": len(leaves),
        "draft": {"leaves_done": len(done) + len(draft_stats), "total_words": total_words,
                  "stats": draft_stats},
        "validate": d.get("summary", {}),
        "export": export_meta,
        "llm_usage": llm_usage,
        "elapsed_s": int(time.time() - t_all),
    }
    result["main_sha256"] = hashlib.sha256(open(MAIN, "rb").read()).hexdigest()
    json.dump(result, open(os.path.join(OUT, "realagent-metrics.json"), "w"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "tool-call-log.json"), "w") as f:
        json.dump(calls, f, ensure_ascii=False, indent=1)
    print(f"[done] {OUT} （{result['elapsed_s']}s, {len(calls)} 次工具调用）")
finally:
    bridge.terminate()
    try:
        bridge.wait(timeout=5)
    except subprocess.TimeoutExpired:
        bridge.kill()
    bridge_log.close()
sys.exit(exit_code)
