from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.sql.trellis_utils import analyze_trellis


class TrellisDirectivesRule(BaseRule):
    rule_id = "IR-trellis-directives"
    description = "Validate Trellis template blocks and use canonical directive comment layout."
    category = "templates"
    is_fixable = "sometimes"
    enabled_by_default = True
    commit_profile = True
    trellis_safe = True

    default_config = {}
    config_options = {}
    examples = []
    additional_validations = []
    cases = [
        RuleCase(
            "canonical conditional",
            "SELECT item_id\nFROM sample_table\n-- trellis: if active_only\n"
            "WHERE retired_at IS NULL\n-- trellis: endif",
            "accepted",
        ),
        RuleCase(
            "directive layout",
            "SELECT item_id\nFROM sample_table\n--trellis:IF active_only\n"
            "WHERE retired_at IS NULL\n--trellis:ENDIF",
            "fixed",
            "SELECT item_id\nFROM sample_table\n-- trellis: if active_only\n"
            "WHERE retired_at IS NULL\n-- trellis: endif",
        ),
        RuleCase(
            "unclosed conditional",
            "SELECT item_id\nFROM sample_table\n-- trellis: if active_only\nWHERE retired_at IS NULL;",
            "not_fixed",
        ),
        RuleCase(
            "unexpected branch",
            "SELECT item_id FROM sample_table;\n-- trellis: else",
            "reported",
        ),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        directives, issues, _ = analyze_trellis(content)
        lines = content.splitlines()
        violations = []
        for directive in directives:
            if directive.original != directive.canonical:
                violations.append(Violation(
                    self.rule_id,
                    directive.line,
                    "Use canonical '-- trellis: directive' spacing and lowercase directive names.",
                    [lines[directive.line - 1]],
                    True,
                ))
        for issue in issues:
            violations.append(Violation(
                self.rule_id,
                issue.line,
                issue.message,
                [lines[issue.line - 1]],
                False,
            ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        directives, issues, _ = analyze_trellis(content)
        if issues:
            return content
        lines = content.splitlines(keepends=True)
        for directive in directives:
            old_line = lines[directive.line - 1]
            ending = "\r\n" if old_line.endswith("\r\n") else ("\n" if old_line.endswith("\n") else "")
            lines[directive.line - 1] = directive.canonical + ending
        return "".join(lines)
