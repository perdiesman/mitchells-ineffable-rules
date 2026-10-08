"""Core lint, fix, dry-run, and staged-Git execution."""

from __future__ import annotations

import difflib
import select
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from mir.engine.config import Config
from mir.engine.disabler import get_disabled_rules_map, get_file_language
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.rules_help import get_supported_languages
from mir.engine.rules_loader import load_rules_for_language
from mir.engine.selection import LineSelection, expand_selection


@dataclass
class DocumentResult:
    path: str
    original: str
    content: str
    errors: int = 0
    warnings: int = 0
    violations: list[tuple[Violation, BaseRule, str]] = field(default_factory=list)
    rules_fixed: set[str] = field(default_factory=set)
    diagnostics: list[str] = field(default_factory=list)


def print_diff_with_delta(diff_lines: List[str]) -> None:
    diff_text = "".join(diff_lines)
    delta_path = shutil.which("delta")
    if delta_path:
        try:
            columns = shutil.get_terminal_size().columns
            process = subprocess.Popen(
                [delta_path, "--side-by-side", "--width", str(columns)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, _ = process.communicate(input=diff_text)
            if process.returncode == 0 and stdout:
                print(stdout, end="")
                return
        except Exception:
            pass
    print(diff_text, end="")


def _plpgsql_bodies(content: str) -> list[dict]:
    from mir.rules.sql.sql_utils import tokenize_sql

    tokens = tokenize_sql(content)
    bodies: list[dict] = []
    previous_active = None
    for token in tokens:
        value = token["value"]
        if token["type"] == "STRING" and value.startswith("$"):
            delimiter_end = value.find("$", 1)
            if delimiter_end != -1:
                tag = value[: delimiter_end + 1]
                if value.endswith(tag):
                    body = value[len(tag) : -len(tag)]
                    first_line = next((line for line in body.splitlines() if line.strip()), "")
                    first_word = first_line.strip().split()[0].upper() if first_line.strip() else ""
                    if (
                        previous_active
                        and previous_active["value"].upper() in {"AS", "DO"}
                    ) or first_word in {"DECLARE", "BEGIN"}:
                        bodies.append({"token": token, "tag": tag, "body": body})
        if token["type"] not in {"WHITESPACE", "COMMENT"}:
            previous_active = token
    return bodies


def run_rule_check_recursively(
    rule: BaseRule,
    content: str,
    file_path: str,
    rule_config: dict,
    lang: str,
) -> List[Violation]:
    violations = [] if rule.only_recursive else rule.check(content, file_path, rule_config)
    if lang != "sql" or rule.exclude_recursive:
        return violations
    lines = content.splitlines()
    for body_info in _plpgsql_bodies(content):
        body = body_info["body"]
        body_start = content.count("\n", 0, body_info["token"]["start"] + len(body_info["tag"])) + 1
        for violation in rule.check(body, file_path, rule_config):
            violation.line_number = body_start + violation.line_number - 1
            violation.offending_lines = [
                lines[violation.line_number - 1] if violation.line_number <= len(lines) else ""
            ]
            violations.append(violation)
    return violations


def run_rule_fix_recursively(
    rule: BaseRule,
    content: str,
    file_path: str,
    rule_config: dict,
    lang: str,
) -> str:
    current = content if rule.only_recursive else rule.fix(content, file_path, rule_config)
    if lang != "sql" or rule.exclude_recursive:
        return current
    for body_info in reversed(_plpgsql_bodies(current)):
        fixed = rule.fix(body_info["body"], file_path, rule_config)
        if fixed == body_info["body"]:
            continue
        token = body_info["token"]
        replacement = body_info["tag"] + fixed + body_info["tag"]
        current = current[: token["start"]] + replacement + current[token["end"] :]
    return current


def apply_filtered_fixes(original: str, fixed: str, target_lines: Set[int]) -> str:
    if not target_lines:
        return fixed
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)
    result: list[str] = []
    matcher = difflib.SequenceMatcher(None, original_lines, fixed_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.extend(original_lines[i1:i2])
            continue
        affected = set(range(i1 + 1, i2 + 1))
        if tag == "insert":
            affected = {max(1, i1), i1 + 1}
        if affected.intersection(target_lines):
            result.extend(fixed_lines[j1:j2])
        else:
            result.extend(original_lines[i1:i2])
    return "".join(result)


def resolve_rule_config(
    config: Config,
    rule_id: str,
    lang: str,
    detected_base_indent: Optional[str] = None,
    lines: Optional[Set[int]] = None,
    template_dialect: Optional[str] = None,
) -> dict:
    rule_config: dict = {}
    global_config = config.rule_configs.get(rule_id, {})
    language_config = config.rule_configs.get(f"{lang}:{rule_id}", {})
    if isinstance(global_config, dict):
        rule_config.update(global_config)
    if isinstance(language_config, dict):
        rule_config.update(language_config)
    rule_config.update(
        {
            "_all_configs": config.rule_configs,
            "_lang": lang,
            "_rules_to_disable": config.rules_to_disable,
            "_rules_to_enable": config.rules_to_enable,
            "_disable_all": config.disable_all,
            "_profile": config.profile,
        }
    )
    if lines:
        rule_config["_lines"] = lines
    if template_dialect:
        rule_config["_template_dialect"] = template_dialect
    if "base_indent" not in rule_config and detected_base_indent is not None:
        rule_config["base_indent"] = detected_base_indent
    return rule_config


def detect_base_indent(content: str) -> str:
    for line in content.splitlines():
        if line.strip():
            return line[: len(line) - len(line.lstrip(" \t"))]
    return ""


def _supported_extensions(include_dirs: Optional[list[str]] = None) -> set[str]:
    extensions = set()
    for language in get_supported_languages(include_dirs):
        extensions.update({".java", ".jav"} if language == "java" else {f".{language}"})
    return extensions


def find_files(paths: List[str], include_dirs: Optional[List[str]] = None) -> List[str]:
    extensions = _supported_extensions(include_dirs)
    found: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_file() and path.suffix.lower() in extensions:
            found.append(str(path))
        elif path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in extensions:
                    found.append(str(candidate))
    return sorted(set(found))


def format_violation(
    violation: Violation,
    file_path: str,
    verbose: bool,
    rule_desc: str,
    severity: str = "error",
) -> str:
    message = f"{violation.rule_id} {file_path}:{violation.line_number}"
    if severity == "warning":
        message = f"[WARN] {message}"
    if not verbose:
        return message
    output = [message, f"  Description: {rule_desc}"]
    if violation.offending_lines:
        output.append("  Offending line(s):")
        output.extend(f"    > {line}" for line in violation.offending_lines)
    return "\n".join(output)


def _rule_enabled(config: Config, rule: BaseRule, lang: str, rule_config: dict) -> bool:
    if rule.rule_id in config.rules_to_disable or f"{lang}:{rule.rule_id}" in config.rules_to_disable:
        return False
    global_config = config.rule_configs.get(rule.rule_id, {})
    language_config = config.rule_configs.get(f"{lang}:{rule.rule_id}", {})
    if global_config is False or language_config is False:
        return False
    if config.profile == "commit" and not rule.commit_profile:
        return False
    if lang == "sql" and rule_config.get("_template_dialect") == "trellis" and not rule.trellis_safe:
        return False
    if config.disable_all:
        return bool(
            rule_config.get("enabled") is True
            or rule.rule_id in config.rules_to_enable
            or f"{lang}:{rule.rule_id}" in config.rules_to_enable
        )
    return bool(rule_config.get("enabled", rule.enabled_by_default))


def _find_rule(rule_id: str, lang: str, config: Config) -> Optional[BaseRule]:
    languages = [lang] + [
        candidate
        for candidate in get_supported_languages(config.include_dirs)
        if candidate != lang
    ]
    for language in languages:
        rule = next(
            (
                candidate
                for candidate in load_rules_for_language(
                    language, config.include_dirs, config.rule_mode
                )
                if candidate.rule_id == rule_id
            ),
            None,
        )
        if rule is not None:
            return rule
    return None


def _collect(
    config: Config,
    content: str,
    path: str,
    lang: str,
    selection: LineSelection,
) -> tuple[list[tuple[Violation, BaseRule, str]], list[str]]:
    disabled = get_disabled_rules_map(content, path)
    base_indent = detect_base_indent(content)
    template_dialect = None
    if lang == "sql":
        from mir.rules.sql.trellis_utils import has_trellis_directives

        if has_trellis_directives(content):
            template_dialect = "trellis"
    collected: list[tuple[Violation, BaseRule, str]] = []
    diagnostics: list[str] = []
    for rule in load_rules_for_language(lang, config.include_dirs, config.rule_mode):
        rule_config = resolve_rule_config(
            config,
            rule.rule_id,
            lang,
            base_indent,
            set(selection.allowed),
            template_dialect,
        )
        if not _rule_enabled(config, rule, lang, rule_config):
            continue
        try:
            violations = run_rule_check_recursively(rule, content, path, rule_config, lang)
        except Exception as error:
            diagnostics.append(f"Error running rule {rule.rule_id} on {path}: {error}")
            continue
        disabled_lines = disabled.get(rule.rule_id, set()) | disabled.get("IR-all", set())
        for violation in violations:
            if not selection.contains(violation.line_number):
                continue
            if violation.line_number in disabled_lines or violation.line_number in disabled.get(violation.rule_id, set()):
                continue
            violation_rule = _find_rule(violation.rule_id, lang, config) or rule
            violation_config = resolve_rule_config(
                config,
                violation_rule.rule_id,
                lang,
                base_indent,
                set(selection.allowed),
                template_dialect,
            )
            severity = violation_rule.get_config_value(violation_config, "severity", "error")
            if config.no_warnings and severity == "warning":
                continue
            if config.warnings_only and severity != "warning":
                continue
            # Keep the host rule as the execution owner. Embedded violations may
            # borrow severity and descriptions from a guest rule, but fixes must
            # flow back through the host's source map rather than run on XML.
            collected.append((violation, rule, severity))
    return collected, diagnostics


def process_document(
    config: Config,
    content: str,
    path: str,
    lang: str,
    selection: Optional[LineSelection] = None,
) -> DocumentResult:
    selection = selection or expand_selection(content, lang, config.lines)
    result = DocumentResult(path, content, content)
    initial, diagnostics = _collect(config, content, path, lang, selection)
    result.diagnostics.extend(diagnostics)

    if config.fix or config.dry_run:
        current = content
        seen = {current}
        violations = initial
        for _ in range(10):
            fix_rules: list[BaseRule] = []
            for violation, rule, _ in violations:
                if violation.is_fixable and rule.is_fixable in {"yes", "sometimes"} and rule not in fix_rules:
                    fix_rules.append(rule)
            if not fix_rules:
                break
            before_pass = current
            template_dialect = None
            if lang == "sql":
                from mir.rules.sql.trellis_utils import has_trellis_directives

                if has_trellis_directives(current):
                    template_dialect = "trellis"
            for rule in fix_rules:
                rule_config = resolve_rule_config(
                    config,
                    rule.rule_id,
                    lang,
                    detect_base_indent(current),
                    set(selection.allowed),
                    template_dialect,
                )
                rule_config["rules_fixed"] = result.rules_fixed
                try:
                    fixed = run_rule_fix_recursively(rule, current, path, rule_config, lang)
                except Exception as error:
                    result.diagnostics.append(f"Error fixing rule {rule.rule_id} on {path}: {error}")
                    continue
                if selection.restricted:
                    fixed = apply_filtered_fixes(current, fixed, set(selection.allowed))
                if fixed != current:
                    result.rules_fixed.add(rule.rule_id)
                    current = fixed
            if current == before_pass:
                break
            cycle_detected = current in seen
            violations, pass_diagnostics = _collect(config, current, path, lang, selection)
            result.diagnostics.extend(pass_diagnostics)
            if cycle_detected:
                result.diagnostics.append(f"Formatter did not converge for {path}; a formatting cycle was detected")
                break
            seen.add(current)
        else:
            result.diagnostics.append(f"Formatter did not converge for {path} after 10 passes")
        result.content = current
        result.violations = violations
    else:
        result.violations = initial

    # Avoid charging the same repeated rule failure from every convergence pass.
    result.diagnostics = list(dict.fromkeys(result.diagnostics))
    for _, _, severity in result.violations:
        if severity == "warning":
            result.warnings += 1
        else:
            result.errors += 1
    result.errors += len(result.diagnostics)
    return result


def _print_result(config: Config, result: DocumentResult) -> None:
    if config.quiet:
        return
    for diagnostic in result.diagnostics:
        print(diagnostic, file=sys.stderr)
    for violation, rule, severity in result.violations:
        print(format_violation(violation, result.path, config.verbose, rule.description, severity))


def _read_stdin() -> Optional[str]:
    if sys.stdin.isatty():
        return None
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0.0)
    except Exception:
        return None
    if not ready:
        return None
    value = sys.stdin.read()
    return value if value else None


def _run_staged(config: Config) -> int:
    from mir.engine.git_staged import read_staged_documents, repository_root, update_staged_documents

    try:
        root = repository_root()
        documents = read_staged_documents(root, _supported_extensions(config.include_dirs))
    except subprocess.CalledProcessError as error:
        print(f"Error reading staged content: {error}", file=sys.stderr)
        return 2

    changes = []
    errors = 0
    for document in documents:
        lang = get_file_language(document.path)
        if not lang:
            continue
        selection = expand_selection(document.content, lang, document.changed_lines)
        result = process_document(config, document.content, document.path, lang, selection)
        _print_result(config, result)
        errors += result.errors
        if config.fix and result.content != document.content:
            changes.append((document, result.content))
            if not config.quiet:
                print(f"Fixed staged issues in {document.path} ({', '.join(sorted(result.rules_fixed))})")
    if config.fix and changes:
        try:
            warnings = update_staged_documents(root, changes)
        except subprocess.CalledProcessError as error:
            print(f"Error updating staged content: {error}", file=sys.stderr)
            return 2
        if not config.quiet:
            for warning in warnings:
                print(f"Warning: {warning}", file=sys.stderr)
    return 1 if errors else 0


def run_linter(config: Config) -> int:
    if config.staged:
        if not config.profile:
            config.profile = "commit"
        return _run_staged(config)

    content = config.content
    lang = config.lang
    if content is None:
        content = _read_stdin()
    if content is not None:
        if not lang:
            print("Error: Language must be specified for raw or piped content (use --lang/--language).", file=sys.stderr)
            return 1
        result = process_document(config, content, "<stdin>", lang)
        _print_result(config, result)
        if config.dry_run and result.content != result.original and not config.quiet:
            print_diff_with_delta(
                list(
                    difflib.unified_diff(
                        result.original.splitlines(keepends=True),
                        result.content.splitlines(keepends=True),
                        fromfile="a/<stdin>",
                        tofile="b/<stdin>",
                    )
                )
            )
        elif config.fix and not config.quiet:
            print(result.content, end="")
        return 1 if result.errors else 0

    total_errors = 0
    for file_path in find_files(config.paths, config.include_dirs):
        language = get_file_language(file_path)
        if not language:
            continue
        try:
            original = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            if not config.quiet:
                print(f"Error reading file '{file_path}': {error}", file=sys.stderr)
            total_errors += 1
            continue
        result = process_document(config, original, file_path, language)
        _print_result(config, result)
        total_errors += result.errors
        if result.content == original:
            continue
        if config.fix:
            Path(file_path).write_text(result.content, encoding="utf-8", newline="")
            if not config.quiet:
                print(f"Fixed issues in {file_path} ({', '.join(sorted(result.rules_fixed))})")
        elif config.dry_run and not config.quiet:
            print_diff_with_delta(
                list(
                    difflib.unified_diff(
                        original.splitlines(keepends=True),
                        result.content.splitlines(keepends=True),
                        fromfile=f"a/{file_path}",
                        tofile=f"b/{file_path}",
                        n=2,
                    )
                )
            )
    return 1 if total_errors else 0
