from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class TrailingSemicolonRule(BaseRule):
    rule_id = "IR-trailing-semicolon"
    description = "Enforce that the last SQL statement ends with a trailing semicolon."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users",
            "correct": "SELECT * FROM users;"
        }
    ]
    additional_validations = [
        'SELECT * FROM users; -- comment at end'
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        
        # Find the last active token (non-whitespace, non-comment)
        last_active = None
        for t in reversed(tokens):
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                last_active = t
                break
                
        if last_active and last_active["value"] != ";":
            violations.append({
                "token": last_active,
                "insert_pos": last_active["end"],
                "line": last_active["line"]
            })
            
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
                    message="SQL statement should end with a semicolon.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        # Since we only insert at one position at the very end, we just apply the first edit
        item = offending[0]
        pos = item["insert_pos"]
        return content[:pos] + ";" + content[pos:]
