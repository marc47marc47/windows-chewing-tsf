# 微軟注音行為移植至 chewing

建立日期：2026-11-22。狀態：已開工。當前目標：完成 I01～I03。

## 最新檢查點（交接時先讀）

- **P0 階段完成**（P0.3 由使用者輸入後的實測收尾：實際載入的是新酷音，微軟 IMETC 未載入）。
- **I01 進行中**：安裝副本／參考檔及公開符號身分已核對；實際啟用版本、相容模式及載入證據仍未確認。已詢問使用者協助切換／確認微軟注音，不能把登錄 Enable=1 當成載入證明。
- **I02 進行中**：字表、正式綁定詞項與原始順位已全量解析；IMTCT 格式 2 與 PINTLGT 格式 3 已全量模型匯出及靜態查詢交叉檢查。IMTCJ 已完整讀出，但有 1 處初聲順序異常。其餘分支、部分屬性子結構及動態查詢驗證仍未完成。
- **I03 進行中**：已有模式與欄位映射；已確認部分路徑以學習 factor 乘上模型分數。仍需解明完整分數尺度、模式來源、學習更新／衰減／持久化與執行驗證。
- **正式 chewing 排序尚未改動**。本次目標沒有完成，不得因解析器測試通過而將 I01～I03 勾選完成。
- 使用者要求在 Token 剩餘 10% 時停止。目前目標未設 Token 上限，工具回傳 `remainingTokens=null`，無法計算比例；不得把累計使用量當成剩餘額度。本輪先保存此檢查點並停止本輪作業；如後續取得明確上限，依該上限保留 10%。

| 已完成子項 | 全量結果／證據 |
|---|---|
| I02-C01 字元／讀音／順位 | 71,931 筆字元、63,875 筆順位；`analyze/imd/coverage.json` |
| I02-C02 正式綁定詞項與尾字索引 | 186,479 筆，無索引不一致／缺漏／重複；`analyze/imd/test-results.txt` |
| I02-C03 不完整讀音索引擷取 | 132,069 筆，與主詞庫可讀音詞項集合相同；有 1 處排序異常，**排序驗收未通過**；`analyze/imd/incomplete-coverage.json` |
| I02-C04 主要格式 2 模型擷取 | 140,034 個 word ID、5,526,057 個 bigram、9,294,037 個 trigram；`analyze/imd/ngram-coverage.json` |
| I02-C05 模型全量查詢交叉檢查 | 所有儲存的 bigram／trigram 逐筆比對，0 不一致；**不是原生執行 oracle 比較**；`analyze/imd/ngram-lookup-verification.json` |
| I02-C06 模型匯出封存驗證 | 完整讀取 gzip、核對全部列數及 SHA-256；`analyze/imd/ngram-export-manifest.json` |
| I02-C07 PINTLGT 格式 3 擷取與查詢交叉檢查 | 385,787 個 word ID、5,413,665 個 bigram，逐筆查詢 0 不一致；`analyze/imd/bigram3-coverage.json`、`parse_bigram3.py`。元件角色雖名為 PYTrigram，實際為格式 3 bigram backoff；後續原生查詢比對見 C12。 |
| I02-C08 格式 3 匯出封存驗證 | 完整讀取 gzip、核對全部列數與 SHA-256；`analyze/imd/bigram3-export-manifest.json`。 |
| I02-C09 PH 部首／筆畫擷取 | 70,195 筆屬性、兩張各 56,982 筆索引；順序無倒置，但各有相同 3 筆重複及 3 筆缺漏，**集合驗收未通過**；`analyze/imd/character-attributes-coverage.json`。 |
| I02-C10 原生詞項／尾字查詢全量比對 | IMTCL、IMTCLS、IMTCD、IMTCV、PINTLGD 共 678,076 筆詞項及 161,861 個索引桶，與原生查詢函式零差異；`analyze/imd/native-lexical-verification.json`。限隔離物件的 getter，不包含載入、過濾、排序或實際啟用輸入法。 |
| I02-C11 原生部首／筆畫查詢全量比對 | 70,195 筆屬性與兩個原生 getter 零差異，含 packed UTF-16 的補充字參數；同一份 `native-lexical-verification.json`。尚不包含索引範圍搜尋行為。 |
| I02-C12 格式 3 原生模型查詢比對 | 原生 Init 接受來源；全部 385,787 筆 unigram、5,413,665 筆已儲存 bigram、385,787 筆回退及 4 個邊界檢查，float32 位元與旗標零差異；`analyze/imd/native-bigram3-verification.json`。回退僅每列一筆，非所有詞對窮舉。 |
| I02-C13 格式 2 原生模型查詢比對 | 原生 Init 接受來源；140,034 筆 unigram、5,526,057 筆 bigram 索引、9,294,037 筆 trigram 值（含 FindPage）及 140,034 筆缺值檢查，零差異；`analyze/imd/native-ngram-verification.json`。不含外層虛擬 GetBigram／GetTrigram 與回退組合。重跑方式：Windows 版 Python（非 Git Bash 內建）執行 `analyze/scripts/verify_native_ngram.py`。 |
| I02-C14 格式 2 外層原生 GetBigram／GetTrigram 比對 | 經重定位的私有 vftable 與 CFG 派發指標呼叫 CCompressedTboLdr 外層函式；全部 5,526,057 筆儲存 bigram、9,294,037 筆儲存 trigram，加 3,000,000 筆隨機案例（含已存 pair 但缺 trigram 的回退）及 10 筆越界，float32 位元與回退旗標零差異；`analyze/imd/native-ngram-outer-verification.json`、`verify_native_ngram_outer.py`（約 97 秒）。隨機案例為抽樣，非窮舉 N³。不含解碼、排序、學習。 |
| I03-C03 學習更新規則靜態規格 | Adjust Unigram／Bigram 乘法、0.6 重啟用規則、active-learn 0.7 規則、1000 節點 LRU、分數方向（factor<1＝提升）；`analyze/selection/learning-persistence.txt` 新增章節。純靜態，無原生執行比對。 |
| I03-C01 呼叫簽章修正 | 4 個呼叫點簽章修正（含特定 %f 可變參數呼叫）；`analyze/scripts/RepairKnownCalls.java` 與 `analyze/selection/call-overrides/` |
| I03-C02 短期權重與保存規格初稿 | 全部 2,048 個可達距離、205 級權重已匯出；保存布局與 0.6／0.4 除法、0.01～1 篩選已核對指令。`analyze/selection/learning-persistence.txt`、`shortterm-weight-spec.json`；啟用條件與原生比較未完成。 |

下次接續順序：I01 模式／載入證據 → I02 索引異常與剩餘格式／屬性 → I03 因子運算、更新／衰減／保存 → 完整驗收審查。I01 等待回覆時，繼續不依賴其結果的靜態工作。

## 執行與驗證規則

- 全量調查詞彙輸入、組詞、選字排序與學習；不得用少量例句特判代表相容。
- 狀態：待辦／進行中／受阻／待驗證／完成。完成須附產物、命令、結果、證據及未解事項。
- 分開記錄靜態證據、推測與執行驗證。有限上下文測試不能宣稱窮盡所有句子。
- 每階段更新本文件；接手 AI 先讀本文件與最新報告。不重做已驗證成果。
- 預設只修改工作區，不覆寫系統 DLL、安裝中的輸入法或個人學習資料。
- 未確認的模式、欄位與分數不能接入正式排序。新增相容行為先保持可關閉。

## 既有基線（開工時需核對）

