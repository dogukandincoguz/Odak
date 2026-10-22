"""Giriş alanları için ortak görünüm ve taşmayan seçim kutusu."""
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (QComboBox, QListView, QSizePolicy, QSpinBox, QStyle,
                               QStyledItemDelegate, QStyleOptionComboBox, QStylePainter, QTimeEdit)


FIELD_STYLE = """
QLineEdit, QTextEdit, QAbstractSpinBox, QComboBox {
    background: #151f2e; color: #e0e7f3; border: 1px solid #344159;
    border-radius: 12px; selection-background-color: #6555ae;
    selection-color: #ffffff; font-size: 13px;
}
QLineEdit { min-height: 44px; padding: 0 13px; }
QTextEdit { padding: 11px 13px; }
QAbstractSpinBox, QComboBox {
    min-height: 44px; max-height: 44px; padding: 0 52px 0 14px;
}
QComboBox { font-weight: 600; }
QLineEdit:hover, QTextEdit:hover, QAbstractSpinBox:hover, QComboBox:hover { border-color: #51617b; }
QLineEdit:focus, QTextEdit:focus, QAbstractSpinBox:focus, QComboBox:focus, QComboBox:on {
    border-color: #a799ff; background: #192335;
}
QLineEdit:disabled, QTextEdit:disabled, QAbstractSpinBox:disabled, QComboBox:disabled {
    color: #63738b; background: #141d2b; border-color: #29364b;
}
QAbstractSpinBox QLineEdit, QComboBox QLineEdit {
    background: transparent; border: none; border-radius: 0;
    padding: 0; min-height: 0; font-weight: normal;
}
QSpinBox::up-button, QDoubleSpinBox::up-button, QDateTimeEdit::up-button {
    subcontrol-origin: border; subcontrol-position: top right;
    width: 41px; height: 22px; margin: 1px 1px 0 0;
    background: #243147; border: none; border-left: 1px solid #344159;
    border-bottom: 1px solid #344159; border-top-right-radius: 11px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button, QDateTimeEdit::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 41px; height: 22px; margin: 0 1px 1px 0;
    background: #243147; border: none; border-left: 1px solid #344159;
    border-bottom-right-radius: 11px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QDateTimeEdit::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover, QDateTimeEdit::down-button:hover {
    background: #34445e;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed, QDateTimeEdit::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed, QDateTimeEdit::down-button:pressed {
    background: #4c406f;
}
QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled, QDateTimeEdit::up-button:disabled,
QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled, QDateTimeEdit::down-button:disabled {
    background: #1c283b; border-color: #29364b;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QDateTimeEdit::up-arrow {
    image: url('__ASSETS__/chevron-up.svg'); width: 13px; height: 13px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QDateTimeEdit::down-arrow {
    image: url('__ASSETS__/chevron-down.svg'); width: 13px; height: 13px;
}
QSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:disabled,
QDoubleSpinBox::up-arrow:off, QDateTimeEdit::up-arrow:disabled, QDateTimeEdit::up-arrow:off {
    image: url('__ASSETS__/chevron-up-muted.svg');
}
QSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:disabled,
QDoubleSpinBox::down-arrow:off, QDateTimeEdit::down-arrow:disabled, QDateTimeEdit::down-arrow:off {
    image: url('__ASSETS__/chevron-down-muted.svg');
}
QComboBox::drop-down, QDateTimeEdit::drop-down {
    subcontrol-origin: border; subcontrol-position: top right;
    width: 41px; margin: 1px;
    background: #243147; border: none; border-left: 1px solid #344159;
    border-top-right-radius: 11px; border-bottom-right-radius: 11px;
}
QComboBox::drop-down:hover, QDateTimeEdit::drop-down:hover { background: #34445e; }
QComboBox::drop-down:pressed, QDateTimeEdit::drop-down:pressed { background: #4c406f; }
QComboBox::drop-down:disabled, QDateTimeEdit::drop-down:disabled {
    background: #1c283b; border-color: #29364b;
}
QComboBox::down-arrow { image: url('__ASSETS__/chevron-down.svg'); width: 15px; height: 15px; }
QComboBox::down-arrow:disabled { image: url('__ASSETS__/chevron-down-muted.svg'); }
QDateEdit::down-arrow { image: url('__ASSETS__/calendar.svg'); width: 18px; height: 18px; }
QDateEdit::down-arrow:disabled { image: url('__ASSETS__/calendar-muted.svg'); }
QComboBox QAbstractItemView {
    background: #182233; color: #c7d2e5; border: 1px solid #485570;
    border-radius: 12px; padding: 6px; outline: none;
    selection-background-color: #3c345a; selection-color: #eee8ff;
}
QComboBox QAbstractItemView::item { min-height: 36px; padding: 3px 10px; border-radius: 7px; }
QComboBox QAbstractItemView::item:hover { background: #29364e; }
QComboBox QAbstractItemView::item:selected { background: #3c345a; color: #eee8ff; }
"""


def field_style() -> str:
    return FIELD_STYLE.replace("__ASSETS__", (Path(__file__).resolve().parents[1] / "assets/ui").as_posix())


class Stepper(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().setTextMargins(12, 0, 8, 0)


class TimeField(QTimeEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().setTextMargins(12, 0, 8, 0)


class ChoiceDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setWidth(max(0, self.parent().viewport().width() - 6))
        return size


class ChoiceBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setIconSize(QSize(18, 18))
        self.setMaxVisibleItems(7)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setTextElideMode(Qt.TextElideMode.ElideRight)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setSpacing(3)
        self.setView(view)
        self.setItemDelegate(ChoiceDelegate(view))
        self.currentIndexChanged.connect(lambda: self.setToolTip(self.currentText()))

    def paintEvent(self, event):
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        field = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                           QStyle.SubControl.SC_ComboBoxEditField, self)
        icon_width = self.iconSize().width() + 8 if not option.currentIcon.isNull() else 0
        option.currentText = self.fontMetrics().elidedText(self.currentText(), Qt.TextElideMode.ElideRight,
                                                         max(0, field.width() - icon_width - 6))
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        screen = self.screen().availableGeometry()
        width = min(self.width(), screen.width() - 16)
        location = self.mapToGlobal(QPoint(0, self.height() + 5))
        top = location.y()
        if top + popup.height() > screen.bottom() - 8:
            top = self.mapToGlobal(QPoint(0, 0)).y() - popup.height() - 5
        left = max(screen.left() + 8, min(location.x(), screen.right() - width - 7))
        popup.setGeometry(left, max(screen.top() + 8, top), width, popup.height())
        self.view().doItemsLayout()
