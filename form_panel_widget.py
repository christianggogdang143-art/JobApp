"""
Form Panel Widget - Right panel (~25% width)
Contains the 7 metadata input fields, live filename preview,
Save & Next and Skip buttons, and a progress counter.

Features:
- Auto-uppercase on Book No. field (Roman numerals)
- Live filename preview updates on every keystroke
- Save button disabled until all 7 fields are filled
- Tab-order navigation through fields
- Enter on last field triggers Save & Next
- Book No. and Series persist between documents (sticky fields)
- Windows-forbidden characters (such as /) are automatically converted to safe lookalikes
- Recent history dropdown on Doc Title, Company/Atty, Borrower fields
  (up to 20 entries per field, persisted via QSettings)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QScrollArea,
    QSizePolicy, QSpacerItem, QCompleter, QMenu,
    QToolButton, QApplication,
)
from PySide6.QtCore import Qt, Signal, QSettings, QStringListModel, QPoint, QMimeData
from PySide6.QtGui import QFont, QKeyEvent, QAction, QDrag, QPainter, QColor, QPen

from naming_logic import (
    DocumentMetadata,
    sanitize_filename_component,
    replace_forbidden_chars,
    FORBIDDEN_CHARS_PATTERN,
    DEFAULT_SEQUENCE,
    FIELD_DEFINITIONS,
    validate_sequence,
)
import re


# Characters to silently strip while typing (control characters)
_STRIP_PATTERN = re.compile(r'[\x00-\x1f\x7f\\/:*?"<>|]')

# Max number of recent items stored per field
HISTORY_MAX = 20
MIME_TYPE_FIELD_ID = "application/x-jobapp-field-id"


# --------------------------------------------------------------------------- #
#  Draggable field row & container                                             #
# --------------------------------------------------------------------------- #

class DraggableFieldRow(QWidget):
    """
    A single metadata field row consisting of:
    - Header line: ⠿ Drag handle + FIELD LABEL + ▲/▼ reorder buttons
    - The actual input widget (e.g. QLineEdit or _HistoryLineEdit)
    """
    move_requested = Signal(str, int)  # (field_id, delta: -1 or +1)

    def __init__(self, field_id: str, label_text: str, input_widget: QWidget, parent=None):
        super().__init__(parent)
        self.field_id = field_id
        self.input_widget = input_widget
        self._drag_start_pos: QPoint | None = None

        self.setObjectName("draggableFieldRow")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        # Header line
        self._header = QWidget()
        self._header.setObjectName("fieldRowHeader")
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        # Drag handle
        self._handle = QLabel("⠿")
        self._handle.setObjectName("fieldDragHandle")
        self._handle.setCursor(Qt.CursorShape.OpenHandCursor)
        self._handle.setToolTip("Click and drag to reorder field")
        hl.addWidget(self._handle)

        # Label
        self._label = QLabel(label_text.upper())
        self._label.setObjectName("fieldLabel")
        self._label.setCursor(Qt.CursorShape.OpenHandCursor)
        self._label.setToolTip("Click and drag to reorder field")
        hl.addWidget(self._label)

        hl.addStretch(1)

        # Reorder buttons
        self._btn_up = QToolButton()
        self._btn_up.setText("▲")
        self._btn_up.setObjectName("fieldRowMoveBtn")
        self._btn_up.setToolTip("Move field up")
        self._btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_up.clicked.connect(lambda: self.move_requested.emit(self.field_id, -1))
        hl.addWidget(self._btn_up)

        self._btn_down = QToolButton()
        self._btn_down.setText("▼")
        self._btn_down.setObjectName("fieldRowMoveBtn")
        self._btn_down.setToolTip("Move field down")
        self._btn_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_down.clicked.connect(lambda: self.move_requested.emit(self.field_id, 1))
        hl.addWidget(self._btn_down)

        v.addWidget(self._header)
        v.addWidget(input_widget)

        self._handle.installEventFilter(self)
        self._label.installEventFilter(self)
        self._header.installEventFilter(self)

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent
        if watched in (self._handle, self._label, self._header):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_pos = event.pos()
            elif event.type() == QEvent.Type.MouseMove and (event.buttons() & Qt.MouseButton.LeftButton) and self._drag_start_pos:
                dist = (event.pos() - self._drag_start_pos).manhattanLength()
                if dist >= QApplication.startDragDistance():
                    self._start_drag()
                    self._drag_start_pos = None
                    return True
        return super().eventFilter(watched, event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_TYPE_FIELD_ID, self.field_id.encode("utf-8"))
        drag.setMimeData(mime)

        pixmap = self.grab()
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 190))
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, 14))

        self.setProperty("dragging", "true")
        self.style().unpolish(self)
        self.style().polish(self)

        drag.exec(Qt.DropAction.MoveAction)

        self.setProperty("dragging", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def update_buttons(self, idx: int, total: int):
        self._btn_up.setEnabled(idx > 0)
        self._btn_down.setEnabled(idx < total - 1)


class DraggableFieldsContainer(QWidget):
    """
    Container for draggable field rows.
    Supports drag-and-drop reordering with visual drop indicator line.
    """
    reordered = Signal(list)  # (new_sequence: list[str])

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drop_indicator_index: int = -1
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_FIELD_ID):
            event.acceptProposedAction()
            self._update_indicator(event.position().toPoint().y())
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_FIELD_ID):
            event.acceptProposedAction()
            self._update_indicator(event.position().toPoint().y())
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_indicator_index = -1
        self.update()
        event.accept()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE_FIELD_ID):
            field_id = bytes(event.mimeData().data(MIME_TYPE_FIELD_ID)).decode("utf-8")
            target_pos = self._drop_indicator_index
            self._drop_indicator_index = -1
            self.update()
            if target_pos != -1:
                self._move_field_to(field_id, target_pos)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _update_indicator(self, mouse_y: int):
        target_idx = self._calculate_target_index(mouse_y)
        if target_idx != self._drop_indicator_index:
            self._drop_indicator_index = target_idx
            self.update()

    def _calculate_target_index(self, mouse_y: int) -> int:
        count = self._layout.count()
        if count == 0:
            return 0
        for i in range(count):
            w = self._layout.itemAt(i).widget()
            if w and w.isVisible():
                if mouse_y < w.y() + w.height() / 2:
                    return i
        return count

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_indicator_index != -1:
            count = self._layout.count()
            if count == 0:
                return
            if self._drop_indicator_index < count:
                w = self._layout.itemAt(self._drop_indicator_index).widget()
                y = w.y() - 3 if w else 0
            else:
                last_w = self._layout.itemAt(count - 1).widget()
                y = (last_w.y() + last_w.height() + 3) if last_w else self.height()

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("#3b82f6"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(2, int(y), self.width() - 2, int(y))
            painter.setBrush(QColor("#3b82f6"))
            painter.drawEllipse(0, int(y) - 3, 6, 6)
            painter.drawEllipse(self.width() - 6, int(y) - 3, 6, 6)
            painter.end()

    def current_sequence(self) -> list[str]:
        seq = []
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, DraggableFieldRow):
                seq.append(w.field_id)
        return seq

    def _move_field_to(self, field_id: str, target_pos: int):
        seq = self.current_sequence()
        if field_id not in seq:
            return
        old_idx = seq.index(field_id)
        row_widget = self._layout.itemAt(old_idx).widget()

        self._layout.removeWidget(row_widget)
        if old_idx < target_pos:
            target_pos -= 1
        target_pos = max(0, min(target_pos, self._layout.count()))
        self._layout.insertWidget(target_pos, row_widget)
        self._update_all_buttons()
        self.reordered.emit(self.current_sequence())

    def move_field_delta(self, field_id: str, delta: int):
        seq = self.current_sequence()
        if field_id not in seq:
            return
        cur_idx = seq.index(field_id)
        target_idx = cur_idx + delta
        if 0 <= target_idx < len(seq):
            row_widget = self._layout.itemAt(cur_idx).widget()
            self._layout.removeWidget(row_widget)
            self._layout.insertWidget(target_idx, row_widget)
            self._update_all_buttons()
            self.reordered.emit(self.current_sequence())

    def _update_all_buttons(self):
        count = self._layout.count()
        for i in range(count):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, DraggableFieldRow):
                w.update_buttons(i, count)


# --------------------------------------------------------------------------- #
#  Base sanitized line edit                                                    #
# --------------------------------------------------------------------------- #

class _SanitizedLineEdit(QLineEdit):
    """
    QLineEdit that converts forbidden Windows filename characters to safe lookalikes on the fly.
    Accepts an optional transform function applied after sanitization
    (e.g., str.upper for Roman numerals).
    """
    def __init__(self, transform=None, placeholder: str = "", parent=None):
        super().__init__(parent)
        self._transform = transform
        self.setPlaceholderText(placeholder)
        self.textEdited.connect(self._on_text_edited)

    def setText(self, text: str):
        if text is not None:
            cleaned = replace_forbidden_chars(text)
            cleaned = _STRIP_PATTERN.sub("", cleaned)
            if self._transform:
                cleaned = self._transform(cleaned)
            super().setText(cleaned)
        else:
            super().setText("")

    def _on_text_edited(self, text: str):
        cleaned = replace_forbidden_chars(text)
        cleaned = _STRIP_PATTERN.sub("", cleaned)
        if self._transform:
            cleaned = self._transform(cleaned)
        if cleaned != text:
            self.blockSignals(True)
            cursor_pos = self.cursorPosition() - (len(text) - len(cleaned))
            super().setText(cleaned)
            self.setCursorPosition(max(0, cursor_pos))
            self.blockSignals(False)
            self.textChanged.emit(cleaned)


# --------------------------------------------------------------------------- #
#  History line edit (sanitized + dropdown of recent values)                  #
# --------------------------------------------------------------------------- #

class _HistoryLineEdit(QWidget):
    """
    A compound widget: a _SanitizedLineEdit + a small ▾ button that
    pops up a dropdown menu of recently-used values loaded from QSettings.

    The widget mimics the QLineEdit API surface needed by FormPanelWidget:
      .text(), .setText(), .clear(), .setFocus(), .setObjectName(),
      .setPlaceholderText(), .textChanged (signal), .returnPressed (signal)

    History is stored under settings key  history/<field_key>  as a list.
    """

    # Forward the inner QLineEdit signals so FormPanelWidget can connect to them
    textChanged    = Signal(str)
    returnPressed  = Signal()

    def __init__(self, settings: QSettings, field_key: str,
                 placeholder: str = "", parent=None):
        super().__init__(parent)
        self._settings  = settings
        self._field_key = f"history/{field_key}"

        # ----- Layout -----
        hl = QHBoxLayout(self)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        # Inner line edit
        self._edit = _SanitizedLineEdit(placeholder=placeholder)
        self._edit.setObjectName("formField")
        hl.addWidget(self._edit)

        # Dropdown button
        self._btn = QToolButton()
        self._btn.setText("▾")
        self._btn.setObjectName("historyDropBtn")
        self._btn.setToolTip("Show recent values")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._show_history_menu)
        hl.addWidget(self._btn)

        # QCompleter for type-ahead
        self._completer_model = QStringListModel()
        completer = QCompleter(self._completer_model, self._edit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._edit.setCompleter(completer)

        # Forward signals
        self._edit.textChanged.connect(self.textChanged)
        self._edit.returnPressed.connect(self.returnPressed)

        self._refresh_completer()

    # ------------------------------------------------------------------ #
    #  Public QLineEdit-like API                                           #
    # ------------------------------------------------------------------ #
    def text(self) -> str:
        return self._edit.text()

    def setText(self, text: str):
        self._edit.setText(text)

    def clear(self):
        self._edit.clear()

    def setFocus(self):
        self._edit.setFocus()

    def setObjectName(self, name: str):
        # Apply object name to the inner edit so stylesheets work
        self._edit.setObjectName(name)
        super().setObjectName(name + "_container")

    def setPlaceholderText(self, text: str):
        self._edit.setPlaceholderText(text)

    # ------------------------------------------------------------------ #
    #  History management                                                  #
    # ------------------------------------------------------------------ #
    def load_history(self) -> list[str]:
        raw = self._settings.value(self._field_key, [])
        if isinstance(raw, str):
            return [raw] if raw else []
        return list(raw) if raw else []

    def push_to_history(self, value: str):
        """
        Adds value to the front of the history list, deduplicating
        and capping at HISTORY_MAX entries. Call this on Save.
        """
        value = value.strip()
        if not value:
            return
        history = self.load_history()
        # Remove existing occurrence (case-insensitive dedup)
        history = [h for h in history if h.lower() != value.lower()]
        history.insert(0, value)
        history = history[:HISTORY_MAX]
        self._settings.setValue(self._field_key, history)
        self._refresh_completer()

    def _refresh_completer(self):
        self._completer_model.setStringList(self.load_history())

    # ------------------------------------------------------------------ #
    #  Dropdown menu                                                       #
    # ------------------------------------------------------------------ #
    def _show_history_menu(self):
        history = self.load_history()
        menu = QMenu(self)
        menu.setObjectName("historyMenu")

        if not history:
            empty_act = QAction("(no recent values)", menu)
            empty_act.setEnabled(False)
            menu.addAction(empty_act)
        else:
            # Section header (not clickable)
            hdr = QAction("🕐  Recent", menu)
            hdr.setEnabled(False)
            hdr.setObjectName("historyMenuHeader")
            menu.addAction(hdr)
            menu.addSeparator()

            for item in history:
                act = QAction(item, menu)
                # Capture item in closure
                act.triggered.connect(lambda checked, v=item: self._select_item(v))
                menu.addAction(act)

            menu.addSeparator()
            clear_act = QAction("🗑  Clear history", menu)
            clear_act.setObjectName("historyClearAct")
            clear_act.triggered.connect(self._clear_history)
            menu.addAction(clear_act)

        # Show below the button
        pos = self._btn.mapToGlobal(QPoint(0, self._btn.height()))
        menu.exec(pos)

    def _select_item(self, value: str):
        self._edit.setText(value)
        self._edit.setFocus()

    def _clear_history(self):
        self._settings.remove(self._field_key)
        self._refresh_completer()


# --------------------------------------------------------------------------- #
#  Main form panel                                                             #
# --------------------------------------------------------------------------- #

class FormPanelWidget(QWidget):
    """
    Right panel containing all form fields, live preview and action buttons.
    """

    save_requested = Signal(DocumentMetadata)
    skip_requested = Signal()
    add_document_requested = Signal()

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._restore_sticky_fields()

    # ------------------------------------------------------------------ #
    #  UI Setup                                                            #
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar with Reset Order button
        header_widget = QWidget()
        header_widget.setObjectName("formHeaderBar")
        header_widget.setFixedHeight(44)
        hbl = QHBoxLayout(header_widget)
        hbl.setContentsMargins(16, 0, 16, 0)

        header = QLabel("Document Details")
        header.setObjectName("formHeader")
        hbl.addWidget(header)

        hbl.addStretch(1)

        self._btn_reset_order = QPushButton("↺ Reset Order")
        self._btn_reset_order.setObjectName("btnResetFieldOrder")
        self._btn_reset_order.setToolTip("Reset fields back to default sequence")
        self._btn_reset_order.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset_order.clicked.connect(self._reset_field_order)
        hbl.addWidget(self._btn_reset_order)

        outer.addWidget(header_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("formSep")
        outer.addWidget(sep)

        # Scrollable form body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("formScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        body.setObjectName("formBody")
        form_layout = QVBoxLayout(body)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)

        # --- Plain fields (no history) ---
        self._f_doc_no   = _SanitizedLineEdit(placeholder="e.g. 14")
        self._f_page_no  = _SanitizedLineEdit(placeholder="e.g. 4")
        self._f_book_no  = _SanitizedLineEdit(transform=str.upper, placeholder="e.g. XVIII")
        self._f_series   = _SanitizedLineEdit(placeholder="e.g. 2025")

        # --- History-enabled fields ---
        self._f_doc_title = _HistoryLineEdit(
            self._settings, "doc_title", placeholder="e.g. Security Agreement"
        )
        self._f_company = _HistoryLineEdit(
            self._settings, "company", placeholder="e.g. AFC"
        )
        self._f_borrower = _HistoryLineEdit(
            self._settings, "borrower", placeholder="e.g. Simeon E. and Crizza Mae Bernabe Berdin Sabaricos"
        )

        self._field_inputs = {
            "doc_no": self._f_doc_no,
            "page_no": self._f_page_no,
            "book_no": self._f_book_no,
            "series": self._f_series,
            "doc_title": self._f_doc_title,
            "company_or_atty": self._f_company,
            "borrower": self._f_borrower,
        }

        # Create DraggableFieldRow for each field
        field_configs = [
            ("doc_no",          "Doc No.",        self._f_doc_no),
            ("page_no",         "Page No.",       self._f_page_no),
            ("book_no",         "Book No.",       self._f_book_no),
            ("series",          "Series Of",      self._f_series),
            ("doc_title",       "Doc Title",      self._f_doc_title),
            ("company_or_atty", "Company / Atty", self._f_company),
            ("borrower",        "Borrower Name",  self._f_borrower),
        ]

        self._field_rows: dict[str, DraggableFieldRow] = {}
        for fid, label, inp in field_configs:
            row = DraggableFieldRow(fid, label, inp, self)
            row.move_requested.connect(lambda f_id, delta: self._fields_container.move_field_delta(f_id, delta))
            inp.textChanged.connect(self._update_preview)
            self._field_rows[fid] = row

        # Container holding draggable rows
        self._fields_container = DraggableFieldsContainer(self)
        self._fields_container.reordered.connect(self._on_fields_reordered)

        # Load saved sequence and populate container in order
        saved_seq = self._load_saved_sequence()
        for fid in saved_seq:
            self._fields_container._layout.addWidget(self._field_rows[fid])
        self._fields_container._update_all_buttons()

        form_layout.addWidget(self._fields_container)

        form_layout.addSpacerItem(
            QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        # --- Live preview ---
        preview_header = QLabel("Filename Preview")
        preview_header.setObjectName("previewHeader")
        form_layout.addWidget(preview_header)

        self._preview_frame = QFrame()
        self._preview_frame.setObjectName("previewFrame")
        pfl = QVBoxLayout(self._preview_frame)
        pfl.setContentsMargins(10, 8, 10, 8)

        self._preview_label = QLabel("")
        self._preview_label.setObjectName("previewLabel")
        self._preview_label.setWordWrap(True)
        self._preview_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        pfl.addWidget(self._preview_label)

        self._preview_path_label = QLabel("")
        self._preview_path_label.setObjectName("previewPathLabel")
        self._preview_path_label.setWordWrap(True)
        self._preview_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        pfl.addWidget(self._preview_path_label)

        form_layout.addWidget(self._preview_frame)

        form_layout.addSpacerItem(
            QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # --- Pinned Bottom Action Area ---
        bottom_area = QWidget()
        bottom_area.setObjectName("formBottomArea")
        bottom_layout = QVBoxLayout(bottom_area)
        bottom_layout.setContentsMargins(16, 6, 16, 8)
        bottom_layout.setSpacing(6)

        # Merge / Add Document card
        self._merged_info_card = QFrame()
        self._merged_info_card.setObjectName("mergedInfoCard")
        mic_layout = QVBoxLayout(self._merged_info_card)
        mic_layout.setContentsMargins(10, 6, 10, 6)
        mic_layout.setSpacing(4)

        self._merged_info_label = QLabel("Missing pages in this document?")
        self._merged_info_label.setObjectName("mergedInfoLabel")
        self._merged_info_label.setWordWrap(True)
        mic_layout.addWidget(self._merged_info_label)

        self._btn_form_add_doc = QPushButton("➕ Add Document (Insert Pages)")
        self._btn_form_add_doc.setObjectName("btnFormAddDoc")
        self._btn_form_add_doc.setToolTip("Select an additional PDF from file manager to merge missing pages")
        self._btn_form_add_doc.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_form_add_doc.clicked.connect(self.add_document_requested.emit)
        mic_layout.addWidget(self._btn_form_add_doc)

        bottom_layout.addWidget(self._merged_info_card)

        # Buttons row
        self._btn_save = QPushButton("💾  Save && Next")
        self._btn_save.setObjectName("btnSave")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)

        self._btn_skip = QPushButton("⏭  Skip")
        self._btn_skip.setObjectName("btnSkip")
        self._btn_skip.clicked.connect(self.skip_requested.emit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_skip)
        bottom_layout.addLayout(btn_row)

        outer.addWidget(bottom_area)

        # --- Progress bar area ---
        self._progress_bar_widget = _ProgressWidget()
        self._progress_bar_widget.setObjectName("progressWidget")
        outer.addWidget(self._progress_bar_widget)

        self._last_edit_connected = None
        self._update_tab_order()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def set_output_root(self, output_root: str):
        """Provide the output root path so preview can show full destination."""
        self._output_root = output_root
        self._update_preview()

    def set_attached_info(self, attached_count: int, total_pages: int, attached_names: list[str]):
        """Updates the visual merge banner and save button text according to connected documents."""
        if not hasattr(self, "_merged_info_card"):
            return
        if attached_count == 0:
            self._merged_info_card.setProperty("hasAttached", "false")
            self._merged_info_label.setText("Missing pages in this document?")
            self._btn_form_add_doc.setText("➕ Add Document (Insert Pages)")
            self._btn_save.setText("💾  Save && Next")
        else:
            self._merged_info_card.setProperty("hasAttached", "true")
            names_str = ", ".join(attached_names[:2])
            if len(attached_names) > 2:
                names_str += f" (+{len(attached_names) - 2} more)"
            self._merged_info_label.setText(
                f"🔗 <b>{attached_count} Document{'s' if attached_count > 1 else ''} Connected</b> "
                f"({total_pages} total pages)<br>"
                f"<span style='color: #cbd5e1; font-size: 11px;'>Attached: {names_str}</span><br>"
                f"<span style='color: #38bdf8; font-size: 11px; font-weight: 600;'>Will merge into a single PDF upon Save & Next</span>"
            )
            self._btn_form_add_doc.setText("➕ Add Another Document")
            self._btn_save.setText(f"💾  Merge ({total_pages} pgs) && Next")

        self._merged_info_card.style().unpolish(self._merged_info_card)
        self._merged_info_card.style().polish(self._merged_info_card)

    def reset_for_next(self):
        """Clear per-document fields (keep sticky Book No. + Series)."""
        self.set_attached_info(0, 0, [])
        self._f_doc_no.clear()
        self._f_page_no.clear()
        # Intentionally do NOT clear book_no and series (sticky)
        self._f_doc_title.clear()
        self._f_company.clear()
        self._f_borrower.clear()
        self._f_doc_no.setFocus()
        self._update_preview()

    def set_progress(self, done: int, total: int):
        self._progress_bar_widget.set_progress(done, total)

    def current_sequence(self) -> list[str]:
        if hasattr(self, "_fields_container"):
            return self._fields_container.current_sequence()
        return list(DEFAULT_SEQUENCE)

    def current_metadata(self) -> DocumentMetadata:
        return DocumentMetadata(
            doc_no=self._f_doc_no.text(),
            page_no=self._f_page_no.text(),
            book_no=self._f_book_no.text(),
            series=self._f_series.text(),
            doc_title=self._f_doc_title.text(),
            company_or_atty=self._f_company.text(),
            borrower=self._f_borrower.text(),
            sequence=self.current_sequence(),
        )

    # ------------------------------------------------------------------ #
    #  Sequence persistence and reorder handlers                          #
    # ------------------------------------------------------------------ #
    def _load_saved_sequence(self) -> list[str]:
        raw = self._settings.value("filename/sequence", None)
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

    def _on_fields_reordered(self, seq: list[str]):
        self._settings.setValue("filename/sequence", seq)
        self._update_tab_order()
        self._update_preview()

    def _reset_field_order(self):
        for fid in DEFAULT_SEQUENCE:
            row = self._field_rows.get(fid)
            if row:
                self._fields_container._layout.removeWidget(row)
                self._fields_container._layout.addWidget(row)
        self._fields_container._update_all_buttons()
        self._on_fields_reordered(list(DEFAULT_SEQUENCE))

    def _update_tab_order(self):
        if not hasattr(self, "_fields_container") or not hasattr(self, "_field_inputs"):
            return
        seq = self._fields_container.current_sequence()
        edits = []
        for fid in seq:
            field_widget = self._field_inputs.get(fid)
            if field_widget:
                e = getattr(field_widget, "_edit", field_widget)
                edits.append(e)

        for i in range(len(edits) - 1):
            self.setTabOrder(edits[i], edits[i + 1])

        # Disconnect previous last edit returnPressed
        if hasattr(self, "_last_edit_connected") and self._last_edit_connected:
            try:
                self._last_edit_connected.returnPressed.disconnect(self._on_save)
            except Exception:
                pass
        if edits:
            edits[-1].returnPressed.connect(self._on_save)
            self._last_edit_connected = edits[-1]

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #
    def _update_preview(self):
        meta = self.current_metadata()
        is_valid, _ = meta.validate()

        if is_valid:
            filename = meta.build_filename()
            book_folder = meta.build_book_folder_name()
            self._preview_label.setText(f"📄 {filename}")
            output_root = getattr(self, "_output_root", "")
            if output_root:
                import os
                dest = os.path.join(output_root, book_folder, filename)
                self._preview_path_label.setText(f"📁 {dest}")
                self._preview_path_label.setVisible(True)
            else:
                self._preview_path_label.setVisible(False)
            self._preview_frame.setProperty("valid", "true")
        else:
            self._preview_label.setText("Fill in all fields to see preview…")
            self._preview_path_label.setVisible(False)
            self._preview_frame.setProperty("valid", "false")

        self._preview_frame.style().unpolish(self._preview_frame)
        self._preview_frame.style().polish(self._preview_frame)

        self._btn_save.setEnabled(is_valid)

    def _on_save(self):
        meta = self.current_metadata()
        is_valid, _ = meta.validate()
        if not is_valid:
            return

        s = meta.sanitized()

        # Persist sticky fields
        self._settings.setValue("sticky/book_no", s.book_no)
        self._settings.setValue("sticky/series",  s.series)

        # Push history for the three content fields
        self._f_doc_title.push_to_history(s.doc_title)
        self._f_company.push_to_history(s.company_or_atty)
        self._f_borrower.push_to_history(s.borrower)

        self.save_requested.emit(meta)

    def _restore_sticky_fields(self):
        book_no = self._settings.value("sticky/book_no", "")
        series  = self._settings.value("sticky/series",  "")
        if book_no:
            self._f_book_no.setText(book_no)
        if series:
            self._f_series.setText(series)


# --------------------------------------------------------------------------- #
#  Progress widget                                                             #
# --------------------------------------------------------------------------- #

class _ProgressWidget(QWidget):
    """Compact progress bar + counter shown at the bottom of the panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self._label = QLabel("No files loaded")
        self._label.setObjectName("progressLabel")
        layout.addWidget(self._label)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        from PySide6.QtWidgets import QProgressBar
        self._bar = QProgressBar()
        self._bar.setObjectName("progressBar")
        self._bar.setFixedWidth(80)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)

    def set_progress(self, done: int, total: int):
        if total > 0:
            self._label.setText(f"{done} of {total} done")
            self._bar.setMaximum(total)
            self._bar.setValue(done)
        else:
            self._label.setText("No files loaded")
            self._bar.setValue(0)
