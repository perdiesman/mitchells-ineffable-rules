from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class JoinOnMultiRule(BaseRule):
    rule_id = "IR-join-on-multi"
    description = "Split AND or OR conditions in JOIN ON clauses to separate lines, indented 4 spaces."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM table_one JOIN table_two ON table_one.some_long_column_identifier = table_two.some_long_column_identifier AND table_one.another_long_column_identifier = table_two.another_long_column_identifier;",
            "correct": "SELECT * FROM table_one JOIN table_two ON table_one.some_long_column_identifier = table_two.some_long_column_identifier\n    AND table_one.another_long_column_identifier = table_two.another_long_column_identifier;"
        }
    ]
    additional_validations = [
        'SELECT * FROM t1 JOIN t2 ON t1.id = t2.id;'
    ]

    def _find_violations(self, content: str, rule_config: Dict[str, Any] = None) -> List[dict]:
        if rule_config is None:
            rule_config = {}
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "ON":
                outer_depth = depths[i]
                
                line_start = content.rfind("\n", 0, tok["start"]) + 1
                line_prefix = content[line_start:tok["start"]]
                on_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        on_indent += char
                    else:
                        break
                        
                expected_indent = on_indent + "    "
                
                clause_end = n
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if d < outer_depth:
                        clause_end = idx
                        break
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NATURAL",
                            "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] == "SEMI":
                            clause_end = idx
                            break
                            
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                
                on_clause_tokens = tokens[i : clause_end]
                on_clause_str = "".join(t["value"] for t in on_clause_tokens)
                import re
                on_clause_single = re.sub(r'\s+', ' ', on_clause_str)
                estimated_line_len = len(on_indent) + len("JOIN ") + len(on_clause_single)
                
                from mir.rules.sql.line_length import LineLengthRule
                max_len = self.get_config_value(rule_config, "max_line_length", 100, fallbacks=[(LineLengthRule, "max_length")])
                
                first_cond_toks = []
                for t, d in zip(clause_tokens, clause_depths):
                    if d == outer_depth and t["type"] == "KEYWORD" and t["value"].upper() in ("AND", "OR"):
                        break
                    first_cond_toks.append(t)
                
                if first_cond_toks and first_cond_toks[0]["type"] == "WHITESPACE":
                    first_cond_toks.pop(0)
                    
                first_cond_str = "".join(t["value"] for t in first_cond_toks).strip()
                first_cond_str_normalized = re.sub(r'\s+', ' ', first_cond_str)
                
                estimated_first_line_len = len(line_prefix) + len("ON ") + len(first_cond_str_normalized)
                expected_on_ws = "\n" + expected_indent if estimated_first_line_len > max_len else " "
                
                ws_after_on = None
                if i + 1 < n and tokens[i + 1]["type"] == "WHITESPACE":
                    ws_after_on = tokens[i + 1]
                    
                actual_on_ws = ws_after_on["value"] if ws_after_on else ""
                if actual_on_ws != expected_on_ws:
                    violations.append({
                        "token": tok,
                        "ws_start": ws_after_on["start"] if ws_after_on else tok["end"],
                        "ws_end": ws_after_on["end"] if ws_after_on else tok["end"],
                        "replacement": expected_on_ws
                    })
                
                if estimated_line_len <= max_len:
                    continue
                    
                for j_idx, (t, d) in enumerate(zip(clause_tokens, clause_depths)):
                    if d == outer_depth and t["type"] == "KEYWORD" and t["value"].upper() in ("AND", "OR"):
                        actual_idx = i + 1 + j_idx
                        ws_before = None
                        if actual_idx - 1 >= 0 and tokens[actual_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[actual_idx - 1]
                            
                        expected_replacement = "\n" + expected_indent
                        if not ws_before or ws_before["value"] != expected_replacement:
                            violations.append({
                                "token": t,
                                "ws_start": ws_before["start"] if ws_before else t["start"],
                                "ws_end": t["start"],
                                "replacement": expected_replacement
                            })
                            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        
        for item in offending:
            tok = item["token"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="AND or OR condition in JOIN ON clause should start on a new line.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content, rule_config)
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
