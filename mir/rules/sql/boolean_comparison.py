from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class BooleanComparisonRule(BaseRule):
    commit_profile = True
    commit_semantic_rewrite = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-boolean-comparison"
    description = "Standardize boolean comparison predicates to use idiomatic boolean predicates."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE active = true AND blocked = false;",
            "correct": "SELECT * FROM users WHERE active AND NOT blocked;"
        },
        {
            "violating": "SELECT * FROM users WHERE active != true OR blocked <> false;",
            "correct": "SELECT * FROM users WHERE NOT active OR blocked;"
        },
        {
            "violating": "SELECT id FROM sample WHERE coalesce(enabled, false) = false AND #{includeHidden} = true;",
            "correct": "SELECT id FROM sample WHERE NOT coalesce(enabled, false) AND #{includeHidden};"
        },
        {
            "violating": "SELECT id FROM sample WHERE (#{scope} = 'all') IS TRUE;",
            "correct": "SELECT id FROM sample WHERE (#{scope} = 'all');"
        }
    ]
    additional_validations = [
        "SELECT enabled = TRUE AS is_enabled FROM sample;",
        "UPDATE sample SET enabled = FALSE WHERE id = 1;",
        "SELECT id FROM sample WHERE FALSE = ANY(flags);",
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        active = [
            token for token in tokens if token["type"] not in ("WHITESPACE", "COMMENT")
        ]

        def matching_open(close_position: int) -> int | None:
            depth = 0
            for position in range(close_position, -1, -1):
                token = active[position]
                if token["type"] != "PAREN":
                    continue
                if token["value"] == ")":
                    depth += 1
                elif token["value"] == "(":
                    depth -= 1
                    if depth == 0:
                        return position
            return None

        def operand_start(end_position: int) -> int | None:
            if end_position < 0:
                return None
            token = active[end_position]
            if token["type"] == "PAREN" and token["value"] == ")":
                start = matching_open(end_position)
                if start is None:
                    return None
                # Include a qualified function name, but retain grouping
                # parentheses when they are the expression itself.
                if start > 0 and active[start - 1]["type"] in {"IDENTIFIER", "KEYWORD"}:
                    start -= 1
                    while (
                        start >= 2
                        and active[start - 1]["type"] == "DOT"
                        and active[start - 2]["type"] in {"IDENTIFIER", "KEYWORD"}
                    ):
                        start -= 2
                return start
            if token["type"] not in {"IDENTIFIER", "KEYWORD", "PARAM"}:
                return None
            start = end_position
            while (
                start >= 2
                and active[start - 1]["type"] == "DOT"
                and active[start - 2]["type"] in {"IDENTIFIER", "KEYWORD"}
            ):
                start -= 2
            return start

        def in_predicate_context(start_position: int) -> bool:
            predicate_markers = {"WHERE", "HAVING", "ON", "WHEN", "AND", "OR"}
            boundaries = {
                "SELECT", "FROM", "GROUP", "ORDER", "LIMIT", "SET", "VALUES",
                "RETURNING", "THEN", "ELSE", ";",
            }
            depth = 0
            for position in range(start_position - 1, -1, -1):
                token = active[position]
                if token["type"] == "PAREN":
                    depth += 1 if token["value"] == ")" else -1
                    continue
                if depth > 0:
                    continue
                value = token["value"].upper()
                if value in predicate_markers:
                    return True
                if value in boundaries:
                    return False
            return False

        position = 0
        while position < len(active) - 1:
            operator = active[position]
            value_token = active[position + 1]
            value = value_token["value"].upper()
            is_boolean = value_token["type"] in {"KEYWORD", "IDENTIFIER"} and value in {
                "TRUE", "FALSE",
            }
            comparison = operator["type"] == "OPERATOR" and operator["value"] in {
                "=", "!=", "<>",
            }
            is_predicate = operator["value"].upper() == "IS"
            if not is_boolean or not (comparison or is_predicate):
                position += 1
                continue

            if is_predicate and value == "TRUE" and in_predicate_context(position):
                # Removing the suffix works for an arbitrarily complex
                # predicate, including ``parameter = value IS TRUE``.
                violations.append({
                    "start_offset": active[position - 1]["end"],
                    "end_offset": value_token["end"],
                    "line": operator["line"],
                    "replacement": "",
                })
                position += 2
                continue

            start_position = operand_start(position - 1)
            if start_position is None or not in_predicate_context(start_position):
                position += 1
                continue

            expression_start = active[start_position]["start"]
            expression_end = active[position - 1]["end"]
            expression = content[expression_start:expression_end].strip()
            positive = operator["value"] in {"=", "IS"}
            retain_expression = (value == "TRUE") == positive
            replacement = expression if retain_expression else f"NOT {expression}"
            violations.append({
                "start_offset": expression_start,
                "end_offset": value_token["end"],
                "line": active[start_position]["line"],
                "replacement": replacement,
            })
            position += 2
            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message="Standardize boolean comparisons to clean boolean predicates.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        edits = []
        for item in offending:
            edits.append((item["start_offset"], item["end_offset"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
