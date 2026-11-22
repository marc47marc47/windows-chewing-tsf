#!/usr/bin/env bash
# 編譯：libchewing 命令列工具與候選清單範例 → ./bin；工作區（TIP）檢查。
# 用法：./build.sh [--release|--debug] [--no-workspace]
set -euo pipefail
cd "$(dirname "$0")"
source ./setenv.app
PROG=build; LOG="$(app_log_file "$PROG")"
PROFILE=release; WORKSPACE=1
for a in "$@"; do case "$a" in
  --release) PROFILE=release;; --debug) PROFILE=debug;; --no-workspace) WORKSPACE=0;;
  *) echo "unknown option: $a" >&2; exit 2;; esac; done
exec > >(tee -a "$LOG") 2>&1
echo "=== $PROG $(date '+%F %T') profile=$PROFILE ==="
FLAG=(); [ "$PROFILE" = release ] && FLAG=(--release)
CARGO=(cargo --config "$CARGO_CONFIG_VENDOR")
( cd libchewing && "${CARGO[@]}" build --offline "${FLAG[@]}" -p chewing-cli && "${CARGO[@]}" build --offline "${FLAG[@]}" --example candidate_inventory --example key_replay )
T="libchewing/target/$PROFILE"
install -m 0755 "$T/chewing-cli.exe" bin/
install -m 0755 "$T/examples/candidate_inventory.exe" bin/
install -m 0755 "$T/examples/key_replay.exe" bin/
if [ "$WORKSPACE" = 1 ]; then "${CARGO[@]}" check --offline; fi
echo "=== done: $(ls bin | tr '\n' ' ') ==="
