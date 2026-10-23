"""Bootstrap sonrası güvenli dosya güncellemesi ve kullanıcı verisinin korunması.

Yalnız standart kütüphane kullanır; PySide6 kurulmadan da çalışır.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path, PurePosixPath

FORMAT = "odak-install-v1"
ROOT_FILES = {"app.py", "bootstrap.ps1", "install.ps1", "install.sh", ".python-version",
              "pyproject.toml", "uv.lock", "README.md"}
TOOL_FILES = {"tools/install_state.py", "tools/install_desktop.py"}
MARKER = ".odak-install.json"


def managed_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative.replace("\\", "/"))
    if parts.is_absolute() or ".." in parts.parts or not parts.parts:
        raise ValueError("Kurulum dosya yolu geçersiz.")
    if not (str(parts) in ROOT_FILES or parts.parts[0] in ("odak", "assets") or str(parts) in TOOL_FILES):
        raise ValueError("Kurulum yalnız uygulama dosyalarını değiştirebilir.")
    target = root.joinpath(*parts.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Kurulum dosyası hedef klasörün dışına çıkıyor.")
    # Junction/symlink parents are not part of a managed installation.
    for path in [target, *target.parents]:
        if path == root.parent:
            break
        if path.is_symlink() or path.is_junction():
            raise ValueError("Kurulum yolunda sembolik bağ bulunuyor.")
    return target


def source_files(source: Path) -> list[str]:
    files = [p for p in ROOT_FILES if (source/p).is_file()]
    for directory in ("odak", "assets"):
        files.extend(p.relative_to(source).as_posix() for p in (source/directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    files.extend(relative for relative in TOOL_FILES if (source / relative).is_file())
    for relative in files:
        managed_path(source, relative)
    required = {"app.py", "install.ps1", "install.sh", "bootstrap.ps1", ".python-version", "pyproject.toml", "uv.lock",
                "tools/install_state.py", "tools/install_desktop.py", "odak/ui.py", "odak/model.py",
                "assets/fonts/Inter.ttf", "assets/fonts/OFL.txt", "assets/odak.ico", "assets/odak.png", "assets/odak.icns"}
    if not required <= set(files):
        raise ValueError("Kurulum arşivinde gerekli uygulama dosyaları eksik.")
    return sorted(files)


def stop_running(data: Path):
    lock = data/"odak.lock"
    if not lock.exists():
        return
    try:
        pid = int(lock.read_text(encoding="utf-8").splitlines()[0])
    except (ValueError, IndexError, UnicodeError):
        raise RuntimeError("Odak kilidi okunamadı. Uygulamayı kapatıp yeniden dene.")
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        raise RuntimeError("Güncellemeden önce açık Odak penceresini kapat; görevlerin ve taslakların korunuyor.")
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    process = kernel32.OpenProcess(0x1000, False, pid)
    if not process:
        return  # Qt handles a stale lock on next launch.
    try:
        status = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(process, ctypes.byref(status)) and status.value != 259:
            return
    finally:
        kernel32.CloseHandle(process)
    windows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowEnabled.argtypes = [wintypes.HWND]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]

    @callback_type
    def inspect(hwnd, _):
        identity = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(identity))
        if identity.value == pid:
            caption = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, caption, len(caption))
            if caption.value == "Odak · Görevlerin":
                windows.append(hwnd)
        return True
    user32.EnumWindows(inspect, 0)
    if not windows or any(not user32.IsWindowEnabled(w) for w in windows):
        raise RuntimeError("Odak'ta açık bir form var veya uygulama meşgul. Taslağını kaydedip Odak'ı kapat; sonra kurulumu yeniden çalıştır.")
    for hwnd in windows:
        if not user32.PostMessageW(hwnd, 0x10, 0, 0):
            raise RuntimeError("Odak kapatılamadı. Çarpıdan kapatıp yeniden dene.")
    until = time.monotonic()+8
    while lock.exists() and time.monotonic() < until:
        time.sleep(.05)
    if lock.exists():
        raise RuntimeError("Odak henüz kapanmadı. Uygulamayı kapatıp yeniden dene.")


def database_copy(source: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name+".install-tmp")
    if temporary.exists():
        raise RuntimeError("Önceki veri kopyası tamamlanmamış; .install-tmp dosyasını kontrol et.")
    try:
        with closing(sqlite3.connect(source.resolve().as_uri()+"?mode=ro", uri=True)) as incoming:
            if incoming.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Görev veritabanı doğrulanamadı; mevcut veriler korunuyor.")
            columns = {r[1] for r in incoming.execute("PRAGMA table_info(tasks)")}
            if not {"id", "title", "deadline", "created_at"} <= columns:
                raise ValueError("Kaynak veritabanı Odak'a ait değil.")
            output = sqlite3.connect(temporary)
            try:
                incoming.backup(output)
            finally:
                output.close()
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_data(data: Path, legacy: Path | None = None):
    database = data/"odak.sqlite3"
    # Stop only the instance whose data is being updated or migrated.
    if database.exists():
        stop_running(data)
    elif legacy and (legacy/"odak.sqlite3").exists() and legacy.resolve() != data.resolve():
        stop_running(legacy)
        database_copy(legacy/"odak.sqlite3", database)
        print("Mevcut görevler yeni veri klasörüne kopyalandı; eski kopya korundu.")
    data.mkdir(parents=True, exist_ok=True)
    if database.exists():
        backups = data/"backups"
        backups.mkdir(exist_ok=True)
        database_copy(database, backups/f"odak-{datetime.now():%Y-%m-%d-%H%M%S-%f}.sqlite3")
        own = sorted(p for p in backups.glob("odak-*.sqlite3")
                     if re.fullmatch(r"odak-\d{4}-\d{2}-\d{2}-\d{6}-\d{6}\.sqlite3", p.name))
        for old in own[:-3]:
            old.unlink()


@contextmanager
def install_lock(target: Path):
    with (target/".install.lock").open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Başka bir Odak kurulumu çalışıyor.")
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


RUNTIME_CHECK = """
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from odak.model import Store
from odak.ui import MainWindow, configure_app
app=QApplication([])
configure_app(app)
with tempfile.TemporaryDirectory() as directory:
    store=Store(Path(directory)/'check.sqlite3')
    window=MainWindow(store,Path.cwd(),with_tray=False)
    window.timer.stop()
    window.hide()
    store.close()
