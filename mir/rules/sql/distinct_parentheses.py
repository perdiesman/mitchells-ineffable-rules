from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren

class DistinctParenthesesRule(BaseRule):
    rule_id = "IR-distinct-parentheses"
    description = "Remove redundant parentheses around DISTINCT arguments, preserving DISTINCT ON (col) syntax."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT DISTINCT(id), name FROM users;",
            "correct": "SELECT DISTINCT id, name FROM users;"
        }
    ]
    additional_validations = [
        "SELECT DISTINCT ON (company_id) id, name FROM users;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        active = []
        for idx, t in enumerate(tokens):
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append((t, idx))
                
        num_active = len(active)
        i = 0
        while i < num_active:
            t, actual_idx = active[i]
            if t["type"] == "KEYWORD" and t["value"].upper() == "DISTINCT":
                # Check for DISTINCT ON
                if i + 1 < num_active and active[i+1][0]["type"] == "KEYWORD" and active[i+1][0]["value"].upper() == "ON":
                    i += 2
                    continue
                    
                # Check for DISTINCT(
                if i + 1 < num_active and active[i+1][0]["type"] == "PAREN" and active[i+1][0]["value"] == "(":
                    open_paren_idx = active[i+1][1]
                    close_paren_idx = find_matching_paren(tokens, open_paren_idx)
                    if close_paren_idx is not None:
                        # Extract the content inside the parentheses
                        open_tok = tokens[open_paren_idx]
                        close_tok = tokens[close_paren_idx]
                        inner_text = content[open_tok["end"]:close_tok["start"]]
                        
                        violations.append({
                            "token": t,
                            "start_offset": open_tok["start"],
                            "end_offset": close_tok["end"],
                            "replacement": f" {inner_text}",
                            "line": t["line"]
                        })
                        i += 2
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
                    message="Remove redundant parentheses around DISTINCT arguments.",
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
