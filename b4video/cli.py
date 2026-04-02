"""CLI entry point for b4video."""

import typer

app = typer.Typer(
    name="b4video",
    help="Automated video production pipeline — script to YouTube.",
    no_args_is_help=True,
)

voices_app = typer.Typer(help="Manage ElevenLabs voice aliases.")
avatars_app = typer.Typer(help="Manage HeyGen avatar aliases.")
app.add_typer(voices_app, name="voices")
app.add_typer(avatars_app, name="avatars")


@app.command()
def render(
    script: str = typer.Argument(help="Path to the video script (.md)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and estimate cost only"),
    stage: str | None = typer.Option(None, "--stage", help="Run a single stage (parse/voice/visuals/compose/assemble)"),
    force: bool = typer.Option(False, "--force", help="Regenerate all artifacts"),
) -> None:
    """Render a video from a Markdown script."""
    from b4video.pipeline import run_pipeline

    run_pipeline(script, dry_run=dry_run, stage=stage, force=force)


@app.command()
def cost(
    script: str = typer.Argument(help="Path to the video script (.md)"),
) -> None:
    """Estimate rendering cost for a script."""
    from b4video.pipeline import estimate_cost

    estimate_cost(script)


@voices_app.command("list")
def voices_list() -> None:
    """Show configured voice aliases."""
    from b4video.config import load_config

    config = load_config()
    for alias, voice_id in config.voices.items():
        typer.echo(f"  {alias}: {voice_id}")


@voices_app.command("preview")
def voices_preview(alias: str = typer.Argument(help="Voice alias to preview")) -> None:
    """Generate a 10-second voice sample."""
    typer.echo(f"Generating preview for voice '{alias}'...")
    # TODO: implement ElevenLabs preview


@avatars_app.command("list")
def avatars_list() -> None:
    """Show configured avatar aliases."""
    from b4video.config import load_config

    config = load_config()
    for alias, avatar_id in config.avatars.items():
        typer.echo(f"  {alias}: {avatar_id}")


@avatars_app.command("preview")
def avatars_preview(alias: str = typer.Argument(help="Avatar alias to preview")) -> None:
    """Generate a 5-second avatar test clip."""
    typer.echo(f"Generating preview for avatar '{alias}'...")
    # TODO: implement HeyGen preview


templates_app = typer.Typer(help="Generate intro/outro template videos.")
app.add_typer(templates_app, name="templates")


@templates_app.command("intro")
def templates_intro(
    logo: str = typer.Argument(help="Path to logo image (PNG with transparency)"),
    output: str = typer.Option("assets/intro.mp4", "--output", "-o", help="Output path"),
    title: str = typer.Option("#B4arena", "--title", help="Title text"),
    subtitle: str = typer.Option("", "--subtitle", help="Subtitle text below title"),
) -> None:
    """Generate an intro template video."""
    from pathlib import Path

    from b4video.templates import generate_intro

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    generate_intro(Path(output), Path(logo), title=title, subtitle=subtitle)
    typer.echo(f"Intro generated: {output}")


@templates_app.command("outro")
def templates_outro(
    logo: str = typer.Argument(help="Path to logo image (PNG with transparency)"),
    output: str = typer.Option("assets/outro.mp4", "--output", "-o", help="Output path"),
    title: str = typer.Option("#B4arena", "--title", help="Brand title"),
    website: str = typer.Option("b4arena.com", "--website", help="Website text"),
    url: str = typer.Option("tabula.b4madservice.workers.dev", "--url", help="URL label under QR code"),
    cta: str = typer.Option("Subscribe for more", "--cta", help="Call-to-action text"),
    qr_code: str | None = typer.Option(None, "--qr", help="Path to QR code image (PNG)"),
) -> None:
    """Generate an outro template video."""
    from pathlib import Path

    from b4video.templates import generate_outro

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    qr_path = Path(qr_code) if qr_code else None
    generate_outro(
        Path(output), Path(logo),
        title=title, website=website, url=url, cta=cta, qr_code=qr_path,
    )
    typer.echo(f"Outro generated: {output}")


@app.command()
def subtitles(
    video: str = typer.Argument(help="Path to rendered video or build directory"),
) -> None:
    """Regenerate SRT subtitles from timing data."""
    typer.echo(f"Regenerating subtitles for '{video}'...")
    # TODO: implement subtitle regeneration
