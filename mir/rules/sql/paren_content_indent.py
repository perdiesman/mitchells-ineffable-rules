from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren, get_token_depths, is_values_multi
from mir.rules.sql.table_function_indent import table_function_parens


def is_insert_column_opening(tokens: List[dict], open_index: int) -> bool:
    """Return whether ``(`` starts an INSERT target-column list."""
    index = open_index - 1
    saw_table_name = False
    while index >= 0:
        token = tokens[index]
        if token["type"] in ("WHITESPACE", "COMMENT"):
            index -= 1
            continue
        if token["type"] in ("IDENTIFIER", "DOT"):
            saw_table_name = saw_table_name or token["type"] == "IDENTIFIER"
            index -= 1
            continue
        return bool(
            saw_table_name
            and token["type"] == "KEYWORD"
            and token["value"].upper() == "INTO"
        )
    return False


def insert_column_lines(tokens: List[dict]) -> set[int]:
    """Return source lines whose indentation is owned by an INSERT list."""
    lines = set()
    for index, token in enumerate(tokens):
        if (
            token["type"] != "PAREN"
            or token["value"] != "("
            or not is_insert_column_opening(tokens, index)
        ):
            continue
        close_index = find_matching_paren(tokens, index)
        if close_index is None:
            continue
        lines.update(range(token["line"] + 1, tokens[close_index]["line"] + 1))
    return lines


def is_returns_table_opening(tokens: List[dict], open_index: int) -> bool:
    """Return whether ``(`` begins a RETURNS TABLE result declaration."""
    active = []
    for index in range(open_index - 1, -1, -1):
        if tokens[index]["type"] in ("WHITESPACE", "COMMENT"):
            continue
        active.append(tokens[index])
        if len(active) == 2:
            break
    return bool(
        len(active) == 2
        and active[0]["type"] == "KEYWORD"
        and active[0]["value"].upper() == "TABLE"
        and active[1]["value"].upper() == "RETURNS"
    )


def is_create_table_opening(tokens: List[dict], open_index: int) -> bool:
    """Return whether ``(`` begins a CREATE TABLE field declaration."""
    active = []
    for index in range(open_index - 1, -1, -1):
        token = tokens[index]
        if token["type"] in ("WHITESPACE", "COMMENT"):
            continue
        if token["type"] in ("COMMA", "PAREN", "SEMI"):
            break
        active.append(token)
        if len(active) >= 12:
            break
    chronological = list(reversed(active))
    words = [token["value"].upper() for token in chronological]
    if "TABLE" not in words:
        return False
    table_index = words.index("TABLE")
    return bool(
        "CREATE" in words[:table_index]
        and all(
            word in {"CREATE", "GLOBAL", "LOCAL", "TEMP", "TEMPORARY", "UNLOGGED"}
            for word in words[:table_index]
        )
        and all(
            token["value"].upper() in {"IF", "NOT", "EXISTS"}
            or token["type"] in {"IDENTIFIER", "DOT"}
            for token in chronological[table_index + 1:]
        )
    )


