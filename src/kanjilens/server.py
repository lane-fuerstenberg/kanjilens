"""Persistent OCR server that keeps the model loaded in memory."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

from kanjilens.config import Config, load_config
from kanjilens.pipeline import create_ocr_engine, load_image

DEFAULT_SOCKET = Path("/tmp/kanjilens.sock")


def serve(config: Config, socket_path: Path = DEFAULT_SOCKET) -> None:
    """Start the OCR server, listening on a Unix socket."""
    engine = create_ocr_engine(config)
    # Force model load now so first request is fast
    print("Loading OCR model...", flush=True)
    engine._load()
    print("Model ready.", flush=True)

    if socket_path.exists():
        socket_path.unlink()

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(socket_path))
    sock.listen(1)
    print(f"Listening on {socket_path}", flush=True)

    try:
        while True:
            conn, _ = sock.accept()
            try:
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk

                image_path = data.decode("utf-8").strip()
                if not image_path:
                    conn.sendall(b"")
                    continue

                image = load_image(Path(image_path))
                text = engine.recognize(image)
                conn.sendall(text.encode("utf-8"))
            except Exception as e:
                try:
                    conn.sendall(f"ERROR: {e}".encode("utf-8"))
                except OSError:
                    pass
                print(f"Error processing request: {e}", file=sys.stderr, flush=True)
            finally:
                conn.close()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        sock.close()
        if socket_path.exists():
            socket_path.unlink()


def ocr_via_server(image_path: Path, socket_path: Path = DEFAULT_SOCKET) -> str:
    """Send an image path to the running server and return the OCR text."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(socket_path))
    try:
        sock.sendall(str(image_path).encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8")
    finally:
        sock.close()