- [x] B01 全部 9 個模組取得公開 PDB、套用符號並匯出 10,097 個函式，記錄失敗 0 個。
- [x] B02 匯出 21,195 個公開符號及指令、資料交叉參照。
- [x] B03 完整擷取 4 張候選按鍵表，共 96 筆。
- [x] B04 定位注音解析、詞庫、解碼、CStncCandList 及學習元件。
- [x] B05 chewing 基線：125,575 個讀音、165,258 筆候選；unsupported=0、empty=0。
- [x] B06 核心測試曾達 129 通過、0 失敗、1 略過；主程式檢查曾通過。
- [x] B07 本地核心、詞庫、CLI 及 219 個鎖定版相依套件快取已建立。

證據入口：[現況](analyze/selection/status.txt)、[具名匯出](analyze/modules-symbolized/)、[索引與基準](analyze/selection/)。

## 分階段任務

### P0 固定版本與重現環境

依賴：開工授權（已取得）。

- [x] P0.1 核對 DLL、PDB、詞庫、chewing 版本並保存 SHA-256。證據：`analyze/p0/manifest.json`（`build_p0_manifest.py`）；9/9 系統安裝副本與參考副本 SHA-256 相同；13/13 系統 IMD 與解析快照相同；chewing 無 .git，以 Cargo.lock／詞庫檔雜湊釘選。
- [x] P0.2 驗證 PE/PDB GUID、Age，記錄公開符號的限制。證據：`analyze/symbols/identity-audit.json`；9 個 GUID/DBI age 核對通過，PDB info age 差異依 Microsoft OpenValidate 規則處理，見 `ranking-mapping.txt`。
- [x] P0.3 確認實際啟用版本、相容模式、載入模組及路徑。**已由實測確認（2026-11-22，使用者回報用「微軟注音」輸入後立即量測，`selection/loaded-tip-evidence.json`）**：①實際載入的輸入法 TIP 是**新酷音**：Notepad.exe(pid 31572) 載入 `C:\WINDOWS\system32\chewing_tip_x64_26_11_724.dll`（SHA-256 AC42F266…FBB1；該程序先前無任何 TIP，輸入後才出現）；Notepad++(pid 15660) 載入 `C:\Program Files\ChewingTextService\chewing_tip.dll`（檔案已不在磁碟，為舊版殘留映射）。②全系統可存取處理程序（420 個，186 個存取被拒）**沒有任何** IMTCTIP／IMTCCORE／ChtIME 模組；故微軟 IMETC 引擎在此機器目前不在輸入路徑上，此時「相容模式」對輸入沒有作用。③微軟注音 TIP（CLSID {B115690A-…}）仍為已註冊、使用者語言清單啟用的 profile，InProcServer＝`C:\WINDOWS\system32\IME\IMETC\IMTCTIP.DLL`，其 SHA-256 與分析用參考副本相同（版本 10.0.26100.9818，見 manifest.json）；相容模式控制項為 `HKCU\Software\Microsoft\Input\TSF\Tsf3Override\{B115690A-…}\NoTsf3Override4`（現況：值不存在；其語義僅由靜態分析推論，並做過可還原的暫改實驗，未觀察到差異，因為微軟 TIP 本就未被載入）。④與使用者「已用微軟注音輸入」的口頭說法不符：量測顯示輸入由新酷音處理；使用者語言清單只有微軟注音、但 CTF Assemblies 預設為新酷音，疑為新酷音以微軟注音的語言項目名義被選用或切換未生效，原因未查。**對專案的含意**：分析所用微軟參考二進位（SHA 鎖定）是準確的靜態／原生隔離參考，但本機沒有微軟注音的實機輸出可供動態對照，P3/P4 的動態驗證需另行取得（例如讓微軟注音真正可選）。
- [x] P0.4 不同版本分開保存，不混用位址或結論。證據：`manifest.json` 分 microsoft_reference／microsoft_installed_dicts／chewing 三組；所有位址結論僅適用 SHA-256 E4001110…971E 的 IMTCCORE.DLL（見各驗證 JSON 的 native_reference_sha256）。
- [x] P0.5 保存核心測試、主程式檢查、詞庫建置及全量清單的重現命令。證據：`analyze/p0/REPRODUCE.md`；本輪已實際重跑：核心測試 129 通過／0 失敗／1 略過（12 doctest 通過）、主程式檢查 exit 0、詞庫四個 .bin 重建後與既有檔 SHA-256 相同、全量清單 125,575 讀音／165,258 候選且與既有輸出位元組相同。

驗收：另一個 AI 能重現；實際版本明確；未能觀察的項目有具體紀錄。

### P1 完整輸入與選字狀態機

依賴：P0。

- [x] P1.1 追蹤鍵盤事件至解析、組字、進入選字、提交的流程。證據：`selection/input-state-machine.md` 第 1 節（InvokeEvent→佇列→ControlProvider 堆疊→Candidate/Typing/Compose 控制→提交與學習，含位址）；控制堆疊順序出自 SetupKeyAndCommandControlStack 1800334c4。
- [x] P1.2 解明 96 筆命令、修飾鍵及四表切換條件。證據：`candidate_key_model.py`＋`test_candidate_key_model.py`（11 測試，逐筆覆蓋 96 筆；18 筆被先到先中規則遮蔽，已標出）；旗標位元、表選擇、Tab／左右鍵例外見規格第 3 節。命令名稱為依按鍵綁定推定（消費端在作業系統候選 UI，不在參考二進位內）。
- [x] P1.3 補齊表外的進入選字、聲調完成、編輯、取消及提交行為。證據：`ms_input_model.py`＋`test_ms_input_model.py`（11 測試）涵蓋輸入層（CTypingControl::HandleKeyEvent）、候選層（Enter／Esc／Space／翻頁／方向／數字／版面）與組字層路由；聲調完成＝Space 進注音剖析器（CPhoneticConv::OnSpace）。組字層 Delete／Home／End／方向鍵邊界與 Esc（設定 0x12b）未解，見規格第 6 節。
- [x] P1.4 列出空輸入、未完成注音、完成音節、未提交文字、候選、英文及符號模式的所有已辨識轉移。證據：規格第 2 節三張分派表（無輸入／輸入中／已組字／候選）；**英文與符號模式未解碼**（符號輸入僅見 CSymbolWrap::OnTypingInput 的空白路徑），已於規格第 6 節列為障礙，不計為已辨識轉移。
- [x] P1.5 建立微軟與 chewing 的操作重播與結果對照。證據：`libchewing/examples/key_replay.rs`（隔離、記憶體內使用者資料）、`run_p1_replay.py`、`analyze/p1/replay-results.json`；18 個情境：SAME 10、DIFF_OPTION 2、DIFF_STRUCTURAL 3（S09 索引游標環繞、S11 候選內 Enter、S17 輸入中 Tab／Delete）、MS_UNDECODED 3（S03、S10、S15，未宣稱結論）。
- [x] P1.6 定義 Space 開啟選字，保留第一聲、正常空白與候選內操作。證據：規格第 5 節；S05 以 `space_is_select_key=true` 驗證四條件全成立（已組字開選字、空緩衝為一般空白、ㄇㄚ＋Space＝嗎、候選內 Space 換頁）；不做全域 Space→Down 替換。實作僅需把該選項做成可關閉的相容設定（P5.1）。

驗收：每個命令與轉移均有證據、測試或明列障礙，不採全域 Space→Down 替換。

### P2 微軟詞庫與原始順位全量解碼

依賴：P0；可與 P1 獨立推進。

- [ ] P2.1 列舉實際使用的系統詞庫、使用者資料及載入條件。
- [ ] P2.2 解明 IMD 標頭、節區、索引、壓縮、編碼與版本差異。
- [ ] P2.3 解明讀音、字元、詞項 ID、Unicode、多音字、罕用字及補充平面映射。
- [ ] P2.4 實作唯讀解析器，檢查損壞、長度、索引及偏移。
- [ ] P2.5 全量匯出讀音、詞項、原始順序與已確認分數／旗標，保留來源。
- [ ] P2.6 每節區記錄總量、成功量、未解量及原因，不靜默略過。
- [ ] P2.7 以原生查詢或其他獨立證據交叉驗證解析結果。

