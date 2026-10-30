"""
Unit tests for naming_logic.py
"""

import os
import pytest
from naming_logic import (
    DocumentMetadata,
    sanitize_filename_component,
    normalize_roman_numeral,
)


def test_user_example_exact_match():
    """
    User prompt specified:
    Example:
    Doc No. 14, Page No. 4, Book No. XVIII, Series of 2025, Security Agreement of AFC- Simeon E. and Crizza Mae Bernabe Berdin Sabaricos

    Strict formatting rules:
    - "Doc No.", "Page No.", "Book No." have periods
    - Commas separate the sections
    - Hyphen separates company and borrower: {CompanyOrAtty}- {Borrower}
    """
    meta = DocumentMetadata(
        doc_no="14",
        page_no="4",
        book_no="xviii",  # test lower case roman numeral conversion
        series="2025",
        doc_title="Security Agreement",
        company_or_atty="AFC",
        borrower="Simeon E. and Crizza Mae Bernabe Berdin Sabaricos",
    )
    assert meta.book_no == "xviii"
    assert meta.sanitized().book_no == "XVIII"

    expected_filename = (
        "Doc No. 14, Page No. 4, Book No. XVIII, Series of 2025, "
        "Security Agreement of AFC- Simeon E. and Crizza Mae Bernabe Berdin Sabaricos.pdf"
    )
    assert meta.build_filename() == expected_filename

    assert meta.build_book_folder_name() == "Book No. XVIII"

    target_path = meta.build_target_path("C:/Output")
    assert target_path == os.path.normpath(
        "C:/Output/Book No. XVIII/Doc No. 14, Page No. 4, Book No. XVIII, Series of 2025, "
        "Security Agreement of AFC- Simeon E. and Crizza Mae Bernabe Berdin Sabaricos.pdf"
    )


def test_sanitize_forbidden_characters():
    r"""
    Test conversion of Windows forbidden characters (\ / : * ? " < > |)
    to safe Unicode lookalikes so users can enter slashes, colons, etc.
    """
    raw_title = 'Promissory: Note / "Special" *2025? <Draft> | Final\\'
    cleaned = sanitize_filename_component(raw_title)
    assert cleaned == "Promissory∶ Note ∕ ”Special” ∗2025？ ‹Draft› │ Final⧵"

    meta = DocumentMetadata(
        doc_no="12/34:A",
        page_no="5*",
        book_no="v|i",
        series="2025?",
        doc_title='Deed of "Sale"',
        company_or_atty="Law & Co.<Ltd>",
        borrower="John Doe/Jane Doe",
    )
    s = meta.sanitized()
    assert s.doc_no == "12∕34∶A"
    assert s.page_no == "5∗"
    assert s.book_no == "V│I"
    assert s.series == "2025？"
    assert s.doc_title == "Deed of ”Sale”"
    assert s.company_or_atty == "Law & Co.‹Ltd›"
    assert s.borrower == "John Doe∕Jane Doe"


def test_validation_missing_fields():
    # Incomplete metadata
    meta = DocumentMetadata(
        doc_no="123",
        page_no="45",
        book_no="",
        series="2025",
        doc_title="Mortgage",
        company_or_atty="BDO",
        borrower="",
    )
    is_valid, err = meta.validate()
    assert not is_valid
    assert "Book No." in err
    assert "Borrower Name" in err

    # Complete metadata
    meta_complete = DocumentMetadata(
        doc_no="123",
        page_no="45",
        book_no="I",
        series="2025",
        doc_title="Mortgage",
        company_or_atty="BDO",
        borrower="Jane Smith",
    )
    is_valid, err = meta_complete.validate()
    assert is_valid
    assert err is None


def test_whitespace_handling():
    meta = DocumentMetadata(
        doc_no="  100  ",
        page_no="  20  ",
        book_no="  iv  ",
        series="  2024  ",
        doc_title="  Affidavit  ",
        company_or_atty="  Atty. Cruz  ",
        borrower="  Carlos Ray  ",
    )
    filename = meta.build_filename()
    expected = "Doc No. 100, Page No. 20, Book No. IV, Series of 2024, Affidavit of Atty. Cruz- Carlos Ray.pdf"
    assert filename == expected


