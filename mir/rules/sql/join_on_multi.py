import re
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import (
    find_between_delimiter_indices,
    find_boolean_operator_indices,
    find_matching_paren,
    get_token_depths,
    tokenize_sql,
)

class JoinOnMultiRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-join-on-multi"
    description = (
        "Keep JOIN ON conditions inline when they fit; otherwise split AND or OR "
        "conditions onto aligned continuation lines."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM table_one JOIN table_two ON table_one.some_long_column_identifier = table_two.some_long_column_identifier AND table_one.another_long_column_identifier = table_two.another_long_column_identifier;",
            "correct": "SELECT * FROM table_one JOIN table_two ON table_one.some_long_column_identifier = table_two.some_long_column_identifier\n    AND table_one.another_long_column_identifier = table_two.another_long_column_identifier;"
        },
        {
            "violating": "SELECT item.id FROM sample_item item JOIN sample_window window ON item.created_at BETWEEN window.start_at\n    AND window.end_at AND item.organization_identifier = window.organization_identifier;",
            "correct": "SELECT item.id FROM sample_item item JOIN sample_window window\n    ON item.created_at BETWEEN window.start_at AND window.end_at\n    AND item.organization_identifier = window.organization_identifier;"
        },
        {
            "violating": "SELECT item.id FROM sample_item item JOIN sample_owner owner ON owner.id = item.owner_id\n    AND owner.active;",
            "correct": "SELECT item.id FROM sample_item item JOIN sample_owner owner ON owner.id = item.owner_id AND owner.active;"
        }
    ]
    additional_validations = [
        'SELECT * FROM t1 JOIN t2 ON t1.id = t2.id;',
        'SELECT DISTINCT ON (item.item_id) item.item_id FROM sample_item item;',
        'SELECT * FROM t1 JOIN t2 ON t1.created_at BETWEEN t2.start_at AND t2.end_at;'
    ]

    def _find_violations(self, content: str, rule_config: Dict[str, Any] = None) -> List[dict]:
        if rule_config is None:
            rule_config = {}
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        mybatis_dynamic_offsets = rule_config.get("mybatis_dynamic_offsets", set())
        mybatis_boundary_offsets = sorted(
            rule_config.get("mybatis_boundary_offsets", set())
        )
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "ON":
                outer_depth = depths[i]

                prev_active = next(
                    (
                        tokens[index]
                        for index in range(i - 1, -1, -1)
                        if tokens[index]["type"] not in ("WHITESPACE", "COMMENT")
                    ),
                    None,
                )
                if prev_active and prev_active["value"].upper() == "DISTINCT":
                    continue
                
                # Find the preceding JOIN token at the same depth to reconstruct join prefix
                join_tok = None
                for idx in range(i - 1, -1, -1):
                    t = tokens[idx]
                    d = depths[idx]
                    if d == outer_depth and t["type"] == "KEYWORD":
                        value = t["value"].upper()
                        if value in ("JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NATURAL"):
                            join_tok = t
                            break
                        if value in (
                            "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "HAVING",
                            "LIMIT", "UNION", "INTERSECT", "EXCEPT",
                        ):
                            break

                if join_tok is None:
                    continue
                
                if join_tok:
                    join_line_start = content.rfind("\n", 0, join_tok["start"]) + 1
                    join_part = content[join_line_start:tok["start"]]
                    join_target_multiline = "\n" in join_part
                    join_target_is_subquery = bool(
                        join_target_multiline
                        and re.search(r"\bSELECT\b", join_part, re.IGNORECASE)
                    )
                    join_indent = join_part[:len(join_part) - len(join_part.lstrip())]
                    if "\n" in join_part:
                        last_line = join_part.splitlines()[-1]
                        if last_line.strip() == "":
                            non_empty_lines = [l for l in join_part.splitlines() if l.strip() != ""]
                            if non_empty_lines:
                                join_text_normalized = re.sub(r'\s+', ' ', non_empty_lines[-1].strip())
                                join_prefix_for_on = join_indent + join_text_normalized + " "
                            else:
                                join_prefix_for_on = join_indent
                        else:
                            join_prefix_for_on = last_line
                    else:
                        join_text_normalized = re.sub(r'\s+', ' ', join_part.strip())
                        join_prefix_for_on = join_indent + join_text_normalized + " "
                    on_indent = join_indent
                else:
                    join_target_multiline = False
                    join_target_is_subquery = False
                    line_start = content.rfind("\n", 0, tok["start"]) + 1
                    line_prefix = content[line_start:tok["start"]]
                    join_prefix_for_on = line_prefix
                    on_indent = ""
                    for char in line_prefix:
                        if char in (" ", "\t"):
                            on_indent += char
                        else:
                            break
                            
                expected_indent = on_indent + "    "
                
                clause_end = n
                next_boundary = next(
                    (
                        offset
                        for offset in mybatis_boundary_offsets
                        if offset > tok["end"]
                    ),
                    None,
                )
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if next_boundary is not None and t["end"] > next_boundary:
                        clause_end = idx
                        break
                    if d < outer_depth:
                        clause_end = idx
                        break
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NATURAL",
                            "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] == "SEMI":
                            clause_end = idx
                            break
                            
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                boolean_indices = find_boolean_operator_indices(
                    tokens, depths, outer_depth, i + 1, clause_end
                )
                has_dynamic_boolean = any(
                    tokens[index]["start"] in mybatis_dynamic_offsets
                    for index in boolean_indices
                )
                between_delimiter_indices = find_between_delimiter_indices(
                    tokens, depths, outer_depth, i + 1, clause_end
                )
                
                on_clause_tokens = tokens[i : clause_end]
                has_multiline_group = False
                for group_index in range(i + 1, clause_end):
                    group_token = tokens[group_index]
                    if group_token["type"] != "PAREN" or group_token["value"] != "(":
                        continue
                    group_close_index = find_matching_paren(tokens, group_index)
                    if (
                        group_close_index is not None
                        and tokens[group_close_index]["line"] > group_token["line"]
                    ):
                        has_multiline_group = True
                        break
                grouped_boolean_edits = []
                for boolean_index in boolean_indices:
                    next_active_index = next(
                        (
                            index
                            for index in range(boolean_index + 1, clause_end)
                            if tokens[index]["type"] not in {"WHITESPACE", "COMMENT"}
                        ),
                        None,
                    )
                    if (
                        next_active_index is None
                        or tokens[next_active_index]["type"] != "PAREN"
                        or tokens[next_active_index]["value"] != "("
                    ):
                        continue
                    group_close_index = find_matching_paren(
                        tokens, next_active_index
                    )
                    if (
                        group_close_index is None
                        or group_close_index >= clause_end
                    ):
                        continue
                    first_group_active = next(
                        (
                            index
                            for index in range(
                                next_active_index + 1, group_close_index
                            )
                            if tokens[index]["type"]
                            not in {"WHITESPACE", "COMMENT"}
                        ),
                        None,
                    )
                    if (
                        first_group_active is not None
                        and tokens[first_group_active]["type"] == "PAREN"
                        and tokens[first_group_active]["value"] == "("
                    ):
                        # Nullable-equality rewrites use a double-wrapped
                        # boolean form. Leave it intact for the semantic rule
                        # that replaces the whole expression with coalesce().
                        continue
                    inner_booleans = [
                        index
                        for index in find_boolean_operator_indices(
                            tokens,
                            depths,
                            outer_depth + 1,
                            next_active_index + 1,
                            group_close_index,
                        )
                    ]
                    if not inner_booleans:
                        continue
                    has_multiline_group = True
                    group_indent = expected_indent + "    "

                    after_open = (
                        tokens[next_active_index + 1]
                        if next_active_index + 1 < len(tokens)
                        and tokens[next_active_index + 1]["type"] == "WHITESPACE"
                        else None
                    )
                    grouped_boolean_edits.append({
                        "token": tokens[next_active_index],
                        "ws_start": (
                            after_open["start"]
                            if after_open else tokens[next_active_index]["end"]
                        ),
                        "ws_end": (
                            after_open["end"]
                            if after_open else tokens[next_active_index]["end"]
                        ),
                        "replacement": "\n" + group_indent,
                    })
                    for inner_index in inner_booleans:
                        before_inner = (
                            tokens[inner_index - 1]
                            if inner_index > 0
                            and tokens[inner_index - 1]["type"] == "WHITESPACE"
                            else None
                        )
                        grouped_boolean_edits.append({
                            "token": tokens[inner_index],
                            "ws_start": (
                                before_inner["start"]
                                if before_inner else tokens[inner_index]["start"]
                            ),
                            "ws_end": tokens[inner_index]["start"],
                            "replacement": "\n" + group_indent,
                        })
                    before_close = (
                        tokens[group_close_index - 1]
                        if group_close_index > 0
                        and tokens[group_close_index - 1]["type"] == "WHITESPACE"
                        else None
                    )
                    grouped_boolean_edits.append({
                        "token": tokens[group_close_index],
                        "ws_start": (
                            before_close["start"]
                            if before_close else tokens[group_close_index]["start"]
                        ),
                        "ws_end": tokens[group_close_index]["start"],
                        "replacement": "\n" + expected_indent,
                    })
                on_clause_single = "".join(
                    " " if t["type"] == "WHITESPACE" else t["value"]
                    for t in on_clause_tokens
                )
                estimated_line_len = (
                    len(join_prefix_for_on.rstrip())
                    + 1
                    + len(on_clause_single.strip())
                )
                source_indent_offset = 0
                base_indent = rule_config.get("base_indent")
                if (
                    "original_xml" in rule_config
                    and isinstance(base_indent, str)
                    and (
                        join_target_multiline
                        or has_dynamic_boolean
                        or next_boundary is not None
                    )
                ):
                    source_indent_offset = len(
                        base_indent.replace("\t", "    ")
                    )
                    estimated_line_len += source_indent_offset
                
                from mir.rules.sql.line_length import LineLengthRule
                max_len = self.get_config_value(rule_config, "max_line_length", 100, fallbacks=[(LineLengthRule, "max_length")])
                
                first_cond_toks = []
                for actual_idx, t in enumerate(tokens[i + 1:clause_end], start=i + 1):
                    if actual_idx in boolean_indices:
                        break
                    first_cond_toks.append(t)
                
                if first_cond_toks and first_cond_toks[0]["type"] == "WHITESPACE":
                    first_cond_toks.pop(0)
                    
                first_cond_str = "".join(t["value"] for t in first_cond_toks).strip()
                first_cond_str_normalized = "".join(
                    " " if t["type"] == "WHITESPACE" else t["value"]
                    for t in first_cond_toks
                ).strip()
                # An additive continuation has its own wrapping policy.  Do
                # not count the continuation when deciding whether ON fits
                # beside a multiline join target; otherwise a stable
                # ``target ON expression\n    + operand`` layout is pulled
                # apart on the next convergence pass.
                first_cond_line_tokens = []
                has_additive_continuation = False
                for first_cond_index, item in enumerate(first_cond_toks):
                    if (
                        item["type"] == "WHITESPACE"
                        and "\n" in item["value"]
                    ):
                        next_item = next(
                            (
                                candidate
                                for candidate in first_cond_toks[
                                    first_cond_index + 1 :
                                ]
                                if candidate["type"]
                                not in {"WHITESPACE", "COMMENT"}
                            ),
                            None,
                        )
                        has_additive_continuation = bool(
                            next_item
                            and next_item["type"] == "OPERATOR"
                            and next_item["value"] in {"+", "||"}
                        )
                        break
                    first_cond_line_tokens.append(item)
                first_cond_line_normalized = "".join(
                    " " if item["type"] == "WHITESPACE" else item["value"]
                    for item in first_cond_line_tokens
                ).strip()

                operator_split = None
                comparison_operators = {"=", "!=", "<>", "<", ">", "<=", ">="}
                for actual_idx in range(i + 1, clause_end):
                    if actual_idx in boolean_indices:
                        break
                    candidate = tokens[actual_idx]
                    if (
                        depths[actual_idx] == outer_depth
                        and candidate["type"] == "OPERATOR"
                        and candidate["value"] in comparison_operators
                    ):
                        left = "".join(
                            " " if item["type"] == "WHITESPACE" else item["value"]
                            for item in tokens[i + 1 : actual_idx + 1]
                        ).strip()
                        first_condition_end = (
                            boolean_indices[0] if boolean_indices else clause_end
                        )
                        right = "".join(
                            " " if item["type"] == "WHITESPACE" else item["value"]
                            for item in tokens[actual_idx + 1 : first_condition_end]
                        ).strip()
                        first_candidate = (
                            join_prefix_for_on.rstrip() + " ON " + left
                        )
                        second_candidate = expected_indent + right
                        right_active = [
                            item
                            for item in tokens[actual_idx + 1:first_condition_end]
                            if item["type"] not in ("WHITESPACE", "COMMENT")
                        ]
                        right_is_subquery = bool(
                            len(right_active) >= 2
                            and right_active[0]["type"] == "PAREN"
                            and right_active[0]["value"] == "("
                            and right_active[1]["type"] == "KEYWORD"
                            and right_active[1]["value"].upper() == "SELECT"
                        )
                        compact_on_candidate = (
                            expected_indent
                            + "ON "
                            + left
                            + " "
                            + candidate["value"]
                            + " "
                            + right
                        )
                        if (
                            right
                            and len(right) > max_len // 3
                            and len(first_candidate) + len(candidate["value"]) + 1
                            <= max_len
                            and len(second_candidate) <= max_len
                            and len(first_candidate) + 1 + len(right) > max_len
                            and not (
                                right_is_subquery
                                and len(compact_on_candidate) <= max_len
                            )
                        ):
                            operator_split = actual_idx
                        break
                
                estimated_first_line_len = (
                    len(join_prefix_for_on)
                    + len("ON ")
                    + len(
                        first_cond_line_normalized
                        if has_additive_continuation
                        else first_cond_str_normalized
                    )
                    + source_indent_offset
                )
                prospective_additive_index = None
                if (
                    not has_additive_continuation
                    and estimated_line_len > max_len
                ):
                    for first_cond_position in range(
                        len(first_cond_toks) - 1,
                        -1,
                        -1,
                    ):
                        candidate = first_cond_toks[first_cond_position]
                        if (
                            candidate["type"] != "OPERATOR"
                            or candidate["value"] not in {"+", "||"}
                        ):
                            continue
                        before_additive = "".join(
                            " " if item["type"] == "WHITESPACE" else item["value"]
                            for item in first_cond_toks[:first_cond_position]
                        ).strip()
                        prospective_length = (
                            len(join_prefix_for_on)
                            + len("ON ")
                            + len(before_additive)
                            + source_indent_offset
                        )
                        if prospective_length <= max_len:
                            estimated_first_line_len = prospective_length
                            prospective_additive_index = next(
                                (
                                    index
                                    for index, item in enumerate(tokens)
                                    if item is candidate
                                ),
                                None,
                            )
                            break
                expected_pre_on_ws = (
                    "\n" + expected_indent
                    if estimated_first_line_len > max_len and operator_split is None
                    else " "
                )
                expected_post_on_ws = " "
                
                ws_before_on = None
                if i - 1 >= 0 and tokens[i - 1]["type"] == "WHITESPACE":
                    ws_before_on = tokens[i - 1]
                    
                actual_pre_on_ws = ws_before_on["value"] if ws_before_on else ""
                if actual_pre_on_ws != expected_pre_on_ws:
                    violations.append({
                        "token": tok,
                        "ws_start": ws_before_on["start"] if ws_before_on else tok["start"],
                        "ws_end": tok["start"],
                        "replacement": expected_pre_on_ws
                    })
                    
                ws_after_on = None
                if i + 1 < n and tokens[i + 1]["type"] == "WHITESPACE":
                    ws_after_on = tokens[i + 1]
                    
                actual_post_on_ws = ws_after_on["value"] if ws_after_on else ""
                if actual_post_on_ws != expected_post_on_ws:
                    violations.append({
                        "token": tok,
                        "ws_start": ws_after_on["start"] if ws_after_on else tok["end"],
                        "ws_end": ws_after_on["end"] if ws_after_on else tok["end"],
                        "replacement": expected_post_on_ws
                    })

                if prospective_additive_index is not None:
                    additive = tokens[prospective_additive_index]
                    whitespace_before_additive = (
                        tokens[prospective_additive_index - 1]
                        if prospective_additive_index > 0
                        and tokens[prospective_additive_index - 1]["type"]
                        == "WHITESPACE"
                        else None
                    )
                    expected_additive_ws = "\n" + expected_indent
                    if (
                        whitespace_before_additive is None
                        or whitespace_before_additive["value"]
                        != expected_additive_ws
                    ):
                        violations.append({
                            "token": additive,
                            "ws_start": (
                                whitespace_before_additive["start"]
                                if whitespace_before_additive
                                else additive["start"]
                            ),
                            "ws_end": additive["start"],
                            "replacement": expected_additive_ws,
                        })

                violations.extend(
                    item
                    for item in grouped_boolean_edits
                    if content[item["ws_start"]:item["ws_end"]]
                    != item["replacement"]
                )

                if operator_split is not None:
                    operator = tokens[operator_split]
                    ws_after_operator = (
                        tokens[operator_split + 1]
                        if operator_split + 1 < n
                        and tokens[operator_split + 1]["type"] == "WHITESPACE"
                        else None
                    )
                    expected_operator_ws = "\n" + expected_indent
                    if (
                        ws_after_operator is None
                        or ws_after_operator["value"] != expected_operator_ws
                    ):
                        violations.append({
                            "token": operator,
                            "ws_start": (
                                ws_after_operator["start"]
                                if ws_after_operator
                                else operator["end"]
                            ),
                            "ws_end": (
                                ws_after_operator["end"]
                                if ws_after_operator
                                else operator["end"]
                            ),
                            "replacement": expected_operator_ws,
                        })

                for delimiter_idx in between_delimiter_indices:
                    delimiter = tokens[delimiter_idx]
                    ws_before = (
                        tokens[delimiter_idx - 1]
                        if delimiter_idx and tokens[delimiter_idx - 1]["type"] == "WHITESPACE"
                        else None
                    )
                    condition_start = max(
                        (index + 1 for index in boolean_indices if index < delimiter_idx),
                        default=i + 1,
                    )
                    condition_end = min(
                        (index for index in boolean_indices if index > delimiter_idx),
                        default=clause_end,
                    )
                    condition_single = "".join(
                        " " if token["type"] == "WHITESPACE" else token["value"]
                        for token in tokens[condition_start:condition_end]
                    ).strip()
                    expected_delimiter_ws = (
                        " "
                        if len(expected_indent) + len(condition_single) <= max_len
                        else "\n" + expected_indent + "    "
                    )
                    if (
                        not ws_before
                        or ws_before["value"] != expected_delimiter_ws
                    ):
                        violations.append({
                            "token": delimiter,
                            "ws_start": ws_before["start"] if ws_before else delimiter["start"],
                            "ws_end": delimiter["start"],
                            "replacement": expected_delimiter_ws,
                        })
                
                if (
                    estimated_line_len <= max_len
                    and (
                        not join_target_multiline
                        or join_target_is_subquery
                        or has_additive_continuation
                    )
                    and not has_multiline_group
                ):
                    if not any(
                        token["type"] == "COMMENT"
                        for token in tokens[i + 1 : clause_end]
                    ):
                        last_active_idx = next(
                            (
                                index
                                for index in range(clause_end - 1, i, -1)
                                if tokens[index]["type"] not in ("WHITESPACE", "COMMENT")
                            ),
                            None,
                        )
                        if last_active_idx is not None:
                            for index in range(i + 1, last_active_idx):
                                whitespace = tokens[index]
                                if (
                                    whitespace["type"] == "WHITESPACE"
                                    and whitespace["value"] != " "
                                ):
                                    violations.append({
                                        "token": whitespace,
                                        "ws_start": whitespace["start"],
                                        "ws_end": whitespace["end"],
                                        "replacement": " ",
                                    })
                    continue
                    
                for actual_idx in boolean_indices:
                    t = tokens[actual_idx]
                    ws_before = None
                    if actual_idx - 1 >= 0 and tokens[actual_idx - 1]["type"] == "WHITESPACE":
                        ws_before = tokens[actual_idx - 1]

                    expected_replacement = "\n" + expected_indent
                    if not ws_before or ws_before["value"] != expected_replacement:
                        violations.append({
                            "token": t,
                            "ws_start": ws_before["start"] if ws_before else t["start"],
                            "ws_end": t["start"],
                            "replacement": expected_replacement
                        })
                    next_active_idx = next(
                        (
                            index
                            for index in range(actual_idx + 1, clause_end)
                            if tokens[index]["type"]
                            not in ("WHITESPACE", "COMMENT")
                        ),
                        None,
                    )
                    if next_active_idx is None:
                        continue
                    next_active = tokens[next_active_idx]
                    crosses_dynamic_boundary = (
                        next_active["start"] in mybatis_dynamic_offsets
                        or any(
                            t["end"] <= offset <= next_active["start"]
                            for offset in mybatis_boundary_offsets
                        )
                    )
                    if crosses_dynamic_boundary:
                        continue
                    ws_after = (
                        tokens[actual_idx + 1]
                        if actual_idx + 1 < len(tokens)
                        and tokens[actual_idx + 1]["type"] == "WHITESPACE"
                        else None
                    )
                    if ws_after is None or ws_after["value"] != " ":
                        violations.append({
                            "token": t,
                            "ws_start": ws_after["start"] if ws_after else t["end"],
                            "ws_end": ws_after["end"] if ws_after else t["end"],
                            "replacement": " ",
                        })
                            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        
        for item in offending:
            tok = item["token"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="AND or OR condition in JOIN ON clause should start on a new line.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content, rule_config)
        if not offending:
            return content
            
        edits = []
        for item in offending:
            edits.append((item["ws_start"], item["ws_end"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
