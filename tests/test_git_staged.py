import subprocess
import tempfile
import unittest
from pathlib import Path

from mir.engine.config import Config
from mir.engine.git_staged import read_staged_documents, update_staged_documents
from mir.engine.runner import process_document
from mir.engine.selection import expand_selection


class TestGitStaged(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.git("init", "-q")
        self.git("config", "user.name", "MIR Test")
        self.git("config", "user.email", "mir@example.invalid")

    def tearDown(self):
        self.temp_dir.cleanup()

    def git(self, *args: str, input_text: str | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            input=input_text,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def config(self) -> Config:
        config = Config()
        config.fix = True
        config.profile = "commit"
        return config

    def test_partial_staging_preserves_unstaged_line(self):
        path = self.root / "queries.sql"
        path.write_text("select item_id from sample_items;\n", encoding="utf-8")
        self.git("add", "queries.sql")
        path.write_text(
            "select item_id from sample_items;\n-- unstaged developer note\n",
            encoding="utf-8",
        )

        document = read_staged_documents(self.root, {".sql"})[0]
        selection = expand_selection(document.content, "sql", document.changed_lines)
        result = process_document(self.config(), document.content, document.path, "sql", selection)
        warnings = update_staged_documents(self.root, [(document, result.content)])

        self.assertEqual(warnings, [])
        self.assertEqual(
            self.git("show", ":queries.sql"),
            "SELECT item_id FROM sample_items;\n",
        )
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "SELECT item_id FROM sample_items;\n-- unstaged developer note\n",
        )

    def test_overlapping_unstaged_edit_stays_in_worktree(self):
        path = self.root / "queries.sql"
        path.write_text("SELECT item_id FROM sample_items;\n", encoding="utf-8")
        self.git("add", "queries.sql")
        self.git("commit", "-qm", "initial")
        path.write_text("select item_id from sample_items;\n", encoding="utf-8")
        self.git("add", "queries.sql")
        path.write_text("select item_name from sample_items;\n", encoding="utf-8")

        document = read_staged_documents(self.root, {".sql"})[0]
        result = process_document(
            self.config(),
            document.content,
            document.path,
            "sql",
            expand_selection(document.content, "sql", document.changed_lines),
        )
        warnings = update_staged_documents(self.root, [(document, result.content)])

        self.assertEqual(len(warnings), 1)
        self.assertEqual(self.git("show", ":queries.sql"), "SELECT item_id FROM sample_items;\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "select item_name from sample_items;\n")

    def test_selection_expands_only_intersecting_statement(self):
        content = "select first_id from first_table;\nselect second_id from second_table;\n"
        selection = expand_selection(content, "sql", {1})
        self.assertIn(1, selection.allowed)
        self.assertNotIn(2, selection.allowed)


if __name__ == "__main__":
    unittest.main()
