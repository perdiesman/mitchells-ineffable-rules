import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestDockerCommitHook(unittest.TestCase):
    def git(self, root: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def test_docker_mode_formats_index_and_preserves_unstaged_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.git(root, "init", "-q")
            self.git(root, "config", "user.email", "test@example.com")
            self.git(root, "config", "user.name", "Test User")
            source = root / "sample.sql"
            source.write_text("select item_id from sample_table;\n", encoding="utf-8")
            self.git(root, "add", "sample.sql")
            source.write_text(
                "select item_id from sample_table;\n-- unstaged note\n",
                encoding="utf-8",
            )

            hook = root / "pre-commit-hook.sh"
            shutil.copy2(ROOT / "pre-commit-hook.sh", hook)
            self.git(root, "config", "mir.executionMode", "docker")
            self.git(root, "config", "mir.dockerImage", "mir-test:latest")
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            docker = fake_bin / "docker"
            docker.write_text(
                "#!/usr/bin/env bash\n"
                "set -u\n"
                "exchange=\n"
                "printf '%s\\n' \"$@\" > \"$MIR_TEST_DOCKER_ARGS\"\n"
                "for argument in \"$@\"; do\n"
                "    case \"$argument\" in\n"
                "        *:/exchange:rw) exchange=${argument%:/exchange:rw} ;;\n"
                "    esac\n"
                "done\n"
                "test -n \"$exchange\"\n"
                "exec \"$MIR_TEST_PYTHON\" -m mir.main "
                "--batch-manifest \"$exchange/request.jsonl\" "
                "--batch-output \"$exchange/result\" --profile commit --fix\n",
                encoding="utf-8",
            )
            docker.chmod(0o755)
            docker_args = root / "docker-args"
            environment = os.environ.copy()
            environment.update(
                {
                    "MIR_TEST_DOCKER_ARGS": str(docker_args),
                    "MIR_TEST_PYTHON": sys.executable,
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                }
            )

            result = subprocess.run(
                ["bash", str(hook)],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                self.git(root, "show", ":sample.sql"),
                "SELECT item_id FROM sample_table;\n",
            )
            self.assertEqual(
                source.read_text(encoding="utf-8"),
                "SELECT item_id FROM sample_table;\n-- unstaged note\n",
            )
            arguments = docker_args.read_text(encoding="utf-8")
            self.assertIn(f"{root}:/workspace:ro", arguments)
            self.assertIn("/workspace/.git:ro", arguments)
            self.assertIn("--network\nnone", arguments)

            source.write_text("select item_id from sample_table;\n", encoding="utf-8")
            self.git(root, "add", "sample.sql")
            source.write_text("select other_id from sample_table;\n", encoding="utf-8")
            overlapping = subprocess.run(
                ["bash", str(hook)],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(overlapping.returncode, 0, overlapping.stderr)
            self.assertEqual(
                self.git(root, "show", ":sample.sql"),
                "SELECT item_id FROM sample_table;\n",
            )
            self.assertEqual(
                source.read_text(encoding="utf-8"),
                "select other_id from sample_table;\n",
            )
            self.assertIn("overlapping unstaged edits", overlapping.stderr)

    @unittest.skipUnless(
        os.environ.get("MIR_TEST_DOCKER_IMAGE"),
        "set MIR_TEST_DOCKER_IMAGE to run the real container integration",
    )
    def test_real_container_formats_staged_snapshot_without_git_mount(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.git(root, "init", "-q")
            self.git(root, "config", "user.email", "test@example.com")
            self.git(root, "config", "user.name", "Test User")
            source = root / "sample.sql"
            source.write_text("select item_id from sample_table;\n", encoding="utf-8")
            self.git(root, "add", "sample.sql")
            source.write_text(
                "select item_id from sample_table;\n-- unstaged note\n",
                encoding="utf-8",
            )
            hook = root / "pre-commit-hook.sh"
            shutil.copy2(ROOT / "pre-commit-hook.sh", hook)
            self.git(root, "config", "mir.executionMode", "docker")
            self.git(
                root,
                "config",
                "mir.dockerImage",
                os.environ["MIR_TEST_DOCKER_IMAGE"],
            )

            result = subprocess.run(
                ["bash", str(hook)],
                cwd=root,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                self.git(root, "show", ":sample.sql"),
                "SELECT item_id FROM sample_table;\n",
            )
            self.assertEqual(
                source.read_text(encoding="utf-8"),
                "SELECT item_id FROM sample_table;\n-- unstaged note\n",
            )


if __name__ == "__main__":
    unittest.main()
