"""Üretim verisine dokunmadan ekran görüntüleri oluşturur."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from PySide6.QtWidgets import QApplication
from odak.model import Store
from odak.ui import MainWindow, TaskDialog, app_icon, configure_app


app = QApplication([])
configure_app(app)
output = PROJECT / "artifacts"
output.mkdir(exist_ok=True)
assets = PROJECT / "assets"
assets.mkdir(exist_ok=True)
assert app_icon().pixmap(128, 128).save(str(assets / "odak.ico"), "ICO")
with tempfile.TemporaryDirectory() as directory:
    store = Store(Path(directory) / "preview.sqlite3")
    now = datetime.now().replace(second=0, microsecond=0)
    store.save("Proje sunumunu tamamla", "Son slaytları gözden geçir, demo akışını dene.", now + timedelta(hours=5, minutes=20), True,
               steps=["Slaytları gözden geçir", "Demo akışını dene"], today=True)
    store.save("Yeni fikrin taslağını çıkar", "İlk adımı küçük tut. Başlamak da ilerlemektir.", now + timedelta(days=2, hours=3), True)
    store.save("Haftalık okuma listesi", "Bir kahve, birkaç sayfa. Kendi hızında.")
    store.save("Yeni bir dil öğren", "Aklındaki fikirler için biraz alan.", someday=True)
    store.save_reminder("Haftalık ekip toplantısı", "Gündem maddelerini yanında bulundur.", [0], "14:00")
    store.save_reminder("Kısa bir yürüyüş", "Ekrandan uzaklaş, biraz hava al.", list(range(5)), "17:30")
    store.save("Faturayı kontrol et", "Ödeme tarihini tekrar gözden geçir.", now - timedelta(hours=3), True)
    done = store.save("Çalışma alanını düzenle")
    store.complete(done, True)
    deleted = store.save("Eski taslağı incele")
    store.delete(deleted)
    window = MainWindow(store, PROJECT, with_tray=False)
    window.timer.stop()
    window.show()
    app.processEvents()
    window.grab().save(str(output / "odak-gorevler.png"))
    for tab in ("overdue", "trash"):
        window.set_tab(tab)
        app.processEvents()
        window.grab().save(str(output / f"odak-{tab}.png"))
    for view in ("reminders", "focus"):
        window.set_view(view)
        app.processEvents()
        window.grab().save(str(output / f"odak-{view}.png"))
    window.set_view("tasks")
    dialog = TaskDialog(window)
    dialog.title.setText("Bir sonraki güzel fikir")
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(output / "odak-yeni-gorev.png"))
    dialog.hide()
    window.hide()
    store.close()
print("Ekran görüntüleri: artifacts/")
