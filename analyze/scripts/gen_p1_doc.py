"""Generate analyze/selection/input-state-machine.md (P1 spec) from the models and replay results."""
import json
from pathlib import Path

from candidate_key_model import CMD_NAMES, load_tables
from ms_input_model import CONTROL_STACK

ROOT = Path(__file__).resolve().parents[2]
T = load_tables()
RES = json.loads((ROOT / 'analyze/p1/replay-results.json').read_text(encoding='utf-8'))
VKN = {9: 'Tab', 13: 'Enter', 27: 'Esc', 32: 'Space', 33: 'PageUp', 34: 'PageDown', 35: 'End', 36: 'Home',
       37: 'Left', 38: 'Up', 39: 'Right', 40: 'Down', 46: 'Delete'}


def keyname(e):
    if e.flags == 0xFFFFFFFF:
        return f"char '{chr(e.key & 0xFFFF)}'"
    if 0x30 <= e.key <= 0x39:
        return f"VK {chr(e.key)}"
    return VKN.get(e.key, hex(e.key))


def mods(e):
    if e.flags == 0xFFFFFFFF:
        return 'typed character (ToUnicode), modifiers not checked'
    out = []
    out.append('Shift required' if e.flags & 1 else ('Shift up' if e.flags & 2 else 'Shift ignored'))
    out.append('Ctrl required' if e.flags & 4 else ('Ctrl up' if e.flags & 8 else 'Ctrl ignored'))
    return ', '.join(out)


lines = []
w = lines.append
w('# 微軟注音輸入與選字狀態機（P1 規格）')
w('')
w('產生方式：`python analyze/scripts/gen_p1_doc.py`。證據：IMTCTIP.dll／IMTCCORE.DLL 反編譯（SHA-256 見 `analyze/p0/manifest.json`）。')
w('模型：`candidate_key_model.py`、`ms_input_model.py`（共 22 個單元測試，`python -m unittest test_candidate_key_model test_ms_input_model`）。')
w('重播：`run_p1_replay.py` → `analyze/p1/replay-results.json`（微軟模型 vs libchewing 實際編輯器）。')
w('**限制**：本機實際輸入由新酷音處理（P0.3），沒有微軟注音實機輸出；以下微軟行為皆為靜態反編譯規則，不是實機觀察。命令名稱為依按鍵綁定推定，編號與比對規則來自二進位。')
w('')
w('## 1. 事件流（P1.1）')
w('')
w('1. TSF 按鍵 → IMTCTIP → `CImeCore::OnTestKeyEvent` 18002ed08／事件處理 → `CIMController::InvokeEvent` 18002f8a0。')
w('2. `QueuingEvent` 18002fa18 將事件放入 64 槽佇列（溢出則整批中止）；`ProcessEventQueue` 18002f95c 逐筆交給 `CImeControlProvider::HandleEvent` 180031760。')
w('3. 事件類型（`CTypingControl::HandleEvent` 1800350d0 讀取欄位 +8）：1＝按鍵 → `HandleKeyEvent`；5＝命令 → `HandleCommand`；其他回傳 1（不處理）。')
w('4. 控制堆疊（`SetupKeyAndCommandControlStack` 1800334c4 的推入順序）：')
for n, c in CONTROL_STACK:
    w(f'   - {n}：{c}')
