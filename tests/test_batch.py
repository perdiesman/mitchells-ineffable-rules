import base64
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from mir.engine.batch import run_batch
from mir.engine.config import Config


class TestBatchExchange(unittest.TestCase):
    def make_exchange(
        self,
        content: str,
        *,
        content_file: str = "request/000000/content",
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        request = root / "request" / "000000"
        request.mkdir(parents=True)
        (request / "content").write_text(content, encoding="utf-8")
        (request / "diff").write_text(
            "@@ -1 +1 @@\n-old\n+new\n",
            encoding="utf-8",
        )
        record = {
            "schema_version": 1,
            "id": "000000",
            "path_base64": base64.b64encode(b"queries/sample.sql").decode(),
            "mode": "100644",
            "content_file": content_file,
            "diff_file": "request/000000/diff",
        }
        manifest = root / "request.jsonl"
        manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
        return root, manifest

    def config(self, root: Path, manifest: Path) -> Config:
        config = Config()
        config.fix = True
        config.profile = "commit"
        config.batch_manifest = str(manifest)
        config.batch_output = str(root / "result")
        return config

    def test_formats_staged_snapshot_without_git(self):
        root, manifest = self.make_exchange("select item_id from sample_table;\n")
        config = self.config(root, manifest)

        with patch(
            "mir.engine.git_staged._run",
            side_effect=AssertionError("batch processing must not invoke Git"),
        ):
            exit_code = run_batch(config)

        self.assertEqual(exit_code, 0)
        output = root / "result" / "000000"
        self.assertEqual(
            (output / "content").read_text(encoding="utf-8"),
            "SELECT item_id FROM sample_table;\n",
        )
        patch_text = (output / "working-tree.patch").read_text(encoding="utf-8")
        self.assertIn("--- a/queries/sample.sql", patch_text)
        self.assertIn("+++ b/queries/sample.sql", patch_text)
        result = json.loads(
            (root / "result" / "result.jsonl").read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "changed")
        self.assertEqual(result["path"], "queries/sample.sql")

    def test_rejects_exchange_path_escape(self):
        root, manifest = self.make_exchange(
            "select item_id from sample_table;\n",
            content_file="../outside.sql",
        )
        config = self.config(root, manifest)
        stderr = StringIO()

        with redirect_stderr(stderr):
            exit_code = run_batch(config)

        self.assertEqual(exit_code, 1)
        self.assertIn("escapes the exchange directory", stderr.getvalue())
        result = json.loads(
            (root / "result" / "result.jsonl").read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()
