from __future__ import annotations

import math
import time
from datetime import datetime

from PySide6.QtCore import QLocale, QDate, Qt, QTime
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QTextEdit,
    QTimeEdit, QVBoxLayout, QWidget)

from .model import Reminder, UNDO_SECONDS, category
from .schedule import DAYS, DAY_SHORTS
from .ui import app_icon, icon, label, tool


class ReminderDialog(QDialog):
    def __init__(self, owner, reminder: Reminder | None = None):
        super().__init__(owner, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Hatırlatmayı düzenle" if reminder else "Yeni düzenli hatırlatma")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(13)
        layout.addWidget(label("DÜZENLİ HATIRLATMA", "eyebrow"))
        layout.addWidget(label("Takvimin seni hatırlasın.", "section"))
        self.title = QLineEdit(reminder.title if reminder else "")
        self.title.setMaxLength(180)
        self.title.setPlaceholderText("Örneğin: Haftalık toplantı")
        self.title.setAccessibleName("Hatırlatma başlığı")
        layout.addWidget(self.title)
        self.notes = QTextEdit()
        self.notes.setAcceptRichText(False)
        self.notes.setFixedHeight(74)
        self.notes.setPlaceholderText("İsteğe bağlı not")
        self.notes.setAccessibleName("Hatırlatma notu")
        self.notes.setPlainText(reminder.notes if reminder else "")
        layout.addWidget(self.notes)
        layout.addWidget(label("Hangi günler?", "muted"))
        days = QHBoxLayout()
        days.setSpacing(3)
        self.days = []
        for index, short in enumerate(DAY_SHORTS):
            button = QPushButton(short)
            button.setObjectName("tab")
            button.setAccessibleName(DAYS[index])
            button.setCheckable(True)
            button.setChecked(index in reminder.weekdays if reminder else index == datetime.now().weekday())
            button.toggled.connect(self.validate)
            days.addWidget(button, 1)
            self.days.append(button)
        layout.addLayout(days)
        presets = QHBoxLayout()
        for text, selected in (("Her gün", range(7)), ("Hafta içi", range(5))):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, values=selected: self.select_days(values))
            presets.addWidget(button)
        layout.addLayout(presets)
        layout.addWidget(label("Hatırlatma saati", "muted"))
        self.clock = QTimeEdit()
        self.clock.setDisplayFormat("HH:mm")
        self.clock.setTime(QTime.fromString(reminder.clock, "HH:mm") if reminder else QTime(9, 0))
        self.clock.setAccessibleName("Hatırlatma saati")
        layout.addWidget(self.clock)
        layout.addWidget(label("Seçilen günlerde Windows bildirimi alırsın. Her tekrar aynı kayıt üzerinde ilerler.", "muted", True))
        actions = QHBoxLayout()
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton("Kaydet" if reminder else "Hatırlatmayı ekle")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setDefault(True)
        actions.addWidget(cancel)
        actions.addWidget(self.save_button, 1)
        layout.addLayout(actions)
        self.title.textChanged.connect(self.validate)
        self.validate()
        self.title.setFocus()

    def validate(self):
        if hasattr(self, "save_button"):
            self.save_button.setEnabled(bool(self.title.text().strip()) and any(b.isChecked() for b in self.days))

    def select_days(self, selected):
        for index, button in enumerate(self.days):
            button.setChecked(index in selected)

    def values(self):
        return dict(title=self.title.text(), notes=self.notes.toPlainText(),
                    weekdays=[i for i, button in enumerate(self.days) if button.isChecked()],
                    clock=self.clock.time().toString("HH:mm"))