驗收：所有相關檔案及節區已盤點；全量數量可核對；未知資料不得計為成功。

### P3 排序、解碼與學習語義

完整驗收依賴：P1、P2；可先調查不依賴未解資料的靜態規則。

- [ ] P3.1 解明模式 3、4、5、6、9、11 的來源、條件及用途。
- [ ] P3.2 解明長度、來源旗標、切換、提示、原始順位、同分比較、去重及索引回寫。 **部分完成**：模式 6（舊式／固定順序）比較器與序號資料已全量解明並移植（`analyze/p3/README.md`）；模式 3/4 的模型分數、模式 5 提示、模式 11 切換的完整規格仍待完成，故不勾選。
- [ ] P3.3 追蹤候選分數、字元統計與語言模型的產生和使用位置。
- [ ] P3.4 確認實際啟用的 unigram/bigram/trigram、搜尋及剪枝。
- [ ] P3.5 解明選字、重複使用、上下文、衰減、短期學習及持久化。
- [ ] P3.6 建立欄位與單位對照，區分機率、log 機率、乘數、排序值及旗標。
- [ ] P3.7 為所有已辨識模式建立輸入、比較條件及輸出規格。

驗收：每條規則可追溯到函式和資料；靜態與動態證據分開；不直接混用兩套引擎分數。

### P4 全量比較工具與差異分類

依賴：P2、P3。

- [ ] P4.1 統一查詢：讀音、上下文、模式、設定、初始學習狀態、操作序列。
- [ ] P4.2 統一結果：候選全集與順序、範圍、提交、學習前後狀態及版本。
- [ ] P4.3 以兩邊全部已解析讀音／詞彙聯集建立全量集合。
- [ ] P4.4 比較缺詞、多詞、順序、首選、長度及多音字。
- [ ] P4.5 生成全部排序模式、邊界及狀態轉移測試，公開有限上下文的生成規則。
- [ ] P4.6 分類詞庫、解析、範圍、評分、排序、去重、學習及 UI 差異。
- [ ] P4.7 保存逐筆差異與統計，不只保存通過案例或首選率。

驗收：相同快照可重現；所有查詢有結果或錯誤；工具成功不等於相容成功。

### P5 分項移植至 chewing

依賴：P4；每項修改須有已確認規格。

- [ ] P5.1 新增可關閉的相容設定，保留原有行為。
- [ ] P5.2 移植輸入、選字狀態與 Space 操作。
- [ ] P5.3 實作資料轉換及 ID 映射，記錄版本與來源，不靜默丟棄。
- [ ] P5.4 移植候選產生、模式、同分比較及去重。 **部分完成**：舊式候選順序（模式 6）已以可關閉選項移植到 libchewing（`legacy_order.rs`、`EditorOptions::ms_legacy_candidate_order`、TSF 登錄值 `MsLegacyCandidateOrder`），全量驗證違規 0；其他模式與去重未做，故不勾選。
- [ ] P5.5 移植已確認上下文評分與解碼。
- [ ] P5.6 移植學習，使用隔離資料，不覆寫既有詞庫。
- [ ] P5.7 每項修改重跑對應全量比較，保存前後差異。
- [ ] P5.8 記錄公共 API、設定、檔案格式與向後相容性。

驗收：規格、回歸與全量差異齊備，新增不一致需說明。預設採本地 chewing 實作與可轉換資料；若需依賴微軟 DLL，先登錄決策議題。

### P6 整合與完成判定

依賴：P5。

- [ ] P6.1 核心測試、主程式檢查、實際建置及 Windows 操作驗證。
- [ ] P6.2 驗證第一聲、空白、候選操作、取消、提交、標點、英文及應用程式相容性。
- [ ] P6.3 驗證重啟後學習一致性、舊資料遷移與回復。
- [ ] P6.4 測量耗時、記憶體及操作延遲，保存環境和基準。
- [ ] P6.5 重跑所有已解析資料、模式及轉移的比較。
- [ ] P6.6 交付建置、使用、轉換、回復與限制說明。

驗收：範圍內無未解釋差異；所有例外與未知均明列。存在未知時不得宣稱全面相容。

## 議題與決策

| ID | 議題 | 狀態 | 完成條件 |
|---|---|---|---|
| I01 | 實際使用版本與參考 DLL 是否相同 | 進行中 | P0 的載入與版本證據；差異有可追溯處理 |
| I02 | 微軟詞庫格式與資料能否完整轉換 | 進行中 | 全節區盤點、格式規格、解析與交叉驗證；限制明列 |
| I03 | 全部排序模式與學習權重如何映射到 chewing | 進行中 | 模式、欄位、單位、資料流與映射規格，未知不得計為完成 |
| I04 | 個人歷史及既有詞庫遷移 | 待調查 | 隔離驗證、遷移及回復規格 |
| I05 | 相容設定是否成為預設 | 待決策 | 全量比較後由使用者決定 |
| I06 | 微軟資料／DLL 的交付依賴 | 待評估 | 確認技術需求與來源後提出具體方案 |
| I07 | 間接呼叫簽章缺失造成偽碼語義誤判 | 進行中 | 每個移植所用的間接呼叫需核對簽章及指令，不能以「反編譯成功」代替語義驗證 |
| I08 | IMTCJ 初聲索引的 1 處原始順序異常 | 靜態模擬完成，待原生驗證 | 核對位置 11275→11276、word ID 112148→127124，確認與原生查詢的影響；不能靜默重排或視為已解決 |
| I09 | PH 部首／筆畫索引重複與缺漏 | 靜態判讀完成，待原生範圍搜尋驗證 | 兩索引均重複 Unicode scalar 22232、27366、29499；缺少非零屬性 scalar 22248、27364、29755。核對原生語義與來源，不靜默去重或補字；證據 `character-attributes-coverage.json` |
| I10 | PY 分支尾字索引與原始詞項差異 | 暫緩（拼音分支，非注音範圍） | 套用目前布局得到 120 筆 posting 不一致、14,261 個未被索引詞 ID、20 個重複詞 ID；需確認 PY 的 ID 共用／載入規則，不先判定為來源損壞；證據 `pinyin-index-differences.json` |

| I11 | 本機微軟注音無法實機啟用，缺動態對照 | 已繞過（見 2026-11-22 TIP 內嵌主機紀錄） | 實測顯示輸入由新酷音處理、IMETC 未載入（`loaded-tip-evidence.json`）；需讓微軟注音真正可選，或由使用者同意 P3／P4 僅用靜態＋原生隔離證據 |
決策：D01 全量機制與資料、不做例句特判；D02 證據及比較先於正式排序；D03 使用者已說「開工」，授權 I01～I03。

新增議題格式：日期、影響任務、證據、選項、決策者、結論。

## 工作紀錄

### 2026-11-22／AI

- 任務：建立追蹤文件；開始 I01～I03。
- 結果：計畫落檔，保留全部階段與驗收條件。
- 下一步：核對載入版本、PDB 身分及詞庫來源；後續證據存於 analyze。

後續每筆紀錄：日期／執行者、任務 ID、本次完成、命令及結果、證據、新議題、狀態變更、下次起點。

### 2026-11-22／AI：I01 初步核對

- 核對本地參考與系統安裝副本的版本、SHA-256；結果存於 `analyze/selection/installed-version-comparison.json`。
- 核心與 TIP 版本為 `10.0.26100.9818`，其參考副本與系統副本 SHA-256 相同。
- 系統安裝副本相同不等於執行中已載入，I01 保持進行中；下一步確認啟用的 TSF profile、相容模式及載入證據。

