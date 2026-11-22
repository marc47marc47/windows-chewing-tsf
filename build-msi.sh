#!/usr/bin/env bash
# 建置可發行的 MSI：dist/windows-chewing-tsf-<版本>-local.msi（含 SHA-256）。
# 用法：./build-msi.sh [版本，預設 26.11.<MMDD>]   環境變數 OFFICIAL_MSI 指定官方安裝包（取預編譯元件）
#
# 元件來源：
#   本倉庫自建：x64／x86 的 chewing_tip.dll（含 libchewing 修正）、tsfreg.exe、詞庫 *.bin、ARM64X 轉接 DLL(platform/arm64x)
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
STAGE="build/installer"; OUT_MSI="dist/windows-chewing-tsf-${VER}-local.msi"
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
export RUSTFLAGS="-Ctarget-feature=+crt-static"
CARGO=(cargo --config "$CARGO_CONFIG_VENDOR")
"${CARGO[@]}" build --offline --release -p chewing_tip --target x86_64-pc-windows-msvc
"${CARGO[@]}" build --offline --release -p chewing_tip --target i686-pc-windows-msvc
"${CARGO[@]}" build --offline --release -p tsfreg --target x86_64-pc-windows-msvc
unset RUSTFLAGS
X64="target/x86_64-pc-windows-msvc/release"; X86="target/i686-pc-windows-msvc/release"

# 4) 組裝暫存目錄（結構同 xtask build-installer）
rm -rf "$STAGE"; mkdir -p "$STAGE"/{Dictionary,x64,x86} dist
cp installer/windows-chewing-tsf.wxs "$STAGE/"
cat > "$STAGE/version.wxi" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<Include>
    <?define Version = "$VER"?>
    <?define VersionSuffix = "local"?>
</Include>
EOF
printf '{\n  "product_version": "%s",\n  "build_date": "%s"\n}\n' "$VER" "$(date '+%Y 年 %m 月 %d 日')" > "$STAGE/version.json"
cp "$OFF"/{chewing.ico,chewing-cli.exe,chewing-editor.exe,ChewingPreferences.exe,chewing_tip_host.exe,WebView2Loader.dll} "$STAGE/"
cp "$X64/tsfreg.exe" "$STAGE/"
for f in static_dict static_words static_lm rare_dict; do cp "analyze/p0/dict-rebuild/$f.bin" "$STAGE/Dictionary/"; done
cp libchewing/data/misc/swkb.dat libchewing/data/misc/symbols.dat "$STAGE/Dictionary/"
cp "$X64/chewing_tip.dll" "$STAGE/x64/chewing_tip_x64.dll"
cp platform/arm64x/chewing_tip.dll "$STAGE/x64/chewing_tip.dll"                              # ARM64X 轉接（轉發到 *_local）
cp "$OFFI/System64/chewing_tip_arm64_26_11_724.dll" "$STAGE/x64/chewing_tip_arm64.dll"        # 官方 ARM64（無法自建）
cp "$X86/chewing_tip.dll" "$STAGE/x86/chewing_tip.dll"
# 官方 724 有、倉庫 .wxs 沒有的 chewing_tip_host.exe（TIP 從安裝資料夾啟動它）
"$WIN_PYTHON" - "$STAGE/windows-chewing-tsf.wxs" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
anchor = '''                <Component>
                    <File Id="tsfreg.exe" Source="tsfreg.exe" />
                </Component>'''
add = anchor + '''
                <Component>
                    <File Id="chewing_tip_host.exe" Source="chewing_tip_host.exe" />
                </Component>'''
assert anchor in s, 'tsfreg anchor not found in .wxs'
if 'Id="chewing_tip_host.exe"' not in s:
    s = s.replace(anchor, add, 1)
# older WiX does not know the newer UpgradeStrategy attribute; <MajorUpgrade> already provides the behaviour
s = s.replace(' UpgradeStrategy="majorUpgrade"', '')
open(p, 'w', encoding='utf-8').write(s)
PY

# 5) 打包
( cd "$STAGE" && dotnet "$(cygpath -w "$OLDPWD/$WIXDLL")" build -arch x64 -culture zh-TW \
    -o "$(cygpath -w "$OLDPWD/$OUT_MSI")" -pdbtype none windows-chewing-tsf.wxs )
sha256sum "$OUT_MSI" | tee "$OUT_MSI.sha256"
ls -la "$OUT_MSI"
echo "=== done: $OUT_MSI ==="
