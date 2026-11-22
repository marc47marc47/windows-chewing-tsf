# 微軟字詞排序 → 新酷音（P3／P5 部分成果，2026-11-22）

## 已完成（有證據）
1. **比較器解碼**：`CStncCandList::NewCompItemLegacy` 180059db0（模式 6「舊式／固定順序」）、`NewCompItemLenAsc/LenDes` 180059e10/e50（模式 3/4，依長度再依模型分數）、`Sort` 18005a820（接受模式 3/4/5/6/9/11）、`NewSort` 180059fb0。
   舊式比較：①字數少者在前 ②兩者皆有「舊式序號」(+0x4e) 時比序號，有序號者先於無序號者 ③否則比 Unicode 序列（擴充 A U+3400..U+4DB5 排在其他 BMP 之後，增補平面最後）④原位置。
2. **序號資料全量匯出**：`ms-char-order.tsv`（`export_ms_char_order.py`）：IMTCPH 1,484 個讀音＋IMTCPHCS 1,303 個讀音，共 63,871 個字元，來源 `analyze/imd/*.order.csv`（CDicCharIDPH 順位表）。
3. **chewing 實作（預設關閉）**：`libchewing/src/editor/legacy_order.rs`；選項 `EditorOptions::ms_legacy_candidate_order`；`Editor::set_legacy_order`；`Editor::chewing` 在搜尋路徑找到 `ms_char_order.tsv` 時自動載入。TSF 設定登錄值 `MsLegacyCandidateOrder`（預設 0）。4 個單元測試；libchewing 全測 133 通過。
4. **全量驗證**：`legacy_order_check.exe` 對 1,519 個讀音、26,112 筆候選（其中 26,021 筆有微軟序號）逐一檢查：有序號者依序號遞增、皆在無序號者之前、同長度分組，**違規 0**，資料列解析略過 0（`legacy-order-check.txt`）。
5. **與 chewing 現況比較**（`char-order-comparison.json`，1,519 個讀音全量）：chewing 原始詞庫順序與微軟順序完全相同者 516 個、第一名相同 1,373 個、平均 Kendall τ=0.787；chewing 依頻率排序（`sort_candidates_by_frequency`）後相同 388 個、第一名相同 1,017、τ=0.547。

## 新證據：固定候選順序設定與舊式序號的關係（2026-11-22）
- `CPhoneticConv::AddSylCharIDListToRawLatt` 180047848 對每個讀音的字元清單先呼叫設定物件 vtbl+0x170（＝`CIMEditorCfg::IsFixedCandOrder`，config 0x13b，使用者登錄值 `Fixed Candidate Order.New Phonetic`）：**非 0 時**才以 `CIMEditorDic::GetLegacyOrder` 取得每個字的讀音序號，打包進格網節點集合（高 16 位為序號，低位為旗標；`CRawLatt::AddRawNode` 18009c760 存入節點 +0x38），並把「序號最小的字以外」的節點標記旗標位 1；**為 0 時**序號清為 0、不附序號。
- 因此微軟只在「固定候選順序」開啟時才使用舊式序號；使用者目前設定為 0＝微軟預設走分數序（模式 3/4），**不是**本次移植的舊式序。我們的 `ms_legacy_candidate_order` 對應「固定候選順序＝開」的狀態，語義一致。
- 統計字序表：`CDic+0x80` 僅在建構與 Close 被清零、全程無寫入，`GetScoreByStatCharOrder` 恆回傳預設 65535.5，僅影響提示模式 5；與模式 3/4 無關（它們比較候選項自己的 +0x20/+0x24 浮點分數）。
- 未決：「序號最小以外的節點」旗標位 1 在整句解碼中的用途未追到（可能影響預設轉換字），故**未**移植到轉換引擎，只移植候選清單順序。

## 未完成／不能宣稱
- 微軟預設（固定候選順序＝0）走分數序（模式 3/4：長度、旗標、候選項 +0x20/+0x24 浮點分數、Unicode）；分數來自語言模型與學習 factor 的建構路徑，尚未移植、也無實機可驗證（I11）。本成果對應的是**固定候選順序＝開**，不是微軟預設順序。
- 多字詞：舊式模式下詞沒有序號，只比長度與 Unicode；其他模式的詞順序（模型分數）尚未移植。
- 微軟有 37,850 個字元（相對這些讀音）不在 chewing 詞庫中，本次只重排既有候選，不新增候選。
- 本機沒有微軟注音實機輸出可對照（I11）；全部為靜態證據＋chewing 側全量驗證。
- **發佈限制（I06）**：`ms-char-order.tsv` 由微軟詞庫衍生，未放入安裝程式或 libchewing/data；僅本機放在 CHEWING_PATH 目錄時啟用。

## 重現
```
python analyze/scripts/export_ms_char_order.py
cut -f1 analyze/p3/ms-char-order.tsv | sort -u > tmp/ms_readings.txt
libchewing/target/release/examples/raw_order.exe analyze/p0/dict-rebuild tmp/ms_readings.txt > tmp/chewing_raw_vs_ranked.tsv
python analyze/scripts/compare_char_order.py
libchewing/target/release/examples/legacy_order_check.exe analyze/p0/dict-rebuild analyze/p3/ms-char-order.tsv
libchewing/target/release/examples/key_replay.exe analyze/p0/dict-rebuild --ms-order analyze/p3/ms-char-order.tsv --page-size 9 g 4 "<DOWN>"
```

## 啟用方式（2026-11-22）
設定程式 `ChewingPreferences.exe` 是預先編譯的外部檔案（installer 僅引用，原始碼不在本倉庫），因此**沒有**加入設定畫面選項。目前啟用步驟：
1. 把 `analyze/p3/ms-char-order.tsv` 複製為 `ms_char_order.tsv`，放到詞庫目錄（`CHEWING_PATH` 或安裝目錄的 `Dictionary`）。
2. 設定登錄值（輸入法自動重新載入設定）：
   `reg add "HKCU\Software\ChewingTextService" /v MsLegacyCandidateOrder /t REG_DWORD /d 1 /f`；關閉改 `/d 0`。
3. 建議同時設定 `SelAreaLen`＝9（微軟每頁 9 項）；是否同時設 `ShowCandWithSpaceKey`＝1 見 `analyze/selection/input-state-machine.md` 第 5 節（P1.6）。
預設值為關閉，有單元測試保護（`chewing_tip_core` `ms_legacy_candidate_order_is_opt_in`）。
