from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class CaseWhenWhenRule(BaseRule):
    rule_id = "IR-case-when-when"
    description = "Remove duplicate adjacent WHEN keywords."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT CASE WHEN WHEN active = true THEN 1 ELSE 0 END FROM users;",
            "correct": "SELECT CASE WHEN active = true THEN 1 ELSE 0 END FROM users;"
        }
    ]
    additional_validations = [
        "SELECT CASE WHEN active = true THEN 1 ELSE 0 END FROM users;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        for i in range(n):
            tok1 = tokens[i]
            if tok1["type"] == "KEYWORD" and tok1["value"].upper() == "WHEN":
                # Find next active token
                next_tok = None
                whitespace_tokens = []
                for idx in range(i + 1, n):
                    if tokens[idx]["type"] == "WHITESPACE":
                        whitespace_tokens.append(tokens[idx])
                    else:
                        next_tok = tokens[idx]
                        break
                        
                if next_tok and next_tok["type"] == "KEYWORD" and next_tok["value"].upper() == "WHEN":
                    # Duplicate WHEN found! We will delete tok1 and the trailing whitespace
                    end_idx = next_tok["start"]
                    violations.append({
                        "start": tok1["start"],
                        "end": end_idx,
                        "line": tok1["line"]
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
                    message="Duplicate WHEN keyword found.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
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
            edits.append((item["start"], item["end"], ""))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
