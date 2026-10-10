from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import get_token_depths, tokenize_sql


class AlterTableLayoutRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-alter-table-layout"
    description = (
        "Long ALTER TABLE statements place the table action on a continuation "
        "line and expand constraint clauses without changing their tokens."
    )
    category = "schema-definition"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"max_length": 120, "indent_size": 4}
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length before wrapping ALTER TABLE.",
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
                "ALTER TABLE sample_item_history ADD CONSTRAINT "
                "sample_item_history_owner_id_fkey FOREIGN KEY (owner_id) "
                "REFERENCES sample_owner (owner_id);"
            ),
            "correct": (
                "ALTER TABLE sample_item_history\n"
                "    ADD CONSTRAINT sample_item_history_owner_id_fkey\n"
                "        FOREIGN KEY (owner_id)\n"
                "        REFERENCES sample_owner (owner_id);"
            ),
        }
    ]
    additional_validations = [
        "ALTER TABLE sample_item ADD COLUMN owner_id INTEGER;",
    ]

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
        action_words = {"ADD", "ALTER", "DISABLE", "DROP", "ENABLE", "RENAME", "VALIDATE"}
        detail_words = {"CHECK", "EXCLUDE", "FOREIGN", "PRIMARY", "REFERENCES", "UNIQUE"}
        for line_number, indices in active_by_line.items():
            if line_number > len(lines) or len(lines[line_number - 1]) <= max_length:
                continue
            root = [index for index in indices if depths[index] == 0]
            if len(root) < 4:
                continue
            values = [tokens[index]["value"].upper() for index in root]
            if values[:2] != ["ALTER", "TABLE"]:
                continue
            action_position = next(
                (position for position in range(2, len(root)) if values[position] in action_words),
                None,
            )
            if action_position is None:
                continue

            physical = lines[line_number - 1]
            base_indent = physical[: len(physical) - len(physical.lstrip(" \t"))]
            action_indent = base_indent + " " * indent_size
            detail_indent = action_indent + " " * indent_size
            break_positions = [(root[action_position], action_indent)]
            if values[action_position] == "ADD":
                for position in range(action_position + 1, len(root)):
                    if values[position] in detail_words:
                        break_positions.append((root[position], detail_indent))

            for token_index, indent in break_positions:
                previous = tokens[token_index - 1] if token_index > 0 else None
                if (
                    previous is None
                    or previous["type"] != "WHITESPACE"
                    or "\n" in previous["value"]
                ):
                    continue
                replacement = "\n" + indent
                if previous["value"] != replacement:
                    edits.append((previous["start"], previous["end"], replacement))
        return sorted(set(edits), reverse=True)

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=content.count("\n", 0, start) + 1,
                message="Long ALTER TABLE statement should use constraint continuations.",
                offending_lines=[
                    lines[content.count("\n", 0, start)]
                    if content.count("\n", 0, start) < len(lines)
                    else ""
                ],
                is_fixable=True,
            )
            for start, _, _ in self._edits(content, rule_config)[:1]
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        edits = self._edits(content, rule_config)
        if not edits:
            return content
        chars = list(content)
        for start, end, replacement in edits:
            chars[start:end] = list(replacement)
        return "".join(chars)
