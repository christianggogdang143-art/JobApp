"""
Application entry point + global dark-mode styling.
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont, QFontDatabase

from main_window import MainWindow, APP_NAME, ORG_NAME


# ------------------------------------------------------------------ #
#  Premium dark theme stylesheet                                       #
# ------------------------------------------------------------------ #
STYLESHEET = """
/* ===========================
   Global reset & base
   =========================== */
QWidget {
    background-color: #0f1117;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}

/* ===========================
   Main window & splitter
   =========================== */
QMainWindow {
    background-color: #0f1117;
}

QSplitter::handle {
    background-color: #1e2433;
    width: 2px;
}

/* ===========================
   Toolbar (top main toolbar)
   =========================== */
QToolBar#mainToolbar {
    background-color: #161b27;
    border-bottom: 1px solid #2d3748;
    padding: 4px 8px;
    spacing: 6px;
}

QToolBar#mainToolbar QToolButton {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 13px;
}

QToolBar#mainToolbar QToolButton:hover {
    background-color: #1e2d48;
    border-color: #3b82f6;
    color: #e2e8f0;
}

QLabel#toolbarLabel {
    color: #64748b;
    font-size: 12px;
    padding-left: 6px;
}

/* ===========================
   PDF Viewer panel
   =========================== */
QWidget#viewerPanel {
    background-color: #0a0d14;
    border: none;
}

QWidget#viewerToolbar {
    background-color: #161b27;
    border-bottom: 1px solid #2d3748;
}

QToolButton#toolbarBtn {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid #2d3748;
    border-radius: 5px;
    padding: 4px 10px;
    min-width: 28px;
    font-size: 13px;
}

QToolButton#toolbarBtn:hover {
    background-color: #1e2d48;
    border-color: #3b82f6;
    color: #e2e8f0;
}

QToolButton#toolbarBtn:pressed {
    background-color: #1e3a5f;
}

QLabel#pageLabel {
    color: #94a3b8;
    background-color: #1e2433;
    border: 1px solid #2d3748;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#zoomLabel {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 600;
    padding-left: 2px;
}

QComboBox#zoomCombo {
    background-color: #161b27;
    color: #e2e8f0;
    border: 1px solid #2d3748;
    border-radius: 5px;
    padding: 2px 6px;
    min-width: 125px;
    font-size: 12px;
    font-weight: 600;
}

QComboBox#zoomCombo:hover {
    border-color: #3b82f6;
    background-color: #1e2433;
}

QComboBox#zoomCombo::drop-down {
    border: none;
    width: 18px;
}

QComboBox#zoomCombo::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #94a3b8;
    margin-right: 4px;
}

QComboBox#zoomCombo QAbstractItemView {
    background-color: #161b27;
    color: #e2e8f0;
    border: 1px solid #2d3748;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    padding: 4px;
}

QComboBox#zoomCombo QLineEdit {
    background: transparent;
    color: #e2e8f0;
    border: none;
    font-weight: 600;
    selection-background-color: #3b82f6;
}

QFrame#viewerSep {
    color: #2d3748;
    background-color: #2d3748;
    max-height: 1px;
}

/* QPdfView scroll area */
QPdfView {
    background-color: #0a0d14;
    border: none;
}

/* ===========================
   Form panel (right)
   =========================== */
QWidget#formPanel {
    background-color: #111827;
    border-left: 1px solid #1e2433;
}

QLabel#formHeader {
    background-color: #161b27;
    color: #f1f5f9;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #2d3748;
    padding-left: 4px;
}

QFrame#formSep {
    color: #1e2433;
    background-color: #1e2433;
    max-height: 1px;
}

QScrollArea#formScroll {
    background-color: transparent;
    border: none;
}

QWidget#formBody {
    background-color: transparent;
}

QLabel#fieldLabel {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-bottom: 2px;
}

QLineEdit#formField {
    background-color: #1e2433;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 8px 10px;
    color: #f1f5f9;
    font-size: 13px;
    selection-background-color: #3b82f6;
}

QLineEdit#formField:focus {
    border-color: #3b82f6;
    background-color: #1a2540;
    outline: none;
}

QLineEdit#formField:hover:!focus {
    border-color: #4b5563;
}

/* History dropdown button (▾ beside history fields) */
QToolButton#historyDropBtn {
    background-color: #1a2030;
    color: #64748b;
    border: 1px solid #2d3748;
    border-left: none;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    min-width: 26px;
    max-width: 26px;
    font-size: 13px;
    padding: 0px 4px;
}

