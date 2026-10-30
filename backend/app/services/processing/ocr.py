"""Tesseract OCR with light image pre-processing for low-quality scans."""
from __future__ import annotations

import logging
import numpy as np
import pytesseract
from PIL import Image, ImageOps, ImageFilter

log = logging.getLogger(__name__)


def _preprocess(img: Image.Image) -> Image.Image:
    # Grayscale, auto-contrast, slight sharpen, binarize via adaptive threshold
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g, cutoff=1)
    g = g.filter(ImageFilter.SHARPEN)

    arr = np.array(g)
    # Simple Otsu-ish threshold without cv2 dep
    try:
        import cv2  # type: ignore
        _, arr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    except Exception:
        thr = arr.mean()
        arr = (arr > thr).astype(np.uint8) * 255
    return Image.fromarray(arr)


def ocr_image(img: Image.Image, lang: str = "eng") -> str:
    try:
        pre = _preprocess(img)
        text = pytesseract.image_to_string(pre, lang=lang, config="--oem 3 --psm 6")
        if len(text.strip()) < 10:
            # retry with different page-seg mode
            text = pytesseract.image_to_string(pre, lang=lang, config="--oem 3 --psm 4")
        return text
    except Exception as e:
        log.warning("ocr error: %s", e)
        return ""
