from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren, get_token_depths

class SubqueryIndentRule(BaseRule):
    rule_id = "IR-subquery-indent"
    description = "Subqueries should be indented 4 spaces relative to their opening parenthesis."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM (\nSELECT a FROM t\n) sub;",
            "correct": "SELECT * FROM (\n        SELECT a FROM t\n    ) sub;"
        },
        {
            "violating": "SELECT * FROM users WHERE id IN (\nSELECT user_id FROM roles\n);",
            "correct": "SELECT * FROM users WHERE id IN (\n    SELECT user_id FROM roles\n);"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "PAREN" and tok["value"] == "(":
                next_active = None
                for idx in range(i + 1, n):
                    if tokens[idx]["type"] == "WHITESPACE":
                        continue
                    if tokens[idx]["type"] != "COMMENT":
                        next_active = tokens[idx]
                        break
                        
                if next_active and next_active["type"] == "KEYWORD" and next_active["value"].upper() == "SELECT":
                    close_idx = find_matching_paren(tokens, i)
                    if close_idx is None:
                        continue
                        
                    if tok["line"] == tokens[close_idx]["line"]:
                        continue
                        
                    line_start = content.rfind("\n", 0, tok["start"]) + 1
                    line_prefix = content[line_start:tok["start"]]
                    open_indent = ""
                    for char in line_prefix:
                        if char in (" ", "\t"):
                            open_indent += char
                        else:
                            break
                            
                    # Scan backward on the same line to find the nearest preceding token
                    is_from_join = False
                    for idx in range(i - 1, -1, -1):
                        if tokens[idx]["line"] != tok["line"]:
                            break
                        if tokens[idx]["type"] != "WHITESPACE" and tokens[idx]["type"] != "COMMENT":
                            if tokens[idx]["type"] == "KEYWORD" and tokens[idx]["value"].upper() in ("FROM", "JOIN"):
                                is_from_join = True
                            break
                            
                    expected_close_indent = open_indent + "    " if is_from_join else open_indent
                    expected_content_indent = expected_close_indent + "    "
                    
                    lines = content.splitlines()
                    start_line = tok["line"] + 1
                    end_line = tokens[close_idx]["line"]
                    
                    needs_fix = False
                    
                    close_line_text = lines[end_line - 1]
                    stripped_close = close_line_text.lstrip()
                    if stripped_close.startswith(")"):
                        actual_close_indent = close_line_text[:len(close_line_text) - len(stripped_close)]
                        if actual_close_indent != expected_close_indent:
                            needs_fix = True
                            
                    for line_no in range(start_line, end_line):
                        line_text = lines[line_no - 1]
                        if line_text.strip() != "":
                            stripped = line_text.lstrip()
                            actual_indent = line_text[:len(line_text) - len(stripped)]
                            if not actual_indent.startswith(expected_content_indent):
                                needs_fix = True
                                break
                                
                    if needs_fix:
                        violations.append({
                            "open_tok": tok,
                            "close_tok": tokens[close_idx],
                            "open_line": tok["line"],
                            "close_line": tokens[close_idx]["line"],
                            "content_indent": expected_content_indent,
                            "close_indent": expected_close_indent
                        })
                        
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["open_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Subquery contents or closing parenthesis are not indented correctly.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        lines = content.splitlines()
        offending.sort(key=lambda x: x["open_line"], reverse=True)
        
        for item in offending:
            start_line = item["open_line"] + 1
            end_line = item["close_line"]
            expected_content_indent = item["content_indent"]
            expected_close_indent = item["close_indent"]
            
            for line_no in range(start_line, end_line):
                line_text = lines[line_no - 1]
                if line_text.strip() != "":
                    lines[line_no - 1] = expected_content_indent + line_text.lstrip()
                    
            close_line_text = lines[end_line - 1]
            stripped_close = close_line_text.lstrip()
            if stripped_close.startswith(")"):
                lines[end_line - 1] = expected_close_indent + stripped_close
                
        ending = "\n" if content.endswith("\n") else ""
        return "\n".join(lines) + ending
