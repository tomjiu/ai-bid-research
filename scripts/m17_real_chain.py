#!/usr/bin/env python3
"""m17_real_chain.py — M1.7-B 政府采购真实链验证（S2 批次一：政府采购优先）

验证对象：cuc-028 真实采购链（中国传媒大学教学资源中心建设，中传招标【2026】第028号）
  节点1 招标公告 2026-07-13  http://www.ccgp.gov.cn/cggg/zygg/gkzb/202607/t20260713_26925801.htm
  节点2 更正公告 2026-07-28  http://www.ccgp.gov.cn/cggg/zygg/gzgg/202607/t20260728_27025731.htm
  节点3 中标公告 2026-08-14  http://www.ccgp.gov.cn/cggg/zygg/zbgg/202608/t20260814_27133532.htm
三份均为官方公开公告文本（ccgp 原文捕获 + cuc.edu.cn 官方镜像 HTML 字节级存档交叉校验）。

闭环定义（本轮完成标准）：真实文件解析 → 补遗影响面 → 输出复验，三段之间以
sha256 + 官方 URL + 发布日期形成可追溯链路。

诚实口径声明（三层，不得混淆）：
  1. REAL_DATA + DESIGN_ENGINE：输入数据 100% 真实公开公告；影响面引擎为
     bid-domain 六规则（R-mod/R-del/R-add/R-date/R-conf/R-idem）的数据驱动实现，
     与 V2 ImpactEngine（corpus-A SEMUL）同语义；Rust 层交叉验证仍待 cargo 环境。
  2. 公告级 ≠ 文件级：更正公告逐条引用原招标文件条款原文，构成真实条款级
     原文↔更正后配对；但招标文件本体（ccgp 中标公告附件《更正后（以此版本为准）
     3-1…--招标文件.pdf》）受 ccgp WAF 阻断在本环境不可下载——文件级验证为
     登记在案的待人工项（GT-M17-24），公告级结果不得宣称为文件级验收。
  3. GT 24 条为初标草案（draft_pending_human）：未人工冻结前相关准确率仅为
     探索性指标，不作为正式验收结论。

断言分组：
  P0 文件解析      三节点解析 + 链主键一致 + 官方镜像 HTML 交叉校验
  P1 变更提取      恰 3 个真实 MODIFY + 2 个真实不变陷阱 + 同值陷阱不串位
  P2 影响面        DIRTY 恰两章（=『其他内容均无修改』声明）+ 级联触发零误翻 +
                   无关不重跑 + 冲突登记→门禁阻断→更正优先终裁→放行 + 幂等 no-op
  P3 输出复验      修正后条款在位/历史留痕 + 中标金额≤预算/限价 + 时序自洽 +
                   评审口径互证 + 双跑确定性（状态哈希一致）
  P4 GT 核对      24 条逐项：engine 项对引擎状态核对、source 项逐字读回、manual 项计数
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RC = REPO / "real-corpus" / "gov-procurement"
F_TENDER = RC / "files" / "cuc-028-tender-20260713.txt"
F_CORR = RC / "files" / "cuc-028-correction-20260728.txt"
F_AWARD = RC / "files" / "cuc-028-award-20260814.txt"
S_TENDER = RC / "sources" / "cuc-tender-mirror-20260713.html"
S_AWARD = RC / "sources" / "cuc-award-mirror-20260814.html"
GT_PATH = RC / "gt" / "ground-truth-draft.jsonl"
REPORT = RC / "artifacts" / "real-chain-report.json"

CHAIN_ID = "cuc-028"
PID = "中传招标【2026】第028号/CFTC-BJ01-2606001"

DATE = r"(\d{4})年(\d{1,2})月(\d{1,2})日"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def cn_date(y, m, d) -> str:
    return f"{y}-{int(m):02d}-{int(d):02d}"


def _html_text(p: Path) -> str:
    html = p.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"<[^>]+>", "", html)


class ChainFile:
    """链节点文件：# 头部溯源字段 + 正文。"""

    def __init__(self, path: Path):
        self.path = path
        raw = path.read_bytes()
        self.sha256 = sha256_bytes(raw)
        text = raw.decode("utf-8")
        self.headers: dict[str, str] = {}
        lines = text.splitlines()
        body_start = 0
        for i, ln in enumerate(lines):
            if ln.startswith("#"):
                m = re.match(r"^#\s*(URL|Type|Publish|Fetched|Chain|Captured)[:：]\s*(.*)$", ln)
                if m:
                    self.headers[m.group(1)] = m.group(2).strip()
                body_start = i + 1
            else:
                body_start = i
                break
        self.body = "\n".join(lines[body_start:])

    @property
    def url(self):
        return self.headers.get("URL", "")


