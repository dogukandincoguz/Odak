import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

# Gerçek giriş noktasını çalıştır; test penceresi birkaç saniye sonra kapanır.
TIMED_APP = """
import sys
import app
from PySide6.QtCore import QTimer
class TimedApplication(app.QApplication):
    def __init__(self, *args):
        super().__init__(*args)
        QTimer.singleShot(5000, self.quit)
app.QApplication = TimedApplication
raise SystemExit(app.main())
"""


class LifecycleTests(unittest.TestCase):
    def test_second_launch_uses_existing_instance_and_exit_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
            command = [sys.executable, "-c", TIMED_APP, "--data-dir", directory]
            first = subprocess.Popen(command, cwd=PROJECT, env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                limit = time.monotonic() + 3
                while not (data / "odak.sqlite3").exists() and time.monotonic() < limit:
                    if first.poll() is not None:
                        self.fail("İlk uygulama açılamadı: " + first.communicate()[1].decode(errors="replace"))
                    time.sleep(0.04)
                self.assertTrue((data / "odak.lock").exists())
                second = subprocess.run([sys.executable, "app.py", "--data-dir", directory],
                    cwd=PROJECT, env=env, capture_output=True, timeout=4)
                self.assertEqual(second.returncode, 0, second.stderr.decode(errors="replace"))
                self.assertIsNone(first.poll(), "İlk uygulama açık kalmalı")
                out, errors = first.communicate(timeout=7)
                self.assertEqual(first.returncode, 0, errors.decode(errors="replace"))
                self.assertFalse((data / "odak.lock").exists(), "Çıkışta kilit bırakılmalı")
                log = (data / "odak.log").read_text(encoding="utf-8")
                self.assertNotIn("ERROR", log)
            finally:
                if first.poll() is None:
                    first.terminate()
                    first.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
