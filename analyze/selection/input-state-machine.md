# 微軟注音輸入與選字狀態機（P1 規格）

產生方式：`python analyze/scripts/gen_p1_doc.py`。證據：IMTCTIP.dll／IMTCCORE.DLL 反編譯（SHA-256 見 `analyze/p0/manifest.json`）。
模型：`candidate_key_model.py`、`ms_input_model.py`（共 22 個單元測試，`python -m unittest test_candidate_key_model test_ms_input_model`）。
重播：`run_p1_replay.py` → `analyze/p1/replay-results.json`（微軟模型 vs libchewing 實際編輯器）。
**限制**：本機實際輸入由新酷音處理（P0.3），沒有微軟注音實機輸出；以下微軟行為皆為靜態反編譯規則，不是實機觀察。命令名稱為依按鍵綁定推定，編號與比對規則來自二進位。

## 1. 事件流（P1.1）

1. TSF 按鍵 → IMTCTIP → `CImeCore::OnTestKeyEvent` 18002ed08／事件處理 → `CIMController::InvokeEvent` 18002f8a0。
2. `QueuingEvent` 18002fa18 將事件放入 64 槽佇列（溢出則整批中止）；`ProcessEventQueue` 18002f95c 逐筆交給 `CImeControlProvider::HandleEvent` 180031760。
3. 事件類型（`CTypingControl::HandleEvent` 1800350d0 讀取欄位 +8）：1＝按鍵 → `HandleKeyEvent`；5＝命令 → `HandleCommand`；其他回傳 1（不處理）。
4. 控制堆疊（`SetupKeyAndCommandControlStack` 1800334c4 的推入順序）：
   - CSearchIntegrationControl：always (provider+0x70)
   - CBalloonControl：if config 0x11c and 0x11d both set (provider+0x48)
   - CSoftKbdCtrl：if config 0x145 set (provider+0x50)
   - CCandidateControl：if candidate editor reports an active candidate list (provider+0x58)
   - CTypingControl：if a typing editor exists (provider+0x60)
   - CComposeControl：if a compose editor exists (provider+0x68)
   - CCommandControl：always, last (provider+0x38)
5. 候選視窗開啟後的按鍵，在 TIP 層另由 `CFnCandUIKeyHandler::CandUICommandFromKey` 180028070 以四張表轉成命令（第 3 節）。
6. 提交：`CCandEditor::OnFinalize` 18003f060（選取候選）→ `CImeSentenceWrap::LearnContext` 18009afe0 → 短期學習環（見 learning-persistence.txt）。

## 2. 各層按鍵分派（P1.3／P1.4）

### 2.1 輸入中（CTypingControl::HandleKeyEvent 180035954）
槽位：+0x20 GetConvertibleLength、+0xb0 OnSpace、+0xb8 OnBackSpace、+0xc0 OnDelete、+0xd8 ForceConvert、+0xe8 CancelTyping（CTypingEditor vftable 1800cc490）。

| 按鍵 | 無輸入內容 | 有輸入內容 |
|---|---|---|
| Space | 不處理，交給應用程式 | OnSpace：注音剖析器收到空白（第一聲），否則取消輸入並插入空白符號（`CTypingEditor::OnSpace` 18003e520、`CPhoneticConv::OnSpace` 180049fd0） |
| Enter | 不處理 | ForceConvert，吞鍵 |
| Esc | 查詢編輯器 +0x58→+0x50，非 0 才處理 | CancelTyping，吞鍵 |
| Backspace | 不處理 | OnBackSpace（按鍵旗標位 +0x102&1 為 1 時不處理），吞鍵 |
| Delete | 不處理 | OnDelete，吞鍵 |
| Tab／Insert | 不處理(Tab)；Insert 見原始碼 | 吞鍵、無動作 |
| Home／End／PgUp／PgDn／方向鍵 | 不處理 | 若設定 0x108 非 0 則 ForceConvert；一律吞鍵 |
| 小鍵盤 0x60–0x6F | 不處理 | 取消輸入後不處理 |
| 其他字元 | 進入字元輸入 `OnCharInput` 180036b54（`Tsf3OverrideUtil::IsTsf3OverrideEnabled` 決定參數） | 同左 |

### 2.2 已組字（CComposeControl::HandleKeyEvent 180035408，部分解碼）

