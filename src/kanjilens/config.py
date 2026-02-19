"""Configuration loader for kanjilens."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


CONFIG_DIR = Path.home() / ".kanjilens"
CONFIG_PATH = CONFIG_DIR / "config.toml"


@dataclass
class OCRConfig:
    engine: str = "manga-ocr"
    google_vision_key: str = ""


@dataclass
class TranslationConfig:
    engine: str = "deepl"
    deepl_api_key: str = ""
    cache_enabled: bool = True


@dataclass
class AnkiConfig:
    host: str = "localhost"
    port: int = 8765
    deck: str = "Japanese::Kanjilens"
    note_type: str = "Kanjilens"


@dataclass
class WordsConfig:
    known_words_file: str = str(CONFIG_DIR / "known.json")
    auto_skip_particles: bool = True
    auto_skip_below: str = "N4"


@dataclass
class InputConfig:
    watch_dir: str = ""
    preprocess: bool = False


@dataclass
class Config:
    ocr: OCRConfig = field(default_factory=OCRConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    anki: AnkiConfig = field(default_factory=AnkiConfig)
    words: WordsConfig = field(default_factory=WordsConfig)
    input: InputConfig = field(default_factory=InputConfig)


def load_config(path: Path | None = None) -> Config:
    """Load config from TOML file, falling back to defaults."""
    path = path or CONFIG_PATH

    if not path.exists():
        return Config()

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    config = Config()

    if "ocr" in raw:
        config.ocr = OCRConfig(**raw["ocr"])
    if "translation" in raw:
        config.translation = TranslationConfig(**raw["translation"])
    if "anki" in raw:
        config.anki = AnkiConfig(**raw["anki"])
    if "words" in raw:
        config.words = WordsConfig(**raw["words"])
    if "input" in raw:
        config.input = InputConfig(**raw["input"])

    return config
