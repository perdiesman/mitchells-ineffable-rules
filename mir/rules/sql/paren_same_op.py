from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren, get_token_depths

class ParenSameOpRule(BaseRule):
    rule_id = "IR-paren-same-op"
    description = "Unnecessary parentheses around homogeneous logical conditions should be removed."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT id FROM users WHERE (active = true AND type = 'admin' AND age > 21);",
            "correct": "SELECT id FROM users WHERE active = true AND type = 'admin' AND age > 21;"
        }
    ]
    additional_validations = [
        "SELECT id FROM users WHERE (active = true AND type = 'admin') OR age > 21;",
        "SELECT id FROM users WHERE active = true AND (type = 'admin' OR age > 21);",
        "SELECT id FROM users WHERE (active = true);"  # Checked by IR-paren-single, skip here
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        depths = get_token_depths(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "PAREN" and tok["value"] == "(":
                close_idx = find_matching_paren(tokens, i)
                if close_idx is None:
                    continue
                    
                # 1. Subquery check
                next_active = None
                for idx in range(i + 1, close_idx):
                    if tokens[idx]["type"] != "WHITESPACE":
                        next_active = tokens[idx]
                        break
                if next_active and next_active["type"] == "KEYWORD" and next_active["value"].upper() == "SELECT":
                    continue
                    
                # 2. Function call & special keyword check
                prev_active = None
                prev_active_idx = -1
                for idx in range(i - 1, -1, -1):
                    if tokens[idx]["type"] != "WHITESPACE":
                        prev_active = tokens[idx]
                        prev_active_idx = idx
                        break
                        
                is_special = False
                if prev_active:
                    val_upper = prev_active["value"].upper()
                    if val_upper == "ON":
                        # Check DISTINCT ON
                        prev_prev = None
                        for p_idx in range(prev_active_idx - 1, -1, -1):
                            if tokens[p_idx]["type"] != "WHITESPACE":
                                prev_prev = tokens[p_idx]
                                break
                        if prev_prev and prev_prev["value"].upper() == "DISTINCT":
                            is_special = True
                    elif val_upper == "OVER":
                        is_special = True
                    elif prev_active["type"] == "IDENTIFIER":
                        is_special = True
                    elif prev_active["type"] == "KEYWORD" and val_upper in ("COUNT", "COALESCE", "SUM", "AVG", "MIN", "MAX", "CONCAT", "SUBSTR", "DATE_PART", "NOW", "STRING_AGG", "DATE"):
                        is_special = True
                        
                if is_special:
                    continue
                    
                # Extract inner tokens and their depth relative to the open paren
                inner_tokens = tokens[i + 1:close_idx]
                inner_depths = depths[i + 1:close_idx]
                base_depth = depths[i] + 1
                
                # Check logical operators at depth 0
                ops_seen = set()
                has_sub_select_or_comma = False
                for t, d in zip(inner_tokens, inner_depths):
                    if d == base_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("AND", "OR"):
                            ops_seen.add(t["value"].upper())
                        elif t["type"] in ("COMMA", "KEYWORD") and t["value"].upper() in ("SELECT", ","):
                            has_sub_select_or_comma = True
                            break
                            
                if has_sub_select_or_comma or len(ops_seen) != 1:
                    continue
                    
                op = list(ops_seen)[0]
                opposite_op = "OR" if op == "AND" else "AND"
                
                # Check if opposite operator is outside at depth depths[i]
                outer_depth = depths[i]
                has_opposite = False
                
                # Walk backward
                for idx in range(i - 1, -1, -1):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("SELECT", "FROM", "WHERE", "HAVING", "LIMIT", "ORDER", "GROUP"):
                            break
                        if t["type"] == "KEYWORD" and t["value"].upper() == opposite_op:
                            has_opposite = True
                            break
                        if t["type"] == "SEMI":
                            break
                            
                # Walk forward
                if not has_opposite:
                    for idx in range(close_idx + 1, n):
                        t = tokens[idx]
                        d = depths[idx]
                        if d == outer_depth:
                            if t["type"] == "KEYWORD" and t["value"].upper() in ("SELECT", "FROM", "WHERE", "HAVING", "LIMIT", "ORDER", "GROUP"):
                                break
                            if t["type"] == "KEYWORD" and t["value"].upper() == opposite_op:
                                has_opposite = True
                                break
                            if t["type"] == "SEMI":
                                break
                                
                if has_opposite:
                    continue
                    
                # Check next token for CAST
                next_after_close = None
                for idx in range(close_idx + 1, n):
                    if tokens[idx]["type"] != "WHITESPACE":
                        next_after_close = tokens[idx]
                        break
                if next_after_close and next_after_close["type"] == "CAST":
                    continue
                    
                violations.append({
                    "open_tok": tok,
                    "close_tok": tokens[close_idx]
                })
                
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending_pairs = self._find_violations(content)
        
        for pair in offending_pairs:
            tok = pair["open_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Unnecessary parentheses around homogeneous logical conditions.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending_pairs = self._find_violations(content)
        if not offending_pairs:
            return content
            
        tokens = tokenize_sql(content)
        edits = []
        for pair in offending_pairs:
            open_tok = pair["open_tok"]
            close_tok = pair["close_tok"]
            
            try:
                open_idx = tokens.index(open_tok)
                close_idx = tokens.index(close_tok)
            except ValueError:
                continue
                
            open_start = open_tok["start"]
            open_end = open_tok["end"]
            open_rep = ""
            
            if open_idx + 1 < len(tokens) and tokens[open_idx + 1]["type"] == "WHITESPACE":
                open_end = tokens[open_idx + 1]["end"]
                if open_idx - 1 >= 0 and tokens[open_idx - 1]["type"] != "WHITESPACE":
                    open_rep = " "
            elif open_idx - 1 >= 0 and tokens[open_idx - 1]["type"] != "WHITESPACE":
                open_rep = " "
                
            close_start = close_tok["start"]
            close_end = close_tok["end"]
            
            if close_idx - 1 >= 0 and tokens[close_idx - 1]["type"] == "WHITESPACE":
                close_start = tokens[close_idx - 1]["start"]
                
            edits.append((open_start, open_end, open_rep))
            edits.append((close_start, close_end, ""))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
