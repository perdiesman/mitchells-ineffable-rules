"""Prettier-backed web source formatting."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict

from mir.engine.provider_interface import BaseProvider, ProviderCapabilities, ProviderContext, ProviderFinding, ProviderResult
from mir.providers.common import contiguous_ranges, offset_for_location, resolve_executable, run_process


class PrettierProvider(BaseProvider):
    provider_id = "prettier"
    description = "Format JavaScript, TypeScript, styles, and HTML with Prettier."
    languages = ("javascript", "typescript", "css", "html")
    extensions = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".css", ".scss", ".html")
    capabilities = ProviderCapabilities(check=True, format=True, range_format=True, batch=True)
    documentation_url = "https://prettier.io/docs/"
    default_config = {"enabled": "auto", "executable": "auto", "config": "discover", "timeout_seconds": 30}

    def _format(self, executable: str, content: str, context: ProviderContext, config: Dict[str, Any]) -> str:
        disabled = set(context.disabled_lines.get("prettier", frozenset())) | set(context.disabled_lines.get("all", frozenset()))
        if context.restricted or disabled:
            candidates = set(context.selected_lines) if context.restricted else set(range(1, len(content.splitlines()) + 1))
            candidates.difference_update(disabled)
            ranges = list(reversed(contiguous_ranges(candidates)))
        else:
            ranges = [(0, 0)]
        current = content
        for start, end in ranges:
            command = [executable, "--stdin-filepath", context.path]
            configured = config.get("config")
            if isinstance(configured, str) and configured not in {"", "auto", "discover"}:
                command.extend(["--config", configured])
            if start:
                range_start = offset_for_location(current, start, 1)
                range_end = offset_for_location(current, end, len(current.splitlines()[end - 1]) + 1)
                command.extend(["--range-start", str(range_start), "--range-end", str(range_end)])
            process = run_process(command, current, str(Path(executable).resolve().parents[2]), float(config.get("timeout_seconds", 30)))
            if process.returncode != 0:
                raise RuntimeError(process.stderr.strip() or f"Prettier exited with {process.returncode}")
            current = process.stdout
        return current

    def run(self, content: str, context: ProviderContext, provider_config: Dict[str, Any]) -> ProviderResult:
        executable = resolve_executable(context.path, "prettier", provider_config.get("executable"), project_local=True)
        if not executable:
            if provider_config.get("enabled") is True:
                return ProviderResult(content, diagnostics=[f"Provider prettier is enabled but no project executable was found for {context.path}"])
            return ProviderResult(content)
        try:
            formatted = self._format(executable, content, context, provider_config)
            findings = []
            if formatted != content and not context.fix:
                findings.append(ProviderFinding("format", "File is not formatted with Prettier", min(context.selected_lines or {1})))
                formatted = content
            return ProviderResult(formatted, findings, changed=formatted != content)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            return ProviderResult(content, diagnostics=[f"Error running provider prettier on {context.path}: {error}"])

