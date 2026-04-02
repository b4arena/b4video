"""Tests for the build manifest."""

from b4video.manifest import Manifest


class TestManifest:
    def test_roundtrip(self, tmp_path):
        m = Manifest()
        art = m.get_or_create("test-key", "test/path.mp3")
        art.mark_complete()

        m.save(tmp_path)
        loaded = Manifest.load(tmp_path)

        assert loaded.is_complete("test-key")
        assert loaded.artifacts["test-key"].path == "test/path.mp3"

    def test_failed_artifact(self, tmp_path):
        m = Manifest()
        art = m.get_or_create("test-key", "test/path.mp3")
        art.mark_failed("Something went wrong")

        m.save(tmp_path)
        loaded = Manifest.load(tmp_path)

        assert not loaded.is_complete("test-key")
        assert loaded.artifacts["test-key"].error == "Something went wrong"

    def test_empty_manifest(self, tmp_path):
        m = Manifest.load(tmp_path)
        assert not m.is_complete("nonexistent")

    def test_get_or_create_idempotent(self):
        m = Manifest()
        art1 = m.get_or_create("key", "path")
        art1.mark_complete()
        art2 = m.get_or_create("key", "path")
        assert art2.status == "complete"
