from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class TruncateTableRule(BaseRule):
    rule_id = "IR-truncate-table"
    description = "Prefer TRUNCATE table_name over DELETE FROM table_name with no conditions."
    category = "data-modification"
    is_fixable = "no"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "DELETE FROM users;",
            "correct": "TRUNCATE users;"
        }
    ]
    additional_validations = [
        "DELETE FROM users WHERE id = 1;",
        "DELETE FROM users USING logs WHERE logs.user_id = users.id;"
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
            if t["type"] == "KEYWORD" and t["value"].upper() == "DELETE":
                if i + 1 < num_active and active[i + 1]["value"].upper() == "FROM":
                    idx = i + 2
                    # Skip table reference (identifiers and dots)
                    while idx < num_active and active[idx]["type"] in ("IDENTIFIER", "DOT"):
                        idx += 1
                    
                    # Scan until end of statement to see if WHERE is present
                    has_where = False
                    depth = 0
                    while idx < num_active:
                        tok = active[idx]
                        if tok["type"] == "PAREN" and tok["value"] == "(":
                            depth += 1
                        elif tok["type"] == "PAREN" and tok["value"] == ")":
                            depth -= 1
                        
                        # Stop scanning at semicolon or start of next command
                        if depth == 0:
                            if tok["value"] == ";":
                                break
                            if tok["type"] == "KEYWORD" and tok["value"].upper() in (
                                "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "BEGIN", "DECLARE"
                            ):
                                break
                            if tok["type"] == "KEYWORD" and tok["value"].upper() == "WHERE":
                                has_where = True
                                break
                        idx += 1
                    
                    if not has_where:
                        violations.append({
                            "token": t,
                            "line": t["line"],
                            "message": f"Prefer TRUNCATE over DELETE FROM with no conditions on line {t['line']}."
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
