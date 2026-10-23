"""Linux/macOS kaynak kurulumu için masaüstü başlatıcısı ve otomatik açılış."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from odak.platforms import default_data_directory
from odak.startup import Startup, desktop_entry


def create_launcher(project: Path, data: Path, directory: Path | None = None) -> Path:
    command = [sys.executable, str(project / "app.py"), "--data-dir", str(data)]
    if sys.platform == "darwin":
        target = (directory or Path.home() / "Applications") / "Odak.app"
        contents = target / "Contents"
        executable = contents / "MacOS/odak"
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("#!/bin/sh\nexec " + shlex.join(command) + "\n", encoding="utf-8")
        executable.chmod(0o755)
        resources = contents / "Resources"
        resources.mkdir(exist_ok=True)
        shutil.copy2(project / "assets/odak.icns", resources / "odak.icns")
        (contents / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleName": "Odak", "CFBundleDisplayName": "Odak",
            "CFBundleIdentifier": "io.github.dogukandincoguz.odak",
            "CFBundleExecutable": "odak", "CFBundlePackageType": "APPL",
            "CFBundleIconFile": "odak.icns", "LSUIElement": True,
        }))
        return target
    if not sys.platform.startswith("linux"):
        raise OSError("Bu başlatıcı yalnız Linux ve macOS içindir.")
    configured = Path(os.environ.get("XDG_DATA_HOME", ""))
    base = configured if configured.is_absolute() else Path.home() / ".local/share"
    target = (directory or base / "applications") / "odak.desktop"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(desktop_entry(command, project), encoding="utf-8")
    target.chmod(0o644)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--no-shortcuts", action="store_true")
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args()
    data = (args.data_dir or default_data_directory(PROJECT)).expanduser().resolve()
    data.mkdir(parents=True, exist_ok=True)
    if not args.no_shortcuts:
        print("Başlatıcı:", create_launcher(PROJECT, data))
        Startup(PROJECT, data).set_enabled(True)
    if args.launch:
        subprocess.Popen([sys.executable, str(PROJECT / "app.py"), "--data-dir", str(data)],
                         cwd=PROJECT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    print("Odak hazır. Görev verileri:", data)


if __name__ == "__main__":
    main()
