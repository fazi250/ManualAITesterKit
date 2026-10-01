"""Full-screen HD evidence (taskbar and clock included) on Windows, with safe fallbacks.

A full-screen snap is only taken when the kit browser is verified to be the front window.
If Windows is locked or the browser can't come to the front, a browser-only capture is saved
instead, so evidence never shows other windows.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import Page

from .config import QA, fail, rel

IS_WIN = sys.platform == "win32"

if IS_WIN:
    import winsound
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetForegroundWindow.restype = wintypes.HWND
    for _name, _args in {
        "SetForegroundWindow": [wintypes.HWND], "BringWindowToTop": [wintypes.HWND],
        "ShowWindow": [wintypes.HWND, ctypes.c_int], "IsIconic": [wintypes.HWND], "IsWindowVisible": [wintypes.HWND],
        "SwitchToThisWindow": [wintypes.HWND, wintypes.BOOL], "GetWindowTextLengthW": [wintypes.HWND],
        "GetWindowTextW": [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],
        "GetClassNameW": [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],
        "GetWindowRect": [wintypes.HWND, ctypes.POINTER(wintypes.RECT)],
        "AttachThreadInput": [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL],
        "keybd_event": [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p],
        "EnumWindows": [_ENUM_PROC, wintypes.LPARAM], "SwitchDesktop": [wintypes.HANDLE], "CloseDesktop": [wintypes.HANDLE],
        "RegisterHotKey": [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT],
        "UnregisterHotKey": [wintypes.HWND, ctypes.c_int],
        "GetMessageW": [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT],
        "GetCursorPos": [ctypes.POINTER(wintypes.POINT)],
    }.items():
        getattr(user32, _name).argtypes = _args
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.OpenInputDesktop.restype = wintypes.HANDLE

    try:  # real pixels on 125% / 150% displays
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if not user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            user32.SetProcessDPIAware()
    except AttributeError:
        user32.SetProcessDPIAware()


def _title(hwnd: int | None) -> str:
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def is_locked() -> bool:
    if _title(user32.GetForegroundWindow()) == "Windows Default Lock Screen":
        return True
    desk = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not desk:
        return True
    try:
        return not user32.SwitchDesktop(desk)
    finally:
        user32.CloseDesktop(desk)


def _browser_pid(page: Page) -> int | None:
    browser = page.context.browser
    if browser is None:
        return None
    try:
        cdp = browser.new_browser_cdp_session()
        info = cdp.send("SystemInfo.getProcessInfo")
        cdp.detach()
    except Exception:
        return None
    return next((int(p["id"]) for p in info.get("processInfo", []) if p.get("type") == "browser"), None)


def _window_of(pid: int) -> int | None:
    found: list[int] = []

    def visit(hwnd: int, _: int) -> bool:
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if (owner.value == pid and user32.IsWindowVisible(hwnd) and cls.value == "Chrome_WidgetWin_1"
                and user32.GetWindowTextLengthW(hwnd) > 0):
            found.append(hwnd)
        return True

    user32.EnumWindows(_ENUM_PROC(visit), 0)
    return found[0] if found else None


def _is_front(hwnd: int) -> bool:
    return (user32.GetForegroundWindow() or 0) == hwnd


def _focus(hwnd: int) -> bool:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # restore
    me = kernel32.GetCurrentThreadId()
    fg = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    attached = fg != me and bool(user32.AttachThreadInput(me, fg, True))
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    if attached:
        user32.AttachThreadInput(me, fg, False)
    if _is_front(hwnd):
        return True
    user32.keybd_event(0x12, 0, 0, None)  # Alt tap lets a background app take focus
    user32.keybd_event(0x12, 0, 2, None)
    user32.SetForegroundWindow(hwnd)
    if _is_front(hwnd):
        return True
    user32.SwitchToThisWindow(hwnd, True)
    time.sleep(0.2)
    if _is_front(hwnd):
        return True
    user32.ShowWindow(hwnd, 6)  # minimize, then maximize
    user32.ShowWindow(hwnd, 3)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    return _is_front(hwnd)


def _grab(path: Path, x: int, y: int) -> str:
    """Saves the monitor that contains point (x, y). Returns its size."""
    import mss
    import mss.tools

    with mss.mss() as screens:
        monitors = screens.monitors[1:]
        mon = next((m for m in monitors if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]),
                   monitors[0])
        shot = screens.grab(mon)
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))
        return f"{shot.width}x{shot.height}"


def _page_capture(page: Page, path: Path, reason: str) -> str:
    page.screenshot(path=str(path))
    return f"{rel(path)} ({reason}: browser-only capture)"


def snap_step(page: Page, test_id: str, step: int) -> str:
    """qa/evidence/<id>/step-NN.png with the browser in front. Returns the saved path (+ note)."""
    folder = QA / "evidence" / test_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"step-{step:02d}.png"
    if os.environ.get("QA_SNAP_MODE") == "page" or not IS_WIN:
        return _page_capture(page, path, "QA_SNAP_MODE=page" if IS_WIN else "not Windows")
    if is_locked():
        return _page_capture(page, path, "screen locked")
    page.bring_to_front()
    pid = _browser_pid(page)
    hwnd = _window_of(pid) if pid else None
    if not hwnd or not _focus(hwnd):
        return _page_capture(page, path, "browser not in front")
    time.sleep(0.5)
    if not _is_front(hwnd):
        return _page_capture(page, path, "browser not in front")
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    _grab(path, (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    return rel(path)


def hotkey_mode(test_id: str, key: str = "P") -> None:
    """Your own manual testing: Ctrl+Alt+<key> snaps the screen under the mouse, Ctrl+Alt+Q stops."""
    if not IS_WIN:
        fail("Hotkey mode works on Windows only")
    folder = QA / "evidence" / test_id
    folder.mkdir(parents=True, exist_ok=True)
    key = key.upper()
    if len(key) == 1 and key.isalnum():
        vk = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        vk = 0x6F + int(key[1:])
    else:
        fail(f"--key must be a letter, digit or F1-F12, got {key}")
    mods = 0x1 | 0x2 | 0x4000  # Alt + Ctrl, no auto-repeat
    if not user32.RegisterHotKey(None, 1, mods, vk):
        fail(f"Ctrl+Alt+{key} is taken by another app. Try --key F9.")
    if not user32.RegisterHotKey(None, 2, mods, ord("Q")):
        user32.UnregisterHotKey(None, 1)
        fail("Ctrl+Alt+Q is taken by another app.")
    print(f"[{test_id}] Ctrl+Alt+{key} = snap next step, Ctrl+Alt+Q = stop. Saving to {rel(folder)}", flush=True)
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message != 0x0312:  # WM_HOTKEY
                continue
            if msg.wParam != 1:
                break
            numbers = [int(p.stem[5:]) for p in folder.glob("step-*.png") if p.stem[5:].isdigit()]
            path = folder / f"step-{max(numbers, default=0) + 1:02d}.png"
            cursor = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(cursor))
            size = _grab(path, cursor.x, cursor.y)
            winsound.MessageBeep()
            print(f"Saved {rel(path)} ({size})", flush=True)
    finally:
        user32.UnregisterHotKey(None, 1)
        user32.UnregisterHotKey(None, 2)
        print("Stopped.")
