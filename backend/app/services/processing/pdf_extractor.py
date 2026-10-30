"""
PDF text extraction with automatic fallback to OCR when a page is scanned.

Strategy:
  1. Try pdfplumber for digital text.
  2. If total text is below a threshold OR a page has no text, render that
     page with PyMuPDF and OCR it with Tesseract.
  3. Returns (full_text, page_count, kind) where kind ∈ {'pdf_text','pdf_scanned'}.
"""
from __future__ import annotations

import io
import logging
from typing import Tuple

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except (ImportError, Exception):
    fitz = None  # type: ignore
    HAS_FITZ = False

from PIL import Image
from .ocr import ocr_image

log = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 40  # below this -> treat page as scanned


def extract_pdf(path: str) -> Tuple[str, int, str]:
    pages_text: list[str] = []
    page_count = 0
    scanned_pages = 0

    # Phase 1: digital text via pdfplumber
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(path) as pdf:
                page_count = len(pdf.pages)
                for p in pdf.pages:
                    try:
                        t = p.extract_text() or ""
                    except Exception as e:
                        log.warning("pdfplumber page err: %s", e)
                        t = ""
                    pages_text.append(t)
        except Exception as e:
            log.warning("pdfplumber open failed, will OCR entire file: %s", e)
            pages_text = []
            page_count = 0
    else:
        log.warning("pdfplumber not available, skipping digital text extraction")

    # Phase 2: OCR any weak pages using PyMuPDF
    if HAS_FITZ and fitz is not None:
        try:
            doc = fitz.open(path)
            if page_count == 0:
                page_count = doc.page_count
                pages_text = [""] * page_count

            for i in range(page_count):
                if len(pages_text[i].strip()) >= MIN_CHARS_PER_PAGE:
                    continue
                try:
                    page = doc.load_page(i)
                    pix = page.get_pixmap(dpi=250)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = ocr_image(img)
                    if ocr_text.strip():
                        pages_text[i] = ocr_text
                        scanned_pages += 1
                except Exception as e:
                    log.warning("OCR failed on page %d: %s", i, e)
            doc.close()
        except Exception as e:
            log.warning("PyMuPDF open failed: %s", e)
    else:
        log.warning("PyMuPDF not available — OCR fallback disabled")

    full_text = "\n\n".join(pages_text).strip()
    kind = "pdf_scanned" if scanned_pages >= max(1, page_count // 2) else "pdf_text"
    return full_text, page_count, kind

