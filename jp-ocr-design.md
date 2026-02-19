# Kanjilens — Japanese OCR Learning Pipeline

## Overview

Kanjilens is a CLI-first tool that extracts Japanese text from images (manga, screenshots, game captures, signs) via OCR, processes it into structured linguistic data, and generates Anki flashcards automatically. The goal is to close the loop between encountering Japanese in the wild and having it in your SRS system with minimal friction.

## Goals

- Screenshot/image → Anki card in under 10 seconds
- Rich card data: sentence, reading, word-level breakdowns, translation
- Works offline where possible (OCR + segmentation local, translation API optional)
- Desktop-first MVP, designed for future mobile expansion
- Minimal dependencies, easy to install and run

## Non-Goals (MVP)

- Mobile app
- Live screen recording / overlay
- Browser extension
- GUI (CLI + optional TUI is fine)
- Custom SRS implementation (leverage Anki)

---

## Architecture

```
┌─────────────┐
│  Image Input │  clipboard, file path, screenshot hotkey
└──────┬──────┘
       │
       ▼
┌─────────────┐
│     OCR      │  manga-ocr (local, PyTorch)
└──────┬──────┘
       │  raw Japanese text
       ▼
┌──────────────┐
│ Segmentation │  fugashi (MeCab wrapper)
└──────┬───────┘
       │  tokens: surface, reading, POS, base form
       ▼
┌──────────────┐
│   Lookup     │  jamdict (JMDict/KanjiDic2)
└──────┬───────┘
       │  definitions, kanji info, JLPT level
       ▼
┌──────────────┐
│ Translation  │  DeepL API Free (full sentence)
└──────┬───────┘
       │  EN translation
       ▼
┌──────────────┐
│ Card Builder │  assemble fields, format HTML
└──────┬───────┘
       │  structured card payload
       ▼
┌──────────────┐
│  AnkiConnect │  REST API → create note
└──────────────┘
```

---

## Components

### 1. Image Input

**Modes:**
- `kanjilens <image_path>` — process a file
- `kanjilens --clipboard` — grab from clipboard (PIL ImageGrab)
- `kanjilens --watch <dir>` — monitor a directory for new screenshots
- `kanjilens --interactive` — REPL mode, paste/type paths repeatedly

**Libraries:** `Pillow`, `watchdog` (for directory monitoring)

**Preprocessing:** Convert to grayscale, resize if needed, optional binarization for low-contrast images. Keep preprocessing minimal — manga-ocr handles most cases well without it.

### 2. OCR Engine

