from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths, find_matching_paren

class ParenMultiRule(BaseRule):
    rule_id = "IR-paren-multi"
    description = "Parentheses wrapping multiple logical conditions in WHERE/ON clauses must format contents on separate lines, indented 4 spaces."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE active AND (enabled OR not blocked);",
            "correct": "SELECT * FROM users WHERE active AND (\n    enabled\n    OR not blocked\n);"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        def next_active(start_idx: int) -> int:
            for idx in range(start_idx, n):
                if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                    return idx
            return n

        for i, tok in enumerate(tokens):
            if tok["type"] == "PAREN" and tok["value"] == "(":
                in_where_or_on = False
                for idx in range(i - 1, -1, -1):
                    t = tokens[idx]
                    if depths[idx] == depths[i]:
                        if t["type"] == "SEMI" or t["value"] == ";":
                            break
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("WHERE", "ON"):
                            in_where_or_on = True
                            break
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("SELECT", "FROM", "GROUP", "ORDER", "LIMIT", "WITH"):
                            break
                            
                if not in_where_or_on:
                    continue
                    
                close_idx = find_matching_paren(tokens, i)
                if close_idx is None:
                    continue
                    
                has_logical_check = False
                inner_keywords = []
                for idx in range(i + 1, close_idx):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == depths[i] + 1 and t["type"] == "KEYWORD":
                        val_upper = t["value"].upper()
                        if val_upper in ("AND", "OR"):
                            has_logical_check = True
                            inner_keywords.append((t, idx))
                            
                if not has_logical_check:
                    continue
                    
                line_start = content.rfind("\n", 0, tok["start"]) + 1
                line_prefix = content[line_start:tok["start"]]
                paren_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        paren_indent += char
                    else:
                        break
                        
                expected_content_indent = paren_indent + "    "
                expected_close_indent = paren_indent
                
                # Check first active token inside parenthesis
                first_tok_idx = next_active(i + 1)
                if first_tok_idx < close_idx:
                    first_tok = tokens[first_tok_idx]
                    ws_before = None
                    if first_tok_idx - 1 >= 0 and tokens[first_tok_idx - 1]["type"] == "WHITESPACE":
                        ws_before = tokens[first_tok_idx - 1]
                    expected_ws = "\n" + expected_content_indent
                    if not ws_before or ws_before["value"] != expected_ws:
                        violations.append({
                            "token": first_tok,
                            "ws_start": ws_before["start"] if ws_before else first_tok["start"],
                            "ws_end": first_tok["start"],
                            "replacement": expected_ws
                        })
                        
                # Check subsequent top-level logical check keywords inside
                for kw, kw_idx in inner_keywords:
                    ws_before = None
                    if kw_idx - 1 >= 0 and tokens[kw_idx - 1]["type"] == "WHITESPACE":
                        ws_before = tokens[kw_idx - 1]
                    expected_ws = "\n" + expected_content_indent
                    if not ws_before or ws_before["value"] != expected_ws:
                        violations.append({
                            "token": kw,
                            "ws_start": ws_before["start"] if ws_before else kw["start"],
                            "ws_end": kw["start"],
                            "replacement": expected_ws
                        })
                        
                # Check closing parenthesis
                ws_before_close = None
                if close_idx - 1 >= 0 and tokens[close_idx - 1]["type"] == "WHITESPACE":
                    ws_before_close = tokens[close_idx - 1]
                expected_ws = "\n" + expected_close_indent
                if not ws_before_close or ws_before_close["value"] != expected_ws:
                    violations.append({
                        "token": tokens[close_idx],
                        "ws_start": ws_before_close["start"] if ws_before_close else tokens[close_idx]["start"],
                        "ws_end": tokens[close_idx]["start"],
                        "replacement": expected_ws
                    })
                    
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["token"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Logical condition parenthesis block inside WHERE/ON should be split to separate lines.",
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
            edits.append((item["ws_start"], item["ws_end"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
