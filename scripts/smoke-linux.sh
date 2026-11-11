#!/usr/bin/env bash
# 离线全链冒烟（Linux/macOS，#601 R67）
#
# 用法：bash scripts/smoke-linux.sh [PYTHON]
#   PYTHON 缺省为 python3。任意一步失败立即非零退出。
#
# 覆盖面：--version → collect（fixture 装载+去重+入库）→ db --status
# → data-quality（R82 质量巡检）→ analyze（离线报告）→ db export
# → db --runs（R83 台账）→ 产物断言 → 批 N 沉睡字段链路
# （R95-R98：十八至二十一节 + 跨平台信号）。
# 全程离线（不依赖 LLM/网络）——CI 与本机自检通用。

set -euo pipefail

PYTHON="${1:-python3}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/bid-smoke.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

DB="$TMP_DIR/smoke.db"
REPORTS="$TMP_DIR/reports"
SNAP="$TMP_DIR/snap.json"
SRC="tests/fixtures/announcements/a-别名与重复.json"

step() { printf '\n== %s ==\n' "$1"; }

step "版本面"
"$PYTHON" main.py --version

step "collect：fixture 装载 → 去重 → 入库"
"$PYTHON" main.py collect --source "$SRC" --db "$DB"

step "db --status：库结构"
"$PYTHON" main.py db --db "$DB" --status

step "data-quality：质量巡检（R82，含语义健康分）"
"$PYTHON" main.py data-quality --db "$DB" --json > "$TMP_DIR/dq.json"

step "analyze：离线数据报告"
"$PYTHON" main.py analyze --db "$DB" --output-dir "$REPORTS"

step "db export：研究快照（R88 近重复感知去重双跑）"
"$PYTHON" main.py db --db "$DB" --export json --out "$SNAP"
"$PYTHON" main.py db --db "$DB" --export json --dedupe --out "$TMP_DIR/snap-dedup.json"

step "data-quality --min-score 门槛门（R87，应过）"
"$PYTHON" main.py data-quality --db "$DB" --min-score 50

step "pipeline（无源分析链）→ db --runs：运行台账（R83）"
"$PYTHON" main.py pipeline --db "$DB" --output-dir "$REPORTS"
"$PYTHON" main.py db --db "$DB" --runs 3

step "产物断言"
"$PYTHON" - "$DB" "$REPORTS" "$SNAP" "$TMP_DIR/dq.json" << 'PYASSERT'
import json
import sys
from pathlib import Path

db_path, reports_dir, snap_path, dq_path = (Path(a) for a in sys.argv[1:5])

assert db_path.exists(), "数据库未落盘"
assert db_path.stat().st_size > 0, "数据库为空"

snap = json.loads(snap_path.read_text(encoding="utf-8"))
assert isinstance(snap, list) and snap, "快照为空"
first = snap[0]
assert first.get("bid_id"), "快照缺 bid_id"

# R82：质量巡检 JSON 面可解析且健康分在界内
dq = json.loads(dq_path.read_text(encoding="utf-8"))
assert 0 <= dq["semantic_health"]["health_score"] <= 100, "健康分越界"

reports = sorted((reports_dir).glob("*.md"))
assert reports, "报告未生成"
body = reports[-1].read_text(encoding="utf-8")
assert "# 领域数据分析报告" in body, "报告标题缺失"
assert "## 目录" in body, "目录缺失（R63）"
assert "## 十六、近重复公告检测" in body, "近重复节缺失（R80）"
assert "## 十七、语义质量审计" in body, "语义质量节缺失（R82）"
assert "\r" not in body, "行尾非 LF（R45 契约违背）"

# R88：去重快照可解析且条数 ≤ 全量（簇内剔除或相等）
dedup = json.loads(
    Path(snap_path.parent, "snap-dedup.json").read_text(encoding="utf-8")
)
assert isinstance(dedup, list), "去重快照非纯数组（--diff 兼容破坏）"
assert len(dedup) <= len(snap), "去重后条数反增"

print(f"断言通过：快照 {len(snap)} 条（去重后 {len(dedup)}），报告 {reports[-1].name}")
PYASSERT

step "批 N 沉睡字段链路：g-fixture → 四新节渲染（R95-R98）"
GDB="$TMP_DIR/smoke-n.db"
GREPORTS="$TMP_DIR/reports-n"
"$PYTHON" main.py collect --source "tests/fixtures/announcements/g-沉睡字段.json" --db "$GDB"
"$PYTHON" main.py analyze --db "$GDB" --output-dir "$GREPORTS"
"$PYTHON" - "$GREPORTS" << 'PYASSERT_N'
import sys
from pathlib import Path

reports = sorted(Path(sys.argv[1]).glob("*.md"))
assert reports, "批 N 报告未生成"
body = reports[-1].read_text(encoding="utf-8")
for marker in (
    "## 十八、响应窗口期",       # R95 deadline
    "## 十九、代理机构画像",      # R96 agency
    "## 二十、品类分布",         # R97 category
    "## 二十一、平台来源分布",    # R98 source_url
    "### 跨平台转发信号",        # R98 与十六节簇交叉
    "研究提示非违规认定",         # R95 短窗诚实口径注
):
    assert marker in body, f"批 N 缺: {marker}"
# 短窗示例：GN-03 智慧安防改造工程（14 日 < 20）
assert "智慧安防改造工程 | 14" in body, "短窗示例缺失（R95）"
# 域名归一：www/裸域名/http 三形态折叠为同平台（qianlima 2 条）
sec21 = body.split("## 二十一")[1]
assert "| qianlima.com | 2 |" in sec21, "域名归一失效（R98）"
assert "\r" not in body, "行尾非 LF（R45 契约违背）"
print("批 N 断言通过：十八至二十一节 + 跨平台信号 + 域名归一")
PYASSERT_N

printf '\nSMOKE OK（Linux 离线全链）\n'
