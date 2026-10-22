"""Görev listelerindeki kartlar için tutamak ve bırakma göstergesi."""
from PySide6.QtCore import QMimeData, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import QApplication, QToolButton, QWidget

MIME = "application/x-odak-task"


class TaskGrip(QToolButton):
    def __init__(self, owner, task_id, card):
        super().__init__(card)
        self.owner, self.task_id, self.card = owner, task_id, card
        self.setFixedSize(24, 30)
        self.setStyleSheet("padding:0;")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAccessibleName("Görevi sıralamak için sürükle")
        self.setToolTip("Sıralamak için tutup sürükle")
        self._press = None

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#a69bcf"))
        for x in (8, 14):
            for y in (9, 15, 21):
                painter.drawEllipse(QRectF(x-1.4, y-1.4, 2.8, 2.8))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            order = self.owner._list_order
            if self.task_id not in order:
                return
            index = order.index(self.task_id)
            next_index = index + (-1 if event.key() == Qt.Key.Key_Up else 1)
            if 0 <= next_index < len(order):
                self.owner.move_task(self.task_id, order[next_index], next_index > index)
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is not None and event.buttons() & Qt.MouseButton.LeftButton and (event.position().toPoint()-self._press).manhattanLength() >= QApplication.startDragDistance():
            self._press = None
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(MIME, self.task_id.encode("ascii"))
            drag.setMimeData(mime)
            drag.setPixmap(self.card.grab().scaledToWidth(300, Qt.TransformationMode.SmoothTransformation))
            drag.setHotSpot(QPoint(12, 12))
            self.owner._task_dragging = True
            self.owner._drag_tab = self.owner.current_tab
            try:
                drag.exec(Qt.DropAction.MoveAction)
            finally:
                self.owner._task_dragging = False
                self.owner._drag_tab = None
                self.owner.list_widget.clear_indicator()
                self.owner.refresh(force=True)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = None
        super().mouseReleaseEvent(event)


class TaskDropArea(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner, self.indicator = owner, None
        self.setAcceptDrops(True)

    def eligible(self, event):
        source = event.source()
        return (isinstance(source, TaskGrip) and source.owner is self.owner and event.mimeData().hasFormat(MIME)
                and self.owner.current_view == "tasks" and self.owner.current_tab == self.owner._drag_tab
                and not self.owner.search.text().strip())

    def dragEnterEvent(self, event):
        if self.eligible(event):
            event.acceptProposedAction()

    def target(self, y):
        for card in self.owner.cards:
            if y < card.geometry().center().y():
                return card.task.id, False, card.y() - 7
        if self.owner.cards:
            card = self.owner.cards[-1]
            return card.task.id, True, card.geometry().bottom() + 7
        return None

    def dragMoveEvent(self, event):
        if self.eligible(event):
            target = self.target(event.position().y())
            self.indicator = target[2] if target else None
            viewport = self.owner.scroll.viewport()
            local = viewport.mapFromGlobal(self.mapToGlobal(event.position().toPoint()))
            bar = self.owner.scroll.verticalScrollBar()
            if local.y() < 40:
                bar.setValue(bar.value() - 20)
            elif local.y() > viewport.height() - 40:
                bar.setValue(bar.value() + 20)
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.clear_indicator()

    def clear_indicator(self):
        self.indicator = None
        self.update()

    def dropEvent(self, event):
        if self.eligible(event):
            target = self.target(event.position().y())
            if target:
                identity = bytes(event.mimeData().data(MIME)).decode("ascii")
                self.owner.move_task(identity, target[0], target[1])
            event.acceptProposedAction()
        self.clear_indicator()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.indicator is not None:
            p = QPainter(self)
            p.setPen(QPen(QColor("#b9aaff"), 3))
            p.drawLine(5, int(self.indicator), self.width()-10, int(self.indicator))
