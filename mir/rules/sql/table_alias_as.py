from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths, find_clause_end

class TableAliasAsRule(BaseRule):
    rule_id = "IR-table-alias-as"
    description = "Table and subquery aliases should not use the AS keyword."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users AS u LEFT JOIN roles AS r ON u.role_id = r.id;",
            "correct": "SELECT * FROM users u LEFT JOIN roles r ON u.role_id = r.id;"
        },
        {
            "violating": "SELECT * FROM (SELECT * FROM raw_users) AS sub;",
            "correct": "SELECT * FROM (SELECT * FROM raw_users) sub;"
        }
    ]
    additional_validations = [
        "SELECT * FROM users u;",
        "SELECT * FROM (SELECT a AS b FROM t) sub;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        seen_as_starts = set()
        
        clause_keywords = [
            "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT", "ON", "USING"
        ]
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() in ("FROM", "JOIN"):
                outer_depth = depths[i]
                clause_end = find_clause_end(tokens, depths, i, clause_keywords)
                            
                for idx in range(i + 1, clause_end):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth and t["type"] == "KEYWORD" and t["value"].upper() == "AS":
                        if t["start"] not in seen_as_starts:
                            seen_as_starts.add(t["start"])
                            
                            ws_before = None
                            if idx - 1 >= 0 and tokens[idx - 1]["type"] == "WHITESPACE":
                                ws_before = tokens[idx - 1]
                            ws_after = None
                            if idx + 1 < n and tokens[idx + 1]["type"] == "WHITESPACE":
                                ws_after = tokens[idx + 1]
                                
                            violations.append({
                                "as_tok": t,
                                "ws_before": ws_before,
                                "ws_after": ws_after
                            })
                            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["as_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Table/subquery alias should not use the AS keyword.",
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
            tok = item["as_tok"]
            ws_before = item["ws_before"]
            ws_after = item["ws_after"]
            
            start_offset = ws_before["start"] if ws_before else tok["start"]
            end_offset = ws_after["end"] if ws_after else tok["end"]
            
            edits.append((start_offset, end_offset, " "))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
