from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class SelectCommaRule(BaseRule):
    rule_id = "IR-select-comma"
    description = "Missing commas between SELECT columns split across lines should be inserted."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT\n    id\n    name\nFROM users;",
            "correct": "SELECT\n    id,\n    name\nFROM users;"
        }
    ]
    additional_validations = [
        'SELECT id AS user_id FROM users;'
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "SELECT":
                outer_depth = depths[i]
                
                # Find end of SELECT clause
                clause_end = n
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "FROM", "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] in ("SEMI", "PAREN"):
                            clause_end = idx
                            break
                            
                # Get all non-whitespace, non-comment tokens at depth 0 inside select list
                select_tokens = []
                for idx in range(i + 1, clause_end):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth and t["type"] not in ("WHITESPACE", "COMMENT"):
                        select_tokens.append(t)
                        
                # Check adjacent tokens
                for j in range(len(select_tokens) - 1):
                    t1 = select_tokens[j]
                    t2 = select_tokens[j + 1]
                    
                    if t2["line"] > t1["line"]:
                        # Verify neither is comma and other skipped keywords
                        if t1["type"] != "COMMA" and t2["type"] != "COMMA":
                            v1 = t1["value"].upper()
                            v2 = t2["value"].upper()
                            if v1 not in ("SELECT", "DISTINCT", "AS") and v2 not in ("AS",):
                                violations.append({
                                    "insert_after_tok": t1
                                })
                                
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["insert_after_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Missing comma between SELECT columns split across lines.",
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
            tok = item["insert_after_tok"]
            edits.append((tok["end"], tok["end"], ","))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
