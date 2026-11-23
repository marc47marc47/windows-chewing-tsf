"""Drives the guided WebView IME test with real keyboard events (keybd_event) - no mouse.
Run with the Windows Python:  /c/Python313/python.exe drive.py
It restores CapsLock to its original state at the end.
"""
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes

u = ctypes.windll.user32
TITLE = "新酷音 IME 引導測試"
DIR = r"C:\Users\marc4\rust\windows-chewing-tsf\tmp\webpad"
BUN = r"C:\Users\marc4\.local\bin\bun.exe"

VK = {"esc": 0x1B, "tab": 0x09, "space": 0x20, "caps": 0x14, "shift": 0x10, "alt": 0x12, "slash": 0xBF}
for c in "abcdefghijklmnopqrstuvwxyz0123456789":
    VK[c] = ord(c.upper())


def key(name, down=True, up=True):
    vk = VK[name]
    if down:
        u.keybd_event(vk, 0, 0, 0)
    if up:
        u.keybd_event(vk, 0, 2, 0)


def tap(name, pause=0.25):
    key(name)
    time.sleep(pause)


def find_windows():
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        n = u.GetWindowTextLengthW(h)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, buf, n + 1)
            if TITLE in buf.value and u.IsWindowVisible(h):
                found.append(h)
        return True

    u.EnumWindows(cb, 0)
    return found


def focus(h):
    key("alt")  # Alt tap: lets SetForegroundWindow succeed
    u.SetForegroundWindow(h)
    time.sleep(0.8)


def caps_on():
    return bool(u.GetKeyState(0x14) & 1)


def set_caps(want):
    if caps_on() != want:
        tap("caps", 0.6)


def alt_tab():
    key("alt", up=False)
    time.sleep(0.15)
    key("tab")
    time.sleep(0.15)
    key("alt", down=False)
    time.sleep(1.0)


def next_step():
    """Shift+Tab twice reaches the '這步做完了' button, Space presses it; the page re-focuses the text box."""
    key("esc")
    time.sleep(0.3)
    key("shift", up=False)
    tap("tab", 0.2)
    tap("tab", 0.2)
    key("shift", down=False)
    time.sleep(0.2)
    tap("space", 0.8)


def click_box(h):
    """Click inside the text box so the WebView really owns keyboard focus (the original cursor is restored)."""
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    x, y = (r.left + r.right) // 2, r.top + int((r.bottom - r.top) * 0.62)
    old = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(old))
    u.SetCursorPos(x, y)
    time.sleep(0.15)
    u.mouse_event(0x0002, 0, 0, 0, 0)  # left down
    u.mouse_event(0x0004, 0, 0, 0, 0)  # left up
    time.sleep(0.4)
    u.SetCursorPos(old.x, old.y)


def ensure_focus(h):
    if u.GetForegroundWindow() != h:
        focus(h)
    click_box(h)


def skip_step():
    """Shift+Tab once reaches the '略過' button."""
    key("esc")
    time.sleep(0.3)
    key("shift", up=False)
    tap("tab", 0.3)
    key("shift", down=False)
    time.sleep(0.2)
    tap("space", 0.8)


def type_keys(h, keys, pause=0.45):
    ensure_focus(h)
    for k in keys:
        tap(k, pause)


def main():
    for h in find_windows():  # close a leftover instance
        u.PostMessageW(h, 0x0010, 0, 0)
    time.sleep(1.5)
    subprocess.Popen([BUN, "guided.ts"], cwd=DIR)
    for _ in range(40):
        time.sleep(0.5)
        if find_windows():
            break
    else:
        sys.exit("test window did not appear")
    time.sleep(2.5)
    h = find_windows()[0]
    original_caps = caps_on()
    focus(h)
    try:
        # step 1: Chinese mode (CapsLock on = Chinese in this user's config)
        ensure_focus(h)
        set_caps(True)
        time.sleep(1.0)
        type_keys(h, ["t", "slash"])
        next_step()
        # step 2: English (CapsLock off)
        ensure_focus(h)
        set_caps(False)
        time.sleep(1.0)
        type_keys(h, ["a", "b", "c"], 0.35)
        next_step()
        # step 3: back to Chinese
        ensure_focus(h)
        set_caps(True)
        time.sleep(1.0)
        type_keys(h, ["t", "slash", "6"])
        next_step()
        # steps 4 and 5 need Alt+Tab: left to the user
        ensure_focus(h)
        skip_step()
        skip_step()
    finally:
        for vk in (0x10, 0x12, 0x11):
            u.keybd_event(vk, 0, 2, 0)
        time.sleep(0.5)
        set_caps(original_caps)
        print("CapsLock restored to", caps_on())
    res = json.load(open(DIR + "/results.json", encoding="utf-8"))
    for r in res:
        status = "SKIP" if r["ok"] is None else "PASS" if r["ok"] else "FAIL"
        print(status, r["step"], "composition=%d keys=%d inputs=%r blur=%d" % (r["composition"], r["keys"], r["inputs"], r["blur"]))


main()
