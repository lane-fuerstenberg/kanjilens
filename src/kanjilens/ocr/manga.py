"""manga-ocr wrapper."""

from __future__ import annotations

from PIL import Image


class MangaOCREngine:
    def __init__(self) -> None:
        self._ocr: object | None = None

    def _load(self) -> None:
        """Lazy-load the model so startup stays fast when OCR isn't needed."""
        if self._ocr is not None:
            return
        from manga_ocr import MangaOcr

        self._ocr = MangaOcr()

    def recognize(self, image: Image.Image) -> str:
        self._load()
        return self._ocr(image)  # type: ignore[misc]
