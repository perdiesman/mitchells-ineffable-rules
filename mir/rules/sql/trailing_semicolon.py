from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class TrailingSemicolonRule(BaseRule):
    rule_id = "IR-trailing-semicolon"
    description = "Enforce that the last SQL statement ends with a trailing semicolon, placed immediately after the statement text."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users",
            "correct": "SELECT * FROM users;"
        },
        {
            "violating": "SELECT * FROM users\n    ;",
            "correct": "SELECT * FROM users;"
        }
    ]
    additional_validations = [
        'SELECT * FROM users; -- comment at end'
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        
        # 1. Enforce trailing semicolon for the entire file
        last_active = None
        for t in reversed(tokens):
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                last_active = t
                break
                
        if last_active and last_active["value"] != ";":
            violations.append({
                "type": "missing",
                "token": last_active,
                "insert_pos": last_active["end"],
                "line": last_active["line"]
            })
            
        # 2. Check ALL semicolons for placement layout
        for idx, tok in enumerate(tokens):
            if tok["type"] != "WHITESPACE" and tok["type"] != "COMMENT" and tok["value"] == ";":
                prev_tok = None
                has_newline_before_semi = False
                ws_before = None
                
                for p_idx in range(idx - 1, -1, -1):
                    t = tokens[p_idx]
                    if t["type"] == "WHITESPACE":
                        ws_before = t
                        if "\n" in t["value"]:
                            has_newline_before_semi = True
                    elif t["type"] != "COMMENT":
                        prev_tok = t
                        break
                        
                if prev_tok and (has_newline_before_semi or (ws_before and ws_before["value"] != "")):
                    violations.append({
                        "type": "placement",
                        "semi_tok": tok,
                        "insert_pos": prev_tok["end"],
                        "line": tok["line"]
                    })
                    
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            msg = "SQL statement should end with a semicolon."
            if item["type"] == "placement":
                msg = "Semicolon should be placed immediately after the preceding token without leading spaces/newlines."
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message=msg,
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
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
            if item["type"] == "placement":
                semi = item["semi_tok"]
                pos = item["insert_pos"]
                edits.append((pos, semi["end"], ";"))
            else:
                pos = item["insert_pos"]
                edits.append((pos, pos, ";"))
                
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
        return "".join(chars)
