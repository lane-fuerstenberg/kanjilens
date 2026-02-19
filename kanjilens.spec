# PyInstaller spec file for kanjilens-gui
#
# Build with:
#   pyinstaller kanjilens.spec
#
# Produces: dist/kanjilens/kanjilens.exe (folder mode for faster startup)

import sys
from pathlib import Path
import importlib

block_cipher = None

# Collect data files that libraries need at runtime
extra_datas = []

# unidic_lite dictionary files (needed by fugashi tokenizer)
try:
    unidic_path = Path(importlib.import_module('unidic_lite').__file__).parent
    extra_datas.append((str(unidic_path / 'dicdir'), 'unidic_lite/dicdir'))
except ImportError:
    pass

# manga_ocr source files (transformers inspects source at runtime)
try:
    manga_ocr_path = Path(importlib.import_module('manga_ocr').__file__).parent
    extra_datas.append((str(manga_ocr_path), 'manga_ocr'))
except ImportError:
    pass

a = Analysis(
    ['src/kanjilens/gui.py'],
    pathex=[],
    binaries=[],
    datas=extra_datas,
    hiddenimports=[
        # manga-ocr pulls in transformers which has dynamic imports
        'manga_ocr',
        'transformers',
        'transformers.models.vision_encoder_decoder',
        'transformers.models.vit',
        'transformers.models.bert',
        'transformers.models.bert_japanese',
        'sentencepiece',
        'torch',
        'torchvision',
        # tokenizer dependencies
        'unidic_lite',
        'fugashi',
        'protobuf',
        # pystray backend on Windows
        'pystray._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch.utils.tensorboard',
        # unused ML libraries
        'tensorflow',
        'onnx',
        'onnxruntime',
        # unused GUI frameworks
        'tkinter',
        'PyQt5',
        'PyQt6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kanjilens',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowless -- runs in system tray
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='kanjilens',
)
