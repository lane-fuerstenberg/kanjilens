"""Shared data models for the kanjilens pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Token:
    surface: str
    reading: str
    base_form: str
    pos: str
    pos_detail: str = ""
    conjugation: str = ""


@dataclass
class WordInfo:
    token: Token
    definitions: list[str] = field(default_factory=list)
    jlpt_level: int | None = None
    kanji_info: list[dict] = field(default_factory=list)
    is_known: bool = False


@dataclass
class KanjilensCard:
    sentence: str
    sentence_reading: str = ""
    translation: str = ""
    target_word: str = ""
    target_reading: str = ""
    target_definition: str = ""
    word_breakdown: str = ""
    jlpt_level: str = ""
    source: str = ""
    image_base64: str = ""
