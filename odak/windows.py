"""Uygulamaya ait başlık çubuğu ve çerçevesiz pencere boyutlandırması."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
                              QPushButton, QToolButton, QVBoxLayout, QWidget)


WINDOW_STYLE = """
QDialog#styledDialog { background: transparent; }
QDialog#fileDialog { background: #141b28; border: 1px solid #3b4359; border-radius: 17px; }
QFrame#dialogSurface { background: #141b28; border: 1px solid #3b4359; border-radius: 17px; }
QWidget#dialogHeader { background: transparent; }
QLabel#dialogTitle { color: #e0d9ff; font-size: 16px; font-weight: 650; }
QToolButton#dialogClose { background: transparent; border: none; padding: 0; }
QToolButton#dialogClose:hover { background: #49303e; }
QToolButton#dialogClose:focus { background: #35314e; }
QPushButton#foldout { text-align: left; background: #1b2535; border-color: #2d394d; padding: 11px 13px; }
QPushButton#foldout:checked { color: #d6ccff; background: #26283e; border-color: #51476d; }
QLineEdit#taskTitle { font-size: 17px; font-weight: 600; min-height: 51px; }
QLabel#formError { color: #ff9ba5; background: #342430; border-radius: 8px; padding: 8px; }
"""


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


class CloseButton(QToolButton):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.setObjectName("dialogClose")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(32, 32)
        self.setAccessibleName("Pencereyi kapat")
        self.setToolTip("Kapat · Esc")
        self.clicked.connect(callback)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#d4cde8"), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        c = self.rect().center()
        p.drawLine(QPointF(c.x()-4, c.y()-4), QPointF(c.x()+4, c.y()+4))
        p.drawLine(QPointF(c.x()+4, c.y()-4), QPointF(c.x()-4, c.y()+4))


def dialog_header(window, title):
    header = DragHeader(window)
    header.setObjectName("dialogHeader")
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    title_label = QLabel(title)
    title_label.setTextFormat(Qt.TextFormat.PlainText)
    title_label.setObjectName("dialogTitle")
    title_label.setWordWrap(True)
    title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    row.addWidget(title_label, 1)
    header.close_button = CloseButton(header, window.reject)
    row.addWidget(header.close_button)
    return header


class FileDialog(QFileDialog):
    def __init__(self, parent, title, location, pattern):
        super().__init__(parent, title, location, pattern)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setObjectName("fileDialog")
        self.header = dialog_header(self, title)
        self.layout().setContentsMargins(20, 66, 20, 20)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.header.setGeometry(24, 14, self.width()-48, 36)
        self.header.raise_()


class StyledDialog(QDialog):
    def __init__(self, parent, title, width=440, height=660):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setObjectName("styledDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        area = self.screen().availableGeometry()
        self.setMinimumWidth(min(400, area.width() - 32))
        self.resize(min(width, area.width() - 32), min(height, area.height() - 48))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setObjectName("dialogSurface")
        outer.addWidget(surface)
        self.body = QVBoxLayout(surface)
        self.body.setContentsMargins(24, 17, 24, 22)
        self.body.setSpacing(16)
        self.header = dialog_header(self, title)
        self.close_button = self.header.close_button
        self.body.addWidget(self.header)

    def footer(self, caption, callback=None):
        row = QHBoxLayout()
        row.setSpacing(10)
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        save = QPushButton(caption)
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(callback or self.accept)
        row.addWidget(cancel)
        row.addWidget(save, 1)
        self.body.addLayout(row)
        return save


class Foldout(QWidget):
    def __init__(self, caption, content, expanded=False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.toggle = QPushButton()
        self.toggle.setObjectName("foldout")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setAccessibleName(caption)
        def update(checked):
            self.toggle.setText(("⌄  " if checked else "›  ") + caption)
            content.setVisible(checked)
        self.toggle.toggled.connect(update)
        layout.addWidget(self.toggle)
        layout.addWidget(content)
        update(expanded)


class ResizeHandle(QWidget):
    def __init__(self, window, edges):
        super().__init__(window)
        self.edges = edges
        horizontal = bool(edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
        vertical = bool(edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
        if horizontal and vertical:
            same = bool(edges & Qt.Edge.TopEdge) == bool(edges & Qt.Edge.LeftEdge)
            cursor = Qt.CursorShape.SizeFDiagCursor if same else Qt.CursorShape.SizeBDiagCursor
        else:
            cursor = Qt.CursorShape.SizeHorCursor if horizontal else Qt.CursorShape.SizeVerCursor
        self.setCursor(cursor)
        self._origin = None

    def paintEvent(self, event):
        if self.edges == (Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor("#51607b"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            right, bottom = self.width()-10, self.height()-10
            for length in (4, 8, 12):
                p.drawLine(right-length, bottom, right, bottom-length)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            if not window.windowHandle().startSystemResize(self.edges):
                self._origin = (event.globalPosition().toPoint(), window.geometry())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._origin and event.buttons() & Qt.MouseButton.LeftButton:
            point, rect = self._origin
            dx, dy = (event.globalPosition().toPoint() - point).toTuple()
            target = rect.adjusted(dx if self.edges & Qt.Edge.LeftEdge else 0,
                                   dy if self.edges & Qt.Edge.TopEdge else 0,
                                   dx if self.edges & Qt.Edge.RightEdge else 0,
                                   dy if self.edges & Qt.Edge.BottomEdge else 0)
            window = self.window()
            if target.width() >= window.minimumWidth() and target.height() >= window.minimumHeight():
                window.setGeometry(target)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._origin = None


def make_resize_handles(window):
    top, bottom, left, right = Qt.Edge.TopEdge, Qt.Edge.BottomEdge, Qt.Edge.LeftEdge, Qt.Edge.RightEdge
    return [ResizeHandle(window, edges) for edges in (top, bottom, left, right, top|left, top|right, bottom|left, bottom|right)]


def position_resize_handles(window, handles):
    w, h, b, c = window.width(), window.height(), 7, 22
    rectangles = [(c,0,w-2*c,b),(c,h-b,w-2*c,b),(0,c,b,h-2*c),(w-b,c,b,h-2*c),
                  (0,0,c,c),(w-c,0,c,c),(0,h-c,c,c),(w-c,h-c,c,c)]
    for handle, rect in zip(handles, rectangles):
        handle.setGeometry(*rect)
        handle.raise_()