| 按鍵 | 路由 |
|---|---|
| Space | `OnPhraseKey(0x20)` 180037070：詞組輸入（PhraseInput）條件成立時接受，否則 `CComposeEditor::OnSymbolInput(0x20)`＝插入空白符號；**不是開啟候選** |
| ↑／↓ | `OnCaretKey` 180036614 → `OnCandSwitch` 18003601c／`OpenCandidate` 180037378 開啟候選；設定 0x14f 可重新對應四個方向鍵 |
| ←／→／Home／End | 游標移動（`OnCaretKey`） |
| Enter | 提交 |
| Esc | 依設定 299（0x12b）清除區塊或取消（語義未解碼） |
| Backspace／Delete | `CComposeEditor::OnBackSpace` 18008ede0／`OnDelete` 18008efa0 |
| Tab | 詞組輸入（Tab）或轉送 Tab（設定 0x141） |
| PgUp／PgDn | 設定 0x141 為 0 時取消編輯並轉送原按鍵 |

### 2.3 候選控制（CCandidateControl::HandleKeyEvent 180035204；每頁 9 項）

| 按鍵 | 行為 |
|---|---|
| Enter | `OnFinalizeItem`(目前索引) |
| Esc | `OnCancel` 180035efc：關閉清單、文字保留 |
| Space | `OnSpace` 180037274：cur+9<總數→cur+9；總數<10→不動作；cur<總數−總數%9→最後一項；否則 cur%9 |
| PgUp | cur−9（<0 不動作） |
| PgDn | cur+9；越界且總數≥10→索引 0；總數<10→不動作 |
| ↑ | cur−1；cur=0 時到最後一項 |
| ↓ | cur+1；到尾端回 0 |
| ← | 版面 1／2：cur−9≥0 則索引 cur−9，否則切換版面（1→0、2→3）；其他版面不動作 |
| → | 版面 0／3 且總數≥10：切換版面（0→1、3→2）；版面 1／2：同 PgDn |
| Home／End | 不處理 |
| Delete | 吞鍵 |
| 數字 1–9 | `OnCharInput` 180036a80 → `OnFinalizeItem`(數字−1) |
| Tab | 切換候選版面（0→1…依 +0x128／+0x130） |

## 3. 候選視窗命令表（P1.2，96 筆全量）

表選擇（`CandUICommandFromKey` 180028070）：候選類型＝3 → candidate_type_3；否則整合模式且視窗旗標為 0 → composition_variant；否則設定檔 ID∈{3,7} → profile_variant；否則 default。
比對規則：flags＝0xFFFFFFFF 為「輸入字元」比對；否則比對虛擬鍵，flags 位元 0＝需 Shift、位元 1＝Shift 須放開、位元 2＝需 Ctrl、位元 3＝Ctrl 須放開；先到先中（default 與 composition_variant 的數字 1–9 各出現兩次，第二組永遠被遮蔽，共 18 筆）。
例外：Tab（無修飾、非類型 3、非整合、非 shell 模式）→ 命令 0x14；←／→在非 profile 表且無修飾時先過版面檢查（垂直版面 → 為 0x14／0，← 為 0；水平版面反之）；profile_variant 下 ←／→ 一律命令 0。
命令名稱（推定）：0=NONE_CONSUME、1=SELECT_CURRENT、2=CANCEL_CLOSE、4=SELECT_BY_NUMBER、7=PAGE_NEXT、8=PAGE_PREV、9=FIRST_PAGE、10=LAST_PAGE、11=MOVE_11、12=MOVE_12、13=MOVE_LEFT、14=MOVE_RIGHT、20=TAB_0x14；0xFFFFFFFF＝不處理。

### 表 default（30 筆）

