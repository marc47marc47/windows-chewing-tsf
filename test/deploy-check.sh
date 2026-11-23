#!/usr/bin/env bash
# 部署驗證：安裝後檢查實際狀態，全程不送任何鍵盤／滑鼠輸入。
# 用法：./test/deploy-check.sh        結果寫入 ./logs/deploy-check_YYYYMMDD.log，失敗時結束碼 1
set -uo pipefail
cd "$(dirname "$0")/.."
source ./setenv.app
export MSYS_NO_PATHCONV=1
LOG="$(app_log_file deploy-check)"; exec > >(tee -a "$LOG") 2>&1
FAIL=0; pass(){ echo "PASS  $*"; }; fail(){ echo "FAIL  $*"; FAIL=1; }
CLSID='{13F2EF08-575C-4D8C-88E0-F67BB8052B84}'
R64='/c/Program Files/ChewingTextService'
echo "=== deploy-check $(date '+%F %T') ==="

# NB: 本機語系的 reg 輸出含非 ASCII 位元組（預設值名稱），所以只取以磁碟機代號開頭的路徑；grep 要加 -a
regval() { reg query "$1" /ve 2>/dev/null | tr -d '\000\r' | LC_ALL=C grep -a REG_SZ | LC_ALL=C sed 's/.*REG_SZ[ ]*//; s/^[^A-Za-z]*//' | LC_ALL=C grep -a '^[A-Za-z]:'; }

# 1) 註冊的 COM 伺服器檔案必須存在（上次升級就是這裡壞掉：啟動器被刪，無法輸入）
reg64=$(regval 'HKCR\CLSID\'"$CLSID"'\InprocServer32')
reg32=$(regval 'HKCR\WOW6432Node\CLSID\'"$CLSID"'\InprocServer32')
for r in "$reg64" "$reg32"; do
  if [ -z "$r" ]; then fail "registry InprocServer32 not found"; continue; fi
  if [ -f "$(cygpath -u "$r")" ]; then pass "registered server exists: $r"; else fail "registered server MISSING: $r"; fi
done

# 2) 最新版本資料夾完整
latest=$(ls -d "$R64"/[0-9]*.[0-9]* 2>/dev/null | sort -V | tail -1)
if [ -n "$latest" ]; then
  for f in chewing_tip_impl.dll chewing_tip_host.exe ChewingPreferences.exe chewing-editor.exe version.json \
           Dictionary/static_dict.bin Dictionary/static_words.bin Dictionary/static_lm.bin Dictionary/rare_dict.bin; do
    if [ -f "$latest/$f" ]; then pass "$(basename "$latest")/$f"; else fail "$(basename "$latest")/$f missing"; fi
  done
  echo "INFO  version.json: $(tr -d '\n\r ' < "$latest/version.json")"
else
  # System32 版面：程式與詞庫在 Program Files\ChewingTextService，DLL 在 System32／SysWOW64（檔名帶版號）
  for f in chewing_tip_host.exe ChewingPreferences.exe chewing-editor.exe version.json \
           Dictionary/static_dict.bin Dictionary/static_words.bin Dictionary/static_lm.bin Dictionary/rare_dict.bin; do
    if [ -f "$R64/$f" ]; then pass "$f"; else fail "$f missing"; fi
  done
  echo "INFO  version.json: $(tr -d '\n\r ' < "$R64/version.json")"
  # 遊戲（如 WoW）只會載入 System32／SysWOW64 底下的輸入法 DLL，登錄的伺服器必須在那裡
  for r in "$reg64" "$reg32"; do
    case "$(echo "$r" | tr 'A-Z' 'a-z')" in
      c:\\windows\\system32\\*|c:\\windows\\syswow64\\*) pass "server under Windows system folder: $r";;
      *) fail "server NOT under system folder (games may refuse to load it): $r";;
    esac
  done
  if [ -f "$R64/chewing_tip.dll" ]; then fail "legacy stub still present: $R64/chewing_tip.dll"; else pass "no legacy stub"; fi
fi
n=$(ls -d "$R64"/[0-9]*.[0-9]* 2>/dev/null | wc -l)
if [ "$n" -le 2 ]; then pass "version folders kept: $n (<=2)"; else fail "version folders: $n (>2, prune did not run)"; fi

# 3) 沙盒程式（AppContainer）可讀取：ALL APPLICATION PACKAGES 要有 (RX)
for f in ${reg64:+"$(cygpath -u "$reg64")"} ${reg32:+"$(cygpath -u "$reg32")"} ${latest:+"$R64/chewing_tip.dll" "$latest/chewing_tip_impl.dll"}; do
  [ -f "$f" ] || continue
  if icacls "$(cygpath -w "$f")" 2>/dev/null | tr -d '\000' | grep -aqi "ALL APPLICATION PACKAGES.*RX"; then
    pass "AppContainer RX: $(basename "$f")"
  else
    fail "AppContainer cannot read $(basename "$f")"
  fi
done

# 4) 啟動器可被載入且 DllGetClassObject 回 S_OK（64 位元）
mkdir -p tmp
( cd test && /c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe /nologo /platform:x64 /out:../tmp/stubload.exe StubLoad.cs ) 2>&1 | grep -ai error
if [ -n "$reg64" ]; then
  out=$(./tmp/stubload.exe "$reg64" 2>&1)
  if echo "$out" | grep -aq "hr=0x0 obj=True"; then pass "stub loads and creates class object"; else fail "stub load failed: $(echo "$out" | tr '\n' ' ' | cut -c1-120)"; fi
fi

# 5) 使用者資料目錄
ud="$APPDATA/Chewing/v4"
if [ -d "$ud" ]; then pass "user data dir: $ud"; else echo "INFO  no user data dir yet"; fi

# 6) 輸入法功能回歸（不需要視窗）：libchewing 重播
R=libchewing/target/release/examples/key_replay.exe; D=analyze/p0/dict-rebuild
if [ -x "$R" ]; then
  o=$($R $D t / 6 g 4 2>/dev/null | tail -1)
  if echo "$o" | grep -aq '"display":"城市"\|"display":"程式"'; then pass "key_replay converts ㄔㄥˊ ㄕˋ"; else fail "key_replay unexpected: $o"; fi
else
  echo "INFO  key_replay not built, skip"
fi

echo "=== result: $([ $FAIL = 0 ] && echo ALL PASS || echo FAILED) (log: $LOG) ==="
exit $FAIL
