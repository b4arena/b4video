"""Pipeline orchestrator — runs stages in sequence with idempotency."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from b4video.config import load_config
from b4video.manifest import Manifest
from b4video.parser import parse_script, write_scenes_json

console = Console()

STAGES = ("parse", "voice", "visuals", "compose", "assemble")


def run_pipeline(
    script_path: str,
    *,
    dry_run: bool = False,
    stage: str | None = None,
    force: bool = False,
) -> None:
    """Run the full rendering pipeline or a single stage."""
    if stage and stage not in STAGES:
        console.print(f"[red]Unknown stage '{stage}'. Valid: {', '.join(STAGES)}[/red]")
        raise typer.Exit(1)

    config = load_config()
    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)

    manifest = Manifest.load(build_dir) if not force else Manifest()

    # Stage 1: Parse
    if _should_run("parse", stage):
        console.print("[bold blue]Stage 1/5: Parse[/bold blue]")
        meta, scenes = parse_script(script_path)
        write_scenes_json(meta, scenes, build_dir)
        console.print(f"  Parsed {len(scenes)} scenes from {script_path}")
    else:
        # Need meta/scenes for later stages even if not re-parsing
        meta, scenes = parse_script(script_path)

    if dry_run:
        _print_cost_estimate(meta, scenes)
        return

    # Stage 2: Voice
    if _should_run("voice", stage):
        console.print("[bold blue]Stage 2/5: Voice (ElevenLabs)[/bold blue]")
        from b4video.voice import generate_voice
        generate_voice(meta, scenes, build_dir, manifest, config, force=force)
        console.print("  Audio generated for all scenes")

    # Stage 3: Visuals
    if _should_run("visuals", stage):
        console.print("[bold blue]Stage 3/5: Visuals (HeyGen + Showboat)[/bold blue]")
        from b4video.visuals import generate_visuals
        generate_visuals(meta, scenes, build_dir, manifest, config, force=force)
        console.print("  Visual assets generated")

    # Stage 4: Compose
    if _should_run("compose", stage):
        console.print("[bold blue]Stage 4/5: Compose[/bold blue]")
        from b4video.compose import compose_scenes
        compose_scenes(meta, scenes, build_dir, manifest, force=force)
        console.print("  Scenes composed")

    # Stage 5: Assemble
    if _should_run("assemble", stage):
        console.print("[bold blue]Stage 5/5: Assemble[/bold blue]")
        from b4video.assemble import assemble_video
        final = assemble_video(meta, scenes, build_dir, manifest, force=force)
        console.print(f"  [bold green]Done![/bold green] Output: {final}")

    manifest.save(build_dir)


def estimate_cost(script_path: str) -> None:
    """Parse script and print cost estimate."""
    meta, scenes = parse_script(script_path)
    _print_cost_estimate(meta, scenes)


def _print_cost_estimate(meta, scenes) -> None:
    """Print estimated cost breakdown."""
    total_chars = sum(len(s.narration) for s in scenes)
    presenter_count = sum(1 for s in scenes if s.scene_type == "presenter")
    demo_count = sum(1 for s in scenes if s.scene_type == "demo")

    # ElevenLabs: roughly $0.30 per 1000 characters (Scale plan)
    voice_cost = (total_chars / 1000) * 0.30

    # HeyGen: roughly $3-5 per minute of avatar video
    # Estimate ~1 min per scene for presenter, ~30s for demo PiP
    avatar_minutes = presenter_count * 1.0 + demo_count * 0.5
    avatar_cost = avatar_minutes * 4.0  # ~$4/min average

    total = voice_cost + avatar_cost

    console.print()
    console.print("[bold]Cost Estimate[/bold]")
    console.print(f"  Scenes: {len(scenes)} ({presenter_count} presenter, {demo_count} demo)")
    console.print(f"  Narration: {total_chars:,} characters (~{total_chars // 5:,} words)")
    console.print(f"  ElevenLabs: ~${voice_cost:.2f}")
    console.print(f"  HeyGen:     ~${avatar_cost:.2f}")
    console.print(f"  [bold]Total:      ~${total:.2f}[/bold]")
    console.print()


def _should_run(current: str, target: str | None) -> bool:
    """Check if a stage should run given the --stage filter."""
    return target is None or target == current