### 2026-11-22／AI：I01～I03 全量解碼與交叉驗證

- I01：唯讀 `probe_runtime.ps1` 確認使用者微軟注音 profile Enable=1，InProcServer 指向參考 DLL 對應位置；LocalServer 指向 ChtIME.exe。執行環境的 GetForegroundWindow 回傳 0，不能將呼叫執行緒的 HKL 當作記事本目前 profile。
- 使用者提供空白記事本；已觀察注音組字並用 Escape 取消，最後觀察為空白頁。尚未取得實際微軟注音版本／相容模式的可靠載入證據，已詢問使用者協助確認，I01 不標完成。
- PDB：9 個 GUID 相符；PE age=1、PDB info age=3、DBI age=1，符合 Microsoft OpenValidate 接受規則。`validate_symbols.py` 與 `identity-audit.json` 可重跑。
- I02：從 DLL RCDATA 還原全部 42 個注音／聲調編碼；盤點全部 13 個 IMD，擷取 41 筆元件 ID／檔名／角色綁定。
- I02：2 份字表共 71,931 個字元，63,875 個順位記錄逐筆讀音核對無不一致；主／補充／虛擬 3 份詞庫共 186,479 個詞項，尾字反向索引逐筆核對無不一致、缺漏或重複。
- IMTCD 123,958 個 raw 詞項未取得目前載入綁定，只保留 provisional 欄位，不混入正式文字成果。詞庫內無指定讀音記錄保留統計，未靜默丟棄。
- 驗證命令：`python analyze/scripts/test_imd_parser.py`；7 個測試通過，涵蓋完整已解析語料及損壞輸入。結果：`analyze/imd/test-results.txt`。
- 規格與未知範圍：`analyze/imd/FORMAT.txt`；逐檔雜湊／節區／統計：`analyze/imd/coverage.json`。壓縮語言模型、不完整讀音索引與部分子結構仍未完成，I02 保持進行中。
- I03：整理所有已辨識排序模式與學習讀取路徑，見 `analyze/selection/ranking-mapping.txt`。尚未完成單位、學習更新與動態驗證。
- I07：證實 CImeDicWrap::GetBigramFactor 的原偽碼錯誤顯示固定 0.0。補入 18009d537 呼叫簽章後，偽碼與 18009d53c 指令一致，回傳輸出 factor。產物：`analyze/selection/call-overrides/CImeDicWrap_GetBigramFactor.c`；Ghidra 腳本執行及保存成功。
- 下一步：取得 I01 的實際模式／載入證據；繼續 I02 的 IMTCT 壓縮模型與 IMTCJ 索引；沿已修正的 factor 呼叫追查 I03 評分運算與學習更新。

### 2026-11-22／AI：模型全量解析完成；更新狀態後停止本輪

- 上一筆紀錄所列 IMTCT 主模型的靜態解析已完成：格式 2、143 pages、140,034 個 word ID、5,526,057 個 bigram、9,294,037 個 trigram。
- 執行 `python analyze/scripts/parse_ngram.py --export`，保留全部量化索引、5 組 codebook 及其原始 bytes，沒有剪枝或未經證實的 log-base 轉換。
- 執行 `python analyze/scripts/verify_ngram.py`，對所有儲存的 bigram／trigram 使用隨機存取查詢交叉檢查，0 不一致；約 61.4 秒。這驗證解析索引與查詢一致性，未冒充微軟原生 oracle。
- 執行 `python analyze/scripts/seal_ngram_exports.py`，完整讀取匯出 gzip 並核對列數、CRC 與 SHA-256，結果見 `ngram-export-manifest.json`。
- 執行 `python analyze/scripts/parse_incomplete.py`，IMTCJ 全部 132,069 筆 ID 與主詞庫可讀音集合完全對上，沒有缺漏或多出；初聲順序檢查有 1 處異常，已登錄 I08，未修寫來源。
- 延伸修正 GetTrigram 兩個間接呼叫的輸出指標簽章，證實查詢使用動態 pair index，而非原偽碼誤顯示的固定 0；Ghidra 執行及保存成功，證據為 `call-overrides/CCompressedTboLdr_GetTrigram.c`。
- I03：已追到補充單字候選中，調整後分數與原始分數分別進入 +0x20／+0x24；部分路徑會乘上持久及 active unigram factor。路徑評分中也有 bigram factor 乘法。完整語義尚未完成，不直接塞入 chewing 的 log 歷史機率。
- 本輪停止條件：使用者要求保留 10% Token；目前沒有可計算的 Token 上限，已記錄限制並保留交接點。未將目標標為完成，也未自行更改目標範圍。

### 2026-11-22／AI：格式 3 封存與部首／筆畫全量擷取

- 確認前次格式 3 解析已終止且成功，未重啟重複工作。執行 `python analyze/scripts/seal_ngram_exports.py --format 3`，385,787 筆 unigram 與 5,413,665 筆 bigram 匯出完整讀取與雜湊完成。
- 執行 `python analyze/scripts/parse_character_attributes.py`，依 fOpenLex、UnicodeToRadical、UnicodeToStroke 的索引公式擷取全部 PH 屬性及兩張反向索引。部首上限 214、筆畫上限 64，超界 0；70,195 個屬性槽中 56,982 個非零，保留 2 bytes padding。
- 兩張索引各 56,982 筆，排序倒置 0；但集合有相同 3 筆重複與 3 筆缺漏，登錄 I09。尚未驗證原生範圍查詢邊界，不宣稱完整相容。
- I01～I03 保持進行中；下一步追查 I08／I09 原生行為、其餘分支和補充屬性布局，再補齊學習因子的更新與持久化規格。

### 2026-11-22／AI：短期權重與持久化規格

- I09：重複／缺漏的三對字元各自具有相同部首及筆畫值，因此索引排序檢查仍能通過；這不能證明是合法別名，I09 保持待調查。
- I03：核對 ShortTermWeight 指令，還原全部 205 級權重及 2,048 個可達距離。執行 `python analyze/scripts/export_shortterm_weights.py` 成功；保存來源 SHA-256、float32 位元及原始倍率常數。
- I03：確認 USERLERN 保存布局，以及 unigram 條件除以 0.6、bigram 除以 0.4 後篩選至 [0.01,1]；不是直接原封保存所有 factor，也未證明保存會改寫記憶體因子。
- 新規格 `analyze/selection/learning-persistence.txt` 明列原生位址、指令、未解的設定／呼叫條件。ProcessLearningData 的浮點掃描輸出仍有 I07 類型遺漏，不採用原偽碼固定 0 的結論。
- 下一步：補修文字匯入的浮點資料流、追查保存呼叫條件與設定來源，再建立隔離的學習更新／保存對照；I01～I03 未完成。

### 2026-11-22／AI：修復文字匯入資料流

- 在 Ghidra 針對 ProcessLearningData 的 180067b0c 補入 input、format、float* 簽章；修正後的 C 顯示 %f 結果實際傳入 RegisterUnigram／RegisterBigram，與 180067b42／180067ba9 MOVSS 一致。
- 執行 RepairKnownCalls.java 成功並保存專案；產物 `analyze/selection/call-overrides/CStatisLearn_ProcessLearningData.c`。只改分析專案，未修改 DLL。
- 確認 ImportLearningFile 成功後 this+0x70=0，導致後續 unigram 保存略過 0.6 除法；其他修改點仍待盤點。直接保存呼叫者已找到 SaveUserData 與析構函式，上層觸發仍未完整。
- 更新 `learning-persistence.txt`，分開文字匯入的乘法更新與磁碟保存時的縮放，保留錯誤行／部分匯入／原生執行對照等未解事項。
- I01～I03 保持進行中；下一步建立隔離資料的學習更新與保存對照，並繼續未解資料分支與實際啟用模式核對。

