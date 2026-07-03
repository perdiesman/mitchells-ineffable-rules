from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class WhereSingleRule(BaseRule):
    rule_id = "IR-where-single"
    description = "Single WHERE condition should be on the same line as the WHERE keyword."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT id FROM users\nWHERE\n    active = true;",
            "correct": "SELECT id FROM users\nWHERE active = true;"
        }
    ]
    additional_validations = [
        "SELECT id FROM users WHERE active = true;",
        "SELECT id FROM users WHERE active = true AND age > 21;" # Multi-condition is skipped here
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "WHERE":
                outer_depth = depths[i]
                
                # Find end of WHERE clause
                clause_end = n
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if d < outer_depth:
                        clause_end = idx
                        break
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "GROUP", "ORDER", "LIMIT", "HAVING", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] == "SEMI":
                            clause_end = idx
                            break
                            
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                
                # Check for AND/OR at depth outer_depth
                has_logical = False
                first_cond_tok = None
                
                for idx, (t, d) in enumerate(zip(clause_tokens, clause_depths)):
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("AND", "OR"):
                            has_logical = True
                            break
                        elif t["type"] != "WHITESPACE" and first_cond_tok is None:
                            first_cond_tok = t
                            
                if first_cond_tok and not has_logical:
                    # Single condition! Verify line numbers
                    if first_cond_tok["line"] != tok["line"]:
                        violations.append({
                            "where_tok": tok,
                            "cond_tok": first_cond_tok,
                            "ws_start": tok["end"],
                            "ws_end": first_cond_tok["start"]
                        })
                        
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["where_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Single WHERE condition should be on the same line as WHERE.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
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
            edits.append((item["ws_start"], item["ws_end"], " "))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