def is_cte_column_opening(tokens: List[dict], open_index: int) -> bool:
    """Return whether ``(`` begins a named CTE's output-column list."""
    previous = next(
        (
            tokens[index]
            for index in range(open_index - 1, -1, -1)
            if tokens[index]["type"] not in ("WHITESPACE", "COMMENT")
        ),
        None,
    )
    if previous is None or previous["type"] != "IDENTIFIER":
        return False
    close_index = find_matching_paren(tokens, open_index)
    if close_index is None:
        return False
    following = []
    for token_index in range(close_index + 1, len(tokens)):
        token = tokens[token_index]
        if token["type"] in ("WHITESPACE", "COMMENT"):
            continue
        following.append(token)
        if len(following) >= 4:
            break
    if not following or following[0]["value"].upper() != "AS":
        return False
    index = 1
    if index < len(following) and following[index]["value"].upper() == "NOT":
        index += 1
    if index < len(following) and following[index]["value"].upper() == "MATERIALIZED":
        index += 1
    return bool(
        index < len(following)
        and following[index]["type"] == "PAREN"
        and following[index]["value"] == "("
    )


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
            "correct": "SELECT COALESCE(\n    a,\n    b\n) FROM users;"
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
        'INSERT INTO t(c) VALUES\n    (1),\n    (2);',
        'IMPORT FOREIGN SCHEMA sample_remote LIMIT TO (sample_table) '
        'FROM SERVER sample_server INTO sample_local;'
    ]

    def _get_line_expected_indents(self, content: str) -> Dict[int, str]:
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        n = len(tokens)
        
        # Find all multiline parentheses that are NOT subqueries
        multiline_parens = []
        subquery_close_lines = set()
        table_function_openings = table_function_parens(tokens)
        for i, tok in enumerate(tokens):
            if tok["type"] == "PAREN" and tok["value"] == "(":
                if i in table_function_openings:
                    continue
                next_active = None
                for idx in range(i + 1, n):
                    if tokens[idx]["type"] == "WHITESPACE":
                        continue
                    if tokens[idx]["type"] != "COMMENT":
                        next_active = tokens[idx]
                        break
                if next_active and next_active["type"] == "KEYWORD" and next_active["value"].upper() == "SELECT":
                    close_idx = find_matching_paren(tokens, i)
                    if close_idx is not None:
                        close_line = tokens[close_idx]["line"]
                        if lines[close_line - 1].lstrip().startswith(")"):
                            subquery_close_lines.add(close_line)
                    continue
                    
                close_idx = find_matching_paren(tokens, i)
                if close_idx is not None:
                    close_tok = tokens[close_idx]
                    if tok["line"] < close_tok["line"]:
                        multiline_parens.append((i, close_idx, tok, close_tok))
                        
        # Map each line to its innermost owning parenthesis. Iterating every
        # parenthesis for every line was quadratic on bulk INSERT archives;
        # walking only the lines spanned by each parenthesis preserves the
        # same innermost-open precedence while scaling with actual nesting.
        owners = {}
        for open_idx, close_idx, open_tok, close_tok in multiline_parens:
            for line_no in range(open_tok["line"] + 1, close_tok["line"]):
                current = owners.get(line_no)
                if current is None or open_idx > current[0]:
                    owners[line_no] = (
                        open_idx, "content", open_tok, close_tok
                    )
            close_line = close_tok["line"]
            if (
                lines[close_line - 1].lstrip().startswith(")")
                and (
                    close_line not in owners
                    or open_idx > owners[close_line][0]
                )
            ):
                owners[close_line] = (
                    open_idx, "close", open_tok, close_tok
                )

        expected_indents = {}
        for line_no, inner in owners.items():
            line = lines[line_no - 1]
            if line.strip() == "" or line_no in subquery_close_lines:
                # Subquery indentation owns a leading closing parenthesis,
                # even when that line is also content of an enclosing
                # arithmetic/grouping parenthesis.
                continue
            open_tok = inner[2]
            
            # Get opening indent of open_tok's line
            open_line_text = lines[open_tok["line"] - 1]
            open_indent = open_line_text[:len(open_line_text) - len(open_line_text.lstrip())]
            
            if inner[1] == "content":
                expected_indents[line_no] = open_indent + "    "
            else:
                expected_indents[line_no] = open_indent
                
        return expected_indents

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        
        # Check opening parenthesis position
        tokens = tokenize_sql(content)
        exact_indent_lines = insert_column_lines(tokens)
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
                        is_keyword_op = val_up in ("VALUES", "TABLE", "IN") and not is_returns_table_opening(tokens, i)
                        is_create_table = is_create_table_opening(tokens, i)
                        is_cte_columns = is_cte_column_opening(tokens, i)
                        is_func_like = not (is_create_table or is_cte_columns) and ((prev_tok["type"] == "IDENTIFIER") or (val_up in ("COALESCE", "ROW_NUMBER", "NULLIF", "GREATEST", "LEAST")) or is_keyword_op)
                        if is_func_like or is_create_table or is_cte_columns:
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
                                expected_spaces = " " if is_keyword_op or is_create_table or is_cte_columns else ""
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
            if is_close_line or line_no in exact_indent_lines:
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
                        is_keyword_op = val_up in ("VALUES", "TABLE", "IN") and not is_returns_table_opening(tokens, i)
                        is_create_table = is_create_table_opening(tokens, i)
                        is_cte_columns = is_cte_column_opening(tokens, i)
                        is_func_like = not (is_create_table or is_cte_columns) and ((prev_tok["type"] == "IDENTIFIER") or (val_up in ("COALESCE", "ROW_NUMBER", "NULLIF", "GREATEST", "LEAST")) or is_keyword_op)
                        if is_func_like or is_create_table or is_cte_columns:
                            start_ws = prev_tok["end"]
                            end_ws = tok["start"]
                            expected_spaces = " " if is_keyword_op or is_create_table or is_cte_columns else ""
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
        exact_indent_lines = insert_column_lines(tokenize_sql(content))
        for line_no in range(1, len(lines) + 1):
            if line_no in expected_indents:
                expected_indent = expected_indents[line_no]
                line_text = lines[line_no - 1]
                actual_indent = line_text[:len(line_text) - len(line_text.lstrip())]
                
                is_close_line = line_text.lstrip().startswith(")")
                if is_close_line or line_no in exact_indent_lines:
                    mismatch = actual_indent != expected_indent
                else:
                    mismatch = not actual_indent.startswith(expected_indent)
                    
                if mismatch:
                    lines[line_no - 1] = expected_indent + line_text.lstrip()
                    # Nested opening lines settle on the runner's next bounded
                    # convergence pass. Re-tokenizing the full document after
                    # every changed line makes large migrations quadratic.
                    
        ending = "\n" if content.endswith("\n") else ""
        return "\n".join(lines) + ending
