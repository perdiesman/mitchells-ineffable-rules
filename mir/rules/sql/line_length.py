from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.indent import IndentRule

def wrap_comment_line(line: str, max_length: int) -> List[str]:
    # Find leading indentation
    indent = line[:len(line) - len(line.lstrip())]
    stripped = line.lstrip()
    
    if not stripped.startswith("--"):
        return [line]
        
    if stripped.startswith("-- "):
        comment_prefix = "-- "
        comment_text = stripped[3:]
    else:
        comment_prefix = "--"
        comment_text = stripped[2:]
        
    prefix = indent + comment_prefix
    
    if len(line) <= max_length:
        return [line]
        
    max_text_len = max(1, max_length - len(prefix))
    
    words = comment_text.split(" ")
    wrapped_lines = []
    current_line_words = []
    current_line_len = 0
    
    for word in words:
        word_len = len(word)
        space_len = 1 if current_line_words else 0
        if current_line_len + space_len + word_len > max_text_len:
            if current_line_words:
                wrapped_lines.append(prefix + " ".join(current_line_words))
                current_line_words = [word]
                current_line_len = word_len
            else:
                wrapped_lines.append(prefix + word)
                current_line_words = []
                current_line_len = 0
        else:
            current_line_words.append(word)
            current_line_len += space_len + word_len
            
    if current_line_words:
        wrapped_lines.append(prefix + " ".join(current_line_words))
        
    return wrapped_lines

class LineLengthRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-line-length"
    description = (
        "Lines must not exceed the configured maximum length. Overlong "
        "keyword-owned IN, VALUES, and TABLE lists wrap one item per line."
    )
    category = "general"
    is_fixable = "sometimes"
    exclude_recursive = True
    
    default_config = {
        "max_length": 120,
        "base_indent": 0
    }
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length limit."
        },
        "base_indent": {
            "default": 0,
            "description": "Base indentation offset (in spaces or leading space string) to subtract before checking line lengths.",
            "fallback": "IR-indent:base_indent"
        }
    }
    
    examples = [
        {
            "violating": "-- This is a very long comment line that exceeds the maximum line length limit of 120 characters to demonstrate how the comment wrapping works.",
            "correct": "-- This is a very long comment line that exceeds the maximum line length limit of 120 characters to demonstrate how the\n-- comment wrapping works."
        }
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        base_indent_opt = self.get_config_value(
            rule_config,
            "base_indent",
            default_value=0,
            fallbacks=[(IndentRule, "base_indent")]
        )
        # Handle string or integer base_indent
        if isinstance(base_indent_opt, str):
            # To get indent_size for normalizing tabs, look up IndentRule.indent_size default
            indent_size = 4
            all_configs = rule_config.get("_all_configs", {})
            lang = rule_config.get("_lang")
            indent_config = all_configs.get(f"{lang}:IR-indent", all_configs.get("IR-indent", {}))
            if isinstance(indent_config, dict):
                indent_size = indent_config.get("indent_size", 4)
            base_indent_spaces = len(base_indent_opt.replace("\t", " " * indent_size))
        elif isinstance(base_indent_opt, int):
            base_indent_spaces = base_indent_opt
        else:
            base_indent_spaces = 0
        if "original_xml" in rule_config:
            # MyBatis review uses the physical XML line width. The mapper's
            # statement indent is real horizontal space, not a display-only
            # wrapper that should be discounted.
            base_indent_spaces = 0
            
        violations = []
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            effective_len = len(line) - base_indent_spaces
            if effective_len > max_length:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=idx,
                        message=f"Line exceeds maximum length of {max_length} characters (actual effective length: {effective_len}, total length: {len(line)}).",
                        offending_lines=[line],
                        is_fixable=True
                    )
                )
                
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_length = rule_config.get("max_length", self.default_config["max_length"])

        # Collapse a simple one-argument call when its surrounding expression
        # fits after compaction. This also repairs calls expanded during an
        # earlier pass before their enclosing SELECT layout had stabilized.
        from mir.rules.sql.sql_utils import find_matching_paren, tokenize_sql
        from mir.rules.sql.table_function_indent import table_function_parens
        compact_tokens = tokenize_sql(content)
        table_function_openings = table_function_parens(compact_tokens)
        compact_edits = []
        for index, token in enumerate(compact_tokens):
            if token["type"] not in ("IDENTIFIER", "KEYWORD"):
                continue
            if (
                token["type"] == "KEYWORD"
                and token["value"].upper()
                not in {
                    "ANY", "CAST", "COALESCE", "EXTRACT", "FILTER",
                    "GREATEST", "LEAST", "LEFT", "NULLIF", "RIGHT",
                    "ROW_NUMBER", "SOME",
                }
            ):
                continue
            open_index = next(
                (
                    candidate
                    for candidate in range(index + 1, len(compact_tokens))
                    if compact_tokens[candidate]["type"]
                    not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            if (
                open_index is None
                or open_index in table_function_openings
                or compact_tokens[open_index]["type"] != "PAREN"
                or compact_tokens[open_index]["value"] != "("
            ):
                continue
            close_index = find_matching_paren(compact_tokens, open_index)
            if close_index is None:
                continue
            open_token = compact_tokens[open_index]
            close_token = compact_tokens[close_index]
            call_text = content[open_token["start"]:close_token["end"]]
            if "\n" not in call_text:
                continue
            inner_tokens = compact_tokens[open_index + 1:close_index]
            active_inner = [
                item
                for item in inner_tokens
                if item["type"] not in ("WHITESPACE", "COMMENT")
            ]
            if (
                token["type"] == "KEYWORD"
                and token["value"].upper() == "IN"
                and active_inner
                and active_inner[0]["type"] == "KEYWORD"
                and active_inner[0]["value"].upper() == "SELECT"
            ):
                # IN (SELECT ...) is a predicate subquery, not a function
                # call. Preserve its deliberate multiline layout, especially
                # when a MyBatis tag supplies part of the inner predicate.
                continue
            if (
                not active_inner
                or any(item["type"] == "COMMENT" for item in inner_tokens)
                or any(item["type"] in ("COMMA", "PAREN") for item in active_inner)
            ):
                continue
            compact_call = "(" + "".join(
                " " if item["type"] == "WHITESPACE" else item["value"]
                for item in inner_tokens
            ).strip() + ")"
            line_start = content.rfind("\n", 0, token["start"]) + 1
            line_end = content.find("\n", close_token["end"])
            if line_end == -1:
                line_end = len(content)
            candidate_line = (
                content[line_start:open_token["start"]]
                + compact_call
                + content[close_token["end"]:line_end]
            )
            if "\n" not in candidate_line and len(candidate_line) <= max_length:
                compact_edits.append(
                    (open_token["start"], close_token["end"], compact_call)
                )
        if compact_edits:
            chars = list(content)
            for start, end, replacement in sorted(compact_edits, reverse=True):
                chars[start:end] = list(replacement)
            content = "".join(chars)

        # Prefer a semantic range boundary over splitting the function calls
        # used as BETWEEN bounds. Only take the break when both resulting
        # physical lines fit the configured limit.
        from mir.rules.sql.sql_utils import (
            find_between_delimiter_indices,
            get_token_depths,
        )
        range_tokens = tokenize_sql(content)
        range_depths = get_token_depths(range_tokens)
        range_edits = []
        content_lines = content.splitlines()
        delimiter_indices = sorted({
            index
            for depth in set(range_depths)
            for index in find_between_delimiter_indices(
                range_tokens, range_depths, depth
            )
        })
        for delimiter_index in delimiter_indices:
            delimiter = range_tokens[delimiter_index]
            line_index = delimiter["line"] - 1
            if line_index >= len(content_lines):
                continue
            line = content_lines[line_index]
            if len(line) <= max_length:
                continue
            whitespace = (
                range_tokens[delimiter_index - 1]
                if delimiter_index > 0
                and range_tokens[delimiter_index - 1]["type"] == "WHITESPACE"
                else None
            )
            if whitespace is None or "\n" in whitespace["value"]:
                continue
            line_start = content.rfind("\n", 0, delimiter["start"]) + 1
            line_end = content.find("\n", delimiter["start"])
            if line_end == -1:
                line_end = len(content)
            indent = line[: len(line) - len(line.lstrip())]
            first_line = content[line_start:whitespace["start"]].rstrip()
            second_line = indent + "    " + content[delimiter["start"]:line_end].lstrip()
            if len(first_line) <= max_length and len(second_line) <= max_length:
                range_edits.append(
                    (
                        whitespace["start"],
                        whitespace["end"],
                        "\n" + indent + "    ",
                    )
                )
        if range_edits:
            chars = list(content)
            for start, end, replacement in sorted(range_edits, reverse=True):
                chars[start:end] = list(replacement)
            content = "".join(chars)

        # Expand long comma-separated SQL lists whose parentheses have clear
        # keyword ownership. This covers IN predicates, VALUES rows, and
        # RETURNS TABLE declarations without guessing at arbitrary grouping
        # parentheses or changing any list item.
        list_tokens = tokenize_sql(content)
        list_edits = []
        for open_index, opening in enumerate(list_tokens):
            if opening["type"] != "PAREN" or opening["value"] != "(":
                continue
            close_index = find_matching_paren(list_tokens, open_index)
            if close_index is None or list_tokens[close_index]["line"] != opening["line"]:
                continue
            previous_index = next(
                (
                    index
                    for index in range(open_index - 1, -1, -1)
                    if list_tokens[index]["type"] not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            if previous_index is None:
                continue
            owner = list_tokens[previous_index]
            if (
                owner["type"] != "KEYWORD"
                or owner["value"].upper() not in {"IN", "TABLE", "VALUES"}
            ):
                continue
            active_inner = [
                item
                for item in list_tokens[open_index + 1:close_index]
                if item["type"] not in ("WHITESPACE", "COMMENT")
            ]
            if (
                not active_inner
                or active_inner[0]["type"] == "KEYWORD"
                and active_inner[0]["value"].upper() in {"SELECT", "WITH"}
                or any(
                    item["type"] == "COMMENT"
                    for item in list_tokens[open_index + 1:close_index]
                )
            ):
                continue
            depth = 0
            commas = []
            for index in range(open_index + 1, close_index):
                item = list_tokens[index]
                if item["type"] == "PAREN":
                    depth += 1 if item["value"] == "(" else -1
                elif item["type"] == "COMMA" and depth == 0:
                    commas.append(index)
            if not commas:
                continue
            line_start = content.rfind("\n", 0, opening["start"]) + 1
            line_end = content.find("\n", list_tokens[close_index]["end"])
            if line_end == -1:
                line_end = len(content)
            physical_line = content[line_start:line_end]
            if len(physical_line) <= max_length:
                continue
            indent = physical_line[: len(physical_line) - len(physical_line.lstrip())]
            item_indent = indent + "    "

            def replace_adjacent_whitespace(token_index, replacement, *, before):
                adjacent = token_index - 1 if before else token_index + 1
                if (
                    0 <= adjacent < len(list_tokens)
                    and list_tokens[adjacent]["type"] == "WHITESPACE"
                ):
                    whitespace = list_tokens[adjacent]
                    start, end = whitespace["start"], whitespace["end"]
                else:
                    token = list_tokens[token_index]
                    start = end = token["start"] if before else token["end"]
                if content[start:end] != replacement:
                    list_edits.append((start, end, replacement))

            replace_adjacent_whitespace(
                open_index, "\n" + item_indent, before=False
            )
            for comma_index in commas:
                replace_adjacent_whitespace(
                    comma_index, "\n" + item_indent, before=False
                )
            replace_adjacent_whitespace(
                close_index, "\n" + indent, before=True
            )
        if list_edits:
            chars = list(content)
            for start, end, replacement in sorted(
                set(list_edits), reverse=True
            ):
                chars[start:end] = list(replacement)
            content = "".join(chars)
        
        # 1. Run function call splitting on SQL code lines
        try:
            tokens = tokenize_sql(content)
            lines = content.splitlines()
            token_depths = get_token_depths(tokens)
            case_arm_lines = set()
            active_by_line = {}
            for token_index, token in enumerate(tokens):
                if token["type"] not in ("WHITESPACE", "COMMENT"):
                    active_by_line.setdefault(token["line"], []).append(token_index)
            for line_number, indices in active_by_line.items():
                when_depths = {
                    token_depths[index]
                    for index in indices
                    if tokens[index]["type"] == "KEYWORD"
                    and tokens[index]["value"].upper() == "WHEN"
                }
                if any(
                    tokens[index]["type"] == "KEYWORD"
                    and tokens[index]["value"].upper() == "THEN"
                    and token_depths[index] in when_depths
                    for index in indices
                ):
                    case_arm_lines.add(line_number)

            next_active_indices = [None] * len(tokens)
            next_active_index = None
            for token_index in range(len(tokens) - 1, -1, -1):
                next_active_indices[token_index] = next_active_index
                if tokens[token_index]["type"] not in ("WHITESPACE", "COMMENT"):
                    next_active_index = token_index
            paren_pairs = {}
            paren_stack = []
            for token_index, token in enumerate(tokens):
                if token["type"] != "PAREN":
                    continue
                if token["value"] == "(":
                    paren_stack.append(token_index)
                elif token["value"] == ")" and paren_stack:
                    paren_pairs[paren_stack.pop()] = token_index
            
            # Find all function calls
            all_calls = []
            for i, tok in enumerate(tokens):
                if tok["type"] in ("IDENTIFIER", "KEYWORD"):
                    if tok["line"] in case_arm_lines:
                        continue
                    if (
                        tok["type"] == "KEYWORD"
                        and tok["value"].upper()
                        not in {
                            "ANY", "CAST", "COALESCE", "EXTRACT", "FILTER",
                            "GREATEST", "LEAST", "LEFT", "NULLIF", "RIGHT",
                            "ROW_NUMBER", "SOME",
                        }
                    ):
                        continue
                    next_act_idx = next_active_indices[i]
                    if next_act_idx is not None and tokens[next_act_idx]["type"] == "PAREN" and tokens[next_act_idx]["value"] == "(":
                        open_idx = next_act_idx
                        close_idx = paren_pairs.get(open_idx)
                        if close_idx is not None:
                            all_calls.append({
                                "start": tokens[open_idx]["start"],
                                "end": tokens[close_idx]["end"],
                                "open_idx": open_idx,
                                "close_idx": close_idx,
                                "name_token": tok
                            })
                            
            # Prefer the outer call only when it begins on the same overlong
            # physical line. A short wrapper on an earlier line must not hide
            # a nested call whose own argument line needs expansion.
            outer_calls = []
            call_stack = []
            for call in all_calls:
                while call_stack and call["start"] >= call_stack[-1]["end"]:
                    call_stack.pop()
                is_nested = any(
                    len(lines[parent["name_token"]["line"] - 1]) > max_length
                    for parent in call_stack
                    if parent["name_token"]["line"] <= len(lines)
                )
                if not is_nested:
                    outer_calls.append(call)
                call_stack.append(call)

            last_call_start_by_line = {}
            for call in all_calls:
                line_number = call["name_token"]["line"]
                last_call_start_by_line[line_number] = max(
                    last_call_start_by_line.get(line_number, -1),
                    call["start"],
                )
                    
            # Generate edits for long lines
            edits = []
            indent_size = 4
            all_configs = rule_config.get("_all_configs", {})
            lang = rule_config.get("_lang")
            indent_config = all_configs.get(f"{lang}:IR-indent", all_configs.get("IR-indent", {}))
            if isinstance(indent_config, dict):
                indent_size = indent_config.get("indent_size", 4)
                
            for call in outer_calls:
                line_idx = call["name_token"]["line"] - 1
                line = lines[line_idx] if line_idx < len(lines) else ""
                if len(line) > max_length:
                    earlier_line_tokens = [
                        tokens[index]
                        for index in active_by_line.get(
                            call["name_token"]["line"], []
                        )
                        if tokens[index]["start"] < call["name_token"]["start"]
                    ]
                    earlier_keywords = {
                        item["value"].upper()
                        for item in earlier_line_tokens
                        if item["type"] == "KEYWORD"
                    }
                    if (
                        "JOIN" in earlier_keywords
                        and earlier_keywords.intersection({"AND", "OR"})
                    ):
                        # JOIN layout owns the earlier boolean boundary. Let
                        # it move the predicate to a continuation before
                        # expanding a function that will fit on that line.
                        continue
                    if last_call_start_by_line.get(
                        call["name_token"]["line"], -1
                    ) > call["end"]:
                        # Prefer the last call on a physical line. For
                        # count(*) FILTER (...), expanding count(*) only
                        # makes noise while the FILTER predicate remains the
                        # actual wrapping opportunity.
                        continue
                    # Parse arguments
                    args = []
                    current_arg = []
                    depth = 0
                    for k in range(call["open_idx"] + 1, call["close_idx"]):
                        t = tokens[k]
                        if t["type"] == "PAREN" and t["value"] == "(":
                            depth += 1
                            current_arg.append(t)
                        elif t["type"] == "PAREN" and t["value"] == ")":
                            depth -= 1
                            current_arg.append(t)
                        elif t["type"] == "COMMA" and depth == 0:
                            args.append(current_arg)
                            current_arg = []
                        else:
                            current_arg.append(t)
                    if current_arg or not args:
                        args.append(current_arg)
                        
                    arg_strings = []
                    for a_toks in args:
                        if a_toks:
                            s = a_toks[0]["start"]
                            e = a_toks[-1]["end"]
                            arg_strings.append(content[s:e].strip())
                    arg_strings = [s for s in arg_strings if s]
                    
                    if arg_strings:
                        indent = ""
                        for char in line:
                            if char in (" ", "\t"):
                                indent += char
                            else:
                                break
                        arg_indent = indent + " " * indent_size
                        
                        replacement = "(\n"
                        for idx, arg_str in enumerate(arg_strings):
                            comma = "," if idx < len(arg_strings) - 1 else ""
                            replacement += arg_indent + arg_str + comma + "\n"
                        replacement += indent + ")"
                        
                        edits.append((call["start"], call["end"], replacement))
                        
            if edits:
                chars = list(content)
                for s, e, rep in sorted(edits, key=lambda x: x[0], reverse=True):
                    chars[s:e] = list(rep)
                content = "".join(chars)
        except Exception:
            pass
            
        # 2. Wrap comment lines (original logic)
        lines = content.splitlines()
        fixed_lines = []
        for line in lines:
            if line.lstrip().startswith("--"):
                fixed_lines.extend(wrap_comment_line(line, max_length))
            else:
                fixed_lines.append(line)
                
        return "\n".join(fixed_lines) + ("\n" if content.endswith("\n") else "")
