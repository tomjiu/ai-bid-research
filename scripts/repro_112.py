#!/usr/bin/env python3
"""repro_112.py —— #112 松岭 67 关键点产品复验的机器面（只读复跑，不改产品）。

口径（issue #112 验收原文）：
  - 原件 PDF 重跑抽取（真实工具链：create → import → extract）
  - 七类分类分布（资格条件/否决项/评分项/技术参数/商务要求/格式要求/其他）
  - 16 条人工复核金标准（expected/requirements.reviewed.json）逐项召回：
    数值+单位双侧归一（NFKC 康熙部首 + 千分位剥离）匹配，记录 REQ/页码出处
  - ★标记面（params.star）与商务表 ★锚文对照
  - 误分类抽样（其他/格式要求两类——锚文随行供人工判读）
  - 67 条原始材料是否取得：本脚本不碰 67 条（材料四路皆缺，见报告）——
    不凑数、不改抽取器、不自动升级金标准。

跨平台重放纪律（#156 收口——2026-11-13）：
  - 全部文件 IO 与子进程显式 encoding="utf-8"（不依赖系统 locale——
    Windows cp936 下读 UTF-8 JSON 不再 UnicodeDecodeError 崩启动）
  - 参数化 ws/out/bin：默认 root 从脚本位置取得；exe 按平台补 .exe 后缀
    （Windows）；--workspace 支持唯一目录或验证为空目录（不固定共用旧数据）
  - 失败非零退出（工具链任一步 ok=false / 金标准文件缺失 → exit 1，
    附失败摘要——不再 assert 裸崩）
  - 记录：bid-mcp-stdio 二进制 SHA-256、PDF 原件 SHA-256、实际解析通道
    （工具 stderr/回执里的 pdfium/poppler 信号——只登记不裁决）

基线口径警示（防误读，如实）：
  - 16/16 检索/分类匹配 = 检索锚 OR 命中 + 分类一致——不等于「单位/上
    下限/完整语义保真」；语义级核对归人工复核（#112 金标准 sixteen 条
    的 statement 才是全文语义）
  - 67 条原始材料仍未取得（manifest MISSING 5 项）——召回面 16/16 不得
    抵充材料面
  - 解析通道不预设：每次实跑从导入回执/db 解析摘要取证据（无证据记
    unknown，不冒充）；PR #146 报告的 Poppler 318REQ 基线是作者研究链
    口径——通道间数字不可互充基线、不可直接比对

用法:
  python3 scripts/repro_112.py <ws_dir> <out_json> [bid-mcp-stdio 路径]
  （ws/out/bin 亦可用 --workspace/--out/--bin 覆盖；默认 root 取脚本位置）
默认二进制 = <root>/bidcore/target/debug/bid-mcp-stdio（Windows 自动补 .exe）。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "fixtures/songling-232762/tender/光纤租赁费招标文件.pdf"
GR_PATH = ROOT / "fixtures/songling-232762/expected/requirements.reviewed.json"


def die(msg: str) -> "None":
    print(f"[repro-112] FAIL：{msg}", file=sys.stderr)
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="#112 松岭复验机器面（只读复跑")
    ap.add_argument("ws_pos", nargs="?", help="工作区目录（或省略走 --workspace）")
    ap.add_argument("out_pos", nargs="?", help="报告 JSON 落盘路径（或省略走 --out）")
    ap.add_argument("bin_pos", nargs="?", help="bid-mcp-stdio 路径（或省略走 --bin）")
    ap.add_argument("--workspace", default=None, help="工作区目录（新建/唯一/或验证为空）")
    ap.add_argument("--out", default=None, help="报告 JSON 落盘路径")
    ap.add_argument("--bin", default=None, help="bid-mcp-stdio 可执行路径")
    args = ap.parse_args()
    args.ws = args.workspace or args.ws_pos
    args.out = args.out or args.out_pos
    args.bin = args.bin or args.bin_pos
    if not args.ws or not args.out:
        ap.error("ws 与 out 必须提供（位置参数或 --workspace/--out）")
    return args


def resolve_bin(bin_arg: str) -> Path:
    p = Path(bin_arg) if bin_arg else ROOT / "bidcore/target/debug/bid-mcp-stdio"
    # 平台 exe 后缀（#156：Windows 下自动补 .exe）
    if os.name == "nt" and p.suffix.lower() != ".exe" and not p.exists():
        cand = p.with_suffix(p.suffix + ".exe")
        if cand.exists():
            p = cand
    return p


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_ws(ws: Path) -> None:
    """安全复跑纪律（#156）：唯一目录或验证为空——不静默复用旧数据。"""
    if ws.exists():
        leftovers = [x for x in ws.iterdir() if x.name not in (".DS_Store",)]
        if leftovers:
            die(f"工作区 {ws} 非空（{len(leftovers)} 项旧数据）——换目录或清空后重跑，"
                "不固定共用旧 workspace")
    ws.mkdir(parents=True, exist_ok=True)


