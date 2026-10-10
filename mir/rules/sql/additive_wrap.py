from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import get_token_depths, source_text_length, tokenize_sql


class AdditiveWrapRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    embedded_dynamic_indent_safe = True
    rule_id = "IR-additive-wrap"
    description = (
        "Long additive expressions should wrap before an operator, with all "
        "continuation operators aligned one indentation level in."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {
        "max_line_length": 100,
        "continuation_max_line_length": 120,
    }
    config_options = {
        "max_line_length": {
            "default": 100,
            "description": "Line length threshold for wrapping additive expressions.",
        },
        "continuation_max_line_length": {
            "default": 120,
            "description": (
                "Line length threshold for an already-wrapped additive "
                "continuation."
            ),
        }
    }

    examples = [
        {
            "violating": (
                "                            first_measure + second_measure + "
                "third_measure + fourth_measure + fifth_measure_with_a_long_name,"
            ),
            "correct": (
                "                            first_measure + second_measure + "
                "third_measure + fourth_measure\n"
                "                                + fifth_measure_with_a_long_name,"
            ),
        },
        {
            "violating": (
                "    first_measure + second_measure\n"
                "           + third_measure +\n"
                "                 fourth_measure"
            ),
            "correct": (
                "    first_measure + second_measure\n"
                "        + third_measure + fourth_measure"
            ),
        },
        {
            "violating": (
                "    first_measure\n"
                "        + second_measure\n"
                "        + third_measure_with_a_long_name + fourth_measure"
            ),
            "correct": (
                "    first_measure + second_measure\n"
                "        + third_measure_with_a_long_name + fourth_measure"
            ),
        },
    ]
    additional_validations = [
        "SELECT first_measure + second_measure FROM sample_measure;",
    ]

    def _find_continuation_edits(
        self, content: str, rule_config: Dict[str, Any]
    ) -> List[dict]:
        """Align existing continuations and rejoin a stranded final operand."""
        base_max_length = self.get_config_value(
            rule_config,
            "max_line_length",
            default_value=100,
        )
        max_length = self.get_config_value(
            rule_config,
            "continuation_max_line_length",
            default_value=120,
        )
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        lines = content.splitlines(keepends=True)
        line_starts = []
        offset = 0
        for line in lines:
            line_starts.append(offset)
            offset += len(line)

        active_by_line: Dict[int, List[int]] = {}
        for index, token in enumerate(tokens):
            if token["type"] not in {"WHITESPACE", "COMMENT"}:
                active_by_line.setdefault(token["line"], []).append(index)

        edits = []
        for line_number, indices in active_by_line.items():
            leading_index = indices[0]
            leading = tokens[leading_index]
            line_start = line_starts[line_number - 1]
            line = lines[line_number - 1].rstrip("\r\n")
            line_indent = line[: len(line) - len(line.lstrip(" \t"))]
            leading_additive = (
                leading["type"] == "OPERATOR"
                and leading["value"] in {"+", "||"}
            )
            expected_indent = line_indent
            continuation_depth = None
            if leading_additive:
                previous_indices = active_by_line.get(line_number - 1)
                continuation_depth = depths[leading_index]
                previous_active_index = next(
                    (
                        index
                        for index in range(leading_index - 1, -1, -1)
                        if tokens[index]["type"] not in {"WHITESPACE", "COMMENT"}
                    ),
                    None,
                )
                is_binary_continuation = (
                    previous_indices
                    and previous_active_index is not None
                    and not any(
                        tokens[index]["type"] == "KEYWORD"
                        and tokens[index]["value"].upper() in {"JOIN", "ON"}
                        for index in previous_indices
                    )
                    and depths[previous_active_index] == continuation_depth
                    and tokens[previous_active_index]["type"]
                    not in {"OPERATOR", "COMMA"}
                    and not (
                        tokens[previous_active_index]["type"] == "PAREN"
                        and tokens[previous_active_index]["value"] == "("
                    )
                )
                if not is_binary_continuation:
                    leading_additive = False
                else:
                    previous_line = lines[line_number - 2].rstrip("\r\n")
                    previous_indent = previous_line[:
                        len(previous_line) - len(previous_line.lstrip(" \t"))
                    ]
                    previous_leading = tokens[previous_indices[0]]
                    expected_indent = previous_indent + (
                        ""
                        if previous_leading["type"] == "OPERATOR"
                        and previous_leading["value"] in {"+", "||"}
                        else "    "
                    )
                    # Expression splitting can strand the first additive
                    # operator on its own continuation even though that first
                    # pair still fits on the base line. Rejoin only to the
                    # stricter base threshold; later continuation lines retain
                    # their separate continuation allowance.
                    whitespace_before_leading = (
                        tokens[leading_index - 1]
                        if leading_index > 0
                        and tokens[leading_index - 1]["type"] == "WHITESPACE"
                        else None
                    )
                    joined_previous = (
                        previous_line.rstrip(" \t")
                        + " "
                        + line.lstrip(" \t")
                    )
                    previous_has_additive = any(
                        tokens[index]["type"] == "OPERATOR"
                        and tokens[index]["value"] in {"+", "||"}
                        and depths[index] == continuation_depth
                        for index in previous_indices
                    )
                    rejoins_previous = (
                        whitespace_before_leading is not None
                        and "\n" in whitespace_before_leading["value"]
                        and not previous_has_additive
                        and source_text_length(joined_previous, rule_config)
                        <= base_max_length
                    )
                    if rejoins_previous:
                        edits.append({
                            "token": leading,
                            "start": whitespace_before_leading["start"],
                            "end": whitespace_before_leading["end"],
                            "replacement": " ",
                        })
                    else:
                        actual_indent = content[line_start:leading["start"]]
                        if actual_indent != expected_indent:
                            edits.append({
                                "token": leading,
                                "start": line_start,
                                "end": leading["start"],
                                "replacement": expected_indent,
                            })

                    following_indices = active_by_line.get(line_number + 1)
                    if following_indices and not rejoins_previous:
                        following_leading_index = following_indices[0]
                        following_leading = tokens[following_leading_index]
                        if (
                            following_leading["type"] == "OPERATOR"
                            and following_leading["value"] in {"+", "||"}
                            and depths[following_leading_index]
                            == continuation_depth
                        ):
                            whitespace_before_following = (
                                tokens[following_leading_index - 1]
                                if following_leading_index > 0
                                and tokens[following_leading_index - 1]["type"]
                                == "WHITESPACE"
                                else None
                            )
                            following_line = lines[line_number].rstrip(
                                "\r\n"
                            ).lstrip(" \t")
                            joined_line = (
                                expected_indent
                                + line.lstrip(" \t")
                                + " "
                                + following_line
                            )
                            if (
                                whitespace_before_following is not None
                                and "\n" in whitespace_before_following["value"]
                                and source_text_length(joined_line, rule_config)
                                <= max_length
                            ):
                                edits.append({
                                    "token": following_leading,
                                    "start": whitespace_before_following["start"],
                                    "end": whitespace_before_following["end"],
                                    "replacement": " ",
                                })

            trailing_index = indices[-1]
            trailing = tokens[trailing_index]
            following_indices = active_by_line.get(line_number + 1)
            if (
                trailing["type"] != "OPERATOR"
                or trailing["value"] not in {"+", "||"}
                or not following_indices
                or depths[following_indices[0]] != depths[trailing_index]
            ):
                continue
            whitespace = (
                tokens[trailing_index + 1]
                if trailing_index + 1 < len(tokens)
                and tokens[trailing_index + 1]["type"] == "WHITESPACE"
                else None
            )
            following = tokens[following_indices[0]]
            if whitespace is None or "\n" not in whitespace["value"]:
                continue
            current_line = line.lstrip(" \t")
            following_line = lines[line_number].rstrip("\r\n").lstrip(" \t")
            joined_line = expected_indent + current_line + " " + following_line
            if source_text_length(joined_line, rule_config) <= max_length:
                edits.append({
                    "token": trailing,
                    "start": whitespace["start"],
                    "end": following["start"],
                    "replacement": " ",
                })
            elif not leading_additive:
                whitespace_before = (
                    tokens[trailing_index - 1]
                    if trailing_index > 0
                    and tokens[trailing_index - 1]["type"] == "WHITESPACE"
                    else None
                )
                if (
                    whitespace_before is not None
                    and "\n" not in whitespace_before["value"]
                ):
                    edits.append({
                        "token": trailing,
                        "start": whitespace_before["start"],
                        "end": following["start"],
                        "replacement": (
                            "\n" + line_indent + "    "
                            + trailing["value"] + " "
                        ),
                    })
        return edits

    def _find_edits(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_length = self.get_config_value(
            rule_config,
            "max_line_length",
            default_value=100,
        )
        continuation_max_length = self.get_config_value(
            rule_config,
            "continuation_max_line_length",
            default_value=120,
        )
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        lines = content.splitlines(keepends=True)
        line_starts = []
        offset = 0
        for line in lines:
            line_starts.append(offset)
            offset += len(line)

        edits = []
        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip("\r\n")
            line_keywords = {
                token["value"].upper()
                for token in tokens
                if token["line"] == line_number and token["type"] == "KEYWORD"
            }
            line_max_length = (
                continuation_max_length
                if (
                    (
                        "CASE" in line_keywords
                        or (
                            "ON" in line_keywords
                            and "DISTINCT" not in line_keywords
                            and "CONFLICT" not in line_keywords
                        )
                    )
                )
                else max_length
            )
            if (
                line.lstrip(" \t").startswith(("+", "||"))
                and source_text_length(line, rule_config)
                <= continuation_max_length
            ):
                continue
            if source_text_length(line, rule_config) <= line_max_length:
                continue
            line_start = line_starts[line_number - 1]
            line_end = line_start + len(line)
            candidates = []
            for index, token in enumerate(tokens):
                if token["line"] != line_number:
                    continue
                if token["type"] != "OPERATOR" or token["value"] not in {"+", "||"}:
                    continue
                previous = next(
                    (
                        tokens[prior]
                        for prior in range(index - 1, -1, -1)
                        if tokens[prior]["type"] not in {"WHITESPACE", "COMMENT"}
                    ),
                    None,
                )
                if previous is None or previous["type"] in {"OPERATOR", "COMMA"}:
                    continue
                candidates.append((index, token, depths[index]))
            if not candidates:
                continue

            shallowest = min(depth for _, _, depth in candidates)
            candidates = [item for item in candidates if item[2] == shallowest]
            first_active = next(
                (
                    (index, token)
                    for index, token in enumerate(tokens)
                    if token["line"] == line_number
                    and token["type"] not in {"WHITESPACE", "COMMENT"}
                ),
                None,
            )
            if first_active is not None and depths[first_active[0]] < shallowest:
                # A function opened on this line owns the wrapping decision.
                # Its arguments should expand before arithmetic inside one
                # argument is considered for continuation wrapping.
                continue
            indent = line[: len(line) - len(line.lstrip(" \t"))] + "    "
            segment_start = line_start
            remaining = candidates
            while source_text_length(
                indent + content[segment_start:line_end].lstrip(" \t"),
                rule_config,
            ) > line_max_length:
                limit = (
                    line_start + line_max_length
                    if segment_start == line_start
                    else segment_start + max_length - len(indent)
                )
                eligible = [item for item in remaining if item[1]["start"] <= limit]
                if not eligible:
                    break
                index, operator, _ = eligible[-1]
                whitespace = (
                    tokens[index - 1]
                    if index > 0 and tokens[index - 1]["type"] == "WHITESPACE"
                    else None
                )
                if whitespace is None or "\n" in whitespace["value"]:
                    break
                edits.append(
                    {
                        "token": operator,
                        "start": whitespace["start"],
                        "end": whitespace["end"],
                        "replacement": "\n" + indent,
                    }
                )
                segment_start = operator["start"]
                remaining = [item for item in remaining if item[1]["start"] > segment_start]
                if not remaining:
                    break
        return edits

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        edits = self._find_edits(content, rule_config)
        edits.extend(self._find_continuation_edits(content, rule_config))
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="Long additive expression should wrap before an operator.",
                offending_lines=[lines[item["token"]["line"] - 1]],
                is_fixable=True,
            )
            for item in edits
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        def apply_nonoverlapping_edits(text: str, items: List[dict]) -> str:
            by_span = {
                (item["start"], item["end"]): item["replacement"]
                for item in items
            }
            accepted = []
            next_start = len(text) + 1
            for (start, end), replacement in sorted(
                by_span.items(), key=lambda item: item[0][0], reverse=True
            ):
                if end > next_start:
                    continue
                accepted.append((start, end, replacement))
                next_start = start
            chars = list(text)
            for start, end, replacement in accepted:
                chars[start:end] = list(replacement)
            return "".join(chars)

        fixed = content
        seen = {fixed}
        for _ in range(16):
            wrapped = apply_nonoverlapping_edits(
                fixed, self._find_edits(fixed, rule_config)
            )
            continuation_edits = self._find_continuation_edits(
                wrapped,
                rule_config,
            )
            updated = apply_nonoverlapping_edits(
                wrapped, continuation_edits
            )
            if updated == fixed:
                break
            if updated in seen:
                break
            seen.add(updated)
            fixed = updated
        return fixed