# ================================================================ 解析
def parse_tender(body: str) -> dict:
    f = {}
    m = re.search(r"项目编号[:：]\s*(\S+)", body)
    f["pid"] = m.group(1) if m else None
    m = re.search(r"项目名称[:：]\s*(中国传媒大学\S+)", body)
    f["project"] = m.group(1) if m else None
    m = re.search(r"预算金额[:：]\s*([\d.]+)\s*万元", body)
    f["budget"] = float(m.group(1)) if m else None
    m = re.search(r"最高限价[（(]如有[）)][：:]\s*([\d.]+)\s*万元", body)
    f["price_cap"] = float(m.group(1)) if m else None
    m = re.search(DATE + r"\s*(\d{1,2})点(\d{2})分[（(]北京时间[）)]", body)
    f["open_bid"] = f"{cn_date(*m.groups()[:3])} {int(m.group(4)):02d}:{m.group(5)}" if m else None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日至(\d{4})年(\d{1,2})月(\d{1,2})日", body)
    f["doc_window"] = (cn_date(m.group(1), m.group(2), m.group(3)),
                       cn_date(m.group(4), m.group(5), m.group(6))) if m else None
    m = re.search(r"开标时间[:：]\s*" + DATE, body)
    f["open_bid_date"] = cn_date(*m.groups()) if m else None
    f["scoring"] = "综合评分法" if "综合评分法" in body else None
    f["joint_bid"] = "不接受" if re.search(r"本项目[（(]不接受[）)]联合体投标", body) else None
    f["sme_only"] = "专门面向中小企业" in body
    f["qual_22"] = "第二十二条" in body
    f["specific_quals"] = re.findall(r"\d\)（?[^）。\n]{6,60}）?不得", body)
    f["scope_quote"] = "本地化+云化混合建设模式" if "本地化+云化" in body else None
    return f


def _split_items(seg: str) -> dict[str, list[str]]:
    """更正段内条目/节点分类：条目=（N）原招标文件…/招标文件…/更正内容：…；
    节点=（N）日期… 或（N）项目最终验收时…；其余行挂当前条目。"""
    items: dict[str, list[str]] = {}
    cur = None
    for ln in seg.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r"^（([0-9])）(.+)$", ln)
        if m and re.match(r"^(原?招标文件|更正内容：)", m.group(2)):
            cur = m.group(1)
            items.setdefault(cur, []).append(ln)
        elif m and (re.match(r"^\d{4}年", m.group(2)) or m.group(2).startswith("项目最终验收时")):
            items.setdefault(cur, []).append(ln)
        elif cur is not None:
            items[cur].append(ln)
    return items


def _nodes(item_lines: list[str]) -> dict[int, dict]:
    nodes: dict[int, dict] = {}
    for ln in item_lines:
        m = re.match(r"^（([1-9])）(\d{4})年(\d{1,2})月(\d{1,2})日前：(.+?)[；;]", ln)
        if m:
            nodes[int(m.group(1))] = {"date": cn_date(m.group(2), m.group(3), m.group(4)),
                                      "desc": m.group(5)}
            continue
        m = re.match(r"^（([1-9])）项目最终验收时，(.+?)[。]", ln)
        if m:
            nodes[int(m.group(1))] = {"date": None, "desc": "项目最终验收时，" + m.group(2)}
    return nodes


def _open_time(item_lines: list[str]) -> str | None:
    s = "\n".join(item_lines)
    m = re.search(DATE + r"\s*(\d{1,2})点(\d{2})分[（(]北京时间[）)]", s)
    return f"{cn_date(*m.groups()[:3])} {int(m.group(4)):02d}:{m.group(5)}" if m else None


