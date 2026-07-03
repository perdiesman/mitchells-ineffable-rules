from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths, find_matching_paren
from mir.rules.sql.indent import IndentRule

class CteFormatRule(BaseRule):
    rule_id = "IR-cte-format"
    description = "Format layout of CTE WITH blocks: align subquery aliases, parenthesis and the final query block."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "WITH cte1 AS (SELECT * FROM t1), cte2 AS (SELECT * FROM t2) SELECT * FROM cte1;",
            "correct": "WITH cte1 AS (\n    SELECT * FROM t1\n), cte2 AS (\n    SELECT * FROM t2\n)\nSELECT * FROM cte1;"
        }
    ]
    additional_validations = [
        'WITH cte1 AS MATERIALIZED (\n    SELECT * FROM t1\n), cte2 (col1, col2) AS (\n    SELECT * FROM t2\n)\nSELECT * FROM cte1;'
    ]

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
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "WITH":
                outer_depth = depths[i]
                
                # Resolve WITH indent
                line_start = content.rfind("\n", 0, tok["start"]) + 1
                line_prefix = content[line_start:tok["start"]]
                with_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        with_indent += char
                    else:
                        break
                        
                expected_alias_indent = with_indent + "    "
                
                # Find all CTE declarations
                ctes = []
                curr = i + 1
                if curr < n and tokens[curr]["type"] == "KEYWORD" and tokens[curr]["value"].upper() == "RECURSIVE":
                    curr += 1
                
                curr = next_active(curr)
                while curr < n:
                    alias_tok = tokens[curr]
                    
                    next_act = next_active(curr + 1)
                    if next_act < n and tokens[next_act]["type"] == "PAREN" and tokens[next_act]["value"] == "(":
                        col_close_idx = find_matching_paren(tokens, next_act)
                        if col_close_idx is None:
                            break
                        as_idx = next_active(col_close_idx + 1)
                    else:
                        as_idx = next_act
                        
                    if as_idx >= n or tokens[as_idx]["type"] != "KEYWORD" or tokens[as_idx]["value"].upper() != "AS":
                        break
                    as_tok = tokens[as_idx]
                    
                    open_idx = next_active(as_idx + 1)
                    if open_idx < n and tokens[open_idx]["type"] == "KEYWORD":
                        val_upper = tokens[open_idx]["value"].upper()
                        if val_upper == "MATERIALIZED":
                            open_idx = next_active(open_idx + 1)
                        elif val_upper == "NOT":
                            next_next = next_active(open_idx + 1)
                            if next_next < n and tokens[next_next]["type"] == "KEYWORD" and tokens[next_next]["value"].upper() == "MATERIALIZED":
                                open_idx = next_active(next_next + 1)
                                
                    if open_idx >= n or tokens[open_idx]["type"] != "PAREN" or tokens[open_idx]["value"] != "(":
                        break
                    open_tok = tokens[open_idx]
                    
                    close_idx = find_matching_paren(tokens, open_idx)
                    if close_idx is None:
                        break
                    close_tok = tokens[close_idx]
                    
                    comma_tok = None
                    next_act = next_active(close_idx + 1)
                    if next_act < n and tokens[next_act]["type"] == "COMMA":
                        comma_tok = tokens[next_act]
                        
                    ctes.append({
                        "alias": alias_tok,
                        "as": as_tok,
                        "open_paren": open_tok,
                        "close_paren": close_tok,
                        "comma": comma_tok
                    })
                    
                    if comma_tok:
                        curr = next_active(next_act + 1)
                    else:
                        curr = next_act
                        break
                        
                for idx, cte in enumerate(ctes):
                    alias = cte["alias"]
                    as_tok = cte["as"]
                    open_paren = cte["open_paren"]
                    close_paren = cte["close_paren"]
                    comma = cte["comma"]
                    
                    alias_idx = tokens.index(alias)
                    as_token_idx = tokens.index(as_tok)
                    
                    col_open_tok = None
                    for check_idx in range(alias_idx + 1, as_token_idx):
                        t = tokens[check_idx]
                        if t["type"] == "PAREN" and t["value"] == "(":
                            col_open_tok = t
                            break
                            
                    # 1. Space before alias (first CTE only)
                    if idx == 0:
                        ws_before = None
                        if alias_idx - 1 >= 0 and tokens[alias_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[alias_idx - 1]
                        expected_ws = " "
                        if not ws_before or ws_before["value"] != expected_ws:
                            violations.append({
                                "token": alias,
                                "ws_start": ws_before["start"] if ws_before else alias["start"],
                                "ws_end": alias["start"],
                                "replacement": expected_ws
                            })
                    else:
                        prev_comma = ctes[idx - 1]["comma"]
                        if prev_comma:
                            ws_before = None
                            if alias_idx - 1 >= 0 and tokens[alias_idx - 1]["type"] == "WHITESPACE":
                                ws_before = tokens[alias_idx - 1]
                            expected_ws = " "
                            if not ws_before or ws_before["value"] != expected_ws:
                                violations.append({
                                    "token": alias,
                                    "ws_start": ws_before["start"] if ws_before else alias["start"],
                                    "ws_end": alias["start"],
                                    "replacement": expected_ws
                                })

                    # 2. Format column list open paren (if exists)
                    if col_open_tok:
                        col_open_idx = tokens.index(col_open_tok)
                        ws_before = None
                        if col_open_idx - 1 >= 0 and tokens[col_open_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[col_open_idx - 1]
                        expected_ws = " "
                        if not ws_before or ws_before["value"] != expected_ws:
                            violations.append({
                                "token": col_open_tok,
                                "ws_start": ws_before["start"] if ws_before else col_open_tok["start"],
                                "ws_end": col_open_tok["start"],
                                "replacement": expected_ws
                            })

                    # 3. Space before AS
                    ws_before = None
                    if as_token_idx - 1 >= 0 and tokens[as_token_idx - 1]["type"] == "WHITESPACE":
                        ws_before = tokens[as_token_idx - 1]
                    expected_ws = " "
                    if not ws_before or ws_before["value"] != expected_ws:
                        violations.append({
                            "token": as_tok,
                            "ws_start": ws_before["start"] if ws_before else as_tok["start"],
                            "ws_end": as_tok["start"],
                            "replacement": expected_ws
                        })

                    # 4. Space before open_paren or modifier (MATERIALIZED / NOT MATERIALIZED)
                    open_token_idx = tokens.index(open_paren)
                    for mid_idx in range(as_token_idx + 1, open_token_idx + 1):
                        mid_tok = tokens[mid_idx]
                        if mid_tok["type"] not in ("WHITESPACE", "COMMENT"):
                            ws_before = None
                            if mid_idx - 1 >= 0 and tokens[mid_idx - 1]["type"] == "WHITESPACE":
                                ws_before = tokens[mid_idx - 1]
                            expected_ws = " "
                            if not ws_before or ws_before["value"] != expected_ws:
                                violations.append({
                                    "token": mid_tok,
                                    "ws_start": ws_before["start"] if ws_before else mid_tok["start"],
                                    "ws_end": mid_tok["start"],
                                    "replacement": expected_ws
                                })
                            break

                    # 5. Newline + indent before first token of subquery
                    first_sub = next_active(open_token_idx + 1)
                    if first_sub < tokens.index(close_paren):
                        first_sub_tok = tokens[first_sub]
                        ws_before = None
                        if first_sub - 1 >= 0 and tokens[first_sub - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[first_sub - 1]
                        expected_ws = "\n" + expected_alias_indent
                        if not ws_before or ws_before["value"] != expected_ws:
                            violations.append({
                                "token": first_sub_tok,
                                "ws_start": ws_before["start"] if ws_before else first_sub_tok["start"],
                                "ws_end": first_sub_tok["start"],
                                "replacement": expected_ws
                            })

                    # 6. Newline + with_indent before close_paren
                    close_token_idx = tokens.index(close_paren)
                    ws_before = None
                    if close_token_idx - 1 >= 0 and tokens[close_token_idx - 1]["type"] == "WHITESPACE":
                        ws_before = tokens[close_token_idx - 1]
                    expected_ws = "\n" + with_indent
                    if not ws_before or ws_before["value"] != expected_ws:
                        violations.append({
                            "token": close_paren,
                            "ws_start": ws_before["start"] if ws_before else close_paren["start"],
                            "ws_end": close_paren["start"],
                            "replacement": expected_ws
                        })

                    # 7. No space before trailing comma
                    if comma:
                        comma_idx = tokens.index(comma)
                        ws_before = None
                        if comma_idx - 1 >= 0 and tokens[comma_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[comma_idx - 1]
                        expected_ws = ""
                        if ws_before and ws_before["value"] != expected_ws:
                            violations.append({
                                "token": comma,
                                "ws_start": ws_before["start"],
                                "ws_end": comma["start"],
                                "replacement": expected_ws
                            })

                # 8. Final query start
                if ctes:
                    last_cte = ctes[-1]
                    last_tok = last_cte["comma"] if last_cte["comma"] else last_cte["close_paren"]
                    last_idx = tokens.index(last_tok)
                    final_query_idx = next_active(last_idx + 1)
                    if final_query_idx < n:
                        final_tok = tokens[final_query_idx]
                        ws_before = None
                        if final_query_idx - 1 >= 0 and tokens[final_query_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[final_query_idx - 1]
                        expected_ws = "\n" + with_indent
                        if not ws_before or ws_before["value"] != expected_ws:
                            violations.append({
                                "token": final_tok,
                                "ws_start": ws_before["start"] if ws_before else final_tok["start"],
                                "ws_end": final_tok["start"],
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
                    message="CTE layout element is not aligned correctly.",
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
