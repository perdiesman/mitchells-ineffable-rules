from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import get_token_depths, tokenize_sql


class CommentOnLayoutRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-comment-on-layout"
    description = (
        "Overlong COMMENT ON statements place IS and the unchanged comment "
        "literal on an indented continuation line."
    )
    category = "schema-definition"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"max_length": 120, "indent_size": 4}
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length before wrapping COMMENT ON.",
            "fallback": "IR-line-length:max_length",
        },
        "indent_size": {
            "default": 4,
            "description": "Continuation indentation in spaces.",
            "fallback": "IR-indent:indent_size",
        },
    }
    examples = [
        {
            "violating": (
                "COMMENT ON COLUMN sample_item.extraordinarily_long_status_name "
                "IS 'Status assigned after the item has completed validation and review.';"
            ),
            "correct": (
                "COMMENT ON COLUMN sample_item.extraordinarily_long_status_name\n"
                "    IS 'Status assigned after the item has completed validation and review.';"
            ),
        }
    ]
    additional_validations = ["COMMENT ON TABLE sample_item IS 'Items.';"]

    def _edits(self, content: str, rule_config: Dict[str, Any]) -> List[tuple]:
        max_length = self.get_config_value(rule_config, "max_length", 120)
        indent_size = self.get_config_value(rule_config, "indent_size", 4)
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        lines = content.splitlines()
        active_by_line = {}
        for index, token in enumerate(tokens):
            if token["type"] not in ("WHITESPACE", "COMMENT"):
                active_by_line.setdefault(token["line"], []).append(index)

        edits = []
        for line_number, indices in active_by_line.items():
            if line_number > len(lines) or len(lines[line_number - 1]) <= max_length:
                continue
            root = [index for index in indices if depths[index] == 0]
            if len(root) < 4:
                continue
            values = [tokens[index]["value"].upper() for index in root]
            if values[:2] != ["COMMENT", "ON"] or "IS" not in values[2:]:
                continue
            is_index = root[values.index("IS", 2)]
            previous = tokens[is_index - 1] if is_index > 0 else None
            if (
                previous is None
                or previous["type"] != "WHITESPACE"
                or "\n" in previous["value"]
            ):
                continue
            physical = lines[line_number - 1]
            base_indent = physical[: len(physical) - len(physical.lstrip(" \t"))]
            replacement = "\n" + base_indent + " " * indent_size
            edits.append((previous["start"], previous["end"], replacement))
        return sorted(set(edits), reverse=True)

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        violations = []
        for start, _, _ in self._edits(content, rule_config):
            line_number = content.count("\n", 0, start) + 1
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=line_number,
                message="Long COMMENT ON statement should place IS on a continuation.",
                offending_lines=[lines[line_number - 1]],
                is_fixable=True,
            ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        chars = list(content)
        for start, end, replacement in self._edits(content, rule_config):
            chars[start:end] = list(replacement)
        return "".join(chars)