QToolButton#historyDropBtn:hover {
    background-color: #253048;
    color: #3b82f6;
    border-color: #3b82f6;
}

QToolButton#historyDropBtn:pressed {
    background-color: #1e3a5f;
    color: #60a5fa;
}

/* History dropdown menu */
QMenu#historyMenu {
    background-color: #1a2030;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 4px 0px;
    min-width: 220px;
}

QMenu#historyMenu::item {
    color: #e2e8f0;
    padding: 7px 16px;
    font-size: 13px;
    border-radius: 4px;
}

QMenu#historyMenu::item:selected {
    background-color: #1e3a5f;
    color: #60a5fa;
}

QMenu#historyMenu::item:disabled {
    color: #4b5563;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
}

QMenu#historyMenu::separator {
    height: 1px;
    background-color: #2d3748;
    margin: 4px 8px;
}

/* QCompleter popup */
QListView {
    background-color: #1a2030;
    border: 1px solid #3b82f6;
    border-radius: 6px;
    color: #e2e8f0;
    font-size: 13px;
    padding: 2px;
    selection-background-color: #1e3a5f;
    selection-color: #60a5fa;
    outline: none;
}

/* ===========================
   Document Details Header Bar & Reset
   =========================== */
QWidget#formHeaderBar {
    background-color: #161b27;
    border-bottom: 1px solid #2d3748;
}

QLabel#formHeader {
    color: #f1f5f9;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.5px;
    border: none;
    background: transparent;
}

QPushButton#btnResetFieldOrder {
    background-color: #1e2433;
    color: #94a3b8;
    border: 1px solid #2d3748;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton#btnResetFieldOrder:hover {
    background-color: #1e2d48;
    border-color: #3b82f6;
    color: #e2e8f0;
}

QPushButton#btnResetFieldOrder:pressed {
    background-color: #1e3a5f;
    color: #ffffff;
}

/* ===========================
   Draggable field rows
   =========================== */
QWidget#fieldRowHeader {
    background-color: transparent;
}

QLabel#fieldDragHandle {
    color: #64748b;
    font-size: 13px;
    font-weight: bold;
    padding-right: 2px;
}

QLabel#fieldDragHandle:hover {
    color: #3b82f6;
}

QToolButton#fieldRowMoveBtn {
    background-color: transparent;
    color: #64748b;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 1px 4px;
    font-size: 9px;
    min-width: 14px;
    max-width: 16px;
}

QToolButton#fieldRowMoveBtn:hover {
    background-color: #1e2d48;
    border-color: #3b82f6;
    color: #60a5fa;
}

QToolButton#fieldRowMoveBtn:disabled {
    color: #334155;
    background-color: transparent;
    border-color: transparent;
}

/* ===========================
   Filename Preview
   =========================== */
QLabel#previewHeader {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

QFrame#previewFrame {
    background-color: #0f1723;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 2px;
}

QFrame#previewFrame[valid="true"] {
    border-color: #10b981;
    background-color: #0d1f17;
}

QLabel#previewLabel {
    color: #e2e8f0;
    font-size: 12px;
    line-height: 1.5;
}

QLabel#previewPathLabel {
    color: #64748b;
    font-size: 11px;
    margin-top: 4px;
}


/* ===========================
   Add Document & Connected Documents Strip
   =========================== */
QToolButton#toolbarBtnAddDoc {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #059669, stop:1 #047857);
    color: #ffffff;
    border: 1px solid #10b981;
    border-radius: 5px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
}

QToolButton#toolbarBtnAddDoc:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #10b981, stop:1 #059669);
    border-color: #34d399;
    color: #ffffff;
}

QToolButton#toolbarBtnAddDoc:pressed {
    background: #065f46;
}

QFrame#toolbarVLine {
    color: #2d3748;
    background-color: #2d3748;
    width: 1px;
    margin: 4px 4px;
}

QFrame#attachedDocsStrip {
    background-color: #111827;
    max-height: 38px;
    border-bottom: 1px solid #1e293b;
    padding: 2px 10px;
}

QLabel#attachedStripTitle {
    color: #38bdf8;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.3px;
}

QScrollArea#attachedScroll {
    background: transparent;
    border: none;
}

QWidget#chipsContainer {
    background: transparent;
}

QToolButton#btnStripAddMore {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px dashed #0284c7;
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QToolButton#btnStripAddMore:hover {
    background-color: #0369a1;
    color: #ffffff;
    border-color: #38bdf8;
}

