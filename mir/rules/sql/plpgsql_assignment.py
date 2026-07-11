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
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "NEW.file_uploader = TRUE;",
            "correct": "NEW.file_uploader := TRUE;"
        }
    ]
    additional_validations = [
        "NEW.resolution := 'BY_POINT';"
    ]

    def _check_tokens(self, tokens: List[dict], offset_delta: int, violations: List[dict]):
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
            active_tokens = [t for t in stmt if t["type"] not in ("WHITESPACE", "COMMENT")]
            if not active_tokens:
                continue
                
            first_tok = active_tokens[0]
            if first_tok["type"] in ("KEYWORD", "IDENTIFIER") and first_tok["value"].upper() in EXCLUDED_STARTERS:
                continue
                
            # Find the first '=' operator that is not part of ':='
            for idx, t in enumerate(stmt):
                if t["type"] == "OPERATOR" and t["value"] == "=":
                    # Check if preceded by ':' (possibly with whitespace in between, but usually adjacent)
                    is_assignment = True
                    prev_idx = idx - 1
                    while prev_idx >= 0 and stmt[prev_idx]["type"] in ("WHITESPACE", "COMMENT"):
                        prev_idx -= 1
                    if prev_idx >= 0 and stmt[prev_idx]["value"] == ":":
                        is_assignment = False
                        
                    if is_assignment:
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
                    message="PL/pgSQL assignments should use the standard assignment operator (:=) instead of =.",
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
