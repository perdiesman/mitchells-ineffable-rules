from typing import Any, ClassVar

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql


class NullCoalesceRule(BaseRule):
    commit_profile = True
    commit_semantic_rewrite = True
    embedded_safe = True
    rule_id = "IR-null-coalesce"
    description = "Standardize isolated explicit -1 fallback predicates to COALESCE(x, -1); preserve nullable-column equality and surrounding boolean precedence."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE active = -1 OR active IS NULL;",
            "correct": "SELECT * FROM users WHERE COALESCE(active, -1) = -1;",
        }
    ]
    additional_validations: ClassVar[list[str]] = [
        "SELECT * FROM t1 JOIN t2 ON t1.id = t2.id OR (t1.id IS NULL AND t2.id IS NULL);",
        "SELECT * FROM items WHERE enabled AND owner_id = -1 OR owner_id IS NULL;",
        "SELECT * FROM items WHERE owner_id = -1 OR owner_id IS NULL AND enabled;",
        "SELECT * FROM items WHERE NOT owner_id = -1 OR owner_id IS NULL;",
    ]

    def _find_violations(self, content: str) -> list[dict]:
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
            # Match only an explicit -1 fallback, never two nullable columns.
            op1_str, next_idx = parse_operand(i)
            if op1_str and next_idx < num_active:
                t_eq = active[next_idx]
                if t_eq["type"] == "OPERATOR" and t_eq["value"] == "=":
                    val_str, next_idx2 = parse_operand(next_idx + 1)
                    if val_str == "-1" and next_idx2 < num_active:
                        t_or = active[next_idx2]
                        if t_or["type"] == "KEYWORD" and t_or["value"].upper() == "OR":
                            op1_check, next_check = parse_operand(next_idx2 + 1)
                            if op1_check and op1_check.lower() == op1_str.lower() and next_check < num_active:
                                t_is = active[next_check]
                                if t_is["type"] == "KEYWORD" and t_is["value"].upper() == "IS" and next_check + 1 < num_active:
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

            # Match the same explicit fallback in reverse order.
            op1_str, next_idx = parse_operand(i)
            if op1_str and next_idx < num_active:
                t_is = active[next_idx]
                if t_is["type"] == "KEYWORD" and t_is["value"].upper() == "IS" and next_idx + 2 < num_active:
                    t_null = active[next_idx + 1]
                    if t_null["type"] == "KEYWORD" and t_null["value"].upper() == "NULL":
                        t_or = active[next_idx + 2]
                        if t_or["type"] == "KEYWORD" and t_or["value"].upper() == "OR":
                            op1_check, next_check = parse_operand(next_idx + 3)
                            if op1_check and op1_check.lower() == op1_str.lower() and next_check < num_active:
                                t_eq = active[next_check]
                                if t_eq["type"] == "OPERATOR" and t_eq["value"] == "=":
                                    val_str, next_check2 = parse_operand(next_check + 1)
                                    if val_str == "-1":
                                        violations.append({
                                            "start_offset": active[i]["start"],
                                            "end_offset": active[next_check2 - 1]["end"],
                                            "line": active[i]["line"],
                                            "replacement": f"COALESCE({op1_str}, -1) = {val_str}"
                                        })
                                        i = next_check2
                                        continue
            i += 1

        safe = []
        for item in violations:
            before = next(
                (
                    token
                    for token in reversed(active)
                    if token["end"] <= item["start_offset"]
                ),
                None,
            )
            after = next(
                (token for token in active if token["start"] >= item["end_offset"]),
                None,
            )
            if (
                before is None
                or before["value"].upper() in {"WHERE", "ON", "HAVING", "SELECT", "("}
            ) and (after is None or after["value"] in {")", ";"}):
                safe.append(item)
        return safe

    def check(
        self, content: str, file_path: str, rule_config: dict[str, Any]
    ) -> list[Violation]:
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

    def fix(self, content: str, file_path: str, rule_config: dict[str, Any]) -> str:
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
