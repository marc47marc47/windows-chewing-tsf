#!/usr/bin/env bash
# 建置可發行的 MSI：dist/windows-chewing-tsf-<版本>-local.msi（含 SHA-256）。
# 用法：./build-msi.sh [版本，預設 26.11.<MMDD>]   環境變數 OFFICIAL_MSI 指定官方安裝包（取預編譯元件）
#
# 元件來源：
#   本倉庫自建：x64／x86 的 chewing_tip（實作）與 chewing_tip_stub（啟動器）、tsfreg.exe、詞庫 *.bin；安裝成 Chrome 式「版本資料夾」(見 installer/windows-chewing-tsf-versioned.wxs)
#   本倉庫建不出來、取自官方 MSI（以 msiexec /a 管理映像解壓到 ./tmp，不安裝、不動系統）：
#     ChewingPreferences.exe、chewing-editor.exe、chewing_tip_host.exe、chewing-cli.exe、WebView2Loader.dll、
#     chewing.ico，以及 ARM64 的 chewing_tip DLL（本機 Visual Studio 沒有 ARM64 函式庫）
set -euo pipefail
cd "$(dirname "$0")"
source ./setenv.app
PROG=build-msi; LOG="$(app_log_file "$PROG")"
exec > >(tee -a "$LOG") 2>&1

VER="${1:-26.11.$(date +%m%d | sed 's/^0*//')}"
OFFICIAL_MSI="${OFFICIAL_MSI:-/c/Users/$USERNAME/Downloads/windows-chewing-tsf-26.11.724.msi}"
# DLL 檔名帶版號（如 chewing_tip_x64_26_11_1125.dll）：每版是新檔名，安裝時不必覆寫「已被各程式載入」的舊 DLL，
# 因此不需要重新開機（舊 DLL 留到下次重開機由系統清除；已開啟的程式要重開才會用新版）。與官方 724 的命名做法相同。
SUF="${VER//./_}"   # （版本資料夾版面已不再使用檔名後綴，保留供舊版面參考）
LAYOUT="${LAYOUT:-system32}"   # system32（預設）＝像官方 724 把 DLL 放進 System32/SysWOW64，檔名帶版號（WoW 等遊戲只認這個位置）；versioned＝舊的 Chrome 式版本資料夾＋stub（遊戲會擋，僅供參考）
case "$LAYOUT" in versioned) WXS=windows-chewing-tsf-versioned.wxs; TAG=versioned;; system32) WXS=windows-chewing-tsf-system32.wxs; TAG=local;; *) echo "LAYOUT 只能是 versioned 或 system32" >&2; exit 2;; esac
STAGE="build/installer"; OUT_MSI="dist/windows-chewing-tsf-${VER}-${TAG}.msi"
echo "=== $PROG $(date '+%F %T') version=$VER ==="

# 1) WiX 6（MS-RL；NuGet 套件，用已安裝的 .NET 執行階段執行；.wxs 沒用到 ui/util 擴充，不需要擴充套件）
WIXVER="${WIXVER:-6.0.2}"
WIXDLL="tmp/wix/wixtool-$WIXVER/tools/net6.0/any/wix.dll"
if [ ! -f "$WIXDLL" ]; then
  mkdir -p tmp/wix
  curl -sL --max-time 180 -o "tmp/wix/wix.$WIXVER.nupkg" "https://api.nuget.org/v3-flatcontainer/wix/$WIXVER/wix.$WIXVER.nupkg"
  "$WIN_PYTHON" -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "tmp/wix/wix.$WIXVER.nupkg" "tmp/wix/wixtool-$WIXVER"
fi
export DOTNET_ROLL_FORWARD=LatestMajor

# 2) 官方預編譯元件（管理映像解壓，只寫入 ./tmp）
OFFI="tmp/msi_extract"
if [ ! -f "$OFFI/PFiles64/ChewingTextService/chewing_tip_host.exe" ]; then
  [ -f "$OFFICIAL_MSI" ] || { echo "找不到官方 MSI：$OFFICIAL_MSI（用 OFFICIAL_MSI= 指定）" >&2; exit 1; }
  mkdir -p "$OFFI"
  msiexec.exe /a "$(cygpath -w "$OFFICIAL_MSI")" /qn TARGETDIR="$(cygpath -w "$PWD/$OFFI")"
  for i in $(seq 1 30); do [ -f "$OFFI/PFiles64/ChewingTextService/chewing_tip_host.exe" ] && break; sleep 1; done
fi
OFF="$OFFI/PFiles64/ChewingTextService"

