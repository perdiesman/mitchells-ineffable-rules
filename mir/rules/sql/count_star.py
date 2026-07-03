from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class CountStarRule(BaseRule):
    rule_id = "IR-count-star"
    description = "Standardize COUNT(1) or row-counting expressions to COUNT(*)."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT COUNT(1) FROM users;",
            "correct": "SELECT COUNT(*) FROM users;"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        active = []
        for idx, t in enumerate(tokens):
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)
                
        num_active = len(active)
        i = 0
        while i < num_active:
            t = active[i]
            if t["type"] in ("IDENTIFIER", "KEYWORD") and t["value"].upper() == "COUNT":
                if i + 3 < num_active:
                    t1 = active[i + 1]
                    t2 = active[i + 2]
                    t3 = active[i + 3]
                    if (
                        t1["type"] == "PAREN" and t1["value"] == "("
                        and t2["type"] in ("NUMBER", "STRING") and t2["value"] in ("1", "0", "'1'", '"1"')
                        and t3["type"] == "PAREN" and t3["value"] == ")"
                    ):
                        violations.append({
                            "token": t,
                            "start_offset": t1["start"],
                            "end_offset": t3["end"],
                            "replacement": "(*)",
                            "line": t["line"]
                        })
                        i += 4
                        continue
            i += 1
            
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
                    message="Standardize row-counting expressions to COUNT(*).",
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
