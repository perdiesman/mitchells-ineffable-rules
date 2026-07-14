from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class StatementBlankLinesRule(BaseRule):
    rule_id = "IR-statement-blank-lines"
    description = "Ensure at least one blank line between consecutive SQL statements."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    exclude_recursive = True
    
    default_config = {
        "min_blank_lines": 1
    }
    config_options = {
        "min_blank_lines": {
            "type": "int",
            "description": "Minimum number of blank lines between consecutive SQL statements.",
            "default": 1
        }
    }
    
    examples = [
        {
            "violating": "SELECT 1;\nSELECT 2;",
            "correct": "SELECT 1;\n\nSELECT 2;"
        },
        {
            "violating": "SELECT 1;\n-- comment for 2\nSELECT 2;",
            "correct": "SELECT 1;\n\n-- comment for 2\nSELECT 2;"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        n = len(tokens)
        violations = []
        
        for idx, t in enumerate(tokens):
            if t["type"] == "SEMI":
                next_active_idx = None
                for j in range(idx + 1, n):
                    if tokens[j]["type"] in ("WHITESPACE", "SEMI"):
                        continue
                    if tokens[j]["type"] == "COMMENT" and tokens[j]["line"] == t["line"]:
                        continue
                    next_active_idx = j
                    break
                        
                if next_active_idx is not None:
                    next_active = tokens[next_active_idx]
                    
                    target_tok_idx = next_active_idx
                    for j in range(idx + 1, next_active_idx):
                        if tokens[j]["type"] == "COMMENT":
                            if tokens[j]["line"] > t["line"]:
                                target_tok_idx = j
                                break
                                
                    target_tok = tokens[target_tok_idx]
                    
                    ws_tok = None
                    if target_tok_idx - 1 >= 0 and tokens[target_tok_idx - 1]["type"] == "WHITESPACE":
                        ws_tok = tokens[target_tok_idx - 1]
                        
                    has_blank = False
                    if ws_tok:
                        if ws_tok["value"].count("\n") >= 2:
                            has_blank = True
                            
                    if not has_blank:
                        violations.append({
                            "line": t["line"],
                            "target_tok": target_tok,
                            "ws_tok": ws_tok
                        })
                        
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message="Consecutive SQL statements must be separated by at least one blank line.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        tokens = tokenize_sql(content)
        n = len(tokens)
        edits = []
        
        for idx, t in enumerate(tokens):
            if t["type"] == "SEMI":
                next_active_idx = None
                for j in range(idx + 1, n):
                    if tokens[j]["type"] in ("WHITESPACE", "SEMI"):
                        continue
                    if tokens[j]["type"] == "COMMENT" and tokens[j]["line"] == t["line"]:
                        continue
                    next_active_idx = j
                    break
                        
                if next_active_idx is not None:
                    next_active = tokens[next_active_idx]
                    
                    target_tok_idx = next_active_idx
                    for j in range(idx + 1, next_active_idx):
                        if tokens[j]["type"] == "COMMENT":
                            if tokens[j]["line"] > t["line"]:
                                target_tok_idx = j
                                break
                                
                    target_tok = tokens[target_tok_idx]
                    
                    ws_tok = None
                    if target_tok_idx - 1 >= 0 and tokens[target_tok_idx - 1]["type"] == "WHITESPACE":
                        ws_tok = tokens[target_tok_idx - 1]
                        
                    has_blank = False
                    if ws_tok:
                        if ws_tok["value"].count("\n") >= 2:
                            has_blank = True
                            
                    if not has_blank:
                        if ws_tok:
                            ws_val = ws_tok["value"]
                            indent = ws_val.split("\n")[-1]
                            rep = "\n\n" + indent
                            edit_start = ws_tok["start"]
                            edit_end = ws_tok["end"]
                        else:
                            rep = "\n\n"
                            edit_start = target_tok["start"]
                            edit_end = target_tok["start"]
                            
                        edits.append((edit_start, edit_end, rep))
                        
        if not edits:
            return content
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, rep in edits:
            chars[start:end] = list(rep)
            
        return "".join(chars)
