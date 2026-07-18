from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths, find_datatype_token_groups

class AliasAsRule(BaseRule):
    rule_id = "IR-alias-as"
    description = "Column aliases must use the AS keyword."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT id user_id, name customer_name FROM users;",
            "correct": "SELECT id AS user_id, name AS customer_name FROM users;"
        }
    ]
    additional_validations = [
        "SELECT id AS user_id FROM users;",
        "SELECT COUNT(*) AS cnt FROM users;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        datatype_groups = find_datatype_token_groups(tokens, content)
        datatype_tok_ids = {id(tok) for group in datatype_groups for tok in group}
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
                    if d < outer_depth:
                        clause_end = idx
                        break
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "FROM", "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] == "SEMI":
                            clause_end = idx
                            break
                            
                # Get tokens inside SELECT list at depth 0
                select_tokens = tokens[i + 1:clause_end]
                select_depths = depths[i + 1:clause_end]
                
                # Split select_tokens by depth-0 COMMA to isolate select items
                items = []
                current_item = []
                for t, d in zip(select_tokens, select_depths):
                    if d == outer_depth and t["type"] == "COMMA":
                        items.append(current_item)
                        current_item = []
                    else:
                        current_item.append(t)
                if current_item:
                    items.append(current_item)
                    
                # Inspect each select item
                for item_idx, item in enumerate(items):
                    active = [t for t in item if t["type"] not in ("WHITESPACE", "COMMENT")]
                    if item_idx == 0 and active and active[0]["value"].upper() in ("DISTINCT", "ALL"):
                        active = active[1:]
                    if len(active) >= 2:
                        last_tok = active[-1]
                        # Skip if it is part of a data type name
                        if id(last_tok) in datatype_tok_ids:
                            continue
                        # Check if last token is identifier (column alias)
                        if last_tok["type"] == "IDENTIFIER":
                            prev_tok = active[-2]
                            if id(prev_tok) in datatype_tok_ids:
                                continue
                            if prev_tok["value"] == ".":
                                continue
                            if prev_tok["type"] in ("OPERATOR", "CAST"):
                                continue
                            if prev_tok["value"].upper() in ("AND", "OR", "NOT", "IN", "LIKE", "IS", "BETWEEN", "CASE", "WHEN", "THEN", "ELSE", "END"):
                                continue
                            if prev_tok["type"] != "KEYWORD" or prev_tok["value"].upper() != "AS":
                                # Violation! Missing AS
                                violations.append({
                                    "alias_tok": last_tok
                                })
                                
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["alias_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message=f"Missing AS keyword before column alias '{tok['value']}'.",
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
            tok = item["alias_tok"]
            edits.append((tok["start"], tok["start"], "AS "))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
