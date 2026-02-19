"""CLI entrypoint for kanjilens."""

from __future__ import annotations

from pathlib import Path

import click

from kanjilens.config import load_config


@click.group(invoke_without_command=True)
@click.option("--image", "-i", type=click.Path(exists=True, path_type=Path), help="Image file to OCR.")
@click.option("--screenshot", "-s", is_flag=True, help="Open region selector and OCR the capture.")
@click.option("--clipboard", "-c", is_flag=True, help="OCR an image from the clipboard (use after Win+Shift+S).")
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None, help="Path to config file.")
@click.pass_context
def main(ctx: click.Context, image: Path | None, screenshot: bool, clipboard: bool, config_path: Path | None) -> None:
    """Kanjilens - Japanese OCR to Anki flashcard pipeline."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config_path)

    if ctx.invoked_subcommand is not None:
        return

    config = ctx.obj["config"]

    if screenshot:
        from kanjilens.capture import capture_region
        from kanjilens.pipeline import recognize

        click.echo("Opening region selector...")
        img = capture_region()
        text = recognize(img, config)
        click.echo(text)
    elif clipboard:
        from kanjilens.capture import capture_clipboard
        from kanjilens.pipeline import recognize

        img = capture_clipboard()
        text = recognize(img, config)
        click.echo(text)
    elif image is not None:
        # If the server is running, use it for faster OCR
        from kanjilens.server import DEFAULT_SOCKET

        if DEFAULT_SOCKET.exists():
            from kanjilens.server import ocr_via_server

            text = ocr_via_server(image)
        else:
            from kanjilens.pipeline import run_ocr

            text = run_ocr(image, config)
        click.echo(text)
    else:
        click.echo(ctx.get_help())


@main.command()
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start persistent OCR server (keeps model loaded in memory)."""
    from kanjilens.server import serve as run_server

    run_server(ctx.obj["config"])
