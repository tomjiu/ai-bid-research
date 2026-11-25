#!/usr/bin/env python3
"""recheck_other_tenders.py —— #113 用户问：其他标书的结果文件用当前引擎复检。

背景：multifile 验收（2026-11-18，基线 main 59790da）跑过 6 项目；songling 复核（11-13）
跑过松岭抽取。但那些都是批四~批七引擎（当前 eab556b）落地**之前**的旧基线——新透镜
（D1 拆点扩面/评分点抽取）从未应用于其他真实标书。

本脚本：纯确定性链（create→import→extract→outline→coverage），无 LLM，不受上游 429 影响。
对照基线：unicom-ry 302 REQ / songjiang 317 / cqyd 339（multifile 与 songling 复核口径）。
产出：识别层漂移 + D1 拆点新面 + 冲突告警面 → /home/z/my-project/scripts/recheck-report.json
"""
import json
import os
import re
import shutil
import subprocess

REPO = "/home/z/my-project/ai-bid-research"
BIN = os.path.join(REPO, "bidcore/target/debug/bid-mcp-stdio")

# (tag, 相对路径, 基线 REQ 数（旧引擎时代）, 基线来源)
FILES = [
    ("unicom-ry", "real-corpus/telecom/parse-input/A-unicom-ry-2026CUC-RJY-PT0783-招标文件.docx",
     302, "multifile-20261118"),
    ("songjiang", "real-corpus/telecom/parse-input/A-telecom-shanghai-songjiang-光终端放装-招标文件.docx",
     317, "songling-67-recheck-20261113"),
    ("shanxi", "real-corpus/telecom/parse-input/A-telecom-shanxi-灵枢智关-招标正文.docx",
     None, "无 REQ 级基线（engine-diff 仅块级 2587）"),
    ("cqyd", "real-corpus/telecom/parse-input/A-cqyd-20260500728-重庆西永水冷空调-招标文件.pdf",
     339, "multifile-20261118"),
]

REPORT = {"engine": "eab556b", "generated_at": "2026-11-25T12:2x", "projects": []}


def call(ws, tool, args, timeout=240):
    env = dict(os.environ, BID_WS=ws, BID_FS_ROOT=REPO)
    line = json.dumps({"tool": tool, "args": args}, ensure_ascii=False)
    r = subprocess.run([BIN], input=line + "\n", capture_output=True, text=True,
                       env=env, timeout=timeout)
    out = r.stdout.strip().splitlines()
    if not out:
        return {"ok": False, "error": {"what": f"no output; stderr={r.stderr[:200]}"}}
    try:
        return json.loads(out[-1])
    except Exception as e:
        return {"ok": False, "error": {"what": f"parse fail {e}; tail={out[-1][:200]}"}}