### 2026-11-22／AI：PY 分支 raw 匯出與差異

- 核對 CDicCharIDPHS::fOpenLex 18007e090：清空屬性指標，未讀取第一區塊。不把未使用區塊宣稱為已解碼，也不套用 PH 的部首／筆畫布局。
- `python analyze/scripts/export_pinyin_lexicon.py` 匯出 26,894 個字元及 367,639 個詞項；讀音保留 raw uint16，未使用注音 EPX 解碼；所有詞項引用的字元 ID 均可找到。
- 驗證退出碼 1：PY 尾字索引不符合 PH 分支目前的不變式，差異全量保存於 `analyze/imd/pinyin-index-differences.json`；未計為成功轉換，新增 I10。
- 覆蓋統計及來源雜湊：`analyze/imd/pinyin-lexical-coverage.json`；原始詞項與字表 CSV 保留供核對，不接入 chewing。
- 下一步：追查 PY 的字元 ID／詞 ID 正規化或共用規則，再處理 I10；並續查 I08、I09 與學習持久化。I01～I03 仍未完成。

### 2026-11-22／AI：隔離原生查詢比對

- 新增 `python analyze/scripts/verify_native_lexical.py`，僅對固定 SHA-256 的工作區參考 DLL 執行三個已核對的查詢函式；使用 DONT_RESOLVE_DLL_REFERENCES，不執行 DllMain，不呼叫匯入函式，不讀寫個人資料。
- 物件欄位依 fOpen 已確認布局建立於獨立緩衝區；對 IMTCL、IMTCD、IMTCV、PINTLGD 全部詞項比對長度與字元串，並比對所有尾字桶。結果：644,347 筆詞項、128,132 個桶，零差異，退出碼 0。
- I10 的異常 posting 也由原生 getter 回傳相同結果，排除目前三個 getter 的解析誤差；尚未證明載入或上層正規化語義，因此 I10 不關閉。
- 證據：`analyze/imd/native-lexical-verification.json`、`native-lexical-run.log`。此項不證明 fOpen、補充字 getter、語言模型、篩選、排序、學習或實際啟用版本相容。
- 下一步：以同等隔離方法擴充補充字及模型查詢；再核對 I08／I09 與 I10 上層規則。I01～I03 仍未完成。

### 2026-11-22／AI：補充字與屬性原生比對

- 擴充 `verify_native_lexical.py` 使用 CDicSurrogateLex::WordIDToCharIDStrPtr 180073f48，核對 IMTCLS 全部 33,729 筆詞項與尾字桶，零差異；五份詞庫合計 678,076 筆詞項、161,861 個桶。
- 同一隔離程序加入 UnicodeToRadical／UnicodeToStroke，對已匯出全部 70,195 個屬性槽逐筆比對，補充字參數使用 packed UTF-16；零差異。
- 重跑驗證退出碼 0，報告及 log 已更新。未執行 DLL 進入點，未啟動輸入法，也未讀寫個人學習資料。
- I09 仍開放：屬性查詢已一致，不代表部首／筆畫反向索引的重複／缺漏已解釋。下一步原生模型查詢與索引範圍搜尋、完整載入／模式證據仍待完成。

### 2026-11-22／AI：格式 3 原生查詢驗證

- 新增並執行 `python analyze/scripts/verify_native_bigram3.py`，使用固定版本參考 DLL 的 Init 1800c3a40、GetUnigram 1800c3a00、GetBigram 1800c38c0；三函式無匯入呼叫，使用隔離模型副本與物件，不執行 DLL 進入點。
- 原生 Init 成功；385,787 筆 unigram、5,413,665 筆儲存 bigram、每個前詞一筆缺值回退及 4 個越界／停用檢查，float32 位元與 fallback flag 零差異，退出碼 0；約 6.7 秒。
- 證據 `analyze/imd/native-bigram3-verification.json` 與 `native-bigram3-run.log`。明列回退不是全部詞對窮舉，尚不涵蓋格式 2 模型、解碼器、排序、學習或實際啟用輸入法。
- 下一步：核對格式 2 的原生查詢與間接呼叫依賴，繼續 I08／I09／I10 上層語義及 I01 載入證據；I01～I03 仍未完成。

### 2026-11-22／AI：格式 2 原生查詢驗證補記
- 前輪已產生 `verify_native_ngram.py` 與結果但未寫入本文件；本輪以 Windows 版 Python 重跑，結果相同（零差異、約 19.7 秒），補登 I02-C13。
- 注意：Git Bash 內建 python 為 msys 版，會因 `os.name!='nt'` 拒絕執行原生驗證腳本。
- 下一步：外層 GetBigram／GetTrigram 回退組合、I08／I09／I10 上層語義、I03 學習更新與保存對照；I01 仍待使用者確認載入證據。I01～I03 未完成。

### 2026-11-22／AI：格式 2 外層回退組合原生驗證
- 新增 `verify_native_ngram_outer.py`：僅在本程序私有映像副本重定位 vftable 槽及 `__guard_dispatch_icall_fptr`（0x1800d2498 → 0x1800c3f90），不執行 DllMain、不呼叫匯入函式、不改 DLL 檔。
- 結果零差異（I02-C14）。回退規則已由原生執行確認：bigram 缺值＝unigram 回退(前詞)＋unigram(後詞)；trigram 前置 pair 缺＝bigram(w2,w3)；pair 在而 trigram 缺＝bigram(w2,w3)＋pair 碼高 4 位的回退碼表；越界回傳 this+0x28（測試設 -500.0）並設旗標 1。
- 下一步：I08／I09／I10 上層語義，再進 I03 學習更新與保存對照。I01～I03 未完成。

### 2026-11-22／AI：I08 查詢影響靜態模擬
- 新增 `analyze/scripts/simulate_incomplete_search.py`，依 EpxStrToWordIDList 18007 4524 的二分搜尋與等值區間展開、CompareInitialEpxStrWithWordID 的前綴比較語義，對全部 33,693 個相異初聲前綴（315,672 組詞項／前綴）模擬；結果 `analyze/imd/incomplete-search-emulation.json`。
- 結果：僅 4 個詞 ID（112148 一個三國、127124 為國爭光、126826 溫故知新、132384 言歸正傳）在前綴長度 3 與 4 的查詢不會被找到；其餘 315,664 組皆可達。這是靜態模擬，不是原生執行，I08 不關閉。
- 移植含義：chewing 若以雜湊／Trie 建索引，這 4 詞會比原生多出現；是否複製此缺陷待 I05 決策，不靜默重排或修補。
- 下一步：I09／I10 上層語義，再進 I03 學習更新與保存對照。

### 2026-11-22／AI：I09 判讀與 I10 範圍判定
- I09：三組重複／缺漏皆為「索引中第二筆重複項，正好落在缺漏字元的排序位置，且兩字的部首／筆畫相同」：22232 囘／22248 囨（13,5）、27366 櫦／27364 櫤（75,19）、29499 猻／29755 琻（94,13）；十六進位各僅差一個位元組內的數碼。判讀為來源索引資料的筆誤，非合法別名。影響：依部首／筆畫範圍搜尋時，重複字出現兩次，缺漏字（囨、櫤、琻）找不到。原生範圍搜尋函式尚未執行驗證，因此仍不關閉；移植時是否複製此缺陷待 I05 決策，不靜默補字。
- I10：差異集中在 PINTLGD 的低編號詞 ID（6402～約 6600）與兩個詞（6433、29458）被 51 個連續桶重複；三個原生 getter 與本解析結果一致，故問題不在 getter 解析而在 PY 載入／ID 語義。PY 為拼音輸入分支，本專案目標（注音行為移植）不使用，且 PY 排序模式未納入目前模式清單。暫緩，不納入 I01～I03 完成條件；若後續納入拼音需重開。證據 `pinyin-index-differences.json`。
- 下一步：I03 學習更新與保存對照（`learning-persistence.txt` 未解項）；I01 仍待使用者確認。

