#!/usr/bin/env bash
# rust-env.sh —— Rust 沙箱环境自愈手册（单一真源：本文件）
#
# 背景：云沙箱默认无 Rust 工具链，且会被周期性回收（2026-11-11 实测：回收
# 清掉 ~/.cargo ~/.rustup ~/.optroot 与未推送的本地分支——**push 要趁早**）。
# 本脚本把「从裸沙箱到 cargo test -p bid-mcp 全绿」的恢复流程固化成一条命令。
#
# 用法（bash scripts/rust-env.sh，幂等——每步先探测已存在）：
#   ① 装rustup（minimal + stable，~21MB 下载 / ~1.5G 装后）
#   ② 配 mdcore 认证（git url.insteadOf——bid-engine 的 git 依赖需要）
#   ③ 磁盘纪律：CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
#      CARGO_INCREMENTAL=0
#      （debuginfo 关闭后链接产物 ~40MB vs ~300MB；9.9G 盘装得下全树测试。
#      实测教训：开着 debuginfo 链接第 ~30 个测试二进制即 Bus error/ENOSPC；
#      增量目录单独即可打满盘——INCREMENTAL=0 必须与 DEBUG=0 并用，
#      mdcore 仓 #152 同日实证 [2026-11-11]）
#   ④ （可选，mang-app 面才需要）optroot：apt download + dpkg -x 解
#      gtk/webkit2gtk dev 树到 ~/.optroot——无 sudo 的 sysroot 自愈
#
# 各测试面对照（2026-11-11 实测，2 核沙箱）：
#   cargo test -p bid-tools      ~400 测试 / ~6min 首建
#   cargo test -p bid-mcp        ~423 测试 / ~10min 首建（含 python3+mcp 包时
#                                mcp_sdk_e2e 真跑；无则 SKIP）
#   python3 scripts/run_tests.py 主链 55+ 过（T17e/T18a 需 ~2G 盘余给
#                                engine_probe 独立 target；不足则假失败——
#                                磁盘满 ≠ 代码红，先 df -h 再定罪）
#   cargo test -p mang-app       需 ④（gtk optroot ~2G）+ ~3G 构建；缺件时
#                                run_tests.py 判 SKIP（非失败）
set -euo pipefail

CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"
OPTROOT="${OPTROOT:-$HOME/.optroot}"

log() { printf '[rust-env] %s\n' "$*"; }

# ---- ① rustup（minimal + stable）-------------------------------------------
if ! command -v cargo >/dev/null 2>&1 && [ ! -x "$CARGO_HOME/bin/cargo" ]; then
    log "① 安装 rustup（minimal + stable）"
    tmp_init=$(mktemp /tmp/rustup-init.XXXX)
    curl -sfL https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init -o "$tmp_init"
    chmod +x "$tmp_init"
    RUSTUP_HOME="$RUSTUP_HOME" CARGO_HOME="$CARGO_HOME" "$tmp_init" -y \
        --profile minimal --default-toolchain stable
    rm -f "$tmp_init"
    for b in "$CARGO_HOME"/bin/*; do
        [ -x "$b" ] && ln -sf "$b" /usr/local/bin/ 2>/dev/null || true
    done
else
    log "① cargo 已在位（$(command -v cargo || echo "$CARGO_HOME/bin/cargo")）"
fi
cargo --version

# ---- ② mdcore 认证（bid-engine git 依赖）-----------------------------------
GITEA_USER="sandbox-agent"
GITEA_TOKEN="${GITEA_TOKEN:?需要环境变量 GITEA_TOKEN（沙箱代理凭据）}"
if ! git config --global --get url."https://$GITEA_USER:$GITEA_TOKEN@git.mingjiu.store/sandbox/mdcore".insteadOf >/dev/null 2>&1; then
    log "② 配置 mdcore insteadOf 认证"
    git config --global url."https://$GITEA_USER:$GITEA_TOKEN@git.mingjiu.store/sandbox/mdcore".insteadOf \
        "https://git.mingjiu.store/sandbox/mdcore"
else
    log "② mdcore insteadOf 已在位"
fi

# ---- ③ 磁盘纪律（环境变量形态——用法：source 本文件或 eval 输出）------------
log "③ 磁盘纪律提示：cargo 测试统一用："
log "   CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_INCREMENTAL=0 cargo test -p <crate> -j1"
log "   （-j1 防链接期并发爆盘；INCREMENTAL=0 防增量目录打满盘；盘余 <1G 时清顶层测试二进制）"
log "   环境变量已导出（若 source 执行）："
export CARGO_PROFILE_DEV_DEBUG=0
export CARGO_PROFILE_TEST_DEBUG=0
export CARGO_INCREMENTAL=0

# ---- ④ optroot（mang-app 的 gtk/webkit sysroot，无 sudo 自愈）--------------
if [ "${1:-}" = "--with-gtk" ]; then
    if [ -f "$OPTROOT/usr/lib/x86_64-linux-gnu/pkgconfig/webkit2gtk-4.1.pc" ]; then
        log "④ optroot gtk 树已在位"
    else
        log "④ 下载 gtk/webkit2gtk dev 包树（~500MB）→ 解到 $OPTROOT"
        mkdir -p "$OPTROOT/debs"
        cd "$OPTROOT/debs"
        apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts \
            --no-breaks --no-replaces --no-enhances \
            libgtk-3-dev libwebkit2gtk-4.1-dev pkg-config 2>/dev/null \
            | grep '^\w' | sort -u | xargs -r apt-get download -y
        for d in ./*.deb; do dpkg -x "$d" "$OPTROOT"; done
        rm -rf "$OPTROOT/debs" "$OPTROOT/usr/share/doc" "$OPTROOT/usr/share/locale" \
               "$OPTROOT/usr/share/man" "$OPTROOT/usr/share/gtk-doc"
        cd -
    fi
    cat <<'ENVECHO'
mang-app 面运行前导出：
  OPTROOT=$HOME/.optroot
  export PKG_CONFIG_PATH="$OPTROOT/usr/lib/x86_64-linux-gnu/pkgconfig:$OPTROOT/usr/share/pkgconfig"
  export LD_LIBRARY_PATH="$OPTROOT/usr/lib/x86_64-linux-gnu:$OPTROOT/usr/lib"
  export LIBRARY_PATH="$OPTROOT/usr/lib/x86_64-linux-gnu"
  CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 cargo test -p mang-app -j1
ENVECHO
fi

log "完成。下一步：cd bidcore && cargo fetch && cargo test -p bid-mcp -j1"
