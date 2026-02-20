# Portability: native Windows packaging

The current setup requires WSL to run the Python OCR pipeline, with a
PowerShell wrapper (`kanjilens.ps1`) bridging Windows screen capture to the
WSL-hosted Python process over a Unix socket. This works but has significant
friction: users need WSL installed, a Linux Python environment configured, and
the PowerShell script handles path translation, encoding, process management,
and health checks across the OS boundary.

This document captures what's needed to make kanjilens a self-contained Windows
application with no WSL dependency.

## Current architecture (WSL)

```
PowerShell (hotkey listener, clipboard, screen capture)
  --> wsl wslpath (path translation)
  --> wsl python3 (socket client)
  --> Unix socket
  --> kanjilens serve (WSL Python process, manga-ocr on GPU)
```

## Target architecture (native Windows)

```
Python (hotkey listener, clipboard, screen capture, OCR)
  --> single process, no IPC needed
```

## Requirements

### 1. Python on Windows with CUDA

manga-ocr depends on PyTorch. PyTorch has native Windows builds with CUDA
support, so this works today. The key dependency chain:

- Python 3.10+ (Windows installer or embedded distribution)
- PyTorch with CUDA (pip install from the PyTorch index)
- manga-ocr (pip install, pulls in transformers/huggingface)
- Pillow (already cross-platform)

No WSL-specific dependencies exist in the Python code itself.

### 2. Screen capture on Windows

Replace the current WSL/PowerShell capture flow with native Python screen
capture. Options:

- **mss** (pip): fast, lightweight, captures arbitrary screen regions. Does not
  provide a selection UI on its own.
- **PIL.ImageGrab** (bundled with Pillow): `ImageGrab.grab()` for full screen
  or `ImageGrab.grabclipboard()` for clipboard. No selection UI.
- **Windows Snipping Tool integration**: use `ctypes` or `subprocess` to invoke
  `ms-screenclip:` and poll the clipboard, same approach as the PowerShell
  script but from Python directly.

Recommended approach: keep the current snipping tool strategy (it provides the
selection UI for free) but do it from Python using `ctypes` to call Win32 APIs
for clipboard access, removing the PowerShell dependency.

### 3. Global hotkey registration

The PowerShell script currently uses P/Invoke for `RegisterHotKey`. The same
Win32 API is accessible from Python:

- **pynput** (pip): cross-platform hotkey listener, simple API
- **keyboard** (pip): global hotkey registration, requires admin on some setups
- **ctypes directly**: call `user32.RegisterHotKey` and run a `GetMessage` loop,
  same as the PowerShell script but in Python

Recommended: use `pynput` for simplicity, or raw `ctypes` to avoid the extra
dependency.

### 4. Clipboard access

Reading/writing the clipboard from Python on Windows:

- **pyperclip** (pip): text clipboard, cross-platform
- **Pillow's ImageGrab.grabclipboard()**: reads images from clipboard
- **win32clipboard** (pywin32): full clipboard API access
- **ctypes**: call Win32 clipboard APIs directly

For reading snipped images: `PIL.ImageGrab.grabclipboard()` is sufficient.
For writing OCR text: `pyperclip` or raw `ctypes` `SetClipboardData`.

### 5. Packaging and distribution

Options for creating a standalone Windows executable:

- **PyInstaller**: bundles Python + dependencies into a single .exe or folder.
  Works with PyTorch but produces large bundles (~1-2 GB with CUDA).
- **Nuitka**: compiles Python to C, can produce smaller bundles.
- **Embedded Python + pip**: ship Python embedded distribution with a
  `requirements.txt` and a launcher script. More transparent than PyInstaller.

Recommended: start with PyInstaller for simplicity. The large bundle size is
acceptable since manga-ocr already requires a ~300 MB model download.

### 6. System tray integration

A background Windows app should live in the system tray rather than a console
window:

- **pystray** (pip): cross-platform system tray icon with menu
- Provides start/stop, status indicator, and settings access

### 7. Overlay display (future)

The floating overlay was disabled due to difficulties with WinForms from
PowerShell. From native Python on Windows, options are simpler:

- **tkinter** (bundled): borderless topmost window, works well for overlays
- **PyQt/PySide**: heavier but more control over rendering
- **win32gui** (pywin32): raw Win32 window creation via ctypes

tkinter is the path of least resistance since it ships with Python.

## Migration plan

1. Add a `kanjilens.pyw` entry point (windowless Python on Windows) that
   replaces `kanjilens.ps1`:
   - Register global hotkey via pynput or ctypes
   - On hotkey: launch snipping tool, poll clipboard with
     `ImageGrab.grabclipboard()`, run OCR (model stays loaded in-process),
     copy result to clipboard
   - Run from system tray via pystray

2. The existing `kanjilens serve` / `server.py` socket architecture becomes
   unnecessary since everything runs in one process. The server module can
   remain for headless/remote use cases.

3. Package with PyInstaller into a single-folder distribution.

4. The existing Linux/WSL code paths in `capture.py` remain for Linux users.

## Dependencies for Windows-native build

```
pyperclip     # text clipboard
pystray       # system tray icon
pyinstaller   # packaging (dev dependency)
```

All other dependencies (manga-ocr, Pillow, PyTorch) already have Windows
wheels. Hotkey registration uses ctypes (no extra dependency).

## Building with PyInstaller

From a Windows machine with the venv activated:

```
pip install -e ".[dev,windows]"
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pyinstaller kanjilens.spec
```

This produces `dist/kanjilens/` with `kanjilens.exe` and all dependencies.
The folder will be large (~1-2 GB) due to PyTorch and CUDA libraries.

To run: double-click `kanjilens.exe`. It starts in the system tray and
listens for Ctrl+Shift+Z.