# 3) 自建元件（靜態 CRT，與官方一致）
# 版本資訊（顯示在輸入法選單最上方，由 tip/build.rs 寫入資源）
export BUILD_VERSION="$VER"
export BUILD_TIME="$(date '+%Y-%m-%d %H:%M')"
if git rev-parse --short=7 HEAD >/dev/null 2>&1; then
  BUILD_GIT_HASH="$(git rev-parse --short=7 HEAD)"; git diff --quiet HEAD 2>/dev/null || BUILD_GIT_HASH="$BUILD_GIT_HASH+local"
else  # 工作資料夾不是 git 倉庫時，取最近一次推送用的複本，並標 +local 表示可能含未提交修改
  BUILD_GIT_HASH="$(git -C tmp/push-repo rev-parse --short=7 HEAD 2>/dev/null || echo unknown)+local"
fi
export BUILD_GIT_HASH
echo "build info: $VER | $BUILD_TIME | $BUILD_GIT_HASH"
export RUSTFLAGS="-Ctarget-feature=+crt-static"
CARGO=(cargo --config "$CARGO_CONFIG_VENDOR")
"${CARGO[@]}" build --offline --release -p chewing_tip --target x86_64-pc-windows-msvc
"${CARGO[@]}" build --offline --release -p chewing_tip --target i686-pc-windows-msvc
"${CARGO[@]}" build --offline --release -p tsfreg --target x86_64-pc-windows-msvc
if [ "$LAYOUT" = versioned ]; then
  "${CARGO[@]}" build --offline --release -p chewing_tip_stub --target x86_64-pc-windows-msvc
  "${CARGO[@]}" build --offline --release -p chewing_tip_stub --target i686-pc-windows-msvc
fi
unset RUSTFLAGS
X64="target/x86_64-pc-windows-msvc/release"; X86="target/i686-pc-windows-msvc/release"

# 4) 組裝暫存目錄（結構同 xtask build-installer）
rm -rf "$STAGE"; mkdir -p "$STAGE"/{Dictionary,x64,x86} dist
cp "installer/$WXS" "$STAGE/windows-chewing-tsf.wxs"
cat > "$STAGE/version.wxi" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<Include>
    <?define Version = "$VER"?>
    <?define VersionSuffix = "$SUF"?>
</Include>
EOF
printf '{\n  "product_version": "%s",\n  "build_date": "%s"\n}\n' "$VER" "$(date '+%Y 年 %m 月 %d 日')" > "$STAGE/version.json"
cp "$OFF"/{chewing.ico,chewing-cli.exe,chewing-editor.exe,ChewingPreferences.exe,chewing_tip_host.exe,WebView2Loader.dll} "$STAGE/"
cp "$X64/tsfreg.exe" "$STAGE/"
for f in static_dict static_words static_lm rare_dict; do cp "analyze/p0/dict-rebuild/$f.bin" "$STAGE/Dictionary/"; done
cp libchewing/data/misc/swkb.dat libchewing/data/misc/symbols.dat "$STAGE/Dictionary/"
cp "$X64/chewing_tip.dll" "$STAGE/x64/chewing_tip_x64.dll"          # 實作 DLL（安裝到 <版號>\chewing_tip_impl.dll）
[ "$LAYOUT" = versioned ] && cp "$X64/chewing_tip_stub.dll" "$STAGE/x64/chewing_tip_stub.dll"      # 穩定啟動器（唯一被登錄的 COM 伺服器，不隨版本改名）
cp "$X86/chewing_tip.dll" "$STAGE/x86/chewing_tip.dll"
[ "$LAYOUT" = versioned ] && cp "$X86/chewing_tip_stub.dll" "$STAGE/x86/chewing_tip_stub.dll"

# 版本資料夾的元件是 Permanent 且路徑每版不同，GUID 必須每版不同（以版號做確定性產生，重建同版得到同一份）
"$WIN_PYTHON" - "$STAGE/windows-chewing-tsf.wxs" "$VER" <<'PY'
import sys, uuid
p, ver = sys.argv[1], sys.argv[2]
s = open(p, encoding='utf-8').read()
for name in ('VerFiles64', 'Dict64', 'VerFiles32'):
    s = s.replace('@%s@' % name, str(uuid.uuid5(uuid.NAMESPACE_URL, 'chewing-tsf/%s/%s' % (ver, name))))
assert '@' not in ''.join(l for l in s.splitlines() if 'Guid=' in l), 'unreplaced Guid placeholder'
open(p, 'w', encoding='utf-8').write(s)
PY

# 5) 打包
( cd "$STAGE" && dotnet "$(cygpath -w "$OLDPWD/$WIXDLL")" build -arch x64 -culture zh-TW \
    -o "$(cygpath -w "$OLDPWD/$OUT_MSI")" -pdbtype none windows-chewing-tsf.wxs )
sha256sum "$OUT_MSI" | tee "$OUT_MSI.sha256"
ls -la "$OUT_MSI"
echo "=== done: $OUT_MSI ==="
