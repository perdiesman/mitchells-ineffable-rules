"""ESLint-backed JavaScript and TypeScript checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

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
    resolve_executable,
    selected_edit,
    version_diagnostic,
)
from mir.providers.node_bridge import NodeBridgeError, node_request


class EslintProvider(BaseProvider):
    provider_id = "eslint"
    description = "Lint JavaScript and TypeScript with project-local ESLint."
    languages = ("javascript", "typescript")
    extensions = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
    capabilities = ProviderCapabilities(check=True, fix=True, batch=True)
    documentation_url = "https://eslint.org/docs/latest/"
    default_config = {
        "enabled": "auto",
        "executable": "auto",
        "config": "discover",
        "fix": True,
        "required_version": None,
        "timeout_seconds": 30,
    }
    config_options = {
        "enabled": {"default": "auto", "description": "auto, true, or false"},
        "fix": {"default": True, "description": "Apply fixes reported safe by ESLint."},
        "required_version": {
            "default": None,
            "description": "Require an exact ESLint version.",
        },
    }
    cases = (ProviderCase("reported expression", "value == null;\n", "reported"),)

    def _check(
        self,
        executable: str,
        content: str,
        context: ProviderContext,
        config: Dict[str, Any],
    ):
        configured = config.get("config")
        payload = {"path": str(Path(context.path).resolve()), "content": content}
        if isinstance(configured, str) and configured not in {"", "auto", "discover"}:
            payload["config"] = configured
        response = node_request(
            "eslint", executable, payload, float(config.get("timeout_seconds", 30))
        )
        messages = response.get("messages") or []
        findings = []
        for message in messages:
            edits = ()
            fix = message.get("fix")
            if fix and isinstance(fix.get("range"), list):
                edits = (
                    ProviderEdit(
                        int(fix["range"][0]),
                        int(fix["range"][1]),
                        str(fix.get("text") or ""),
                    ),
                )
            findings.append(
                ProviderFinding(
                    str(message.get("ruleId") or "parse-error"),
                    str(message.get("message") or "ESLint violation"),
                    int(message.get("line") or 1),
                    int(message.get("column") or 1),
                    int(message.get("endLine") or message.get("line") or 1),
                    int(message.get("endColumn") or message.get("column") or 1),
                    "error" if int(message.get("severity") or 2) == 2 else "warning",
                    edits,
                )
            )
        return findings, str(response.get("version") or "") or None

    def run(
        self, content: str, context: ProviderContext, provider_config: Dict[str, Any]
    ) -> ProviderResult:
        executable = resolve_executable(
            context.path,
            "eslint",
            provider_config.get("executable"),
            project_local=True,
        )
        if not executable:
            if provider_config.get("enabled") is True:
                return ProviderResult(
                    content,
                    diagnostics=[
                        f"Provider eslint is enabled but no project executable was found for {context.path}"
                    ],
                )
            return ProviderResult(content)
        try:
            current = content
            findings, version = self._check(
                executable, current, context, provider_config
            )
            mismatch = version_diagnostic(
                "eslint", version, provider_config.get("required_version")
            )
            if mismatch:
                return ProviderResult(content, diagnostics=[mismatch], version=version)
            if context.fix and provider_config.get("fix", True):
                for _ in range(10):
                    disabled = set(
                        context.disabled_lines.get("eslint", frozenset())
                    ) | set(context.disabled_lines.get("all", frozenset()))
                    edits = []
                    for finding in findings:
                        if (
                            context.restricted
                            and finding.line not in context.selected_lines
                        ):
                            continue
                        for edit in finding.edits:
                            touched = range(
                                current.count("\n", 0, edit.start) + 1,
                                current.count("\n", 0, edit.end) + 2,
                            )
                            if selected_edit(
                                current,
                                edit,
                                context.selected_lines,
                                context.restricted,
                            ) and not disabled.intersection(touched):
                                edits.append(edit)
                    updated = apply_edits(current, edits)
                    if updated == current:
                        break
                    current = updated
                    findings, version = self._check(
                        executable, current, context, provider_config
                    )
            final, version = self._check(executable, current, context, provider_config)
            return ProviderResult(
                current, final, changed=current != content, version=version
            )
        except (
            OSError,
            RuntimeError,
            NodeBridgeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            return ProviderResult(
                content,
                diagnostics=[
                    f"Error running provider eslint on {context.path}: {error}"
                ],
            )
