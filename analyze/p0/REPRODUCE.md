# P0 重現指引（2026-11-22）

工作目錄一律為 `<repo>`。測試用 Git Bash；需要 Windows 原生 API 的腳本必須用
Windows 版 Python（`/c/Python313/python.exe`），Git Bash 內建 python 會因 `os.name!='nt'` 拒絕。
先 `export MSYS_NO_PATHCONV=1` 再使用 `reg query ... /s`。

## 版本釘選（P0.1／P0.4）
- `python analyze/scripts/build_p0_manifest.py` → `analyze/p0/manifest.json`
  內容：9 個參考 DLL/EXE（版本、SHA-256、與系統安裝副本逐位元比較）、PDB GUID／age／SHA-256、
  13 個系統 IMD 的 SHA-256（與解析快照 `analyze/imd/coverage.json` 比對）、chewing 工作區版本與詞庫檔雜湊、工具版本。
  參考副本、系統副本、chewing 分開成不同記錄，不混用。結果：9/9 安裝副本等於參考副本；13/13 IMD 等於解析快照。
- `python analyze/scripts/validate_symbols.py` → `analyze/symbols/identity-audit.json`（9 個 PE/PDB GUID、age 核對）

## chewing 建置與測試（P0.5）
Cargo 離線使用工作區內 vendor 快取：`CFG=$(pwd)/.cache/vendor-config.toml`
- 核心測試：`cd libchewing && cargo --config "$CFG" test --offline`
  → 129 passed／0 failed／1 ignored（另 12 doctest）；紀錄 `analyze/p0/cargo-test-libchewing.log`
- 主程式檢查：`cargo --config "$CFG" check --offline`（工作區根目錄）
  → exit 0；紀錄 `analyze/p0/cargo-check-workspace.log`
- 詞庫建置（等同 CMake `dict_chewing_v4`）：
  `cargo --config "$CFG" build --offline -p chewing-cli`（於 libchewing），再以
  `libchewing/target/debug/chewing-cli.exe` 執行
  `index create-string-table static_words.txt → static_words.bin`、
  `index create-dict tsi_dict.csv static_words.txt → static_dict.bin`、
  `index create-dict rare_dict.csv static_words.txt → rare_dict.bin`、
  `lm compile static_lm.arpa static_words.txt → static_lm.bin`（輸入在 `libchewing/data/dict/chewing_v4/`）。
  輸出 `analyze/p0/dict-rebuild/`；四個 .bin 的 SHA-256 與 `build/local-dictionary/dict/chewing_v4/` 既有檔相同。
- 全量候選清單：`cd libchewing && cargo --config "$CFG" run --offline --release --example candidate_inventory -- ../analyze/p0/dict-rebuild data/dict/chewing_v4/tsi_dict.csv data/dict/chewing_v4/rare_dict.csv > out.tsv`
  → readings=125575 candidates=165258 unsupported=0 empty=0；輸出與 `analyze/selection/chewing-candidates.tsv` 位元組相同。

## 微軟 IMD 解析與原生比對
- `python analyze/scripts/test_imd_parser.py`（7 測試通過）
- 原生查詢驗證（需 Windows Python）：`verify_native_lexical.py`、`verify_native_bigram3.py`、
  `verify_native_ngram.py`、`verify_native_ngram_outer.py`；皆載入 SHA 鎖定的參考 DLL（不執行進入點）。

## 執行環境觀測（P0.3）
- `python analyze/scripts/probe_active_tsf_profile.py`：TSF 回報的作用中鍵盤 TIP → `analyze/selection/active-tsf-profile.json`
- `python analyze/scripts/probe_loaded_modules.py [等待秒數]`：掃描各處理程序是否載入 IMETC／ChtIME 模組 → `analyze/selection/loaded-modules-probe.json`
- `analyze/scripts/probe_runtime.ps1`：登錄檔設定唯讀快照 → `analyze/selection/runtime-probe.json`

## 專案慣例與腳本（2026-11-22）
- 目錄：`./bin` 執行檔、`./etc` 設定、`./data/[DB_NAME]` 資料、`./tmp` 作業暫存（授權所有檔案操作）、`./logs` 紀錄（`[PROG_NAME]_YYYYMMDD.log`）。
- `source ./setenv.app`：設定 APP_* 路徑、把 `./bin` 加入 PATH、離線 Cargo 設定、Windows Python 路徑、`app_log_file` 函式。
- `./build.sh [--release|--debug] [--no-workspace]`：建置 chewing-cli 與 candidate_inventory → `./bin`，並做工作區檢查；紀錄 `logs/build_YYYYMMDD.log`。
- `./pack-release.sh [版本]`：打包 bin/etc/腳本/P0 文件 → `tmp/release/*.zip` + SHA-256；紀錄 `logs/pack-release_YYYYMMDD.log`。

## P1 輸入與選字狀態機
- 單元測試：`cd analyze/scripts && python -m unittest test_candidate_key_model test_ms_input_model`（22 個）
- 重播：`./build.sh`（會建置 `bin/key_replay.exe`）後 `python analyze/scripts/run_p1_replay.py` → `analyze/p1/replay-results.json`
- 單次重播：`bin/key_replay.exe analyze/p0/dict-rebuild [--space-select] s u 3 c l 3 "<SPACE>"`
- 規格文件：`python analyze/scripts/gen_p1_doc.py` → `analyze/selection/input-state-machine.md`

## 可發行 MSI（2026-11-22）
- `./pack-release.sh`：先呼叫 `./build-msi.sh` 產生 `dist/windows-chewing-tsf-<版本>-local.msi`（+ .sha256），再打工具包 zip；兩者都複製到 `tmp/release/`。`NO_MSI=1` 只打 zip；`MSI_VERSION=` 指定版本（預設 `26.11.<MMDD>`）。
- `./build-msi.sh` 步驟：下載 WiX 6.0.2（NuGet，用已安裝的 .NET 8 執行；MS-RL）→ 以 `msiexec /a` 把官方 MSI 解壓到 `tmp/msi_extract`（只取預編譯元件，不安裝）→ 靜態 CRT 建 x64／x86 `chewing_tip.dll` 與 `tsfreg.exe` → 組裝 `build/installer` → `wix build`。
- 自建：x64／x86 TIP（含 libchewing 修正）、tsfreg、詞庫 *.bin、ARM64X 轉接 DLL（倉庫內預編譯）。**取自官方 724（本倉庫建不出來）**：ChewingPreferences、chewing-editor、chewing_tip_host、chewing-cli、WebView2Loader、ARM64 的 TIP DLL（本機 VS 無 ARM64 函式庫）。
- 對 `.wxs` 的暫存副本做兩項調整（不改 installer/ 原檔）：補上 `chewing_tip_host.exe` 元件（官方 724 有、倉庫 712 版 .wxs 沒有）；移除舊 WiX 不認得的 `UpgradeStrategy` 屬性（`<MajorUpgrade>` 已提供同等行為）。
- 驗證：MSI 以管理映像解壓後，x64／x86／ARM64X 轉接／ARM64／host 的雜湊皆與來源檔相符；x64 TIP 含修正字串。MSI 未簽章。
