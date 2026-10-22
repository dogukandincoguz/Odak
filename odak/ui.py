from __future__ import annotations

import math
import os
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, QLocale, QPointF, QRectF, QSize, Qt, QTime, QTimer
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QIcon, QKeySequence, QPainter,
                           QPainterPath, QPen, QPixmap, QShortcut)
from PySide6.QtWidgets import (QApplication, QCheckBox, QDateEdit, QDialog,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSystemTrayIcon, QTextEdit, QTimeEdit,
    QToolButton, QVBoxLayout, QWidget)

from .model import Store, Task, UNDO_SECONDS, category, make_deadline, time_label

COLORS = {"neutral": "#9a8bff", "urgent": "#ff828e", "soon": "#efc575",
          "overdue": "#ff828e", "done": "#80d3b5", "trash": "#9cacc2"}


def search_key(text: str) -> str:
    # Türkçe İ/i ve I/ı aramaları klavye düzeninden bağımsız eşleşsin.
    return text.casefold().replace("\u0307", "").replace("ı", "i")

STYLE = """
QWidget { color: #e8edf7; font-family: 'Segoe UI'; font-size: 13px; }
QFrame#surface { background: #111722; border: 1px solid #303849; border-radius: 20px; }
QDialog { background: #141b28; }
QLabel { background: transparent; border: none; }
QLabel#muted { color: #96a3b8; }
QLabel#eyebrow { color: #a398ed; font-size: 10px; font-weight: 700; }
QLabel#brand { font-size: 26px; font-weight: 700; letter-spacing: -1px; }
QLabel#section { font-size: 17px; font-weight: 650; }
QFrame#summary { background: #1d2438; border: 1px solid #343952; border-radius: 14px; }
QLabel#summaryValue { font-size: 28px; font-weight: 700; }
QLabel#summaryCaption { color: #b6bfd3; font-size: 11px; }
QPushButton { background: #242d3f; border: 1px solid #37435a; border-radius: 9px;
              padding: 9px 13px; font-weight: 600; }
QPushButton:hover { background: #303c54; border-color: #596780; }
QPushButton:pressed { background: #1c2537; }
QPushButton:focus { border: 1px solid #b3a8ff; }
QPushButton#primary { background: #a799ff; color: #14132a; border: 1px solid #a799ff; }
QPushButton#primary:hover { background: #bcafff; }
QPushButton#primary:disabled { background: #3c3a54; color: #8d88a6; border-color: #3c3a54; }
QPushButton#tab { background: transparent; color: #96a3b8; border: none;
                 border-radius: 8px; padding: 9px 7px; font-size: 11px; }
QPushButton#tab:hover { background: #202a3b; color: #e8edf7; }
QPushButton#tab:checked { background: #2a2c46; color: #d5cdff; }
QFrame#tabs { background: #171f2d; border-radius: 11px; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 5px; }
QToolButton:hover { background: #303a50; }
QToolButton:focus { border-color: #a799ff; }
QLineEdit, QTextEdit, QDateEdit, QTimeEdit { background: #101722; border: 1px solid #354158;
    border-radius: 9px; padding: 9px; selection-background-color: #6555ae; }
QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QTimeEdit:focus { border-color: #a799ff; }
QDateEdit:disabled, QTimeEdit:disabled { color: #59677c; background: #161d29; border-color: #253044; }
QDateEdit::drop-down { border: none; width: 24px; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #5e6a83; border-radius: 5px; background: #101722; }
QCheckBox::indicator:checked { background: #a799ff; border-color: #a799ff; image: url(none); }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #3d4861; min-height: 30px; border-radius: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QMenu { background: #1c2535; border: 1px solid #3b4961; padding: 5px; }
QMenu::item { padding: 9px 20px; border-radius: 5px; }
QMenu::item:selected { background: #393653; }
QToolTip { color: #e8edf7; background: #283347; border: 1px solid #4a5873; padding: 5px; }
QCalendarWidget QWidget { background: #1c2535; color: #e8edf7; }
QCalendarWidget QAbstractItemView { background: #141b28; selection-background-color: #6555ae; }
"""


