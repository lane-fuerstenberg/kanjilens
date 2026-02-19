"""Native Windows GUI entry point for kanjilens.

Runs as a background process with a global hotkey (Ctrl+Shift+Z).
On hotkey press: opens snipping tool, OCRs the capture, copies text
to clipboard. The OCR model stays loaded in memory for fast responses.

Usage:
    kanjilens-gui          # from command line
    pythonw kanjilens/gui.py   # windowless
"""

from __future__ import annotations

import sys
import time

import pyperclip

from kanjilens.capture import capture_region
from kanjilens.config import load_config
from kanjilens.pipeline import create_ocr_engine


def _on_hotkey(engine: object) -> None:
    """Called when the global hotkey is pressed."""
    try:
        img = capture_region()
        text = engine.recognize(img)

        if not text or not text.strip():
            print("OCR returned no text.", flush=True)
            return

        pyperclip.copy(text)
        print(text, flush=True)
    except RuntimeError as e:
        print(f"Capture error: {e}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)


def main() -> None:
    """Entry point for the native Windows kanjilens GUI."""
    from kanjilens.hotkey import HotkeyListener

    config = load_config()

    print("Loading OCR model...", flush=True)
    engine = create_ocr_engine(config)
    engine._load()
    print("Model ready.", flush=True)

    hotkey = "ctrl+shift+z"
    listener = HotkeyListener(hotkey, lambda: _on_hotkey(engine))
    listener.start()

    print(f"kanjilens is running. Press {hotkey} to snip and OCR.", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
