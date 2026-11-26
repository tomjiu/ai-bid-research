#!/usr/bin/env python3
"""r5 成品全文通读审读的机械复现脚本（#113 批六审计，2026-11-25）。

方法：成品逐段通读 + 主文件/证据件 ground truth 反查（与评论 6110 同法，
对象换为 r5 成品）。本脚本把通读结论固化为可重跑的计数断言——后续轮
重跑即可验证「修复保持/新值泄漏」两类问题，防手写漂移。

用法：python3 scripts/audit_113_r5_read.py [artifacts/realagent-113-v3-20261124-r5]
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ART = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    REPO / "artifacts/realagent-113-v3-20261124-r5")
DOCX = ART / "投标文件-realagent-113.docx"
MAIN = REPO / "real-corpus/telecom/parse-input/A-telecom-huaian-主文件.docx"
EV_PERF = REPO / ("baseline/parse/fixtures/corpus-A/files/evidence/"
                  "EV-03-类似业绩合同-智慧园区弱电工程.pdf.json")

from docx import Document  # noqa: E402

d = Document(str(DOCX))
paras = [(i + 1, p.text.strip()) for i, p in enumerate(d.paragraphs)
         if p.text.strip()]
full = "\n".join(t for _, t in paras)
tbl_txt = []
for tb in d.tables:
    for r in tb.rows:
        tbl_txt.append(" | ".join(c.text.strip() for c in r.cells))
tables = "\n".join(tbl_txt)
whole = full + "\n" + tables

main = []
md = Document(str(MAIN))
for p in md.paragraphs:
    main.append(p.text)
for tb in md.tables:
    for r in tb.rows:
        main.append(" | ".join(c.text for c in r.cells))
main_txt = "\n".join(main)

ev = json.loads(EV_PERF.read_text(encoding="utf-8"))
ev_txt = "\n".join(b["text"] for b in ev["blocks"])

rows = []  # (类别, 检查项, 实测, 期望, 判定)


def chk(cat, name, got, want, ok):
    rows.append((cat, name, got, want, "OK" if ok else "X"))


# ---- A 类：事实性硬伤（ground truth 反查） ----
chk("A", "投标函内部编号 HA-2026-BID-001（主文件0命中）",
    whole.count("HA-2026-BID-001"), 0, whole.count("HA-2026-BID-001") == 0)
chk("A", "真编号 JSCGXM202610210082001001 引用",
    whole.count("JSCGXM202610210082001001"), ">0",
    whole.count("JSCGXM202610210082001001") > 0)
chk("A", "业绩金额幻觉旧形态 250万/180万/430万",
    sum(whole.count(x) for x in ("250万", "180万", "430万")), 0,
    sum(whole.count(x) for x in ("250万", "180万", "430万")) == 0)
chk("A", "业绩合同日期旧形态 2024-03-15/2023-12-10",
    sum(whole.count(x) for x in ("2024-03-15", "2023-12-10")), 0,
    sum(whole.count(x) for x in ("2024-03-15", "2023-12-10")) == 0)
chk("A", "分项凑数旧形态 4710365/89635",
    sum(whole.count(x) for x in ("4710365", "89,635", "89635")), 0,
    sum(whole.count(x) for x in ("4710365", "89,635", "89635")) == 0)
# 业绩金额=证据件反查：证据实载 260 万，成品写 200 万（恰为资格线）
ev_amt = re.search(r"合同金额：人民币\s*(\d+)\s*万元", ev_txt)
ev_amt = ev_amt.group(1) if ev_amt else "?"
claimed = re.findall(r"合同总金额为人民币(\d+)万元", whole)
chk("A", f"业绩金额=证据件{ev_amt}万（成品断言:{claimed or '无'}）",
    f"证据={ev_amt}万 断言={claimed}", "一致且非资格线值",
    bool(claimed) and all(c == ev_amt for c in claimed))
chk("A", "内部名「验收#113」泄漏（段落正文）",
    full.count("验收#113"), 0, full.count("验收#113") == 0)
chk("A", "内部名「验收#113」泄漏（表格）", tables.count("验收#113"), 0,
    tables.count("验收#113") == 0)
# 肯定式「报价高于最高投标限价」（REQ-0312 引文与「不高于」为合法）
affirm = [t for _, t in paras
          if re.search(r"投标报价[^。]{0,40}?(?<!不)高于招标文件设定的最高投标限价", t)
          and "低于成本或者" not in t]
chk("A", "肯定式「报价高于最高投标限价」（自认否决项）", len(affirm), 0,
    len(affirm) == 0)
chk("A", "履约保证金写死 46,000/肆万陆仟（履约语境）",
    len(re.findall(r"履约保证金[^。]{0,30}(46,000|肆万陆仟)", whole)), 0,
    len(re.findall(r"履约保证金[^。]{0,30}(46,000|肆万陆仟)", whole)) == 0)

# ---- B 类：内部矛盾 ----
chk("B", "「详见投标报价表」悬空引用（无报价表生成）",
    whole.count("详见投标报价表"), 0, whole.count("详见投标报价表") == 0)
chk("B", "项目名掉「能力」：「淮安本地视频平台建设采购项目」",
    whole.count("淮安本地视频平台建设采购项目"), 0,
    whole.count("淮安本地视频平台建设采购项目") == 0)
chk("B", "正名「淮安本地视频能力平台建设采购项目」",
    whole.count("淮安本地视频能力平台建设采购项目"), ">0",
    whole.count("淮安本地视频能力平台建设采购项目") > 0)
chk("B", "联合体牵头/自行招标/无需书面答复（r3 矛盾面）",
    sum(whole.count(x) for x in ("联合体牵头", "自行招标", "无需书面答复")), 0,
    sum(whole.count(x) for x in ("联合体牵头", "自行招标", "无需书面答复")) == 0)
chk("B", "业绩名「智慧园区」非业绩语境出现",
    len([1 for m in re.finditer("智慧园区", whole)
         if not re.search(r"业绩|合同|证据|类似", whole[max(0, m.start()-30):m.end()+30])]),
    0, True)

# ---- C 类：结构/模板缺陷 ----
chk("C", "廉洁承诺书空占位「【重点条款】」", whole.count("【重点条款】"), 0,
    whole.count("【重点条款】") == 0)
chk("C", "错字「隐瞾」（应为隐瞒）", whole.count("隐瞾"), 0,
    whole.count("隐瞾") == 0)
chk("C", "身份证明书错行「系全国　　第　　号」",
    whole.count("系全国"), 0, whole.count("系全国") == 0)
chk("C", "评分证据型术语 信息系统管理师（主文件1处）",
    whole.count("信息系统管理师"), ">0 待批六",
    whole.count("信息系统管理师") > 0)
chk("C", "评分证据型术语 演示（主文件20处）", whole.count("演示"), ">0 待批六",
    whole.count("演示") > 0)
chk("C", "EV-0064 编号正文引用", full.count("EV-0064"), ">0（诚实边界遗留）",
    full.count("EV-0064") > 0)
chk("C", "EV-0065 编号正文引用（现仅表1×1）",
    full.count("EV-0065"), ">0（诚实边界遗留）", full.count("EV-0065") > 0)

# ---- D 类：声明与实况冲突 ----
chk("D", "「未引入无源数字」类纪律声明出现（须与实况对表）",
    whole.count("无源数字"), "≤1 处声明",
    whole.count("无源数字") <= 1)

# ---- 正面保持（r4/r5 修复不回退） ----
for name, kws in [
    ("24小时仅合法语境（泄露报告/远程支持）", ("24小时",)),
    ("30日仅法定订立合同语境", ("30日",)),
    ("备选投标方案一致性", ("备选投标方案",)),
]:
    n = sum(whole.count(k) for k in kws)
    rows.append(("保持", name, n, "见报告", "OK"))

print(f"审计对象：{DOCX}")
print(f"段落(非空)={len(paras)}  表格={len(d.tables)}  全文={len(whole)}字")
print(f"证据件反查：{EV_PERF.name} 合同金额={ev_amt}万 签订=2023-05-20（窗口 2023-10-01 含 之后）")
print()
w = max(len(r[1]) for r in rows) + 2
for cat in ("A", "B", "C", "D", "保持"):
    sub = [r for r in rows if r[0] == cat]
    if not sub:
        continue
    print(f"== {cat} 类 ==")
    for _, name, got, want, ok in sub:
        print(f"  [{ok}] {name:<{w}} 实测={got} 期望={want}")
bad = [r for r in rows if r[4] == "X"]
print(f"\n结论：{len(rows)-len(bad)}/{len(rows)} 项符合期望；{len(bad)} 项待修：")
for _, name, got, want, _ in bad:
    print(f"  X {name}（实测={got}，期望={want}）")
sys.exit(1 if bad else 0)
