from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

EXCLUDED_STARTERS = {
    "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "WITH",
    "RAISE", "RETURN", "CLOSE", "OPEN", "FETCH", "LOOP", "WHILE", "FOR", "IF",
    "CASE", "BEGIN", "DECLARE", "REFRESH", "COMMIT", "ROLLBACK", "END",
    "CALL", "PERFORM", "GET", "MOVE", "EXPLAIN", "LOCK", "COPY", "GRANT", "REVOKE",
    "EXECUTE", "TRUNCATE", "REINDEX", "ANALYZE", "VACUUM"
}

class PlpgsqlAssignmentRule(BaseRule):
    rule_id = "IR-plpgsql-assignment"
    description = "PL/pgSQL variable and trigger field assignments must use the standard assignment operator (:=)."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    exclude_recursive = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "BEGIN\n    NEW.file_uploader := TRUE;\nEND;",
            "correct": "BEGIN\n    NEW.file_uploader = TRUE;\nEND;"
        },
        {
            "violating": "DECLARE\n    my_var INT = 1;\nBEGIN\nEND;",
            "correct": "DECLARE\n    my_var INT := 1;\nBEGIN\nEND;"
        }
    ]
    additional_validations = [
        "BEGIN\n    NEW.resolution = 'BY_POINT';\nEND;"
    ]

    def _check_tokens(self, tokens: List[dict], offset_delta: int, violations: List[dict]):
        in_declare = False
        in_body = False
        
        # Group tokens into statements by semicolon
        statements = []
        current_statement = []
        for t in tokens:
            current_statement.append(t)
            if t["type"] == "SEMI":
                statements.append(current_statement)
                current_statement = []
        if current_statement:
            statements.append(current_statement)
            
        for stmt in statements:
            # Update state based on keywords inside this statement
            for t in stmt:
                val_up = t["value"].upper()
                if val_up == "DECLARE":
                    in_declare = True
                    in_body = False
                elif val_up == "BEGIN":
                    in_declare = False
                    in_body = True
            
            active_tokens = [t for t in stmt if t["type"] not in ("WHITESPACE", "COMMENT")]
            if not active_tokens:
                continue
                
            first_tok_idx = 0
            while first_tok_idx < len(active_tokens) and active_tokens[first_tok_idx]["value"].upper() in ("DECLARE", "BEGIN", "EXCEPTION"):
                first_tok_idx += 1
                
            if first_tok_idx >= len(active_tokens):
                continue
                
            first_tok = active_tokens[first_tok_idx]
            if first_tok["type"] in ("KEYWORD", "IDENTIFIER") and first_tok["value"].upper() in EXCLUDED_STARTERS:
                continue
                
            # Find the first '=' operator (or ':=' combination)
            for idx, t in enumerate(stmt):
                if t["type"] == "OPERATOR" and t["value"] == "=":
                    # Check if preceded by ':'
                    prev_idx = idx - 1
                    while prev_idx >= 0 and stmt[prev_idx]["type"] in ("WHITESPACE", "COMMENT"):
                        prev_idx -= 1
                        
                    is_colon_equals = (prev_idx >= 0 and stmt[prev_idx]["value"] == ":")
                    
                    if is_colon_equals:
                        # It is ':=' operator!
                        # In the body (or outside declare), we want '=' instead of ':='!
                        if in_body or not in_declare:
                            colon_tok = stmt[prev_idx]
                            violations.append({
                                "token": t,
                                "start_offset": colon_tok["start"] + offset_delta,
                                "end_offset": t["end"] + offset_delta,
                                "replacement": "=",
                                "line": t["line"]
                            })
                    else:
                        # It is '=' operator!
                        # In the declare block, we want ':=' instead of '='!
                        if in_declare:
                            violations.append({
                                "token": t,
                                "start_offset": t["start"] + offset_delta,
                                "end_offset": t["end"] + offset_delta,
                                "replacement": ":=",
                                "line": t["line"]
                            })
                    # Only check/replace the first assignment operator in the statement
                    break

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        
        # Check outer tokens
        self._check_tokens(tokens, 0, violations)
        
        # Check inside dollar-quoted function bodies
        for t in tokens:
            if t["type"] == "STRING" and t["value"].startswith("$"):
                val = t["value"]
                dollar_idx = val.find("$", 1)
                if dollar_idx == -1:
                    continue
                tag = val[:dollar_idx + 1]
                if not val.endswith(tag):
                    continue
                    
                body = val[len(tag):-len(tag)]
                body_lines = body.splitlines()
                first_line = None
                for line in body_lines:
                    if line.strip():
                        first_line = line
                        break
                if first_line is None:
                    continue
                    
                first_word = first_line.strip().split()[0].upper() if first_line.strip() else ""
                if first_word not in ("DECLARE", "BEGIN"):
                    continue
                    
                body_tokens = tokenize_sql(body)
                body_violations = []
                self._check_tokens(body_tokens, t["start"] + len(tag), body_violations)
                violations.extend(body_violations)
                
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
                    message="PL/pgSQL assignments must use '=' in the function body and ':=' in the DECLARE section.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
        offending.sort(key=lambda x: x["start_offset"], reverse=True)
        chars = list(content)
        for item in offending:
            start = item["start_offset"]
            end = item["end_offset"]
            repl = item["replacement"]
            chars[start:end] = list(repl)
        return "".join(chars)
