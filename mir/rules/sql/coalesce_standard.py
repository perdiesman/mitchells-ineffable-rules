from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class CoalesceStandardRule(BaseRule):
    rule_id = "IR-coalesce-standard"
    description = "Use standard COALESCE instead of dialect-specific null-handling functions like NVL, IFNULL, or ISNULL."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT NVL(val, 0) FROM users;",
            "correct": "SELECT COALESCE(val, 0) FROM users;"
        },
        {
            "violating": "SELECT IFNULL(val, 0) FROM users;",
            "correct": "SELECT COALESCE(val, 0) FROM users;"
        },
        {
            "violating": "SELECT ISNULL(val, 0) FROM users;",
            "correct": "SELECT COALESCE(val, 0) FROM users;"
        }
    ]
    additional_validations = [
        "SELECT COALESCE(val, 0) FROM users;"
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
            val_upper = t["value"].upper()
            if t["type"] in ("IDENTIFIER", "KEYWORD") and val_upper in ("NVL", "IFNULL", "ISNULL"):
                # Check if followed by (
                if i + 1 < num_active and active[i + 1]["type"] == "PAREN" and active[i + 1]["value"] == "(":
                    violations.append({
                        "token": t,
                        "line": t["line"],
                        "start_offset": t["start"],
                        "end_offset": t["end"],
                        "message": f"Use standard COALESCE instead of dialect-specific '{t['value']}' function on line {t['line']}."
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
                is_fixable=True
            ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        edits = []
        for item in offending:
            edits.append((item["start_offset"], item["end_offset"], "COALESCE"))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
