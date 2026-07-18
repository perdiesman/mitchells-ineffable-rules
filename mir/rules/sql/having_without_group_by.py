from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class HavingWithoutGroupByRule(BaseRule):
    rule_id = "IR-having-without-group-by"
    description = "Detect HAVING clauses used without a corresponding GROUP BY clause."
    category = "queries"
    is_fixable = "no"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT count(*) FROM users HAVING count(*) > 5;",
            "correct": "SELECT count(*) FROM users WHERE id > 0;"
        }
    ]
    additional_validations = [
        "SELECT role, count(*) FROM users GROUP BY role HAVING count(*) > 5;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)

        # Filter active tokens
        active = []
        for t in tokens:
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)

        num_active = len(active)
        stack = []
        depth = 0

        i = 0
        while i < num_active:
            t = active[i]
            val_upper = t["value"].upper()

            if t["type"] == "PAREN" and t["value"] == "(":
                depth += 1
            elif t["type"] == "PAREN" and t["value"] == ")":
                # Pop contexts that are at depth >= current depth
                # We check before decrementing depth
                new_stack = []
                for ctx in stack:
                    if ctx["depth"] >= depth:
                        if ctx["has_having"] and not ctx["has_group_by"]:
                            violations.append({
                                "token": ctx["having_token"],
                                "line": ctx["having_token"]["line"],
                                "message": f"HAVING clause on line {ctx['having_token']['line']} used without a corresponding GROUP BY clause."
                            })
                    else:
                        new_stack.append(ctx)
                stack = new_stack
                depth -= 1
            elif t["type"] == "KEYWORD" and val_upper == "SELECT":
                stack.append({
                    "depth": depth,
                    "has_group_by": False,
                    "has_having": False,
                    "having_token": None
                })
            elif t["type"] == "KEYWORD" and val_upper == "GROUP":
                if i + 1 < num_active and active[i + 1]["value"].upper() == "BY":
                    # Mark the active block matching the current depth
                    for ctx in reversed(stack):
                        if ctx["depth"] == depth:
                            ctx["has_group_by"] = True
                            break
                    i += 1
            elif t["type"] == "KEYWORD" and val_upper == "HAVING":
                for ctx in reversed(stack):
                    if ctx["depth"] == depth:
                        ctx["has_having"] = True
                        ctx["having_token"] = t
                        break
            elif t["value"] == ";":
                # Pop all contexts
                for ctx in stack:
                    if ctx["has_having"] and not ctx["has_group_by"]:
                        violations.append({
                            "token": ctx["having_token"],
                            "line": ctx["having_token"]["line"],
                            "message": f"HAVING clause on line {ctx['having_token']['line']} used without a corresponding GROUP BY clause."
                        })
                stack = []

            i += 1

        # Pop any remaining contexts
        for ctx in stack:
            if ctx["has_having"] and not ctx["has_group_by"]:
                violations.append({
                    "token": ctx["having_token"],
                    "line": ctx["having_token"]["line"],
                    "message": f"HAVING clause on line {ctx['having_token']['line']} used without a corresponding GROUP BY clause."
                })

        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        for v in offending:
            line_idx = v["line"] - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=v["line"],
                message=v["message"],
                offending_lines=[offending_line],
                is_fixable=False
            ))
        return violations
