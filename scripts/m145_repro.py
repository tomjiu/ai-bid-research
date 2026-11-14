#!/usr/bin/env python3
"""m145 复现：松岭块 610-619 圈号子项（1）（2）（5）的 REQ 开/不开一致性。

步骤：create → import（PDF）→ extract → 对块 610-619 逐块：
  - get_block_requirements（单块 REQ 锚归属——#183 只读发现面）
  - 块原文文本（含行号/圈号形态）
产出 stdout 对照表 + 落盘 JSON 报告。

口径修正（#156 收口——2026-11-13）：
  - 旧文档「614-616 应无 REQ」是**修复前口径**（GR-004 漏抽缺陷的复现
    预期）；PR #148 修复后圈号子项段落一致开条款——本脚本不再断言「应无」，
    改为逐块登记 REQ 归属表（观测面——是否一致由人对照 #148 修复说明判读）
  - 参数化 root/ws/out/bin（默认 root 从脚本位置取得；exe 按平台补 .exe
    后缀）；不再写死 /home/z 与 /tmp
  - 全部子进程/文件 IO 显式 encoding="utf-8"（不依赖系统 locale）
  - 工作区唯一或验证为空（安全复跑——不固定共用旧数据）；失败非零退出

用法:
  python3 scripts/m145_repro.py [--ws DIR] [--out FILE] [--bin PATH] [--root DIR]
  兼容旧位置参数（ws/out/bin——但 root 不再接受写死默认值）。
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def die(msg: str) -> None:
    print(f"[m145] FAIL：{msg}", file=sys.stderr)
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="m145 圈号子项 REQ 归属复现（只读观测）")
    ap.add_argument("ws_pos", nargs="?", help="工作区目录（或省略走 --ws）")
    ap.add_argument("out_pos", nargs="?", help="报告 JSON 落盘路径（或省略走 --out）")
    ap.add_argument("bin_pos", nargs="?", help="bid-mcp-stdio 路径（或省略走 --bin）")
    ap.add_argument("--root", default=None, help="仓库根（默认 = 脚本位置上溯）")
    ap.add_argument("--ws", default=None, help="工作区目录（唯一或为空）")
    ap.add_argument("--out", default=None, help="报告 JSON 落盘路径")
    ap.add_argument("--bin", default=None, help="bid-mcp-stdio 可执行路径")
    ap.add_argument("--block-from", type=int, default=610, help="起始块号（默认 610）")
    ap.add_argument("--block-to", type=int, default=619, help="结束块号（默认 619）")
    args = ap.parse_args()
    args.root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    args.ws = args.ws or args.ws_pos
    args.out = args.out or args.out_pos
    args.bin = args.bin or args.bin_pos
    if not args.ws:
        # 旧默认 /tmp/m145-ws 的跨平台替代：平台临时目录下唯一名
        tmpbase = os.environ.get("TEMP") if os.name == "nt" else "/tmp"
        args.ws = str(Path(tmpbase) / "m145-ws")
    if not args.out:
        die("out 必须提供（--out 或位置参数）——报告不留盘等于不可重放")
    return args


def resolve_bin(root: Path, bin_arg: str) -> Path:
    p = Path(bin_arg) if bin_arg else root / "bidcore/target/debug/bid-mcp-stdio"
    # 平台 exe 后缀（#156：Windows 下自动补 .exe）
    if os.name == "nt" and p.suffix.lower() != ".exe" and not p.exists():
        cand = p.with_suffix(p.suffix + ".exe")
        if cand.exists():
            p = cand
    return p


def prepare_ws(ws: Path) -> None:
    """安全复跑纪律（#156）：唯一目录或验证为空——不静默复用旧数据。"""
    if ws.exists():
        leftovers = [x for x in ws.iterdir() if x.name not in (".DS_Store",)]
        if leftovers:
            die(f"工作区 {ws} 非空（{len(leftovers)} 项旧数据）——换目录或清空后重跑")
    ws.mkdir(parents=True, exist_ok=True)


