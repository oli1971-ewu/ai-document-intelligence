"""
Document processing pipeline.

Routes a file to the correct extractor based on content-type / extension,
returning raw text + a structured per-sheet payload where applicable.
Handles corrupted files gracefully (returns success=False with error).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from .pdf_extractor import extract_pdf
from .image_extractor import extract_image
from .spreadsheet_extractor import extract_spreadsheet, extract_csv

log = logging.getLogger(__name__)

PDF_EXT = {".pdf"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
XLSX_EXT = {".xlsx", ".xlsm"}
XLS_EXT = {".xls"}
CSV_EXT = {".csv"}


@dataclass
class DocumentProcessingResult:
    success: bool
    doc_type: str                 # pdf_text | pdf_scanned | image | xlsx | xls | csv | unknown
    text: str = ""
    page_count: int | None = None
    structured: dict[str, Any] = field(default_factory=dict)   # e.g. {"sheets": {...}}
    error: str | None = None


def _ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def process_document(path: str, filename: str | None = None) -> DocumentProcessingResult:
    name = filename or os.path.basename(path)
    ext = _ext(name)

    if not os.path.exists(path):
        return DocumentProcessingResult(
            success=False, doc_type="unknown", error=f"File not found: {path}"
        )

    try:
        if ext in PDF_EXT:
            text, pages, kind = extract_pdf(path)
            return DocumentProcessingResult(
                success=True, doc_type=kind, text=text, page_count=pages
            )

        if ext in IMG_EXT:
            text = extract_image(path)
            return DocumentProcessingResult(success=True, doc_type="image", text=text, page_count=1)

        if ext in XLSX_EXT or ext in XLS_EXT:
            text, sheets = extract_spreadsheet(path, engine="openpyxl" if ext in XLSX_EXT else "xlrd")
            return DocumentProcessingResult(
                success=True,
                doc_type="xlsx" if ext in XLSX_EXT else "xls",
                text=text,
                structured={"sheets": sheets},
            )

        if ext in CSV_EXT:
            text, rows = extract_csv(path)
            return DocumentProcessingResult(
                success=True, doc_type="csv", text=text, structured={"rows": rows}
            )

        return DocumentProcessingResult(
            success=False, doc_type="unknown", error=f"Unsupported file type: {ext}"
        )

    except Exception as e:  # pragma: no cover - broad on purpose for corrupted files
        log.exception("processing failed for %s", name)
        return DocumentProcessingResult(
            success=False, doc_type="unknown", error=f"{type(e).__name__}: {e}"
        )