w('5. 候選視窗開啟後的按鍵，在 TIP 層另由 `CFnCandUIKeyHandler::CandUICommandFromKey` 180028070 以四張表轉成命令（第 3 節）。')
w('6. 提交：`CCandEditor::OnFinalize` 18003f060（選取候選）→ `CImeSentenceWrap::LearnContext` 18009afe0 → 短期學習環（見 learning-persistence.txt）。')
w('')
w('## 2. 各層按鍵分派（P1.3／P1.4）')
w('')
w('### 2.1 輸入中（CTypingControl::HandleKeyEvent 180035954）')
w('槽位：+0x20 GetConvertibleLength、+0xb0 OnSpace、+0xb8 OnBackSpace、+0xc0 OnDelete、+0xd8 ForceConvert、+0xe8 CancelTyping（CTypingEditor vftable 1800cc490）。')
w('')
w('| 按鍵 | 無輸入內容 | 有輸入內容 |')
w('|---|---|---|')
w('| Space | 不處理，交給應用程式 | OnSpace：注音剖析器收到空白（第一聲），否則取消輸入並插入空白符號（`CTypingEditor::OnSpace` 18003e520、`CPhoneticConv::OnSpace` 180049fd0） |')
w('| Enter | 不處理 | ForceConvert，吞鍵 |')
w('| Esc | 查詢編輯器 +0x58→+0x50，非 0 才處理 | CancelTyping，吞鍵 |')
w('| Backspace | 不處理 | OnBackSpace（按鍵旗標位 +0x102&1 為 1 時不處理），吞鍵 |')
w('| Delete | 不處理 | OnDelete，吞鍵 |')
w('| Tab／Insert | 不處理(Tab)；Insert 見原始碼 | 吞鍵、無動作 |')
w('| Home／End／PgUp／PgDn／方向鍵 | 不處理 | 若設定 0x108 非 0 則 ForceConvert；一律吞鍵 |')
w('| 小鍵盤 0x60–0x6F | 不處理 | 取消輸入後不處理 |')
w('| 其他字元 | 進入字元輸入 `OnCharInput` 180036b54（`Tsf3OverrideUtil::IsTsf3OverrideEnabled` 決定參數） | 同左 |')
w('')
w('### 2.2 已組字（CComposeControl::HandleKeyEvent 180035408，部分解碼）')
w('')
w('| 按鍵 | 路由 |')
w('|---|---|')
w('| Space | `OnPhraseKey(0x20)` 180037070：詞組輸入（PhraseInput）條件成立時接受，否則 `CComposeEditor::OnSymbolInput(0x20)`＝插入空白符號；**不是開啟候選** |')
w('| ↑／↓ | `OnCaretKey` 180036614 → `OnCandSwitch` 18003601c／`OpenCandidate` 180037378 開啟候選；設定 0x14f 可重新對應四個方向鍵 |')
w('| ←／→／Home／End | 游標移動（`OnCaretKey`） |')
w('| Enter | 提交 |')
w('| Esc | 依設定 299（0x12b）清除區塊或取消（語義未解碼） |')
w('| Backspace／Delete | `CComposeEditor::OnBackSpace` 18008ede0／`OnDelete` 18008efa0 |')
w('| Tab | 詞組輸入（Tab）或轉送 Tab（設定 0x141） |')
w('| PgUp／PgDn | 設定 0x141 為 0 時取消編輯並轉送原按鍵 |')
w('')
w('### 2.3 候選控制（CCandidateControl::HandleKeyEvent 180035204；每頁 9 項）')
w('')
w('| 按鍵 | 行為 |')
w('|---|---|')
w('| Enter | `OnFinalizeItem`(目前索引) |')
w('| Esc | `OnCancel` 180035efc：關閉清單、文字保留 |')
w('| Space | `OnSpace` 180037274：cur+9<總數→cur+9；總數<10→不動作；cur<總數−總數%9→最後一項；否則 cur%9 |')
w('| PgUp | cur−9（<0 不動作） |')
w('| PgDn | cur+9；越界且總數≥10→索引 0；總數<10→不動作 |')
w('| ↑ | cur−1；cur=0 時到最後一項 |')
w('| ↓ | cur+1；到尾端回 0 |')
w('| ← | 版面 1／2：cur−9≥0 則索引 cur−9，否則切換版面（1→0、2→3）；其他版面不動作 |')
w('| → | 版面 0／3 且總數≥10：切換版面（0→1、3→2）；版面 1／2：同 PgDn |')
w('| Home／End | 不處理 |')
w('| Delete | 吞鍵 |')
w('| 數字 1–9 | `OnCharInput` 180036a80 → `OnFinalizeItem`(數字−1) |')
w('| Tab | 切換候選版面（0→1…依 +0x128／+0x130） |')
w('')
w('## 3. 候選視窗命令表（P1.2，96 筆全量）')
w('')
w('表選擇（`CandUICommandFromKey` 180028070）：候選類型＝3 → candidate_type_3；否則整合模式且視窗旗標為 0 → composition_variant；否則設定檔 ID∈{3,7} → profile_variant；否則 default。')
w('比對規則：flags＝0xFFFFFFFF 為「輸入字元」比對；否則比對虛擬鍵，flags 位元 0＝需 Shift、位元 1＝Shift 須放開、位元 2＝需 Ctrl、位元 3＝Ctrl 須放開；先到先中（default 與 composition_variant 的數字 1–9 各出現兩次，第二組永遠被遮蔽，共 18 筆）。')
w('例外：Tab（無修飾、非類型 3、非整合、非 shell 模式）→ 命令 0x14；←／→在非 profile 表且無修飾時先過版面檢查（垂直版面 → 為 0x14／0，← 為 0；水平版面反之）；profile_variant 下 ←／→ 一律命令 0。')
w('命令名稱（推定）：' + '、'.join(f'{k}={v}' for k, v in CMD_NAMES.items()) + '；0xFFFFFFFF＝不處理。')
w('')
for name, entries in T.items():
    w(f'### 表 {name}（{len(entries)} 筆）')
    w('')
    w('| # | 按鍵 | 修飾鍵條件 | 命令 | 參數 |')
    w('|---|---|---|---|---|')
    for i, e in enumerate(entries):
        shadow = next((j for j, x in enumerate(entries[:i]) if x.flags == e.flags and x.key == e.key), None)
        mark = f' （被 #{shadow} 遮蔽，不可達）' if shadow is not None else ''
        w(f'| {i} | {keyname(e)} | {mods(e)} | {e.command} {CMD_NAMES.get(e.command, "")}{mark} | {e.argument} |')
    w('')
