# source ./setenv.app   -- 啟用本專案環境（不要直接執行）
_APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export APP_ROOT="$_APP_ROOT"
export APP_BIN="$APP_ROOT/bin"
export APP_ETC="$APP_ROOT/etc"
export APP_DATA="$APP_ROOT/data"
export APP_TMP="$APP_ROOT/tmp"
export APP_LOGS="$APP_ROOT/logs"
# 離線 Cargo：使用工作區內 vendor 快取（見 analyze/p0/REPRODUCE.md）
export CARGO_CONFIG_VENDOR="$(cygpath -m "$APP_ROOT")/.cache/vendor-config.toml"
# Windows 版 Python（需要 Windows 原生 API 的探測／驗證腳本用）
export WIN_PYTHON="${WIN_PYTHON:-/c/Python313/python.exe}"
export MSYS_NO_PATHCONV=1   # 讓 reg.exe 等原生工具的 /s /f 參數不被轉成路徑
case ":$PATH:" in *":$APP_BIN:"*) ;; *) export PATH="$APP_BIN:$PATH";; esac
mkdir -p "$APP_BIN" "$APP_ETC" "$APP_DATA" "$APP_TMP" "$APP_LOGS"
# 紀錄檔命名：[PROG_NAME]_YYYYMMDD.log
app_log_file() { echo "$APP_LOGS/${1:?PROG_NAME}_$(date +%Y%m%d).log"; }
unset _APP_ROOT
