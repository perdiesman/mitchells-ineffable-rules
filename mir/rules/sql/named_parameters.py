from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren

EXCLUDED_FUNCTIONS = {
    "COALESCE", "COUNT", "SUM", "AVG", "MIN", "MAX", "CONCAT", "LOWER", "UPPER",
    "SUBSTR", "SUBSTRING", "TRIM", "REPLACE", "NULLIF", "GREATEST", "LEAST",
    "VALUES", "ARRAY", "DECODE", "ROW_TO_JSON", "JSON_BUILD_OBJECT", "JSONB_BUILD_OBJECT",
    "TO_JSON", "TO_JSONB", "EXISTS", "ABS", "ROUND", "CEIL", "FLOOR", "CAST",
    "NOW", "GETDATE", "LEAST", "GREATEST", "IFNULL", "NVL",
    "UNNEST", "ARRAY_CAT", "ARRAY_APPEND", "ARRAY_PREPEND", "ARRAY_TO_STRING",
    "STRING_TO_ARRAY", "REGEXP_REPLACE", "REGEXP_MATCH", "REGEXP_SPLIT_TO_ARRAY",
    "REGEXP_SPLIT_TO_TABLE", "SPLIT_PART", "DATE_PART", "DATE_TRUNC",
    "AGE", "CLOCK_TIMESTAMP", "STATEMENT_TIMESTAMP", "TRANSACTION_TIMESTAMP"
}

RESERVED_WORDS = {
    "SELECT", "FROM", "WHERE", "AND", "OR", "ON", "IN", "NOT", "INSERT", "UPDATE",
    "DELETE", "CREATE", "ALTER", "DROP", "WITH", "IF", "WHILE", "LOOP", "FOR",
    "RETURN", "RAISE", "CASE", "WHEN", "THEN", "ELSE", "END", "DECLARE", "BEGIN"
}

class NamedParametersRule(BaseRule):
    rule_id = "IR-named-parameters"
    description = "Enforce named parameter notation (:= or =>) in function calls with 3 or more arguments."
    category = "routines"
    is_fixable = "no"
    enabled_by_default = False

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT calculate_statistics(105, true, 'monthly_aggregation');",
            "correct": "SELECT calculate_statistics(user_id := 105, include_deactivated := true, run_mode := 'monthly_aggregation');"
        }
    ]
    additional_validations = [
        "SELECT my_func(1, 2);",
        "SELECT coalesce(a, b, c, d);",
        "SELECT my_func(a := 1, b := 2, c := 3);"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)

        # Map token ids to index in tokens
        token_to_idx = {id(t): idx for idx, t in enumerate(tokens)}

        # Filter active tokens
        active = []
        for t in tokens:
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)

        num_active = len(active)
        i = 0
        while i < num_active:
            t = active[i]
            if t["type"] in ("IDENTIFIER", "KEYWORD") and t["value"].upper() not in RESERVED_WORDS and t["value"].upper() not in EXCLUDED_FUNCTIONS:
                # Check if followed by (
                if i + 1 < num_active and active[i + 1]["type"] == "PAREN" and active[i + 1]["value"] == "(":
                    open_paren_idx = token_to_idx[id(active[i + 1])]
                    close_paren_idx = find_matching_paren(tokens, open_paren_idx)
                    
                    if close_paren_idx is not None:
                        # Collect inside active tokens
                        inside_active = []
                        for k in range(i + 2, num_active):
                            t_k = active[k]
                            t_k_idx = token_to_idx[id(t_k)]
                            if t_k_idx >= close_paren_idx:
                                break
                            inside_active.append(t_k)
                        
                        # Split by top-level commas
                        args = []
                        current_arg = []
                        depth = 0
                        for ta in inside_active:
                            if ta["type"] == "PAREN" and ta["value"] == "(":
                                depth += 1
                            elif ta["type"] == "PAREN" and ta["value"] == ")":
                                depth -= 1
                            
                            if ta["value"] == "," and depth == 0:
                                args.append(current_arg)
                                current_arg = []
                            else:
                                current_arg.append(ta)
                        if current_arg or len(args) > 0:
                            args.append(current_arg)
                        
                        # If 3 or more arguments, check if all use := or =>
                        if len(args) >= 3:
                            has_unnamed = False
                            for arg in args:
                                # Check if arg contains := or => at depth 0
                                arg_depth = 0
                                has_assignment = False
                                for arg_idx_a in range(len(arg)):
                                    arg_tok = arg[arg_idx_a]
                                    if arg_tok["type"] == "PAREN" and arg_tok["value"] == "(":
                                        arg_depth += 1
                                    elif arg_tok["type"] == "PAREN" and arg_tok["value"] == ")":
                                        arg_depth -= 1
                                    
                                    if arg_depth == 0:
                                        if arg_tok["value"] in (":=", "=>"):
                                            has_assignment = True
                                            break
                                        if arg_idx_a + 1 < len(arg):
                                            next_arg_tok = arg[arg_idx_a + 1]
                                            if (
                                                (arg_tok["value"] == ":" and next_arg_tok["value"] == "=")
                                                or (arg_tok["value"] == "=" and next_arg_tok["value"] == ">")
                                            ):
                                                has_assignment = True
                                                break
                                if not has_assignment:
                                    has_unnamed = True
                                    break
                            
                            if has_unnamed:
                                violations.append({
                                    "token": t,
                                    "line": t["line"],
                                    "message": f"Function call '{t['value']}' on line {t['line']} must use named parameter notation (:= or =>) for all arguments."
                                })
                    # Move past the matching paren in active list
                    # We can find the active index of the matching close paren
                    if close_paren_idx is not None:
                        close_paren_tok = tokens[close_paren_idx]
                        if id(close_paren_tok) in token_to_idx:
                            # find index in active list
                            for active_idx in range(i + 2, num_active):
                                if id(active[active_idx]) == id(close_paren_tok):
                                    i = active_idx
                                    break
            i += 1

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