def test_company_with_trailing_hyphen():
    meta = DocumentMetadata(
        doc_no="14",
        page_no="4",
        book_no="XVIII",
        series="2025",
        doc_title="Security Agreement",
        company_or_atty="AFC-",
        borrower="Simeon E. and Crizza Mae Bernabe Berdin Sabaricos",
    )
    expected = (
        "Doc No. 14, Page No. 4, Book No. XVIII, Series of 2025, "
        "Security Agreement of AFC- Simeon E. and Crizza Mae Bernabe Berdin Sabaricos.pdf"
    )
    assert meta.build_filename() == expected


def test_custom_sequence_book_no_first():
    """
    Scenario: Move Book No. to the first position.
    Sequence: Book No. -> Doc No. -> Page No. -> Series Of -> Doc Title -> Company / Atty -> Borrower Name
    """
    seq = ["book_no", "doc_no", "page_no", "series", "doc_title", "company_or_atty", "borrower"]
    meta = DocumentMetadata(
        doc_no="14",
        page_no="4",
        book_no="XVIII",
        series="2025",
        doc_title="Security Agreement",
        company_or_atty="AFC",
        borrower="Simeon E. and Crizza Mae Bernabe Berdin Sabaricos",
        sequence=seq,
    )
    expected = (
        "Book No. XVIII, Doc No. 14, Page No. 4, Series of 2025, "
        "Security Agreement of AFC- Simeon E. and Crizza Mae Bernabe Berdin Sabaricos.pdf"
    )
    assert meta.build_filename() == expected


def test_custom_sequence_page_no_third():
    """
    Scenario: Move Page No. to the third position.
    Sequence: Doc No. -> Book No. -> Page No. -> Series Of -> Doc Title -> Company / Atty -> Borrower Name
    """
    seq = ["doc_no", "book_no", "page_no", "series", "doc_title", "company_or_atty", "borrower"]
    meta = DocumentMetadata(
        doc_no="14",
        page_no="4",
        book_no="XVIII",
        series="2025",
        doc_title="Security Agreement",
        company_or_atty="AFC",
        borrower="Simeon E. and Crizza Mae Bernabe Berdin Sabaricos",
        sequence=seq,
    )
    expected = (
        "Doc No. 14, Book No. XVIII, Page No. 4, Series of 2025, "
        "Security Agreement of AFC- Simeon E. and Crizza Mae Bernabe Berdin Sabaricos.pdf"
    )
    assert meta.build_filename() == expected


def test_custom_sequence_doc_title_first():
    """
    Scenario: Move Doc Title to the first position before reference numbers.
    Sequence: Doc Title -> Company / Atty -> Borrower Name -> Book No. -> Doc No. -> Page No. -> Series Of
    """
    seq = ["doc_title", "company_or_atty", "borrower", "book_no", "doc_no", "page_no", "series"]
    meta = DocumentMetadata(
        doc_no="14",
        page_no="4",
        book_no="XVIII",
        series="2025",
        doc_title="Security Agreement",
        company_or_atty="AFC",
        borrower="Simeon E. and Crizza Mae Bernabe Berdin Sabaricos",
    )
    expected = (
        "Security Agreement of AFC- Simeon E. and Crizza Mae Bernabe Berdin Sabaricos, "
        "Book No. XVIII, Doc No. 14, Page No. 4, Series of 2025.pdf"
    )
    assert meta.build_filename(sequence=seq) == expected


def test_validate_sequence_fallback_on_invalid():
    """
    Tests that invalid, missing, or duplicate field sequences safely fall back to DEFAULT_SEQUENCE.
    """
    from naming_logic import validate_sequence, DEFAULT_SEQUENCE

    # Missing fields
    assert validate_sequence(["doc_no", "page_no"]) == DEFAULT_SEQUENCE

    # Duplicate fields
    assert validate_sequence(["doc_no", "doc_no", "page_no", "book_no", "series", "doc_title", "company_or_atty"]) == DEFAULT_SEQUENCE

    # Unknown field names
    assert validate_sequence(["unknown", "page_no", "book_no", "series", "doc_title", "company_or_atty", "borrower"]) == DEFAULT_SEQUENCE

    # None or non-list
    assert validate_sequence(None) == DEFAULT_SEQUENCE
    assert validate_sequence("not a list") == DEFAULT_SEQUENCE

