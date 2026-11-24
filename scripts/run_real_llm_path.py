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

    # ---- P6.6 细则覆盖修复轮（#113 审计批三：P9 0/39 根治面）----
    # v2 实锚：字面细则命中 0/39、条件 2 机器面回退为零。与 P6.5 同款
    # 定向重起草——对未命中点的映射叶注入该叶全部评分点（含已命中——
    # 重起草保持节内全文一致），复测直至覆盖或轮次耗尽（如实登记，
    # 不豁免）。留痕并入 repair（kind=scoring；round 100 起避开 P6.5
    # 1-15 的判别键空间）。
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
    while (cov_mid["summary"].get("points_covered", 0)
           < cov_mid["summary"].get("points_total", 0)):
        unc = realagent_evidence.aggregate_uncovered_points(cov_mid)["uncovered"]
        crit_by_id = {c.get("criterion_id"): c for c in cov_mid.get("criteria", [])}
        sid_pts = {}
        for u in unc:
            c = crit_by_id.get(u.get("criterion_id")) or {}
            for s in (c.get("mapped_sections") or []):
                sid_pts.setdefault(s, []).append(u["point"])
        if not sid_pts:
            print("[P6.6] 未命中点无映射叶可定向——如实登记退出（不豁免）")
            break
        sc_round += 1
        if sc_round > 5:
            print("[P6.6] 细则覆盖修复轮耗尽——剩余缺口如实登记（不豁免）")
            break
        print(f"[P6.6] 细则覆盖修复轮 {sc_round}: {len(unc)} 点未命中 → "
              f"{len(sid_pts)} 叶定向重起草")
        for sid, pts in sorted(sid_pts.items()):
            instr = (INITIAL_INSTR + EV_HINT
                     + realagent_evidence.scoring_points_hint(pts)
                     + " 本节当前版本未逐点命中上述评分细则——重起草逐点"
                       "补齐，正文不少于 600 字。")
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
                              "why": [f"P6.6 细则覆盖: {len(pts)} 点未命中——注入逐点响应指令重起草"],
                              "floor": 600, "ban": False,
                              "words": st.get("words"), "citations": st.get("citations")})
            print(f"[P6.6] {sid} 重起草 words={st.get('words')} "
                  f"cites={st.get('citations')}（注入 {len(pts)} 点）", flush=True)
            save_state({"draft": {"stats": draft_stats}, "repair": repair_log})
            time.sleep(DRAFT_GAP_S)
        if exit_code == 2:
            sys.exit(2)
        cov_mid = must("check_scoring_coverage", {"project_id": PID}, f"cov-mid:{sc_round}")
    print(f"[P6.6] 细则覆盖收口: covered={cov_mid['summary']['points_covered']}/"
          f"{cov_mid['summary']['points_total']}")

    # ---- P6 校验 ----
    d = must("validate_bid_document", {"project_id": PID, "scope": "all",
                                       "project_version": "latest"}, "validate")
    print(f"[P6] 校验: ok={d.get('ok')} counts={d.get('counts')}")

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
        for sid, e in sorted(plan.items()):
            r = call("draft_response_section", {
                "project_id": PID, "section_id": sid,
                # 批三补（v3 E_STATE 修复同款纪律）：修复指令携带本节映射
                # 评分点——整节重起草换全文，点不随行即洗掉 P6.6 已命中的
                # 细则覆盖（覆盖不回退）。
                "instructions": (repair_instruction(
                                     e["floor"], e["ban"], bool(e.get("no_split")))
                                 + EV_HINT
                                 + realagent_evidence.scoring_points_hint(
                                     POINTS_MAP.get(sid) or [])),
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
