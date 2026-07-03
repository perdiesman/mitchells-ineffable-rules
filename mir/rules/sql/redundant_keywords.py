from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class RedundantKeywordsRule(BaseRule):
    rule_id = "IR-redundant-keywords"
    description = "Remove redundant implied keywords like INNER, OUTER, and ASC."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM t1 INNER JOIN t2 LEFT OUTER JOIN t3 ORDER BY col ASC;",
            "correct": "SELECT * FROM t1 JOIN t2 LEFT JOIN t3 ORDER BY col;"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        def next_active(start_idx: int) -> int:
            for idx in range(start_idx, n):
                if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                    return idx
            return n

        idx = 0
        while idx < n:
            tok = tokens[idx]
            if tok["type"] != "KEYWORD":
                idx += 1
                continue
                
            val_upper = tok["value"].upper()
            
            # 1. INNER JOIN -> JOIN
            if val_upper == "INNER":
                next_act = next_active(idx + 1)
                if next_act < n and tokens[next_act]["type"] == "KEYWORD" and tokens[next_act]["value"].upper() == "JOIN":
                    join_val = tokens[next_act]["value"]
                    violations.append({
                        "token": tok,
                        "start_offset": tok["start"],
                        "end_offset": tokens[next_act]["end"],
                        "replacement": join_val,
                        "message": "Redundant 'INNER' keyword before 'JOIN'."
                    })
                    idx = next_act + 1
                    continue
                    
            # 2. <LEFT/RIGHT/FULL> OUTER JOIN -> <LEFT/RIGHT/FULL> JOIN
            if val_upper in ("LEFT", "RIGHT", "FULL"):
                next_act = next_active(idx + 1)
                if next_act < n and tokens[next_act]["type"] == "KEYWORD" and tokens[next_act]["value"].upper() == "OUTER":
                    next_next = next_active(next_act + 1)
                    if next_next < n and tokens[next_next]["type"] == "KEYWORD" and tokens[next_next]["value"].upper() == "JOIN":
                        join_val = tokens[next_next]["value"]
                        violations.append({
                            "token": tokens[next_act],
                            "start_offset": tokens[next_act]["start"],
                            "end_offset": tokens[next_next]["end"],
                            "replacement": join_val,
                            "message": f"Redundant 'OUTER' keyword after '{tok['value']}'."
                        })
                        idx = next_next + 1
                        continue
                        
            # 3. ASC -> empty
            if val_upper == "ASC":
                ws_before = None
                if idx - 1 >= 0 and tokens[idx - 1]["type"] == "WHITESPACE":
                    ws_before = tokens[idx - 1]
                    
                start_rem = ws_before["start"] if ws_before else tok["start"]
                violations.append({
                    "token": tok,
                    "start_offset": start_rem,
                    "end_offset": tok["end"],
                    "replacement": "",
                    "message": "Redundant 'ASC' sort specifier."
                })
                idx += 1
                continue
                
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
                    message=item["message"],
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
            edits.append((item["start_offset"], item["end_offset"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