print('Odak calisma ortami dogrulandi.')
"""


def install(source: Path, target: Path, data: Path, uv: str, revision: str, ref: str,
            legacy: Path | None = None, no_launch=False, no_shortcuts=False):
    source, target, data = source.resolve(), target.absolute(), data.absolute()
    if target == Path(target.anchor) or data == Path(data.anchor) or source == target:
        raise ValueError("Kurulum ve veri klasörleri geçersiz.")
    if any(p.is_symlink() or p.is_junction() for p in [target, *target.parents, data, *data.parents]):
        raise ValueError("Kurulum ve veri klasörlerinde sembolik bağ kullanılamaz.")
    target, data = target.resolve(), data.resolve()
    if target == Path(target.anchor) or data == Path(data.anchor) or data.is_relative_to(target) or target.is_relative_to(data):
        raise ValueError("Uygulama ve veri klasörleri ayrı olmalı; disk kökü kullanılamaz.")
    files = source_files(source)
    marker = target/MARKER
    if target.exists() and not marker.exists() and any(target.iterdir()):
        raise ValueError("Hedef klasör dolu ve yönetilen Odak kurulumu değil.")
    previous = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else None
    if previous and previous.get("format") != FORMAT:
        raise ValueError("Kurulum kaydı geçersiz.")
    old_files = previous.get("files", []) if previous else []
    if not isinstance(old_files, list):
        raise ValueError("Kurulum dosya listesi geçersiz.")
    affected = sorted(set(files) | set(old_files))
    for relative in affected:
        path = managed_path(target, relative)
        if path.exists() and not path.is_file():
            raise ValueError("Uygulama dosyasının yerinde klasör bulunuyor.")
    target.mkdir(parents=True, exist_ok=True)
    with install_lock(target):
        prepare_data(data, legacy)
        initial = dict(format=FORMAT, data_dir=str(data), files=[], revision=None, ref=ref)
        if not previous:
            marker.write_text(json.dumps(initial), encoding="utf-8")
        environment = dict(os.environ)
        environment.pop("ODAK_GITHUB_TOKEN", None)
        environment.pop("VIRTUAL_ENV", None)
        environment["UV_PROJECT_ENVIRONMENT"] = str(target/".venv")
        with tempfile.TemporaryDirectory(prefix="odak-rollback-") as directory:
            rollback = Path(directory)
            existing = []
            for relative in affected:
                path = managed_path(target, relative)
                if path.is_file():
                    copy = rollback/relative
                    copy.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, copy)
                    existing.append(relative)
            try:
                for relative in files:
                    destination = managed_path(target, relative)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source/relative, destination)
                for relative in set(old_files)-set(files):
                    managed_path(target, relative).unlink(missing_ok=True)
                command = [uv, "sync", "--locked", "--no-dev", "--python", sys.executable, "--project", str(target)]
                subprocess.run(command, check=True, env=environment)
                runtime = target / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
                subprocess.run([str(runtime), "-c", RUNTIME_CHECK], cwd=target, check=True,
                               env={**environment, "QT_QPA_PLATFORM": "offscreen"})
            except BaseException:
                for relative in affected:
                    destination = managed_path(target, relative)
                    if relative in existing:
                        shutil.copy2(rollback/relative, destination)
                    else:
                        destination.unlink(missing_ok=True)
                print("Kurulum tamamlanamadı. Önceki uygulama dosyaları ve görev verileri korundu.", file=sys.stderr)
                raise
        state = dict(format=FORMAT, data_dir=str(data), files=files, revision=revision, ref=ref,
                     installed_at=datetime.now().isoformat())
        marker.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        if os.name == "nt":
            script = target/"install.ps1"
            command = [str(Path(os.environ["SystemRoot"])/"System32/WindowsPowerShell/v1.0/powershell.exe"),
                       "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-DataDir", str(data)]
        else:
            command = [str(runtime), str(target / "tools/install_desktop.py"), "--data-dir", str(data)]
        if no_shortcuts:
            command.append("-NoShortcuts" if os.name == "nt" else "--no-shortcuts")
        if not no_launch:
            command.append("-Launch" if os.name == "nt" else "--launch")
        subprocess.run(command, check=True, env=environment)
        print(f"Odak hazır. Uygulama: {target}\nGörev verileri: {data}")


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
        # Inherit the terminal's normal encoding, with a printable fallback.
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    parser = argparse.ArgumentParser()
    for name in ("source", "target", "data-dir", "uv", "revision", "ref"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--legacy-data-dir")
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--no-shortcuts", action="store_true")
    args = parser.parse_args()
    try:
        install(Path(args.source), Path(args.target), Path(args.data_dir), args.uv, args.revision, args.ref,
                Path(args.legacy_data_dir) if args.legacy_data_dir else None, args.no_launch, args.no_shortcuts)
    except Exception as exc:
        print("Odak kurulamadı: "+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
