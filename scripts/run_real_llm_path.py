#!/usr/bin/env python3
"""run_real_llm_path.py —— #113 真实 Agent 标书起草验收的机器面（真实 LLM 通路）。

口径（issue #113 验收原文 + Lead 闭门五条件）：
  - 按 sdk/skill/bid-response-pipeline 的实际 MCP tools 调用（纯 MCP 面）
  - 真实模型起草：draft_response_section generator="real"（RealGenerator →
    OpenAI 兼容 HTTP → 本地桥 scripts/zai-llm-bridge.mjs → z-ai glm-4-plus；
    桥由本脚本托管生命周期）
  - 证据 = 仓内 corpus-A 合成 fixture（FILE_EXISTS 文件级锚 + 主体名标注合成）
  - 审核门 = #277 agent 声明过门（require_human_receipt=false 显式开，
    human_confirmed=false——不冒充人工批准；人工追认 = NOT_RUN）
  - 评分项映射 = #153 map_scoring_item MCP 正门逐项映射（bigram 重合度选叶
    + 决策留痕——multifile_matrix 同款口径；#178 分值面解锁后 huaian 真件
    携 14 条带分值评分项）——门 1h 零豁免目标；映射后仍有 unmapped 才豁免
  - P9 = check_scoring_coverage 细则点命中（闭门条件 2：命中 > 0）
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
import re
import subprocess
import sys
import time
import urllib.request

# 同目录状态持久层（#113 审计修复批：断点续跑不洗 decisions/repair 历史）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realagent_state
# #113 审计修复批二：口径注入指令 / 证据明细聚合 / REPORT 机器底稿
import realagent_evidence

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
    "bid_amount": 4_800_000.0,
    # 批六（r5 通读审读 A4 根治）：project_no 必须传主文件正源编号——
    # 曾写内部虚构编号 HA-2026-BID-001（主文件 0 命中），经 profile 进入
    # LLM 上下文后照抄进投标函「项目编号为 HA-2026-BID-001」（r5 段643
    # 实锤泄漏）。正源：A-telecom-huaian-主文件.docx ×3 命中。
    "project_no": "JSCGXM202610210082001001",
    "legal_rep_gender": "男",
    # 批五（审计 A5 根治）：格式件（投标函等）抬头取 profile.project_name——
    # 引擎 export.rs 在缺位时 fallback 内部项目名「验收#113-真实LLM起草」
    # 并打警告（r3/r4 成品实锤泄漏）。传招标文件正名（主文件封面）。
    "project_name": "中国电信股份有限公司淮安分公司2026年淮安本地视频能力平台建设采购项目",
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
    # #113 审计修复批：读-改-写合并（旧实现全量重建——断点续跑 9 轮把
    # scoring_mapping.decisions / repair 历史洗掉，REPORT.md 与 driver-state
    # 实际内容矛盾即此根因）。base = 每轮恒新鲜面；extra 键覆盖、其余保留；
    # scoring_mapping/repair 走累积合并（幂等判别键去重）。
    base = {
        "project_id": PID, "actor": ACTOR,
        "main_file": os.path.basename(MAIN),
        "main_sha256": hashlib.sha256(open(MAIN, "rb").read()).hexdigest(),
        "star_missing": {"count": star_missing_n, "detail": star_missing_detail,
                         "handling": "零标记正则兜底 + 导出豁免（章标题装饰，设计内）"},
        "evidence": [{"ev_id": e, "kind": k, "title": t, "synthetic": True,
                      "provenance": "fixtures/corpus-A/files/evidence（仓内合成 fixture）"}
                     for e, k, t in ev_ids],
        "req_total": req_total,
        # draft 恒入 state（resume 后任何保存点不丢已起草进度——P4.6 等中段
        # 保存面曾在 resume 轮把 draft_stats 洗掉的隐患收口；draft_stats 在
        # 进程内自维护全量，extra 直盖即正确）
        "draft": {"stats": draft_stats},
        # #113 审计修复批二：累计口径随每轮保存落盘（resume 轮从 state 恢复）
        "elapsed_total_s": elapsed0 + int(time.time() - t_all),
        "resume_rounds": resume_rounds,
    }
    return realagent_state.save_state(STATE_FILE, base, extra)


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
# #113 审计修复批二：elapsed 累计口径——封存包 elapsed_s=2 实为末轮进程秒数
# （resume 洗史面），跨轮累计 + resume_rounds 落 metrics/state 如实呈现
elapsed0 = 0
resume_rounds = 0
exit_code = 0
PID = None
star_missing_n, star_missing_detail = 0, []
req_total, ev_ids, draft_stats = 0, [], []
repair_log = []  # #113 审计修复批：模块级初始化——resume 轮从 state 恢复（跨轮不丢）
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
        repair_log = sv.get("repair", [])  # 跨轮恢复：旧实现在轮次边界洗掉修复历史
        elapsed0 = int(sv.get("elapsed_total_s", 0))  # 前轮累计耗时（累计口径）
        resume_rounds = int(sv.get("resume_rounds", 0)) + 1  # 本次 = 第 N 轮续跑
        # 批九 G2（r6 实弹终验后实锚）：EXIT=0 全链完成后项目处 EXPORTED
        # 终态——状态机（#243 家族）不放行 draft_response_section，重跑
        # 会在 P6.6 撞 E_STATE 抛 traceback（EXIT=1 崩溃假象，驱动器 UX
        # 缺陷非引擎缺陷）。已完成项目重跑 = 幂等收口：如实报告 + 退出 0。
        _st = call("get_bid_project_state", {"project_id": PID})
        _status = (_st.get("data") or {}).get("status") or ""
        if _status == "EXPORTED":
            print(f"[resume] {PID} 已处 EXPORTED 终态——全链此前已完成（EXIT=0）；"
                  f"状态机不放行再起草（#243 家族），本次重跑幂等收口退出。")
            sys.exit(0)
        print(f"[resume] 续跑 {PID}（P1-P4 已完成，已起草 {len(draft_stats)} 叶，"
              f"修复历史 {len(repair_log)} 节次，累计 {elapsed0}s/{resume_rounds} 轮）")
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
        # 批十一根因修（r7 实锚 EV-0064 营业执照零援引）：绑定循环旧面只
        # 绑 quals[0]/perfs[0]——第二个 qualification 件注册后从未绑定任何
        # REQ 组；不绑定即不进任何节的 per-section 素材面（draft.rs
        # bound_evidence_ids），且起草器剔除「不在已知集」的引用——LLM 写了
        # [EV-0064] 也会被剥掉。全量绑定：每个 qualification/performance
        # 证据各绑其组（绑定是引用存活的前置件，不只是台账登记）。
        bind_pairs = ([(ev, "qual") for ev in quals]
                      + [(ev, "perf") for ev in perfs]
                      + [(ev_ids[0][0], "other")])
        for ev, key in bind_pairs:
            if groups[key]:
                must("bind_evidence", {
                    "project_id": PID, "ev_id": ev, "requirement_ids": groups[key],
                    "bid_open_date": "2026-12-31", "project_version": "latest",
                }, f"bind:{key}:{ev}")
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
    leaf_titles = {s["section_id"]: s.get("title") or "" for s in q["sections"]}
    done = {s["section_id"] for s in q["sections"] if s.get("status") not in (None, "PENDING")}
    pending = [s for s in leaves if s not in done]
    print(f"[P3] 起草叶 {len(leaves)}（已完成 {len(done)}，待起草 {len(pending)}）")

    # ---- P4.6 评分项映射（#153 正门——闭门条件：门 1h 零豁免）----
    # 多件矩阵同款口径：check_scoring_coverage 拿未映射评分面（工具层已滤
    # 否决项 hard gate）→ bigram 重合度选叶 + 决策留痕；幂等键重提更新
    #（resume 轮重跑安全）。
    def bigrams(s):
        cs = [c for c in s if not c.isspace()]
        return {"".join(p) for p in zip(cs, cs[1:])}

    cov0 = must("check_scoring_coverage", {"project_id": PID}, "cov0")
    unmapped = [c for c in cov0["criteria"] if not c["mapped_sections"]]
    mapping_log = []
    for c in unmapped:
        excerpt = (c["criteria_excerpt"] or "")[:60]
        ba = bigrams(c["criteria_excerpt"] or "")
        best_sid, best_score = None, -1
        for sid in leaves:
            sc = len(ba & bigrams(leaf_titles[sid]))
            if sc > best_score:
                best_sid, best_score = sid, sc
        method = f"bigram-overlap:{best_score}" if best_score > 0 else "fallback-last-leaf"
        if best_score <= 0:
            best_sid = leaves[-1]
        must("map_scoring_item", {
            "project_id": PID, "req_id": c["criterion_id"], "section_id": best_sid,
            "weight_share": 1.0,
            "anchor": {
                "excerpt": f"#113 真实验收映射（{method}）：{excerpt}",
                "locator": "run_real_llm_path P4.6——评分项→章节映射",
            },
        }, f"map:{c['criterion_id']}")
        mapping_log.append({"req_id": c["criterion_id"], "section_id": best_sid,
                            "method": method})
    cov1 = must("check_scoring_coverage", {"project_id": PID}, "cov1")
    print(f"[P4.6] 评分映射: {len(unmapped)} 未映射 → 逐项映射（bigram {sum(1 for m in mapping_log if m['method'].startswith('bigram-overlap:') and not m['method'].endswith(':0'))}）"
          f"；映射后 criteria_unmapped={cov1['summary']['criteria_unmapped']}")
    # #113 审计修复批：仅当本轮有新映射才保存（resume 轮已映射完时重存会把
    # decisions=[] 覆盖首轮 36 项决策——审计缺口 1 根因）；累积合并兜底。
    if mapping_log or not resume:
        save_state({"scoring_mapping": {"unmapped_before": len(unmapped),
                                        "unmapped_after": cov1["summary"]["criteria_unmapped"],
                                        "decisions": mapping_log}})

    # ---- P5b 逐叶真实起草（限速 + 429 优雅退出）----
    t_draft = time.time()
    # #113 审计修复批二：canonical 口径注入首稿（修复方向②——三处大写幻觉
    # 与段55 抄限价都是「无源数字自由发挥」产物；预防优于检出-修复）
    INITIAL_INSTR = realagent_evidence.initial_instructions()
    # #113 审计批三：证据引用指令（v2 实锚 EV-0064 营业执照 0 次引用）
    # + 每叶评分细则点注入（v2 实锚细则覆盖 0/39——首稿从未见过 39 个
    # 评分点原文，正文无从逐点命中；逐点响应是评标实务正路）
    EV_HINT = realagent_evidence.evidence_citation_hint(ev_ids)
    POINTS_MAP = realagent_evidence.leaf_points_map(cov1)
    n_pts = sum(len(v) for v in POINTS_MAP.values())
    print(f"[P5b] 初始指令含 canonical 口径 + 证据引用纪律 + 评分点注入"
          f"（{len(POINTS_MAP)} 叶 / {n_pts} 点）")
    for i, sid in enumerate(pending, 1):
        instr = INITIAL_INSTR + EV_HINT
        leaf_pts = POINTS_MAP.get(sid)
        if leaf_pts:
            instr += realagent_evidence.scoring_points_hint(leaf_pts)
        r = call("draft_response_section", {
            "project_id": PID, "section_id": sid,
            "instructions": instr,
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

    # ---- P6.6 细则覆盖修复轮（#113 审计批三：P9 0/39 根治面 + 批七 D3 防回退）----
    # v2 实锚：字面细则命中 0/39、条件 2 机器面回退为零。与 P6.5 同款
    # 定向重起草——批七（#113 全链审计 D3）修复注入面：r6b 实锚 SEC-0028
    # 修复轮覆盖 7→8→31 回退——重起草指令只注入未命中点，模型重写把已
    # 命中点丢了。现按叶聚合**全量点**双注入：未命中点逐点补齐 + 已命中
    # 点关键术语保留（只增不删）；复测直至覆盖或轮次耗尽（如实登记，
    # 不豁免）。留痕并入 repair（kind=scoring；round 100 起避开 P6.5
    # 1-15 的判别键空间）；覆盖回退每轮打印告警（如实登记）。
    # ★执行位置契约（v3 实弹 E_STATE 教训，tests/test_p66_scoring_repair_order.py
    # 回归锁）：本修复轮必须在**首个全稿 validate_bid_document 之前**执行。
    # 状态机事实链：#243——全稿校验**通过**即推进 Drafting→Validating（失败
    # 留原态可修订）；bid-domain allowed_tools() 的 Validating 白名单**不含**
    # draft_response_section（整节重起草在复核态被合法拒绝——v3 首跑
    # SEC-0028 E_STATE 崩溃实锚）。故 P6.6 前置于 P6/P6.5；P6.5 blocker
    # 重起草随后仍在 Drafting 态内合法（带 blocker 的校验不推进状态），
    # 且其修复指令携带本节评分点防覆盖回退（见 repair 调用处）。
    cov_mid = must("check_scoring_coverage", {"project_id": PID}, "cov-mid")
    sc_round = 0
    # 批九 G1（r6 实弹终验实锚）：P6.6「逐点织入正文」对短碎片点不收敛
    # ——r6b 五轮 49/52，残余三点（合同内容页/合同金额页/所提供人员2026
    # 年3月份）每轮注入仍被 LLM 重写丢词，且整节重写两次覆盖回退
    # （49→21 / 49→46）。叶级 stuck 计数（含跨 invocation 的 repair 留痕
    # kind=scoring 预载）：≥2 轮未收敛即切「逐点响应对照表」兜底——
    # 表第一列逐字复述点原文（一字不差），字面命中口径下结构性保证覆盖。
    sid_stuck = {}
    for e in repair_log:
        if e.get("kind") == "scoring":
            sid_stuck[e["sid"]] = sid_stuck.get(e["sid"], 0) + 1
    while (cov_mid["summary"].get("points_covered", 0)
           < cov_mid["summary"].get("points_total", 0)):
        sec_pts = realagent_evidence.section_points_for_repair(cov_mid)
        sid_pts = {s: v["missing"] for s, v in sec_pts.items() if v["missing"]}
        if not sid_pts:
            print("[P6.6] 未命中点无映射叶可定向——如实登记退出（不豁免）")
            break
        sc_round += 1
        if sc_round > 5:
            print("[P6.6] 细则覆盖修复轮耗尽——剩余缺口如实登记（不豁免）")
            break
        print(f"[P6.6] 细则覆盖修复轮 {sc_round}: "
              f"{cov_mid['summary']['points_total'] - cov_mid['summary']['points_covered']} 点未命中 → "
              f"{len(sid_pts)} 叶定向重起草（全量点双注入防回退）")
        # 批#221：P6.6 整节重写同样是 REQ/EV 引用回退入口——节级已援引
        # EV 洗掉**不**触发 P6.8 重收口（其判据是文档级零援引，别节仍
        # 援引即不复活本节）。每轮取活体 check_bid_quality 面
        # （covered_reqs/cited_evs）→ 指令尾统一走
        # p66_repair_instruction_tail（REQ/EV 保留纪律随行；REQ 补齐仍归
        # P6.7 轮次，不前置抢跑）。
        q_p66 = must("check_bid_quality", {"project_id": PID, "project_version": "latest"},
                     f"q-p66:{sc_round}")
        sec_q_p66 = {s.get("section_id"): s for s in (q_p66.get("sections") or [])}
        for sid, pts in sorted(sid_pts.items()):
            hit_pts = sec_pts[sid]["hit"]
            stuck = sid_stuck.get(sid, 0) + 1
            sid_stuck[sid] = stuck
            s66 = sec_q_p66.get(sid) or {}
            # 批九 G1：stuck ≥ 2 切对照表兜底（点原文列逐字复述，含全量
            # 点：表格即逐点响应载体；retained 双注入不豁免——尾函数统一）。
            instr = (INITIAL_INSTR + EV_HINT
                     + realagent_evidence.p66_repair_instruction_tail(
                         pts, hit_pts,
                         s66.get("covered_reqs") or [],
                         s66.get("cited_evs") or [], stuck))
            why = (f"P6.6 细则覆盖: {len(pts)} 点未命中——" + (
                f"对照表兜底重起草（历史 {stuck - 1} 轮织入未收敛，表列逐字复述）"
                if stuck >= 2 else
                f"全量点双注入重起草（已命中 {len(hit_pts)} 点保留防回退）"))
            r = call("draft_response_section", {
                "project_id": PID, "section_id": sid,
                "instructions": instr,
                "generator": "real", "project_version": "latest",
            }, timeout=620)
            if not r.get("ok"):
                err = json.dumps(r.get("error", {}), ensure_ascii=False)
                if "429" in err or "Too many requests" in err or "LLM" in err:
                    print(f"[P6.6] {sid} 修复生成失败（限流）——保存进度优雅退出: {err[:160]}")
                    exit_code = 2
                    break
                raise AssertionError(f"[scoring-repair:{sid}] {err[:400]}")
            st = r["data"].get("stats", {})
            draft_stats = [x for x in draft_stats if x["sid"] != sid]
            draft_stats.append({"sid": sid, "words": st.get("words"),
                                "citations": st.get("citations")})
            repair_log.append({"round": 100 + sc_round, "sid": sid,
                              "kind": "scoring",
                              "why": [why],
                              "floor": 600, "ban": False,
                              "words": st.get("words"), "citations": st.get("citations")})
            print(f"[P6.6] {sid} 重起草 words={st.get('words')} "
                  f"cites={st.get('citations')}"
                  + ("（对照表兜底：全量 " + str(len(pts) + len(hit_pts))
                     + " 点入表逐字复述）" if stuck >= 2 else
                     f"（注入 {len(pts)} 缺点 + {len(hit_pts)} 已命中保留）"),
                  flush=True)
            save_state({"draft": {"stats": draft_stats}, "repair": repair_log})
            time.sleep(DRAFT_GAP_S)
        if exit_code == 2:
            sys.exit(2)
        prev_covered = cov_mid["summary"].get("points_covered", 0)
        cov_mid = must("check_scoring_coverage", {"project_id": PID}, f"cov-mid:{sc_round}")
        now_covered = cov_mid["summary"].get("points_covered", 0)
        if now_covered < prev_covered:
            print(f"[P6.6] ⚠覆盖回退告警: {prev_covered}→{now_covered}"
                  f"（重起草丢已命中点——如实登记，下轮全量点双注入再收敛）")
    print(f"[P6.6] 细则覆盖收口: covered={cov_mid['summary']['points_covered']}/"
          f"{cov_mid['summary']['points_total']}")

    # ---- P6.7 uncovered-REQ 引用补齐修复轮（批十——批九登记候补面落地）----
    # r7 实锚：P9.6 未覆盖 REQ 10 条（SEC-0035×8 / SEC-0040×1 / SEC-0062×1
    # ——第一章「其他」类样板条款：1.8.1 不得存在情形 / 1.9 货物原产地 /
    # 1.10 投标费用 / 1.11 保密 / 2.2 踏勘现场等）。根因非 prompt 缺口
    # （llm.rs 系统规则 2/3 与素材面已含 REQ 清单及引用规则）——LLM 对
    # 低显著度样板条款丢 [REQ-xxxx] 标注，而驱动器有 P6.5（blocker）/
    # P6.6（评分点）两条修复轮唯独 REQ 引用无修复面。同款定向重起草：
    # check_bid_quality 活体取 sections[].uncovered_reqs（补齐面）/
    # covered_reqs（保留面）→ 未覆盖 REQ 逐条补引用 + 已覆盖 REQ 保留
    # 纪律双注入（整节重起草换全文，不点名保留即修复 A 洗掉 B——批七
    # D3 对偶）。≥2 轮未收敛切逐 REQ 显式响应段兜底（批九 G1 对偶：
    # 段落首编号逐字写入是字面引用口径下的结构性保证）。
    # ★执行位置契约（E_STATE 纪律，tests/test_p67_req_repair_order.py
    # 回归锁）：本修复轮必须在**首个全稿 validate_bid_document 之前**
    # 执行（P6.6 之后、P6 校验之前——全在 Drafting 态内）。
    q_mid = must("check_bid_quality", {"project_id": PID, "project_version": "latest"}, "q-mid")
    rq_stuck = {}
    for e in repair_log:
        if e.get("kind") == "req-cite":
            rq_stuck[e["sid"]] = rq_stuck.get(e["sid"], 0) + 1
    rq_round = 0
    # 批十一残余修（批十自审）：P6.7 整节重起草换全文，指令只带 REQ 面
    # 双注入而缺评分点保留——P6.6 收口（52/52）会被洗掉（r6b 7→8→31
    # 覆盖回退同族入口，批七 D3 修了 P6.5 入口后这是同型第三入口）。每轮
    # 取活体覆盖面（P6.6 已过序不会重来，丢点只能在本轮内补回）：
    # scoring_points_hint（重起草丢的点随指令补）+ retained_points_hint
    # （已命中点保留，只增不删）。
    while any(s.get("uncovered_reqs") for s in q_mid["sections"]):
        bad = {s["section_id"]: s for s in q_mid["sections"] if s.get("uncovered_reqs")}
        rq_round += 1
        if rq_round > 5:
            print(f"[P6.7] REQ 引用补齐轮耗尽——剩余 {sum(len(s['uncovered_reqs']) for s in bad.values())}"
                  f" 条如实登记（不豁免）")
            break
        print(f"[P6.7] REQ 引用补齐轮 {rq_round}: "
              f"{sum(len(s['uncovered_reqs']) for s in bad.values())} 条未覆盖 REQ → "
              f"{len(bad)} 叶定向重起草（未覆盖补齐 + 已覆盖保留双注入）")
        cov_rq = must("check_scoring_coverage", {"project_id": PID}, f"cov-p67:{rq_round}")
        sec_pts_rq = realagent_evidence.section_points_for_repair(cov_rq)
        for sid, s in sorted(bad.items()):
            unc = s["uncovered_reqs"]
            cov = s.get("covered_reqs") or []
            pts_now = sec_pts_rq.get(sid, {})
            stuck = rq_stuck.get(sid, 0) + 1
            rq_stuck[sid] = stuck
            # 批#221：EV 保留随行——P6.7 整节重写洗掉的节级已援引 EV 不
            # 触发 P6.8 重收口（其判据是文档级零援引），cited_evs 保留
            # 纪律必须随指令同行。指令尾统一走 p67_repair_instruction_tail
            # （批十双分支——stuck ≥ 2 切逐 REQ 响应段兜底，批九 G1 对偶）。
            instr = (INITIAL_INSTR + EV_HINT
                     + realagent_evidence.p67_repair_instruction_tail(
                         unc, cov,
                         pts_now.get("missing", []), pts_now.get("hit", []),
                         s.get("cited_evs") or [], stuck))
            why = (f"P6.7 REQ 引用: {len(unc)} 条未覆盖——" + (
                f"逐 REQ 响应段兜底（历史 {stuck - 1} 轮织入未收敛）"
                if stuck >= 2 else
                f"定向重起草补引用（已覆盖 {len(cov)} 条保留防回退）"))
            r = call("draft_response_section", {
                "project_id": PID, "section_id": sid,
                "instructions": instr,
                "generator": "real", "project_version": "latest",
            }, timeout=620)
            if not r.get("ok"):
                err = json.dumps(r.get("error", {}), ensure_ascii=False)
                if "429" in err or "Too many requests" in err or "LLM" in err:
                    print(f"[P6.7] {sid} 修复生成失败（限流）——保存进度优雅退出: {err[:160]}")
                    exit_code = 2
                    break
                raise AssertionError(f"[req-cite-repair:{sid}] {err[:400]}")
            st = r["data"].get("stats", {})
            draft_stats = [x for x in draft_stats if x["sid"] != sid]
            draft_stats.append({"sid": sid, "words": st.get("words"),
                                "citations": st.get("citations")})
            repair_log.append({"round": 300 + rq_round, "sid": sid,
                              "kind": "req-cite",
                              "why": [why],
                              "floor": 600, "ban": False,
                              "words": st.get("words"),
                              "citations": st.get("citations")})
            print(f"[P6.7] {sid} 重起草 words={st.get('words')} "
                  f"cites={st.get('citations')}"
                  + ("（逐 REQ 响应段兜底：" + str(len(unc)) + " 条）"
                     if stuck >= 2 else
                     f"（补 {len(unc)} 条引用 + 保留 {len(cov)} 条）"),
                  flush=True)
            save_state({"draft": {"stats": draft_stats}, "repair": repair_log})
            time.sleep(DRAFT_GAP_S)
        if exit_code == 2:
            sys.exit(2)
        q_mid = must("check_bid_quality", {"project_id": PID, "project_version": "latest"},
                     f"q-mid:{rq_round}")
    print(f"[P6.7] REQ 引用收口: uncovered="
          f"{sum(len(s.get('uncovered_reqs') or []) for s in q_mid['sections'])}")

    # ---- P6.8 证据引用补齐修复轮（批十一——r7 诚实边界 P9.5 面落地）----
    # r7 实锚：P9.5 证据引用 2/3——EV-0064（营业执照）全文 0 援引。根因
    # 双层：①绑定面缺口（P4 旧面只绑 quals[0]/perfs[0]——EV-0064 注册后
    # 从未绑定任何 REQ 组：不绑定即不进任何节素材面，且起草器剔除「不在
    # 已知集」的引用，LLM 写了也被剥掉；P4 已修全量绑定，面向新跑生效）；
    # ②引用面无修复轮（P6.5 blocker/P6.6 评分点/P6.7 REQ 引用之后，唯独
    # EV 引用无修复面——evidence_citation 只在 P9.5 落盘登记）。本轮收口②。
    # 引擎口径注记：sections[].uncited_evs 是信息面（绑定集内未援引——非
    # 全部证据都必须在每节援引）；本轮判据是**文档级零援引**（registered
    # − 各节 cited_evs 并集——全档没有任何一节援引过它，审阅面关注项口径），
    # 不做「每节必须援引」的过度收紧。每个零援引 EV 定位其文档序首个绑定
    # 节 → 定向重起草，指令带完整保留栈（评分点 + REQ 引用 + 已援引 EV——
    # 整节重起草换全文，缺哪层保留即洗哪层已收口面）。≥2 轮不收敛切逐
    # EV 援引段兜底（ev_statement_hint，P6.7 响应段兜底对偶）；5 轮上限
    # 耗尽如实登记（不豁免不装绿）。
    # ★执行位置契约（E_STATE 纪律，tests/test_p68_ev_repair_order.py
    # 回归锁）：P6.7 之后、首个全稿 validate 之前（Drafting 态内）。
    ev_registered = [e for e, _, _ in ev_ids]
    ev_stuck = {}
    for e in repair_log:
        if e.get("kind") == "ev-cite":
            for ev in e.get("evs", []):
                ev_stuck[ev] = ev_stuck.get(ev, 0) + 1
    ev_round = 0
    while True:
        cited_any = set()
        sec_ev_uncited = {}
        for s in q_mid["sections"]:
            cited_any.update(s.get("cited_evs") or [])
            for e in (s.get("uncited_evs") or []):
                sec_ev_uncited.setdefault(e, []).append(s["section_id"])
        never_cited = [e for e in ev_registered if e not in cited_any]
        if not never_cited:
            break
        plan_ev = {}
        unlocatable = []
        for e in never_cited:
            sids = sec_ev_uncited.get(e) or []
            if not sids:
                unlocatable.append(e)
                continue
            plan_ev.setdefault(sids[0], []).append(e)
        if not plan_ev:
            print(f"[P6.8] 零援引证据 {never_cited} 无绑定节可定向——绑定面缺口"
                  f"（P4 全量绑定面向新跑生效；如实登记不硬造）")
            break
        ev_round += 1
        if ev_round > 5:
            print(f"[P6.8] 证据引用补齐轮耗尽——剩余零援引 {never_cited} "
                  f"如实登记（不豁免）")
            break
        print(f"[P6.8] 证据引用补齐轮 {ev_round}: 零援引 {never_cited} → "
              f"{len(plan_ev)} 叶定向重起草"
              + (f"（{unlocatable} 无绑定节跳过）" if unlocatable else ""))
        cov_ev = must("check_scoring_coverage", {"project_id": PID}, f"cov-p68:{ev_round}")
        sec_pts_ev = realagent_evidence.section_points_for_repair(cov_ev)
        for sid, evs in sorted(plan_ev.items()):
            s = next(x for x in q_mid["sections"] if x["section_id"] == sid)
            unc_reqs = s.get("uncovered_reqs") or []
            cov_reqs = s.get("covered_reqs") or []
            cited_evs = s.get("cited_evs") or []
            pts_now = sec_pts_ev.get(sid, {})
            stuck_evs, fresh_evs = [], []
            for e in evs:
                stuck_after = ev_stuck.get(e, 0) + 1
                ev_stuck[e] = stuck_after
                (stuck_evs if stuck_after >= 2 else fresh_evs).append(e)
            instr = (INITIAL_INSTR + EV_HINT
                     + realagent_evidence.p68_repair_instruction_tail(
                         fresh_evs, stuck_evs, cited_evs, unc_reqs, cov_reqs,
                         pts_now.get("missing", []), pts_now.get("hit", [])))
            why = (f"P6.8 证据引用: {len(evs)} 项零援引——定向重起草补援引"
                   f"（已援引 {len(cited_evs)} 项保留防回退）")
            r = call("draft_response_section", {
                "project_id": PID, "section_id": sid,
                "instructions": instr,
                "generator": "real", "project_version": "latest",
            }, timeout=620)
            if not r.get("ok"):
                err = json.dumps(r.get("error", {}), ensure_ascii=False)
                if "429" in err or "Too many requests" in err or "LLM" in err:
                    print(f"[P6.8] {sid} 修复生成失败（限流）——保存进度优雅退出: {err[:160]}")
                    exit_code = 2
                    break
                raise AssertionError(f"[ev-cite-repair:{sid}] {err[:400]}")
            st = r["data"].get("stats", {})
            draft_stats = [x for x in draft_stats if x["sid"] != sid]
            draft_stats.append({"sid": sid, "words": st.get("words"),
                                "citations": st.get("citations")})
            repair_log.append({"round": 400 + ev_round, "sid": sid,
                              "kind": "ev-cite", "evs": evs,
                              "why": [why],
                              "floor": 600, "ban": False,
                              "words": st.get("words"),
                              "citations": st.get("citations")})
            print(f"[P6.8] {sid} 重起草 words={st.get('words')} "
                  f"cites={st.get('citations')}"
                  + (f"（援引段兜底：{stuck_evs}）" if stuck_evs
                     else f"（补 {len(fresh_evs)} 项援引 + 保留 {len(cited_evs)} 项）"),
                  flush=True)
            save_state({"draft": {"stats": draft_stats}, "repair": repair_log})
            time.sleep(DRAFT_GAP_S)
        if exit_code == 2:
            sys.exit(2)
        q_mid = must("check_bid_quality", {"project_id": PID, "project_version": "latest"},
                     f"q-ev:{ev_round}")
    ev_cited_final = set()
    for s in q_mid["sections"]:
        ev_cited_final.update(s.get("cited_evs") or [])
    print(f"[P6.8] 证据引用收口: 全档援引 {sorted(ev_cited_final)} / 注册 {ev_registered}")

    # ---- P6 校验 ----
    d = must("validate_bid_document", {"project_id": PID, "scope": "all",
                                       "project_version": "latest"}, "validate")
    print(f"[P6] 校验: ok={d.get('ok')} counts={d.get('counts')}")

    # ---- 批#221：P6.5 前基线捕获（P6.8 收口面——最后一次重写后的集合验证锚）----
    # P6.5 是修复链**最后一个**整节重写入口，其后无任何轮次再兜底。
    # 保留回归门（每轮修复体后）以本基线比对：丢 REQ / 丢 EV（节级已
    # 援引集合）/ 评分点覆盖数。门必须先于零 blocker validate 收口（该
    # 次 validate 即推进 VALIDATING，Drafting 态外重写被状态机拒绝）。
    q_base = must("check_bid_quality", {"project_id": PID, "project_version": "latest"},
                  "q-base")
    base_req_cov, base_ev_cit = set(), set()
    for s_ in q_base.get("sections") or []:
        base_req_cov.update(s_.get("covered_reqs") or [])
        base_ev_cit.update(s_.get("cited_evs") or [])
    cov_base = must("check_scoring_coverage", {"project_id": PID}, "cov-base")
    base_pts_cov = cov_base["summary"].get("points_covered", 0)

    # ---- P6.5 BLOCKER 修复轮（真实 LLM 面的诚实修复——不豁免不绕门）----
    # blocker 形态（huaian 真跑实锚）：E_CHARS_BELOW_MIN（评分章节篇幅门
    # ——无豁免硬门）与 E_AMOUNT_CONFLICT/E_SCHEDULE_CONFLICT（LLM 跨节
    # 金额/工期口径漂移——#113 验收点名的「虚构参数」面）。处置 = 定向
    # 重起草（统一 PROFILE 口径 + 篇幅下限指令），重校直至零 blocker 或
    # 轮次耗尽（耗尽 = 如实报红退出，不豁免）。
    # （repair_log 已模块级初始化并 resume 恢复——#113 审计修复批）
    # 规范值（huaian 真件正源：投标总报价=PROFILE、保证金=须知前附表
    # 3.5.1「人民币肆万陆仟圆整￥46000」、工期=PROFILE 37 天）
    CANON = {"投标总报价": 4800000, "投标保证金": 46000, "工期": 37}
    MONEY_BAN = ("本节为资格/合规响应面：全文不得出现「投标总报价」「投标保证金」"
                 "「报价」等金额表述与任何金额数字（金额口径只在投标函/报价节"
                 "统一表述）；工期如需表述用「自合同签订之日起三十七个日历日内"
                 "完成」的文字形态，不出现阿拉伯数字。")
    # v3-r2 实弹新面：LLM 发明具体分项数且节内自相矛盾（SEC-0012 服务部分
    # 46,365 vs 89,635 / 设备部分 100,000 vs 4,710,365）。修复口径锚 =
    # v2 复审通过的成品面：分项不落具体数、只声明纪律（480万/46,000
    # canonical 照常）——分项和一致性门（批一）继续在线把关。
    NO_SPLIT = ("分项报价纪律（v2 复审通过面）：本节不写任何具体分项报价数值——"
                "「设备部分报价」「服务部分报价」金额一律不落具体数，只保留"
                "「分项报价之和等于投标总报价、未将最高投标限价作为本方分项"
                "报价」的纪律声明；节内金额口径仅限：投标总报价 4,800,000 元"
                "（肆佰捌拾万元整）、投标保证金 46,000 元（肆万陆仟圆整）、"
                "工期 37 天、投标有效期 90 天。")
    # 批八 G3（#113 代码审计）：方向门 blocker 定向口径——句级三要素共现
    # 判 BLOCKER（含规则复述句），重起草必须教会模型合规句式，否则复述
    # 「报价高于限价将被否决」规则句即再犯、轮次耗尽假终局（r6b
    # SEC-0015 实锚）。
    CAP_DIR_DISCIPLINE = (
        "报价方向纪律（#113 批六④门）：全文任何句式——包括对招标文件"
        "规则的复述引用——不得出现「报价/总价…高于/超过/超出…限价」的"
        "表述（句级三要素共现即判废标级 BLOCKER，引述句不放行）；我方"
        "报价合规口径一律写「投标总报价未超过/不高于最高投标限价」。")

    def repair_instruction(floor, ban_money, no_split=False):
        instr = ("按招标文件逐项响应，引用只准用列出的 REQ/EV 编号。"
                 f"正文不少于 {floor} 字（当前版本未达篇幅门——逐条展开写足）。")
        if ban_money:
            instr += MONEY_BAN
        else:
            instr += ("全文金额与工期口径统一：投标总报价 4,800,000 元"
                      "（肆佰捌拾万元整）；投标保证金 46,000 元（肆万陆仟圆整）；"
                      "工期 37 天；投标有效期 90 天。"
                      "分项报价纪律（#113 审计批）：如需分项（设备/服务部分报价），"
                      "分项之和必须等于投标总报价，且不得把招标文件最高投标限价"
                      "当分项报价；源文件未给定金额（如履约保证金费率）不写具体"
                      "数值，按招标文件原文表述（「金额见前附表」）。")
        # 批六③：业绩实载口径随修复指令同行（整节重起草换全文——身份锚
        # 与业绩实载若不随行，重起草产物即回退到无锚自由发挥；r5 段18
        # 凑线值/日期矛盾即此类产物）。口径与 initial_instructions 同源。
        instr += ("业绩实载口径（EV-0065，以证据件为准）：合同金额 260 万元、"
                  "签订日期 2023-05-20——业绩金额/日期表述与此口径一致，"
                  "不得把资格线数值（累计不低于 200 万）当业绩金额写入，"
                  "不得虚写资格窗口内日期；业绩一览表金额/日期栏与正文口径"
                  "一致。")
        if no_split:
            instr += NO_SPLIT
        return instr

    for round_no in range(1, 16):
        d = must("validate_bid_document", {"project_id": PID, "scope": "all",
                                           "project_version": "latest"}, f"validate:{round_no}")
        blockers = [f for f in d.get("findings", [])
                    if str(f.get("severity", "")).upper() == "BLOCKER"]
        if not blockers:
            break
        print(f"[P6.5] 修复轮 {round_no}: {len(blockers)} blocker 待处置")
        # 目标计划：sid → {floor, ban}（同节多问题合并——floor 取最大）
        plan = {}
        unrepairable = []
        for f in blockers:
            msg = f.get("message") or ""
            code = f.get("rule_code")
            if code == "E_TOTAL_CHARS_BELOW_MIN":
                # 总篇幅缺口 → 定向重起草最短的已起草节（真实 LLM 补写，
                # 不用 runner 自拟段——#113 真实性口径）
                m = re.search(r"正文字数 (\d+) 低于总篇幅目标 (\d+)", msg)
                if not m:
                    unrepairable.append(f"{code}: {msg}")
                    continue
                gap = int(m.group(2)) - int(m.group(1)) + 600
                by_words = sorted((x for x in draft_stats if x.get("words")),
                                  key=lambda x: x["words"])
                for x in by_words:
                    if gap <= 0:
                        break
                    add = 1250 - x["words"]
                    if add <= 0:
                        continue
                    e = plan.setdefault(x["sid"], {"floor": 0, "ban": False, "why": []})
                    e["floor"] = max(e["floor"], 1250)
                    e["why"].append(f"总篇幅缺口 {gap}（本节 {x['words']} 字→扩写）")
                    gap -= add
                if gap > 0:
                    unrepairable.append(f"{code}: 短节扩写计划后仍缺 {gap} 字")
            elif code == "E_CHARS_BELOW_MIN":
                sid = f.get("section_id")
                m = re.search(r"最低篇幅 (\d+)", msg)
                floor = (int(m.group(1)) if m else 450) + 250
                e = plan.setdefault(sid, {"floor": 0, "ban": False, "why": []})
                e["floor"] = max(e["floor"], floor)
                e["why"].append(f"{code}: {msg[:80]}")
            elif code in ("E_AMOUNT_CONFLICT", "E_SCHEDULE_CONFLICT"):
                kind = next((k for k in CANON if k in msg), None)
                pairs = re.findall(r"(SEC-\d+)=(\d+)", msg)
                if pairs and not kind:
                    # v3-r2 实弹新面：非规范键的节内分项冲突（服务部分报价
                    # SEC-0012=46365 vs 89635 等——LLM 发明具体分项数）。
                    # 修复 = no_split 定向重起草（不写具体分项数，v2 复审
                    # 通过面口径）；分项和门（批一）继续复验把关。
                    for s in sorted({s for s, _ in pairs}):
                        e = plan.setdefault(s, {"floor": 0, "ban": False, "why": []})
                        e["floor"] = max(e["floor"], 600)
                        e["no_split"] = True
                        e["why"].append(f"{code}: {msg[:80]}（分项口径节内冲突——"
                                        "no_split 重起草：不写具体分项数）")
                    continue
                if not kind or not pairs:
                    unrepairable.append(f"{code}: {msg}")
                    continue
                wrong = {s for s, v in pairs if int(v) != CANON[kind]}
                right = {s for s, v in pairs if int(v) == CANON[kind]}
                targets = wrong if right else {s for s, _ in pairs}
                for s in sorted(targets):
                    e = plan.setdefault(s, {"floor": 0, "ban": False, "why": []})
                    e["floor"] = max(e["floor"], 600)
                    e["ban"] = True
                    e["why"].append(f"{code}: {msg[:80]}（规范 {kind}={CANON[kind]:,}）")
            elif code == "E_BID_CAP_DIRECTION":
                # 批八 G3（#113 代码审计）：方向门 blocker 定向修复——兜底分支
                # 重起草无方向口径，模型复述「报价高于限价将被否决」规则句即
                # 再犯（句级三要素共现判 BLOCKER，引述句不放行），轮次耗尽
                # 假终局。置 cap_dir 旗标，重起草指令注入 CAP_DIR_DISCIPLINE
                # （合规口径「未超过/不高于限价」+ 规则复述句禁写纪律）。
                e = plan.setdefault(f["section_id"], {"floor": 0, "ban": False, "why": []})
                e["floor"] = max(e["floor"], 600)
                e["cap_dir"] = True
                e["why"].append(f"{code}: {msg[:80]}")
            else:
                if f.get("section_id"):
                    e = plan.setdefault(f["section_id"], {"floor": 0, "ban": False, "why": []})
                    e["floor"] = max(e["floor"], 500)
                    e["why"].append(f"{code}: {msg[:80]}")
                else:
                    unrepairable.append(f"{code}: {msg}")
        if unrepairable:
            print(f"[P6.5] {len(unrepairable)} 条不可定向修复——登记: "
                  f"{[u[:60] for u in unrepairable]}")
        # 批八 G2（#113 代码审计——D3 修复不完整的另一半入口）：P6.5 整节
        # 重起草换全文时只带补齐面（scoring_points_hint）而缺已命中点保留
        # 纪律——P6.6 收敛的覆盖仍会被 P6.5 洗掉（覆盖回退入口）。每轮取
        # 当前覆盖面（check_scoring_coverage）算 hit/missing，重起草指令与
        # P6.6 同款双注入：全量点补齐 + 已命中点保留（只增不删）。
        cov_r = must("check_scoring_coverage", {"project_id": PID}, f"cov-p65:{round_no}")
        sec_pts_r = realagent_evidence.section_points_for_repair(cov_r)
        # 批十 P6.7 对偶（批八 G2 同型入口）：P6.5 整节重起草换全文——
        # 不带 REQ 引用纪律会把 P6.7 收口洗掉（REQ 引用回退入口）。每轮
        # 取活体 check_bid_quality 的 REQ 面（validate 响应无
        # sections[].covered_reqs——数据源必须用 quality 工具），指令双
        # 注入：未覆盖 REQ 补齐（req_citation_hint）+ 已覆盖 REQ 保留
        # （retained_req_citation_hint，只增不删）。
        q_r = must("check_bid_quality", {"project_id": PID, "project_version": "latest"},
                   f"q-p65:{round_no}")
        sec_reqs_r = {s.get("section_id"): s for s in (q_r.get("sections") or [])}
        for sid, e in sorted(plan.items()):
            r = call("draft_response_section", {
                "project_id": PID, "section_id": sid,
                # 批三补（v3 E_STATE 修复同款纪律）：修复指令携带本节映射
                # 评分点——整节重起草换全文，点不随行即洗掉 P6.6 已命中的
                # 细则覆盖（覆盖不回退）。批#221：指令尾统一走
                # p65_retention_payload（保留栈含 EV 面——同一 q_r 活体
                # 响应内 cited_evs，零额外工具调用）。
                "instructions": (repair_instruction(
                                     e["floor"], e["ban"], bool(e.get("no_split")))
                                 + EV_HINT
                                 + (CAP_DIR_DISCIPLINE if e.get("cap_dir") else "")
                                 + realagent_evidence.p65_retention_payload(
                                     ((sec_pts_r.get(sid, {}).get("missing", [])
                                       + sec_pts_r.get(sid, {}).get("hit", []))
                                      or (POINTS_MAP.get(sid) or [])),
                                     sec_pts_r.get(sid, {}).get("hit", []),
                                     (sec_reqs_r.get(sid) or {}).get("uncovered_reqs")
                                     or [],
                                     (sec_reqs_r.get(sid) or {}).get("covered_reqs")
                                     or [],
                                     (sec_reqs_r.get(sid) or {}).get("cited_evs")
                                     or [])),
                "generator": "real", "project_version": "latest",
            }, timeout=620)
            if not r.get("ok"):
                err = json.dumps(r.get("error", {}), ensure_ascii=False)
                if "429" in err or "Too many requests" in err or "LLM" in err:
                    print(f"[P6.5] {sid} 修复生成失败（限流）——保存进度优雅退出: {err[:160]}")
                    exit_code = 2
                    break
                raise AssertionError(f"[repair:{sid}] {err[:400]}")
            st = r["data"].get("stats", {})
            draft_stats = [x for x in draft_stats if x["sid"] != sid]
            draft_stats.append({"sid": sid, "words": st.get("words"),
                                "citations": st.get("citations")})
            repair_log.append({"round": round_no, "sid": sid, "why": e["why"],
                               "floor": e["floor"], "ban": e["ban"],
                               "no_split": bool(e.get("no_split")),
                               "words": st.get("words"), "citations": st.get("citations")})
            print(f"[P6.5] {sid} 重起草 floor={e['floor']} ban={e['ban']} "
                  f"no_split={bool(e.get('no_split'))} "
                  f"words={st.get('words')} cites={st.get('citations')}", flush=True)
            save_state({"draft": {"stats": draft_stats}, "repair": repair_log})
            time.sleep(DRAFT_GAP_S)
        if exit_code == 2:
            sys.exit(2)
        # ---- 批#221 保留回归门（issue 任务 3：验证最后一次重写之后的集合）----
        # 每轮修复体后、下轮 validate 前收口（零 blocker validate 即推进
        # VALIDATING——门在推进前才合法重写）。回退 = p68 全栈尾定向修复
        # （≤2 轮，修复有界）；未收口 = 如实 FAIL（regression-unresolved
        # .json + exit 1，不装绿——「不能只在 P9 落日志后标成已收口」）。
        # 只在本轮真发生重写（plan 非空）时过门——无重写即无回退面。
        if plan:
            for gate_round in (1, 2):
                q_gate = must("check_bid_quality",
                              {"project_id": PID, "project_version": "latest"},
                              f"q-gate:{round_no}.{gate_round}")
                cov_gate = must("check_scoring_coverage", {"project_id": PID},
                                f"cov-gate:{round_no}.{gate_round}")
                sec_pts_gate = realagent_evidence.section_points_for_repair(cov_gate)
                now_req_cov, now_ev_cit = set(), set()
                for s_ in q_gate.get("sections") or []:
                    now_req_cov.update(s_.get("covered_reqs") or [])
                    now_ev_cit.update(s_.get("cited_evs") or [])
                now_pts_cov = cov_gate["summary"].get("points_covered", 0)
                lost_reqs = base_req_cov - now_req_cov
                lost_evs = base_ev_cit - now_ev_cit
                lost_pts = base_pts_cov - now_pts_cov
                if not (lost_reqs or lost_evs or lost_pts > 0):
                    break
                if gate_round > 1:
                    json.dump({
                        "baseline": {"covered_reqs": sorted(base_req_cov),
                                     "cited_evs": sorted(base_ev_cit),
                                     "points_covered": base_pts_cov},
                        "after_final_rewrite": {"covered_reqs": sorted(now_req_cov),
                                                "cited_evs": sorted(now_ev_cit),
                                                "points_covered": now_pts_cov},
                        "lost": {"reqs": sorted(lost_reqs), "evs": sorted(lost_evs),
                                 "points": lost_pts},
                    }, open(os.path.join(OUT, "regression-unresolved.json"), "w"),
                        ensure_ascii=False, indent=1)
                    print(f"[P6.5-gate] 保留回退两轮定向修复未收口——如实报红退出："
                          f"丢 REQ {sorted(lost_reqs)} / 丢 EV {sorted(lost_evs)} / "
                          f"评分点 {base_pts_cov}→{now_pts_cov}"
                          f"（regression-unresolved.json，不装绿）")
                    sys.exit(1)
                print(f"[P6.5-gate] ⚠保留回退（P6.5 轮 {round_no} 后）：丢 REQ "
                      f"{sorted(lost_reqs)} / 丢 EV {sorted(lost_evs)} / 评分点 "
                      f"{base_pts_cov}→{now_pts_cov}——全栈指令定向修复（门轮 {gate_round}）")
                gate_plan = {}
                for s_ in q_gate.get("sections") or []:
                    sid_ = s_.get("section_id")
                    if ((lost_reqs & set(s_.get("uncovered_reqs") or []))
                            or (lost_evs & set(s_.get("uncited_evs") or []))
                            or (lost_pts > 0 and sec_pts_gate.get(sid_, {}).get("missing"))):
                        gate_plan[sid_] = s_
                for sid_, s_ in sorted(gate_plan.items()):
                    pf = sec_pts_gate.get(sid_, {})
                    fresh_evs = sorted(lost_evs & set(s_.get("uncited_evs") or []))
                    instr = (INITIAL_INSTR + EV_HINT
                             + realagent_evidence.p68_repair_instruction_tail(
                                 fresh_evs, [],
                                 s_.get("cited_evs") or [],
                                 s_.get("uncovered_reqs") or [],
                                 s_.get("covered_reqs") or [],
                                 pf.get("missing", []), pf.get("hit", [])))
                    r = call("draft_response_section", {
                        "project_id": PID, "section_id": sid_,
                        "instructions": instr,
                        "generator": "real", "project_version": "latest",
                    }, timeout=620)
                    if not r.get("ok"):
                        err = json.dumps(r.get("error", {}), ensure_ascii=False)
                        if "429" in err or "Too many requests" in err or "LLM" in err:
                            print(f"[P6.5-gate] {sid_} 修复生成失败（限流）——"
                                  f"保存进度优雅退出: {err[:160]}")
                            exit_code = 2
                            break
                        raise AssertionError(f"[retain-gate:{sid_}] {err[:400]}")
                    st = r["data"].get("stats", {})
                    draft_stats = [x for x in draft_stats if x["sid"] != sid_]
                    draft_stats.append({"sid": sid_, "words": st.get("words"),
                                        "citations": st.get("citations")})
                    repair_log.append({"round": 500 + round_no, "sid": sid_,
                                      "kind": "retain-gate",
                                      "why": [f"保留回归门：丢 REQ {sorted(lost_reqs)} /"
                                              f" 丢 EV {sorted(lost_evs)} /"
                                              f" 评分点 {base_pts_cov}→{now_pts_cov}"],
                                      "floor": 600, "ban": False,
                                      "words": st.get("words"),
                                      "citations": st.get("citations")})
                    print(f"[P6.5-gate] {sid_} 定向重写 words={st.get('words')} "
                          f"cites={st.get('citations')}", flush=True)
                    save_state({"draft": {"stats": draft_stats}, "repair": repair_log})
                    time.sleep(DRAFT_GAP_S)
                if exit_code == 2:
                    sys.exit(2)
        if unrepairable and not plan:
            break  # 无可修复面——轮次无意义，提前收口报红
    d = must("validate_bid_document", {"project_id": PID, "scope": "all",
                                       "project_version": "latest"}, "validate:final")
    if d.get("counts", {}).get("blocker", 0) > 0:
        print(f"[P6.5] 修复轮耗尽仍有 {d['counts']['blocker']} blocker——如实报红退出（不豁免）")
        for f in d.get("findings", []):
            if str(f.get("severity", "")).upper() == "BLOCKER":
                print(f"    {f.get('rule_code')}@{f.get('section_id')}: {f.get('message')}")
        json.dump({"validate_final": d.get("counts"), "blockers": [
            f for f in d.get("findings", []) if str(f.get("severity", "")).upper() == "BLOCKER"],
            "repair_log": repair_log},
            open(os.path.join(OUT, "blockers-unresolved.json"), "w"), ensure_ascii=False, indent=1)
        sys.exit(1)
    print(f"[P6.5] 零 blocker（修复 {len(repair_log)} 节次）")

    # ---- P7' 导出前门 ----
    pass_gate("pre_export_confirm", "#113 验收跑批：定稿内容过门（agent 声明——留痕待人工追认）")

    # ---- P8 导出（output_path 须工作区相对路径）----
    rel_out = "out/投标文件-realagent-113.docx"
    export_args = {
        "project_id": PID, "format": "docx", "output_path": rel_out,
        "profile": PROFILE, "max_overrun_pct": 10000,
        "project_version": "latest",
    }
    # 门 1h：P4.6 已逐项映射（#153 正门）；若仍有 unmapped（理论不应——
    # 映射覆盖 check_scoring_coverage 全部未映射面）才豁免并如实登记。
    cov_pre = must("check_scoring_coverage", {"project_id": PID}, "cov-pre-export")
    if cov_pre["summary"]["criteria_unmapped"] > 0:
        export_args["waive_unmapped_scoring"] = (
            f"#113 验收如实登记：P4.6 映射后仍有 "
            f"{cov_pre['summary']['criteria_unmapped']} 条未映射评分项（映射面兜底后残留）"
        )
    # 格式件三件套（投标函抬头/法定代表人身份证明/授权委托书）企业身份
    # 数据缺位：合成素材面无真实企业材料——issue 红线「不造企业材料」，
    # 走显式豁免通道（成品定位 = 可交付审阅稿，格式件【待填】位人工补齐）。
    export_args["waive_format_placeholder"] = (
        "#113 验收如实登记：格式件三件套（投标函抬头/法定代表人身份证明/"
        "授权委托书）企业身份字段缺位——验收用合成素材无真实企业身份材料"
        "（issue 红线：不造企业材料）；成品按可交付审阅稿定位（不等正式"
        "可投标），格式件【待填】位由投标人人工补齐"
    )
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

    # ---- P9 细则点覆盖（闭门条件 2：命中 > 0）----
    cov = must("check_scoring_coverage", {"project_id": PID}, "cov-final")
    coverage_summary = cov["summary"]
    print(f"[P9] 细则覆盖: criteria={coverage_summary['criteria_total']} "
          f"points={coverage_summary['points_total']} covered={coverage_summary['points_covered']} "
          f"ratio={coverage_summary['coverage_ratio']:.3f} "
          f"deduction={coverage_summary['suggested_deduction']:.1f}")

    # ---- P9.5 证据引用计数（#113 审计缺口 4：EV-0065 实质未用零提示）----
    # 注册证据件是否被成品正文实际引用（审计实锚：3 件注册证据仅 EV-0063
    # 按 ID 引用，EV-0065 业绩合同正文 0 次出现——「真实模型实际调用证据」
    # 维度弱通过的事实本跑批结束时应留痕，不留给审计才发现）。
    ev_cite = realagent_state.count_evidence_citations(
        out_path, [e for e, _, _ in ev_ids])
    if ev_cite.get("uncited"):
        print(f"[P9.5] 证据引用审计: {len(ev_cite['cited'])}/{len(ev_ids)} 被引用；"
              f"未引用: {ev_cite['uncited']}（审阅面关注：证据件是否实质调用）")
    else:
        print(f"[P9.5] 证据引用审计: {len(ev_cite['cited'])}/{len(ev_ids)} 全部被引用")

    # ---- 质量面 + 台账 ----
    d = must("check_bid_quality", {"project_id": PID, "project_version": "latest"}, "quality")
    # #113 审计缺口②落盘：sections[].uncovered_reqs 明细引擎已算出，
    # 只落 summary 的旧面把「9 条未覆盖」变成了无明细总数——审校无从查
    uncovered_detail = realagent_evidence.aggregate_uncovered_reqs(d)
    if uncovered_detail["total"]:
        print(f"[P9.6] 未覆盖 REQ 明细: {uncovered_detail['total']} 条 "
              f"（mismatch={uncovered_detail['mismatch']}）——已落 metrics.uncovered_reqs")
    # #113 审计 P9 弱正留痕：哪 38 条细则点没逐字命中（审校素材）
    uncovered_points = realagent_evidence.aggregate_uncovered_points(cov)
    llm_usage = None
    up = os.path.join(WS, ".mang/llm-usage.json")
    if os.path.exists(up):
        llm_usage = json.load(open(up))
        # #113 审计批二补：llm-usage.json 台账随证据包归档（v1 是手拷的——
        # 漏拷即缺件，REPORT 文件表机器列实际清单时台账缺席）
        import shutil as _shutil
        _shutil.copyfile(up, os.path.join(OUT, "llm-usage.json"))
    result = {
        "project_id": PID, "actor": ACTOR,
        "main_file": os.path.basename(MAIN),
        "star_missing": {"count": star_missing_n, "detail": star_missing_detail},
        "evidence": [{"ev_id": e, "kind": k, "title": t, "synthetic": True} for e, k, t in ev_ids],
        "req_total": req_total, "leaves": len(leaves),
        "draft": {"leaves_done": len(done) + len(draft_stats), "total_words": total_words,
                  "stats": draft_stats},
        "validate": d.get("summary", {}),
        "uncovered_reqs": uncovered_detail,          # 审计缺口②：明细落盘
        "export": export_meta,
        "evidence_citation": ev_cite,
        "scoring_coverage": coverage_summary,
        "scoring_coverage_uncovered_points": uncovered_points,  # P9 哪条缺
        "llm_usage": llm_usage,
        # 累计口径：末轮进程秒数（旧口径 resume 下洗成 2s）→ 跨轮累计如实
        "elapsed_s": elapsed0 + int(time.time() - t_all),
        "resume_rounds": resume_rounds,
    }
    result["main_sha256"] = hashlib.sha256(open(MAIN, "rb").read()).hexdigest()
    json.dump(result, open(os.path.join(OUT, "realagent-metrics.json"), "w"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "tool-call-log.json"), "w") as f:
        json.dump(calls, f, ensure_ascii=False, indent=1)
    # ---- REPORT.md 机器底稿（#113 审计批二：防手写漂移——fe9d7ca 手写
    # 「含 13 节次修复决策日志」而 state 实为 decisions=[] 的教训；决策数/
    # 文件表全取 state 实留与 OUT 实际清单，人只改叙事。既有 REPORT.md
    # 不覆盖（封存不回改）→ REPORT.generated.md。----
    state_final = {}
    if os.path.exists(STATE_FILE):
        try:
            state_final = json.load(open(STATE_FILE))
        except (OSError, ValueError):
            state_final = {}
    report_path = realagent_evidence.report_target(OUT)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(realagent_evidence.build_report_md(result, state_final, OUT))
    print(f"[P10] REPORT 底稿: {os.path.basename(report_path)}"
          f"（机器取数；人工叙事在其上改）")
    print(f"[done] {OUT} （累计 {result['elapsed_s']}s/{result['resume_rounds'] + 1} 轮, "
          f"{len(calls)} 次工具调用）")
finally:
    bridge.terminate()
    try:
        bridge.wait(timeout=5)
    except subprocess.TimeoutExpired:
        bridge.kill()
    bridge_log.close()
sys.exit(exit_code)
