from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class BooleanComparisonRule(BaseRule):
    rule_id = "IR-boolean-comparison"
    description = "Standardize boolean comparison predicates to use idiomatic boolean predicates."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE active = true AND blocked = false;",
            "correct": "SELECT * FROM users WHERE active AND NOT blocked;"
        },
        {
            "violating": "SELECT * FROM users WHERE active != true OR blocked <> false;",
            "correct": "SELECT * FROM users WHERE NOT active OR blocked;"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        active = []
        for idx, t in enumerate(tokens):
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)
                
        num_active = len(active)
        
        def parse_operand(idx: int) -> tuple:
            if idx >= len(active):
                return None, None
            if active[idx]["type"] == "OPERATOR" and active[idx]["value"] in ("-", "+"):
                if idx + 1 < len(active) and active[idx+1]["type"] == "NUMBER":
                    return f"{active[idx]['value']}{active[idx+1]['value']}", idx + 2
            if active[idx]["type"] == "IDENTIFIER":
                if idx + 2 < len(active) and active[idx+1]["type"] == "DOT" and active[idx+2]["type"] == "IDENTIFIER":
                    return f"{active[idx]['value']}.{active[idx+2]['value']}", idx + 3
                return active[idx]["value"], idx + 1
            if active[idx]["type"] in ("NUMBER", "STRING", "KEYWORD"):
                return active[idx]["value"], idx + 1
            return None, None

        i = 0
        while i < num_active:
            is_assignment = False
            if i == 0 or active[i - 1]["value"].upper() in (";", "BEGIN", "THEN", "ELSE", "LOOP"):
                is_assignment = True
                
            if is_assignment:
                _, next_idx = parse_operand(i)
                i = next_idx if next_idx is not None else i + 1
                continue
                
            op_str, next_idx = parse_operand(i)
            if op_str and next_idx < num_active:
                t_op = active[next_idx]
                if t_op["type"] == "OPERATOR" and t_op["value"] in ("=", "!=", "<>"):
                    if next_idx + 1 < num_active:
                        val_tok = active[next_idx + 1]
                        if val_tok["type"] in ("KEYWORD", "IDENTIFIER") and val_tok["value"].upper() in ("TRUE", "FALSE"):
                            val_upper = val_tok["value"].upper()
                            op_val = t_op["value"]
                            
                            if val_upper == "TRUE":
                                if op_val == "=":
                                    replacement = op_str
                                else:
                                    replacement = f"NOT {op_str}"
                            else:
                                if op_val == "=":
                                    replacement = f"NOT {op_str}"
                                else:
                                    replacement = op_str
                                    
                            violations.append({
                                "start_offset": active[i]["start"],
                                "end_offset": val_tok["end"],
                                "line": active[i]["line"],
                                "replacement": replacement
                            })
                            i = next_idx + 2
                            continue
            i += 1
            
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
                    message="Standardize boolean comparisons to clean boolean predicates.",
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
            edits.append((item["start_offset"], item["end_offset"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
