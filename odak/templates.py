"""Tekrar kullanılan görev taslakları; şablonlar kendiliğinden görev üretmez."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QPushButton,
                              QScrollArea, QTextEdit, QVBoxLayout, QWidget)

from .windows import StyledDialog


def text_label(text, muted=False):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    if muted:
        label.setObjectName("muted")
    return label


class TemplateEditor(StyledDialog):
    def __init__(self, parent, store, template=None, values=None):
        super().__init__(parent, "Şablonu düzenle" if template else "Yeni görev şablonu", 460, 670)
        self.store, self.template, self.saved_id = store, template, None
        values = values or {}
        self.body.addWidget(text_label("Başlık, not ve adımları sakla; deadline'ı yeni görevde seç.", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        fields = QWidget()
        layout = QVBoxLayout(fields)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.name = QLineEdit(template.name if template else values.get("title", "")[:80])
        self.name.setMaxLength(80)
        self.name.setAccessibleName("Şablon adı")
        self.title = QLineEdit(template.title if template else values.get("title", ""))
        self.title.setMaxLength(180)
        self.title.setAccessibleName("Şablon görev başlığı")
        self.notes = QTextEdit()
        self.notes.setAcceptRichText(False)
        self.notes.setPlainText(template.notes if template else values.get("notes", ""))
        self.notes.setFixedHeight(90)
        self.steps = QTextEdit()
        self.steps.setAcceptRichText(False)
        self.steps.setPlainText("\n".join(template.steps if template else values.get("steps", [])))
        self.steps.setFixedHeight(125)
        for caption, field in (("Şablon adı",self.name),("Görev başlığı",self.title),("Not · isteğe bağlı",self.notes),("Alt adımlar · her satıra bir adım",self.steps)):
            layout.addWidget(text_label(caption, True))
            layout.addWidget(field)
        layout.addStretch()
        scroll.setWidget(fields)
        self.body.addWidget(scroll, 1)
        self.error = text_label("")
        self.error.setObjectName("formError")
        self.error.hide()
        self.body.addWidget(self.error)
        self.save_button = self.footer("Şablonu kaydet", self.save)
        self.name.textChanged.connect(self.validate)
        self.title.textChanged.connect(self.validate)
        self.validate()

    def validate(self):
        self.save_button.setEnabled(bool(self.name.text().strip() and self.title.text().strip()))

    def save(self):
        try:
            self.saved_id = self.store.save_template(self.name.text(), self.title.text(), self.notes.toPlainText(),
                self.steps.toPlainText().splitlines(), self.template.id if self.template else None)
        except Exception as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        self.accept()


class TemplateManager(StyledDialog):
    def __init__(self, parent, store):
        super().__init__(parent, "Görev şablonları", 460, 600)
        self.store = store
        self.body.addWidget(text_label("Hazır adımları yeni görev penceresinden kullanabilirsin.", True))
        add = QPushButton("+  Yeni şablon")
        add.setObjectName("primary")
        add.clicked.connect(lambda: self.edit())
        self.body.addWidget(add)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list = QWidget()
        self.list_layout = QVBoxLayout(self.list)
        self.list_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.list)
        self.body.addWidget(scroll, 1)
        done = QPushButton("Kapat")
        done.clicked.connect(self.accept)
        self.body.addWidget(done)
        self.refresh()

    def refresh(self):
        while self.list_layout.count():
            widget = self.list_layout.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        templates = self.store.templates()
        if not templates:
            self.list_layout.addWidget(text_label("İlk şablonunu ekle. Sunum, alışveriş veya haftalık hazırlık adımlarını saklayabilirsin.", True))
        for template in templates:
            card = QFrame()
            card.setStyleSheet("QFrame {background:#1b2535; border-radius:12px;}")
            layout = QVBoxLayout(card)
            layout.addWidget(text_label(template.name))
            layout.addWidget(text_label(f"{template.title}\n{len(template.steps)} alt adım", True))
            row = QHBoxLayout()
            edit = QPushButton("Düzenle")
            edit.clicked.connect(lambda checked=False,t=template:self.edit(t))
            remove = QPushButton("Sil")
            remove.clicked.connect(lambda checked=False,t=template:self.remove(t))
            row.addWidget(edit)
            row.addWidget(remove)
            layout.addLayout(row)
            self.list_layout.addWidget(card)

    def edit(self, template=None):
        dialog = TemplateEditor(self, self.store, template)
        dialog.exec()
        dialog.deleteLater()
        self.refresh()

    def remove(self, template):
        from .ui import message_box
        from PySide6.QtWidgets import QMessageBox
        if message_box(self, "Şablonu sil", f'“{template.name}” şablonu silinsin mi?', question=True) == QMessageBox.StandardButton.Yes:
            self.store.delete_template(template.id)
            self.refresh()
