from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class NullCoalesceRule(BaseRule):
    rule_id = "IR-null-coalesce"
    description = "Standardize nullable equality predicates to COALESCE(x, -1) form."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE active = -1 OR active IS NULL;",
            "correct": "SELECT * FROM users WHERE COALESCE(active, -1) = -1;"
        },
        {
            "violating": "SELECT * FROM t1 JOIN t2 ON t1.id = t2.id OR (t1.id IS NULL AND t2.id IS NULL);",
            "correct": "SELECT * FROM t1 JOIN t2 ON COALESCE(t1.id, -1) = COALESCE(t2.id, -1);"
        }
    ]
    additional_validations = [
        "SELECT * FROM users WHERE COALESCE(active, -1) = -1;",
        "SELECT * FROM t1 JOIN t2 ON COALESCE(t1.id, -1) = COALESCE(t2.id, -1);"
    ]

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
            # Support signed numbers e.g. -1
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
            # 1. Try to match: a = b OR (a IS NULL AND b IS NULL) or without parens
            op1_str, next_idx = parse_operand(i)
            if op1_str and next_idx < num_active:
                t_eq = active[next_idx]
                if t_eq["type"] == "OPERATOR" and t_eq["value"] == "=":
                    op2_str, next_idx2 = parse_operand(next_idx + 1)
                    if op2_str and next_idx2 < num_active:
                        t_or = active[next_idx2]
                        if t_or["type"] == "KEYWORD" and t_or["value"].upper() == "OR":
                            has_parens = False
                            check_idx = next_idx2 + 1
                            if check_idx < num_active and active[check_idx]["type"] == "PAREN" and active[check_idx]["value"] == "(":
                                has_parens = True
                                check_idx += 1
                                
                            op1_check, next_check = parse_operand(check_idx)
                            if op1_check and op1_check.lower() == op1_str.lower() and next_check < num_active:
                                t_is = active[next_check]
                                if t_is["type"] == "KEYWORD" and t_is["value"].upper() == "IS":
                                    t_null = active[next_check + 1]
                                    if t_null["type"] == "KEYWORD" and t_null["value"].upper() == "NULL":
                                        t_and = active[next_check + 2]
                                        if t_and["type"] == "KEYWORD" and t_and["value"].upper() == "AND":
                                            op2_check, next_check2 = parse_operand(next_check + 3)
                                            if op2_check and op2_check.lower() == op2_str.lower() and next_check2 < num_active:
                                                t_is2 = active[next_check2]
                                                if t_is2["type"] == "KEYWORD" and t_is2["value"].upper() == "IS":
                                                    t_null2 = active[next_check2 + 1]
                                                    if t_null2["type"] == "KEYWORD" and t_null2["value"].upper() == "NULL":
                                                        end_idx = next_check2 + 2
                                                        if has_parens:
                                                            if end_idx < num_active and active[end_idx]["type"] == "PAREN" and active[end_idx]["value"] == ")":
                                                                end_idx += 1
                                                            else:
                                                                end_idx = None
                                                        
                                                        if end_idx is not None:
                                                            violations.append({
                                                                "start_offset": active[i]["start"],
                                                                "end_offset": active[end_idx - 1]["end"],
                                                                "line": active[i]["line"],
                                                                "replacement": f"COALESCE({op1_str}, -1) = COALESCE({op2_str}, -1)"
                                                            })
                                                            i = end_idx
                                                            continue

            # 2. Try to match reverse pattern: (a IS NULL AND b IS NULL) OR a = b
            has_parens = False
            check_idx = i
            if check_idx < num_active and active[check_idx]["type"] == "PAREN" and active[check_idx]["value"] == "(":
                has_parens = True
                check_idx += 1
                
            op1_str, next_idx = parse_operand(check_idx)
            if op1_str and next_idx < num_active:
                t_is = active[next_idx]
                if t_is["type"] == "KEYWORD" and t_is["value"].upper() == "IS":
                    t_null = active[next_idx + 1]
                    if t_null["type"] == "KEYWORD" and t_null["value"].upper() == "NULL":
                        t_and = active[next_idx + 2]
                        if t_and["type"] == "KEYWORD" and t_and["value"].upper() == "AND":
                            op2_str, next_idx2 = parse_operand(next_idx + 3)
                            if op2_str and next_idx2 < num_active:
                                t_is2 = active[next_idx2]
                                if t_is2["type"] == "KEYWORD" and t_is2["value"].upper() == "IS":
                                    t_null2 = active[next_idx2 + 1]
                                    if t_null2["type"] == "KEYWORD" and t_null2["value"].upper() == "NULL":
                                        end_idx = next_idx2 + 2
                                        if has_parens:
                                            if end_idx < num_active and active[end_idx]["type"] == "PAREN" and active[end_idx]["value"] == ")":
                                                end_idx += 1
                                            else:
                                                end_idx = None
                                        
                                        if end_idx is not None and end_idx < num_active:
                                            t_or = active[end_idx]
                                            if t_or["type"] == "KEYWORD" and t_or["value"].upper() == "OR":
                                                op1_check, next_check = parse_operand(end_idx + 1)
                                                if op1_check and op1_check.lower() == op1_str.lower() and next_check < num_active:
                                                    t_eq = active[next_check]
                                                    if t_eq["type"] == "OPERATOR" and t_eq["value"] == "=":
                                                        op2_check, next_check2 = parse_operand(next_check + 1)
                                                        if op2_check and op2_check.lower() == op2_str.lower():
                                                            violations.append({
                                                                "start_offset": active[i]["start"],
                                                                "end_offset": active[next_check2 - 1]["end"],
                                                                "line": active[i]["line"],
                                                                "replacement": f"COALESCE({op1_check}, -1) = COALESCE({op2_check}, -1)"
                                                            })
                                                            i = next_check2
                                                            continue

            # 3. Match: x = v OR x IS NULL
            op1_str, next_idx = parse_operand(i)
            if op1_str and next_idx < num_active:
                t_eq = active[next_idx]
                if t_eq["type"] == "OPERATOR" and t_eq["value"] == "=":
                    val_str, next_idx2 = parse_operand(next_idx + 1)
                    if val_str and next_idx2 < num_active:
                        t_or = active[next_idx2]
                        if t_or["type"] == "KEYWORD" and t_or["value"].upper() == "OR":
                            op1_check, next_check = parse_operand(next_idx2 + 1)
                            if op1_check and op1_check.lower() == op1_str.lower() and next_check < num_active:
                                t_is = active[next_check]
                                if t_is["type"] == "KEYWORD" and t_is["value"].upper() == "IS":
                                    t_null = active[next_check + 1]
                                    if t_null["type"] == "KEYWORD" and t_null["value"].upper() == "NULL":
                                        violations.append({
                                            "start_offset": active[i]["start"],
                                            "end_offset": t_null["end"],
                                            "line": active[i]["line"],
                                            "replacement": f"COALESCE({op1_str}, -1) = {val_str}"
                                        })
                                        i = next_check + 2
                                        continue

            # 4. Match: x IS NULL OR x = v
            op1_str, next_idx = parse_operand(i)
            if op1_str and next_idx < num_active:
                t_is = active[next_idx]
                if t_is["type"] == "KEYWORD" and t_is["value"].upper() == "IS":
                    t_null = active[next_idx + 1]
                    if t_null["type"] == "KEYWORD" and t_null["value"].upper() == "NULL":
                        t_or = active[next_idx + 2]
                        if t_or["type"] == "KEYWORD" and t_or["value"].upper() == "OR":
                            op1_check, next_check = parse_operand(next_idx + 3)
                            if op1_check and op1_check.lower() == op1_str.lower() and next_check < num_active:
                                t_eq = active[next_check]
                                if t_eq["type"] == "OPERATOR" and t_eq["value"] == "=":
                                    val_str, next_check2 = parse_operand(next_check + 1)
                                    if val_str:
                                        violations.append({
                                            "start_offset": active[i]["start"],
                                            "end_offset": active[next_check2 - 1]["end"],
                                            "line": active[i]["line"],
                                            "replacement": f"COALESCE({op1_str}, -1) = {val_str}"
                                        })
                                        i = next_check2
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
                    message="Predicate structure should be standardized to COALESCE format.",
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
