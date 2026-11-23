# test/ — 部署驗證與 UI 測試

- `deploy-check.sh`：安裝後自動檢查。System32 版面（預設）：登錄的 DLL 存在且位於 System32／SysWOW64（遊戲只載入這兩處）、Program Files 內的程式與詞庫完整、沒有殘留舊版 stub、AppContainer 權限、DLL 可載入、轉換回歸。**不送任何鍵盤／滑鼠輸入。**
- `wow-modules.py`：唯讀列出 `Wow.exe` 載入的模組，回報新酷音 DLL 是否已載入（WoW 要先開著並在聊天框切到新酷音、打幾個鍵）。
- `webpad/`：bun + WebView2 的 IME 測試視窗（`app.ts` 自由輸入並記錄事件；`guided.ts` 逐步引導並自動判讀）。需要 `cd test && bun install`。
  `drive.py` 會用腳本送鍵，在這台機器上焦點不穩定，**預設不用**；請手動操作並讓頁面判讀。
- `StubLoad.cs`：載入已登錄的 DLL 並呼叫 `DllGetClassObject` 的小工具。
