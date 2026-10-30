"""
Filename Sequence Builder Widget
Allows users to visually rearrange the 7 document metadata fields via drag-and-drop,
accessible ▲/▼ buttons, and keyboard navigation.

Persists custom sequence in QSettings so arrangements survive application restarts.
"""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QToolButton, QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, QMimeData, QPoint, Signal, QSettings
from PySide6.QtGui import QDrag, QPixmap, QPainter, QColor, QPen

from naming_logic import DEFAULT_SEQUENCE, validate_sequence, FIELD_DEFINITIONS

MIME_TYPE_FIELD_ID = "application/x-jobapp-field-id"


class _DraggableSegmentCard(QFrame):
    """
    Small rectangular card representing a single draggable metadata field.
    Features:
    - ⠿ Drag handle icon
    - Sequence position badge (1 to 7)
    - Field name label
    - Quick ▲ / ▼ buttons for one-click reordering
    - Keyboard arrow key reordering (Up/Down)
    """

    move_requested = Signal(str, int)  # (field_id, delta: -1 for up, +1 for down)

    def __init__(self, field_id: str, label: str, index: int, parent=None):
        super().__init__(parent)
        self.field_id = field_id
        self._label_text = label
        self._index = index
        self._drag_start_pos: Optional[QPoint] = None

        self.setObjectName("segmentCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{label} (Drag or use ▲/▼ or arrow keys to reorder)")

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        # Drag handle icon
        self._handle = QLabel("⠿")
        self._handle.setObjectName("dragHandleLabel")
        self._handle.setCursor(Qt.CursorShape.OpenHandCursor)
        layout.addWidget(self._handle)

        # Position badge (1..7)
        self._badge = QLabel(str(self._index + 1))
        self._badge.setObjectName("segmentBadge")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._badge)

        # Field title
        self._title = QLabel(self._label_text)
        self._title.setObjectName("segmentTitle")
        layout.addWidget(self._title)

        layout.addStretch(1)

        # Reorder buttons
        self._btn_up = QToolButton()
        self._btn_up.setText("▲")
        self._btn_up.setObjectName("segmentMoveBtn")
        self._btn_up.setToolTip("Move up")
        self._btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_up.clicked.connect(lambda: self.move_requested.emit(self.field_id, -1))
        layout.addWidget(self._btn_up)

        self._btn_down = QToolButton()
        self._btn_down.setText("▼")
        self._btn_down.setObjectName("segmentMoveBtn")
        self._btn_down.setToolTip("Move down")
        self._btn_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_down.clicked.connect(lambda: self.move_requested.emit(self.field_id, 1))
        layout.addWidget(self._btn_down)

    def update_index(self, index: int, total: int):
        self._index = index
        self._badge.setText(str(index + 1))
        self._btn_up.setEnabled(index > 0)
        self._btn_down.setEnabled(index < total - 1)

    # ------------------------------------------------------------------ #
    #  Drag and Drop Events                                                #
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start_pos:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance >= QApplication.startDragDistance():
                self._start_drag()
                self._drag_start_pos = None
                return
        super().mouseMoveEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_TYPE_FIELD_ID, self.field_id.encode("utf-8"))
        drag.setMimeData(mime)

        # Visual feedback: semi-transparent pixmap snapshot of this card
        pixmap = self.grab()
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 200))
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(self._drag_start_pos or QPoint(pixmap.width() // 2, pixmap.height() // 2))

        self.setProperty("dragging", "true")
        self.style().unpolish(self)
        self.style().polish(self)

        drag.exec(Qt.DropAction.MoveAction)

        self.setProperty("dragging", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    # ------------------------------------------------------------------ #
    #  Keyboard navigation                                                 #
    # ------------------------------------------------------------------ #
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up:
            self.move_requested.emit(self.field_id, -1)
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Down:
            self.move_requested.emit(self.field_id, 1)
            event.accept()
            return
        super().keyPressEvent(event)


class _DropTargetContainer(QWidget):
    """
    Container that holds all 7 segment cards and coordinates
    drag-over drop indicators and drop positioning.
    """

    reordered = Signal(str, int)  # (field_id, target_index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drop_indicator_index: int = -1

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_FIELD_ID):
            event.acceptProposedAction()
            self._update_drop_indicator(event.position().toPoint().y())
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_FIELD_ID):
            event.acceptProposedAction()
            self._update_drop_indicator(event.position().toPoint().y())
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_indicator_index = -1
        self.update()
        event.accept()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_FIELD_ID):
            field_id = bytes(event.mimeData().data(MIME_TYPE_FIELD_ID)).decode("utf-8")
            target_idx = self._drop_indicator_index
            self._drop_indicator_index = -1
            self.update()

            if target_idx != -1:
                self.reordered.emit(field_id, target_idx)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _update_drop_indicator(self, mouse_y: int):
        target_idx = self._calculate_target_index(mouse_y)
        if target_idx != self._drop_indicator_index:
            self._drop_indicator_index = target_idx
            self.update()

    def _calculate_target_index(self, mouse_y: int) -> int:
        child_count = self._layout.count()
        if child_count == 0:
            return 0

        for i in range(child_count):
            item = self._layout.itemAt(i)
            widget = item.widget() if item else None
            if widget and widget.isVisible():
                mid_y = widget.y() + widget.height() / 2
                if mouse_y < mid_y:
                    return i
        return child_count

    def paintEvent(self, event):
        super().paintEvent(event)
        # Draw a bright blue drop line indicator between cards
        if self._drop_indicator_index != -1:
            child_count = self._layout.count()
            if child_count == 0:
                return

            if self._drop_indicator_index < child_count:
                widget = self._layout.itemAt(self._drop_indicator_index).widget()
                indicator_y = widget.y() - 2 if widget else 0
            else:
                last_widget = self._layout.itemAt(child_count - 1).widget()
                indicator_y = (last_widget.y() + last_widget.height() + 2) if last_widget else self.height()

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("#3b82f6"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(4, int(indicator_y), self.width() - 4, int(indicator_y))
            # Draw circle end caps on the drop line
            painter.setBrush(QColor("#3b82f6"))
            painter.drawEllipse(2, int(indicator_y) - 3, 6, 6)
            painter.drawEllipse(self.width() - 8, int(indicator_y) - 3, 6, 6)
            painter.end()


class FilenameSequenceBuilderWidget(QWidget):
    """
    'Customize Filename Sequence' component.
    Allows users to drag-and-drop or use ▲/▼ to arrange the 7 metadata fields.
    Integrates directly with QSettings and the live filename preview.
    """

    sequence_changed = Signal(list)  # (sequence: list[str])

    SETTINGS_KEY_SEQUENCE = "filename/sequence"
    SETTINGS_KEY_EXPANDED = "filename/sequence_expanded"

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._sequence: List[str] = self.load_sequence()
        self._cards: dict[str, _DraggableSegmentCard] = {}

        self._setup_ui()
        self._rebuild_cards()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                     #
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        self.setObjectName("sequenceBuilderWidget")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        # Header Bar
        header_bar = QWidget()
        header_bar.setObjectName("sequenceHeaderBar")
        hbl = QHBoxLayout(header_bar)
        hbl.setContentsMargins(0, 4, 0, 4)
        hbl.setSpacing(6)

        # Section title with toggle
        self._btn_toggle = QToolButton()
        self._btn_toggle.setText("▾")
        self._btn_toggle.setObjectName("sequenceToggleBtn")
        self._btn_toggle.setToolTip("Expand / Collapse sequence builder")
        self._btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_toggle.clicked.connect(self._toggle_expand)
        hbl.addWidget(self._btn_toggle)

        title_lbl = QLabel("Customize Filename Sequence")
        title_lbl.setObjectName("sequenceHeader")
        hbl.addWidget(title_lbl)

        hbl.addStretch(1)

        # Reset button
        self._btn_reset = QPushButton("↺ Reset")
        self._btn_reset.setObjectName("btnResetSequence")
        self._btn_reset.setToolTip("Reset to Default Sequence")
        self._btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset.clicked.connect(self.reset_to_default)
        hbl.addWidget(self._btn_reset)

        outer.addWidget(header_bar)

        # Subtitle / Instructions
        self._subtitle = QLabel("Drag segments or use ▲ / ▼ to rearrange filename order:")
        self._subtitle.setObjectName("sequenceSubtitle")
        outer.addWidget(self._subtitle)

        # Expandable container for segment cards
        self._container = _DropTargetContainer()
        self._container.setObjectName("sequenceContainer")
        self._container.reordered.connect(self._on_drop_reorder)
        outer.addWidget(self._container)

        # Restore expanded state (default True so user sees it)
        is_expanded = self._settings.value(self.SETTINGS_KEY_EXPANDED, "true")
        expanded = str(is_expanded).lower() != "false"
        self._set_expanded(expanded)

    def _toggle_expand(self):
        self._set_expanded(not self._container.isVisible())

    def _set_expanded(self, expanded: bool):
        self._container.setVisible(expanded)
        self._subtitle.setVisible(expanded)
        self._btn_toggle.setText("▾" if expanded else "▸")
        self._settings.setValue(self.SETTINGS_KEY_EXPANDED, "true" if expanded else "false")

    def _rebuild_cards(self):
        # Clear existing layout
        while self._container._layout.count():
            item = self._container._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._cards.clear()

        # Re-populate cards in current sequence order
        total = len(self._sequence)
        for idx, field_id in enumerate(self._sequence):
            info = FIELD_DEFINITIONS.get(field_id, {"label": field_id})
            card = _DraggableSegmentCard(field_id, info["label"], idx, self._container)
            card.move_requested.connect(self._on_card_move_requested)
            card.update_index(idx, total)
            self._cards[field_id] = card
            self._container._layout.addWidget(card)

    # ------------------------------------------------------------------ #
    #  Reordering logic                                                    #
    # ------------------------------------------------------------------ #
    def _on_card_move_requested(self, field_id: str, delta: int):
        try:
            cur_idx = self._sequence.index(field_id)
        except ValueError:
            return

        target_idx = cur_idx + delta
        if 0 <= target_idx < len(self._sequence):
            # Swap with neighbor
            self._sequence.pop(cur_idx)
            self._sequence.insert(target_idx, field_id)
            self._apply_sequence(self._sequence)

    def _on_drop_reorder(self, field_id: str, target_pos: int):
        try:
            old_idx = self._sequence.index(field_id)
        except ValueError:
            return

        new_seq = list(self._sequence)
        new_seq.pop(old_idx)
        if old_idx < target_pos:
            target_pos -= 1
        target_pos = max(0, min(target_pos, len(new_seq)))
        new_seq.insert(target_pos, field_id)

        self._apply_sequence(new_seq)

    def _apply_sequence(self, new_seq: List[str]):
        self._sequence = validate_sequence(new_seq)
        self._rebuild_cards()
        self.save_sequence()
        self.sequence_changed.emit(list(self._sequence))

    # ------------------------------------------------------------------ #
    #  Public API & Persistence                                           #
    # ------------------------------------------------------------------ #
    def current_sequence(self) -> List[str]:
        return list(self._sequence)

    def set_sequence(self, sequence: List[str]):
        self._apply_sequence(sequence)

    def reset_to_default(self):
        self._apply_sequence(list(DEFAULT_SEQUENCE))

    def load_sequence(self) -> List[str]:
        raw = self._settings.value(self.SETTINGS_KEY_SEQUENCE, None)
        if raw is not None:
            if isinstance(raw, list):
                return validate_sequence(raw)
            elif isinstance(raw, str):
                import json
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return validate_sequence(parsed)
                except Exception:
                    pass
        return list(DEFAULT_SEQUENCE)

    def save_sequence(self):
        self._settings.setValue(self.SETTINGS_KEY_SEQUENCE, self._sequence)
