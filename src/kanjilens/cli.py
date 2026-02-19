"""CLI entrypoint for kanjilens."""

from __future__ import annotations

from pathlib import Path

import click

from kanjilens.config import load_config


@click.group(invoke_without_command=True)
@click.argument("image", required=False, type=click.Path(exists=True, path_type=Path))
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
        from kanjilens.pipeline import run_ocr

        text = run_ocr(image, config)
        click.echo(text)
    else:
        click.echo(ctx.get_help())