w('## 4. 微軟 vs chewing 操作重播（P1.5）')
w('')
w('| ID | 情境 | 微軟（模型） | chewing（實測） | 判定 | 說明 |')
w('|---|---|---|---|---|---|')
for r in RES:
    w(f"| {r['id']} | {r['scenario']} | {r['microsoft']} | {r['chewing']} | {r['status']} | {r['note']} |")
counts = {}
for r in RES:
    counts[r['status']] = counts.get(r['status'], 0) + 1
w('')
w('統計：' + '、'.join(f'{k} {v}' for k, v in counts.items()))
w('')
w('## 5. Space 規格（P1.6）')
w('')
w('目標（使用者要求）：Space 開啟選字，同時保留第一聲、正常空白與候選內操作；**不採全域 Space→Down 替換**。')
w('')
w('| 狀態 | Space 行為 | 依據 |')
w('|---|---|---|')
w('| 無輸入、無組字 | 輸入一般空白 | 微軟 CTypingControl 不處理→應用程式插入；chewing 直接提交空白（S01） |')
w('| 輸入中（有未完成音節） | 補上第一聲（空白＝陰平）完成音節，不開啟選字 | `CPhoneticConv::OnSpace` 180049fd0；chewing 同（S02）；詞庫無該第一聲詞時 chewing 響鈴不完成（S03，微軟未驗證） |')
w('| 已組字、游標在音節上 | **開啟選字**（新行為） | chewing `space_is_select_key=true`（Entering→QuickSelect）；舊版微軟此處為插入空白或詞組輸入（S04）。游標不在可選音節上且緩衝非空時不動作 |')
w('| 候選視窗開啟 | 下一頁；到末頁的環繞規則見 S09 | 微軟表命令 7 flags 0xa（無 Shift、無 Ctrl）；chewing 換頁（S08） |')
w('| 候選視窗開啟＋Shift/Ctrl＋Space | 微軟不處理（旗標 0xa） | 候選模型測試 `test_space_flags` |')
w('')
w('實作含意：chewing 已具備所需機制，僅需把 `space_is_select_key` 做成可關閉的相容設定（P5.1），不需要改寫按鍵對應。S05 逐項驗證四個條件。')
w('')
w('## 6. 未解與差異清單（障礙）')
w('')
w('- S03／S10／S15 標為 MS_UNDECODED：微軟端依賴剖析器／詞庫檢查（`CTParserPhonetic::Parsing` 1800553cc）、PageDown 與環繞的實機驗證、設定 0x12b 的語義，尚無結論。')
w('- 候選命令編號的消費端在作業系統候選 UI（不在參考二進位內），名稱為推定。')
w('- 組字層 `CComposeControl::HandleKeyEvent` 只解碼了路由，Delete／Home／End／方向鍵的邊界條件尚未逐條驗證。')
w('- DIFF_STRUCTURAL（S09、S11、S17）：chewing 缺少候選索引游標、候選內 Enter 選取、輸入中 Tab／Delete 靜默處理；列入 P5.2／P5.4。')
w('- DIFF_OPTION（S05、S07）：以 `space_is_select_key`、`candidates_per_page=9` 即可對齊。')
w('')
out = ROOT / 'analyze/selection/input-state-machine.md'
out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(out, len(lines), 'lines')
