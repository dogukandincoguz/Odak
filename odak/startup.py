"""Oturum açılışında başlatmayı mevcut veri konumunu koruyarak yönetir."""
from __future__ import annotations

import ctypes
import os
import plistlib
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def startup_directory(platform: str | None = None) -> Path:
    platform = platform or sys.platform
    if platform == "darwin":
        return Path.home() / "Library/LaunchAgents"
    if platform.startswith("linux"):
        configured = Path(os.environ.get("XDG_CONFIG_HOME", ""))
        root = configured if configured.is_absolute() else Path.home() / ".config"
        return root / "autostart"
    if platform != "win32":
        raise OSError("Bu sistemde otomatik başlatma desteklenmiyor.")
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
    def __init__(self, project: Path, data: Path, directory: Path | None = None,
                 platform: str | None = None):
        self.project, self.data, self.directory = project, data, directory
        self.platform = platform or sys.platform

    @property
    def label(self) -> str:
        return {"win32": "Windows başlangıcı", "darwin": "macOS başlangıcı"}.get(
            self.platform, "Oturum açılışında başlat")

    @property
    def shortcut(self) -> Path:
        filename = {"win32": "Odak.lnk", "darwin": "io.github.dogukandincoguz.odak.plist"}.get(
            self.platform, "odak.desktop")
        return (self.directory if self.directory is not None else startup_directory(self.platform)) / filename

    def enabled(self) -> bool:
        return self.shortcut.is_file()

    def set_enabled(self, enabled: bool):
        shortcut = self.shortcut
        if not enabled:
            shortcut.unlink(missing_ok=True)
            return
        if self.platform != "win32":
            self._write_autostart(shortcut)
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

    def _write_autostart(self, shortcut: Path):
        command = [sys.executable, str(self.project / "app.py"), "--data-dir", str(self.data)]
        if self.platform == "darwin":
            content = plistlib.dumps({"Label": "io.github.dogukandincoguz.odak",
                                     "ProgramArguments": command,
                                     "WorkingDirectory": str(self.project),
                                     "RunAtLoad": True, "ProcessType": "Interactive",
                                     "LimitLoadToSessionType": "Aqua"})
        elif self.platform.startswith("linux"):
            content = desktop_entry(command, self.project).encode("utf-8")
        else:
            raise OSError("Bu sistemde otomatik başlatma desteklenmiyor.")
        shortcut.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=shortcut.parent, prefix=".odak-", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(content)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            temporary.chmod(0o644)
            temporary.replace(shortcut)
        finally:
            temporary.unlink(missing_ok=True)


def desktop_entry(command: list[str], project: Path) -> str:
    """Encode Exec arguments without a shell, including desktop-file escaping."""
    def value(text):
        return str(text).replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")

    def argument(text):
        if any(character in text for character in "\0\n\r"):
            raise ValueError("Başlatma yolunda geçersiz karakter var.")
        escaped = text.replace("%", "%%")
        for character in ("\\", '"', "`", "$"):
            escaped = escaped.replace(character, "\\" + character)
        return value('"' + escaped + '"')

    return ("[Desktop Entry]\nType=Application\nName=Odak\n"
            "Comment=Masaüstü görev ve hatırlatma uygulaması\n"
            f"Exec={' '.join(argument(part) for part in command)}\n"
            f"Path={value(project)}\nIcon={value(project / 'assets/odak.png')}\n"
            "Terminal=false\nStartupNotify=false\nCategories=Office;Utility;\n")