class ReminderPanel(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.snapshot = None
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        body.addWidget(label("Düzenli hatırlatmalar", "section"))
        body.addWidget(label("Toplantılar, randevular, küçük hatırlatmalar. Takvim kendi ritminde ilerler.", "muted", True))
        add = QPushButton("  Yeni hatırlatma")
        add.setObjectName("primary")
        add.setIcon(icon("plus", "#14132a"))
        add.setFixedHeight(43)
        add.clicked.connect(lambda: self.edit_reminder())
        body.addWidget(add)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Hatırlatmalarda ara…")
        self.search.setAccessibleName("Hatırlatmalarda ara")
        self.search.textChanged.connect(lambda: self.refresh(force=True))
        body.addWidget(self.search)
        self.deleted = QCheckBox("Son silinenleri göster · 10 dk geri alma")
        self.deleted.toggled.connect(lambda: self.refresh(force=True))
        body.addWidget(self.deleted)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.list_layout = QVBoxLayout(content)
        self.list_layout.setContentsMargins(0, 0, 5, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(content)
        body.addWidget(self.scroll, 1)
        self.countdowns = []

    def change(self, action, message):
        self.owner.perform(action, message)
        self.refresh(force=True)

    def edit_reminder(self, reminder: Reminder | None = None):
        dialog = ReminderDialog(self.owner, reminder)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        values = dialog.values() if accepted else None
        dialog.deleteLater()
        if accepted:
            self.change(lambda: self.owner.store.save_reminder(**values, reminder_id=reminder.id if reminder else None),
                        "Hatırlatma kaydedildi.")
            self.owner.set_view("reminders")

    def refresh(self, force=False):
        from .ui import search_key
        reminders = self.owner.store.reminders()
        reminders = [r for r in reminders if (r.deleted_at is not None) == self.deleted.isChecked()]
        query = search_key(self.search.text().strip())
        reminders = [r for r in reminders if not query or query in search_key(r.title + " " + r.notes)]
        for countdown, deleted_at in self.countdowns:
            remaining = max(0, math.ceil(deleted_at + UNDO_SECONDS - time.time()))
            countdown.setText(f"Geri alma süresi: {remaining // 60}:{remaining % 60:02d}")
        snapshot = tuple(reminders)
        if not force and snapshot == self.snapshot:
            return
        self.snapshot = snapshot
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.countdowns = []
        if not reminders:
            empty = label("Henüz bir hatırlatma yok.\nBir program ekle, zamanı gelince haber verelim.", "muted", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setContentsMargins(20, 40, 20, 20)
            self.list_layout.addWidget(empty)
        for reminder in reminders:
            self.list_layout.addWidget(self.card(reminder))

    def card(self, reminder: Reminder):
        card = QFrame()
        card.setObjectName("reminderCard")
        accent = "#718098" if reminder.paused else "#80d3b5"
        card.setStyleSheet(f"QFrame#reminderCard {{background: #1a2231; border: 1px solid #2b374c; border-left: 3px solid {accent}; border-radius: 12px;}}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 12, 10, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        heading = label(reminder.title, wrap=True)
        heading.setStyleSheet("font-weight: 600; font-size: 14px;")
        header.addWidget(heading, 1)
        if reminder.deleted_at is not None:
            header.addWidget(tool("undo", "Hatırlatmayı geri al", lambda: self.change(
                lambda: self.owner.store.restore_reminder(reminder.id), "Hatırlatma geri alındı.")))
        else:
            header.addWidget(tool("edit", "Hatırlatmayı düzenle", lambda: self.edit_reminder(reminder)))
            header.addWidget(tool("trash", "Hatırlatmayı sil · 10 dakika geri alınabilir", lambda: self.change(
                lambda: self.owner.store.delete_reminder(reminder.id), "Hatırlatma silindi. 10 dakika içinde geri alabilirsin.")))
        layout.addLayout(header)
        if reminder.notes:
            layout.addWidget(label(reminder.notes[:180], "muted", True))
        day_text = "Her gün" if len(reminder.weekdays) == 7 else "Hafta içi" if reminder.weekdays == tuple(range(5)) else ", ".join(DAY_SHORTS[i] for i in reminder.weekdays)
        layout.addWidget(label(day_text + " · " + reminder.clock, "muted", True))
        if reminder.deleted_at is not None:
            countdown = label("", "muted")
            layout.addWidget(countdown)
            self.countdowns.append((countdown, reminder.deleted_at))
            remaining = max(0, math.ceil(reminder.deleted_at + UNDO_SECONDS - time.time()))
            countdown.setText(f"Geri alma süresi: {remaining // 60}:{remaining % 60:02d}")
        else:
            text = "Duraklatıldı" if reminder.paused else "Sıradaki: " + QLocale("tr_TR").toString(QDate(reminder.next_at.date()), "d MMM ddd") + " · " + reminder.clock
            if reminder.snooze_at:
                text += "\nTekrar bildirimi: " + reminder.snooze_at.strftime("%d.%m %H:%M")
            status = label(text, wrap=True)
            status.setStyleSheet(f"color: {accent}; font-size: 11px;")
            layout.addWidget(status)
            actions = QHBoxLayout()
            pause = QPushButton("Devam ettir" if reminder.paused else "Duraklat")
            pause.clicked.connect(lambda: self.change(lambda: self.owner.store.pause_reminder(reminder.id, not reminder.paused),
                "Hatırlatma devam ediyor." if reminder.paused else "Hatırlatma duraklatıldı."))
            skip = QPushButton("Bu tekrarı atla")
            skip.setEnabled(not reminder.paused)
            skip.clicked.connect(lambda: self.change(lambda: self.owner.store.skip_reminder(reminder.id), "Sıradaki tekrar atlandı."))
            actions.addWidget(pause)
            actions.addWidget(skip)
            layout.addLayout(actions)
        return card

    def show_alert(self, reminder):
        current = next((r for r in self.owner.store.reminders() if r.id == reminder.id and r.deleted_at is None and not r.paused), None)
        if current is None:
            return
        dialog = QDialog(self.owner, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        dialog.setWindowTitle("Odak hatırlatması")
        dialog.setMinimumWidth(370)
        body = QVBoxLayout(dialog)
        body.setContentsMargins(24, 24, 24, 24)
        body.setSpacing(14)
        body.addWidget(label(current.title, "section", True))
        if current.notes:
            body.addWidget(label(current.notes, "muted", True))
        body.addWidget(label("İstersen 10 dakika sonra tekrar haber verelim. Düzenli programın aynı kalır.", "muted", True))
        snooze = QPushButton("10 dakika sonra hatırlat")
        snooze.setObjectName("primary")
        snooze.clicked.connect(dialog.accept)
        close = QPushButton("Kapat")
        close.clicked.connect(dialog.reject)
        body.addWidget(snooze)
        body.addWidget(close)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self.change(lambda: self.owner.store.snooze_reminder(current.id), "10 dakika sonra tekrar hatırlatılacak.")


class FocusPanel(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        preferences = owner.store.setting("focus_preferences", {})
        self.phase = "focus"
        self.running = False
        self.end_at = None
        self._task_snapshot = None
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)
        body.addWidget(label("Bir işe yer aç.", "section"))
        body.addWidget(label("Bir görev seç, süreyi başlat. Çalışma ve mola arasında kendi ritmini bul.", "muted", True))
        self.task = QComboBox()
        self.task.setAccessibleName("Odaklanılacak görev")
        body.addWidget(self.task)
        self.phase_label = label("ODAK ZAMANI", "eyebrow")
        self.phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addStretch()
        body.addWidget(self.phase_label)
        self.clock = label("25:00")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock.setStyleSheet("font-size: 62px; font-weight: 700; color: #c2b9ff;")
        body.addWidget(self.clock)
        self.hint = label("Hazır olduğunda başlat.", "muted", True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self.hint)
        body.addStretch()
        durations = QHBoxLayout()
        self.work = QSpinBox()
        self.work.setRange(1, 180)
        self.work.setValue(preferences.get("work", 25))
        self.work.setSuffix(" dk")
        self.work.setAccessibleName("Çalışma süresi")
        self.rest = QSpinBox()
        self.rest.setRange(1, 60)
        self.rest.setValue(preferences.get("rest", 5))
        self.rest.setSuffix(" dk")
        self.rest.setAccessibleName("Mola süresi")
        for title, spin in (("Çalışma", self.work), ("Mola", self.rest)):
            column = QVBoxLayout()
            column.addWidget(label(title, "muted"))
            column.addWidget(spin)
            durations.addLayout(column)
        body.addLayout(durations)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Başlat")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.toggle)
        reset = QPushButton("Sıfırla")
        reset.clicked.connect(self.reset)
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(reset)
        body.addLayout(buttons)
        body.addWidget(label("Sayaç, pencere tepsiye gizlendiğinde de çalışır.", "muted", True))
        self.remaining = self.work.value() * 60
        self.refresh_tasks()
        session = owner.store.setting("focus_session", {})
        if session:
            self.phase = session.get("phase", "focus")
            self.remaining = max(0, int(session.get("remaining", self.remaining)))
            self.running = bool(session.get("running"))
            self.end_at = session.get("end_at")
            self.choose_task(session.get("task_id"))
            if self.running and (not self.end_at or self.end_at <= time.time()):
                self.running = False
                self.end_at = None
                self.phase = "break" if self.phase == "focus" else "focus"
                self.remaining = (self.rest.value() if self.phase == "break" else self.work.value()) * 60
        self.work.valueChanged.connect(self.duration_changed)
        self.rest.valueChanged.connect(self.duration_changed)
        self.task.currentIndexChanged.connect(lambda: self.persist())
        self.render()

    def refresh_tasks(self):
        tasks = [t for t in self.owner.store.all() if category(t) not in ("done", "trash", "someday")]
        snapshot = tuple((t.id, t.title) for t in tasks)
        if snapshot == self._task_snapshot:
            return
        self._task_snapshot = snapshot
        current = self.task.currentData()
        self.task.blockSignals(True)
        self.task.clear()
        self.task.addItem("Serbest odak", None)
        for identity, title in snapshot:
            self.task.addItem(title, identity)
        self.choose_task(current)
        self.task.blockSignals(False)

    def choose_task(self, identity):
        index = self.task.findData(identity)
        self.task.setCurrentIndex(index if index >= 0 else 0)

    def persist(self):
        self.owner.store.set_setting("focus_preferences", {"work": self.work.value(), "rest": self.rest.value()})
        self.owner.store.set_setting("focus_session", {"phase": self.phase, "running": self.running,
            "end_at": self.end_at, "remaining": self.remaining, "task_id": self.task.currentData()})

    def duration_changed(self):
        if not self.running:
            self.remaining = (self.work.value() if self.phase == "focus" else self.rest.value()) * 60
        self.persist()
        self.render()

    def toggle(self):
        if self.running:
            self.remaining = max(0, math.ceil(self.end_at - time.time()))
            self.running = False
            self.end_at = None
        else:
            self.running = True
            self.end_at = time.time() + self.remaining
        self.persist()
        self.render()

    def reset(self):
        self.phase = "focus"
        self.running = False
        self.end_at = None
        self.remaining = self.work.value() * 60
        self.persist()
        self.render()

    def reload_preferences(self):
        preferences = self.owner.store.setting("focus_preferences", {})
        for widget, key, default in ((self.work, "work", 25), (self.rest, "rest", 5)):
            widget.blockSignals(True)
            widget.setValue(preferences.get(key, default))
            widget.blockSignals(False)
        self._task_snapshot = None
        self.refresh_tasks()
        self.reset()

    def tick(self, now: float | None = None):
        if self.running:
            self.remaining = max(0, math.ceil(self.end_at - (now if now is not None else time.time())))
            if self.remaining == 0:
                self.running = False
                self.end_at = None
                self.phase = "break" if self.phase == "focus" else "focus"
                self.remaining = (self.rest.value() if self.phase == "break" else self.work.value()) * 60
                self.owner.system_notice("Mola zamanı" if self.phase == "break" else "Mola bitti",
                    "Yeni süreyi hazır olduğunda başlatabilirsin.")
                self.persist()
        self.render()

    def render(self):
        self.phase_label.setText("ODAK ZAMANI" if self.phase == "focus" else "MOLA ZAMANI")
        remaining = max(0, math.ceil(self.end_at - time.time())) if self.running and self.end_at else self.remaining
        self.clock.setText(f"{remaining // 60:02d}:{remaining % 60:02d}")
        self.start_button.setText("Duraklat" if self.running else "Molayı başlat" if self.phase == "break" else "Başlat / devam et")
        self.task.setEnabled(not self.running)
        self.work.setEnabled(not self.running)
        self.rest.setEnabled(not self.running)
        self.hint.setText("Şu an yalnızca bu adım." if self.running else "Hazır olduğunda başlat.")