def load_gold() -> list[dict]:
    if not GR_PATH.exists():
        die(f"金标准文件缺失：{GR_PATH}")
    with open(GR_PATH, encoding="utf-8") as f:  # 显式 UTF8（#156：GBK 平台不再崩启动）
        doc = json.load(f)
    return doc["requirements"] if isinstance(doc, dict) else doc


def call(bin_path: Path, tool: str, tool_args: dict, env: dict, steps: list) -> dict:
    """工具链单步：显式 UTF8 + 失败可诊断（不裸 assert）。

    失败判定（两道闸，缺一不可——Lead 2026-11-14 实跑反例）：
      ① 子进程退出码非零 → 步骤失败（即使回执 JSON 声称 ok:true——
         「进程活着回执、死了退出」的分歧以退出码为准，回执原样保留
         供诊断，不得被上层 reply.ok 放行）；
      ② 回执 JSON ok:false / 无输出 → 步骤失败。
    步骤记录保留 returncode / stdout 尾部 / stderr 尾部（准确错误与
    输出——不吞）。返回值 ok 字段综合两闸；上层 main 只需检查 .ok。
    """
    line = json.dumps({"tool": tool, "args": tool_args}, ensure_ascii=False)
    t0 = time.time()
    try:
        r = subprocess.run(
            [str(bin_path)], input=line + "\n", capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env, timeout=600,
        )
    except FileNotFoundError as e:
        die(f"bid-mcp-stdio 不在位（{bin_path}）：{e}")
    ms = int((time.time() - t0) * 1000)
    out = (r.stdout or "").strip().splitlines()
    reply = {}
    if out:
        try:
            reply = json.loads(out[-1])
        except json.JSONDecodeError:
            die(f"工具 {tool} 回执非 JSON（尾部行：{out[-1][:120]!r}；"
                f"stderr：{(r.stderr or '')[:300]}）")
    else:
        reply = {"ok": False, "error": f"no output（stderr：{(r.stderr or '')[:300]}）"}
    # 闸①：非零退出码 → 步骤失败（ok:true 回执不豁免——保留原回执与
    # 退出码供诊断，附 failure_reason 标明分歧）
    step_ok = bool(reply.get("ok")) and r.returncode == 0
    if not step_ok and reply.get("ok") and r.returncode != 0:
        reply = dict(reply)
        reply["ok"] = False
        reply["failure_reason"] = (f"子进程退出码非零 {r.returncode}"
                                   f"（回执 JSON 曾称 ok:true——以退出码为准）")
    steps.append({"tool": tool, "ok": step_ok, "ms": ms,
                  "returncode": r.returncode,
                  "stdout_tail": (r.stdout or "")[-400:],
                  "stderr_tail": (r.stderr or "")[-400:]})
    if not step_ok:
        print(f"[repro-112] 工具 {tool} 步骤失败（exit {r.returncode}，"
              f"回执 ok={reply.get('ok')}）——stderr 尾部："
              f"{(r.stderr or '')[-400:]}", file=sys.stderr)
    return reply


def norm(s: str) -> str:
    """检索面归一：NFKC（康熙部首兼容字）+ 千分位剥离（#267 norm_n3 口径）。"""
    s = unicodedata.normalize("NFKC", s)
    return s.replace(",", "").replace("，", "")