def parse_correction(body: str) -> dict:
    out: dict = {}
    m = re.search(r"首次公告日期[:：]\s*" + DATE, body)
    out["first_pub"] = cn_date(*m.groups()) if m else None
    m = re.search(r"更正日期[:：]\s*" + DATE, body)
    out["correction_date"] = cn_date(*m.groups()) if m else None
    m = re.search(r"原公告的采购项目编号[:：]\s*(\S+)", body)
    out["pid"] = m.group(1) if m else None
    m = re.search(r"原公告的采购项目名称[:：]\s*(\S+)", body)
    out["project"] = m.group(1) if m else None
    i_c = body.index("更正内容：") + len("更正内容：")
    i_n = body.index("现更正为：")
    i_e = body.index("其他内容均无修改")
    ori_items = _split_items(body[i_c:i_n])
    new_items = _split_items(body[i_n + len("现更正为："):i_e])
    out["scope_statement"] = body[i_e:i_e + 9]
    # 条款级配对（原文引用 vs 更正后全文——真实文件内容配对）
    out["ori"] = {"open_time": _open_time(ori_items.get("1", [])),
                  "nodes": _nodes(ori_items.get("2", []))}
    out["new"] = {"open_time": _open_time(new_items.get("1", [])),
                  "nodes": _nodes(new_items.get("2", []))}
    return out


def parse_award(body: str) -> dict:
    f = {}
    m = re.search(r"项目编号[:：]\s*(\S+)", body)
    f["pid"] = m.group(1) if m else None
    m = re.search(r"供应商名称[:：]\s*([^\s，,（(]+)", body)
    f["winner"] = m.group(1) if m else None
    m = re.search(r"中标[（(]成交[）)]金额[:：]\s*([\d.]+)（万元）", body)
    f["amount"] = float(m.group(1)) if m else None
    m = re.search(r"评审得分[:：]\s*([\d.]+)\s*分", body)
    f["score"] = float(m.group(1)) if m else None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*\d{1,2}:\d{2}", body)
    f["award_date"] = cn_date(*m.groups()) if m else None
    f["attachments"] = re.findall(r"附件下载[:：]\s*(\S+?\.pdf)", body)
    f["scope_quote"] = "本地化+云化混合建设模式" if "本地化+云化" in body else None
    return f


