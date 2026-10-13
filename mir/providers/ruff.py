"""Ruff-backed Python linting and formatting."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from mir.engine.provider_interface import (
    BaseProvider,
    ProviderCapabilities,
    ProviderCase,
    ProviderContext,
    ProviderEdit,
    ProviderFinding,
    ProviderResult,
)
from mir.providers.common import (
    apply_edits,
    contiguous_ranges,
    offset_for_location,
    resolve_executable,
    run_process,
    selected_edit,
)


class RuffProvider(BaseProvider):
    provider_id = "ruff"
    description = "Lint and format Python with Ruff."
    languages = ("python",)
    extensions = (".py", ".pyi")
    capabilities = ProviderCapabilities(check=True, fix=True, format=True, range_format=True, batch=True)
    documentation_url = "https://docs.astral.sh/ruff/"
    default_config = {
        "enabled": "auto",
        "executable": "auto",
        "config": "discover",
        "check": True,
        "format": True,
        "unsafe_fixes": False,
        "timeout_seconds": 30,
    }
    config_options = {
        "enabled": {"default": "auto", "description": "auto, true, or false"},
        "unsafe_fixes": {"default": False, "description": "Allow Ruff fixes marked unsafe."},
    }
    cases = (
        ProviderCase("formatted function", "def add( left,right ):\n return left+right\n", "fixed", "def add(left, right):\n    return left + right\n"),
    )

    def _check(self, executable: str, content: str, context: ProviderContext, config: Dict[str, Any]):
        command = [executable, "check", "--output-format=json", "--no-cache", "--stdin-filename", context.path, "-"]
        configured = config.get("config")
        if isinstance(configured, str) and configured not in {"", "auto", "discover"}:
            command[2:2] = ["--config", configured]
        process = run_process(command, content, str(Path(context.path).resolve().parent), float(config.get("timeout_seconds", 30)))
        if process.returncode not in {0, 1}:
            raise RuntimeError(process.stderr.strip() or f"Ruff exited with {process.returncode}")
        payload = json.loads(process.stdout or "[]")
        findings: list[ProviderFinding] = []
        for item in payload:
            location = item.get("location") or {}
            end_location = item.get("end_location") or location
            edits: list[ProviderEdit] = []
            fix = item.get("fix") or {}
            applicability = str(fix.get("applicability") or "safe").lower()
            for edit in fix.get("edits") or []:
                start = edit.get("location") or location
                end = edit.get("end_location") or end_location
                edits.append(
                    ProviderEdit(
                        offset_for_location(content, int(start.get("row", 1)), int(start.get("column", 1))),
                        offset_for_location(content, int(end.get("row", 1)), int(end.get("column", 1))),
                        str(edit.get("content") or ""),
                        applicability,
                    )
                )
            findings.append(
                ProviderFinding(
                    str(item.get("code") or "unknown"),
                    str(item.get("message") or "Ruff violation"),
                    int(location.get("row", 1)),
                    int(location.get("column", 1)),
                    int(end_location.get("row", location.get("row", 1))),
                    int(end_location.get("column", location.get("column", 1))),
                    edits=tuple(edits),
                )
            )
        return findings

    def _format(self, executable: str, content: str, context: ProviderContext, config: Dict[str, Any]) -> str:
        disabled = set(context.disabled_lines.get("ruff", frozenset())) | set(context.disabled_lines.get("all", frozenset()))
        if context.restricted or disabled:
            candidates = set(context.selected_lines) if context.restricted else set(range(1, len(content.splitlines()) + 1))
            candidates.difference_update(disabled)
            ranges = list(reversed(contiguous_ranges(candidates)))
        else:
            ranges = [(0, 0)]
        current = content
        for start, end in ranges:
            command = [executable, "format", "--stdin-filename", context.path]
            configured = config.get("config")
            if isinstance(configured, str) and configured not in {"", "auto", "discover"}:
                command.extend(["--config", configured])
            if start:
                line = current.splitlines()[end - 1] if end <= len(current.splitlines()) else ""
                command.extend(["--range", f"{start}:1-{end}:{len(line) + 1}"])
            command.append("-")
            process = run_process(command, current, str(Path(context.path).resolve().parent), float(config.get("timeout_seconds", 30)))
            if process.returncode != 0:
                raise RuntimeError(process.stderr.strip() or f"Ruff formatter exited with {process.returncode}")
            current = process.stdout
        return current

    def run(self, content: str, context: ProviderContext, provider_config: Dict[str, Any]) -> ProviderResult:
        executable = resolve_executable(context.path, "ruff", provider_config.get("executable"))
        if not executable:
            if provider_config.get("enabled") is True:
                return ProviderResult(content, diagnostics=[f"Provider ruff is enabled but no executable was found for {context.path}"])
            return ProviderResult(content)
        try:
            current = content
            findings = self._check(executable, current, context, provider_config) if provider_config.get("check", True) else []
            if context.fix and findings:
                disabled = set(context.disabled_lines.get("ruff", frozenset())) | set(context.disabled_lines.get("all", frozenset()))
                edits = []
                for finding in findings:
                    if context.restricted and finding.line not in context.selected_lines:
                        continue
                    for edit in finding.edits:
                        if edit.applicability != "safe" and not provider_config.get("unsafe_fixes", False):
                            continue
                        if selected_edit(current, edit, context.selected_lines, context.restricted):
                            touched = range(
                                current.count("\n", 0, edit.start) + 1,
                                current.count("\n", 0, edit.end) + 2,
                            )
                            if not disabled.intersection(touched):
                                edits.append(edit)
                current = apply_edits(current, edits)
            format_finding = None
            if provider_config.get("format", True):
                formatted = self._format(executable, current, context, provider_config)
                if formatted != current:
                    if context.fix:
                        current = formatted
                    else:
                        format_finding = ProviderFinding(
                            "format",
                            "File is not formatted with Ruff",
                            min(context.selected_lines or {1}),
                        )
            final = self._check(executable, current, context, provider_config) if provider_config.get("check", True) else []
            if format_finding is not None:
                final.append(format_finding)
            return ProviderResult(current, final, changed=current != content)
        except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
            return ProviderResult(content, diagnostics=[f"Error running provider ruff on {context.path}: {error}"])

