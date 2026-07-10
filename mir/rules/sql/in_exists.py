from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class InExistsRule(BaseRule):
    rule_id = "IR-in-exists"
    description = "EXISTS is preferred over IN with a subquery."
    category = "queries"
    is_fixable = "no"
    enabled_by_default = True
    
    default_config = {
        "severity": "warning"
    }
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE id IN (SELECT user_id FROM roles);"
        }
    ]
    additional_validations = [
        "SELECT * FROM users WHERE EXISTS (SELECT 1 FROM roles WHERE roles.user_id = users.id);"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i in range(n - 2):
            tok = tokens[i]
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "IN":
                # Check next active token is '('
                next_paren_idx = None
                for idx in range(i + 1, n):
                    if tokens[idx]["type"] == "WHITESPACE":
                        continue
                    if tokens[idx]["type"] == "PAREN" and tokens[idx]["value"] == "(":
                        next_paren_idx = idx
                    break
                    
                if next_paren_idx is not None:
                    # Check first active token after '(' is 'SELECT'
                    next_select_idx = None
                    for idx in range(next_paren_idx + 1, n):
                        if tokens[idx]["type"] == "WHITESPACE":
                            continue
                        if tokens[idx]["type"] == "KEYWORD" and tokens[idx]["value"].upper() == "SELECT":
                            next_select_idx = idx
                        break
                        
                    if next_select_idx is not None:
                        violations.append({
                            "token": tok
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
                    message="EXISTS is generally preferred over IN with a subquery.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=False
                )
            )
        return violations
