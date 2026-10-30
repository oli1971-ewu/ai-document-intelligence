from __future__ import annotations

from PIL import Image

from .ocr import ocr_image


def extract_image(path: str) -> str:
    with Image.open(path) as img:
        img.load()
        return ocr_image(img)
