from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class CteFormatRule(BaseRule):
    rule_id = "IR-cte-format"
    description = "Format layout of CTE WITH blocks: align subquery aliases and the final query block."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "WITH cte1 AS (SELECT * FROM t1), cte2 AS (SELECT * FROM t2) SELECT * FROM cte1;",
            "correct": "WITH\n    cte1 AS (SELECT * FROM t1),\n    cte2 AS (SELECT * FROM t2)\nSELECT * FROM cte1;"
        }
    ]
    additional_validations = [
        "WITH\n    cte1 AS (SELECT * FROM t1),\n    cte2 AS (SELECT * FROM t2)\nSELECT * FROM cte1;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
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
                
                # Find all CTE items and the final query start
                # Walk tokens at depth outer_depth after WITH
                # We want to identify:
                # - First CTE item alias (the token after WITH/RECURSIVE)
                # - Subsequent CTE item aliases (the first active token after each depth-0 comma before the final query starts)
                # - Final query start (the first depth-0 SELECT/INSERT/UPDATE/DELETE after the CTE)
                
                first_alias_idx = None
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth and t["type"] not in ("WHITESPACE", "COMMENT"):
                        if t["type"] == "KEYWORD" and t["value"].upper() == "RECURSIVE":
                            continue
                        first_alias_idx = idx
                        break
                        
                if first_alias_idx is None:
                    continue
                    
                # Format first alias to start on a new line at expected_alias_indent
                ws_before = None
                if first_alias_idx - 1 >= 0 and tokens[first_alias_idx - 1]["type"] == "WHITESPACE":
                    ws_before = tokens[first_alias_idx - 1]
                expected_ws = "\n" + expected_alias_indent
                if not ws_before or ws_before["value"] != expected_ws:
                    violations.append({
                        "token": tokens[first_alias_idx],
                        "ws_start": ws_before["start"] if ws_before else tokens[first_alias_idx]["start"],
                        "ws_end": tokens[first_alias_idx]["start"],
                        "replacement": expected_ws
                    })
                    
                # Walk the rest of the WITH clause
                # We need to find commas at depth 0 and the final query
                last_closing_paren_idx = None
                idx = first_alias_idx + 1
                while idx < n:
                    t = tokens[idx]
                    d = depths[idx]
                    
                    if d == outer_depth:
                        if t["type"] == "COMMA":
                            # Find next alias start
                            next_alias_idx = None
                            for n_idx in range(idx + 1, n):
                                nt = tokens[n_idx]
                                nd = depths[n_idx]
                                if nd == outer_depth and nt["type"] not in ("WHITESPACE", "COMMENT"):
                                    next_alias_idx = n_idx
                                    break
                            if next_alias_idx is not None:
                                ws_before = None
                                if next_alias_idx - 1 >= 0 and tokens[next_alias_idx - 1]["type"] == "WHITESPACE":
                                    ws_before = tokens[next_alias_idx - 1]
                                if not ws_before or ws_before["value"] != expected_ws:
                                    violations.append({
                                        "token": tokens[next_alias_idx],
                                        "ws_start": ws_before["start"] if ws_before else tokens[next_alias_idx]["start"],
                                        "ws_end": tokens[next_alias_idx]["start"],
                                        "replacement": expected_ws
                                    })
                                idx = next_alias_idx
                                continue
                        elif t["type"] == "PAREN" and t["value"] == ")":
                            last_closing_paren_idx = idx
                            
                        # If we hit the final query keyword at depth 0 after the last CTE paren
                        elif t["type"] == "KEYWORD" and t["value"].upper() in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                            # This is the final query!
                            ws_before = None
                            if idx - 1 >= 0 and tokens[idx - 1]["type"] == "WHITESPACE":
                                ws_before = tokens[idx - 1]
                            expected_final_ws = "\n" + with_indent
                            if not ws_before or ws_before["value"] != expected_final_ws:
                                violations.append({
                                    "token": t,
                                    "ws_start": ws_before["start"] if ws_before else t["start"],
                                    "ws_end": t["start"],
                                    "replacement": expected_final_ws
                                })
                            break
                    idx += 1
                    
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
            
        # Apply edits in reverse order
        edits = []
        for item in offending:
            edits.append((item["ws_start"], item["ws_end"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
