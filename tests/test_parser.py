"""Tests for the script parser."""

from pathlib import Path
from textwrap import dedent

import pytest

from b4video.parser import Scene, SceneMeta, parse_script


@pytest.fixture
def script_dir(tmp_path):
    return tmp_path


def _write_script(path: Path, content: str) -> Path:
    script = path / "test_script.md"
    script.write_text(dedent(content).lstrip())
    return script


class TestParseScript:
    def test_basic_presenter_scene(self, script_dir):
        script = _write_script(script_dir, """
            ---
            title: "Test Video"
            ---

            ## Intro
            <!-- type: presenter -->
            Hello, welcome to the test.
        """)
        meta, scenes = parse_script(script)

        assert meta.title == "Test Video"
        assert meta.voice == "b4arena-default"
        assert meta.resolution == "1920x1080"
        assert len(scenes) == 1
        assert scenes[0].heading == "Intro"
        assert scenes[0].scene_type == "presenter"
        assert "Hello, welcome" in scenes[0].narration

    def test_demo_scene_with_showboat(self, script_dir):
        demo_script = script_dir / "demo.sh"
        demo_script.write_text("#!/bin/bash\necho hello")

        script = _write_script(script_dir, f"""
            ---
            title: "Demo Test"
            ---

            ## Feature
            <!-- type: demo -->
            <!-- showboat: {demo_script} -->
            Watch the feature in action.
        """)
        meta, scenes = parse_script(script)

        assert len(scenes) == 1
        assert scenes[0].scene_type == "demo"
        assert scenes[0].showboat_script == str(demo_script)

    def test_pip_alias_becomes_demo(self, script_dir):
        demo_script = script_dir / "demo.sh"
        demo_script.write_text("#!/bin/bash\necho hello")

        script = _write_script(script_dir, f"""
            ---
            title: "PiP Test"
            ---

            ## Feature
            <!-- type: pip -->
            <!-- showboat: {demo_script} -->
            Watch it.
        """)
        _, scenes = parse_script(script)
        assert scenes[0].scene_type == "demo"

    def test_multiple_scenes(self, script_dir):
        script = _write_script(script_dir, """
            ---
            title: "Multi"
            ---

            ## Intro
            <!-- type: presenter -->
            Welcome.

            ## Middle
            <!-- type: presenter -->
            The middle part.

            ## Outro
            <!-- type: presenter -->
            Goodbye.
        """)
        _, scenes = parse_script(script)
        assert len(scenes) == 3
        assert [s.heading for s in scenes] == ["Intro", "Middle", "Outro"]

    def test_custom_frontmatter(self, script_dir):
        script = _write_script(script_dir, """
            ---
            title: "Custom"
            voice: my-voice
            avatar: my-avatar
            resolution: 3840x2160
            fps: 60
            ---

            ## Scene
            <!-- type: presenter -->
            Content.
        """)
        meta, _ = parse_script(script)
        assert meta.voice == "my-voice"
        assert meta.avatar == "my-avatar"
        assert meta.resolution == "3840x2160"
        assert meta.fps == 60

    def test_missing_title_raises(self, script_dir):
        script = _write_script(script_dir, """
            ---
            voice: test
            ---

            ## Scene
            <!-- type: presenter -->
            Hello.
        """)
        with pytest.raises(ValueError, match="title"):
            parse_script(script)

    def test_missing_frontmatter_raises(self, script_dir):
        script = _write_script(script_dir, """
            ## Scene
            <!-- type: presenter -->
            No frontmatter here.
        """)
        with pytest.raises(ValueError, match="frontmatter"):
            parse_script(script)

    def test_unknown_scene_type_raises(self, script_dir):
        script = _write_script(script_dir, """
            ---
            title: "Bad Type"
            ---

            ## Scene
            <!-- type: unknown -->
            Content.
        """)
        with pytest.raises(ValueError, match="unknown type"):
            parse_script(script)

    def test_demo_without_showboat_raises(self, script_dir):
        script = _write_script(script_dir, """
            ---
            title: "Missing Showboat"
            ---

            ## Scene
            <!-- type: demo -->
            Content without showboat reference.
        """)
        with pytest.raises(ValueError, match="showboat"):
            parse_script(script)

    def test_empty_narration_raises(self, script_dir):
        script = _write_script(script_dir, """
            ---
            title: "Empty"
            ---

            ## Scene
            <!-- type: presenter -->
        """)
        with pytest.raises(ValueError, match="no narration"):
            parse_script(script)

    def test_narration_strips_html_comments(self, script_dir):
        script = _write_script(script_dir, """
            ---
            title: "Comments"
            ---

            ## Scene
            <!-- type: presenter -->
            <!-- some other comment -->
            The actual narration text.
        """)
        _, scenes = parse_script(script)
        assert scenes[0].narration == "The actual narration text."
