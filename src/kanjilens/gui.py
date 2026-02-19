"""Native Windows GUI entry point for kanjilens.

Runs as a system tray application with a global hotkey (Ctrl+Shift+Z).
On hotkey press: opens snipping tool, OCRs the capture, copies text
to clipboard. The OCR model stays loaded in memory for fast responses.

Usage:
    kanjilens-gui              # from command line
    pythonw -m kanjilens.gui   # windowless
"""

from __future__ import annotations

import sys
import threading

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
            return

        pyperclip.copy(text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)


def _create_tray_icon() -> bytes:
    """Generate a simple 64x64 tray icon (white K on dark background)."""
    from PIL import Image, ImageDraw, ImageFont
    import io

    img = Image.new("RGBA", (64, 64), (30, 30, 30, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "K", font=font)
    x = (64 - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (64 - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), "K", fill=(255, 255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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

    # Try to run as a system tray app, fall back to console loop
    try:
        import pystray
        from PIL import Image
        import io

        icon_bytes = _create_tray_icon()
        icon_image = Image.open(io.BytesIO(icon_bytes))

        def on_quit(icon: pystray.Icon, item: pystray.MenuItem) -> None:
            listener.stop()
            icon.stop()

        icon = pystray.Icon(
            "kanjilens",
            icon_image,
            "kanjilens - Ctrl+Shift+Z to OCR",
            menu=pystray.Menu(
                pystray.MenuItem("Ctrl+Shift+Z to snip and OCR", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", on_quit),
            ),
        )

        icon.run()
    except ImportError:
        # pystray not installed, fall back to console
        import time

        print(f"kanjilens is running. Press {hotkey} to snip and OCR.", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            listener.stop()


if __name__ == "__main__":
    main()
