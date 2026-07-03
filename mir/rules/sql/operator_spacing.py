from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class OperatorSpacingRule(BaseRule):
    rule_id = "IR-operator-spacing"
    description = "Operators should have a single space on both sides."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT a+b AS c FROM users WHERE id=1;",
            "correct": "SELECT a + b AS c FROM users WHERE id = 1;"
        }
    ]
    additional_validations = [
        'SELECT -5 FROM users;',
        'SELECT COUNT(*) FROM users;'
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "OPERATOR":
                val = tok["value"]
                
                # Skip cast operator
                if val == "::":
                    continue
                    
                # Check if it is unary minus or asterisk
                prev_active = None
                for idx in range(i - 1, -1, -1):
                    if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                        prev_active = tokens[idx]
                        break
                        
                is_unary_or_special = False
                if val in ("-", "*"):
                    if prev_active is None:
                        is_unary_or_special = True
                    elif prev_active["type"] in ("OPERATOR", "COMMA"):
                        is_unary_or_special = True
                    elif prev_active["type"] == "PAREN" and prev_active["value"] == "(":
                        is_unary_or_special = True
                    elif prev_active["type"] == "KEYWORD" and prev_active["value"].upper() in (
                        "SELECT", "WHERE", "AND", "OR", "ON", "HAVING", "LIMIT", "BY", "RETURNING"
                    ):
                        is_unary_or_special = True
                        
                if is_unary_or_special:
                    continue
                    
                # Check space before
                ws_before = None
                if i - 1 >= 0 and tokens[i - 1]["type"] == "WHITESPACE":
                    ws_before = tokens[i - 1]
                    
                # Check space after
                ws_after = None
                if i + 1 < n and tokens[i + 1]["type"] == "WHITESPACE":
                    ws_after = tokens[i + 1]
                    
                needs_fix = False
                rep_before = " "
                rep_after = " "
                
                # Handle space before
                if ws_before:
                    # If it contains newline, we keep it as is
                    if "\n" in ws_before["value"]:
                        rep_before = ws_before["value"]
                    elif ws_before["value"] != " ":
                        needs_fix = True
                else:
                    needs_fix = True
                    
                # Handle space after
                if ws_after:
                    if "\n" in ws_after["value"]:
                        rep_after = ws_after["value"]
                    elif ws_after["value"] != " ":
                        needs_fix = True
                else:
                    needs_fix = True
                    
                if needs_fix:
                    violations.append({
                        "token": tok,
                        "ws_before": ws_before,
                        "ws_after": ws_after,
                        "rep_before": rep_before,
                        "rep_after": rep_after
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
                    message=f"Operator '{tok['value']}' must be surrounded by a single space.",
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
            tok = item["token"]
            ws_before = item["ws_before"]
            ws_after = item["ws_after"]
            
            # Edit after first, then before
            if ws_after:
                edits.append((ws_after["start"], ws_after["end"], item["rep_after"]))
            else:
                edits.append((tok["end"], tok["end"], item["rep_after"]))
                
            if ws_before:
                edits.append((ws_before["start"], ws_before["end"], item["rep_before"]))
            else:
                edits.append((tok["start"], tok["start"], item["rep_before"]))
                
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
