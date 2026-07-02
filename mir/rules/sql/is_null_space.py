import re
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class IsNullSpaceRule(BaseRule):
    rule_id = "IR-is-null-space"
    description = "Standardize spacing for null predicates (ISNULL -> IS NULL, ISNOTNULL -> IS NOT NULL)."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE activeISNULL;",
            "correct": "SELECT * FROM users WHERE active IS NULL;"
        },
        {
            "violating": "SELECT * FROM users WHERE ageISNOTNULL;",
            "correct": "SELECT * FROM users WHERE age IS NOT NULL;"
        }
    ]
    additional_validations = [
        "SELECT * FROM users WHERE age IS NULL;",
        "SELECT * FROM users WHERE age IS NOT NULL;",
        "SELECT 'isnull' AS str FROM users;"  # Should not touch strings
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        
        for tok in tokens:
            if tok["type"] in ("IDENTIFIER", "KEYWORD"):
                val = tok["value"]
                val_lower = val.lower()
                if val_lower.endswith("isnull"):
                    prefix = val[:-6]
                    violations.append({
                        "token": tok,
                        "replacement": (prefix + " IS NULL") if prefix else "IS NULL"
                    })
                elif val_lower.endswith("isnotnull"):
                    prefix = val[:-9]
                    violations.append({
                        "token": tok,
                        "replacement": (prefix + " IS NOT NULL") if prefix else "IS NOT NULL"
                    })
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["token"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message=f"Predicates must use standardized IS NULL / IS NOT NULL spacing (found: '{tok['value']}').",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        # Apply edits in reverse order
        edits = []
        for item in offending:
            tok = item["token"]
            edits.append((tok["start"], tok["end"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