**Primary:** [manga-ocr](https://github.com/kha-white/manga-ocr)
- Local PyTorch model, no API costs
- Excellent on manga, game text, stylized fonts
- Works on general Japanese text too
- ~300MB model download on first run

**Fallback (config option):** Google Cloud Vision API
- Better for handwriting, photos of real-world signs
- 1000 units/month free tier
- Requires API key configuration

**Interface:**
```python
class OCREngine(Protocol):
    def recognize(self, image: PIL.Image) -> str: ...
```

### 3. Text Segmentation

**Library:** `fugashi` (MeCab Python wrapper with UniDic)

**Output per token:**
```python
@dataclass
class Token:
    surface: str        # 食べた
    reading: str        # タベタ
    base_form: str      # 食べる
    pos: str            # 動詞
    pos_detail: str     # 一般
    conjugation: str    # 連用形
```

**Furigana generation:** Convert katakana readings to hiragana, pair with kanji segments for display.

### 4. Dictionary Lookup

**Library:** `jamdict` (wraps JMDict + KanjiDic2 + Krad)

**Per-token enrichment:**
```python
@dataclass
class WordInfo:
    token: Token
    definitions: list[str]      # English glosses
    jlpt_level: int | None      # N5-N1 (if available)
    kanji_info: list[KanjiInfo] # per-kanji breakdown
    is_known: bool              # cross-ref with user's known words
```

**Known word tracking:** Simple SQLite database or flat JSON file mapping base forms to "known" status. Words marked known get skipped or de-emphasized on cards. This enables filtering: only generate cards for unknown words.

### 5. Translation

**Primary:** DeepL API Free
- 500k chars/month, plenty for personal use
- Official Python SDK: `deepl`
- JP→EN quality is strong

**Fallback:** None for MVP. Could add Claude API later for grammar explanations.

**Caching:** SQLite cache keyed on source text hash. Avoids redundant API calls for repeated sentences (common in manga with recurring phrases).

### 6. Card Builder

**Anki note type:** `Kanjilens` (auto-created if missing)

**Fields:**

| Field | Content | Example |
|-------|---------|---------|
| Sentence | Full Japanese sentence | 今日は天気がいいですね |
| SentenceReading | With furigana HTML | 今日[きょう]は天気[てんき]がいいですね |
| Translation | DeepL EN translation | The weather is nice today, isn't it? |
| TargetWord | Focus word (base form) | 天気 |
| TargetReading | Reading of target word | てんき |
| TargetDefinition | Top definitions | weather; weather forecast |
| WordBreakdown | All tokens with readings/POS | JSON or formatted HTML |
| JLPTLevel | If known | N4 |
| Source | Where it came from | manga/screenshot/filename |
| Image | Original image thumbnail | `<img>` tag with base64 |

**Card templates:** Ship default front/back HTML+CSS templates. Front shows sentence with target word highlighted. Back reveals reading, definition, translation, and full breakdown.

**One sentence → multiple cards:** If a sentence has multiple unknown words, generate one card per unknown word with that word as the target. Tag them with the same sentence ID so the user can relate them.

### 7. AnkiConnect Integration

**Dependency:** [AnkiConnect](https://ankiweb.net/shared/info/2055492159) plugin installed in Anki desktop.

**Operations:**
- `createModel` — ensure Kanjilens note type exists
- `addNote` — create a card with all fields populated
- `findNotes` — check for duplicates before adding
- `storeMediaFile` — upload source image

**Client:**
```python
class AnkiClient:
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.url = f"http://{host}:{port}"

    def invoke(self, action: str, **params) -> Any:
        # POST JSON to AnkiConnect
        ...

    def add_card(self, card: KanjilensCard) -> int:
        # Dedup check, then addNote
        ...
```

---

## Data Flow Example

**Input:** Screenshot of manga panel containing 「俺はまだ本気を出していない」

**Pipeline:**

1. **OCR** → `"俺はまだ本気を出していない"`
2. **Segmentation** →

| Surface | Reading | Base | POS |
|---------|---------|------|-----|
| 俺 | オレ | 俺 | 代名詞 |
| は | ハ | は | 助詞 |
| まだ | マダ | まだ | 副詞 |
| 本気 | ホンキ | 本気 | 名詞 |
| を | ヲ | を | 助詞 |
| 出して | ダシテ | 出す | 動詞 |
| いない | イナイ | いる | 動詞 |

3. **Lookup** → definitions for 俺, 本気, 出す, etc. Cross-ref known words.
4. **Translation** → "I haven't gotten serious yet."
5. **Card generation** → Cards for each unknown word (e.g., 本気 if unknown)
6. **AnkiConnect** → Card appears in Anki, ready for review

---

## Configuration

`~/.kanjilens/config.toml`

```toml
[ocr]
engine = "manga-ocr"              # or "google-vision"
google_vision_key = ""            # if using google

[translation]
engine = "deepl"
deepl_api_key = ""                # free tier key
cache_enabled = true

[anki]
host = "localhost"
port = 8765
deck = "Japanese::Kanjilens"
note_type = "Kanjilens"

[words]
known_words_file = "~/.kanjilens/known.json"
auto_skip_particles = true        # don't card は, が, を, etc.
auto_skip_below = "N4"            # skip words at or below this JLPT level

[input]
watch_dir = ""                    # optional screenshot watch directory
preprocess = false                # image preprocessing toggle
```

---

## Project Structure

```
kanjilens/
├── pyproject.toml
├── README.md
├── src/
│   └── kanjilens/
│       ├── __init__.py
│       ├── cli.py              # Click CLI entrypoint
│       ├── pipeline.py         # Orchestrates the full flow
│       ├── ocr/
│       │   ├── __init__.py
│       │   ├── base.py         # OCREngine protocol
│       │   ├── manga.py        # manga-ocr wrapper
│       │   └── google.py       # Google Vision wrapper
│       ├── nlp/
│       │   ├── __init__.py
│       │   ├── segmenter.py    # fugashi/MeCab tokenization
│       │   └── lookup.py       # jamdict dictionary lookup
│       ├── translation/
│       │   ├── __init__.py
│       │   ├── deepl.py        # DeepL client with caching
│       │   └── cache.py        # SQLite translation cache
│       ├── anki/
│       │   ├── __init__.py
│       │   ├── client.py       # AnkiConnect REST client
│       │   ├── models.py       # Note type / card template definitions
│       │   └── builder.py      # Card field assembly
│       ├── models.py           # Shared dataclasses (Token, WordInfo, Card)
│       └── config.py           # TOML config loader
├── templates/
│   ├── front.html              # Anki card front template
│   └── back.html               # Anki card back template
└── tests/
    ├── test_pipeline.py
    ├── test_segmenter.py
    └── fixtures/
        └── sample_manga.png
```

---

## Dependencies

```
manga-ocr          # OCR engine (~300MB model)
fugashi[unidic]    # MeCab tokenizer + UniDic dictionary
jamdict             # JMDict/KanjiDic2 Python API
deepl               # Official DeepL SDK
Pillow              # Image handling
click               # CLI framework
toml                # Config parsing
watchdog            # Directory monitoring (optional)
```

**System dependencies:** None beyond Python 3.10+. MeCab is bundled via fugashi. UniDic downloads on first run.

---

## MVP Milestones

### M0 — Skeleton (Day 1)
- Project scaffolding, config loader, CLI entrypoint
- `kanjilens <image>` prints OCR'd text to stdout

### M1 — Pipeline Core (Days 2-3)
- Segmentation + dictionary lookup working
- Rich terminal output: sentence with readings, definitions, POS

### M2 — Anki Integration (Days 4-5)
- AnkiConnect client
- Note type auto-creation
- Card generation from pipeline output
- Duplicate detection

### M3 — Translation + Polish (Days 6-7)
- DeepL integration with caching
- Known word tracking (skip list)
- Clipboard mode
- Config file support

### M4 — Quality of Life (Week 2)
- Watch directory mode
- Image thumbnail on cards
- Card template styling
- JLPT level filtering
- Batch processing (folder of images)

---

## Future Considerations (Post-MVP)

- **Mobile:** Kotlin Android app with screen capture → calls Python backend (local or remote)
- **Browser extension:** Intercept images on web pages, right-click → Kanjilens
- **Grammar notes:** Claude API integration for per-sentence grammar explanations
- **Sentence difficulty scoring:** Estimate sentence complexity for study ordering
- **Kanji stroke order:** Embed stroke order diagrams on kanji-focused cards
- **Export formats:** CSV, TSV for non-Anki SRS tools
- **TUI:** Rich-based interactive terminal UI for reviewing/editing cards before adding
