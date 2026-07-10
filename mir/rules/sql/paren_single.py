from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren, get_token_depths

class ParenSingleRule(BaseRule):
    rule_id = "IR-paren-single"
    description = "Unnecessary parentheses around a single condition should be removed."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT id FROM users WHERE (active = true);",
            "correct": "SELECT id FROM users WHERE active = true;"
        },
        {
            "violating": "SELECT (id)::integer FROM users;",
            "correct": "SELECT id::integer FROM users;"
        }
    ]
    additional_validations = [
        "SELECT (a + b)::integer FROM users;",
        "SELECT COALESCE(id, 0) FROM users;",
        "SELECT id FROM users WHERE (active = true AND type = 'admin');"
    ]

    def _is_simple_atom(self, tokens: List[dict]) -> bool:
        depths = get_token_depths(tokens)
        for tok, d in zip(tokens, depths):
            if d == 0 and tok["type"] in ("OPERATOR", "KEYWORD") and tok["value"].upper() in ("AND", "OR", "+", "-", "*", "/", "%", "=", "<>", "<=", ">=", "!=", "<", ">", "||"):
                return False
        return True

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
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
                    
                # Extract inner tokens
                inner_tokens = tokens[i + 1:close_idx]
                inner_active = [t for t in inner_tokens if t["type"] != "WHITESPACE"]
                if not inner_active:
                    continue
                    
                # Check for comma, AND, OR, SELECT at depth 0 inside the paren
                inner_depths = get_token_depths(inner_tokens)
                has_multi = False
                for t, d in zip(inner_tokens, inner_depths):
                    if d == 0:
                        if t["type"] in ("COMMA", "KEYWORD") and t["value"].upper() in ("AND", "OR", "SELECT", ","):
                            has_multi = True
                            break
                if has_multi:
                    continue
                    
                # Check next token for CAST
                next_after_close = None
                for idx in range(close_idx + 1, n):
                    if tokens[idx]["type"] != "WHITESPACE":
                        next_after_close = tokens[idx]
                        break
                if next_after_close and next_after_close["type"] == "CAST":
                    if not self._is_simple_atom(inner_tokens):
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
                    message="Unnecessary parentheses around single condition.",
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
            
            # We only need a space if the token before '(' and the token after '(' are both "word-like"
            # (alphanumeric/operators) to prevent them from merging together (e.g. WHERE(active -> WHERE active).
            need_space = False
            if open_idx - 1 >= 0 and open_idx + 1 < len(tokens):
                prev_t = tokens[open_idx - 1]
                next_t = tokens[open_idx + 1]
                
                # If there's whitespace immediately inside the parenthesis, the next token is the one after the whitespace
                if next_t["type"] == "WHITESPACE" and open_idx + 2 < len(tokens):
                    next_t = tokens[open_idx + 2]
                
                def is_word_like(t):
                    return t["type"] in ("KEYWORD", "IDENTIFIER", "NUMBER", "OPERATOR") or (t["type"] == "OTHER" and t["value"].isalnum())
                    
                if is_word_like(prev_t) and is_word_like(next_t):
                    need_space = True
            
            if open_idx + 1 < len(tokens) and tokens[open_idx + 1]["type"] == "WHITESPACE":
                open_end = tokens[open_idx + 1]["end"]
                if open_idx - 1 >= 0 and tokens[open_idx - 1]["type"] != "WHITESPACE" and need_space:
                    open_rep = " "
            elif open_idx - 1 >= 0 and tokens[open_idx - 1]["type"] != "WHITESPACE" and need_space:
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
