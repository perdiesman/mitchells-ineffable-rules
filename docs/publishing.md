# Publishing to PyPI

This guide outlines how to package and publish the **Mitchell's Ineffable Rules (MIR) Linter** to the Python Package Index (PyPI).

---

## 1. Prerequisites

You need the `build` package (to compile your source code into distributable packages) and `twine` (to securely upload packages to PyPI).

Install these dependencies locally using `uv`:
```bash
uv pip install build twine
```

---

## 2. Package Configuration (`pyproject.toml`)

The package config [pyproject.toml](file:///home/me/projects/mitchells-ineffable-rules/pyproject.toml) defines metadata and sets up executable CLI entrypoints. After installation, users can invoke the linter directly from their terminal using either command:
- `mir`
- `mir-linter`

---

## 3. Build the Distribution Archives

Before building, clean up any previous build outputs (if `dist/` or `build/` directories exist).

Run the build tool in the root of the project:
```bash
uv run python -m build
```

This command generates two files in the `dist/` directory:
- A source archive (`.tar.gz`)
- A built distribution wheel (`.whl`)

---

## 4. Upload to TestPyPI (Optional but Recommended)

It is good practice to test the publication on TestPyPI first to ensure metadata renders correctly and installation works without issues.

1. Register an account on [TestPyPI](https://test.pypi.org/).
2. Create an API token on TestPyPI.
3. Upload the files using `twine`:
   ```bash
   uv run twine upload --repository testpypi dist/*
   ```
4. Test the installation from TestPyPI:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ --no-deps mitchells-ineffable-rules
   ```

---

## 5. Upload to PyPI

Once verified, upload the build distributions to live PyPI:

1. Register an account on [PyPI](https://pypi.org/).
2. Create an API token on PyPI.
3. Upload the files using `twine` (you will be prompted for your username `__token__` and API token password):
   ```bash
   uv run twine upload dist/*
   ```

---

## 6. Installing and Running the Package

After publishing, anyone can install the linter globally using `pip` or `uv`:

```bash
# Via pip
pip install mitchells-ineffable-rules

# Via uv (recommended tool launcher)
uv tool install mitchells-ineffable-rules
```

Once installed, execute the linter directly:
```bash
# Run on the current directory
mir .

# Run with verbose and auto-fixes
mir-linter --fix -v path/to/file.sql
```
