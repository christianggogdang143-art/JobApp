"""
Main Window - Orchestrates the full application.

Responsibilities:
- Startup folder picker (Input folder + Output root), persisted via QSettings
- Loads all *.pdf files from Input folder into a queue
- Shows each PDF in PdfViewerWidget (left) while FormPanelWidget (right) is filled
- Save & Next: renames and moves the current file to {OutputRoot}/Book No. {BookNo}/
- Skip: moves the current file to the END of the queue
- Shows progress counter
- Warns on duplicate filenames; never overwrites silently
- Shows "All done!" when the queue is empty
"""

import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QMessageBox, QFileDialog, QLabel, QToolBar,
    QDialog, QVBoxLayout, QPushButton, QApplication,
    QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QAction, QFont, QIcon

from pdf_viewer_widget import PdfViewerWidget
from form_panel_widget import FormPanelWidget
from naming_logic import DocumentMetadata


APP_NAME = "PDF Document Naming Tool"
ORG_NAME  = "JobApp"
SETTINGS_KEY_INPUT  = "folders/input"
SETTINGS_KEY_OUTPUT = "folders/output"


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._queue: list[str] = []   # absolute paths of PDFs yet to be processed
        self._done_count = 0
        self._total_count = 0
        self._input_folder = ""
        self._output_folder = ""
        self._current_file: str | None = None
        self._attached_files: list[str] = []

        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        self._setup_ui()
        self._setup_toolbar()

        # Prompt for folders after event loop starts
        QTimer.singleShot(100, self._choose_folders)

    # ------------------------------------------------------------------ #
    #  UI Setup                                                            #
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(2)
        self._splitter.setObjectName("mainSplitter")

        # Left: PDF viewer
        self._viewer = PdfViewerWidget()
        self._viewer.setObjectName("viewerPanel")
        self._splitter.addWidget(self._viewer)

        # Right: Form panel
        self._form = FormPanelWidget(self._settings)
        self._form.setObjectName("formPanel")
        self._form.setMinimumWidth(280)
        self._form.setMaximumWidth(420)
        self._splitter.addWidget(self._form)

        # Set initial split ratio 75/25
        self._splitter.setSizes([960, 320])

        root_layout.addWidget(self._splitter)

        # Connect signals
        self._form.save_requested.connect(self._on_save)
        self._form.skip_requested.connect(self._on_skip)
        self._form.add_document_requested.connect(self._on_add_document)
        self._viewer.add_document_requested.connect(self._on_add_document)
        self._viewer.remove_document_requested.connect(self._on_remove_attached_document)
        self._viewer.move_document_requested.connect(self._on_move_attached_document)

    def _setup_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setObjectName("mainToolbar")

        act_folders = QAction("📂  Change Folders", self)
        act_folders.setToolTip("Pick a new Input or Output folder")
        act_folders.triggered.connect(self._choose_folders)
        tb.addAction(act_folders)

        tb.addSeparator()

        self._toolbar_label = QLabel("  No folder selected")
        self._toolbar_label.setObjectName("toolbarLabel")
        tb.addWidget(self._toolbar_label)

    # ------------------------------------------------------------------ #
    #  Folder selection                                                    #
    # ------------------------------------------------------------------ #
    def _choose_folders(self):
        dlg = _FolderPickerDialog(
            last_input=self._settings.value(SETTINGS_KEY_INPUT, ""),
            last_output=self._settings.value(SETTINGS_KEY_OUTPUT, ""),
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            if not self._input_folder:
                # User closed dialog on first run → exit
                QApplication.quit()
            return

        input_folder, output_folder = dlg.result_folders()
        if not input_folder or not output_folder:
            QMessageBox.warning(self, "Folders Required",
                                "Both Input and Output folders must be selected.")
            return

        self._input_folder  = input_folder
        self._output_folder = output_folder
        self._settings.setValue(SETTINGS_KEY_INPUT,  input_folder)
        self._settings.setValue(SETTINGS_KEY_OUTPUT, output_folder)
        self._form.set_output_root(output_folder)

        self._load_queue()
        self._update_toolbar_label()

    def _update_toolbar_label(self):
        in_short  = _shorten_path(self._input_folder,  40)
        out_short = _shorten_path(self._output_folder, 40)
        self._toolbar_label.setText(
            f"  Input: {in_short}   →   Output: {out_short}"
        )

    # ------------------------------------------------------------------ #
    #  Queue management                                                    #
    # ------------------------------------------------------------------ #
    def _load_queue(self):
        """Scans the input folder for PDF files and loads them into the queue."""
        try:
            all_files = sorted(
                str(p) for p in Path(self._input_folder).iterdir()
                if p.suffix.lower() == ".pdf"
            )
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Cannot read input folder:\n{e}")
            return

        self._queue = all_files
        self._done_count  = 0
        self._total_count = len(all_files)
        self._form.set_progress(0, self._total_count)

        if self._total_count == 0:
            QMessageBox.information(self, "No PDFs Found",
                                    "No PDF files were found in the selected input folder.")
            return

        self._load_next()

    def _load_next(self):
        """Loads the next PDF in the queue into the viewer."""
        self._attached_files.clear()
        self._viewer.clear_attached_docs()
        self._form.set_attached_info(0, 0, [])

        if not self._queue:
            self._show_all_done()
            return

        path = self._queue[0]
        self._current_file = path

        ok = self._viewer.load_pdf(path)
        if not ok:
            QMessageBox.warning(self, "Cannot Open File",
                                f"Failed to open:\n{os.path.basename(path)}\n\nSkipping it.")
            self._queue.pop(0)
            self._done_count += 1
            self._form.set_progress(self._done_count, self._total_count)
            self._load_next()
            return

        self.setWindowTitle(f"{APP_NAME} — {os.path.basename(path)}")
        self._form.reset_for_next()
        self._form.set_progress(self._done_count, self._total_count)

    def _show_all_done(self):
        self._viewer.close_document()
        self.setWindowTitle(f"{APP_NAME} — All Done!")
        dlg = _AllDoneDialog(self._done_count, self._output_folder, self)
        dlg.exec()

    # ------------------------------------------------------------------ #
    #  Save & Skip                                                         #
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  Add & Manage Attached Documents to Merge                          #
    # ------------------------------------------------------------------ #
    def _on_add_document(self):
        """Allows the user to select one or more PDF files from file manager to connect missing pages."""
        if not self._current_file:
            QMessageBox.information(self, "No Document Loaded", "Please load a document before adding/merging pages.")
            return

        start_dir = self._input_folder or os.path.dirname(self._current_file)
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add / Insert Document(s) to Connect Missing Pages",
            start_dir,
            "PDF Files (*.pdf)",
        )
        if not paths:
            return

        import pypdf
        added_any = False
        for path in paths:
            norm_path = os.path.abspath(path)
            if norm_path == os.path.abspath(self._current_file):
                QMessageBox.warning(self, "Already Loaded", "This file is already the current primary document.")
                continue
            if norm_path in [os.path.abspath(p) for p in self._attached_files]:
                continue

            try:
                reader = pypdf.PdfReader(norm_path)
                _ = len(reader.pages)
            except Exception as e:
                QMessageBox.warning(self, "Invalid PDF", f"Failed to read:\n{os.path.basename(norm_path)}\n\nError: {e}")
                continue

            self._attached_files.append(norm_path)
            added_any = True

        if added_any:
            self._refresh_viewer_with_attached()

    def _on_remove_attached_document(self, index: int):
        if 0 <= index < len(self._attached_files):
            self._attached_files.pop(index)
            self._refresh_viewer_with_attached()

    def _on_move_attached_document(self, index: int, delta: int):
        new_idx = index + delta
        if 0 <= index < len(self._attached_files) and 0 <= new_idx < len(self._attached_files):
            self._attached_files[index], self._attached_files[new_idx] = (
                self._attached_files[new_idx],
                self._attached_files[index],
            )
            self._refresh_viewer_with_attached()

    def _refresh_viewer_with_attached(self):
        if not self._current_file:
            return

        all_files = [self._current_file] + self._attached_files
        import pypdf
        doc_infos = []
        total_p = 0
        for p in all_files:
            try:
                cnt = len(pypdf.PdfReader(p).pages)
            except Exception:
                cnt = 1
            doc_infos.append({
                "path": p,
                "name": os.path.basename(p),
                "start_page": total_p,
                "page_count": cnt,
            })
            total_p += cnt

        ok = self._viewer.load_pdf_list(all_files)
        if not ok:
            QMessageBox.warning(self, "Preview Error", "Failed to merge preview pages in memory.")
            return

        self._viewer.update_attached_docs(doc_infos[0], doc_infos[1:])
        self._form.set_attached_info(
            attached_count=len(self._attached_files),
            total_pages=total_p,
            attached_names=[d["name"] for d in doc_infos[1:]]
        )

    def _on_save(self, meta: DocumentMetadata):
        if not self._current_file:
            return

        # Build destination
        book_folder = os.path.join(self._output_folder, meta.build_book_folder_name())
        filename    = meta.build_filename()
        dest_path   = os.path.join(book_folder, filename)

        # Check for duplicates
        if os.path.exists(dest_path):
            reply = QMessageBox.question(
                self,
                "File Already Exists",
                f"A file with this name already exists:\n\n{filename}\n\n"
                f"in: {book_folder}\n\n"
                "Do you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Close the document (buffer) cleanly
        self._viewer.close_document()

        # Create destination folder if needed
        os.makedirs(book_folder, exist_ok=True)

        if not self._attached_files:
            # Single document: move and rename as before
            try:
                shutil.move(self._current_file, dest_path)
            except OSError as e:
                QMessageBox.critical(self, "Move Failed",
                                     f"Could not move the file:\n{e}\n\n"
                                     "The original file has NOT been deleted.")
                self._viewer.load_pdf(self._current_file)
                return
        else:
            # Multiple documents: merge into a single PDF
            import pypdf
            all_files_to_merge = [self._current_file] + list(self._attached_files)
            tmp_dest = dest_path + ".merging.tmp"

            try:
                writer = pypdf.PdfWriter()
                for fpath in all_files_to_merge:
                    writer.append(fpath)
                with open(tmp_dest, "wb") as f_out:
                    writer.write(f_out)
                writer.close()

                if os.path.exists(dest_path):
                    os.remove(dest_path)
                os.replace(tmp_dest, dest_path)
            except Exception as e:
                if os.path.exists(tmp_dest):
                    try:
                        os.remove(tmp_dest)
                    except OSError:
                        pass
                QMessageBox.critical(self, "Merge Failed",
                                     f"Could not merge documents into destination:\n{e}\n\n"
                                     "Original files have NOT been deleted.")
                self._refresh_viewer_with_attached()
                return

            # Successfully written merged PDF!
            # 1. Delete primary file since it is now part of dest_path
            try:
                os.remove(self._current_file)
            except OSError:
                pass

            # 2. For attached files: if in input folder or queue, remove from queue and delete
            in_folder = os.path.normcase(os.path.abspath(self._input_folder)) if self._input_folder else ""
            for att_path in self._attached_files:
                att_norm = os.path.normcase(os.path.abspath(att_path))

                matched_in_queue = None
                for q_item in list(self._queue):
                    if os.path.normcase(os.path.abspath(q_item)) == att_norm:
                        matched_in_queue = q_item
                        break

                is_in_input = (in_folder and att_norm.startswith(in_folder)) or (matched_in_queue is not None)

                if matched_in_queue:
                    self._queue.remove(matched_in_queue)
                    self._done_count += 1

                if is_in_input:
                    try:
                        os.remove(att_path)
                    except OSError:
                        pass

        # Clear attached files state
        self._attached_files.clear()

        # Advance queue
        if self._queue and self._queue[0] == self._current_file:
            self._queue.pop(0)
        elif self._current_file in self._queue:
            self._queue.remove(self._current_file)

        self._done_count += 1
        self._current_file = None

        self._load_next()

    def _on_skip(self):
        """Moves the current file to the end of the queue."""
        if not self._queue:
            return
        self._attached_files.clear()
        self._viewer.clear_attached_docs()
        self._form.set_attached_info(0, 0, [])
        self._viewer.close_document()
        skipped = self._queue.pop(0)
        self._queue.append(skipped)
        self._load_next()

    # ------------------------------------------------------------------ #
    #  Close event                                                         #
    # ------------------------------------------------------------------ #
    def closeEvent(self, event):
        self._viewer.close_document()
        super().closeEvent(event)


# --------------------------------------------------------------------------- #
#  Helper dialogs                                                              #
# --------------------------------------------------------------------------- #

class _FolderPickerDialog(QDialog):
    """Dialog to pick Input and Output folders."""

    def __init__(self, last_input: str, last_output: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Folders")
        self.setModal(True)
        self.setMinimumWidth(500)
        self._input  = last_input
        self._output = last_output

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("📂  Choose Working Folders")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        # Input folder row
        in_row = QHBoxLayout()
        self._in_label = QLabel(f"Input folder:\n{self._input or '(not selected)'}")
        self._in_label.setObjectName("folderLabel")
        self._in_label.setWordWrap(True)
        self._in_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        in_btn = QPushButton("Browse…")
        in_btn.setObjectName("browseBtn")
        in_btn.clicked.connect(self._pick_input)
        in_row.addWidget(self._in_label)
        in_row.addWidget(in_btn)
        layout.addLayout(in_row)

        # Output folder row
        out_row = QHBoxLayout()
        self._out_label = QLabel(f"Output folder:\n{self._output or '(not selected)'}")
        self._out_label.setObjectName("folderLabel")
        self._out_label.setWordWrap(True)
        self._out_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        out_btn = QPushButton("Browse…")
        out_btn.setObjectName("browseBtn")
        out_btn.clicked.connect(self._pick_output)
        out_row.addWidget(self._out_label)
        out_row.addWidget(out_btn)
        layout.addLayout(out_row)

        # Buttons
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("✓  Confirm")
        ok_btn.setObjectName("btnSave")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btnSkip")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _pick_input(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Input Folder (unprocessed PDFs)",
            self._input or ""
        )
        if folder:
            self._input = folder
            self._in_label.setText(f"Input folder:\n{folder}")

    def _pick_output(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Root Folder",
            self._output or ""
        )
        if folder:
            self._output = folder
            self._out_label.setText(f"Output folder:\n{folder}")

    def result_folders(self):
        return self._input, self._output


class _AllDoneDialog(QDialog):
    """Celebration dialog shown when all files are processed."""

    def __init__(self, count: int, output_folder: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("All Done!")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 32, 32, 32)

        emoji = QLabel("🎉")
        emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji.setStyleSheet("font-size: 48px;")
        layout.addWidget(emoji)

        title = QLabel("All Done!")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        msg = QLabel(
            f"Successfully processed <b>{count}</b> document(s).<br><br>"
            f"Files saved to:<br><code>{output_folder}</code>"
        )
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("✓  Close")
        ok_btn.setObjectName("btnSave")
        ok_btn.clicked.connect(self.accept)
        open_btn = QPushButton("📂  Open Output Folder")
        open_btn.setObjectName("btnSkip")
        open_btn.clicked.connect(lambda: os.startfile(output_folder))
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(open_btn)
        layout.addLayout(btn_row)


# --------------------------------------------------------------------------- #
#  Utility                                                                     #
# --------------------------------------------------------------------------- #

def _shorten_path(path: str, max_len: int) -> str:
    if len(path) <= max_len:
        return path
    head, tail = os.path.split(path)
    return f"…{os.sep}{tail}" if tail else f"…{path[-max_len:]}"
