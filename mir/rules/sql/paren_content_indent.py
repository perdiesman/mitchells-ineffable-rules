from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren, get_token_depths, is_values_multi

class ParenContentIndentRule(BaseRule):
    rule_id = "IR-paren-content-indent"
    description = "Content inside multi-line parentheses should be indented 4 spaces relative to the opening parenthesis, and the closing parenthesis should align with it."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT (\na +\nb\n) FROM users;",
            "correct": "SELECT (\n    a +\n    b\n) FROM users;"
        },
        {
            "violating": "SELECT COALESCE(\na,\nb\n) FROM users;",
            "correct": "SELECT COALESCE(\n        a,\n        b\n    ) FROM users;"
        },
        {
            "violating": "INSERT INTO t (c) VALUES\n(1),\n    (2);",
            "correct": "INSERT INTO t(c) VALUES\n    (1),\n    (2);"
        }
    ]
    additional_validations = [
        'SELECT COALESCE(a, b) FROM users;',
        'SELECT (a + b) FROM users;',
        'INSERT INTO t(c) VALUES (1);',
        'INSERT INTO t(c) VALUES\n    (1),\n    (2);'
    ]

    def _get_line_expected_indents(self, content: str) -> Dict[int, str]:
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        n = len(tokens)
        
        # Find all multiline parentheses that are NOT subqueries
        multiline_parens = []
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
                    continue
                    
                close_idx = find_matching_paren(tokens, i)
                if close_idx is not None:
                    close_tok = tokens[close_idx]
                    if tok["line"] < close_tok["line"]:
                        multiline_parens.append((i, close_idx, tok, close_tok))
                        
        # Map each line to its expected indent
        expected_indents = {}
        
        for line_no in range(1, len(lines) + 1):
            line = lines[line_no - 1]
            if line.strip() == "":
                continue
                
            # Find all active multiline parentheses for this line
            active = []
            for open_idx, close_idx, open_tok, close_tok in multiline_parens:
                # Is L a content line?
                if open_tok["line"] < line_no < close_tok["line"]:
                    active.append((open_idx, "content", open_tok, close_tok))
                # Is L the closing line, and the line starts with ')'?
                elif line_no == close_tok["line"] and line.lstrip().startswith(")"):
                    active.append((open_idx, "close", open_tok, close_tok))
                    
            if not active:
                continue
                
            # Sort by open_idx descending to get the innermost active one
            active.sort(key=lambda x: x[0], reverse=True)
            inner = active[0]
            open_tok = inner[2]
            
            # Get opening indent of open_tok's line
            open_line_text = lines[open_tok["line"] - 1]
            open_indent = open_line_text[:len(open_line_text) - len(open_line_text.lstrip())]
            
            # Check if this parenthesis is function-like
            prev_tok = None
            try:
                open_idx = tokens.index(open_tok)
                for p_idx in range(open_idx - 1, -1, -1):
                    if tokens[p_idx]["type"] not in ("WHITESPACE", "COMMENT"):
                        prev_tok = tokens[p_idx]
                        break
            except ValueError:
                pass
                
            is_func_like = False
            if prev_tok:
                val_up = prev_tok["value"].upper()
                is_val_multi = (val_up == "VALUES" and is_values_multi(tokens, open_idx))
                if not is_val_multi and (prev_tok["type"] == "IDENTIFIER" or val_up in ("VALUES", "TABLE", "COALESCE", "ROW_NUMBER", "NULLIF", "GREATEST", "LEAST", "IN", "ANY", "SOME")):
                    is_func_like = True

            if inner[1] == "content":
                expected_indents[line_no] = open_indent + ("        " if is_func_like else "    ")
            else:
                expected_indents[line_no] = open_indent + ("    " if is_func_like else "")
                
        return expected_indents

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        
        # Check opening parenthesis position
        tokens = tokenize_sql(content)
        for i, tok in enumerate(tokens):
            if tok["type"] == "PAREN" and tok["value"] == "(":
                prev_tok = None
                for p_idx in range(i - 1, -1, -1):
                    if tokens[p_idx]["type"] not in ("WHITESPACE", "COMMENT"):
                        prev_tok = tokens[p_idx]
                        break
                if prev_tok:
                    val_up = prev_tok["value"].upper()
                    is_val_multi = (val_up == "VALUES" and is_values_multi(tokens, i))
                    if is_val_multi:
                        prev_line_text = lines[prev_tok["line"] - 1]
                        prev_indent = prev_line_text[:len(prev_line_text) - len(prev_line_text.lstrip())]
                        expected_indent = prev_indent + "    "
                        tok_line_text = lines[tok["line"] - 1]
                        actual_indent = tok_line_text[:len(tok_line_text) - len(tok_line_text.lstrip())]
                        mismatch = (tok["line"] <= prev_tok["line"] or actual_indent != expected_indent or not tok_line_text.lstrip().startswith("("))
                        if mismatch:
                            violations.append(
                                Violation(
                                    rule_id=self.rule_id,
                                    line_number=tok["line"],
                                    message="Opening parenthesis of multiple VALUES sets must be on the next line, indented at 4 spaces.",
                                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                                    is_fixable=True
                                )
                            )
                    else:
                        is_keyword_op = val_up in ("VALUES", "TABLE", "IN", "ANY", "SOME")
                        is_func_like = (prev_tok["type"] == "IDENTIFIER") or (val_up in ("COALESCE", "ROW_NUMBER", "NULLIF", "GREATEST", "LEAST")) or is_keyword_op
                        if is_func_like:
                            if prev_tok["line"] < tok["line"]:
                                violations.append(
                                    Violation(
                                        rule_id=self.rule_id,
                                        line_number=tok["line"],
                                        message="Opening parenthesis of a function call or definition must be on the same line as the function name.",
                                        offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                                        is_fixable=True
                                    )
                                )
                            else:
                                start_ws = prev_tok["end"]
                                end_ws = tok["start"]
                                spaces = content[start_ws:end_ws]
                                expected_spaces = " " if is_keyword_op else ""
                                if spaces != expected_spaces:
                                    violations.append(
                                        Violation(
                                            rule_id=self.rule_id,
                                            line_number=tok["line"],
                                            message=f"Spacing before parenthesis is incorrect. Expected {repr(expected_spaces)}, got {repr(spaces)}.",
                                            offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                                            is_fixable=True
                                        )
                                    )
                            
        expected_indents = self._get_line_expected_indents(content)
        for line_no, expected_indent in expected_indents.items():
            line_text = lines[line_no - 1]
            actual_indent = line_text[:len(line_text) - len(line_text.lstrip())]
            
            is_close_line = line_text.lstrip().startswith(")")
            if is_close_line:
                mismatch = actual_indent != expected_indent
            else:
                mismatch = not actual_indent.startswith(expected_indent)
                
            if mismatch:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=line_no,
                        message="Content inside parentheses or closing parenthesis are not indented correctly.",
                        offending_lines=[line_text],
                        is_fixable=True
                    )
                )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        # First fix opening parenthesis position
        tokens = tokenize_sql(content)
        edits = []
        for i, tok in enumerate(tokens):
            if tok["type"] == "PAREN" and tok["value"] == "(":
                prev_tok = None
                for p_idx in range(i - 1, -1, -1):
                    if tokens[p_idx]["type"] not in ("WHITESPACE", "COMMENT"):
                        prev_tok = tokens[p_idx]
                        break
                if prev_tok:
                    val_up = prev_tok["value"].upper()
                    is_val_multi = (val_up == "VALUES" and is_values_multi(tokens, i))
                    if is_val_multi:
                        lines_orig = content.splitlines()
                        prev_line_text = lines_orig[prev_tok["line"] - 1] if prev_tok["line"] - 1 < len(lines_orig) else ""
                        prev_indent = prev_line_text[:len(prev_line_text) - len(prev_line_text.lstrip())]
                        expected_replacement = "\n" + prev_indent + "    "
                        start_ws = prev_tok["end"]
                        end_ws = tok["start"]
                        if content[start_ws:end_ws] != expected_replacement:
                            edits.append((start_ws, end_ws, expected_replacement))
                    else:
                        is_keyword_op = val_up in ("VALUES", "TABLE", "IN", "ANY", "SOME")
                        is_func_like = (prev_tok["type"] == "IDENTIFIER") or (val_up in ("COALESCE", "ROW_NUMBER", "NULLIF", "GREATEST", "LEAST")) or is_keyword_op
                        if is_func_like:
                            start_ws = prev_tok["end"]
                            end_ws = tok["start"]
                            expected_spaces = " " if is_keyword_op else ""
                            if content[start_ws:end_ws] != expected_spaces:
                                edits.append((start_ws, end_ws, expected_spaces))
        if edits:
            edits.sort(key=lambda x: x[0], reverse=True)
            chars = list(content)
            for start, end, val in edits:
                chars[start:end] = list(val)
            content = "".join(chars)
            
        expected_indents = self._get_line_expected_indents(content)
        if not expected_indents:
            return content
            
        lines = content.splitlines()
        for line_no in range(1, len(lines) + 1):
            if line_no in expected_indents:
                expected_indent = expected_indents[line_no]
                line_text = lines[line_no - 1]
                actual_indent = line_text[:len(line_text) - len(line_text.lstrip())]
                
                is_close_line = line_text.lstrip().startswith(")")
                if is_close_line:
                    mismatch = actual_indent != expected_indent
                else:
                    mismatch = not actual_indent.startswith(expected_indent)
                    
                if mismatch:
                    lines[line_no - 1] = expected_indent + line_text.lstrip()
                    # Re-evaluate expected indents since we modified the line prefix
                    # which might be an opening parenthesis line for nested parens
                    expected_indents = self._get_line_expected_indents("\n".join(lines))
                    
        ending = "\n" if content.endswith("\n") else ""
        return "\n".join(lines) + ending
