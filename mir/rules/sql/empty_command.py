from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class EmptyCommandRule(BaseRule):
    rule_id = "IR-empty-command"
    description = "Remove empty SQL commands, such as duplicate semicolons or leading semicolons."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": ";\nSELECT id FROM users;;",
            "correct": "SELECT id FROM users;"
        }
    ]
    additional_validations = [
        "SELECT 'a;b' FROM users;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        # 1. Check for leading semicolon
        first_non_whitespace_idx = None
        for i in range(n):
            if tokens[i]["type"] not in ("WHITESPACE", "COMMENT"):
                first_non_whitespace_idx = i
                break
                
        if first_non_whitespace_idx is not None:
            first_tok = tokens[first_non_whitespace_idx]
            if first_tok["type"] == "SEMI":
                # Mark everything from start of file to this semicolon, plus subsequent whitespace, for removal
                end_idx = first_tok["end"]
                if first_non_whitespace_idx + 1 < n and tokens[first_non_whitespace_idx + 1]["type"] == "WHITESPACE":
                    end_idx = tokens[first_non_whitespace_idx + 1]["end"]
                violations.append({
                    "start": 0,
                    "end": end_idx,
                    "line": first_tok["line"],
                    "reason": "leading semicolon"
                })
                
        # 2. Check for consecutive semicolons
        for i in range(n):
            tok = tokens[i]
            if tok["type"] == "SEMI":
                # Find next active token
                next_tok = None
                whitespace_tokens = []
                for idx in range(i + 1, n):
                    if tokens[idx]["type"] == "WHITESPACE":
                        whitespace_tokens.append(tokens[idx])
                    else:
                        next_tok = tokens[idx]
                        break
                if next_tok and next_tok["type"] == "SEMI":
                    # Mark the gap and the second semicolon for deletion
                    violations.append({
                        "start": tok["end"],
                        "end": next_tok["end"],
                        "line": next_tok["line"],
                        "reason": "duplicate semicolon"
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
                    message=f"Empty command found ({item['reason']}).",
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
