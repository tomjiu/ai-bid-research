#!/usr/bin/env bash
# run_pkg_direct.sh —— 任意包测试直跑器（磁盘纪律：分批链接→逐跑→即删）
# 用法：bash scripts/run_pkg_direct.sh <crate-name> [过滤正则] [批大小]
set -uo pipefail

CRATE="${1:?用法: run_pkg_direct.sh <crate-name> [filter] [batch]}"
FILTER="${2:-.}"
BATCH="${3:-10}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG_DIR="$ROOT/bidcore/crates/$CRATE"
[ -d "$PKG_DIR" ] || { echo "no such crate dir: $PKG_DIR"; exit 2; }
cd "$PKG_DIR" || exit 2
export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_INCREMENTAL=0
OUT_DIR="../../target/debug/build/$CRATE"
LOG=/tmp/pkg_${CRATE}_direct.log
: > "$LOG"

mapfile -t ALL < <(ls tests/*.rs 2>/dev/null | xargs -n1 basename | sed 's/\.rs$//' | sort)
TARGETS=()
for t in "${ALL[@]}"; do [[ "$t" =~ $FILTER ]] && TARGETS+=("$t"); done
echo "[$CRATE] 测试目标 ${#TARGETS[@]}/${#ALL[@]} 个（filter=$FILTER batch=$BATCH）"

FAILED_LIST=()
run_bin() {
    local bin="$1" name="$2"
    if timeout 900 "$bin" --test-threads=2 >> "$LOG" 2>&1; then
        echo "[ok] $name"
    else
        echo "[FAIL] $name（详见 $LOG）"
        FAILED_LIST+=("$name")
    fi
    rm -f "$bin"
}

i=0
while (( i < ${#TARGETS[@]} )); do
    batch=("${TARGETS[@]:i:BATCH}")
    (( i += BATCH ))
    echo "[link] ${batch[*]}"
    args=()
    for t in "${batch[@]}"; do args+=(--test "$t"); done
    if ! cargo test -p "$CRATE" --no-run -j2 "${args[@]}" >> "$LOG" 2>&1; then
        echo "[LINK-FAIL] ${batch[*]}"
        FAILED_LIST+=("${batch[@]}")
        continue
    fi
    for t in "${batch[@]}"; do
        bin=$(find "$OUT_DIR" -maxdepth 3 -type f -name "${t}-*" -size +5M 2>/dev/null | head -1)
        if [[ -n "$bin" && -x "$bin" ]]; then
            run_bin "$bin" "$t"
        else
            echo "[SKIP] $t：二进制未找到"
        fi
    done
done

echo "[lib] 单元测试"
if cargo test -p "$CRATE" --lib -j2 >> "$LOG" 2>&1; then
    echo "[ok] lib"
else
    echo "[FAIL] lib"
    FAILED_LIST+=("lib")
fi
echo "[doc] 文档测试"
if cargo test -p "$CRATE" --doc -j2 >> "$LOG" 2>&1; then
    echo "[ok] doc"
else
    echo "[FAIL] doc"
    FAILED_LIST+=("doc")
fi

echo "=========================================="
if (( ${#FAILED_LIST[@]} == 0 )); then
    echo "[$CRATE] 全部通过 ✅"
    exit 0
else
    echo "[$CRATE] 失败 ${#FAILED_LIST[@]} 个：${FAILED_LIST[*]}"
    exit 1
fi
