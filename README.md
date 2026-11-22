# windows-chewing-tsf

## 本地核心與詞庫開發

本專案的 Cargo 設定已改為使用 `libchewing/` 本地原始碼。
修改後重新編譯即可使用，不需要推送到上游。

* 核心版本：`bf9a74b7bdd12db446e7d4b69130912bb5d105a4`。
* 詞庫版本：`c7268a82c748732deabaa6e7d630305f05c09026`，位於 `libchewing/data/`。
* 注音鍵盤：`libchewing/src/editor/zhuyin_layout/`。
* 輸入編輯：`libchewing/src/editor/`。
* 組詞與候選排序：`libchewing/src/conversion/`，其中 `decoder.rs` 負責句子候選解碼。
* 詞庫讀取：`libchewing/src/dictionary/`、`libchewing/src/lm/`。
* 使用者詞庫：`libchewing/src/user/`。
* 本版系統詞庫來源：`libchewing/data/dict/chewing_v4/`，包含
  `tsi_dict.csv`、`rare_dict.csv`、`static_words.txt` 與 `static_lm.arpa`。

核心檢查：`cargo check -p chewing`。
主程式檢查：`cargo check -p chewing_tip`。
Rust 的其他相依套件首次建置仍需下載。

詞庫文字檔修改後須重新產生二進位詞庫。於專案根目錄執行：

```powershell
cargo build --manifest-path libchewing/Cargo.toml -p chewing-cli --release
cmake -S libchewing/data -B build/local-dictionary -DCHEWING_CLI="$PWD/libchewing/target/release/chewing-cli.exe"
cmake --build build/local-dictionary --config Release
cmake --install build/local-dictionary --config Release --prefix "$PWD/build/local-data"
$env:CHEWING_PATH = "$PWD/build/local-data/share/libchewing"
```

`CHEWING_PATH` 適用於從該環境啟動的測試程式。已啟動的 Windows
輸入法不會自動取得新的環境變數或載入新詞庫。
Nix 打包流程也已改用本地核心、CLI 及詞庫來源；尚未在此 Windows 環境驗證 Nix 建置。
兩個下載的儲存庫均保留 Git 歷史，並使用 `local-development` 分支。

Implement chewing in Windows via Text Services Framework:

* chewing_tip contains an implementation of Windows text service for libchewing.
* tsfreg contains TSF registration helper used in the installer.
* preferences contains the user preference and phrase editor GUI.

All parts are licensed under GPL-3.0-or-later license.

# Development

## Tool Requirements

**Build natively on Windows using MSVC**

* [Build Tools for Visual Studio 2022](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
* [NodeJS Native](https://nodejs.org/)
* [Rust](https://rustup.rs/)

**Cross compile on Windows using MinGW-W64**

* [MSYS2](https://www.msys2.org/)
* [NodeJS Native](https://nodejs.org/)
* [Rust](https://rustup.rs/)

**Cross compile on Fedora using MinGW-W64**

* [NodeJS Native](https://nodejs.org/)
* [Rust](https://rustup.rs/)

## How to Build

* Get source from codeberg
    ```bash
    git clone https://codeberg.org/chewing/windows-chewing-tsf.git
    cd windows-chewing-tsf
    ```
* Use this xtask command to build the installer
    ```
    cargo xtask build-installer --target msvc --release
    cargo xtask download-components
    cargo xtask package-installer
    ```

## TSF References

* [Text Services Framework](http://msdn.microsoft.com/en-us/library/windows/desktop/ms629032%28v=vs.85%29.aspx)
* [Guidelines and checklist for IME development (Windows Store apps)](http://msdn.microsoft.com/en-us/library/windows/apps/hh967425.aspx)
* [Input Method Editors (Windows Store apps)](http://msdn.microsoft.com/en-us/library/windows/apps/hh967426.aspx)
* [Third-party input method editors](http://msdn.microsoft.com/en-us/library/windows/desktop/hh848069%28v=vs.85%29.aspx)
* [Strategies for App Communication between Windows 8 UI and Windows 8 Desktop](http://software.intel.com/en-us/articles/strategies-for-app-communication-between-windows-8-ui-and-windows-8-desktop)
* [TSF Aware, Dictation, Windows Speech Recognition, and Text Services Framework. (blog)](http://blogs.msdn.com/b/tsfaware/?Redirected=true)
* [Win32 and COM for Windows Store apps](http://msdn.microsoft.com/en-us/library/windows/apps/br205757.aspx)
* [Input Method Editor (IME) sample supporting Windows 8](http://code.msdn.microsoft.com/windowsdesktop/Input-Method-Editor-IME-b1610980)

## Windows ACL (Access Control List) references

* [The Windows Access Control Model Part 1](http://www.codeproject.com/Articles/10042/The-Windows-Access-Control-Model-Part-1#SID)
* [The Windows Access Control Model: Part 2](http://www.codeproject.com/Articles/10200/The-Windows-Access-Control-Model-Part-2#SidFun)
* [Windows 8 App Container Security Notes - Part 1](http://recxltd.blogspot.tw/2012/03/windows-8-app-container-security-notes.html)
* [How AccessCheck Works](http://msdn.microsoft.com/en-us/library/windows/apps/aa446683.aspx)
* [GetAppContainerNamedObjectPath function (enable accessing object outside app containers using ACL)](http://msdn.microsoft.com/en-us/library/windows/desktop/hh448493)
* [Creating a DACL](http://msdn.microsoft.com/en-us/library/windows/apps/ms717798.aspx)

# Code Signing Policy

This [project](https://signpath.org/projects/chewing-im/) is sponsored by SignPath. We use free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

**People and roles:**

* Committers and reviewers: [Chewing core team](https://codeberg.org/org/chewing/teams/owners), [Windows Chewing maintainers](https://codeberg.org/org/chewing/teams/windows)
* Approvers: [Chewing core team](https://codeberg.org/org/chewing/teams/owners)

# Privacy Policy

This program will not transfer any information to other networked systems unless
specifically requested by the user or the person installing or operating it.

# Bug Report
Please report any issue to [here](https://codeberg.org/chewing/windows-chewing-tsf/issues).
