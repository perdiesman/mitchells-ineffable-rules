import re
from bisect import bisect_left
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.line_length import LineLengthRule
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.sql_utils import tokenize_sql


def _normalize_inline_expression(expression: str) -> str:
    """Collapse SQL whitespace without touching literal or quoted contents."""
    tokens = tokenize_sql(expression.strip())
    if any(token["type"] == "COMMENT" for token in tokens):
        return expression.strip()
    return "".join(
        " " if token["type"] == "WHITESPACE" else token["value"]
        for token in tokens
    ).strip()

class ColumnLayoutRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-column-layout"
    description = "On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length limit used to determine if columns fit on a single line.",
            "fallback": "IR-line-length:max_length"
        },
        "indent_size": {
            "default": 4,
            "description": "Number of spaces used for single-level column wrapping indentation.",
            "fallback": "IR-indent:indent_size"
        },
        "base_indent": {
            "default": 0,
            "description": "Base indentation level (in spaces or leading space string) of the outer container.",
            "fallback": "IR-indent:base_indent"
        }
    }
    
    examples = [
        {
            "violating": "SELECT\n    id,\n    name\nFROM users;",
            "correct": "SELECT id, name\nFROM users;"
        },
        {
            "violating": "SELECT first_name, last_name, email, phone_number, mailing_address, date_of_birth, join_date, another_long_column_name, yet_another_one_to_be_sure FROM users;",
            "correct": "SELECT\n    first_name,\n    last_name,\n    email,\n    phone_number,\n    mailing_address,\n    date_of_birth,\n    join_date,\n    another_long_column_name,\n    yet_another_one_to_be_sure FROM users;"
        }
    ]
    additional_validations = [
        "SELECT id, name FROM users;",
        "SELECT DISTINCT ON (item_id, created_at) item_id, created_at FROM sample_item;"
    ]

    @staticmethod
    def _split_top_level_csv(text: str) -> List[str]:
        expressions = []
        start = 0
        depth = 0
        quote = None
        index = 0
        while index < len(text):
            char = text[index]
            if quote:
                if char == quote:
                    if index + 1 < len(text) and text[index + 1] == quote:
                        index += 2
                        continue
                    quote = None
                index += 1
                continue
            if char in ("'", '"'):
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                expression = _normalize_inline_expression(text[start:index])
                if expression:
                    expressions.append(expression)
                start = index + 1
            index += 1
        expression = _normalize_inline_expression(text[start:])
        if expression:
            expressions.append(expression)
        return expressions

    def _format_prefix(
        self,
        clause: dict,
        max_length: int,
        indent_size: int,
        base_indent_spaces: int,
    ) -> str:
        keyword = clause["keyword"]
        distinct_on = clause.get("distinct_on_expressions", [])
        if not distinct_on:
            return keyword

        indentation = clause["indentation"]
        inline = f"SELECT DISTINCT ON ({', '.join(distinct_on)})"
        effective_indent_len = max(0, len(indentation) - base_indent_spaces)
        if effective_indent_len + len(inline) <= max_length:
            return inline

        inner_indent = indentation + (" " * indent_size)
        return (
            "SELECT DISTINCT ON (\n"
            + ",\n".join(f"{inner_indent}{expression}" for expression in distinct_on)
            + f"\n{indentation})"
        )

    def _parse_clauses(self, content: str) -> List[dict]:
        """
        Parses all SELECT, ORDER BY, GROUP BY clauses.
        Returns a list of dicts.
        """
        n = len(content)
        i = 0
        in_string = False
        string_char = None
        in_single_comment = False
        in_multi_comment = False
        line_number = 1
        line_start_idx = 0
        
        clauses = []
        
        while i < n:
            c = content[i]
            
            if c == '\n':
                line_number += 1
                line_start_idx = i + 1
                
            # String / comment states
            if in_string:
                if c == '\n':
                    line_number += 1
                    line_start_idx = i + 1
                elif c == string_char:
                    if i + 1 < n and content[i + 1] == string_char:
                        i += 2
                        continue
                    in_string = False
                i += 1
                continue
                
            if in_single_comment:
                if c == '\n':
                    line_number += 1
                    line_start_idx = i + 1
                    in_single_comment = False
                i += 1
                continue
                
            if in_multi_comment:
                if c == '\n':
                    line_number += 1
                    line_start_idx = i + 1
                elif c == '*' and i + 1 < n and content[i + 1] == '/':
                    in_multi_comment = False
                    i += 2
                    continue
                i += 1
                continue
                
            if c in ("'", '"'):
                in_string = True
                string_char = c
                i += 1
                continue
                
            if c == '$':
                match = re.match(r'^\$[a-zA-Z0-9_]*\$', content[i:])
                if match:
                    tag = match.group(0)
                    tag_end = content.find(tag, i + len(tag))
                    if tag_end != -1:
                        skip_len = tag_end + len(tag) - i
                        skipped_text = content[i : i + skip_len]
                        line_number += skipped_text.count('\n')
                        i += skip_len
                        continue
                        
            if c == '-' and i + 1 < n and content[i + 1] == '-':
                in_single_comment = True
                i += 2
                continue
                
            if c == '/' and i + 1 < n and content[i + 1] == '*':
                in_multi_comment = True
                i += 2
                continue
                
                
            # Match keywords
            if (c.isalpha() or c == '_'):
                w_start = i
                w_line = line_number
                while i < n and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[w_start:i]
                
                keyword = None
                keyword_end = i
                word_lower = word.lower()
                
                if word_lower == "select":
                    keyword = "SELECT"
                elif word_lower in ("group", "order"):
                    next_idx = i
                    while next_idx < n and content[next_idx].isspace():
                        next_idx += 1
                    w2_start = next_idx
                    while next_idx < n and (content[next_idx].isalnum() or content[next_idx] == '_'):
                        next_idx += 1
                    word2 = content[w2_start:next_idx]
                    if word2.lower() == "by":
                        keyword = "GROUP BY" if word_lower == "group" else "ORDER BY"
                        keyword_end = next_idx
                        i = next_idx
                        
                if keyword:
                    # Resolve indentation of keyword line (the leading whitespace of the line)
                    line_text = content[line_start_idx:w_start]
                    indentation = ""
                    for char in line_text:
                        if char in (" ", "\t"):
                            indentation += char
                        else:
                            break
                            
                    # Parse the list of expressions starting immediately after the keyword
                    list_start = keyword_end
                    distinct_on_expressions = []
                    
                    # Check for DISTINCT or ALL modifier right after SELECT
                    if keyword == "SELECT":
                        next_idx = list_start
                        while next_idx < n and content[next_idx].isspace():
                            next_idx += 1
                        w_mod_start = next_idx
                        while next_idx < n and (content[next_idx].isalnum() or content[next_idx] == '_'):
                            next_idx += 1
                        word_mod = content[w_mod_start:next_idx].lower()
                        if word_mod in ("distinct", "all"):
                            keyword = f"SELECT {word_mod.upper()}"
                            list_start = next_idx
                            
                            # Check if it is DISTINCT ON
                            if word_mod == "distinct":
                                next_on_idx = list_start
                                while next_on_idx < n and content[next_on_idx].isspace():
                                    next_on_idx += 1
                                w_on_start = next_on_idx
                                while next_on_idx < n and (content[next_on_idx].isalnum() or content[next_on_idx] == '_'):
                                    next_on_idx += 1
                                word_on = content[w_on_start:next_on_idx].lower()
                                if word_on == "on":
                                    keyword = "SELECT DISTINCT ON"
                                    open_idx = next_on_idx
                                    while open_idx < n and content[open_idx].isspace():
                                        open_idx += 1
                                    if open_idx < n and content[open_idx] == "(":
                                        depth = 0
                                        quote = None
                                        close_idx = open_idx
                                        while close_idx < n:
                                            char = content[close_idx]
                                            if quote:
                                                if char == quote:
                                                    if close_idx + 1 < n and content[close_idx + 1] == quote:
                                                        close_idx += 2
                                                        continue
                                                    quote = None
                                            elif char in ("'", '"'):
                                                quote = char
                                            elif char == "(":
                                                depth += 1
                                            elif char == ")":
                                                depth -= 1
                                                if depth == 0:
                                                    break
                                            close_idx += 1
                                        if close_idx < n:
                                            distinct_on_expressions = self._split_top_level_csv(
                                                content[open_idx + 1 : close_idx]
                                            )
                                            list_start = close_idx + 1
                                        else:
                                            list_start = next_on_idx
                                    else:
                                        list_start = next_on_idx
                                    
                    expressions = []
                    expression_indents = []
                    expression_ranges = []
                    
                    list_paren = 0
                    list_string = False
                    list_str_char = None
                    list_single_comment = False
                    list_multi_comment = False
                    
                    j = list_start
                    current_expr_start = list_start
                    last_non_space_idx = list_start
                    
                    while j < n:
                        jc = content[j]
                        
                        if list_string:
                            if jc == list_str_char:
                                if j + 1 < n and content[j + 1] == list_str_char:
                                    j += 2
                                    last_non_space_idx = j
                                    continue
                                list_string = False
                            if not jc.isspace():
                                last_non_space_idx = j + 1
                            j += 1
                            continue
                        if list_single_comment:
                            if jc == '\n':
                                list_single_comment = False
                            j += 1
                            continue
                        if list_multi_comment:
                            if jc == '*' and j + 1 < n and content[j + 1] == '/':
                                list_multi_comment = False
                                j += 2
                                last_non_space_idx = j
                                continue
                            j += 1
                            continue
                            
                        if jc in ("'", '"'):
                            list_string = True
                            list_str_char = jc
                            last_non_space_idx = j + 1
                            j += 1
                            continue
                        if jc == '-' and j + 1 < n and content[j + 1] == '-':
                            list_single_comment = True
                            j += 2
                            continue
                        if jc == '/' and j + 1 < n and content[j + 1] == '*':
                            list_multi_comment = True
                            j += 2
                            continue
                            
                        if jc == '(':
                            list_paren += 1
                            last_non_space_idx = j + 1
                            j += 1
                            continue
                        if jc == ')':
                            if list_paren == 0:
                                break
                            list_paren -= 1
                            last_non_space_idx = j + 1
                            j += 1
                            continue
                            
                        if list_paren == 0 and (jc.isalpha() or jc == '_'):
                            jw_start = j
                            while j < n and (content[j].isalnum() or content[j] == '_'):
                                j += 1
                            j_word = content[jw_start:j].lower()
                            
                            if keyword.startswith("SELECT"):
                                boundaries = {"from", "where", "group", "order", "limit", "offset", "union", "intersect", "except"}
                            elif keyword.startswith("GROUP"):
                                boundaries = {"having", "order", "limit", "offset", "union", "intersect", "except"}
                            else:
                                boundaries = {"limit", "offset", "union", "intersect", "except"}
                                
                            if j_word in boundaries:
                                j = jw_start
                                break
                            
                            last_non_space_idx = j
                            continue
                            
                        if list_paren == 0 and jc == ';':
                            break
                            
                        if list_paren == 0 and jc == ',':
                            expr = content[current_expr_start:j].strip()
                            if "\n" not in expr:
                                expr = _normalize_inline_expression(expr)
                            if expr:
                                expressions.append(expr)
                                # Find original base indentation of this expression
                                actual_start = current_expr_start
                                while actual_start < j and content[actual_start].isspace():
                                    actual_start += 1
                                line_start = content.rfind("\n", 0, actual_start) + 1
                                line_prefix = content[line_start:actual_start]
                                expr_base_indent = ""
                                for char in line_prefix:
                                    if char in (" ", "\t"):
                                        expr_base_indent += char
                                    else:
                                        break
                                expression_indents.append(expr_base_indent)
                                expression_ranges.append((actual_start, j))
                            last_non_space_idx = j + 1
                            j += 1
                            current_expr_start = j
                            continue
                            
                        if not jc.isspace():
                            last_non_space_idx = j + 1
                        j += 1
                        
                    list_end = last_non_space_idx
                    expr = content[current_expr_start:list_end].strip()
                    if "\n" not in expr:
                        expr = _normalize_inline_expression(expr)
                    if expr:
                        # DISTINCT/ALL has been parsed at the start of SELECT
                        if expr:
                            expressions.append(expr)
                            # Find original base indentation of this expression
                            actual_start = current_expr_start
                            while actual_start < list_end and content[actual_start].isspace():
                                actual_start += 1
                            line_start = content.rfind("\n", 0, actual_start) + 1
                            line_prefix = content[line_start:actual_start]
                            expr_base_indent = ""
                            for char in line_prefix:
                                if char in (" ", "\t"):
                                    expr_base_indent += char
                                else:
                                    break
                            expression_indents.append(expr_base_indent)
                            expression_ranges.append((actual_start, list_end))
                    
                    # Prevent formatting if there is an inline comment inside the clause text
                    clause_text = content[w_start:list_end]
                    
                    # Update line_number and line_start_idx for all newlines skipped during list scanning
                    for idx in range(w_start, list_end):
                        if content[idx] == '\n':
                            line_number += 1
                            line_start_idx = idx + 1
                            
                    if "--" in clause_text or "/*" in clause_text:
                        i = list_end
                        continue
                        
                    clauses.append({
                        "keyword": keyword,
                        "keyword_start": w_start,
                        "keyword_end": keyword_end,
                        "list_start": list_start,
                        "list_end": list_end,
                        "expressions": expressions,
                        "expression_indents": expression_indents,
                        "expression_ranges": expression_ranges,
                        "line_number": w_line,
                        "indentation": indentation,
                        "distinct_on_expressions": distinct_on_expressions,
                    })
                    i = list_end
                    continue
                    
            if (c.isalpha() or c == '_'):
                continue
                
            i += 1
            
        # Mark nested clauses using coordinate containment
        for cl1 in clauses:
            for cl2 in clauses:
                if cl1 is not cl2:
                    if cl2["list_start"] <= cl1["keyword_start"] < cl2["list_end"]:
                        cl1["is_nested"] = True
                        break
        return clauses

    def _reindent_multiline(self, text: str, new_indent: str, orig_base_indent: str) -> str:
        lines = text.splitlines()
        if not lines:
            return text
            
        indent_size = 4
        if isinstance(orig_base_indent, str):
            orig_base_len = len(orig_base_indent.replace("\t", " " * indent_size))
        elif isinstance(orig_base_indent, int):
            orig_base_len = orig_base_indent
        else:
            orig_base_len = 0
            
        rebuilt = [new_indent + lines[0].lstrip()]
        for l in lines[1:]:
            stripped = l.lstrip()
            if stripped == "":
                rebuilt.append("")
            else:
                l_indent = len(l) - len(stripped)
                relative_indent = max(0, l_indent - orig_base_len)
                rebuilt.append(new_indent + " " * relative_indent + stripped)
        return "\n".join(rebuilt)

    @staticmethod
    def _crosses_dynamic_content(clause: dict, dynamic_offsets: List[int]) -> bool:
        if not dynamic_offsets:
            return False
        index = bisect_left(dynamic_offsets, clause["keyword_start"])
        return index < len(dynamic_offsets) and dynamic_offsets[index] < clause["list_end"]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_length = self.get_config_value(
            rule_config,
            "max_length",
            default_value=120,
            fallbacks=[(LineLengthRule, "max_length")]
        )
        indent_size = self.get_config_value(
            rule_config,
            "indent_size",
            default_value=4,
            fallbacks=[(IndentRule, "indent_size")]
        )
        base_indent_opt = self.get_config_value(
            rule_config,
            "base_indent",
            default_value=0,
            fallbacks=[(IndentRule, "base_indent")]
        )
        if isinstance(base_indent_opt, str):
            base_indent_spaces = len(base_indent_opt.replace("\t", " " * indent_size))
        elif isinstance(base_indent_opt, int):
            base_indent_spaces = base_indent_opt
        else:
            base_indent_spaces = 0
        if "original_xml" in rule_config:
            base_indent_spaces = 0
            
        violations = []
        
        clauses = self._parse_clauses(content)
        lines = content.splitlines()
        
        dynamic_offsets = sorted(rule_config.get("mybatis_dynamic_offsets", set()))
        top_level_clauses = [
            cl
            for cl in clauses
            if not cl.get("is_nested", False)
            and not self._crosses_dynamic_content(cl, dynamic_offsets)
        ]
        for cl in top_level_clauses:
            keyword = cl["keyword"]
            expressions = cl["expressions"]
            indentation = cl["indentation"]
            
            if not expressions:
                continue
                
            # 1. Determine if it fits on a single line
            prefix = self._format_prefix(
                cl, max_length, indent_size, base_indent_spaces
            )
            single_line_clause = f"{prefix} {', '.join(expressions)}"
            effective_indent_len = max(0, len(indentation) - base_indent_spaces)
            total_len = effective_indent_len + len(single_line_clause)
            
            current_clause_text = content[cl["keyword_start"]:cl["list_end"]]

            if rule_config.get("mybatis_dynamic_offsets"):
                if "\n" not in current_clause_text:
                    continue
                inner_indent = indentation + (" " * indent_size)
                formatted_exprs = [
                    self._reindent_multiline(expr, inner_indent, orig_indent)
                    if "\n" in expr
                    else f"{inner_indent}{expr}"
                    for expr, orig_indent in zip(
                        expressions,
                        cl.get("expression_indents", [""] * len(expressions)),
                    )
                ]
                expected = f"{prefix}\n" + ",\n".join(formatted_exprs)
                if current_clause_text.replace("\r\n", "\n") != expected.replace("\r\n", "\n"):
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            line_number=cl["line_number"],
                            message=f"Align the multiline {keyword} clause one indentation level below its keyword.",
                            offending_lines=[lines[cl["line_number"] - 1] if cl["line_number"] - 1 < len(lines) else ""],
                            is_fixable=True,
                        )
                    )
                continue
            
            if total_len <= max_length:
                # Expect single-line format
                expected = single_line_clause
                if current_clause_text != expected:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            line_number=cl["line_number"],
                            message=f"Columns fit on a single line. Expected single-line layout for {keyword} clause.",
                            offending_lines=[lines[cl["line_number"] - 1] if cl["line_number"] - 1 < len(lines) else ""],
                            is_fixable=True
                        )
                    )
            else:
                # Expect multi-line format
                inner_indent = indentation + (" " * indent_size)
                
                formatted_exprs = []
                for expr, orig_indent in zip(expressions, cl.get("expression_indents", [""] * len(expressions))):
                    if "\n" in expr:
                        formatted_exprs.append(self._reindent_multiline(expr, inner_indent, orig_indent))
                    else:
                        formatted_exprs.append(f"{inner_indent}{expr}")
                        
                expected = f"{prefix}\n" + ",\n".join(formatted_exprs)
                
                # Normalize line endings for comparison
                current_normalized = current_clause_text.replace("\r\n", "\n")
                expected_normalized = expected.replace("\r\n", "\n")
                
                if current_normalized != expected_normalized:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            line_number=cl["line_number"],
                            message=f"Columns exceed max line length. Expected multi-line (one per line) layout for {keyword} clause.",
                            offending_lines=[lines[cl["line_number"] - 1] if cl["line_number"] - 1 < len(lines) else ""],
                            is_fixable=True
                        )
                    )
                    
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_length = self.get_config_value(
            rule_config,
            "max_length",
            default_value=120,
            fallbacks=[(LineLengthRule, "max_length")]
        )
        indent_size = self.get_config_value(
            rule_config,
            "indent_size",
            default_value=4,
            fallbacks=[(IndentRule, "indent_size")]
        )
        base_indent_opt = self.get_config_value(
            rule_config,
            "base_indent",
            default_value=0,
            fallbacks=[(IndentRule, "base_indent")]
        )
        if isinstance(base_indent_opt, str):
            base_indent_spaces = len(base_indent_opt.replace("\t", " " * indent_size))
        elif isinstance(base_indent_opt, int):
            base_indent_spaces = base_indent_opt
        else:
            base_indent_spaces = 0
        if "original_xml" in rule_config:
            base_indent_spaces = 0
            
        clauses = self._parse_clauses(content)
        dynamic_offsets = sorted(rule_config.get("mybatis_dynamic_offsets", set()))
        top_level_clauses = [
            cl
            for cl in clauses
            if not cl.get("is_nested", False)
            and not self._crosses_dynamic_content(cl, dynamic_offsets)
        ]
        if not top_level_clauses:
            return content
            
        fixed_chunks = []
        last_idx = 0
        
        ending = "\r\n" if "\r\n" in content else "\n"
        
        for cl in top_level_clauses:
            keyword = cl["keyword"]
            expressions = cl["expressions"]
            indentation = cl["indentation"]
            
            if not expressions:
                continue

            current_clause_text = content[cl["keyword_start"]:cl["list_end"]]
            embedded_reindent_only = bool(
                rule_config.get("mybatis_dynamic_offsets")
            )
            if embedded_reindent_only and "\n" not in current_clause_text:
                fixed_chunks.append(content[last_idx:cl["list_end"]])
                last_idx = cl["list_end"]
                continue
                
            # Recursively format nested expressions (subqueries) first
            recursively_formatted_expressions = []
            recursively_formatted_indices = set()
            for idx, (expr, orig_indent) in enumerate(zip(expressions, cl.get("expression_indents", [""] * len(expressions)))):
                if not embedded_reindent_only and any(k in expr.lower() for k in ("select", "group by", "order by")):
                    normalized_expr = self._reindent_multiline(expr, "", orig_indent)
                    recursively_formatted_expressions.append(self.fix(normalized_expr, file_path, rule_config))
                    recursively_formatted_indices.add(idx)
                else:
                    recursively_formatted_expressions.append(expr)
            expressions = recursively_formatted_expressions
            
            prefix = self._format_prefix(
                cl, max_length, indent_size, base_indent_spaces
            )
            single_line_clause = f"{prefix} {', '.join(expressions)}"
            effective_indent_len = max(0, len(indentation) - base_indent_spaces)
            total_len = effective_indent_len + len(single_line_clause)
            
            if (
                not embedded_reindent_only
                and total_len <= max_length
                and not any("\n" in expr for expr in expressions)
            ):
                formatted = single_line_clause
            else:
                inner_indent = indentation + (" " * indent_size)
                formatted_exprs = []
                for idx, (expr, orig_indent) in enumerate(zip(expressions, cl.get("expression_indents", [""] * len(expressions)))):
                    if "\n" in expr:
                        effective_orig_indent = "" if idx in recursively_formatted_indices else orig_indent
                        formatted_exprs.append(self._reindent_multiline(expr, inner_indent, effective_orig_indent))
                    else:
                        formatted_exprs.append(f"{inner_indent}{expr}")
                formatted = f"{prefix}{ending}" + f",{ending}".join(formatted_exprs)
                
            fixed_chunks.append(content[last_idx:cl["keyword_start"]])
            fixed_chunks.append(formatted)
            last_idx = cl["list_end"]
            
        fixed_chunks.append(content[last_idx:])
        return "".join(fixed_chunks)
