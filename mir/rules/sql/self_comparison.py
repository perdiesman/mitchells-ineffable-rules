from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class SelfComparisonRule(BaseRule):
    rule_id = "IR-self-comparison"
    description = "Detect redundant self-comparisons where a column/identifier is compared to itself (e.g. x = x)."
    category = "queries"
    is_fixable = "no"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT * FROM users WHERE age = age;",
            "correct": "SELECT * FROM users WHERE age = 21;"
        },
        {
            "violating": "SELECT * FROM users u WHERE u.id = u.id;",
            "correct": "SELECT * FROM users u WHERE u.id = 100;"
        }
    ]
    additional_validations = [
        "SELECT * FROM users WHERE 1 = 1;",
        "SELECT * FROM users WHERE true = true;",
        "SELECT * FROM users u JOIN profiles p ON u.id = p.user_id;"
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
        i = 0
        while i < num_active:
            t = active[i]
            if t["type"] == "OPERATOR" and t["value"] in ("=", "!=", "<>", "<", ">", "<=", ">="):
                # Resolve left operand path if it is an identifier path
                left_path = []
                if i > 0:
                    if active[i - 1]["type"] == "IDENTIFIER":
                        if i - 3 >= 0 and active[i - 2]["type"] == "DOT" and active[i - 3]["type"] == "IDENTIFIER":
                            left_path = [active[i - 3]["value"].lower(), active[i - 2]["value"], active[i - 1]["value"].lower()]
                        else:
                            left_path = [active[i - 1]["value"].lower()]

                # Resolve right operand path if it is an identifier path
                right_path = []
                if i + 1 < num_active:
                    if active[i + 1]["type"] == "IDENTIFIER":
                        if i + 3 < num_active and active[i + 2]["type"] == "DOT" and active[i + 3]["type"] == "IDENTIFIER":
                            right_path = [active[i + 1]["value"].lower(), active[i + 2]["value"], active[i + 3]["value"].lower()]
                        else:
                            right_path = [active[i + 1]["value"].lower()]

                if left_path and right_path and left_path == right_path:
                    if left_path[-1] not in ("true", "false", "null"):
                        path_str = "".join(left_path)
                        violations.append({
                            "token": t,
                            "line": t["line"],
                            "message": f"Redundant self-comparison of '{path_str}' on line {t['line']}."
                        })
            i += 1

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
