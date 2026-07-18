from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class LikeNoWildcardRule(BaseRule):
    rule_id = "IR-like-no-wildcard"
    description = "Simplify LIKE comparisons to standard = comparisons when the pattern contains no wildcard characters (% or _)."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT * FROM users WHERE name LIKE 'Alice';",
            "correct": "SELECT * FROM users WHERE name = 'Alice';"
        }
    ]
    additional_validations = [
        "SELECT * FROM users WHERE name LIKE 'A%';",
        "SELECT * FROM users WHERE name LIKE 'A_c';",
        "SELECT * FROM users WHERE name ILIKE 'Alice';"
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
            if t["value"].upper() == "LIKE":
                # Check next token is string literal
                if i + 1 < num_active:
                    next_t = active[i + 1]
                    if next_t["type"] == "STRING":
                        val = next_t["value"]
                        # Strip outer quotes (single or double)
                        if len(val) >= 2 and val[0] in ("'", '"') and val[-1] == val[0]:
                            inner = val[1:-1]
                        else:
                            inner = val
                        
                        if "%" not in inner and "_" not in inner:
                            violations.append({
                                "token": t,
                                "line": t["line"],
                                "start_offset": t["start"],
                                "end_offset": t["end"],
                                "message": f"Simplify LIKE to = on line {t['line']} as it contains no wildcards."
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
            edits.append((item["start_offset"], item["end_offset"], "="))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
