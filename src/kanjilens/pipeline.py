"""Pipeline orchestrator for the kanjilens flow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from kanjilens.config import Config
from kanjilens.ocr.manga import MangaOCREngine


def create_ocr_engine(config: Config) -> MangaOCREngine:
    if config.ocr.engine == "manga-ocr":
        return MangaOCREngine()
    raise ValueError(f"Unknown OCR engine: {config.ocr.engine}")


def load_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def recognize(image: Image.Image, config: Config) -> str:
    """Run OCR on a PIL Image and return the recognized text."""
    engine = create_ocr_engine(config)
    return engine.recognize(image)


def run_ocr(image_path: Path, config: Config) -> str:
    """Run OCR on an image file and return the recognized text."""
    image = load_image(image_path)
    return recognize(image, config)
