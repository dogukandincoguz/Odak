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
from odak.ui import MainWindow, TaskDialog, configure_app
from odak.panels import ReminderDialog


app = QApplication([])
configure_app(app)
output = PROJECT / "artifacts"
output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    store = Store(Path(directory) / "preview.sqlite3")
    now = datetime.now().replace(second=0, microsecond=0)
    store.save("Proje sunumunu tamamla", "Son slaytları gözden geçir, demo akışını dene.", now + timedelta(hours=5, minutes=20), True,
               steps=["Slaytları gözden geçir", "Demo akışını dene"], today=True)
    store.save("Yeni fikrin taslağını çıkar", "İlk adımı küçük tut. Başlamak da ilerlemektir.", now + timedelta(days=2, hours=3), True)
    store.save("Haftalık okuma listesi", "Bir kahve, birkaç sayfa. Kendi hızında.")
    store.save("Yeni bir dil öğren", "Aklındaki fikirler için biraz alan.", someday=True)
    store.save_template("Sunum hazırlığı", "Sunumu hazırla", "Gündem ve demoyu birlikte kontrol et.", ["Verileri topla", "Slaytları düzenle", "Prova yap"])
    store.save_reminder("Haftalık ekip toplantısı", "Gündem maddelerini yanında bulundur.", [0], "14:00", lead_minutes=10, link="https://meet.google.com/abc-defg-hij")
    store.save_reminder("Kısa bir yürüyüş", "Ekrandan uzaklaş, biraz hava al.", list(range(5)), "17:30")
    removed = store.save_reminder("Eski takvim hatırlatması", "Gerekirse geri alabilirsin.", [4], "11:00")
    store.delete_reminder(removed)
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
    long_task = store.save("Uzun bir görev adı: proje sunumunun son kontrollerini tamamla ve toplantı öncesinde bütün notları gözden geçir")
    window.focus_panel.refresh_tasks()
    window.focus_panel.choose_task(long_task)
    app.processEvents()
    window.grab().save(str(output / "odak-focus-selected.png"))
    window.focus_panel.task.showPopup()
    app.processEvents()
    window.focus_panel.task.view().window().grab().save(str(output / "odak-gorev-secimi.png"))
    window.focus_panel.task.hidePopup()
    window.set_view("reminders")
    window.reminder_panel.set_tab("trash")
    app.processEvents()
    window.grab().save(str(output / "odak-silinen-hatirlatmalar.png"))
    window.set_view("tasks")
    window.set_tab("today")
    app.processEvents()
    window.grab().save(str(output / "odak-bugun.png"))
    dialog = TaskDialog(window)
    dialog.title.setText("Bir sonraki güzel fikir")
    dialog.show()
    app.processEvents()
    dialog.title.deselect()
    dialog.grab().save(str(output / "odak-yeni-gorev.png"))
    dialog.use_date.setChecked(True)
    dialog.use_time.setChecked(True)
    app.processEvents()
    dialog.grab().save(str(output / "odak-gorev-tarih-saat.png"))
    dialog.hide()
    reminder_dialog = ReminderDialog(window)
    reminder_dialog.title.setText("Haftalık toplantı")
    reminder_dialog.show()
    app.processEvents()
    reminder_dialog.title.deselect()
    reminder_dialog.grab().save(str(output / "odak-yeni-hatirlatma.png"))
    reminder_dialog.kind.setCurrentIndex(reminder_dialog.kind.findData("once"))
    reminder_dialog.date.setDate(reminder_dialog.date.date().addDays(1))
    reminder_dialog.lead.setCurrentIndex(reminder_dialog.lead.findData(10))
    app.processEvents()
    reminder_dialog.grab().save(str(output / "odak-tek-hatirlatma.png"))
    reminder_dialog.kind.setCurrentIndex(reminder_dialog.kind.findData("monthly_weekday"))
    reminder_dialog.ordinal.setCurrentIndex(reminder_dialog.ordinal.findData(-1))
    reminder_dialog.month_weekday.setCurrentIndex(4)
    app.processEvents()
    reminder_dialog.grab().save(str(output / "odak-aylik-hatirlatma.png"))
    reminder_dialog.hide()
    from odak.templates import TemplateManager, TemplateEditor
    manager = TemplateManager(window, store)
    manager.show()
    app.processEvents()
    manager.grab().save(str(output / "odak-sablonlar.png"))
    manager.hide()
    editor = TemplateEditor(window, store, store.templates()[0])
    editor.show()
    app.processEvents()
    editor.grab().save(str(output / "odak-sablon-duzenle.png"))
    editor.hide()
    window.hide()
    store.close()
print("Ekran görüntüleri: artifacts/")
