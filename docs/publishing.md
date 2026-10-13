# Publishing to PyPI

MIR releases are published to the production Python Package Index by GitHub Actions and [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/). The workflow exchanges GitHub's short-lived OpenID Connect identity for permission to upload `mir-linter`; the repository does not store a PyPI password or API token.

## One-time project setup

The repository owner must register the workflow once on the existing [`mir-linter` PyPI project](https://pypi.org/project/mir-linter/):

1. Open **Manage project → Publishing** on PyPI.
2. Add a GitHub publisher with these exact values:

   | Field | Value |
   | --- | --- |
   | GitHub owner | `perdiesman` |
   | Repository | `mitchells-ineffable-rules` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

3. Save the publisher. No PyPI secret needs to be added to GitHub.

The GitHub `pypi` environment permits `v*` tags and does not require a reviewer. Repository settings prevent deletion or force-pushes of `main` without preventing the owner's normal direct pushes.

## Publish a release

1. Update every recorded version and merge the release commit into `main`. The project version in `pyproject.toml` and `mir.__version__` must match.
2. Run the normal checks locally if desired:

   ```bash
   uv run --frozen python -m unittest discover -s tests -p "test_*.py"
   uv run --frozen mir/main.py --help docs
   git diff --exit-code -- docs
   ```

3. On GitHub, create a release targeting `main`. Create or select a tag named `vX.Y.Z`, where `X.Y.Z` exactly matches the package version, and publish the release.

The [Publish to PyPI workflow](../.github/workflows/publish.yml) then verifies the version and `main` ancestry, runs the complete tests, checks generated documentation, builds both distributions, validates their metadata, installs and smoke-tests the wheel, and publishes them to PyPI. Draft releases do not trigger it. A prerelease does trigger it when published and must use a tag matching its Python package version.

PyPI versions are immutable. If validation fails because release content is wrong, fix the problem on `main`, select a new version, and publish a new release rather than reusing a version already uploaded. A transient failed workflow run can be retried from the GitHub Actions page.

## Verify the release

The completed workflow links to the PyPI project from its `pypi` environment deployment. Confirm that the new release displays GitHub provenance, then test either supported installation form:

```bash
pip install mir-linter
uv tool install mir-linter
```

Both installations provide the `mir` and `mir-linter` commands:

```bash
mir --version
mir-linter --version
```