def channel_from(actual: object) -> str | None:
    """从实际证据对象提取 pdfium/poppler 通道——**只采信成功文件的
    实际解析证据字段**（Lead 2026-11-14 三版收紧：整个对象 JSON 关键
    词扫描会把 filename=pdfium.pdf / 失败 probe 备注也当成功通道）。

    采信字段（每个 file 条目内，大小写不敏感）：
      - parse_summary（解析摘要——成功文件的实际通道叙述）；
      - 明确 engine 字段：engine / parse_engine / parser / channel /
        pdf_engine（引擎自述，值为 pdfium/poppler 字样即采信）。
    其余一切（filename、error、备注、路径）不作为通道依据——
    证据不足返回 None（→ unknown，不冒充）。

    纯函数（模块级——可被回归直接调用）；str 输入视为一段
    parse_summary 叙述（按同一口径处理）。"""
    if actual is None:
        return None

    def _from_summary_text(text: str) -> str | None:
        low = text.lower()
        if "pdfium" in low:
            return "pdfium"
        if "poppler" in low:
            return "poppler"
        return None

    if isinstance(actual, str):
        return _from_summary_text(actual)

    def _walk_files(node) -> str | None:
        """在证据对象里找 file 条目，只看其 parse_summary/engine 字段。"""
        if isinstance(node, dict):
            # 明确 engine 字段（引擎自述——不是 filename/error）
            for key in ("engine", "parse_engine", "parser", "channel",
                        "pdf_engine"):
                v = node.get(key)
                if isinstance(v, str):
                    got = _from_summary_text(v)
                    if got:
                        return got
            # 本条目的 parse_summary（file 条目级解析证据）
            v = node.get("parse_summary")
            if isinstance(v, str):
                got = _from_summary_text(v)
                if got:
                    return got
            # 其余键（filename/error/备注等）**不采信**——继续下钻
            # 找嵌套 file 条目
            for v in node.values():
                got = _walk_files(v)
                if got:
                    return got
        elif isinstance(node, list):
            for item in node:
                got = _walk_files(item)
                if got:
                    return got
        return None

    return _walk_files(actual)


def resolve_parse_channel(import_receipt_data: object, db: dict,
                          steps: list) -> tuple[str, str, str | None]:
    """解析通道裁决（Lead 2026-11-14 复验口径）——纯函数，可独立回归。

    证据源优先级（只认**本次实跑**的产物）：
      ① import_receipt_data（导入回执 data——files.parse_summary 等实际字段）；
      ② db 的 domain.files 解析摘要；
      ③ db 根 files 域。
    均无 → **unknown**（不冒充）。stderr 关键词（失败 probe 的 pdfium
    日志）只作 fallback 信号登记，**不采信为成功通道**。

    返回 (channel, source, fallback_signal)。
    """
    for label, ev in (("import_receipt", import_receipt_data),
                      ("db_files", (db.get("domain") or {}).get("files")),
                      ("db_root_files", db.get("files"))):
        got = channel_from(ev)
        if got:
            return got, label, None
    # 均无证据：stderr 信号只记 fallback（不进 channel 本值）
    chan_signal = "".join(s.get("stderr_tail", "") for s in (steps or []))
    fallback_signal = channel_from(chan_signal)
    return "unknown", ("stderr_signal(fallback-未采信)" if fallback_signal
                       else "no-evidence"), fallback_signal


# ---- 16 条金标准的检索键（run-notes.md §2/§3 的数值+单位与同义双锚）----
GR_KEYS = {
    "GR-001": ["295"],
    "GR-002": ["30M/s", "30M／s", "50M/s", "50M／s"],
    "GR-003": ["95%", "95％"],
    "GR-004": ["360"],
    "GR-005": ["15日历天", "15日历天调测"],
    "GR-006": ["双电源"],
    "GR-007": ["0.2dB", "0.2dB／", "0.2dB/"],
    "GR-008": ["服务地点"],
    "GR-009": ["验收要求"],
    "GR-010": ["17,000", "17000", "8,500", "8500"],
    "GR-011": ["20,000", "20000"],
    "GR-012": ["1,195,800", "1195800"],
    "GR-013": ["不缴纳", "无需缴纳"],
    "GR-014": ["90日", "90日历天", "九十日"],
    "GR-015": ["365", "1年", "一年"],
    "GR-016": ["不接受联合体", "不接受联合体投标", "联合体"],
}


