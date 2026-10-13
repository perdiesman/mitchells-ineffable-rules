from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish.yml"


class TestPublishWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.text)

    def test_only_published_releases_trigger_the_workflow(self):
        self.assertEqual(
            self.workflow["on"],
            {"release": {"types": ["published"]}},
        )

    def test_publish_job_uses_isolated_oidc_permissions(self):
        jobs = self.workflow["jobs"]
        self.assertEqual(jobs["build"]["permissions"], {"contents": "read"})
        self.assertEqual(jobs["publish"]["permissions"], {"id-token": "write"})
        self.assertEqual(jobs["publish"]["needs"], "build")
        self.assertEqual(jobs["publish"]["environment"]["name"], "pypi")
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("password:", self.text)

    def test_release_validation_binds_tag_version_and_main(self):
        validation = next(
            step
            for step in self.workflow["jobs"]["build"]["steps"]
            if step["name"] == "Validate release source and version"
        )["run"]
        self.assertIn('test "$RELEASE_TAG" = "v$project_version"', validation)
        self.assertIn('test "$source_version" = "$project_version"', validation)
        self.assertIn(
            'git merge-base --is-ancestor "$GITHUB_SHA" origin/main',
            validation,
        )

    def test_distributions_are_passed_as_an_artifact(self):
        build_uses = [
            step.get("uses", "")
            for step in self.workflow["jobs"]["build"]["steps"]
        ]
        publish_uses = [
            step.get("uses", "")
            for step in self.workflow["jobs"]["publish"]["steps"]
        ]
        self.assertTrue(
            any(use.startswith("actions/upload-artifact@") for use in build_uses)
        )
        self.assertTrue(
            any(use.startswith("actions/download-artifact@") for use in publish_uses)
        )
        self.assertTrue(
            any(
                use.startswith("pypa/gh-action-pypi-publish@")
                for use in publish_uses
            )
        )


if __name__ == "__main__":
    unittest.main()
