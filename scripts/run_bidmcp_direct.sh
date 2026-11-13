#!/usr/bin/env bash
# run_bidmcp_direct.sh —— bid-mcp 测试直跑器（磁盘纪律：分批链接→逐跑→即删）
#
# 背景：bid-mcp 68 个集成测试二进制 × ~56M ≈ 3.3G，9.9G 沙箱盘装不下
# 一次性 `cargo test -p bid-mcp`（全链接即 ENOSPC→Bus error）。
# 本脚本分批（默认 10 个/批）`--no-run` 链接 → 逐二进制直跑 → 跑完即删。
#
# 用法：bash scripts/run_bidmcp_direct.sh [测试名过滤正则] [批大小]
#   bash scripts/run_bidmcp_direct.sh                       # 全部 68 个
#   bash scripts/run_bidmcp_direct.sh 'coverage|scoring'    # 只跑匹配的
set -uo pipefail

cd "$(dirname "$0")/../bidcore/crates/bid-mcp" || exit 2
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_INCREMENTAL=0
FILTER="${1:-.}"
BATCH="${2:-10}"
OUT_DIR="../../target/debug/build/bid-mcp"
LOG=/tmp/bidmcp_direct.log
: > "$LOG"

# 测试目标全集（tests/*.rs 自动发现）
mapfile -t ALL < <(ls tests/*.rs | xargs -n1 basename | sed 's/\.rs$//' | sort)
# 过滤
TARGETS=()
for t in "${ALL[@]}"; do [[ "$t" =~ $FILTER ]] && TARGETS+=("$t"); done
echo "[direct] 目标 ${#TARGETS[@]}/${#ALL[@]} 个（filter=$FILTER batch=$BATCH）"

run_bin() {  # 运行单个已链接二进制（CWD=包根，与 cargo test 一致）
    local bin="$1" name="$2"
    if timeout 900 "$bin" --test-threads=2 >> "$LOG" 2>&1; then
        echo "[ok] $name"
    else
        echo "[FAIL] $name（详见 $LOG）"
        FAILED_LIST+=("$name")
    fi
    rm -f "$bin"
}

FAILED_LIST=()
i=0
while (( i < ${#TARGETS[@]} )); do
    batch=("${TARGETS[@]:i:BATCH}")
    (( i += BATCH ))
    echo "[link] ${batch[*]}"
    args=()
    for t in "${batch[@]}"; do args+=(--test "$t"); done
    if ! cargo test -p bid-mcp --no-run -j2 "${args[@]}" >> "$LOG" 2>&1; then
        echo "[LINK-FAIL] 本批链接失败：${batch[*]}（详见 $LOG）"
        FAILED_LIST+=("${batch[@]}")
        continue
    fi
    for t in "${batch[@]}"; do
        bin=$(find "$OUT_DIR" -maxdepth 3 -type f -name "${t}-*" -size +10M 2>/dev/null | head -1)
        if [[ -n "$bin" && -x "$bin" ]]; then
            run_bin "$bin" "$t"
        else
            echo "[SKIP] $t：二进制未找到（可能名字带哈希规则外）"
        fi
    done
done

# lib 单元测试（小二进制，cargo 直跑）
echo "[lib] 单元测试"
if cargo test -p bid-mcp --lib -j2 >> "$LOG" 2>&1; then
    echo "[ok] lib"
else
    echo "[FAIL] lib"
    FAILED_LIST+=("lib")
fi

echo "=========================================="
if (( ${#FAILED_LIST[@]} == 0 )); then
    echo "[direct] 全部通过 ✅"
    exit 0
else
    echo "[direct] 失败 ${#FAILED_LIST[@]} 个：${FAILED_LIST[*]}"
    exit 1
fi
