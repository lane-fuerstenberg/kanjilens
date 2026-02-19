"""OCR engine protocol."""

from __future__ import annotations

from typing import Protocol

from PIL import Image


class OCREngine(Protocol):
    def recognize(self, image: Image.Image) -> str: ...
