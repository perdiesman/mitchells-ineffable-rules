from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class SelectWildcardRule(BaseRule):
    rule_id = "IR-select-wildcard"
    description = "Avoid wildcard SELECT * in query headers and subqueries; explicitly list columns instead."
    category = "queries"
    is_fixable = "no"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT * FROM users;",
            "correct": "SELECT id, name, email FROM users;"
        },
        {
            "violating": "SELECT u.* FROM users u;",
            "correct": "SELECT u.id, u.name FROM users u;"
        }
    ]
    additional_validations = [
        "SELECT count(*) FROM users;",
        "SELECT count(1) FROM users;",
        "SELECT id, name FROM users WHERE id IN (SELECT user_id FROM profiles);"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)

        # Filter active tokens
        active = []
        for t in tokens:
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)

        num_active = len(active)
        stack = []
        in_select = False

        for idx, t in enumerate(active):
            val_upper = t["value"].upper()

            if t["type"] == "KEYWORD" and val_upper == "SELECT":
                in_select = True
            elif t["type"] == "KEYWORD" and val_upper in ("FROM", "INTO", "WHERE", "GROUP", "ORDER", "LIMIT", "UNION", "INTERSECT", "EXCEPT", "DECLARE", "BEGIN"):
                in_select = False
            elif t["type"] == "PAREN" and t["value"] == "(":
                # Check if function call
                is_fn = False
                if idx > 0:
                    prev = active[idx - 1]
                    if prev["type"] in ("IDENTIFIER", "KEYWORD") and prev["value"].upper() not in ("SELECT", "FROM", "WHERE", "AND", "OR", "ON", "IN", "NOT"):
                        is_fn = True
                stack.append({"in_select": in_select, "is_fn_call": is_fn})
                if is_fn:
                    in_select = False
            elif t["type"] == "PAREN" and t["value"] == ")":
                if stack:
                    state = stack.pop()
                    in_select = state["in_select"]
                else:
                    in_select = False
            elif t["value"] == "*":
                if in_select:
                    # Find original token index for accurate line reporting
                    orig_token = t
                    violations.append({
                        "token": orig_token,
                        "line": orig_token["line"],
                        "message": f"Avoid wildcard '*' in SELECT list on line {orig_token['line']}."
                    })

        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        for v in offending:
            line_idx = v["line"] - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=v["line"],
                message=v["message"],
                offending_lines=[offending_line],
                is_fixable=False
            ))
        return violations
