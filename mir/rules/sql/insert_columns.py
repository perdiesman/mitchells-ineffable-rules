from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class InsertColumnsRule(BaseRule):
    rule_id = "IR-insert-columns"
    description = "Ensure INSERT statements explicitly list target columns."
    category = "queries"
    is_fixable = "no"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "INSERT INTO users VALUES (1, 'Alice');",
            "correct": "INSERT INTO users (id, name) VALUES (1, 'Alice');"
        },
        {
            "violating": "INSERT INTO users SELECT * FROM temp_users;",
            "correct": "INSERT INTO users (id, name) SELECT id, name FROM temp_users;"
        }
    ]
    additional_validations = [
        "INSERT INTO schema.users (id, name) VALUES (1, 'Alice');",
        "INSERT INTO users (id) SELECT id FROM temp_users;"
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
            if t["type"] == "KEYWORD" and t["value"].upper() == "INSERT":
                if i + 1 < num_active and active[i + 1]["value"].upper() == "INTO":
                    idx = i + 2
                    # Skip table reference (identifiers and dots)
                    while idx < num_active and active[idx]["type"] in ("IDENTIFIER", "DOT"):
                        idx += 1
                    
                    if idx < num_active:
                        next_t = active[idx]
                        if next_t["type"] != "PAREN" or next_t["value"] != "(":
                            violations.append({
                                "token": t,
                                "line": t["line"],
                                "message": f"INSERT statement on line {t['line']} is missing an explicit column list."
                            })
                        else:
                            # It is '('. Check if the first active token inside is SELECT or WITH
                            if idx + 1 < num_active:
                                inner_t = active[idx + 1]
                                if inner_t["type"] == "KEYWORD" and inner_t["value"].upper() in ("SELECT", "WITH"):
                                    violations.append({
                                        "token": t,
                                        "line": t["line"],
                                        "message": f"INSERT statement on line {t['line']} is missing an explicit column list."
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