def configure_app(app: QApplication):
    # Qt'nin offscreen sürücüsü Windows yazı tiplerini kendiliğinden yüklemez.
    if "Segoe UI" not in QFontDatabase.families():
        font_dir = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "seguisb.ttf", "segoeuib.ttf"):
            QFontDatabase.addApplicationFont(str(font_dir / filename))
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    QLocale.setDefault(QLocale("tr_TR"))


def icon(kind: str, color: str = "#b9c4d7", size: int = 20) -> QIcon:
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size * 2 / 24, size * 2 / 24)
    p.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine,
                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == "plus":
        p.drawLine(12, 5, 12, 19); p.drawLine(5, 12, 19, 12)
    elif kind == "close":
        p.drawLine(7, 7, 17, 17); p.drawLine(17, 7, 7, 17)
    elif kind == "minus":
        p.drawLine(6, 12, 18, 12)
    elif kind == "check":
        p.drawPolyline([QPointF(5, 12), QPointF(10, 17), QPointF(19, 7)])
    elif kind == "circle":
        p.drawEllipse(QRectF(4, 4, 16, 16))
    elif kind == "trash":
        p.drawLine(4, 6, 20, 6); p.drawLine(9, 3, 15, 3)
        p.drawPolyline([QPointF(6, 6), QPointF(7, 20), QPointF(17, 20), QPointF(18, 6)])
        p.drawLine(10, 10, 10, 16); p.drawLine(14, 10, 14, 16)
    elif kind == "edit":
        p.drawPolyline([QPointF(15, 5), QPointF(19, 9), QPointF(9, 19), QPointF(4, 20), QPointF(5, 15), QPointF(17, 3), QPointF(21, 7), QPointF(19, 9)])
    elif kind == "undo":
        p.drawPolyline([QPointF(8, 4), QPointF(3, 9), QPointF(8, 14)])
        p.drawArc(QRectF(5, 8, 15, 12), -140 * 16, 240 * 16)
    elif kind == "clock":
        p.drawEllipse(QRectF(3, 3, 18, 18)); p.drawLine(12, 7, 12, 12); p.drawLine(12, 12, 16, 14)
    elif kind == "search":
        p.drawEllipse(QRectF(4, 3, 12, 12)); p.drawLine(15, 14, 21, 20)
    elif kind == "menu":
        p.setBrush(QColor(color)); p.setPen(Qt.PenStyle.NoPen)
        for y in (5, 12, 19):
            p.drawEllipse(QRectF(10, y - 1, 3, 3))
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def app_icon() -> QIcon:
    pix = QPixmap(128, 128)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#a799ff"))
    p.drawRoundedRect(QRectF(4, 4, 120, 120), 32, 32)
    p.setPen(QPen(QColor("#1c1839"), 10, Qt.PenStyle.SolidLine,
                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPolyline([QPointF(33, 65), QPointF(55, 85), QPointF(94, 43)])
    p.end()
    return QIcon(pix)


def label(text: str, name: str | None = None, wrap: bool = False) -> QLabel:
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(wrap)
    if name:
        result.setObjectName(name)
    return result


def tool(kind: str, hint: str, callback, color: str = "#aebbd0") -> QToolButton:
    result = QToolButton()
    result.setCursor(Qt.CursorShape.ArrowCursor)
    result.setIcon(icon(kind, color))
    result.setIconSize(QSize(18, 18))
    result.setFixedSize(30, 30)
    result.setToolTip(hint)
    result.setAccessibleName(hint)
    result.clicked.connect(callback)
    return result


class DragHeader(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Taşımak için sol tıkla tutup sürükle")

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self._drag_offset = None
        handle = self.window().windowHandle()
        # Windows'un taşıma davranışı farklı ekran ölçeklerinde de çalışır.
        if handle is None or not handle.startSystemMove():
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class TaskDialog(QDialog):
    def __init__(self, parent: QWidget, task: Task | None = None):
        # Ana pencere gibi üstte kalmalı; aksi hâlde Windows formu arkaya atar.
        # Tool türü, formun da görev çubuğunda ayrı simge açmasını önler.
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.task = task
        self.setWindowTitle("Görevi düzenle" if task else "Yeni görev")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(400)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(13)
        layout.addWidget(label("BİR SONRAKİ ADIM", "eyebrow"))
        layout.addWidget(label("Görevi düzenle" if task else "Aklındakini listeye al.", "section"))
        layout.addSpacing(3)
        layout.addWidget(label("Görev başlığı"))
        self.title = QLineEdit(task.title if task else "")
        self.title.setMaxLength(180)
        self.title.setPlaceholderText("Neyi tamamlamak istiyorsun?")
        self.title.setAccessibleName("Görev başlığı")
        layout.addWidget(self.title)
        layout.addWidget(label("Not · isteğe bağlı", "muted"))
        self.notes = QTextEdit()
        self.notes.setAcceptRichText(False)
        self.notes.setPlainText(task.notes if task else "")
        self.notes.setPlaceholderText("İhtiyacın olan detaylar…")
        self.notes.setAccessibleName("Görev notu")
        self.notes.setFixedHeight(85)
        layout.addWidget(self.notes)
        layout.addWidget(label("Deadline · isteğe bağlı", "muted"))
        options = QHBoxLayout()
        date_column = QVBoxLayout()
        self.use_date = QCheckBox("Tarih ekle")
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setLocale(QLocale("tr_TR"))
        self.date.setDisplayFormat("dd MMM yyyy")
        self.date.setDate(QDate(task.deadline.date()) if task and task.deadline else QDate.currentDate())
        self.date.setAccessibleName("Deadline tarihi")
        self.use_date.toggled.connect(self.date.setEnabled)
        date_column.addWidget(self.use_date)
        date_column.addWidget(self.date)
        time_column = QVBoxLayout()
        self.use_time = QCheckBox("Saat ekle")
        self.clock = QTimeEdit()
        self.clock.setDisplayFormat("HH:mm")
        self.clock.setTime(QTime(task.deadline.time()) if task and task.deadline else QTime.currentTime().addSecs(3600))
        self.clock.setAccessibleName("Deadline saati")
        self.use_time.toggled.connect(self.clock.setEnabled)
        time_column.addWidget(self.use_time)
        time_column.addWidget(self.clock)
        options.addLayout(date_column, 3)
        options.addSpacing(10)
        options.addLayout(time_column, 2)
        layout.addLayout(options)
        self.use_date.setChecked(bool(task and task.deadline))
        self.use_time.setChecked(bool(task and task.has_time))
        self.date.setEnabled(self.use_date.isChecked())
        self.clock.setEnabled(self.use_time.isChecked())
        self.explanation = label("", "muted", True)
        self.explanation.setMinimumHeight(34)
        layout.addWidget(self.explanation)
        self.use_date.toggled.connect(self.update_hint)
        self.use_time.toggled.connect(self.update_hint)
        self.update_hint()
        actions = QHBoxLayout()
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton("Kaydet" if task else "Görevi ekle")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setDefault(True)
        actions.addWidget(cancel)
        actions.addWidget(self.save_button, 1)
        layout.addLayout(actions)
        self.title.textChanged.connect(lambda text: self.save_button.setEnabled(bool(text.strip())))
        self.save_button.setEnabled(bool(self.title.text().strip()))
        self.title.returnPressed.connect(lambda: self.accept() if self.save_button.isEnabled() else None)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=lambda: self.accept() if self.save_button.isEnabled() else None)
        self.title.setFocus()

    def update_hint(self):
        if self.use_date.isChecked() and not self.use_time.isChecked():
            text = "Saat seçmedin; deadline seçtiğin günün 23.59’u olacak."
        elif self.use_time.isChecked() and not self.use_date.isChecked():
            text = "Tarih seçmedin; deadline bugün, seçtiğin saatte olacak."
        elif self.use_date.isChecked():
            text = "24 saatten az: kırmızı · 1–3 gün: sarı."
        else:
            text = "Tarih ve saat olmadan da görev ekleyebilirsin."
        self.explanation.setText(text)

    def values(self) -> dict:
        deadline = make_deadline(self.date.date().toPython() if self.use_date.isChecked() else None,
                                 self.clock.time().toPython().replace(second=0, microsecond=0)
                                 if self.use_time.isChecked() else None)
        return dict(title=self.title.text(), notes=self.notes.toPlainText(),
                    deadline=deadline, has_time=self.use_time.isChecked())


class TaskCard(QFrame):
    def __init__(self, task: Task, owner: MainWindow):
        super().__init__()
        self.task = task
        self.owner = owner
        self.kind = category(task)
        accent = COLORS[self.kind]
        self.setObjectName("taskCard")
        self.setStyleSheet(f"QFrame#taskCard {{ background: #1a2231; border: 1px solid #2b374c; border-left: 3px solid {accent}; border-radius: 12px; }}")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        body = QVBoxLayout(self)
        body.setContentsMargins(12, 12, 10, 11)
        body.setSpacing(7)
        top = QHBoxLayout()
        top.setSpacing(8)
        if self.kind != "trash":
            top.addWidget(tool("check" if self.kind == "done" else "circle",
                "Yeniden aç" if self.kind == "done" else "Tamamlandı işaretle",
                lambda: owner.change_completion(task), accent), 0, Qt.AlignmentFlag.AlignTop)
        title = label(task.title, wrap=True)
        title.setStyleSheet("font-size: 14px; font-weight: 600;" + ("color: #8c9bb1;" if self.kind == "done" else ""))
        if self.kind == "done":
            font = title.font(); font.setStrikeOut(True); title.setFont(font)
        top.addWidget(title, 1)
        if self.kind == "trash":
            top.addWidget(tool("undo", "Görevi geri al", lambda: owner.restore_task(task)), 0, Qt.AlignmentFlag.AlignTop)
        else:
            top.addWidget(tool("edit", "Görevi düzenle", lambda: owner.edit_task(task)), 0, Qt.AlignmentFlag.AlignTop)
            top.addWidget(tool("trash", "Sil · 10 dakika geri alınabilir", lambda: owner.delete_task(task)), 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(top)
        if task.notes:
            notes_text = task.notes if len(task.notes) <= 180 else task.notes[:177] + "…"
            notes = label(notes_text, "muted", True)
            notes.setToolTip(task.notes)
            notes.setContentsMargins(3, 0, 0, 0)
            body.addWidget(notes)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(3, 0, 0, 0)
        self.date_label = label("")
        self.date_label.setStyleSheet("color: #99a8c0; font-size: 11px;")
        bottom.addWidget(self.date_label)
        bottom.addStretch()
        self.badge = label("")
        self.badge.setStyleSheet(f"color: {accent}; background: #242d40; font-size: 10px; font-weight: 600; padding: 4px 6px; border-radius: 5px;")
        bottom.addWidget(self.badge)
        body.addLayout(bottom)
        self.update_time()

    def update_time(self):
        task = self.task
        if task.deadline:
            self.date_label.setText(QLocale("tr_TR").toString(QDate(task.deadline.date()), "d MMM") +
                                    (task.deadline.strftime(" · %H:%M") if task.has_time else " · gün sonu"))
            self.date_label.setToolTip(task.deadline.strftime("%d.%m.%Y %H:%M"))
        else:
            self.date_label.setText("Deadline yok")
        if task.deleted_at is not None:
            remaining = max(0, math.ceil(task.deleted_at + UNDO_SECONDS - time.time()))
            self.badge.setText(f"Geri al · {remaining // 60}:{remaining % 60:02d}")
        elif task.completed_at is not None:
            self.badge.setText("Tamamlandı")
        else:
            self.badge.setText(time_label(task) if task.deadline else "Zamanı sende")


class MainWindow(QWidget):
    def __init__(self, store: Store, project: Path, with_tray: bool = True):
        super().__init__()
        self.store = store
        self.project = project
        self.current_tab = "active"
        self.cards: list[TaskCard] = []
        self.snapshot = None
        self.notice_until = 0.0
        self.setWindowTitle("Odak · Görevlerin")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setObjectName("surface")
        outer.addWidget(surface)
        body = QVBoxLayout(surface)
        body.setContentsMargins(20, 18, 20, 14)
        body.setSpacing(14)

        self.drag_header = DragHeader(self)
        header = QHBoxLayout(self.drag_header)
        header.setContentsMargins(0, 0, 0, 0)
        logo = QLabel()
        logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        logo.setPixmap(app_icon().pixmap(36, 36))
        logo.setFixedSize(36, 36)
        header.addWidget(logo)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        for title_label in (label("odak", "brand"), label("Bir görev. Bir adım ileri.", "muted")):
            title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            title_col.addWidget(title_label)
        header.addLayout(title_col, 1)
        self.menu_button = tool("menu", "Seçenekler", self.show_menu)
        header.addWidget(self.menu_button, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(tool("minus", "Sistem tepsisine gizle", self.hide_to_tray), 0, Qt.AlignmentFlag.AlignTop)
        close = tool("close", "Uygulamayı kapat", self.close)
        close.setObjectName("closeApp")
        header.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        body.addWidget(self.drag_header)

        summary = QFrame()
        summary.setObjectName("summary")
        stats = QHBoxLayout(summary)
        stats.setContentsMargins(16, 12, 16, 14)
        stats.setSpacing(4)
        self.stat_values = {}
        for key, caption, color in (("active", "Açık görev", "#e8edf7"),
                                    ("urgent", "24 saat içinde", "#ff828e"),
                                    ("done", "Tamamlanan", "#80d3b5")):
            column = QVBoxLayout()
            column.setSpacing(0)
            number = label("0", "summaryValue")
            number.setStyleSheet(f"color: {color};")
            column.addWidget(number)
            column.addWidget(label(caption, "summaryCaption"))
            stats.addLayout(column, 1)
            self.stat_values[key] = number
        body.addWidget(summary)

        add_button = QPushButton("  Yeni görev")
        add_button.setObjectName("primary")
        add_button.setIcon(icon("plus", "#14132a"))
        add_button.setFixedHeight(43)
        add_button.setToolTip("Yeni görev · Ctrl+N")
        add_button.clicked.connect(lambda: self.edit_task())
        body.addWidget(add_button)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Görevlerinde ara…")
        self.search.setAccessibleName("Görevlerde ara")
        self.search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(lambda: self.refresh(force=True))
        body.addWidget(self.search)

        tabs = QFrame()
        tabs.setObjectName("tabs")
        tab_row = QHBoxLayout(tabs)
        tab_row.setContentsMargins(4, 4, 4, 4)
        tab_row.setSpacing(1)
        self.tabs = {}
        for key, text in (("active", "Görevler"), ("overdue", "Geçenler"),
                          ("done", "Bitenler"), ("trash", "Silinenler")):
            button = QPushButton(text)
            button.setObjectName("tab")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, k=key: self.set_tab(k))
            tab_row.addWidget(button, 1)
            self.tabs[key] = button
        body.addWidget(tabs)

        section = QHBoxLayout()
        self.section_title = label("Görevlerin", "section")
        section.addWidget(self.section_title)
        section.addStretch()
        self.count_label = label("", "muted")
        section.addWidget(self.count_label)
        body.addLayout(section)
        self.section_hint = label("Deadline’ı yakın olanlar en üstte.", "muted", True)
        self.section_hint.setStyleSheet("font-size: 11px; color: #96a3b8;")
        body.addWidget(self.section_hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget = QWidget()
        self.task_layout = QVBoxLayout(self.list_widget)
        self.task_layout.setContentsMargins(0, 0, 5, 0)
        self.task_layout.setSpacing(10)
        self.task_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.list_widget)
        body.addWidget(self.scroll, 1)
        self.notice = label("", wrap=True)
        self.notice.setStyleSheet("background: #263446; color: #b9e4d4; border-radius: 8px; padding: 8px; font-size: 11px;")
        self.notice.hide()
        body.addWidget(self.notice)
        footer = QHBoxLayout()
        footer.addWidget(label("●  Otomatik kaydedilir", "muted"))
        footer.addStretch()
        self.date_label = label("", "muted")
        footer.addWidget(self.date_label)
        body.addLayout(footer)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.edit_task())
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search.setFocus)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.tray = None
        if with_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(app_icon(), self)
            self.tray.setToolTip("Odak · Görevlerin")
            tray_menu = QMenu(self)
            tray_menu.addAction("Odak’ı göster", self.reveal)
            tray_menu.addSeparator()
            tray_menu.addAction("Uygulamayı kapat", self.close)
            self.tray.setContextMenu(tray_menu)
            self.tray.activated.connect(lambda reason: self.reveal() if reason in
                (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
            self.tray.show()
        self.set_tab("active")
        self.anchor()

    def anchor(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        width = min(420, rect.width() - 24)
        height = min(800, rect.height() - 32)
        self.setFixedSize(width, height)
        self.move(rect.right() - width - 15, rect.top() + 16)

    def show_menu(self):
        menu = QMenu(self)
        menu.addAction("Sağ üste yerleştir", self.anchor)
        menu.addAction("Yeni görev\tCtrl+N", lambda: self.edit_task())
        menu.addSeparator()
        startup = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Odak.lnk"
        status = menu.addAction("Windows başlangıcı: " + ("etkin" if startup.exists() else "kurulu değil"))
        status.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Uygulamayı kapat", self.close)
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))

    def set_tab(self, tab: str):
        self.current_tab = tab
        for key, button in self.tabs.items():
            button.setChecked(key == tab)
        titles = {"active": ("Görevlerin", "Deadline’ı yakın olanlar en üstte."),
                  "overdue": ("Deadline’ı geçenler", "Süresi geçen görevlerini buradan yönetebilirsin."),
                  "done": ("Tamamlananlar", "İlerleme burada birikir. Eline sağlık."),
                  "trash": ("Son silinenler", "Her görevi silindikten sonra 10 dakika içinde geri alabilirsin.")}
        title, hint = titles[tab]
        self.section_title.setText(title)
        self.section_hint.setText(hint)
        self.refresh(force=True)
        self.scroll.verticalScrollBar().setValue(0)

    def tick(self):
        self.refresh()
        if self.notice.isVisible() and time.time() >= self.notice_until:
            self.notice.hide()

    def refresh(self, force: bool = False):
        try:
            tasks = self.store.all()
        except Exception as exc:
            self.timer.stop()
            self.report_error(exc)
            return
        now = datetime.now()
        groups = {"active": [], "overdue": [], "done": [], "trash": []}
        urgent = 0
        for task in tasks:
            kind = category(task, now)
            key = kind if kind in ("overdue", "done", "trash") else "active"
            groups[key].append(task)
            urgent += kind == "urgent"
        self.stat_values["active"].setText(str(len(groups["active"]) + len(groups["overdue"])))
        self.stat_values["urgent"].setText(str(urgent))
        self.stat_values["done"].setText(str(len(groups["done"])))
        self.date_label.setText(QLocale("tr_TR").toString(QDate.currentDate(), "d MMM, ddd"))
        for key, text in (("active", "Görevler"), ("overdue", "Geçenler"),
                          ("done", "Bitenler"), ("trash", "Silinenler")):
            self.tabs[key].setText(f"{text} {len(groups[key])}")
        shown = groups[self.current_tab]
        if self.current_tab in ("active", "overdue"):
            shown.sort(key=lambda t: (t.deadline or datetime.max, -t.created_at))
        elif self.current_tab == "trash":
            shown.sort(key=lambda t: t.deleted_at, reverse=True)
        else:
            shown.sort(key=lambda t: t.completed_at, reverse=True)
        query = search_key(self.search.text().strip())
        if query:
            shown = [t for t in shown if query in search_key(t.title + " " + t.notes)]
        self.count_label.setText(f"{len(shown)} görev")
        snapshot = (self.current_tab, tuple((t, category(t, now)) for t in shown))
        if not force and self.snapshot == snapshot:
            for card in self.cards:
                card.update_time()
            return
        self.snapshot = snapshot
        scroll_position = self.scroll.verticalScrollBar().value()
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.cards = []
        if not shown:
            empty = QWidget()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(14, 35, 14, 20)
            mark = label("✓" if self.current_tab in ("done", "overdue") else "○")
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mark.setStyleSheet("font-size: 43px; color: #8c80ca;")
            empty_layout.addWidget(mark)
            messages = {"active": ("Zihninde yer aç.", "İlk görevini ekle, gerisini adım adım hallet."),
                        "overdue": ("Her şey yolunda.", "Deadline’ı geçmiş görevin yok."),
                        "done": ("İlk tikini bekliyor.", "Tamamladığın görevler burada görünecek."),
                        "trash": ("Burada bir şey yok.", "Sildiğin görevler 10 dakika boyunca burada bekler.")}
            title, subtitle = ("Sonuç bulunamadı.", "Başka bir kelimeyle aramayı dene.") if query else messages[self.current_tab]
            heading = label(title, "section")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(heading)
            desc = label(subtitle, "muted", True)
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(desc)
            self.task_layout.addWidget(empty)
        for task in shown:
            card = TaskCard(task, self)
            self.cards.append(card)
            self.task_layout.addWidget(card)
        self.scroll.verticalScrollBar().setValue(scroll_position)

    def notify(self, text: str):
        self.notice.setText(text)
        self.notice.show()
        self.notice_until = time.time() + 5

    def report_error(self, exc: Exception):
        import logging
        logging.exception("Görev işlemi başarısız")
        QMessageBox.critical(self, "İşlem tamamlanamadı",
            "Değişiklik kaydedilemedi. Disk alanını ve klasör izinlerini kontrol et.\n\n" + str(exc))

    def perform(self, action, text: str):
        try:
            action()
        except Exception as exc:
            self.report_error(exc)
            return
        self.refresh(force=True)
        self.notify(text)

    def edit_task(self, task: Task | None = None):
        dialog = TaskDialog(self, task)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.store.save(**values, task_id=task.id if task else None)
        except Exception as exc:
            self.report_error(exc)
            return
        self.search.clear()
        if task and task.completed_at is not None:
            self.set_tab("done")
        elif values["deadline"] and values["deadline"] <= datetime.now():
            self.set_tab("overdue")
        else:
            self.set_tab("active")
        self.notify("Değişiklikler kaydedildi." if task else "Görev eklendi. Hazırsın.")

    def change_completion(self, task: Task):
        self.perform(lambda: self.store.complete(task.id, task.completed_at is None),
                     "Bir adım daha tamamlandı." if task.completed_at is None else "Görev yeniden açıldı.")

    def delete_task(self, task: Task):
        self.perform(lambda: self.store.delete(task.id), "Görev silindi. Silinenler’den 10 dakika içinde geri alabilirsin.")

    def restore_task(self, task: Task):
        def restore():
            if not self.store.restore(task.id):
                raise ValueError("Bu görevin 10 dakikalık geri alma süresi doldu.")
        self.perform(restore, "Görev önceki durumuyla geri alındı.")

    def hide_to_tray(self):
        if self.tray is not None and self.tray.isVisible():
            self.hide()
        else:
            self.showMinimized()

    def reveal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.timer.stop()
        if self.tray:
            self.tray.hide()
        event.accept()
        QApplication.instance().quit()
