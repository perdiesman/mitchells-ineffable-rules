from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class FromSingleRule(BaseRule):
    rule_id = "IR-from-single"
    description = "Single FROM entry should be on the same line as the FROM keyword."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT id\nFROM\n    users;",
            "correct": "SELECT id\nFROM users;"
        }
    ]
    additional_validations = [
        'SELECT id\nFROM (SELECT * FROM raw_users) AS sub;'
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "FROM":
                outer_depth = depths[i]
                
                # Find end of FROM clause
                clause_end = n
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] == "SEMI":
                            clause_end = idx
                            break
                            
                # Scan FROM clause content
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                
                # Check for JOIN, COMMA, or subquery at depth outer_depth
                has_join = False
                has_comma = False
                has_subquery = False
                first_table_tok = None
                whitespace_before_table = []
                
                # We need to find the first code token inside the FROM clause
                for idx, (t, d) in enumerate(zip(clause_tokens, clause_depths)):
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() == "JOIN":
                            has_join = True
                        elif t["type"] == "COMMA":
                            has_comma = True
                        elif t["type"] != "WHITESPACE" and first_table_tok is None:
                            first_table_tok = t
                            whitespace_before_table = clause_tokens[:idx]
                    elif d > outer_depth and first_table_tok is None:
                        # If depth increases before finding a table, it could be a subquery
                        has_subquery = True
                        
                if first_table_tok and not has_join and not has_comma and not has_subquery:
                    # Single table entry! Verify line numbers
                    if first_table_tok["line"] != tok["line"]:
                        violations.append({
                            "from_tok": tok,
                            "table_tok": first_table_tok,
                            "ws_start": tok["end"],
                            "ws_end": first_table_tok["start"]
                        })
                        
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["from_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Single FROM entry should be on the same line as FROM.",
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
            # Replace all whitespace between FROM and the table token with a single space
            edits.append((item["ws_start"], item["ws_end"], " "))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
