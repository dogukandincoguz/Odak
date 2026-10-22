"""Açık Odak penceresinin Windows konumunu ve üstte kalma durumunu okur."""
import ctypes
import json
import sys
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")
user32 = ctypes.windll.user32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
found = []


@callback_type
def inspect(hwnd, _):
    length = user32.GetWindowTextLengthW(hwnd)
    text = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, text, length + 1)
    if text.value == "Odak · Görevlerin" and user32.IsWindowVisible(hwnd):
        rect = wintypes.RECT()
        process_id = wintypes.DWORD()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        extended_style = user32.GetWindowLongW(hwnd, -20)
        found.append({"title": text.value, "pid": process_id.value,
                      "always_on_top": bool(extended_style & 0x8),
                      "taskbar_hidden": bool(extended_style & 0x80) and not bool(extended_style & 0x40000),
                      "bounds": [rect.left, rect.top, rect.right, rect.bottom]})
    return True


user32.EnumWindows(inspect, 0)
print(json.dumps(found, ensure_ascii=False, indent=2))
if len(found) != 1 or not found[0]["always_on_top"] or not found[0]["taskbar_hidden"]:
    raise SystemExit(1)