def main():
    for tag, rel, baseline, src in FILES:
        ws = f"/home/z/my-project/ws-recheck-{tag}"
        shutil.rmtree(ws, ignore_errors=True)
        os.makedirs(ws, exist_ok=True)
        path = os.path.join(REPO, rel)
        rep = {"tag": tag, "file": os.path.basename(rel), "baseline_req": baseline,
               "baseline_src": src, "steps": {}}

        r = call(ws, "create_bid_project", {
            "name": f"识别层复检-{tag}", "bid_deadline": "2026-12-31",
            "mode": "明标", "external_key": f"recheck-{tag}"})
        rep["steps"]["create"] = r.get("ok")
        if not r.get("ok"):
            rep["steps"]["create_err"] = r.get("error", {})
            REPORT["projects"].append(rep)
            continue
        pid = r["data"]["project_id"]

        r = call(ws, "import_tender_files", {
            "project_id": pid,
            "files": [{"upload_ref": path, "filename": os.path.basename(rel),
                       "kind": "招标文件"}]})
        rep["steps"]["import"] = r.get("ok")
        pf = (r.get("data", {}) or {}).get("per_file", [])
        rep["steps"]["per_file"] = [
            {"f": p.get("filename"), "status": p.get("status"),
             "err": (p.get("error") or {}).get("what", None) if p.get("error") else None}
            for p in pf]

        r = call(ws, "extract_requirements", {"project_id": pid})
        rep["steps"]["extract"] = r.get("ok")
        if r.get("ok"):
            d = r.get("data", {}) or {}
            rep["steps"]["extract_counts"] = d.get("counts", d)

        r = call(ws, "build_outline", {
            "project_id": pid, "target_total_chars": 48000,
            "max_reqs_per_leaf": 8, "project_version": "latest"})
        rep["steps"]["outline"] = r.get("ok")
        if r.get("ok"):
            rep["steps"]["outline_counts"] = (r.get("data", {}) or {}).get("counts", {})

        # D1 透镜：评分细则拆点（无需映射——criteria/points 在抽取面）
        r = call(ws, "check_scoring_coverage", {"project_id": pid})
        if r.get("ok"):
            d = r.get("data", {}) or {}
            summ = d.get("summary", {}) or {}
            crit = d.get("criteria", []) or []
            with_points = [c for c in crit if c.get("points")]
            pts = sum(len(c.get("points", [])) for c in crit)
            rep["scoring"] = {
                "criteria_total": summ.get("criteria_total"),
                "criteria_with_points": summ.get("criteria_with_points"),
                "criteria_unmapped": summ.get("criteria_unmapped"),
                "points_total": summ.get("points_total"),
                "hard_gates_excluded": summ.get("hard_gates_excluded"),
                "实测 with_points": len(with_points),
                "实测 points": pts,
            }
        else:
            rep["scoring"] = {"error": (r.get("error") or {}).get("what")}

        # A 层锚点完整性（全链审计同款）
        try:
            db = json.load(open(os.path.join(ws, "db.json")))
            reqs = db["domain"]["requirements"]
            rep["req_total"] = len(reqs)
            no_anchor = [x["id"] for x in reqs if not x.get("anchors")]
            empty_ex = [x["id"] for x in reqs if x.get("anchors")
                       and not (x["anchors"][0].get("excerpt") or "").strip()]
            bad_file = [x["id"] for x in reqs if x.get("anchors")
                        and x["anchors"][0].get("file") != os.path.basename(rel)]
            rep["anchor_check"] = {
                "A1_缺失": len(no_anchor), "A2_空摘录": len(empty_ex),
                "A3_文件异常": len(bad_file),
                "明细前5": (no_anchor + empty_ex + bad_file)[:5],
            }
            from collections import Counter
            rep["category"] = dict(Counter(x.get("category", "?") for x in reqs))
        except Exception as e:
            rep["anchor_check"] = {"error": str(e)[:120]}

        # db 里的警告/冲突面（抽取回执）
        try:
            rep["conflicts"] = len(db["domain"].get("conflicts", []))
            warns = db["domain"].get("extract_warnings", [])
            rep["extract_warnings"] = len(warns) if isinstance(warns, list) else warns
        except Exception:
            pass

        if baseline is not None and rep.get("req_total") is not None:
            delta = rep["req_total"] - baseline
            rep["req_drift_vs_baseline"] = {"delta": delta,
                                            "verdict": "一致" if delta == 0 else f"漂移 {delta:+d}"}
        REPORT["projects"].append(rep)
        print(f"[{tag}] req={rep.get('req_total')} baseline={baseline} "
              f"criteria={rep.get('scoring', {}).get('criteria_total')} "
              f"with_points={rep.get('scoring', {}).get('criteria_with_points')} "
              f"points={rep.get('scoring', {}).get('points_total')}")
        shutil.rmtree(ws, ignore_errors=True)

    with open("/home/z/my-project/scripts/recheck-report.json", "w") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1)
    print("报告: scripts/recheck-report.json")


if __name__ == "__main__":
    main()
