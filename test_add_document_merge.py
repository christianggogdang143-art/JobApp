import os, pytest, pypdf
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from pdf_viewer_widget import PdfViewerWidget
from form_panel_widget import FormPanelWidget
from main_window import MainWindow
from naming_logic import DocumentMetadata

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def _create_dummy_pdf(filepath, num_pages=1):
    w = pypdf.PdfWriter()
    for _ in range(num_pages):
        w.add_blank_page(width=300, height=400)
    with open(filepath, "wb") as f:
        w.write(f)
    w.close()

def test_pdf_viewer_multi_doc_load(qapp, tmp_path):
    viewer = PdfViewerWidget()
    pdf1 = str(tmp_path / "doc1.pdf")
    pdf2 = str(tmp_path / "doc2.pdf")
    _create_dummy_pdf(pdf1, 2)
    _create_dummy_pdf(pdf2, 3)

    assert viewer.load_pdf(pdf1) is True
    assert viewer._total_pages == 2

    assert viewer.load_pdf_list([pdf1, pdf2]) is True
    assert viewer._total_pages == 5

    viewer.jump_to_page(3)
    assert viewer._view.pageNavigator().currentPage() == 3

    p_info = {"name": "doc1.pdf", "start_page": 0, "page_count": 2}
    att = [{"name": "doc2.pdf", "start_page": 2, "page_count": 3}]
    viewer.update_attached_docs(p_info, att)
    assert not viewer._attached_bar.isHidden()

    viewer.clear_attached_docs()
    assert viewer._attached_bar.isHidden()
    viewer.close_document()

def test_form_panel_attached_info(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat)
    form = FormPanelWidget(settings)

    form.set_attached_info(0, 0, [])
    assert "Save && Next" in form._btn_save.text()

    form.set_attached_info(1, 3, ["doc2.pdf"])
    assert "Merge (3 pgs)" in form._btn_save.text()

    form.reset_for_next()
    assert "Save && Next" in form._btn_save.text()

def test_main_window_merge_save(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(MainWindow, "_choose_folders", lambda self: None)
    monkeypatch.setattr(MainWindow, "_show_all_done", lambda self: None)

    in_d = tmp_path / "input"
    out_d = tmp_path / "output"
    in_d.mkdir()
    out_d.mkdir()

    f1 = str(in_d / "f1.pdf")
    f2 = str(in_d / "f2.pdf")
    _create_dummy_pdf(f1, 1)
    _create_dummy_pdf(f2, 2)

    out_str = tmp_path / "outside"
    out_str.mkdir()
    f_ext = str(out_str / "ext-annex.pdf")
    _create_dummy_pdf(f_ext, 1)

    win = MainWindow()
    win._input_folder = str(in_d)
    win._output_folder = str(out_d)
    win._form.set_output_root(str(out_d))
    win._load_queue()

    assert len(win._queue) == 2
    assert win._current_file == f1

    win._attached_files = [f2, f_ext]
    win._refresh_viewer_with_attached()
    assert win._viewer._total_pages == 4

    meta = DocumentMetadata(
        doc_no="1",
        page_no="1",
        book_no="I",
        series="2026",
        doc_title="Contract",
        company_or_atty="ABC",
        borrower="John Doe",
    )

    win._on_save(meta)

    dest = out_d / "Book No. I" / meta.build_filename()
    assert dest.exists()

    reader = pypdf.PdfReader(str(dest))
    assert len(reader.pages) == 4

    assert not os.path.exists(f1)
    assert not os.path.exists(f2)
    assert os.path.exists(f_ext)
    assert len(win._queue) == 0

    win.close()