### 2026-11-22／AI：I03 學習更新語義（靜態）
- 解明 AdjustUnigramFactor／AdjustBigramFactor／InactiveUnigramFactor／ActiveLearnFromContext／GetActive*／Get*Factor 的偽碼；結果寫入 `learning-persistence.txt`「學習更新語義」。
- 重點：模型分數為負對數，factor 乘上去，<1 為提升；持久保存只留 [0.01,1]；容量 1000 節點淘汰而非時間衰減；選定 unigram 乘 f 並可再乘 0.6，同讀音其他詞僅被重啟用；active-learn 以文件上下文乘 0.7。
- 未解：ProcessCommands 7／8 的 factor 來源、一般選字提交至學習的完整路徑、GetPair 第 4 參數、active 與持久 factor 的排序合成、原生執行對照。I03 不完成。
- 下一步：追 CCandConv 一般選字 OnFinalize 到 Adjust*／AppendContext；找 factor 常數來源；建立隔離學習物件的原生更新對照。I01 仍待使用者確認載入證據。

### 2026-11-22／AI：I03 一般選字提交路徑
- 追到 CImeSentenceWrap::LearnContext → CImeUserDataMgr::LearnContext → CStncLearn::LearnFromContext → CDicShortTerm::AppendContext：一般選字寫入 2048 槽短期上下文環（含後綴索引），不呼叫 Adjust Unigram／Bigram。規格寫入 `learning-persistence.txt`「一般選字提交的學習路徑」。
- 因此 chewing 對應：短期環＋距離權重（已有 205 級表）為主要學習；Adjust* 只對應文字匯入／命令。仍為靜態證據，無原生執行對照。
- 未解：短期權重與模型分數的合成位置、RefreshStatisticalLearningUsage、broker 模式服務端行為。I03 不完成。
- 下一步：在 ranking-mapping 追短期權重（GetWeight 回傳的 log 值）進入候選分數的運算點；之後做隔離 CDicShortTerm 原生對照。

### 2026-11-22／AI：I03 短期／長期詞權重介面
- 還原 CImeUserDataMgr::GetCandidateWeight（0.8−raw×0.2）、GetLatticeWeight（短期類 raw>0 時 0.83−raw×0.1，否則 1.0）、GetInternalScore（長期類 3.0）；詞 ID 類別 0x4xxxxx 長期、0x5xxxxx 短期。常數經 IEEE754 換算核對。寫入 `learning-persistence.txt`。
- 未解：上述三方法的呼叫者及所乘的分數（候選產生／格網評分），尚無原生執行對照。I03 不完成。
- 下一步：從 GetLatticeWeight／GetCandidateWeight 的呼叫者往上追到候選排序；之後建立隔離 CDicShortTerm 對照。I01 仍待使用者確認載入證據。

### 2026-11-22／AI：I03 格網節點權重與詞 ID 類別
- 以組語確認 GetLatticeWeight 回傳值（XMM0→XMM1）傳入格網節點虛擬方法 +0x40，反編譯遺漏（I07 類型）；三個呼叫點 1800ab6a4／1800abb74／1800ac0f1。
- 還原 CImeLexMgr::GetLatticeWeight 的類別／詞長權重表（0.1／0.8／0.9／1.0）與詞 ID 類別對照，寫入 `ranking-mapping.txt`「格網節點權重」。
- 未解：型別 2/3/4/9/10 對應的實體詞庫、節點權重併入路徑分數的位置、候選權重（GetCandidateWeight）的排序用法。靜態證據，無原生對照。I03 不完成。
- 下一步：核對格網節點 vtable +0x40 的名稱與路徑分數運算；把型別對應到 13 個 IMD 的元件綁定（component-bindings）。I01 仍待使用者確認。

### 2026-11-22／AI：I03 詞 ID 類別對應實體詞庫
- 由 CDic::InitData→CDicLexicon::fInit 的參數與 CheckWordIDType／WordIDToCharIDStrPtr 還原類別對照：0x0 主詞庫 IMTCL、0x8 補充字 IMTCLS、0x3 Virtual IMTCV、0x6 外掛、0x2／0x7 使用者造詞、0x4／0x5 學習詞；0x1／0x9／0xa 三類在此版本槽位恆為空（只見歸零，無寫入）。寫入 `ranking-mapping.txt`。
- 因此格網權重實際生效的類別：使用者造詞 0.1、Virtual 詞 0.8／0.9（依長度）、短期學習詞 0.83−raw×0.1，其餘 1.0。IMTCV 詞項已全量解析（19,117）。
- 未解：CT 變體（IMTCCT*）索引對應；節點 vtable +0x40 的名稱與路徑分數運算；一般詞庫詞是否另有其他權重來源。靜態證據。I03 不完成。
- 下一步：核對 ILmLatticeNodePrivate vtable +0x40 的函式並追路徑分數公式（解碼器 Viterbi/beam）。I01 仍待使用者確認。

### 2026-11-22／AI：P0.3 更正（先前誤標完成）
- 先前以「未能觀察項目有具體紀錄」將 P0.3 標為完成並宣稱 P0 完成，與其自身「載入證據未取得」矛盾，已更正：P0.3 回到未完成，P0 未完成。
- 新增：相容模式控制項定位（Tsf3Override／NoTsf3Override4／ConfigureImeVer）；可還原登錄實驗（備份 `analyze/p0/registry-backup-Tsf3Override.reg`、`registry-backup-TSF-parent.reg`；暫加 NoTsf3Override4=1 後刪除，已驗證還原）；探針 `probe_win32_edit_tip.py [msbopomofo|chewing]`（對照組不穩定，不可作為否定證據）。
- 新增專案慣例檔：`setenv.app`、`build.sh`、`pack-release.sh`、`./bin ./etc ./data ./tmp ./logs`；已實際執行 build.sh 與 pack-release.sh 成功。
- 下一步：請使用者在 Notepad++ 以微軟注音輸入，`probe_loaded_modules.py` 取得實際模組；之後才可標 P0.3。

### 2026-11-22／AI：P0.3 使用者在 Notepad++ 實測後的觀察（仍未達驗收）
- 使用者回報已在 Notepad++（傳統 Win32，pid 15660）以微軟注音輸入。回報後立即量測：Notepad++ 的 HKL＝0x04040404（zh-TW），已載入 `C:\Program Files\ChewingTextService\chewing_tip.dll`，**無 IMTCTIP／IMTCCORE／ChtIME 模組**；全系統可存取處理程序（415 個，181 個存取被拒）亦無；`HKCU\...\CTF\Assemblies x00000404\{34745C63-…}` 的 Default／Profile 仍是新酷音 {13F2EF08-…}／{CE45F71D-…}；`HKLM` 的微軟注音 profile 為 Enable=0。
- 結論：客觀量測顯示 zh-TW 實際使用的是新酷音，而非微軟注音，與口頭回報不一致；未取得微軟注音實際載入的證據。TSF 對「全新執行緒」回報的作用中 TIP 是微軟注音（疑為排序第一），不等於使用者目前實際使用者。
- P0.3 保持未完成（P0 未完成）。待使用者決策：(a) 協助讓微軟注音真正可選（HKLM profile Enable=0 可能是原因）後重測；(b) 若此機器無法啟用，改以「靜態參考版本＋原生隔離執行」作為版本依據，並由使用者明確同意放寬 P0.3 驗收。
- 補充觀測：`HKCU\Control Panel\International\User Profile\zh-Hant-TW` 只列出 `0404:{B115690A-…}{B2F9C502-…}`＝1（微軟注音，已啟用）；新酷音不在使用者語言清單內，但 `CTF\Assemblies` 的 Default 仍指向新酷音，且 Notepad++ 載有 chewing_tip.dll。兩處登錄資料互相矛盾，無法僅憑登錄判定實際作用中的 TIP；仍需實際載入證據。P0.3 未完成。