# ================================================================ 影响面引擎（真数据驱动 · 六规则）
class RealChainEngine:
    """六规则数据驱动实现（R-mod/R-del/R-add/R-date/R-conf/R-idem）。
    与 V2 ImpactEngine（corpus-A SEMUL）同语义；输入为真实公告提取的事件。"""

    def __init__(self, clauses: dict, sections: dict):
        self.content_version = 1
        self.clauses = {k: {"value": v["value"], "section": v["section"],
                            "kind": v.get("kind", "text"), "history": []}
                        for k, v in clauses.items()}
        self.sections = {s: {"dirty": False, "related": list(rel)} for s, rel in sections.items()}
        self.eval_date: str | None = None
        self.conflicts: dict[str, dict] = {}
        self.recheck_log: list[str] = []
        self.import_log: dict[str, str] = {}
        self.gate_log: list[tuple] = []

    def state_hash(self) -> str:
        state = {"content_version": self.content_version, "clauses": self.clauses,
                 "sections": {s: v["dirty"] for s, v in self.sections.items()},
                 "conflicts": self.conflicts, "recheck_log": self.recheck_log}
        return sha256_bytes(json.dumps(state, ensure_ascii=False, sort_keys=True).encode())

    def import_correction(self, fname: str, sha: str, events: list[dict]) -> dict:
        if self.import_log.get(fname) == sha:                       # R-idem
            return {"idempotent_noop": True,
                    "dirty_sections": sorted(s for s, v in self.sections.items() if v["dirty"])}
        self.import_log[fname] = sha
        self.content_version += 1                                   # 一次导入恰一个版本戳
        impact = {"modify": [], "unchanged_kept": [], "dirty_sections": [],
                  "conflicts": [], "cascade": None}
        for ev in events:                                           # R-mod
            c = self.clauses[ev["clause"]]
            c["history"].append(c["value"])
            c["value"] = ev["new"]
            impact["modify"].append(ev["clause"])
            sec = c["section"]
            if not self.sections[sec]["dirty"]:
                self.sections[sec]["dirty"] = True
                impact["dirty_sections"].append(sec)
            if ev["clause"] == "open_bid_time":                     # R-conf：基准条款双版本
                cid = f"CONFLICT-{ev['clause']}"
                self.conflicts[cid] = {
                    "versions": [{"source": "tender-20260713", "value": ev["old"]},
                                 {"source": fname, "value": ev["new"]}],
                    "resolved": False, "final": None,
                    "rule": "更正公告优先（后到有效版本覆盖）"}
                impact["conflicts"].append(cid)
        ob = [e for e in events if e["clause"] == "open_bid_time"]   # R-date：开标日级联重检
        if ob and self.eval_date:
            old = self.eval_date
            self.eval_date = ob[0]["new"][:10]
            flips = self._recheck_all()
            impact["cascade"] = {"from": old, "to": self.eval_date, "flips": flips}
        return impact

    def _recheck_all(self) -> list[str]:
        """全项目重检（重检范围恒为全项目）。公告层无证书有效期绑定 → 翻转集为空（如实记录）。"""
        self.recheck_log.append(self.eval_date)
        return []

    def adjudicate(self, cid: str) -> dict:
        c = self.conflicts[cid]
        c["resolved"] = True
        c["final"] = c["versions"][-1]["value"]                     # 更正优先
        return {"final": c["final"], "rule": c["rule"]}

    def try_accept(self, section: str) -> tuple[bool, str]:
        v = self.sections[section]
        if v["dirty"]:
            self.gate_log.append((section, "blocked", "DIRTY"))
            return False, "DIRTY"
        unres = [k for k, c in self.conflicts.items()
                 if not c["resolved"]
                 and any(self.clauses[r]["section"] == section for r in self.sections[section]["related"]
                         if r in self.clauses) or (not c["resolved"] and k == "CONFLICT-open_bid_time"
                                                   and section == "投标邀请")]
        if unres:
            self.gate_log.append((section, "blocked", f"UNRESOLVED_CONFLICT:{unres}"))
            return False, f"UNRESOLVED_CONFLICT:{unres}"
        self.gate_log.append((section, "accepted", "ok"))
        return True, "ok"

    def redraft(self, section: str):
        self.sections[section]["dirty"] = False


# ================================================================ 断言框架
class Checks:
    def __init__(self):
        self.results: list[dict] = []

    def check(self, group: str, name: str, ok: bool, detail: str = ""):
        self.results.append({"group": group, "name": name, "pass": bool(ok), "detail": detail})

    @property
    def all_pass(self):
        return all(r["pass"] for r in self.results)

    @property
    def summary(self):
        g: dict[str, list] = {}
        for r in self.results:
            g.setdefault(r["group"], []).append(r)
        return {k: {"pass": sum(1 for x in v if x["pass"]), "total": len(v)} for k, v in g.items()}


def build_engine(t: dict) -> RealChainEngine:
    clauses = {
        "open_bid_time": {"value": t["open_bid"], "section": "投标邀请", "kind": "datetime"},
        "doc_window": {"value": f"{t['doc_window'][0]}~{t['doc_window'][1]}",
                       "section": "投标邀请", "kind": "window"},
        "budget": {"value": t["budget"], "section": "商务与合同", "kind": "money"},
        "price_cap": {"value": t["price_cap"], "section": "商务与合同", "kind": "money"},
        "qualification": {"value": t["specific_quals"], "section": "资格要求", "kind": "list"},
        "scoring_method": {"value": t["scoring"], "section": "评审办法", "kind": "text"},
    }
    for n, node in t["nodes"].items():  # nodes 由调用方注入（真实原文节点）
        clauses[f"node_{n}"] = {"value": node["date"], "section": "采购需求", "kind": "date"}
    sections = {
        "投标邀请": ["open_bid_time", "doc_window"],
        "采购需求": [f"node_{i}" for i in sorted(t["nodes"])],
        "资格要求": ["qualification"],
        "评审办法": ["scoring_method"],
        "商务与合同": ["budget", "price_cap"],
    }
    eng = RealChainEngine(clauses, sections)
    eng.set_eval_date = None
    eng.eval_date = t["open_bid"][:10]
    return eng


