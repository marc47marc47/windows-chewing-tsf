#!/usr/bin/env bash
# 打包：①可發行的 MSI（呼叫 ./build-msi.sh → ./dist/*.msi）②工具包 zip（bin、etc、分析腳本、P0 文件）→ ./tmp/release/
# 用法：./pack-release.sh [版本標籤]      預設標籤取自根 Cargo.toml version
#       NO_MSI=1 ./pack-release.sh      只打工具包 zip，不建 MSI
#       MSI_VERSION=26.11.1200 ./pack-release.sh   指定 MSI 版本（預設 26.11.<MMDD>）
set -euo pipefail
cd "$(dirname "$0")"
source ./setenv.app
PROG=pack-release; LOG="$(app_log_file "$PROG")"
exec > >(tee -a "$LOG") 2>&1
VER="${1:-$(sed -n 's/^version *= *"\(.*\)"/\1/p' Cargo.toml | head -1)}"
NAME="windows-chewing-tsf-tools-$VER"
OUT="$APP_TMP/release"; STAGE="$OUT/$NAME"
echo "=== $PROG $(date '+%F %T') $NAME ==="
[ -f bin/chewing-cli.exe ] || { echo "bin/ 尚未建置，先執行 ./build.sh" >&2; exit 1; }
if [ "${NO_MSI:-0}" != 1 ]; then
  ./build-msi.sh ${MSI_VERSION:+"$MSI_VERSION"}
  MSI="$(ls -t dist/windows-chewing-tsf-*-local.msi | head -1)"
  echo "MSI: $MSI"
fi
rm -rf "$STAGE"; mkdir -p "$STAGE"/{bin,etc,scripts,docs}
cp -a bin/*.exe "$STAGE/bin/"
cp -a etc/. "$STAGE/etc/" 2>/dev/null || true
cp -a setenv.app build.sh pack-release.sh "$STAGE/"
cp -a analyze/scripts/*.py "$STAGE/scripts/"
cp -a analyze/p0/REPRODUCE.md analyze/p0/manifest.json TODO-ms-bopomofo-chewing.md "$STAGE/docs/"
( cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
( cd "$OUT" && rm -f "$NAME.zip" && "$WIN_PYTHON" -c "import shutil,sys;shutil.make_archive(sys.argv[1],'zip','.',sys.argv[1])" "$NAME" )
( cd "$OUT" && sha256sum "$NAME.zip" | tee "$NAME.zip.sha256" )
if [ -n "${MSI:-}" ]; then cp -f "$MSI" "$MSI.sha256" "$OUT/"; echo "release MSI -> $OUT/$(basename "$MSI")"; fi
echo "=== done: $OUT/$NAME.zip ==="
