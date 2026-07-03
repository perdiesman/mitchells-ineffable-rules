from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class WhereMultiRule(BaseRule):
    rule_id = "IR-where-multi"
    description = "Each AND/OR clause in a multi-condition WHERE clause should start on its own line, indented at 4 spaces."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT id FROM users WHERE active = true AND type = 'admin' OR age > 21;",
            "correct": "SELECT id FROM users WHERE\n    active = true\n    AND type = 'admin'\n    OR age > 21;"
        }
    ]
    additional_validations = [
        "SELECT id FROM users WHERE active = true;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "WHERE":
                outer_depth = depths[i]
                
                line_start = content.rfind("\n", 0, tok["start"]) + 1
                line_prefix = content[line_start:tok["start"]]
                where_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        where_indent += char
                    else:
                        break
                        
                expected_indent = where_indent + "    "
                
                clause_end = n
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "GROUP", "ORDER", "LIMIT", "HAVING", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] in ("SEMI", "PAREN"):
                            clause_end = idx
                            break
                            
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                
                has_multi = False
                for t, d in zip(clause_tokens, clause_depths):
                    if d == outer_depth and t["type"] == "KEYWORD" and t["value"].upper() in ("AND", "OR"):
                        has_multi = True
                        break
                        
                if has_multi:
                    # 1. Format the first condition after WHERE onto its own line
                    first_cond_idx = None
                    for idx in range(i + 1, clause_end):
                        if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                            first_cond_idx = idx
                            break
                            
                    if first_cond_idx is not None:
                        fc_tok = tokens[first_cond_idx]
                        ws_before = None
                        if first_cond_idx - 1 >= 0 and tokens[first_cond_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[first_cond_idx - 1]
                            
                        expected_replacement = "\n" + expected_indent
                        if not ws_before or ws_before["value"] != expected_replacement:
                            violations.append({
                                "token": fc_tok,
                                "ws_start": ws_before["start"] if ws_before else fc_tok["start"],
                                "ws_end": fc_tok["start"],
                                "replacement": expected_replacement
                            })
                            
                    # 2. Format subsequent AND/OR keywords onto their own lines
                    for j_idx, (t, d) in enumerate(zip(clause_tokens, clause_depths)):
                        if d == outer_depth and t["type"] == "KEYWORD":
                            val_upper = t["value"].upper()
                            if val_upper in ("AND", "OR"):
                                actual_idx = i + 1 + j_idx
                                ws_tok = None
                                if actual_idx - 1 >= 0 and tokens[actual_idx - 1]["type"] == "WHITESPACE":
                                    ws_tok = tokens[actual_idx - 1]
                                    
                                expected_replacement = "\n" + expected_indent
                                if not ws_tok or ws_tok["value"] != expected_replacement:
                                    violations.append({
                                        "token": t,
                                        "ws_start": ws_tok["start"] if ws_tok else t["start"],
                                        "ws_end": t["start"],
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
                    message="Logical check operators (AND/OR) in multi-condition WHERE clauses must start on their own lines with 4 spaces of indentation.",
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
