"""
Core naming and path generation logic for PDF Document Naming Tool.
Strict format compliance:
Doc No. {DocNo}, Page No. {PageNo}, Book No. {BookNo}, Series of {Series}, {DocTitle} of {CompanyOrAtty}- {Borrower}.pdf
"""

import os
import re
from dataclasses import dataclass
from typing import Optional, Tuple


# Forbidden Windows filename characters: \ / : * ? " < > |
FORBIDDEN_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|]')

# Mapping of Windows-forbidden characters to safe Unicode lookalikes
# so that users can enter slashes and other symbols without crashing Windows filesystem calls.
SAFE_CHAR_MAP = {
    '/': '∕',   # Division slash (U+2215)
    '\\': '⧵',  # Reverse solidus operator (U+29F5)
    ':': '∶',   # Ratio (U+2236)
    '*': '∗',   # Asterisk operator (U+2217)
    '?': '？',  # Fullwidth question mark (U+FF1F)
    '"': '”',   # Right double quotation mark (U+201D)
    '<': '‹',   # Single left-pointing angle quotation mark (U+2039)
    '>': '›',   # Single right-pointing angle quotation mark (U+203A)
    '|': '│',   # Box drawings light vertical (U+2502)
}


def replace_forbidden_chars(text: str) -> str:
    """Replaces Windows-forbidden characters with safe Unicode lookalikes."""
    if not text:
        return ""
    for char, replacement in SAFE_CHAR_MAP.items():
        text = text.replace(char, replacement)
    return text


def sanitize_filename_component(text: str) -> str:
    r"""
    Converts forbidden Windows filename characters to safe lookalikes:
    e.g., / -> ∕, \ -> ⧵, : -> ∶, * -> ∗, ? -> ？, " -> ”, < -> ‹, > -> ›, | -> │
    and strips outer whitespace while collapsing multiple spaces.
    """
    if text is None:
        return ""
    # Map forbidden characters to safe lookalike equivalents
    text = replace_forbidden_chars(text)
    # Strip any remaining invalid characters (e.g., control characters)
    cleaned = FORBIDDEN_CHARS_PATTERN.sub("", text)
    # Strip whitespace
    cleaned = cleaned.strip()
    return cleaned


def normalize_roman_numeral(text: str) -> str:
    """
    Normalizes Book No. input to uppercase (standard Roman numeral convention),
    while preserving Arabic numerals if provided.
    """
    return sanitize_filename_component(text).upper()


from dataclasses import dataclass, field
from typing import Optional, Tuple, List


# Standard default order of the 7 metadata fields
DEFAULT_SEQUENCE: List[str] = [
    "doc_no",
    "page_no",
    "book_no",
    "series",
    "doc_title",
    "company_or_atty",
    "borrower",
]

# Field metadata definitions for UI sequence builder
FIELD_DEFINITIONS = {
    "doc_no": {
        "id": "doc_no",
        "label": "Doc No.",
        "short_label": "Doc No.",
    },
    "page_no": {
        "id": "page_no",
        "label": "Page No.",
        "short_label": "Page No.",
    },
    "book_no": {
        "id": "book_no",
        "label": "Book No.",
        "short_label": "Book No.",
    },
    "series": {
        "id": "series",
        "label": "Series Of",
        "short_label": "Series",
    },
    "doc_title": {
        "id": "doc_title",
        "label": "Doc Title",
        "short_label": "Doc Title",
    },
    "company_or_atty": {
        "id": "company_or_atty",
        "label": "Company / Atty",
        "short_label": "Company",
    },
    "borrower": {
        "id": "borrower",
        "label": "Borrower Name",
        "short_label": "Borrower",
    },
}