| # | 按鍵 | 修飾鍵條件 | 命令 | 參數 |
|---|---|---|---|---|
| 0 | Enter | Shift ignored, Ctrl ignored | 1 SELECT_CURRENT | 0 |
| 1 | Space | Shift up, Ctrl up | 7 PAGE_NEXT | 0 |
| 2 | Up | Shift ignored, Ctrl ignored | 11 MOVE_11 | 0 |
| 3 | Down | Shift ignored, Ctrl ignored | 12 MOVE_12 | 0 |
| 4 | Left | Shift ignored, Ctrl ignored | 13 MOVE_LEFT | 0 |
| 5 | Right | Shift ignored, Ctrl ignored | 14 MOVE_RIGHT | 0 |
| 6 | PageUp | Shift ignored, Ctrl ignored | 8 PAGE_PREV | 0 |
| 7 | PageDown | Shift ignored, Ctrl ignored | 7 PAGE_NEXT | 0 |
| 8 | Home | Shift ignored, Ctrl ignored | 9 FIRST_PAGE | 0 |
| 9 | End | Shift ignored, Ctrl ignored | 10 LAST_PAGE | 0 |
| 10 | Esc | Shift ignored, Ctrl ignored | 2 CANCEL_CLOSE | 0 |
| 11 | Delete | Shift ignored, Ctrl ignored | 0 NONE_CONSUME | 0 |
| 12 | char '1' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 1 |
| 13 | char '2' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 2 |
| 14 | char '3' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 3 |
| 15 | char '4' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 4 |
| 16 | char '5' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 5 |
| 17 | char '6' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 6 |
| 18 | char '7' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 7 |
| 19 | char '8' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 8 |
| 20 | char '9' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 9 |
| 21 | char '1' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #12 遮蔽，不可達） | 0 |
| 22 | char '2' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #13 遮蔽，不可達） | 0 |
| 23 | char '3' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #14 遮蔽，不可達） | 0 |
| 24 | char '4' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #15 遮蔽，不可達） | 0 |
| 25 | char '5' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #16 遮蔽，不可達） | 0 |
| 26 | char '6' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #17 遮蔽，不可達） | 0 |
| 27 | char '7' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #18 遮蔽，不可達） | 0 |
| 28 | char '8' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #19 遮蔽，不可達） | 0 |
| 29 | char '9' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #20 遮蔽，不可達） | 0 |

### 表 profile_variant（19 筆）

| # | 按鍵 | 修飾鍵條件 | 命令 | 參數 |
|---|---|---|---|---|
| 0 | Enter | Shift ignored, Ctrl ignored | 1 SELECT_CURRENT | 0 |
| 1 | Space | Shift up, Ctrl up | 7 PAGE_NEXT | 0 |
| 2 | Up | Shift ignored, Ctrl ignored | 11 MOVE_11 | 0 |
| 3 | Down | Shift ignored, Ctrl ignored | 12 MOVE_12 | 0 |
| 4 | Left | Shift ignored, Ctrl ignored | 13 MOVE_LEFT | 0 |
| 5 | Right | Shift ignored, Ctrl ignored | 14 MOVE_RIGHT | 0 |
| 6 | PageUp | Shift ignored, Ctrl ignored | 8 PAGE_PREV | 0 |
| 7 | PageDown | Shift ignored, Ctrl ignored | 7 PAGE_NEXT | 0 |
| 8 | Home | Shift ignored, Ctrl ignored | 9 FIRST_PAGE | 0 |
| 9 | End | Shift ignored, Ctrl ignored | 10 LAST_PAGE | 0 |
| 10 | char '1' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 1 |
| 11 | char '2' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 2 |
| 12 | char '3' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 3 |
| 13 | char '4' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 4 |
| 14 | char '5' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 5 |
| 15 | char '6' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 6 |
| 16 | char '7' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 7 |
| 17 | char '8' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 8 |
| 18 | char '9' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 9 |

### 表 candidate_type_3（19 筆）

| # | 按鍵 | 修飾鍵條件 | 命令 | 參數 |
|---|---|---|---|---|
| 0 | Enter | Shift ignored, Ctrl ignored | 2 CANCEL_CLOSE | 0 |
| 1 | Space | Shift up, Ctrl up | 7 PAGE_NEXT | 0 |
| 2 | Up | Shift ignored, Ctrl ignored | 2 CANCEL_CLOSE | 0 |
| 3 | Down | Shift ignored, Ctrl ignored | 2 CANCEL_CLOSE | 0 |
| 4 | Left | Shift ignored, Ctrl ignored | 2 CANCEL_CLOSE | 0 |
| 5 | Right | Shift ignored, Ctrl ignored | 2 CANCEL_CLOSE | 0 |
| 6 | PageUp | Shift ignored, Ctrl ignored | 8 PAGE_PREV | 0 |
| 7 | PageDown | Shift ignored, Ctrl ignored | 7 PAGE_NEXT | 0 |
| 8 | Home | Shift ignored, Ctrl ignored | 9 FIRST_PAGE | 0 |
| 9 | End | Shift ignored, Ctrl ignored | 10 LAST_PAGE | 0 |
| 10 | VK 1 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 1 |
| 11 | VK 2 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 2 |
| 12 | VK 3 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 3 |
| 13 | VK 4 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 4 |
| 14 | VK 5 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 5 |
| 15 | VK 6 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 6 |
| 16 | VK 7 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 7 |
| 17 | VK 8 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 8 |
| 18 | VK 9 | Shift required, Ctrl up | 4 SELECT_BY_NUMBER | 9 |

### 表 composition_variant（28 筆）

