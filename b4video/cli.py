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


@app.command()
def subtitles(
    video: str = typer.Argument(help="Path to rendered video or build directory"),
) -> None:
    """Regenerate SRT subtitles from timing data."""
    typer.echo(f"Regenerating subtitles for '{video}'...")
    # TODO: implement subtitle regeneration
