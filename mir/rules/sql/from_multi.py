from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class FromMultiRule(BaseRule):
    rule_id = "IR-from-multi"
    description = "Multi-table or JOINed FROM entries should be formatted with one entry per line, indented at 4 spaces."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM t1, t2, t3 WHERE x = 1;",
            "correct": "SELECT * FROM\n    t1,\n    t2,\n    t3 WHERE x = 1;"
        },
        {
            "violating": "SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id;",
            "correct": "SELECT * FROM\n    t1\n    LEFT JOIN t2 ON t1.id = t2.id;"
        }
    ]
    additional_validations = [
        'SELECT * FROM t1;'
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "FROM":
                outer_depth = depths[i]
                
                # Resolve SELECT indent for this FROM
                select_indent = ""
                for idx in range(i - 1, -1, -1):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth and t["type"] == "KEYWORD" and t["value"].upper() == "SELECT":
                        line_start = content.rfind("\n", 0, t["start"]) + 1
                        line_prefix = content[line_start:t["start"]]
                        indent = ""
                        for char in line_prefix:
                            if char in (" ", "\t"):
                                indent += char
                            else:
                                break
                        select_indent = indent
                        break
                if not select_indent:
                    line_start = content.rfind("\n", 0, tok["start"]) + 1
                    line_prefix = content[line_start:tok["start"]]
                    indent = ""
                    for char in line_prefix:
                        if char in (" ", "\t"):
                            indent += char
                        else:
                            break
                    select_indent = indent
                    
                expected_indent = select_indent + "    "
                
                # Find FROM range
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
                            
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                
                has_join = False
                has_comma = False
                for t, d in zip(clause_tokens, clause_depths):
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() == "JOIN":
                            has_join = True
                        elif t["type"] == "COMMA":
                            has_comma = True
                            
                if has_join or has_comma:
                    # 1. Format the first entry after FROM onto its own line
                    first_entry_idx = None
                    for idx in range(i + 1, clause_end):
                        if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                            first_entry_idx = idx
                            break
                            
                    if first_entry_idx is not None:
                        fe_tok = tokens[first_entry_idx]
                        ws_before = None
                        if first_entry_idx - 1 >= 0 and tokens[first_entry_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[first_entry_idx - 1]
                            
                        expected_replacement = "\n" + expected_indent
                        if not ws_before or ws_before["value"] != expected_replacement:
                            violations.append({
                                "token": fe_tok,
                                "ws_start": ws_before["start"] if ws_before else fe_tok["start"],
                                "ws_end": fe_tok["start"],
                                "replacement": expected_replacement
                            })
                            
                    # 2. Format subsequent entries (JOINs or COMMAs)
                    if has_join:
                        for j_idx, (t, d) in enumerate(zip(clause_tokens, clause_depths)):
                            if d == outer_depth and t["type"] == "KEYWORD":
                                val_upper = t["value"].upper()
                                if val_upper in ("JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NATURAL"):
                                    start_ws = i + 1 + j_idx
                                    
                                    if val_upper == "JOIN":
                                        prev_active = None
                                        for prev_idx in range(start_ws - 1, -1, -1):
                                            if tokens[prev_idx]["type"] != "WHITESPACE" and tokens[prev_idx]["type"] != "COMMENT":
                                                prev_active = tokens[prev_idx]
                                                break
                                        if prev_active and prev_active["type"] == "KEYWORD" and prev_active["value"].upper() in ("LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NATURAL"):
                                            continue
                                            
                                    ws_tok = None
                                    if start_ws - 1 >= 0 and tokens[start_ws - 1]["type"] == "WHITESPACE":
                                        ws_tok = tokens[start_ws - 1]
                                        
                                    expected_replacement = "\n" + expected_indent
                                    if not ws_tok or ws_tok["value"] != expected_replacement:
                                        violations.append({
                                            "token": t,
                                            "ws_start": ws_tok["start"] if ws_tok else t["start"],
                                            "ws_end": t["start"],
                                            "replacement": expected_replacement
                                        })
                    elif has_comma:
                        for j_idx, (t, d) in enumerate(zip(clause_tokens, clause_depths)):
                            if d == outer_depth and t["type"] == "COMMA":
                                ws_tok = None
                                next_tok = None
                                actual_idx = i + 1 + j_idx
                                if actual_idx + 1 < n:
                                    if tokens[actual_idx + 1]["type"] == "WHITESPACE":
                                        ws_tok = tokens[actual_idx + 1]
                                        if actual_idx + 2 < n:
                                            next_tok = tokens[actual_idx + 2]
                                    else:
                                        next_tok = tokens[actual_idx + 1]
                                        
                                if next_tok:
                                    expected_replacement = "\n" + expected_indent
                                    if not ws_tok or ws_tok["value"] != expected_replacement:
                                        violations.append({
                                            "token": next_tok,
                                            "ws_start": ws_tok["start"] if ws_tok else t["end"],
                                            "ws_end": ws_tok["end"] if ws_tok else t["end"],
                                            "replacement": expected_replacement
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
                    message="Multi-table or JOINed FROM entries must start on separate lines with 4 spaces of indentation.",
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
