from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren, get_token_depths

class JoinParensRule(BaseRule):
    rule_id = "IR-join-parens"
    description = "Unnecessary parentheses around a JOIN clause should be removed."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM (t1 LEFT JOIN t2 ON t1.id = t2.id);",
            "correct": "SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id;"
        }
    ]
    additional_validations = [
        "SELECT * FROM (SELECT * FROM t1) AS sub LEFT JOIN t2 ON sub.id = t2.id;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        depths = get_token_depths(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "PAREN" and tok["value"] == "(":
                close_idx = find_matching_paren(tokens, i)
                if close_idx is None:
                    continue
                    
                inner_tokens = tokens[i + 1:close_idx]
                inner_depths = depths[i + 1:close_idx]
                base_depth = depths[i] + 1
                
                # Check for JOIN at depth 0, and ensure no SELECT at depth 0
                has_join = False
                has_select = False
                for t, d in zip(inner_tokens, inner_depths):
                    if d == base_depth and t["type"] == "KEYWORD":
                        val_upper = t["value"].upper()
                        if val_upper == "JOIN":
                            has_join = True
                        elif val_upper == "SELECT":
                            has_select = True
                            break
                            
                if has_join and not has_select:
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
                    message="Unnecessary parentheses around a JOIN clause.",
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
            
            need_space = False
            if open_idx - 1 >= 0 and open_idx + 1 < len(tokens):
                prev_t = tokens[open_idx - 1]
                next_t = tokens[open_idx + 1]
                
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