def call(bin_path: Path, tool: str, tool_args: dict, env: dict) -> dict:
    """工具链单步：显式 UTF8 + 失败可诊断（不裸崩）。

    失败判定（两道闸——与 repro_112.call 同款，Lead 2026-11-14 实跑反例）：
    子进程退出码非零 → 步骤失败（回执 JSON 曾称 ok:true 也不放行——
    保留原回执/退出码/stderr 供诊断，附 failure_reason）。
    """
    line = json.dumps({"tool": tool, "args": tool_args}, ensure_ascii=False)
    try:
        r = subprocess.run(
            [str(bin_path)], input=line + "\n", capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env, timeout=600,
        )
    except FileNotFoundError as e:
        die(f"bid-mcp-stdio 不在位（{bin_path}）：{e}")
    out = (r.stdout or "").strip().splitlines()
    if not out:
        die(f"工具 {tool} 无输出（stderr：{(r.stderr or '')[:300]}）")
    try:
        reply = json.loads(out[-1])
    except json.JSONDecodeError:
        die(f"工具 {tool} 回执非 JSON（尾部行：{out[-1][:120]!r}；"
            f"stderr：{(r.stderr or '')[:300]}）")
    if reply.get("ok") and r.returncode != 0:
        reply = dict(reply)
        reply["ok"] = False
        reply["failure_reason"] = (f"子进程退出码非零 {r.returncode}"
                                   f"（回执 JSON 曾称 ok:true——以退出码为准）")
        print(f"[m145] 工具 {tool} 步骤失败（exit {r.returncode}，回执曾称 ok:true）"
              f"——stderr 尾部：{(r.stderr or '')[-400:]}", file=sys.stderr)
    return reply


def main() -> int:
    args = parse_args()
    root: Path = args.root
    ws = Path(args.ws)
    out = Path(args.out)
    bin_path = resolve_bin(root, args.bin)
    pdf = root / "fixtures/songling-232762/tender/光纤租赁费招标文件.pdf"

    if not bin_path.exists():
        die(f"bid-mcp-stdio 不在位：{bin_path}（先 cargo build -p bid-mcp --bin bid-mcp-stdio）")
    if not pdf.exists():
        die(f"PDF 原件缺失：{pdf}")
    prepare_ws(ws)

    env = dict(os.environ, BID_WS=str(ws), BID_FS_ROOT=str(root))

    r = call(bin_path, "create_bid_project", {"name": "m145-repro", "bid_deadline": "2026-12-31",
                                              "mode": "明标", "external_key": "m145-repro"}, env)
    if not r.get("ok"):
        die(f"create 失败：{json.dumps(r, ensure_ascii=False)[:300]}")
    pid = r["data"]["project_id"]
    r = call(bin_path, "import_tender_files", {"project_id": pid, "files": [
        {"upload_ref": str(pdf), "filename": "光纤租赁费招标文件.pdf", "kind": "招标文件"}]}, env)
    if not r.get("ok"):
        die(f"import 失败：{json.dumps(r, ensure_ascii=False)[:300]}")
    fid = (r["data"].get("file_ids") or [None])[0]
    print("pid:", pid, "| import:", r.get("ok"), "| file_id:", fid)
    if not fid:
        print("import files 结构:", json.dumps(r["data"], ensure_ascii=False)[:400])
        die("import 未回 file_id——链中断")

    r = call(bin_path, "extract_requirements", {"project_id": pid}, env)
    if not r.get("ok"):
        die(f"extract 失败：{json.dumps(r, ensure_ascii=False)[:300]}")

    blocks = []
    for idx in range(args.block_from, args.block_to + 1):
        r = call(bin_path, "get_block_requirements",
                 {"project_id": pid, "file_id": fid, "block_idx": idx}, env)
        d = r.get("data", {})
        text = d.get("text") or ""
        req_ids = d.get("req_ids") or []
        print(f"--- block {idx}: req_ids={req_ids} | verdict={d.get('verdict')}")
        print(f"    text: {text[:90]!r}")
        blocks.append({"block_idx": idx, "req_ids": req_ids,
                       "verdict": d.get("verdict"), "text": text[:200]})

    report = {
        "repo_head": None,
        "tool": {"bin": str(bin_path)},
        "pdf": str(pdf),
        "workspace": str(ws),
        "blocks": blocks,
        "note": "观测面：GR-004 修复（PR #148）后圈号子项段落一致开条款——本表"
                "不再断言「614-616 应无 REQ」（那是修复前口径）；一致性由人对照"
                " #148 修复说明判读。",
    }
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30)
        report["repo_head"] = head.stdout.strip() if head.returncode == 0 else None
    except (subprocess.SubprocessError, OSError):
        pass
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"块归属表落盘: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