QFrame#attachedChipPrimary {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 1px 4px;
}

QFrame#attachedChip {
    background-color: #132238;
    border: 1px solid #2563eb;
    border-radius: 6px;
    padding: 1px 4px;
}

QLabel#chipLabel {
    color: #f1f5f9;
    font-size: 11px;
    font-weight: 600;
}

QToolButton#btnChipView {
    background-color: #1e3a5f;
    color: #60a5fa;
    border: 1px solid #2563eb;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
    font-weight: 600;
}

QToolButton#btnChipView:hover {
    background-color: #2563eb;
    color: #ffffff;
}

QToolButton#btnChipMove {
    background: transparent;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 3px;
    padding: 1px 4px;
    font-size: 9px;
}

QToolButton#btnChipMove:hover {
    background-color: #334155;
    color: #f1f5f9;
}

QToolButton#btnChipMove:disabled {
    color: #475569;
    border-color: transparent;
}

QToolButton#btnChipRemove {
    background: transparent;
    color: #f87171;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 1px 5px;
    font-size: 11px;
    font-weight: bold;
}

QToolButton#btnChipRemove:hover {
    background-color: #7f1d1d;
    color: #fecaca;
    border-color: #ef4444;
}

/* ===========================
   Form Panel Merge Notification
   =========================== */
QFrame#mergedInfoCard {
    background-color: #0f172a;
    border: 1px dashed #334155;
    border-radius: 8px;
}

QFrame#mergedInfoCard[hasAttached="true"] {
    background-color: #0c1a2e;
    border: 1px solid #0284c7;
}

QLabel#mergedInfoLabel {
    color: #94a3b8;
    font-size: 12px;
    line-height: 1.4;
}

QPushButton#btnFormAddDoc {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px solid #0284c7;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#btnFormAddDoc:hover {
    background-color: #0369a1;
    color: #ffffff;
    border-color: #38bdf8;
}

QPushButton#btnFormAddDoc:pressed {
    background-color: #0284c7;
}

/* ===========================
   Buttons
   =========================== */
QPushButton#btnSave {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3b82f6, stop:1 #2563eb);
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.3px;
}

QPushButton#btnSave:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #60a5fa, stop:1 #3b82f6);
}

QPushButton#btnSave:pressed {
    background: #1d4ed8;
}

QPushButton#btnSave:disabled {
    background-color: #1e2433;
    color: #4b5563;
}

QPushButton#btnSkip {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid #2d3748;
    border-radius: 7px;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#btnSkip:hover {
    background-color: #1e2433;
    border-color: #4b5563;
    color: #e2e8f0;
}

QPushButton#btnSkip:pressed {
    background-color: #0f1723;
}

QPushButton#browseBtn {
    background-color: #1e2433;
    color: #94a3b8;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
}

QPushButton#browseBtn:hover {
    background-color: #253048;
    color: #e2e8f0;
    border-color: #3b82f6;
}

/* ===========================
   Progress area
   =========================== */
QWidget#progressWidget {
    background-color: #0f1117;
    border-top: 1px solid #1e2433;
}

QLabel#progressLabel {
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
}

QProgressBar#progressBar {
    background-color: #1e2433;
    border: none;
    border-radius: 4px;
    height: 8px;
}

QProgressBar#progressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b82f6, stop:1 #10b981);
    border-radius: 4px;
}

/* ===========================
   Dialogs
   =========================== */
QDialog {
    background-color: #111827;
}

QLabel#dialogTitle {
    color: #f1f5f9;
    font-size: 16px;
    font-weight: 700;
}

QLabel#folderLabel {
    color: #94a3b8;
    font-size: 12px;
    background-color: #1e2433;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 8px 10px;
}

/* ===========================
   Scrollbars
   =========================== */
QScrollBar:vertical {
    background: #0f1117;
    width: 8px;
    border: none;
}

QScrollBar::handle:vertical {
    background: #2d3748;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #4b5563;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #0f1117;
    height: 8px;
    border: none;
}

QScrollBar::handle:horizontal {
    background: #2d3748;
    border-radius: 4px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: #4b5563;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ===========================
   Message Boxes
   =========================== */
QMessageBox {
    background-color: #111827;
}

QMessageBox QPushButton {
    background-color: #1e2433;
    color: #e2e8f0;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 6px 18px;
    min-width: 80px;
}

QMessageBox QPushButton:hover {
    background-color: #253048;
    border-color: #3b82f6;
}
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")   # cross-platform; we override with our stylesheet
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
