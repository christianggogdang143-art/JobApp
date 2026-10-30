"""
Unit and integration tests for draggable Document Details fields and sequence persistence.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

from naming_logic import DEFAULT_SEQUENCE
from form_panel_widget import FormPanelWidget, DraggableFieldRow, DraggableFieldsContainer

# Ensure single QApplication instance across tests
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def temp_settings():
    settings = QSettings("JobAppTest", "FieldDragTest")
    settings.clear()
    yield settings
    settings.clear()


def test_form_fields_default_sequence(qapp, temp_settings):
    form = FormPanelWidget(temp_settings)
    assert form.current_sequence() == DEFAULT_SEQUENCE
    assert form._fields_container._layout.count() == 7


def test_form_fields_move_up_and_down(qapp, temp_settings):
    form = FormPanelWidget(temp_settings)

    # Initial order: doc_no (0), page_no (1), book_no (2)...
    assert form.current_sequence()[0] == "doc_no"
    assert form.current_sequence()[1] == "page_no"

    # Move page_no (index 1) UP (-1) -> should become index 0
    form._fields_container.move_field_delta("page_no", -1)
    assert form.current_sequence()[0] == "page_no"
    assert form.current_sequence()[1] == "doc_no"

    # Move page_no DOWN (+1) -> back to index 1
    form._fields_container.move_field_delta("page_no", 1)
    assert form.current_sequence()[0] == "doc_no"
    assert form.current_sequence()[1] == "page_no"


def test_form_fields_drop_reorder(qapp, temp_settings):
    form = FormPanelWidget(temp_settings)

    # Drag book_no to position 0 (first)
    form._fields_container._move_field_to("book_no", 0)
    seq = form.current_sequence()
    assert seq[0] == "book_no"
    assert seq[1] == "doc_no"
    assert seq[2] == "page_no"
    assert len(seq) == 7


def test_form_fields_reset_order(qapp, temp_settings):
    form = FormPanelWidget(temp_settings)

    # Reorder
    form._fields_container._move_field_to("borrower", 0)
    assert form.current_sequence()[0] == "borrower"

    # Reset
    form._reset_field_order()
    assert form.current_sequence() == DEFAULT_SEQUENCE


def test_form_fields_persistence(qapp, temp_settings):
    form1 = FormPanelWidget(temp_settings)
    form1._fields_container._move_field_to("book_no", 0)
    custom_seq = form1.current_sequence()
    assert custom_seq[0] == "book_no"

    # New form instance using same settings should restore the custom field sequence
    form2 = FormPanelWidget(temp_settings)
    assert form2.current_sequence() == custom_seq
    assert form2.current_sequence()[0] == "book_no"


def test_form_panel_preview_updates_on_field_reorder(qapp, temp_settings):
    form = FormPanelWidget(temp_settings)
    form._f_doc_no.setText("14")
    form._f_page_no.setText("4")
    form._f_book_no.setText("XVIII")
    form._f_series.setText("2025")
    form._f_doc_title.setText("Security Agreement")
    form._f_company.setText("AFC")
    form._f_borrower.setText("Simeon E. and Crizza Mae Bernabe Berdin Sabaricos")

    # Form preview with default sequence
    assert "Doc No. 14, Page No. 4, Book No. XVIII" in form._preview_label.text()

    # Move Book No. to the first position
    form._fields_container._move_field_to("book_no", 0)

    # Live preview label updates immediately
    assert form._preview_label.text().startswith("📄 Book No. XVIII, Doc No. 14, Page No. 4")

    # current_metadata() reflects the new sequence
    meta = form.current_metadata()
    assert meta.sequence[0] == "book_no"
    assert meta.build_filename().startswith("Book No. XVIII, Doc No. 14, Page No. 4")