def validate_sequence(seq: Optional[List[str]]) -> List[str]:
    """
    Ensures that a sequence contains exactly the 7 required fields,
    with no duplicates and no missing fields. If invalid, returns DEFAULT_SEQUENCE.
    """
    if not isinstance(seq, (list, tuple)):
        return list(DEFAULT_SEQUENCE)
    cleaned = [str(item).strip() for item in seq]
    if len(cleaned) != len(DEFAULT_SEQUENCE) or set(cleaned) != set(DEFAULT_SEQUENCE):
        return list(DEFAULT_SEQUENCE)
    return cleaned


@dataclass
class DocumentMetadata:
    doc_no: str
    page_no: str
    book_no: str
    series: str
    doc_title: str
    company_or_atty: str
    borrower: str
    sequence: Optional[List[str]] = None

    def sanitized(self) -> "DocumentMetadata":
        return DocumentMetadata(
            doc_no=sanitize_filename_component(self.doc_no),
            page_no=sanitize_filename_component(self.page_no),
            book_no=normalize_roman_numeral(self.book_no),
            series=sanitize_filename_component(self.series),
            doc_title=sanitize_filename_component(self.doc_title),
            company_or_atty=sanitize_filename_component(self.company_or_atty),
            borrower=sanitize_filename_component(self.borrower),
            sequence=validate_sequence(self.sequence) if self.sequence else None,
        )

    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validates whether all 7 required fields are non-empty after sanitization.
        Returns (is_valid, error_message).
        """
        s = self.sanitized()
        fields = [
            ("Doc No.", s.doc_no),
            ("Page No.", s.page_no),
            ("Book No.", s.book_no),
            ("Series of", s.series),
            ("Doc Title", s.doc_title),
            ("Company or Atty", s.company_or_atty),
            ("Borrower Name", s.borrower),
        ]
        missing = [label for label, val in fields if not val]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
        return True, None

    def build_filename(self, sequence: Optional[List[str]] = None) -> str:
        """
        Constructs the filename dynamically according to the specified sequence
        (or self.sequence, or DEFAULT_SEQUENCE).

        Connector conventions:
        - If doc_title is immediately followed by company_or_atty: joined with ' of '
        - If company_or_atty is immediately followed by borrower: joined with '- ' (or ' ' if ends with '-')
        - All other transitions are joined with ', ' (comma space)
        """
        s = self.sanitized()
        seq = validate_sequence(sequence or self.sequence or DEFAULT_SEQUENCE)

        company = s.company_or_atty.rstrip()
        if company.endswith("-"):
            comp_to_borrower_sep = " "
        else:
            comp_to_borrower_sep = "- "

        def get_field_text(field_id: str) -> str:
            if field_id == "doc_no":
                return f"Doc No. {s.doc_no}"
            elif field_id == "page_no":
                return f"Page No. {s.page_no}"
            elif field_id == "book_no":
                return f"Book No. {s.book_no}"
            elif field_id == "series":
                return f"Series of {s.series}"
            elif field_id == "doc_title":
                return s.doc_title
            elif field_id == "company_or_atty":
                return company
            elif field_id == "borrower":
                return s.borrower
            return ""

        parts = []
        for i, field_id in enumerate(seq):
            val = get_field_text(field_id)
            parts.append(val)
            if i < len(seq) - 1:
                next_id = seq[i + 1]
                if field_id == "doc_title" and next_id == "company_or_atty":
                    parts.append(" of ")
                elif field_id == "company_or_atty" and next_id == "borrower":
                    parts.append(comp_to_borrower_sep)
                else:
                    parts.append(", ")

        return "".join(parts) + ".pdf"

    def build_book_folder_name(self) -> str:
        """
        Constructs the Book folder name:
        Book No. {BookNo}
        """
        s = self.sanitized()
        return f"Book No. {s.book_no}"

    def build_target_path(self, output_root: str, sequence: Optional[List[str]] = None) -> str:
        """
        Constructs the full target destination path:
        {output_root}/Book No. {BookNo}/{filename}
        """
        folder_name = self.build_book_folder_name()
        filename = self.build_filename(sequence=sequence)
        return os.path.normpath(os.path.join(output_root, folder_name, filename))
