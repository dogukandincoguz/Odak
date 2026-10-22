from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from odak.model import Store
from odak.ui import MainWindow, app_icon, configure_app

PROJECT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Odak masaüstü görev takipçisi")
    parser.add_argument("--data-dir", type=Path, default=PROJECT / "data")
    args = parser.parse_args()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Odak.Desktop.1")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        args.data_dir / "odak.log", maxBytes=500_000, backupCount=2, encoding="utf-8")],
        format="%(asctime)s %(levelname)s %(message)s")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Odak")
    app.setOrganizationName("OdakDesktop")
    app.setWindowIcon(app_icon())
    configure_app(app)
    app.setQuitOnLastWindowClosed(False)

    def handle_exception(kind, value, traceback):
        logging.error("Beklenmedik hata", exc_info=(kind, value, traceback))
        QMessageBox.critical(None, "Odak", "Bir hata oluştu. Ayrıntılar data/odak.log dosyasına kaydedildi.\n\n" + str(value))
    sys.excepthook = handle_exception

    # Lock + local IPC: ikinci başlatma var olan pencereyi öne getirir.
    lock = QLockFile(str(args.data_dir / "odak.lock"))
    lock.setStaleLockTime(0)
    server_name = "odak-" + hashlib.sha256(str(args.data_dir.resolve()).casefold().encode()).hexdigest()[:24]
    if not lock.tryLock(100):
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(1500):
            socket.write(b"show")
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(server_name)
    if not server.listen(server_name):
        QMessageBox.warning(None, "Odak", "Pencereyi yeniden gösterme bağlantısı kurulamadı.")

    try:
        store = Store(args.data_dir / "odak.sqlite3")
    except Exception as exc:
        logging.exception("Veritabanı açılamadı")
        QMessageBox.critical(None, "Odak açılamadı", "Görev dosyası açılamadı.\n\n" + str(exc))
        lock.unlock()
        return 1
    window = MainWindow(store, PROJECT)

    def activate():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.close()
            connection.deleteLater()
        window.reveal()
    server.newConnection.connect(activate)

    def bind_screen(screen):
        screen.availableGeometryChanged.connect(lambda *_: window.anchor())
    for screen in app.screens():
        bind_screen(screen)
    app.screenAdded.connect(bind_screen)
    app.screenRemoved.connect(lambda *_: QTimer.singleShot(100, window.anchor))
    app.aboutToQuit.connect(store.close)
    app.aboutToQuit.connect(server.close)
    app.aboutToQuit.connect(lock.unlock)
    window.show()
    QTimer.singleShot(0, window.anchor)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
