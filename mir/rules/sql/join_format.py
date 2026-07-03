from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths, find_clause_end

class JoinFormatRule(BaseRule):
    rule_id = "IR-join-format"
    description = "Standardize formatting of JOIN clauses: collapse split qualifiers (e.g., LEFT JOIN on same line) and align ON indentation."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM t1 LEFT\nJOIN t2\nON t1.id = t2.id;",
            "correct": "SELECT * FROM t1 LEFT JOIN t2\n    ON t1.id = t2.id;"
        }
    ]
    additional_validations = [
        'SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id;'
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        seen_split_starts = set()
        seen_on_starts = set()
        
        clause_keywords = [
            "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
        ]
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() in ("FROM", "JOIN"):
                outer_depth = depths[i]
                clause_end = find_clause_end(tokens, depths, i, clause_keywords)
                            
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                
                for j_idx, (t, d) in enumerate(zip(clause_tokens, clause_depths)):
                    actual_idx = i + 1 + j_idx
                    if d == outer_depth and t["type"] == "KEYWORD":
                        val_upper = t["value"].upper()
                        
                        # 1. Split qualifiers check
                        if val_upper in ("LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NATURAL"):
                            next_active = None
                            ws_tok = None
                            for next_idx in range(actual_idx + 1, clause_end):
                                if tokens[next_idx]["type"] == "WHITESPACE":
                                    ws_tok = tokens[next_idx]
                                elif tokens[next_idx]["type"] != "COMMENT":
                                    next_active = tokens[next_idx]
                                    break
                            if next_active and next_active["type"] == "KEYWORD" and next_active["value"].upper() == "JOIN":
                                if ws_tok and "\n" in ws_tok["value"]:
                                    if ws_tok["start"] not in seen_split_starts:
                                        seen_split_starts.add(ws_tok["start"])
                                        violations.append({
                                            "type": "split_qualifier",
                                            "ws_start": ws_tok["start"],
                                            "ws_end": ws_tok["end"],
                                            "token": next_active
                                        })
                                    
                        # 2. ON keyword check
                        elif val_upper == "ON":
                            if t["start"] not in seen_on_starts:
                                seen_on_starts.add(t["start"])
                                
                                ws_before = None
                                if actual_idx - 1 >= 0 and tokens[actual_idx - 1]["type"] == "WHITESPACE":
                                    ws_before = tokens[actual_idx - 1]
                                    
                                if ws_before and "\n" in ws_before["value"]:
                                    join_indent = ""
                                    for prev_idx in range(actual_idx - 1, -1, -1):
                                        pt = tokens[prev_idx]
                                        pd = depths[prev_idx]
                                        if pd == outer_depth and pt["type"] == "KEYWORD" and pt["value"].upper() in (
                                            "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NATURAL"
                                        ):
                                            line_start = content.rfind("\n", 0, pt["start"]) + 1
                                            line_prefix = content[line_start:pt["start"]]
                                            indent = ""
                                            for char in line_prefix:
                                                if char in (" ", "\t"):
                                                    indent += char
                                                else:
                                                    break
                                            join_indent = indent
                                            break
                                            
                                    expected_indent = join_indent + "    "
                                    expected_replacement = "\n" + expected_indent
                                    if ws_before["value"] != expected_replacement:
                                        violations.append({
                                            "type": "on_indent",
                                            "ws_start": ws_before["start"],
                                            "ws_end": ws_before["end"],
                                            "replacement": expected_replacement,
                                            "token": t
                                        })
                                    
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["token"]
            msg = (
                "Split join qualifiers should be on the same line."
                if item["type"] == "split_qualifier"
                else "ON keyword in a new line should be indented 4 spaces relative to the JOIN."
            )
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message=msg,
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
            if item["type"] == "split_qualifier":
                edits.append((item["ws_start"], item["ws_end"], " "))
            else:
                edits.append((item["ws_start"], item["ws_end"], item["replacement"]))
                
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