| # | 按鍵 | 修飾鍵條件 | 命令 | 參數 |
|---|---|---|---|---|
| 0 | Enter | Shift ignored, Ctrl ignored | 1 SELECT_CURRENT | 0 |
| 1 | Space | Shift up, Ctrl up | 7 PAGE_NEXT | 0 |
| 2 | Left | Shift ignored, Ctrl ignored | 11 MOVE_11 | 0 |
| 3 | Right | Shift ignored, Ctrl ignored | 12 MOVE_12 | 0 |
| 4 | PageUp | Shift ignored, Ctrl ignored | 8 PAGE_PREV | 0 |
| 5 | PageDown | Shift ignored, Ctrl ignored | 7 PAGE_NEXT | 0 |
| 6 | Home | Shift ignored, Ctrl ignored | 9 FIRST_PAGE | 0 |
| 7 | End | Shift ignored, Ctrl ignored | 10 LAST_PAGE | 0 |
| 8 | Esc | Shift ignored, Ctrl ignored | 2 CANCEL_CLOSE | 0 |
| 9 | Delete | Shift ignored, Ctrl ignored | 0 NONE_CONSUME | 0 |
| 10 | char '1' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 1 |
| 11 | char '2' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 2 |
| 12 | char '3' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 3 |
| 13 | char '4' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 4 |
| 14 | char '5' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 5 |
| 15 | char '6' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 6 |
| 16 | char '7' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 7 |
| 17 | char '8' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 8 |
| 18 | char '9' | typed character (ToUnicode), modifiers not checked | 4 SELECT_BY_NUMBER | 9 |
| 19 | char '1' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #10 遮蔽，不可達） | 0 |
| 20 | char '2' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #11 遮蔽，不可達） | 0 |
| 21 | char '3' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #12 遮蔽，不可達） | 0 |
| 22 | char '4' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #13 遮蔽，不可達） | 0 |
| 23 | char '5' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #14 遮蔽，不可達） | 0 |
| 24 | char '6' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #15 遮蔽，不可達） | 0 |
| 25 | char '7' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #16 遮蔽，不可達） | 0 |
| 26 | char '8' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #17 遮蔽，不可達） | 0 |
| 27 | char '9' | typed character (ToUnicode), modifiers not checked | 0 NONE_CONSUME （被 #18 遮蔽，不可達） | 0 |

## 4. 微軟 vs chewing 操作重播（P1.5）

| ID | 情境 | 微軟（模型） | chewing（實測） | 判定 | 說明 |
|---|---|---|---|---|---|
| S01 | empty buffer + Space | ('PASS_THROUGH', False) | commit=' ' | SAME | MS passes the key to the app (app inserts the space); chewing commits the space itself: same visible text |
| S02 | partial reading ㄇㄚ + Space (first tone) | ('ON_SPACE', True) | display='嗎' entering=False | SAME | Space completes the syllable as first tone in both; verified with a syllable whose tone-1 reading exists in the dictionary |
| S03 | partial reading with no dictionary word for first tone + Space | ('ON_SPACE', True) | behavior=Bell syllable='ㄋㄧ' | MS_UNDECODED | chewing rings the bell and keeps ㄋㄧ pending (no tone-1 word); Microsoft outcome depends on the parser/lexicon check (CTParserPhonetic::Parsing 1800553cc, CheckReadingString) which is not replayed |
| S04 | composed text + Space | 'PHRASE_INPUT_OR_SYMBOL_SPACE' | default display='你好 ' sel=False; --space-select sel=True | SAME | Legacy Microsoft inserts a space symbol (or PhraseInput); chewing default matches. P1.6 target behaviour (Space opens candidates) = space_is_select_key, see S05 |
| S05 | P1.6: Space opens candidates only on a composed syllable | ('target', None) | composed+Space sel=True; empty+Space commit=' '; ma+Space display='嗎'; in-candidate Space page=1 | DIFF_OPTION | all four requirements hold with space_is_select_key=true: open candidates, normal space on empty buffer, first tone kept, in-candidate Space pages |
| S06 | composed text + Down opens candidates | 'OPEN_CANDIDATE_VIA_CARET_KEY' | selecting=True total_pages=10 | SAME |  |
| S07 | candidate page size | ('page=9', None) | candidates on first page returned=10 | DIFF_OPTION | chewing default candidates_per_page=10 (option exists); Microsoft shows 9 per page with digits 1-9 only |
| S08 | candidate open + Space | ('SET_INDEX', 9) | page=1 | SAME | next page; wrap-around semantics differ at the last page (Microsoft: jump to last item then wrap to the same row; chewing: next phrase group) - see S09 |
| S09 | candidate last page + Space wrap | ('wrap to index cur%9', None) | page=9/10 | DIFF_STRUCTURAL | Microsoft keeps a cursor index inside the list and wraps by index; chewing pages by group (needs an index cursor: P5.4) |
| S10 | candidate open + PageDown on last page | ('INDEX', 0) | page=2/10 | MS_UNDECODED | Microsoft wraps to index 0 on PageDown past the end; chewing PageDown pages without index cursor (compare after P5.4) |
| S11 | candidate open + Enter | ('FINALIZE_ITEM', 0) | behavior=Bell selecting=True | DIFF_STRUCTURAL | Microsoft selects the highlighted item; chewing has no highlighted item and rings the bell |
| S12 | candidate open + digit 2 | ('FINALIZE_ITEM_BY_DIGIT', 1) | selecting=False display='是' | SAME | digit selects the item at that position (note: chewing page has 10 entries, Microsoft 9) |
| S13 | candidate open + Esc | ('CANCEL', None) | selecting=False display='是' | SAME | closes the list, text kept |
| S14 | composed text + Enter | 'COMMIT' | commit='你好' | SAME |  |
| S15 | composed text + Esc | 'CANCEL_OR_CLEAR' | default display='你好' behavior=Ignore | MS_UNDECODED | chewing ignores Esc by default (option esc_clear_all_buffer); Microsoft behaviour depends on config 0x12b whose meaning is not decoded |
| S16 | typing state + Esc | ('CANCEL_TYPING', True) | syllable='' | SAME |  |
| S17 | typing state + Tab / Delete | (('CONSUME_NOTHING', True), ('ON_DELETE', True)) | tab behavior=Bell del behavior=Bell | DIFF_STRUCTURAL | Microsoft consumes Tab silently and Delete edits typing; chewing rings the bell for both |
| S18 | composed text + Backspace | 'ON_BACKSPACE' | display='' | SAME |  |