def main() -> int:
    args = parse_args()
    ws = Path(args.ws)
    out = Path(args.out)
    bin_path = resolve_bin(args.bin)

    if not bin_path.exists():
        die(f"bid-mcp-stdio 不在位：{bin_path}（先 cargo build -p bid-mcp "
            "--bin bid-mcp-stdio；Windows 下自动补 .exe 已尝试）")
    if not PDF.exists():
        die(f"PDF 原件缺失：{PDF}")
    prepare_ws(ws)
    GR = load_gold()

    env = dict(os.environ, BID_WS=str(ws), BID_FS_ROOT=str(ROOT))
    steps = []  # (tool, ok, ms)

    # ---- 真实工具链三步（失败非零退出——不 assert 裸崩） ----
    r1 = call(bin_path, "create_bid_project", {
        "name": "复验#112", "bid_deadline": "2026-12-31", "mode": "明标",
        "external_key": "repro-112"}, env, steps)
    if not r1.get("ok"):
        die(f"create_bid_project 失败：{json.dumps(r1, ensure_ascii=False)[:400]}")
    pid = r1.get("project", {}).get("project_id") or "PRJ-0001"

    r2 = call(bin_path, "import_tender_files", {
        "project_id": pid,
        "files": [{"upload_ref": str(PDF), "filename": "光纤租赁费招标文件.pdf",
                   "kind": "招标文件", "expected_pages": 65}]}, env, steps)
    if not r2.get("ok"):
        die(f"import_tender_files 失败：{json.dumps(r2, ensure_ascii=False)[:400]}")

    r3 = call(bin_path, "extract_requirements", {"project_id": pid, "scope": "all"},
              env, steps)
    if not r3.get("ok"):
        die(f"extract_requirements 失败：{json.dumps(r3, ensure_ascii=False)[:400]}")

    # ---- db.json 读取与核验面（显式 UTF8） ----
    db_path = ws / "db.json"
    if not db_path.exists():
        die(f"工作区无 db.json（{db_path}）——抽取步未产出，链已断")
    with open(db_path, encoding="utf-8") as f:
        db = json.load(f)
    reqs = db["domain"]["requirements"]
    cats = dict(Counter(r["category"] for r in reqs))
    print(f"REQ 总数: {len(reqs)} | 七类分布: {json.dumps(cats, ensure_ascii=False)}")

    # REQ 检索面：锚摘录（归一后拼接）+ 条款号
    def req_haystack(r):
        parts = [a.get("excerpt", "") for a in r.get("anchors", [])]
        parts.append(r.get("clause_no") or "")
        return norm(" ".join(parts))

    hay = {r["id"]: req_haystack(r) for r in reqs}
    by_id = {r["id"]: r for r in reqs}

    # 16 条逐项召回
    gr_results = []
    for gr in GR:
        gid = gr["id"]
        keys = GR_KEYS.get(gid, [])
        hits = []
        for rid, h in hay.items():
            for k in keys:
                if norm(k) in h:
                    r = by_id[rid]
                    page = next((a.get("page") for a in r.get("anchors", []) if a.get("page")), None)
                    hits.append({"req": rid, "category": r["category"],
                                 "key": k, "page": page,
                                 "excerpt": next((a.get("excerpt", "") for a in r.get("anchors", [])
                                                  if norm(k) in norm(a.get("excerpt", ""))), "")[:120]})
        gr_results.append({
            "gr": gid, "statement": gr.get("statement", "")[:80],
            "expected_category": gr.get("category"),
            "hit": bool(hits), "hits": hits,
            "category_match": any(h["category"] == gr.get("category") for h in hits),
        })
    hit_n = sum(1 for g in gr_results if g["hit"])
    cat_match_n = sum(1 for g in gr_results if g["category_match"])
    print(f"16 条金标准召回: {hit_n}/16 | 其中分类与金标准一致: {cat_match_n}/16")

    # ★标记面
    star_reqs = [{"req": r["id"], "category": r["category"],
                  "excerpt": (r.get("anchors") or [{}])[0].get("excerpt", "")[:80]}
                 for r in reqs if (r.get("params") or {}).get("star")]
    star_anchor_hits = [
        {"req": r["id"], "category": r["category"],
         "excerpt": a.get("excerpt", "")[:100]}
        for r in reqs for a in r.get("anchors", [])
        if "★" in a.get("excerpt", "") or "☆" in a.get("excerpt", "")]
    print(f"★标记 REQ（params.star）: {len(star_reqs)} | 锚文含★字符: {len(star_anchor_hits)}")

    # 误分类抽样（其他/格式要求——确定性抽样：每类前 12 条 + 均匀步进 8 条）
    def sample(cat):
        items = [r for r in reqs if r["category"] == cat]
        n = len(items)
        if n == 0:
            return []
        idxs = sorted(set(list(range(min(12, n))) + list(range(0, n, max(1, n // 8)))[:8]))
        return [{"req": items[i]["id"],
                 "clause": items[i].get("clause_no"),
                 "anchors": [a.get("excerpt", "")[:90] for a in items[i].get("anchors", [])[:2]],
                 "pages": [a.get("page") for a in items[i].get("anchors", [])[:3]]}
                for i in idxs]

    # 解析通道识别（Lead 2026-11-14 复验口径）：resolve_parse_channel
    # 纯函数裁决——只认**本次实跑的导入回执 / db.json files 解析摘要**；
    # stderr 关键词搜索会把失败加载的 probe 日志误当成功通道——只作
    # fallback 信号登记，不采信。证据不明 → unknown（不冒充）。
    channel, channel_source, fallback_signal = resolve_parse_channel(
        r2.get("data"), db, steps)

    out_payload = {
        "repo_head": None,  # 由下补
        "tool": {"bin": str(bin_path), "sha256": sha256_of(bin_path)},
        "pdf_sha256": sha256_of(PDF),
        "pdf_bytes": os.path.getsize(PDF),
        "parse_channel_signal": channel,
        "parse_channel_source": channel_source,
        "parse_channel_fallback_signal": fallback_signal,
        "workspace": str(ws),
        "steps": steps,
        "req_total": len(reqs),
        "category_counts": cats,
        "gr_recall": {"hit": hit_n, "total": 16, "category_match": cat_match_n,
                      "items": gr_results},
        "star": {"params_star": star_reqs, "anchor_star": star_anchor_hits},
        "misclass_samples": {"其他": sample("其他"), "格式要求": sample("格式要求"),
                              "技术参数": sample("技术参数"), "商务要求": sample("商务要求")},
        # 口径警示（#156：防 16/16 被误读为语义保真）
        "caveats": [
            "16/16 检索/分类匹配 = 检索锚 OR 命中 + 分类一致——不等价于单位/上下限/完整语义保真（语义级核对归人工复核）",
            "67 条原始材料仍未取得（manifest MISSING 5 项）——召回面不得抵充材料面",
            (f"本次实跑解析通道证据：{channel}（来源 {channel_source}）；"
             "PR #146 的 Poppler 318REQ 是作者研究链口径——两通道不可互充基线"
             + ("；通道证据不明（unknown）——本次不宣称通道" if channel == "unknown" else "")),
        ],
    }
    # repo_head：git 在位则记（缺 git 不阻断——登记为 None）
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30)
        out_payload["repo_head"] = head.stdout.strip() if head.returncode == 0 else None
    except (subprocess.SubprocessError, OSError):
        out_payload["repo_head"] = None

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:  # 显式 UTF8
        json.dump(out_payload, f, ensure_ascii=False, indent=1)
    print(f"报告数据落盘: {out}")

    # 失败非零退出（#156）：召回缺 = 复验面失败——exit 1（完整报告已落盘）
    if hit_n < 16 or cat_match_n < 16:
        print(f"[repro-112] 召回 {hit_n}/16 / 分类 {cat_match_n}/16 —— 复验面失败（exit 1）",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