### 2026-11-22／AI：P0.3 實測收尾、P0 完成
- 使用者輸入後量測：Notepad 新載入 chewing_tip_x64_26_11_724.dll、Notepad++ 載有 chewing_tip.dll；系統內無 IMETC／ChtIME 模組。P0.3 依實測結論勾選，並標明與使用者口頭說法不符及其對 P3／P4 動態驗證的影響。
- 新議題 I11：本機微軟注音無法實機啟用（實際輸入為新酷音），動態對照需另找方式；不影響靜態／原生隔離分析。
- 下一步：回到 I03（格網節點 vtable +0x40 與路徑分數公式）。

### 2026-11-22／AI：P1 階段完成
- 產物：`analyze/selection/input-state-machine.md`（`gen_p1_doc.py` 產生）、`candidate_key_model.py`、`ms_input_model.py`、兩個測試檔（22 個測試通過）、`run_p1_replay.py`、`analyze/p1/replay-results.json`、`libchewing/examples/key_replay.rs`（build.sh 會安裝到 bin/）。
- 新發現：chewing 在 Entering 狀態無候選索引游標，候選內 Enter 為 Bell；每頁預設 10 項（微軟 9）；輸入中 Tab／Delete 為 Bell；Space 作第一聲在詞庫無該第一聲詞時 Bell（S03，微軟未驗證）。
- 障礙（均列於規格第 6 節）：英文／符號模式未解碼；組字層邊界與 Esc 設定語義；S03／S10／S15 無微軟端結論；候選命令名稱為推定。微軟側全為靜態規則，本機無微軟注音實機（I11）。
- 下一步：P2（詞庫解碼已大量完成，補盤點與驗收彙整）或回 I03。

### 2026-11-22／AI：微軟候選排序 → 新酷音（使用者新目標）
- 目標：找出微軟字詞排序順位並放進新酷音。已完成「舊式／固定順序」（模式 6）：比較器 `NewCompItemLegacy` 解碼、序號表全量匯出（IMTCPH 1,484＋IMTCPHCS 1,303 個讀音、63,871 字，`analyze/p3/ms-char-order.tsv`）、chewing 實作（預設關閉）與全量驗證（1,519 讀音／26,112 候選／違規 0）。細節見 `analyze/p3/README.md`。
- 比較：chewing 原始詞庫順序與微軟舊式順序相同者 516/1,519 個讀音、第一名相同 1,373、平均 τ=0.787；chewing 頻率排序則 388、1,017、0.547——chewing 的預設原始順序本來就較接近微軟舊式順序，頻率排序反而偏離。
- 驗證：libchewing 133 測試通過（新增 4）、工作區 check 通過；`key_replay --ms-order` 實測 ㄕˋ 候選依微軟順序（市是事世士勢識室示）。
- 未解（重要）：微軟「預設」（固定候選順序未勾，使用者設定值 0）實際走哪個模式未證實；`IsFixedCandOrder`（config 0x13b，IIMEditor vtbl +0x250）至排序模式的連結未追到，模式 3/4 依賴的統計字序表（`GetScoreByStatCharOrder` 180059b00 的 CDicCharStat）位置未找到。另發現 `GetLegacyOrder`（回傳讀音序號＝讀音內位置，已與本表一致）也被打字轉換的格網建構（`AddReadSylToRawLatt`／`AddSylCharIDListToRawLatt`）使用，舊式序號同時影響整句轉換的單字節點，尚未移植。
- 發佈限制（I06）：序號表衍生自微軟詞庫，未加入安裝程式或 libchewing/data，只在 CHEWING_PATH 目錄存在 `ms_char_order.tsv` 時載入。
- 下一步：①找統計字序表與預設模式（決定微軟預設順序）②移植模式 3/4 ③格網節點序號。

### 2026-11-22／AI：固定候選順序設定與舊式序號
- 追到 `AddSylCharIDListToRawLatt` 以 `IsFixedCandOrder`（vtbl+0x170）決定是否附舊式序號：微軟只在「固定候選順序＝開」才用舊式序號，預設（0）走分數序。移植的選項因此等同「固定候選順序開」；統計字序表為空，僅影響提示模式。
- 格網節點「非最小序號」旗標位 1 的解碼用途未追到，故不移植到轉換引擎（不改變整句轉換結果）。證據與推論見 `analyze/p3/README.md`。
- 微軟預設順序（模式 3/4 的候選項浮點分數）仍未移植；沒有實機對照（I11），建議待決策後再做。

