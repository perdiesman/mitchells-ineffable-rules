from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class BetweenRule(BaseRule):
    rule_id = "IR-between"
    description = "Standardize range predicate check of form 'a >= b AND a <= c' to 'a BETWEEN b AND c'."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE age >= 18 AND age <= 65;",
            "correct": "SELECT * FROM users WHERE age BETWEEN 18 AND 65;"
        },
        {
            "violating": "SELECT * FROM users WHERE age <= 65 AND age >= 18;",
            "correct": "SELECT * FROM users WHERE age BETWEEN 18 AND 65;"
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
            # 1. Pattern A: op1 >= op2 AND op3 <= op4
            op1_str, next_idx = parse_operand(i)
            if op1_str and next_idx < num_active:
                t_op = active[next_idx]
                if t_op["type"] == "OPERATOR" and t_op["value"] == ">=":
                    op2_str, next_idx2 = parse_operand(next_idx + 1)
                    if op2_str and next_idx2 < num_active:
                        t_and = active[next_idx2]
                        if t_and["type"] == "KEYWORD" and t_and["value"].upper() == "AND":
                            op3_str, next_idx3 = parse_operand(next_idx2 + 1)
                            if op3_str and op3_str.lower() == op1_str.lower() and next_idx3 < num_active:
                                t_op2 = active[next_idx3]
                                if t_op2["type"] == "OPERATOR" and t_op2["value"] == "<=":
                                    op4_str, next_idx4 = parse_operand(next_idx3 + 1)
                                    if op4_str:
                                        violations.append({
                                            "start_offset": active[i]["start"],
                                            "end_offset": active[next_idx4 - 1]["end"],
                                            "line": active[i]["line"],
                                            "replacement": f"{op1_str} BETWEEN {op2_str} AND {op4_str}"
                                        })
                                        i = next_idx4
                                        continue

            # 2. Pattern B: op1 <= op2 AND op3 >= op4
            op1_str, next_idx = parse_operand(i)
            if op1_str and next_idx < num_active:
                t_op = active[next_idx]
                if t_op["type"] == "OPERATOR" and t_op["value"] == "<=":
                    op2_str, next_idx2 = parse_operand(next_idx + 1)
                    if op2_str and next_idx2 < num_active:
                        t_and = active[next_idx2]
                        if t_and["type"] == "KEYWORD" and t_and["value"].upper() == "AND":
                            op3_str, next_idx3 = parse_operand(next_idx2 + 1)
                            if op3_str and op3_str.lower() == op1_str.lower() and next_idx3 < num_active:
                                t_op2 = active[next_idx3]
                                if t_op2["type"] == "OPERATOR" and t_op2["value"] == ">=":
                                    op4_str, next_idx4 = parse_operand(next_idx3 + 1)
                                    if op4_str:
                                        violations.append({
                                            "start_offset": active[i]["start"],
                                            "end_offset": active[next_idx4 - 1]["end"],
                                            "line": active[i]["line"],
                                            "replacement": f"{op1_str} BETWEEN {op4_str} AND {op2_str}"
                                        })
                                        i = next_idx4
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
                    message="Standardize range check to BETWEEN operator.",
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
