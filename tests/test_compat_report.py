import tempfile
import unittest
from pathlib import Path

from scripts.compat_report import aggregate_hash, hash_scope, verify_snapshot


class TestCompatibilityReport(unittest.TestCase):
    def test_snapshot_detects_changed_added_and_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sql").mkdir()
            (root / "sql" / "one.sql").write_text("SELECT 1;\n", encoding="utf-8")
            (root / "sql" / "two.sql").write_text("SELECT 2;\n", encoding="utf-8")
            files = hash_scope(root, ["sql/**/*.sql"])
            snapshot = {
                "include": ["sql/**/*.sql"],
                "files": files,
                "aggregate_sha256": aggregate_hash(files),
            }

            self.assertEqual(verify_snapshot(root, snapshot), [])

            (root / "sql" / "one.sql").write_text("SELECT 10;\n", encoding="utf-8")
            (root / "sql" / "two.sql").unlink()
            (root / "sql" / "three.sql").write_text("SELECT 3;\n", encoding="utf-8")

            self.assertEqual(
                verify_snapshot(root, snapshot),
                [
                    "missing: sql/two.sql",
                    "unexpected: sql/three.sql",
                    "changed: sql/one.sql",
                ],
            )

    def test_aggregate_hash_is_path_sensitive_and_deterministic(self):
        files = {"b.sql": "00" * 32, "a.sql": "11" * 32}

        self.assertEqual(aggregate_hash(files), aggregate_hash(dict(reversed(list(files.items())))))
        self.assertNotEqual(
            aggregate_hash(files),
            aggregate_hash({"renamed.sql": files["a.sql"], "b.sql": files["b.sql"]}),
        )


if __name__ == "__main__":
    unittest.main()