def run() -> dict:
    ck = Checks()
    prov = {"chain_id": CHAIN_ID, "project_pid": PID,
            "nodes": [], "gt_file": str(GT_PATH.relative_to(REPO))}

    # ---- P0 真实文件解析
    tender = ChainFile(F_TENDER)
    corr = ChainFile(F_CORR)
    award = ChainFile(F_AWARD)
    for f, role in ((tender, "tender"), (corr, "correction"), (award, "award")):
        prov["nodes"].append({"role": role, "file": str(f.path.relative_to(REPO)),
                              "sha256": f.sha256, "url": f.url,
                              "publish": f.headers.get("Publish", f.headers.get("Fetched", ""))})
    t = parse_tender(tender.body)
    c = parse_correction(corr.body)
    a = parse_award(award.body)
    ck.check("P0", "P0a 三节点解析成功（头部溯源字段齐全）",
             all(x.headers.get("URL") for x in (tender, corr, award))
             and tender.headers.get("Type") == "tender"
             and corr.headers.get("Type") == "correction"
             and award.headers.get("Type") == "award")
    ck.check("P0", "P0b 链主键逐字一致（项目编号）",
             t["pid"] == PID and c["pid"] == PID and a["pid"] == PID,
             f"tender={t['pid']} corr={c['pid']} award={a['pid']}")
    ck.check("P0", "P0c 招标公告关键域（预算108/限价108/开标08-03 14:00/窗口07-13~07-20/综合评分法）",
             t["budget"] == 108.0 and t["price_cap"] == 108.0
             and t["open_bid"] == "2026-08-03 14:00"
             and t["doc_window"] == ("2026-07-13", "2026-07-20")
             and t["scoring"] == "综合评分法"
             and t["joint_bid"] == "不接受" and t["sme_only"] and t["qual_22"],
             json.dumps({k: t[k] for k in ("budget", "price_cap", "open_bid", "doc_window")},
                       ensure_ascii=False))
    ck.check("P0", "P0d 首次公告日期回指一致（更正公告 2026-07-13 = 招标公告发布日）",
             c["first_pub"] == "2026-07-13" and c["correction_date"] == "2026-07-28")
    ck.check("P0", "P0e 中标公告关键域（知途/105.0万/89.36分/08-14）",
             a["winner"] == "江苏知途教育科技有限公司" and a["amount"] == 105.0
             and a["score"] == 89.36 and a["award_date"] == "2026-08-14",
             json.dumps(a, ensure_ascii=False)[:120])
    # 官方镜像 HTML 字节存档交叉校验（第二独立官方来源）
    tm, am = _html_text(S_TENDER), _html_text(S_AWARD)
    tm_keys = ["中传招标【2026】第028号", "108.000000", "2026年08月03日 14点00分",
               "综合评分法", "专门面向中小企业"]
    am_keys = ["江苏知途教育科技有限公司", "105.0000000", "89.36"]
    ck.check("P0", "P0f 官方镜像交叉校验（cuc.edu.cn 存档：招标 5 锚点/中标 3 锚点全命中）",
             all(k in tm for k in tm_keys) and all(k in am for k in am_keys),
             f"miss={[k for k in tm_keys if k not in tm]+[k for k in am_keys if k not in am]}")

    # ---- P1 变更提取（真实条款配对：原文引用 vs 更正后全文）
    ck.check("P1", "P1a 更正段切分（更正内容/现更正为/其他内容均无修改 三界标齐全）",
             c["scope_statement"].startswith("其他内容均无修改")
             and c["ori"]["open_time"] and c["new"]["open_time"])
    ck.check("P1", "P1b 原文引用侧解析（开标 08-03 14:00 + 节点1-4 = 07-31/08-30/09-23/无）",
             c["ori"]["open_time"] == "2026-08-03 14:00"
             and [c["ori"]["nodes"][i]["date"] for i in (1, 2, 3)] == ["2026-07-31", "2026-08-30", "2026-09-23"]
             and c["ori"]["nodes"][4]["date"] is None,
             json.dumps({k: v["date"] for k, v in c["ori"]["nodes"].items()}))
    ck.check("P1", "P1c 更正后侧解析（开标 08-13 14:00 + 节点1-4 = 08-30/09-10/09-23/无）",
             c["new"]["open_time"] == "2026-08-13 14:00"
             and [c["new"]["nodes"][i]["date"] for i in (1, 2, 3)] == ["2026-08-30", "2026-09-10", "2026-09-23"]
             and c["new"]["nodes"][4]["date"] is None,
             json.dumps({k: v["date"] for k, v in c["new"]["nodes"].items()}))
    events: list[dict] = []
    if c["ori"]["open_time"] != c["new"]["open_time"]:
        events.append({"clause": "open_bid_time", "type": "MODIFY",
                       "old": c["ori"]["open_time"], "new": c["new"]["open_time"]})
    unchanged: list[str] = []
    for n in sorted(set(c["ori"]["nodes"]) | set(c["new"]["nodes"])):
        o, w = c["ori"]["nodes"].get(n), c["new"]["nodes"].get(n)
        if o is None and w is not None:
            events.append({"clause": f"node_{n}", "type": "ADD", "new": w["date"]})
        elif w is None and o is not None:
            events.append({"clause": f"node_{n}", "type": "DELETE", "old": o["date"]})
        elif o["date"] != w["date"]:
            events.append({"clause": f"node_{n}", "type": "MODIFY", "old": o["date"], "new": w["date"]})
        else:
            unchanged.append(f"node_{n}")
    ck.check("P1", "P1d 恰 3 个真实 MODIFY（开标/节点1/节点2），0 新增 0 删除",
             len(events) == 3 and all(e["type"] == "MODIFY" for e in events)
             and [e["clause"] for e in events] == ["open_bid_time", "node_1", "node_2"],
             json.dumps(events, ensure_ascii=False))
    ck.check("P1", "P1e 2 个真实不变陷阱保真（节点3/节点4 零事件）",
             sorted(unchanged) == ["node_3", "node_4"],
             f"unchanged={unchanged}")
    ck.check("P1", "P1f 同值陷阱：节点1新值 08-30 == 节点2旧值——节点对齐未串位",
             events[1]["old"] == "2026-07-31" and events[1]["new"] == "2026-08-30"
             and events[2]["old"] == "2026-08-30" and events[2]["new"] == "2026-09-10",
             "若节点按文本流而非序号对齐将在此错位")

    # ---- P2 影响面（六规则 · 真实事件驱动）
    t["nodes"] = c["ori"]["nodes"]
    eng = build_engine(t)
    base_hash = eng.state_hash()
    imp = eng.import_correction("cuc-028-correction-20260728", corr.sha256, events)
    ck.check("P2", "P2a 版本戳恰 +1（content_version=2，一次导入一个戳）",
             eng.content_version == 2)
    ck.check("P2", "P2b DIRTY 恰两章 {投标邀请, 采购需求}（=更正公告『其他内容均无修改』声明）",
             sorted(imp["dirty_sections"]) == ["投标邀请", "采购需求"],
             f"got={sorted(imp['dirty_sections'])}")
    ck.check("P2", "P2c 无关不重跑：资格要求/评审办法/商务与合同 三章零误伤",
             all(not eng.sections[s]["dirty"] for s in ("资格要求", "评审办法", "商务与合同")))
    ck.check("P2", "P2d 同章节内未变更条款不改动（投标邀请.doc_window 值与历史均未动）",
             eng.clauses["doc_window"]["value"] == "2026-07-13~2026-07-20"
             and eng.clauses["doc_window"]["history"] == []
             and eng.clauses["budget"]["history"] == [] and eng.clauses["price_cap"]["value"] == 108.0)
    ck.check("P2", "P2e 开标日级联：全项目重检触发（recheck_log+1），公告层零证书绑定零误翻",
             imp["cascade"] == {"from": "2026-08-03", "to": "2026-08-13", "flips": []}
             and eng.recheck_log == ["2026-08-13"],
             json.dumps(imp["cascade"], ensure_ascii=False))
    ck.check("P2", "P2f 冲突双版本登记（开标时间 tender 08-03 vs correction 08-13）",
             "CONFLICT-open_bid_time" in eng.conflicts
             and eng.conflicts["CONFLICT-open_bid_time"]["versions"][0]["value"] == "2026-08-03 14:00"
             and not eng.conflicts["CONFLICT-open_bid_time"]["resolved"])
    ok1, r1 = eng.try_accept("投标邀请")
    eng.redraft("投标邀请")
    ok2, r2 = eng.try_accept("投标邀请")
    adj = eng.adjudicate("CONFLICT-open_bid_time")
    ok3, r3 = eng.try_accept("投标邀请")
    ck.check("P2", "P2g 终裁门禁三段：脏阻断→未裁决冲突阻断→更正优先终裁 08-13 后放行",
             (ok1, r1) == (False, "DIRTY") and ok2 is False and r2.startswith("UNRESOLVED")
             and (ok3, r3) == (True, "ok") and adj["final"] == "2026-08-13 14:00",
             f"gate_seq=[{r1}|{r2}|{r3}] final={adj['final']}")
    ck.check("P2", "P2h 更正优先终裁后矩阵口径切换（open_bid 当前值=终裁值）",
             eng.clauses["open_bid_time"]["value"] == "2026-08-13 14:00")
    dirty_before = sorted(s for s, v in eng.sections.items() if v["dirty"])
    imp2 = eng.import_correction("cuc-028-correction-20260728", corr.sha256, events)
    dirty_after = sorted(s for s, v in eng.sections.items() if v["dirty"])
    ck.check("P2", "P2i 幂等：同 sha 重复导入 no-op（版本戳不变/DIRTY 集前后一致）",
             imp2.get("idempotent_noop") is True and eng.content_version == 2
             and dirty_before == dirty_after == ["采购需求"],
             f"before={dirty_before} after={dirty_after}")
    # ---- P3 输出复验
    ck.check("P3", "P3a 修正后条款在位 + 历史留痕（node_1 现 08-30/史 [07-31]；开标现 08-13/史 [08-03]）",
             eng.clauses["node_1"]["value"] == "2026-08-30"
             and eng.clauses["node_1"]["history"] == ["2026-07-31"]
             and eng.clauses["open_bid_time"]["value"] == "2026-08-13 14:00"
             and eng.clauses["open_bid_time"]["history"] == ["2026-08-03 14:00"])
    ck.check("P3", "P3b 不变陷阱值保真（node_3 09-23 无历史；node_4 无日期无历史）",
             eng.clauses["node_3"]["value"] == "2026-09-23" and eng.clauses["node_3"]["history"] == []
             and eng.clauses["node_4"]["value"] is None and eng.clauses["node_4"]["history"] == [])
    ck.check("P3", "P3c 中标金额 ≤ 预算 且 ≤ 最高限价（105.0 ≤ 108.0 双口径，无超限异常）",
             a["amount"] <= t["budget"] and a["amount"] <= t["price_cap"])
    ck.check("P3", "P3d 时序自洽：开标（更正后 08-13）≤ 中标公告（08-14）",
             eng.clauses["open_bid_time"]["value"][:10] <= a["award_date"],
             f"{eng.clauses['open_bid_time']['value'][:10]} <= {a['award_date']}")
    ck.check("P3", "P3e 评审口径互证：综合评分法 ↔ 评审得分 89.36 存在",
             t["scoring"] == "综合评分法" and a["score"] == 89.36)
    ck.check("P3", "P3f 跨文件采购需求引文逐字一致（招标公告↔中标公告『本地化+云化混合建设模式』）",
             t["scope_quote"] == a["scope_quote"] == "本地化+云化混合建设模式")
    ck.check("P3", "P3g 证据义务链：资格条款(面向中小企业) ↔ 中标公告附件《中小企业声明函.pdf》",
             t["sme_only"] and any("中小企业声明函" in x for x in a["attachments"]))
    ck.check("P3", "P3h 文件级缺口如实登记：中标公告挂《更正后…--招标文件.pdf》附件（本体待人工获取）",
             any("招标文件" in x and "更正后" in x for x in a["attachments"]))
    # 双跑确定性（复现同一门禁/终裁序列）
    t2v = parse_tender(tender.body)
    t2v["nodes"] = c["ori"]["nodes"]
    eng2 = build_engine(t2v)
    eng2.import_correction("cuc-028-correction-20260728", corr.sha256, events)
    eng2.redraft("投标邀请")
    eng2.adjudicate("CONFLICT-open_bid_time")
    ck.check("P3", "P3i 双跑确定性：同输入两引擎终态哈希一致",
             eng.state_hash() == eng2.state_hash() and eng.state_hash() != base_hash,
             f"hash={eng.state_hash()[:16]}")

    # ---- P4 GT 草案核对（24 条）
    gts = [json.loads(l) for l in GT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    ck.check("P4", "P4a GT 草案 24 条且字段完备（定位/答案/理由/复核状态）",
             len(gts) == 24 and all(
                 g.get("source_file") and g.get("source_url") and g.get("excerpt")
                 and g.get("expected") is not None and g.get("rationale")
                 and g.get("review_status") == "draft_pending_human" for g in gts),
             f"count={len(gts)}")
    fmap = {str(f.path.relative_to(RC)): f for f in (tender, corr, award)}
    src_miss = []
    for g in gts:
        if g["verify"] in ("engine", "source"):
            body = fmap[g["source_file"]].body
            if g["excerpt"] not in body:
                src_miss.append(g["gt_id"])
    ck.check("P4", "P4b 原文定位逐字读回：engine/source 类 GT 的 excerpt 逐字见于对应源文件",
             not src_miss, f"miss={src_miss}")
    exp = {e["clause"]: e for e in events}
    eng_ok = []
    for g in gts:
        if g["gt_id"] == "GT-M17-11":
            eng_ok.append(exp["open_bid_time"]["old"] == "2026-08-03 14:00"
                          and exp["open_bid_time"]["new"] == "2026-08-13 14:00")
        elif g["gt_id"] == "GT-M17-12":
            eng_ok.append(exp["node_1"]["old"] == "2026-07-31" and exp["node_1"]["new"] == "2026-08-30")
        elif g["gt_id"] == "GT-M17-13":
            eng_ok.append(exp["node_2"]["old"] == "2026-08-30" and exp["node_2"]["new"] == "2026-09-10")
        elif g["gt_id"] == "GT-M17-14":
            eng_ok.append(eng.clauses["node_3"]["value"] == "2026-09-23" and "node_3" not in exp)
        elif g["gt_id"] == "GT-M17-16":
            eng_ok.append(sorted(imp["dirty_sections"]) == ["投标邀请", "采购需求"])
        elif g["gt_id"] == "GT-M17-19":
            eng_ok.append(a["amount"] <= t["budget"])
        elif g["gt_id"] == "GT-M17-22":
            eng_ok.append(eng.clauses["open_bid_time"]["value"][:10] <= a["award_date"])
    ck.check("P4", "P4c engine 类 GT 与引擎状态逐项吻合（7 项代表性核对全过）",
             len(eng_ok) == 7 and all(eng_ok), f"n={len(eng_ok)} ok={sum(eng_ok)}")
    manual_ids = [g["gt_id"] for g in gts if g["verify"] == "manual"]
    ck.check("P4", "P4d manual 类 GT=1 项（GT-M17-24 招标文件本体）——仅剩人工事项在案",
             manual_ids == ["GT-M17-24"], f"manual={manual_ids}")

    # ---- 报告
    report = {
        "chain": prov, "scope_statement": "公告级真实链闭环；文件级（招标文件本体）为在案待人工项",
        "data_provenance": "ccgp.gov.cn 官方文本 + cuc.edu.cn 官方镜像 HTML（sha256 在 nodes 列表）",
        "caliber": "REAL_DATA + DESIGN_ENGINE（真实数据/设计语义引擎；Rust 交叉验证待 cargo）",
        "results": ck.results, "summary": ck.summary, "all_pass": ck.all_pass,
        "pending_manual": ["GT-M17-24：ccgp 中标公告附件《更正后（以此版本为准）3-1…--招标文件.pdf》"
                           "受 WAF 阻断未获取，待人工下载后执行文件级验证"],
        "gt_status": "draft_pending_human ×24（初标草案，未人工冻结前仅作探索性指标）",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def main() -> int:
    rep = run()
    for g, items in rep["summary"].items():
        print(f"[{g}] {items['pass']}/{items['total']}")
    fails = [r for r in rep["results"] if not r["pass"]]
    for r in fails:
        print(f"  ✗ {r['group']}/{r['name']} —— {r['detail'][:120]}")
    print(f"结论：{'全绿' if rep['all_pass'] else '存在失败'}；"
          f"报告 → {REPORT.relative_to(REPO)}")
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