統計：SAME 10、MS_UNDECODED 3、DIFF_OPTION 2、DIFF_STRUCTURAL 3

## 5. Space 規格（P1.6）

目標（使用者要求）：Space 開啟選字，同時保留第一聲、正常空白與候選內操作；**不採全域 Space→Down 替換**。

| 狀態 | Space 行為 | 依據 |
|---|---|---|
| 無輸入、無組字 | 輸入一般空白 | 微軟 CTypingControl 不處理→應用程式插入；chewing 直接提交空白（S01） |
| 輸入中（有未完成音節） | 補上第一聲（空白＝陰平）完成音節，不開啟選字 | `CPhoneticConv::OnSpace` 180049fd0；chewing 同（S02）；詞庫無該第一聲詞時 chewing 響鈴不完成（S03，微軟未驗證） |
| 已組字、游標在音節上 | **開啟選字**（新行為） | chewing `space_is_select_key=true`（Entering→QuickSelect）；舊版微軟此處為插入空白或詞組輸入（S04）。游標不在可選音節上且緩衝非空時不動作 |
| 候選視窗開啟 | 下一頁；到末頁的環繞規則見 S09 | 微軟表命令 7 flags 0xa（無 Shift、無 Ctrl）；chewing 換頁（S08） |
| 候選視窗開啟＋Shift/Ctrl＋Space | 微軟不處理（旗標 0xa） | 候選模型測試 `test_space_flags` |

實作含意：chewing 已具備所需機制，僅需把 `space_is_select_key` 做成可關閉的相容設定（P5.1），不需要改寫按鍵對應。S05 逐項驗證四個條件。

## 6. 未解與差異清單（障礙）

- S03／S10／S15 標為 MS_UNDECODED：微軟端依賴剖析器／詞庫檢查（`CTParserPhonetic::Parsing` 1800553cc）、PageDown 與環繞的實機驗證、設定 0x12b 的語義，尚無結論。
- 候選命令編號的消費端在作業系統候選 UI（不在參考二進位內），名稱為推定。
- 組字層 `CComposeControl::HandleKeyEvent` 只解碼了路由，Delete／Home／End／方向鍵的邊界條件尚未逐條驗證。
- DIFF_STRUCTURAL（S09、S11、S17）：chewing 缺少候選索引游標、候選內 Enter 選取、輸入中 Tab／Delete 靜默處理；列入 P5.2／P5.4。
- DIFF_OPTION（S05、S07）：以 `space_is_select_key`、`candidates_per_page=9` 即可對齊。

