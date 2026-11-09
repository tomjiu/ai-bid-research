#!/usr/bin/env python3
"""fp_sampling.py — P2 误报抽样分析（R3 遗留待办：'其他'类 REQ 输出质量）。

两层方法：
  1. 确定性噪声模式分类（全量 749 条'其他'，可复现）：目录行/纯编号行/章节标题/
     表格数据行/需求动词行——正则判据全部落档；
  2. 分层确定性抽样（seed=20261025）60 条供 AI 复核（与 GT 草案同诚实纪律：
     AI 初标，待人工验收）。

输出 artifacts/real-eval/fp-sampling.json；stdout 打印样本供逐条复核。
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVAL = REPO / "artifacts" / "real-eval"
REQ_SRC = EVAL / "extract" / "requirements.json"
GT_SRC = EVAL / "ground-truth-draft.json"
SEED = 20261025

# ---- 确定性噪声/需求判据（全部正则，可复现；抽样后校准 v2） ----
RE_TOC = re.compile(r"\.{4,}|…{2,}\s*\d+\s*$")           # 目录引导点+页码
RE_PURE_NUM = re.compile(r"^[\d\s.、,，:：()（）\-—/]+$")  # 纯编号/数字
RE_CHAPTER = re.compile(r"^(第[一二三四五六七八九十\d]+[章节]|[一二三四五六七八九十]+[、.．])\S{0,20}$")
RE_NUM_HEADING = re.compile(r"^\d+(\.\d+)*\s*\S{1,15}$")   # "15.7 计日工"型短标题
RE_TEMPLATE_BLANK = re.compile(r"[：:]\s*[，。;；\s]*$|为\s*[，,]\s*其余")  # 模板空填位
RE_TABLE_DATA = re.compile(r"^[\d\s.,，%‰℃±×/()（）\-—≈≥≤<>=]+%?$")
RE_CONTRACT = re.compile(r"承包人|发包人|监理人|争议评审|合同协议书")
RE_REQ_VERB = re.compile(r"须|应当|必须|不得|不应|严禁|应|承诺|具备|提供|提交|缴纳|交纳|持有|授权|委托|盖章|签字|响应|满足")


def classify_noise(excerpt: str) -> str:
    t = excerpt.strip()
    if not t:
        return "空行"
    if RE_TOC.search(t):
        return "目录行"
    if RE_PURE_NUM.fullmatch(t):
        return "纯编号/数字行"
    if RE_CHAPTER.match(t) or RE_NUM_HEADING.match(t):
        return "章节标题行"
    if RE_TEMPLATE_BLANK.search(t):
        return "模板空填行"
    if RE_TABLE_DATA.fullmatch(t):
        return "表格数据行"
    if RE_CONTRACT.search(t):
        return "合同条款面（承包人/发包人义务——中标后合同正文）"
    if RE_REQ_VERB.search(t):
        return "含需求动词（候选需求）"
    return "正文叙述行"


def norm_n2(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKC", s) if c.isalnum())


def strip_leading_no(text: str) -> str:
    return re.sub(r"^[\d.、（）()\s]+", "", text).strip()


def gt_matched(rc_full: str, gt_cores: list[str]) -> bool:
    """与 real_eval_score 同源对齐：剥前导编号后互含（rc 取剥号后 ≥8 字符核心）。"""
    rc = norm_n2(strip_leading_no(rc_full))
    if len(rc) < 8:
        return False
    return any(g and (g[:24] in rc or rc[:24] in g) for g in gt_cores)


def main() -> int:
    reqs = json.load(open(REQ_SRC, encoding="utf-8"))
    r04 = [r for r in reqs if r["source_file"] == "A-某水利施工标段招标文件.pdf"]
    others = [r for r in r04 if r["category"] == "其他"]
    gts = json.load(open(GT_SRC, encoding="utf-8"))["items"]
    gt_cores = [norm_n2(strip_leading_no(g["excerpt"])) for g in gts]

    # 1) 全量确定性分类
    det = Counter()
    det_detail = {}
    for r in others:
        k = classify_noise(r["anchors"][0]["excerpt"])
        det[k] += 1
        det_detail.setdefault(k, []).append(r["id"])
    print(f"'其他'类全量确定性分类（n={len(others)}，判据正则落档）：")
    for k, v in det.most_common():
        print(f"  {k}: {v}（{v/len(others):.1%}）")

    # 2) 分层抽样：噪声类各抽 5 + 需求动词类抽 25 + 正文叙述抽 15
    rng = random.Random(SEED)
    sample = []
    for k, ids in det_detail.items():
        n = 25 if "需求动词" in k else (15 if k == "正文叙述行" else 5)
        sample += rng.sample(ids, min(n, len(ids)))
    sample = sorted(set(sample))
    by_id = {r["id"]: r for r in others}
    print(f"\n分层样本 {len(sample)} 条（seed={SEED}，确定性可复现）：")
    print("（复核协议：噪声=目录/标题/表格数据/纯编号；边缘=程序性说明；"
          "需求=对投标人设定义务/条件——若 GT 未含则同时暴露 GT 覆盖缺口）\n")
    for i, rid in enumerate(sample, 1):
        r = by_id[rid]
        a = r["anchors"][0]
        print(f"[{i:02d}] {rid} {r['clause_no'] or '—'} {a['locator']}"
              f" [{classify_noise(a['excerpt'])}]")
        print(f"     {a['excerpt'][:80]}")

    # 3) 需求动词类中 GT 已覆盖比例（对齐口径与 real_eval_score 同源：剥号互含）
    cand = det_detail.get("含需求动词（候选需求）", [])
    cov = sum(1 for rid in cand if gt_matched(by_id[rid]["anchors"][0]["excerpt"], gt_cores))
    print(f"\n需求动词候选 {len(cand)} 条：与 GT 草案剥号互含重叠 {cov} 条"
          f"（{cov/max(1,len(cand)):.1%}）——未重叠部分为 GT 覆盖缺口候选（非误报；"
          f"含错类真需求如 1.4.1 资质条款落'其他'）")

    out = {
        "eval": "P2-false-positive-sampling",
        "status": "AI 初标（确定性分类 + 分层样本 AI 复核，待人工验收）",
        "file": "A-某水利施工标段招标文件.pdf",
        "others_total": len(others),
        "deterministic_breakdown": dict(det.most_common()),
        "sample_seed": SEED,
        "sample_ids": sample,
        "req_verb_candidates": len(cand),
        "req_verb_gt_overlap": cov,
        "criteria": {
            "目录行": r"\.{4,}|…{2,}\s*\d+\s*$",
            "纯编号/数字行": r"^[\d\s.、,，:：()（）\-—/]+$",
            "章节标题行": r"^(第[一二三四五六七八九十\d]+[章节]|[一二三四五六七八九十]+[、.．])\S{0,20}$",
            "表格数据行": r"^[\d\s.,，%‰℃±×/()（）\-—≈≥≤<>=]+%?$",
            "需求动词": r"须|应当|必须|不得|不应|严禁|应|承诺|具备|提供|提交|缴纳|交纳|持有|授权|委托|盖章|签字|响应|满足",
        },
    }
    (EVAL / "fp-sampling.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n落档 {EVAL / 'fp-sampling.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
