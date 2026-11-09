"""Prettier-backed web source formatting."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any, Dict

from mir.engine.provider_interface import (
    BaseProvider,
    ProviderCapabilities,
    ProviderCase,
    ProviderContext,
    ProviderFinding,
    ProviderResult,
)
from mir.providers.common import (
    contiguous_ranges,
    offset_for_location,
    resolve_executable,
    version_diagnostic,
)
from mir.providers.node_bridge import NodeBridgeError, node_request


class PrettierProvider(BaseProvider):
    provider_id = "prettier"
    description = "Format JavaScript, TypeScript, styles, and HTML with Prettier."
    languages = ("javascript", "typescript", "css", "html")
    extensions = (
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".css",
        ".scss",
        ".html",
    )
    capabilities = ProviderCapabilities(
        check=True, format=True, range_format=True, batch=True
    )
    documentation_url = "https://prettier.io/docs/"
    default_config = {
        "enabled": "auto",
        "executable": "auto",
        "config": "discover",
        "required_version": None,
        "timeout_seconds": 30,
    }
    config_options = {
        "enabled": {"default": "auto", "description": "auto, true, or false"},
        "required_version": {
            "default": None,
            "description": "Require an exact Prettier version.",
        },
    }
    cases = (
        ProviderCase(
            "formatted object",
            "const options={enabled:true};\n",
            "fixed",
            "const options = { enabled: true };\n",
        ),
    )

    def _format(
        self,
        executable: str,
        content: str,
        context: ProviderContext,
        config: Dict[str, Any],
    ):
        disabled = set(context.disabled_lines.get("prettier", frozenset())) | set(
            context.disabled_lines.get("all", frozenset())
        )
        candidates = (
            set(context.selected_lines)
            if context.restricted
            else set(range(1, len(content.splitlines()) + 1))
        )
        candidates.difference_update(disabled)
        full_format = context.language in {"css", "html"}
        if context.restricted or disabled:
            ranges = list(reversed(contiguous_ranges(candidates)))
        else:
            ranges = [(0, 0)]
        if full_format:
            # Prettier silently ignores partial ranges for styles and HTML.
            ranges = [(0, 0)] if candidates or not content else []
        current = content
        version = None
        for start, end in ranges:
            configured = config.get("config")
            payload = {"path": str(Path(context.path).resolve()), "content": current}
            if isinstance(configured, str) and configured not in {
                "",
                "auto",
                "discover",
            }:
                payload["config"] = configured
            if start:
                range_start = offset_for_location(current, start, 1)
                range_end = offset_for_location(
                    current, end, len(current.splitlines()[end - 1]) + 1
                )
                payload["options"] = {"rangeStart": range_start, "rangeEnd": range_end}
            response = node_request(
                "prettier",
                executable,
                payload,
                float(config.get("timeout_seconds", 30)),
            )
            version = str(response.get("version") or version or "") or None
            if response.get("ignored"):
                return content, version
            current = str(response.get("content", current))
        if full_format and (context.restricted or disabled) and current != content:
            changes = difflib.SequenceMatcher(
                None,
                content.splitlines(keepends=True),
                current.splitlines(keepends=True),
                autojunk=False,
            )
            for kind, start, end, _, _ in changes.get_opcodes():
                if kind == "equal":
                    continue
                affected = (
                    set(range(start + 1, end + 1)) if start != end else {max(1, start)}
                )
                if not affected.issubset(candidates):
                    raise NodeBridgeError(
                        "Prettier formatting would change lines outside the staged or enabled scope; format and stage the file with the project's locked Prettier before committing"
                    )
        return current, version

    def run(
        self, content: str, context: ProviderContext, provider_config: Dict[str, Any]
    ) -> ProviderResult:
        executable = resolve_executable(
            context.path,
            "prettier",
            provider_config.get("executable"),
            project_local=True,
        )
        if not executable:
            if provider_config.get("enabled") is True:
                return ProviderResult(
                    content,
                    diagnostics=[
                        f"Provider prettier is enabled but no project executable was found for {context.path}"
                    ],
                )
            return ProviderResult(content)
        try:
            formatted, version = self._format(
                executable, content, context, provider_config
            )
            mismatch = version_diagnostic(
                "prettier", version, provider_config.get("required_version")
            )
            if mismatch:
                return ProviderResult(content, diagnostics=[mismatch], version=version)
            findings = []
            if formatted != content and not context.fix:
                findings.append(
                    ProviderFinding(
                        "format",
                        "File is not formatted with Prettier",
                        min(context.selected_lines or {1}),
                    )
                )
                formatted = content
            return ProviderResult(
                formatted, findings, changed=formatted != content, version=version
            )
        except (OSError, RuntimeError, NodeBridgeError) as error:
            return ProviderResult(
                content,
                diagnostics=[
                    f"Error running provider prettier on {context.path}: {error}"
                ],
            )
