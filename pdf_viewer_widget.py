import io
import pypdf

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QLabel, QLineEdit, QToolButton, QSizePolicy,
    QSpacerItem, QFrame, QComboBox, QScrollArea,
)
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument
from PySide6.QtCore import Qt, QBuffer, QByteArray, Signal, QPoint, QPointF
from PySide6.QtGui import QIcon, QFont, QAction, QKeySequence, QShortcut, QWheelEvent


class _InteractivePdfView(QPdfView):
    """
    Subclass of QPdfView that supports:
    - Ctrl + Mouse Wheel zooming centered on cursor
    - Native trackpad pinch gesture zoom
    - Middle-click mouse drag to pan
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pan_active = False
        self._pan_start = QPoint()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta != 0:
                parent = self.parent()
                while parent and not hasattr(parent, "_handle_wheel_zoom"):
                    parent = parent.parent()
                if parent:
                    pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    parent._handle_wheel_zoom(delta, pos)
                    event.accept()
                    return
        super().wheelEvent(event)

    def event(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.NativeGesture:
            if hasattr(Qt, "NativeGestureType") and hasattr(event, "gestureType") and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                val = event.value()
                if abs(val) > 0.01:
                    parent = self.parent()
                    while parent and not hasattr(parent, "_handle_wheel_zoom"):
                        parent = parent.parent()
                    if parent:
                        delta = 120 if val > 0 else -120
                        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                        parent._handle_wheel_zoom(delta, pos)
                        event.accept()
                        return True
        return super().event(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan_active:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class PdfViewerWidget(QWidget):
    """
    Left panel: large PDF viewer with comprehensive toolbar controls,
    direct interactive zoom in the preview, and an Attached Documents bar
    that supports multi-document in-memory merging and page jumping.
    """

    page_changed = Signal(int, int)  # (current_page, total_pages)
    add_document_requested = Signal()
    remove_document_requested = Signal(int)  # index of attached doc
    move_document_requested = Signal(int, int)  # (index, delta: -1 or +1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._document = QPdfDocument(self)
        self._buffer = None   # keep reference so GC doesn't collect it
        self._byte_array = None
        self._total_pages = 0
        self._setup_ui()
        self._setup_shortcuts()

    # ------------------------------------------------------------------ #
    #  UI setup                                                            #
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Interactive PDF View
        self._view = _InteractivePdfView(self)
        self._view.setDocument(self._document)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Toolbar
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        # Attached documents strip (appears when documents are attached/connected)
        self._attached_bar = self._build_attached_bar()
        layout.addWidget(self._attached_bar)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("viewerSep")
        layout.addWidget(sep)

        layout.addWidget(self._view, 1)

        # Connect page change signals
        nav = self._view.pageNavigator()
        nav.currentPageChanged.connect(self._on_page_changed)

    def _setup_shortcuts(self):
        # Keyboard zoom shortcuts
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Plus), self, self.zoom_in)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Equal), self, self.zoom_in)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Minus), self, self.zoom_out)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_0), self, self.zoom_fit_width)
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_9), self, self.zoom_fit_page)

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setObjectName("viewerToolbar")
        toolbar.setFixedHeight(44)

        hl = QHBoxLayout(toolbar)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(4)

        def _btn(text: str, tooltip: str, callback) -> QToolButton:
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tooltip)
            b.setObjectName("toolbarBtn")
            b.clicked.connect(callback)
            return b

        # ---- Zoom controls ----
        lbl_zoom = QLabel("Zoom:")
        lbl_zoom.setObjectName("zoomLabel")
        hl.addWidget(lbl_zoom)

        self._btn_zoom_out = _btn("−", "Zoom Out (Ctrl+Minus or Ctrl+Scroll Down)", self.zoom_out)
        hl.addWidget(self._btn_zoom_out)

        # Zoom level dropdown / editable indicator
        self._zoom_combo = QComboBox()
        self._zoom_combo.setObjectName("zoomCombo")
        self._zoom_combo.setFixedWidth(135)
        self._zoom_combo.setEditable(True)
        self._zoom_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._zoom_combo.addItems([
            "Fit Width",
            "Fit Page",
            "50%",
            "75%",
            "100%",
            "125%",
            "150%",
            "200%",
            "300%",
            "400%",
        ])
        self._zoom_combo.setToolTip("Zoom level (select preset or type percentage; Ctrl+Scroll to zoom)")
        self._zoom_combo.activated.connect(self._on_zoom_combo_activated)
        if self._zoom_combo.lineEdit():
            self._zoom_combo.lineEdit().returnPressed.connect(self._on_zoom_custom_entered)
            self._zoom_combo.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self._zoom_combo)

        self._btn_zoom_in  = _btn("+", "Zoom In (Ctrl+Plus or Ctrl+Scroll Up)",  self.zoom_in)
        hl.addWidget(self._btn_zoom_in)

        self._btn_100       = _btn("100%", "Zoom to 100% (Actual Size)", lambda: self.zoom_to_factor(1.0))
        self._btn_fit_width = _btn("Fit Width",   "Fit to Width (Ctrl+0)",    self.zoom_fit_width)
        self._btn_fit_page  = _btn("Fit Page",    "Fit Entire Page (Ctrl+9)", self.zoom_fit_page)
        hl.addWidget(self._btn_100)
        hl.addWidget(self._btn_fit_width)
        hl.addWidget(self._btn_fit_page)

        # ---- Page mode toggle ----
        self._btn_single = _btn("Single", "Single Page Mode", lambda: self._set_page_mode(QPdfView.PageMode.SinglePage))
        self._btn_multi  = _btn("Multi",  "Continuous Scroll", lambda: self._set_page_mode(QPdfView.PageMode.MultiPage))
        hl.addWidget(self._btn_single)
        hl.addWidget(self._btn_multi)

        hl.addItem(QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        # ---- Page navigation ----
        self._btn_prev = _btn("◀", "Previous Page", self.prev_page)
        hl.addWidget(self._btn_prev)

        self._page_label = QLabel("— / —")
        self._page_label.setObjectName("pageLabel")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setFixedWidth(90)
        hl.addWidget(self._page_label)

        self._btn_next = _btn("▶", "Next Page", self.next_page)
        hl.addWidget(self._btn_next)

        # Vertical separator
        vline = QFrame()
        vline.setFrameShape(QFrame.Shape.VLine)
        vline.setObjectName("toolbarVLine")
        hl.addWidget(vline)

        # ---- Add Document button ----
        self._btn_add_doc = QToolButton()
        self._btn_add_doc.setText("➕ Add Document")
        self._btn_add_doc.setToolTip("Add / insert a document from file manager to connect missing pages")
        self._btn_add_doc.setObjectName("toolbarBtnAddDoc")
        self._btn_add_doc.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add_doc.clicked.connect(lambda: self.add_document_requested.emit())
        hl.addWidget(self._btn_add_doc)

        return toolbar

    def _build_attached_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("attachedDocsStrip")
        bar.setFixedHeight(38)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(10, 4, 10, 4)
        bar_layout.setSpacing(8)

        lbl_icon = QLabel("🔗 Connected Pages:")
        lbl_icon.setObjectName("attachedStripTitle")
        bar_layout.addWidget(lbl_icon)

        # Chips container inside a horizontal scroll area
        self._chips_container = QWidget()
        self._chips_container.setObjectName("chipsContainer")
        self._chips_layout = QHBoxLayout(self._chips_container)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._chips_container)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("attachedScroll")
        scroll.setFixedHeight(34)
        bar_layout.addWidget(scroll, 1)

        # Quick Add More button
        self._btn_strip_add_more = QToolButton()
        self._btn_strip_add_more.setText("➕ Add More")
        self._btn_strip_add_more.setToolTip("Connect another document from file manager")
        self._btn_strip_add_more.setObjectName("btnStripAddMore")
        self._btn_strip_add_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_strip_add_more.clicked.connect(lambda: self.add_document_requested.emit())
        bar_layout.addWidget(self._btn_strip_add_more)

        bar.setVisible(False)
        return bar

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def load_pdf(self, file_path: str) -> bool:
        """
        Convenience wrapper around load_pdf_list for a single file.
        """
        return self.load_pdf_list([file_path])

    def load_pdf_list(self, file_paths: list[str]) -> bool:
        """
        Reads one or multiple PDF files into memory (QBuffer) without locking on-disk files.
        If multiple files are given, merges them seamlessly in-memory via pypdf.
        Returns True on success, False on failure.
        """
        self.close_document()
        if not file_paths:
            return False

        try:
            if len(file_paths) == 1:
                with open(file_paths[0], "rb") as f:
                    raw = f.read()
            else:
                writer = pypdf.PdfWriter()
                for p in file_paths:
                    writer.append(p)
                out = io.BytesIO()
                writer.write(out)
                writer.close()
                raw = out.getvalue()
        except Exception:
            self.close_document()
            return False

        self._byte_array = QByteArray(raw)
        self._buffer = QBuffer()
        self._buffer.setData(self._byte_array)
        self._buffer.open(QBuffer.OpenModeFlag.ReadOnly)

        self._document.load(self._buffer)

        if self._document.status() == QPdfDocument.Status.Ready:
            self._total_pages = self._document.pageCount()
            self._update_page_label(0)
            nav = self._view.pageNavigator()
            nav.jump(0, QPointF(0, 0))
            self._update_nav_buttons(0)
            self._update_zoom_display()
            return True
        else:
            self.close_document()
            return False

    def jump_to_page(self, page_index: int):
        """Scrolls/jumps the viewer to the specified 0-indexed page."""
        if self._document.status() == QPdfDocument.Status.Ready and 0 <= page_index < self._total_pages:
            self._view.pageNavigator().jump(page_index, QPointF(0, 0))
            self._update_page_label(page_index)
            self._update_nav_buttons(page_index)

    def update_attached_docs(self, primary_doc: dict, attached_docs: list[dict]):
        """
        Renders chips for primary document and attached documents.
        Each doc dict: {'name': str, 'start_page': int, 'page_count': int}
        """
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not attached_docs:
            self._attached_bar.setVisible(False)
            return

        self._attached_bar.setVisible(True)

        # Primary chip
        prim_chip = self._create_doc_chip(
            name=primary_doc["name"],
            page_range=f"pp. 1-{primary_doc['page_count']}" if primary_doc['page_count'] > 1 else "p. 1",
            start_page=0,
            is_primary=True,
        )
        self._chips_layout.addWidget(prim_chip)

        # Attached doc chips
        for idx, doc in enumerate(attached_docs):
            end_p = doc["start_page"] + doc["page_count"]
            prange = f"p. {doc['start_page'] + 1}" if doc["page_count"] == 1 else f"pp. {doc['start_page'] + 1}-{end_p}"
            chip = self._create_doc_chip(
                name=doc["name"],
                page_range=prange,
                start_page=doc["start_page"],
                is_primary=False,
                index=idx,
                total_attached=len(attached_docs),
            )
            self._chips_layout.addWidget(chip)

        self._chips_layout.addStretch(1)

    def clear_attached_docs(self):
        """Hides the attached documents bar and clears all chips."""
        self._attached_bar.setVisible(False)
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _create_doc_chip(
        self,
        name: str,
        page_range: str,
        start_page: int,
        is_primary: bool,
        index: int = 0,
        total_attached: int = 0,
    ) -> QWidget:
        chip = QFrame()
        chip.setObjectName("attachedChipPrimary" if is_primary else "attachedChip")
        layout = QHBoxLayout(chip)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        display_name = name if len(name) <= 24 else name[:10] + "..." + name[-11:]
        prefix = "📄 Primary: " if is_primary else "📎 "
        lbl = QLabel(f"{prefix}{display_name} ({page_range})")
        lbl.setObjectName("chipLabel")
        lbl.setToolTip(f"{name}\nPage range: {page_range}\nClick 'Preview' to view these pages")
        layout.addWidget(lbl)

        # View / Jump button
        btn_view = QToolButton()
        btn_view.setText("👁 Preview")
        btn_view.setToolTip(f"Jump preview to {name} ({page_range})")
        btn_view.setObjectName("btnChipView")
        btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_view.clicked.connect(lambda: self.jump_to_page(start_page))
        layout.addWidget(btn_view)

        if not is_primary:
            if total_attached > 1:
                btn_up = QToolButton()
                btn_up.setText("◀")
                btn_up.setToolTip("Move earlier in document order")
                btn_up.setObjectName("btnChipMove")
                btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_up.setEnabled(index > 0)
                btn_up.clicked.connect(lambda: self.move_document_requested.emit(index, -1))
                layout.addWidget(btn_up)

                btn_down = QToolButton()
                btn_down.setText("▶")
                btn_down.setToolTip("Move later in document order")
                btn_down.setObjectName("btnChipMove")
                btn_down.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_down.setEnabled(index < total_attached - 1)
                btn_down.clicked.connect(lambda: self.move_document_requested.emit(index, 1))
                layout.addWidget(btn_down)

            btn_remove = QToolButton()
            btn_remove.setText("✕")
            btn_remove.setToolTip(f"Disconnect {name}")
            btn_remove.setObjectName("btnChipRemove")
            btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_remove.clicked.connect(lambda: self.remove_document_requested.emit(index))
            layout.addWidget(btn_remove)

        return chip

    def close_document(self):
        """Explicitly closes and clears the document and its buffer."""
        self._document.close()
        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None
        self._byte_array = None
        self._total_pages = 0
        self._page_label.setText("— / —")
        self._update_zoom_display()

    # ------------------------------------------------------------------ #
    #  Zoom calculations & actions                                         #
    # ------------------------------------------------------------------ #
    def current_effective_zoom(self) -> float:
        if self._view.zoomMode() == QPdfView.ZoomMode.Custom:
            return self._view.zoomFactor()

        if self._document.status() == QPdfDocument.Status.Ready and self._document.pageCount() > 0:
            nav = self._view.pageNavigator()
            cur_page = max(0, nav.currentPage())
            page_size = self._document.pagePointSize(cur_page)
            if page_size.width() > 0 and page_size.height() > 0:
                vp = self._view.viewport()
                margins = self._view.documentMargins()
                margin_w = margins.left() + margins.right()
                margin_h = margins.top() + margins.bottom()
                avail_w = max(10, vp.width() - margin_w)
                avail_h = max(10, vp.height() - margin_h)

                if self._view.zoomMode() == QPdfView.ZoomMode.FitToWidth:
                    return avail_w / page_size.width()
                elif self._view.zoomMode() == QPdfView.ZoomMode.FitInView:
                    return min(avail_w / page_size.width(), avail_h / page_size.height())

        return max(0.1, self._view.zoomFactor())

    def zoom_in(self):
        current_factor = self.current_effective_zoom()
        new_factor = min(current_factor * 1.25, 8.0)
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(new_factor)
        self._update_zoom_display()

    def zoom_out(self):
        current_factor = self.current_effective_zoom()
        new_factor = max(current_factor / 1.25, 0.1)
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(new_factor)
        self._update_zoom_display()

    def zoom_fit_width(self):
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._update_zoom_display()

    def zoom_fit_page(self):
        self._view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self._update_zoom_display()

    def zoom_to_factor(self, factor: float):
        factor = max(0.1, min(factor, 8.0))
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(factor)
        self._update_zoom_display()

    def _handle_wheel_zoom(self, delta: int, cursor_pos: QPoint):
        if self._document.status() != QPdfDocument.Status.Ready or self._total_pages <= 0:
            return

        current_factor = self.current_effective_zoom()
        step = 1.15
        if delta > 0:
            new_factor = min(current_factor * step, 8.0)
        else:
            new_factor = max(current_factor / step, 0.1)

        if abs(new_factor - current_factor) < 0.001:
            return

        h_bar = self._view.horizontalScrollBar()
        v_bar = self._view.verticalScrollBar()

        old_h = h_bar.value()
        old_v = v_bar.value()
        ratio = new_factor / current_factor

        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(new_factor)

        new_h = int((old_h + cursor_pos.x()) * ratio - cursor_pos.x())
        new_v = int((old_v + cursor_pos.y()) * ratio - cursor_pos.y())
        h_bar.setValue(max(0, new_h))
        v_bar.setValue(max(0, new_v))

        self._update_zoom_display()

    def _on_zoom_combo_activated(self, index: int):
        text = self._zoom_combo.itemText(index)
        if text.startswith("Fit Width"):
            self.zoom_fit_width()
        elif text.startswith("Fit Page"):
            self.zoom_fit_page()
        else:
            val_str = text.replace("%", "").strip()
            try:
                factor = float(val_str) / 100.0
                self.zoom_to_factor(factor)
            except ValueError:
                pass

    def _on_zoom_custom_entered(self):
        text = self._zoom_combo.currentText().replace("%", "").strip().lower()
        if text.startswith("fit width"):
            self.zoom_fit_width()
        elif text.startswith("fit"):
            self.zoom_fit_page()
        else:
            try:
                val = float(text)
                factor = val / 100.0
                self.zoom_to_factor(factor)
            except ValueError:
                self._update_zoom_display()

    def _update_zoom_display(self):
        if not hasattr(self, "_zoom_combo"):
            return
        self._zoom_combo.blockSignals(True)
        mode = self._view.zoomMode()
        if mode == QPdfView.ZoomMode.FitToWidth:
            eff = round(self.current_effective_zoom() * 100)
            self._zoom_combo.setCurrentText(f"Fit Width ({eff}%)")
        elif mode == QPdfView.ZoomMode.FitInView:
            eff = round(self.current_effective_zoom() * 100)
            self._zoom_combo.setCurrentText(f"Fit Page ({eff}%)")
        else:
            pct = f"{round(self._view.zoomFactor() * 100)}%"
            self._zoom_combo.setCurrentText(pct)
        self._zoom_combo.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_view") and self._view.zoomMode() in (QPdfView.ZoomMode.FitToWidth, QPdfView.ZoomMode.FitInView):
            self._update_zoom_display()

    # ------------------------------------------------------------------ #
    #  Page navigation                                                     #
    # ------------------------------------------------------------------ #
    def prev_page(self):
        nav = self._view.pageNavigator()
        cur = nav.currentPage()
        if cur > 0:
            nav.jump(cur - 1, QPointF(0, 0))

    def next_page(self):
        nav = self._view.pageNavigator()
        cur = nav.currentPage()
        if cur < self._total_pages - 1:
            nav.jump(cur + 1, QPointF(0, 0))

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #
    def _set_page_mode(self, mode: QPdfView.PageMode):
        self._view.setPageMode(mode)

    def _on_page_changed(self, page: int):
        self._update_page_label(page)
        self._update_nav_buttons(page)
        self.page_changed.emit(page + 1, self._total_pages)

    def _update_page_label(self, page: int):
        if self._total_pages > 0:
            self._page_label.setText(f"{page + 1} / {self._total_pages}")
        else:
            self._page_label.setText("— / —")

    def _update_nav_buttons(self, page: int):
        self._btn_prev.setEnabled(page > 0)
        self._btn_next.setEnabled(page < self._total_pages - 1)
