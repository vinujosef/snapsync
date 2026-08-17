from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from snapsync.duplicate import build_hash_index, calculate_hash, decide_destination


class DuplicateTests(unittest.TestCase):
    def test_build_hash_index_ignores_system_files(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media = root / "photo.jpg"
            media.write_bytes(b"media")
            (root / ".DS_Store").write_bytes(b"finder")
            reports = root / "_snapsync_reports"
            reports.mkdir()
            (reports / "duplicate_groups.csv").write_bytes(b"report")

            index = build_hash_index(root)

            self.assertEqual(len(index), 1)
            self.assertEqual(index[calculate_hash(media)], media)

    def test_duplicate_hash_is_skipped(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = root / "existing.jpg"
            source = root / "source.jpg"
            existing.write_bytes(b"same")
            source.write_bytes(b"same")
            hash_index = {calculate_hash(existing): existing}

            decision = decide_destination(calculate_hash(source), root / "target.jpg", hash_index)

            self.assertEqual(decision.action, "skip")
            self.assertIsNone(decision.destination)
            self.assertEqual(decision.duplicate_kind, "destination")

    def test_repeated_source_hash_is_skipped(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_source = root / "first.jpg"
            second_source = root / "second.jpg"
            first_source.write_bytes(b"same")
            second_source.write_bytes(b"same")
            file_hash = calculate_hash(second_source)

            decision = decide_destination(file_hash, root / "target.jpg", {}, {file_hash: first_source})

            self.assertEqual(decision.action, "skip")
            self.assertIsNone(decision.destination)
            self.assertEqual(decision.duplicate_kind, "source")

    def test_filename_collision_uses_collision_suffix_for_different_hash(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "2026-05-18_142211_Canon_a8f31c9e71d4.jpg"
            source = root / "source.jpg"
            target.write_bytes(b"existing")
            source.write_bytes(b"different")

            decision = decide_destination(calculate_hash(source), target, {})

            self.assertEqual(decision.action, "copy")
            self.assertTrue(decision.collision)
            self.assertEqual(
                decision.destination,
                root / "2026-05-18_142211_Canon_a8f31c9e71d4_collision-01.jpg",
            )


if __name__ == "__main__":
    unittest.main()
