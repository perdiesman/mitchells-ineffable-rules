from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren

class SubqueryDepthLimitRule(BaseRule):
    rule_id = "IR-subquery-depth-limit"
    description = "Subquery nesting depth should not exceed the configured limit (default: 3). When over the limit, Common Table Expressions (CTEs) are preferred."
    category = "queries"
    is_fixable = "no"
    enabled_by_default = True
    
    default_config = {
        "severity": "warning"
    }
    config_options = {
        "max_depth": {
            "default": 3,
            "description": "Maximum allowed subquery nesting depth."
        }
    }
    
    examples = [
        {
            "violating": "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM users) u4) u3) u2) u1;"
        }
    ]
    additional_validations = [
        "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM users) u3) u2) u1;",
        "WITH u2 AS (SELECT * FROM users) SELECT * FROM u2;"
    ]

    def _find_violations(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_depth = self.get_config_value(
            rule_config,
            "max_depth",
            default_value=3
        )
        
        tokens = tokenize_sql(content)
        n = len(tokens)
        
        subqueries = []
        for i in range(n):
            tok = tokens[i]
            if tok["type"] == "PAREN" and tok["value"] == "(":
                close_idx = find_matching_paren(tokens, i)
                if close_idx is not None:
                    first_inner = None
                    for idx in range(i + 1, close_idx):
                        if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                            first_inner = tokens[idx]
                            break
                    if first_inner and first_inner["type"] == "KEYWORD" and first_inner["value"].upper() == "SELECT":
                        # Check if it is a CTE definition (preceded by AS, which is preceded by an identifier)
                        is_cte = False
                        prev1_idx = None
                        for idx in range(i - 1, -1, -1):
                            if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                                prev1_idx = idx
                                break
                        if prev1_idx is not None and tokens[prev1_idx]["value"].upper() == "AS":
                            prev2_idx = None
                            for idx in range(prev1_idx - 1, -1, -1):
                                if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                                    prev2_idx = idx
                                    break
                            if prev2_idx is not None and tokens[prev2_idx]["type"] == "IDENTIFIER":
                                is_cte = True
                                
                        if not is_cte:
                            subqueries.append((i, close_idx, first_inner))
                        
        violations = []
        for i, close_idx, first_inner in subqueries:
            depth = 0
            for other_start, other_end, _ in subqueries:
                if other_start < i and close_idx < other_end:
                    depth += 1
            if depth >= max_depth:
                violations.append({
                    "token": first_inner,
                    "depth": depth,
                    "max_depth": max_depth
                })
                
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        
        for item in offending:
            tok = item["token"]
            depth = item["depth"]
            max_depth = item["max_depth"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message=(
                        f"Subquery nesting depth ({depth + 1}) exceeds the configured limit of {max_depth}. "
                        "Rewrite the query to use Common Table Expressions (CTEs) instead."
                    ),
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=False
                )
            )
        return violations
