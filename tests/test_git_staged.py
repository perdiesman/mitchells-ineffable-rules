import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mir.engine.config import Config
from mir.engine.git_staged import read_staged_documents, update_staged_documents
from mir.engine.runner import process_document, run_linter
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

    def test_staged_fix_leaves_existing_out_of_scope_violation_untouched(self):
        path = self.root / "queries.sql"
        path.write_text(
            "select legacy_id from legacy_table;\nSELECT item_id FROM sample_table;\n",
            encoding="utf-8",
        )
        self.git("add", "queries.sql")
        self.git("commit", "-qm", "initial")
        path.write_text(
            "select legacy_id from legacy_table;\nselect item_name from sample_table;\n",
            encoding="utf-8",
        )
        self.git("add", "queries.sql")

        document = read_staged_documents(self.root, {".sql"})[0]
        selection = expand_selection(document.content, "sql", document.changed_lines)
        result = process_document(self.config(), document.content, document.path, "sql", selection)
        update_staged_documents(self.root, [(document, result.content)])

        self.assertEqual(
            self.git("show", ":queries.sql"),
            "select legacy_id from legacy_table;\nSELECT item_name FROM sample_table;\n",
        )

    def test_staged_statement_formats_between_without_splitting_its_delimiter(self):
        path = self.root / "queries.sql"
        path.write_text(
            "SELECT item_id FROM sample_item WHERE recorded_at BETWEEN :start\n"
            "    AND :end AND owning_organization_identifier_for_processed_sample_record = :old_organization;\n",
            encoding="utf-8",
        )
        self.git("add", "queries.sql")
        self.git("commit", "-qm", "initial")
        path.write_text(
            "SELECT item_id FROM sample_item WHERE recorded_at BETWEEN :start\n"
            "    AND :end AND owning_organization_identifier_for_processed_sample_record = :new_organization;\n",
            encoding="utf-8",
        )
        self.git("add", "queries.sql")

        document = read_staged_documents(self.root, {".sql"})[0]
        selection = expand_selection(document.content, "sql", document.changed_lines)
        result = process_document(self.config(), document.content, document.path, "sql", selection)
        update_staged_documents(self.root, [(document, result.content)])

        self.assertEqual(
            self.git("show", ":queries.sql"),
            "SELECT item_id FROM sample_item WHERE\n"
            "    recorded_at BETWEEN :start AND :end\n"
            "    AND owning_organization_identifier_for_processed_sample_record = :new_organization;\n",
        )

    def test_staged_mybatis_sql_fix_preserves_parameters_and_xml(self):
        path = self.root / "SampleMapper.xml"
        path.write_text(
            """<mapper namespace="sample.Mapper">
    <select id="findItem">
        select item_id from sample_table where item_id=#{itemId}
    </select>
</mapper>
""",
            encoding="utf-8",
        )
        self.git("add", "SampleMapper.xml")

        document = read_staged_documents(self.root, {".xml"})[0]
        selection = expand_selection(document.content, "xml", document.changed_lines)
        result = process_document(self.config(), document.content, document.path, "xml", selection)
        update_staged_documents(self.root, [(document, result.content)])
        staged = self.git("show", ":SampleMapper.xml")

        self.assertIn("SELECT item_id FROM sample_table WHERE item_id = #{itemId}", staged)
        self.assertIn('<select id="findItem">', staged)
        self.assertIn("</mapper>", staged)

    def test_staged_trellis_fix_preserves_named_bind(self):
        path = self.root / "find_items.sql"
        path.write_text(
            """select item_id from sample_table
--trellis:IF active_only
where item_id=:filters.item_id
--trellis:ENDIF
""",
            encoding="utf-8",
        )
        self.git("add", "find_items.sql")

        document = read_staged_documents(self.root, {".sql"})[0]
        selection = expand_selection(document.content, "sql", document.changed_lines)
        result = process_document(self.config(), document.content, document.path, "sql", selection)
        update_staged_documents(self.root, [(document, result.content)])

        self.assertEqual(
            self.git("show", ":find_items.sql"),
            "SELECT item_id FROM sample_table\n"
            "-- trellis: if active_only\n"
            "    WHERE item_id = :filters.item_id\n"
            "-- trellis: endif\n",
        )

    def test_staged_dry_run_prints_diff_without_updating_index(self):
        path = self.root / "queries.sql"
        path.write_text("select item_id from sample_table;\n", encoding="utf-8")
        self.git("add", "queries.sql")
        config = Config()
        config.staged = True
        config.dry_run = True
        output = StringIO()

        with patch("mir.engine.git_staged.repository_root", return_value=self.root):
            with patch("mir.engine.runner.shutil.which", return_value=None):
                with redirect_stdout(output):
                    exit_code = run_linter(config)

        self.assertEqual(exit_code, 0)
        self.assertIn("--- a/queries.sql", output.getvalue())
        self.assertIn("+++ b/queries.sql", output.getvalue())
        self.assertIn("+SELECT item_id FROM sample_table;", output.getvalue())
        self.assertEqual(self.git("show", ":queries.sql"), "select item_id from sample_table;\n")


if __name__ == "__main__":
    unittest.main()
