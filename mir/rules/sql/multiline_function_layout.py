from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql
from mir.rules.sql.table_function_indent import table_function_parens
from mir.rules.sql.paren_content_indent import is_create_table_opening


class MultilineFunctionLayoutRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    embedded_dynamic_indent_safe = True
    rule_id = "IR-multiline-function-layout"
    description = (
        "Multiline function calls, row constructors, and single-row VALUES "
        "lists should put every direct argument on its own indented line and "
        "align the closing parenthesis with the caller."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"indent_size": 4}
    config_options = {
        "indent_size": {
            "default": 4,
            "description": "Spaces added for function arguments.",
            "fallback": "IR-indent:indent_size",
        }
    }

    examples = [
        {
            "violating": "coalesce(item_count,\n0)",
            "correct": (
                "coalesce(\n"
                "    item_count,\n"
                "    0\n"
                ")"
            ),
        },
        {
            "violating": "WHERE (item_id,\nowner_id) = (source_id,\nsource_owner_id)",
            "correct": (
                "WHERE (\n"
                "    item_id,\n"
                "    owner_id\n"
                ") = (\n"
                "    source_id,\n"
                "    source_owner_id\n"
                ")"
            ),
        },
    ]
    additional_validations = [
        "sum(item_count)",
        "coalesce(item_count, 0)",
        "WHERE (item_id, owner_id) = (:item_id, :owner_id)",
    ]

    def _find_edits(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        table_openings = table_function_parens(tokens)
        boundary_offsets = rule_config.get("mybatis_boundary_offsets", set())
        indent_size = self.get_config_value(rule_config, "indent_size", 4)
        unit = " " * indent_size
        edits = []
        previous_active_indices = [None] * len(tokens)
        previous_active_index = None
        paren_pairs = {}
        closing_to_opening = {}
        parent_openings = {}
        paren_stack = []
        for token_index, token in enumerate(tokens):
            previous_active_indices[token_index] = previous_active_index
            if token["type"] not in ("WHITESPACE", "COMMENT"):
                previous_active_index = token_index
            if token["type"] != "PAREN":
                continue
            if token["value"] == "(":
                parent_openings[token_index] = (
                    paren_stack[-1] if paren_stack else None
                )
                paren_stack.append(token_index)
            elif token["value"] == ")" and paren_stack:
                matched_open = paren_stack.pop()
                paren_pairs[matched_open] = token_index
                closing_to_opening[token_index] = matched_open

        def edit_whitespace(index: int, replacement: str, before: bool) -> None:
            whitespace_index = index - 1 if before else index + 1
            whitespace = (
                tokens[whitespace_index]
                if 0 <= whitespace_index < len(tokens)
                and tokens[whitespace_index]["type"] == "WHITESPACE"
                else None
            )
            token = tokens[index]
            start = whitespace["start"] if whitespace else (
                token["start"] if before else token["end"]
            )
            end = whitespace["end"] if whitespace else (
                token["start"] if before else token["end"]
            )
            if content[start:end] != replacement:
                edits.append({
                    "token": token,
                    "start": start,
                    "end": end,
                    "replacement": replacement,
                })

        for open_index, opening in enumerate(tokens):
            if (
                opening["type"] != "PAREN"
                or opening["value"] != "("
                or open_index in table_openings
            ):
                continue
            close_index = paren_pairs.get(open_index)
            if close_index is None or tokens[close_index]["line"] == opening["line"]:
                continue
            direct_comma = False
            depth = 0
            for candidate in range(open_index + 1, close_index):
                token = tokens[candidate]
                if token["type"] == "PAREN":
                    depth += 1 if token["value"] == "(" else -1
                elif token["type"] == "COMMA" and depth == 0:
                    direct_comma = True
                    break

            name_index = previous_active_indices[open_index]
            has_callable_owner = bool(
                name_index is not None
                and (
                    tokens[name_index]["type"] == "IDENTIFIER"
                    or (
                        tokens[name_index]["type"] == "KEYWORD"
                        and tokens[name_index]["value"].upper()
                        in {"COALESCE", "NULLIF", "VALUES"}
                    )
                )
            )
            next_active_index = next(
                (
                    candidate
                    for candidate in range(close_index + 1, len(tokens))
                    if tokens[candidate]["type"]
                    not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            first_inner_index = next(
                (
                    candidate
                    for candidate in range(open_index + 1, close_index)
                    if tokens[candidate]["type"]
                    not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            follows_row_operator = bool(
                next_active_index is not None
                and (
                    tokens[next_active_index]["type"] == "OPERATOR"
                    or (
                        tokens[next_active_index]["type"] == "KEYWORD"
                        and tokens[next_active_index]["value"].upper()
                        in {"IS", "IN"}
                    )
                )
            )
            follows_comparison_operator = bool(
                name_index is not None
                and tokens[name_index]["type"] == "OPERATOR"
            )
            preceded_by_distinct_from = False
            if (
                name_index is not None
                and tokens[name_index]["type"] == "KEYWORD"
                and tokens[name_index]["value"].upper() == "FROM"
            ):
                distinct_index = previous_active_indices[name_index]
                preceded_by_distinct_from = bool(
                    distinct_index is not None
                    and tokens[distinct_index]["type"] == "KEYWORD"
                    and tokens[distinct_index]["value"].upper() == "DISTINCT"
                )
            is_row_value_list = bool(
                name_index is not None
                and tokens[name_index]["type"] == "KEYWORD"
                and tokens[name_index]["value"].upper() == "IN"
                and first_inner_index is not None
                and tokens[first_inner_index]["type"] == "PAREN"
            )
            parent_open = parent_openings.get(open_index)
            if parent_open is None and is_create_table_opening(tokens, open_index):
                # The relation name before a CREATE TABLE column list is an
                # identifier, but it is not a callable owner. DDL field layout
                # and generic parenthesis indentation own this list.
                continue
            parent_owner = (
                previous_active_indices[parent_open]
                if parent_open is not None else None
            )
            is_nested_row_value = bool(
                parent_owner is not None
                and tokens[parent_owner]["type"] == "KEYWORD"
                and tokens[parent_owner]["value"].upper() == "IN"
            )
            # Parenthesized comma expressions are SQL row constructors (or a
            # list of row constructors). They use the same readable layout as
            # function arguments even though there is no callable identifier
            # immediately before the opening parenthesis.
            is_row_constructor = direct_comma and not has_callable_owner and (
                follows_row_operator
                or follows_comparison_operator
                or preceded_by_distinct_from
                or is_row_value_list
                or is_nested_row_value
            )
            if not has_callable_owner and not is_row_constructor:
                continue
            preceding_active = []
            preceding_index = (
                previous_active_indices[name_index]
                if name_index is not None else None
            )
            while preceding_index is not None and len(preceding_active) < 4:
                preceding_active.append(tokens[preceding_index])
                preceding_index = previous_active_indices[preceding_index]
            is_insert_target = any(
                token["type"] == "KEYWORD"
                and token["value"].upper() == "INTO"
                for token in preceding_active
            )
            is_reference_target = any(
                token["type"] == "KEYWORD"
                and token["value"].upper() == "REFERENCES"
                for token in preceding_active
            )
            if is_reference_target:
                # A relation followed by its referenced columns is schema
                # syntax, not a function call. Constraint layout owns it.
                continue
            first_inner_active = next(
                (
                    tokens[candidate]
                    for candidate in range(open_index + 1, close_index)
                    if tokens[candidate]["type"]
                    not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            if (
                is_insert_target
                and first_inner_active is not None
                and first_inner_active["type"] == "KEYWORD"
                and first_inner_active["value"].upper() in {"SELECT", "WITH"}
            ):
                # INSERT INTO relation (...) may contain a parenthesized
                # query rather than a column list. It is not a function call.
                continue
            line = lines[opening["line"] - 1]
            base_indent = line[: len(line) - len(line.lstrip(" \t"))]
            connector_start = None
            left_close_index = None
            if name_index is not None and tokens[name_index]["type"] == "KEYWORD":
                connector = tokens[name_index]["value"].upper()
                if connector == "IN":
                    connector_start = name_index
                    left_close_index = previous_active_indices[name_index]
                elif connector == "FROM":
                    distinct_index = previous_active_indices[name_index]
                    if (
                        distinct_index is not None
                        and tokens[distinct_index]["type"] == "KEYWORD"
                        and tokens[distinct_index]["value"].upper() == "DISTINCT"
                    ):
                        is_index = previous_active_indices[distinct_index]
                        if (
                            is_index is not None
                            and tokens[is_index]["type"] == "KEYWORD"
                            and tokens[is_index]["value"].upper() == "NOT"
                        ):
                            is_index = previous_active_indices[is_index]
                        if (
                            is_index is not None
                            and tokens[is_index]["type"] == "KEYWORD"
                            and tokens[is_index]["value"].upper() == "IS"
                        ):
                            connector_start = is_index
                            left_close_index = previous_active_indices[is_index]
            left_open_index = closing_to_opening.get(left_close_index)
            if left_open_index is not None:
                left_opening = tokens[left_open_index]
                left_line = lines[left_opening["line"] - 1]
                base_indent = left_line[
                    : len(left_line) - len(left_line.lstrip(" \t"))
                ]
                edit_whitespace(connector_start, " ", before=True)
                edit_whitespace(open_index, " ", before=True)
            argument_indent = base_indent + unit
            edit_whitespace(open_index, "\n" + argument_indent, before=False)
            edit_whitespace(close_index, "\n" + base_indent, before=True)

            depth = 0
            for candidate in range(open_index + 1, close_index):
                token = tokens[candidate]
                if token["type"] == "PAREN":
                    depth += 1 if token["value"] == "(" else -1
                elif token["type"] == "COMMA" and depth == 0:
                    if token["start"] in boundary_offsets:
                        continue
                    edit_whitespace(
                        candidate, "\n" + argument_indent, before=False
                    )

        return list({(item["start"], item["end"]): item for item in edits}.values())

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="Multiline function arguments should use one aligned line per argument.",
                offending_lines=[lines[item["token"]["line"] - 1]],
                is_fixable=True,
            )
            for item in self._find_edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        chars = list(content)
        for item in sorted(self._find_edits(content, rule_config), key=lambda edit: edit["start"], reverse=True):
            chars[item["start"]:item["end"]] = list(item["replacement"])
        return "".join(chars)
