from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class ASSpacingRule(BaseRule):
    rule_id = "IR-as-spacing"
    description = "The AS keyword must be preceded by exactly one space."
    category = "general"
    is_fixable = "yes"
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT a   AS b FROM t;",
            "correct": "SELECT a AS b FROM t;"
        }
    ]
    additional_validations = [
        "SELECT a AS b FROM t;",
        "SELECT a\nAS b FROM t;"
    ]
    
    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "AS":
                if i - 1 >= 0:
                    prev = tokens[i - 1]
                    if prev["type"] == "WHITESPACE":
                        ws_val = prev["value"]
                        if "\n" not in ws_val and ws_val != " ":
                            violations.append({
                                "token": tok,
                                "ws_before": prev,
                                "type": "modify_ws"
                            })
                    elif prev["type"] != "COMMENT":
                        # Needs a space inserted
                        violations.append({
                            "token": tok,
                            "ws_before": None,
                            "type": "insert_ws"
                        })
                else:
                    # 'AS' at start of content
                    pass
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
                    message="The AS keyword must be preceded by exactly one space.",
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
            tok = item["token"]
            ws_before = item["ws_before"]
            if item["type"] == "modify_ws":
                edits.append((ws_before["start"], ws_before["end"], " "))
            elif item["type"] == "insert_ws":
                edits.append((tok["start"], tok["start"], " "))
                
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
