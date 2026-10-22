"""Windows başlangıç kısayolunu mevcut veri konumuyla yönetir."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import uuid
from pathlib import Path


def startup_directory() -> Path:
    if sys.platform != "win32":
        raise OSError("Windows başlangıç ayarı yalnız Windows'ta kullanılabilir.")
    folder_id = (ctypes.c_byte * 16).from_buffer_copy(
        uuid.UUID("B97D20BB-F46A-4C97-BA10-5E3608430854").bytes_le)
    path = ctypes.c_void_p()
    get_folder = ctypes.windll.shell32.SHGetKnownFolderPath
    get_folder.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                           ctypes.POINTER(ctypes.c_void_p)]
    get_folder.restype = ctypes.c_long
    free = ctypes.windll.ole32.CoTaskMemFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = None
    try:
        result = get_folder(ctypes.byref(folder_id), 0, None, ctypes.byref(path))
        if result != 0:
            raise OSError("Windows başlangıç klasörü bulunamadı.")
        return Path(ctypes.wstring_at(path.value))
    finally:
        if path.value:
            free(path)


class Startup:
    def __init__(self, project: Path, data: Path, directory: Path | None = None):
        self.project, self.data, self.directory = project, data, directory

    @property
    def shortcut(self) -> Path:
        return (self.directory if self.directory is not None else startup_directory()) / "Odak.lnk"

    def enabled(self) -> bool:
        return self.shortcut.is_file()

    def set_enabled(self, enabled: bool):
        shortcut = self.shortcut
        if not enabled:
            shortcut.unlink(missing_ok=True)
            return
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        command = [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(self.project / "install.ps1"), "-DataDir", str(self.data),
                   "-ShortcutDirectories", str(shortcut.parent)]
        try:
            subprocess.run(command, capture_output=True, check=True, timeout=15,
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           env={**os.environ, "PSModulePath": str(powershell.parent / "Modules")})
        except (OSError, subprocess.SubprocessError) as exc:
            raise OSError("Windows başlangıç kısayolu oluşturulamadı.") from exc
        if not shortcut.is_file():
            raise OSError("Windows başlangıç kısayolu oluşturulamadı.")