### 2026-11-22／AI：取得微軟引擎實機對照（TIP 內嵌主機）— 重要
- 突破：不經 TSF 路由，直接在本程序內啟動舊版微軟注音 TIP（IMTCTIP.DLL），傳入**代理 ITfThreadMgr**攔截 TIP 註冊的 `ITfKeyEventSink`，再直接餵鍵；文字寫入記憶體內的 `ITextStoreACP`（`tip_host2.py`、`tip_host4.py`）。證實 `ㄋㄧˇㄏㄠˇ`→你好、`ㄨㄛˇㄞˋㄋㄧˇ`→我愛你、`ㄕˋㄐㄧㄝˋ`→世界。IFELanguage（工廠 {F407D01A-…}）所有方法回 E_NOTIMPL，無法使用。
- msctf 對 `ActivateProfile`（微軟注音）退回載入新酷音（HKLM 微軟注音 profile Enable=0），所以 TSF 路徑不可行；P0.3 結論因此更明確：此機器的微軟注音 TIP 在 TSF 層是停用的。
- **事故（必須知情）**：我在未隔離的情況下驅動 TIP，**寫入了你的微軟注音使用者資料** `%APPDATA%\Microsoft\IME
.0\IMETC\`（TCHFTL.DAT、TCHFTS.DAT、TCLRN.IMD，修改時間為本次作業期間）。該目錄的建立時間早於本輪（11/21 23:08），無法確定檔案原貌，備份的是**寫入後**的現況：`analyze/p0/ms-ime-user-data-backup/`。污染證據：同一輸入 `ㄕˋ ㄐㄧㄝˋ` 在污染環境得「是葉」，隔離後得「世界」。
- 補救：之後所有微軟端測試一律先把 USERPROFILE／APPDATA／LOCALAPPDATA 指到 `tmp/msprofile`（`ms_convert.py` 內建），並以雜湊驗證真實資料未再變動（已驗證一致）。尚未對真實檔案做還原；若你要還原到原貌，需要你決定（我沒有寫入前的備份）。
- 語料與基準：`make_corpus.py` 由 chewing 詞庫固定種子產生 2,469 句（1,500 詞組＋969 串接，`analyze/p4/corpus.tsv`）；微軟端 `ms_convert.py`（背景執行，可續跑，`analyze/p4/ms-results.jsonl`）；新酷音端 `convert_batch.rs`（`analyze/p4/chewing-results.jsonl`）。

### 2026-11-22／AI：首批實機對照結果與使用者案例「測試任務」
- 使用者案例「測試任務」（ㄘㄜˋ ㄕˋ ㄖㄣˋ ㄨˋ，鍵位 hk4g4bp4j4）：微軟引擎轉出「測試任務」；新酷音（本機詞庫＝安裝版，SHA 相同）預設設定與使用者實際設定＋使用者資料副本（頻率排序開、空白鍵選字開）下也轉出「測試任務」，在「任」位置（游標 2）候選為「任務」。**無法重現失敗**，需使用者提供實際操作步驟與畫面。注意：我先前一次測試漏打 `p`（ㄣ）得到「測試日物」，已更正，兩邊皆如此。
- 使用者設定（登錄）：SortCandidatesByFrequency=1、ShowCandWithSpaceKey=1、ConvEngine=1、SelAreaLen=10、EnableAutoLearn=0；頻率排序與微軟順序偏離較大（見 analyze/p3/README.md）。
- 首批 336 句詞組（微軟端仍在背景跑完 2,469 句）：轉換結果相同 273／336＝81.25%；差異皆為語言模型同音字選擇（例：進草/勁草、六遍/六便、借看一夏/借看一下）。語料取自 chewing 詞庫，故偏向 chewing；差異不是對錯，而是兩套 LM 的選擇不同。要讓新酷音與微軟一致必須移植微軟的 n-gram 評分與格網權重（P5.5），現在有實機基準可驗證。
- 下一步：①微軟端跑完後出完整比較（`compare_conversion.py`→`analyze/p4/conversion-comparison.json`）②以已解析的 IMTCT 模型重建解碼器，對照實機結果量測一致率③候選清單擷取（TIP 未註冊 ITfFunctionProvider，ITfFnReconversion 路徑未通；需另找 TIP 的候選匯出途徑）。

### 2026-11-22／AI：使用者回報「冊市任勿」（新酷音實際輸出）
- 使用者以新酷音打「測試任務」得到「冊市任勿」（微軟得「測試任務」）。以 `key_replay --engine` 重現：**簡易引擎（SimpleEngine）**輸入 `hk4g4bp4j4` 得「冊市任勿」，智慧引擎與模糊引擎皆得「測試任務」。「冊市任勿」＝每個讀音在詞庫原始順序的第一個候選，完全未使用詞組與語言模型。
- 矛盾：登錄 `HKCU\Software\ChewingTextService\ConvEngine`＝1（智慧），TIP 對應 0→簡易、2→模糊、其他→智慧；安裝版詞庫與本機重建 SHA 相同。故使用者那次輸入時實際生效的引擎應為簡易，原因未明（可能：設定程式暫時存成 0、設定未重新載入、或安裝版 TIP 組建 26.11.724 與本倉庫對應不同）。待使用者確認設定畫面的轉換引擎與重現步驟。
- 微軟注音在簡易／無 LM 情況下也不是逐字取首選，所以此現象與「微軟排序移植」是兩件事：先確保新酷音在智慧引擎下運作，再談與微軟一致。

### 2026-11-22／AI：「冊市任勿」根因調查（未定案）
- 事實：①設定畫面截圖顯示「模式：智慧選詞」；登錄 ConvEngine=1；TIP 每次按鍵都重讀登錄（`reload_if_needed`，無時間戳門檻），所以設定不會過期。②安裝版詞庫／chewing-cli 版本與本機重建相同（0.14.0-rc.1）。③用智慧引擎重現得「測試任務」，只有簡易引擎得「冊市任勿」；「冊市任勿」＝詞庫原始順序首選（頻率排序首選會是「是」而非「市」），故不是使用者從頻率排序的選字窗挑出。④使用者詞典（44 行）與歷史不含這些字；模擬以簡易引擎提交 3 次後再用智慧引擎仍得「測試任務」。
- 嘗試在 C# TSF 主機（`analyze/scripts/TsfHost.cs`）內直接驅動安裝版 TIP 以觀察真實行為：TIP 可載入並初始化（日誌顯示 Standard 注音編輯器），但在我的主機中前景焦點不穩（`IsThreadFocus` 常為 False，使用者正在操作電腦），按鍵未被處理；未取得安裝版 TIP 的實際轉換輸出。TIP 只在偵錯器存在時輸出日誌且 release 建置僅 Info 等級，看不到按鍵決策。
- 副作用揭露：我的測試讓新酷音 TIP 在我的程序內執行「檢查更新」，寫入 `HKCU\Software\ChewingTextService\LastUpdateCheckTime`（無害，僅更新檢查時間）。
- 待使用者確認以縮小範圍：①重啟該應用程式後重打；②逐音節回報每打完一個音節畫面顯示什麼、是否自動跳出選字窗；③是否有按 Space／Enter／Tab／Shift。懷疑方向：安裝版 TIP 組建 26.11.724 與本倉庫原始碼行為不同、或選字窗自動開啟導致數字聲調鍵被當成選字鍵。

### 2026-11-22／AI：Ctrl+數字「記憶」問題——根因與修正
- 使用者回報 Notepad++ 已可打出「測試任務」（先前「冊市任勿」重啟後消失，原因仍未定案），但 Ctrl+數字儲存詞（記憶）有問題。
- 引擎層 Ctrl+數字本身正常（Ctrl+2 加入「任務」、Ctrl+3「試任務」、Ctrl+4「測試任務」，超過字數才失敗；需 `user_phrase_add_dir=Backward`，與使用者 AddPhraseForward=1 一致）。
- **根因（已重現）**：`Editor::flush` 每次存詞後以該程序記憶體重寫整份 `user_dict.csv`（DIRTY_THRESHOLD=0），多個應用程式（Notepad++、記事本…）各持一份記憶體副本，後寫的覆蓋先寫的（遺失更新）。重現：兩個編輯器載入同一資料夾，A 存「任務」、B 存「你好」，結果檔只剩「你好」（`libchewing/examples/multi_instance_check.rs`）。
- 另發現使用者真實 `user_dict.csv` 第一行是損壞記錄：詞為 33 個 NUL 位元組、讀音 `ㄈㄟˋ ㄑㄧˋ`，成因未明（無法重現），載入時會被當成詞保留並每次重寫。
- **修正**（`libchewing/src/user/dict.rs`、`src/editor/mod.rs`）：①`merge_missing`：寫檔前先讀磁碟上的檔案，把本程序沒有的詞合併進來；②`FileLock`（`user_dict.csv.lock`，獨佔建立，10 秒視為過期）序列化寫入者；③載入與存檔都略過空詞或含控制字元（NUL）的記錄，損壞行會在下次存檔時清除。驗證：同一重現改為兩詞皆保留、NUL 位元組 0；libchewing 測試 135 通過（新增 2）；工作區 check 通過。
- 限制：①`history_dict.bin`（歷史統計）有同樣的多程序覆蓋，未處理；②刪除（unlearn）以負 boost 保存，不受合併影響，但跨程序即時同步仍無；③已安裝的 TIP（System32 的 chewing_tip_x64_26_11_724.dll）**沒有被替換**，修正要等重新建置並安裝才生效。我沒有改動你的真實使用者資料。

### 2026-11-22／AI：可發行 MSI 與完整測試準備
- 使用者自行反安裝了官方新酷音 724（那是使用者自己安裝的），以便測試我建的版本；我沒有替換或改動任何系統檔案。
- 新增 `build-msi.sh`，`pack-release.sh` 已接上：產物 `dist/windows-chewing-tsf-26.11.1122-local.msi`（18 MB，未簽章）。細節與限制見 `analyze/p0/REPRODUCE.md`「可發行 MSI」。
- 限制與風險：①ARM64 DLL、設定程式、編輯器、tip host、cli 取自官方 724（倉庫建不出來），官方 724 的 TIP 含本倉庫沒有的 `update/config.rs`，代表倉庫原始碼與 724 不完全相同，host／設定程式與我建的 TIP 可能有 IPC／設定相容性差異——這正是需要實機完整測試的點；②用 WiX 6.0.2 而非倉庫指定的 WiX 7；③MSI 未簽章，安裝時 UAC 會顯示發行者不明。
- 測試重點：安裝後「測試任務」轉換、Ctrl+數字在多個應用程式同時記憶、設定程式能否開啟與儲存、tip host 是否正常啟動、反安裝是否乾淨。
