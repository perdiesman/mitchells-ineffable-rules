from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class JoinAndRule(BaseRule):
    rule_id = "IR-join-and"
    description = "Split AND or OR conditions in JOIN ON clauses to separate lines, indented 4 spaces."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM t1 JOIN t2 ON t1.id = t2.id AND t1.active = t2.active;",
            "correct": "SELECT * FROM t1 JOIN t2 ON t1.id = t2.id\n    AND t1.active = t2.active;"
        },
        {
            "violating": "SELECT * FROM t1 JOIN t2 ON t1.id = t2.id OR t1.code = t2.code;",
            "correct": "SELECT * FROM t1 JOIN t2 ON t1.id = t2.id\n    OR t1.code = t2.code;"
        }
    ]
    additional_validations = [
        'SELECT * FROM t1 JOIN t2 ON t1.id = t2.id;'
    ]

    def _find_violations(self, content: str) -> List[dict]:
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
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NATURAL",
                            "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] in ("SEMI", "PAREN"):
                            clause_end = idx
                            break
                            
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                
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
        offending = self._find_violations(content)
        
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
