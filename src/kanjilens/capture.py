"""Screen capture with region selection and clipboard reading.

Supports three environments:
- WSL2: uses powershell.exe to talk to the Windows clipboard/snipping tool
- Native Linux: uses maim or ImageMagick import
- Native Windows: uses PowerShell directly
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


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

    On WSL/Windows: launches the Windows Snipping Tool.
    On native Linux: uses maim or ImageMagick import.
    """
    if _is_wsl():
        return _snip_via_powershell()
    return _capture_linux_region()


def capture_clipboard() -> Image.Image:
    """Read an image from the system clipboard.

    On WSL/Windows: reads from the Windows clipboard via PowerShell.
    On native Linux: not yet supported (use --screenshot instead).
    """
    if _is_wsl():
        return _read_clipboard_via_powershell()
    raise RuntimeError(
        "Clipboard capture on native Linux is not yet supported. "
        "Use --screenshot or pass an image file."
    )
