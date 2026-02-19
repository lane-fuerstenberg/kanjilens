"""Screen capture with region selection and clipboard reading.

Supports three environments:
- Native Windows: uses ms-screenclip: URI and PIL.ImageGrab
- WSL2: uses powershell.exe to talk to the Windows clipboard/snipping tool
- Native Linux: uses maim or ImageMagick import
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image


def _is_windows() -> bool:
    return sys.platform == "win32"


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def _powershell_cmd() -> str:
    """Return the right PowerShell executable for the environment."""
    # WSL has powershell.exe on PATH via Windows interop
    for name in ("powershell.exe", "powershell"):
        if shutil.which(name):
            return name
    raise RuntimeError("PowerShell not found")


def _wsl_to_windows_path(posix_path: Path) -> str:
    """Convert a WSL path to a Windows path via wslpath."""
    result = subprocess.run(
        ["wslpath", "-w", str(posix_path)],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


# -- Windows / WSL clipboard helpers ------------------------------------------


def _read_clipboard_via_powershell() -> Image.Image:
    """Read an image from the Windows clipboard using PowerShell."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    if _is_wsl():
        win_path = _wsl_to_windows_path(tmp_path)
    else:
        win_path = str(tmp_path)

    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$img = [System.Windows.Forms.Clipboard]::GetImage(); "
        "if ($img -eq $null) { exit 1 } "
        f"$img.Save('{win_path}')"
    )

    try:
        result = subprocess.run(
            [_powershell_cmd(), "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "No image in clipboard. Copy an image first (Win+Shift+S)."
            )
        return Image.open(tmp_path).convert("RGB")
    finally:
        tmp_path.unlink(missing_ok=True)


def _snip_via_powershell() -> Image.Image:
    """Launch Windows Snipping Tool, wait for the user, read from clipboard."""
    ps_cmd = _powershell_cmd()

    # Clear clipboard, launch snip overlay, wait for it to finish
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Clipboard]::Clear(); "
        "Start-Process snippingtool '/clip' -Wait"
    )
    subprocess.run(
        [ps_cmd, "-NoProfile", "-Command", ps_script],
        capture_output=True,
    )

    return _read_clipboard_via_powershell()


# -- Native Windows capture (no PowerShell needed) ----------------------------


def _read_clipboard_image() -> Image.Image | None:
    """Read an image from the Windows clipboard using PIL."""
    from PIL import ImageGrab

    return ImageGrab.grabclipboard()


def _clear_clipboard_win32() -> None:
    """Clear the Windows clipboard using ctypes."""
    import ctypes
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.OpenClipboard(None)
    user32.EmptyClipboard()
    user32.CloseClipboard()


def _snip_native_windows() -> Image.Image:
    """Launch Windows Snipping Tool and wait for the image to land on clipboard."""
    _clear_clipboard_win32()

    os.startfile("ms-screenclip:")  # type: ignore[attr-defined]

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        time.sleep(0.3)
        img = _read_clipboard_image()
        if img is not None:
            return img.convert("RGB")

    raise RuntimeError("No snip captured (timed out or cancelled).")


def _read_clipboard_native_windows() -> Image.Image:
    """Read an image already on the Windows clipboard."""
    img = _read_clipboard_image()
    if img is None:
        raise RuntimeError(
            "No image in clipboard. Copy an image first (Win+Shift+S)."
        )
    return img.convert("RGB")


# -- Native Linux capture tools -----------------------------------------------


def _find_linux_capture_tool() -> str:
    for tool in ("maim", "import"):
        if shutil.which(tool):
            return tool
    raise RuntimeError(
        "No screen capture tool found. Install maim (recommended) or imagemagick."
    )


def _capture_maim(output_path: Path) -> None:
    result = subprocess.run(
        ["maim", "--select", str(output_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode().strip()
        raise RuntimeError(f"maim failed: {stderr or 'selection cancelled'}")


def _capture_import(output_path: Path) -> None:
    result = subprocess.run(
        ["import", str(output_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode().strip()
        raise RuntimeError(f"import failed: {stderr or 'selection cancelled'}")


_LINUX_CAPTURE = {
    "maim": _capture_maim,
    "import": _capture_import,
}


def _capture_linux_region() -> Image.Image:
    tool = _find_linux_capture_tool()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        _LINUX_CAPTURE[tool](tmp_path)
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            raise RuntimeError("Capture produced no output -- selection cancelled?")
        return Image.open(tmp_path).convert("RGB")
    finally:
        tmp_path.unlink(missing_ok=True)


# -- Public API ----------------------------------------------------------------


def capture_region() -> Image.Image:
    """Open a region selector and return the captured image.

    On native Windows: launches ms-screenclip and reads clipboard via PIL.
    On WSL: launches the Windows Snipping Tool via PowerShell.
    On native Linux: uses maim or ImageMagick import.
    """
    if _is_windows():
        return _snip_native_windows()
    if _is_wsl():
        return _snip_via_powershell()
    return _capture_linux_region()


def capture_clipboard() -> Image.Image:
    """Read an image from the system clipboard.

    On native Windows: reads via PIL.ImageGrab.
    On WSL: reads from the Windows clipboard via PowerShell.
    On native Linux: not yet supported (use --screenshot instead).
    """
    if _is_windows():
        return _read_clipboard_native_windows()
    if _is_wsl():
        return _read_clipboard_via_powershell()
    raise RuntimeError(
        "Clipboard capture on native Linux is not yet supported. "
        "Use --screenshot or pass an image file."
    )
