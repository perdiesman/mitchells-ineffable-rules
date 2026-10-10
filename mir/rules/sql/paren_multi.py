from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import (
    find_boolean_operator_indices,
    find_matching_paren,
    get_token_depths,
    source_text_length,
    tokenize_sql,
)

class ParenMultiRule(BaseRule):
    commit_profile = True
    rule_id = "IR-paren-multi"
    description = "Parenthesized logical conditions stay inline when they fit; longer groups put each condition on its own indented line."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE active AND (\n    enabled\n    OR not blocked\n);",
            "correct": "SELECT * FROM users WHERE active AND (enabled OR not blocked);"
        }
    ]
    additional_validations = [
        "SELECT item_id FROM sample_item WHERE NOT EXISTS (SELECT 1 FROM sample_child);",
        "SELECT item_id FROM sample_item WHERE (created_at BETWEEN :start AND :end);",
    ]

    def _find_violations(
        self, content: str, rule_config: Dict[str, Any] | None = None
    ) -> List[dict]:
        rule_config = rule_config or {}
        from mir.rules.sql.line_length import LineLengthRule

        max_length = self.get_config_value(
            rule_config,
            "max_line_length",
            100,
            fallbacks=[(LineLengthRule, "max_length")],
        )
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        def next_active(start_idx: int) -> int:
            for idx in range(start_idx, n):
                if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                    return idx
            return n

        for i, tok in enumerate(tokens):
            if tok["type"] == "PAREN" and tok["value"] == "(":
                in_where_or_on = False
                for idx in range(i - 1, -1, -1):
                    t = tokens[idx]
                    if depths[idx] == depths[i]:
                        if t["type"] == "SEMI" or t["value"] == ";":
                            break
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("WHERE", "ON"):
                            in_where_or_on = True
                            break
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("SELECT", "FROM", "GROUP", "ORDER", "LIMIT", "WITH"):
                            break
                            
                if not in_where_or_on:
                    continue
                    
                close_idx = find_matching_paren(tokens, i)
                if close_idx is None:
                    continue

                first_inner_idx = next_active(i + 1)
                if (
                    first_inner_idx < close_idx
                    and tokens[first_inner_idx]["type"] == "KEYWORD"
                    and tokens[first_inner_idx]["value"].upper() == "SELECT"
                ):
                    continue
                    
                boolean_indices = find_boolean_operator_indices(
                    tokens, depths, depths[i] + 1, i + 1, close_idx
                )
                has_logical_check = bool(boolean_indices)
                inner_keywords = [(tokens[index], index) for index in boolean_indices]
                            
                if not has_logical_check:
                    continue
                    
                line_start = content.rfind("\n", 0, tok["start"]) + 1
                line_prefix = content[line_start:tok["start"]]
                paren_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        paren_indent += char
                    else:
                        break
                        
                expected_content_indent = paren_indent + "    "
                expected_close_indent = paren_indent

                group_single = "".join(
                    " " if item["type"] == "WHITESPACE" else item["value"]
                    for item in tokens[i:close_idx + 1]
                )
                if (
                    not any(
                        item["type"] == "COMMENT"
                        for item in tokens[i:close_idx + 1]
                    )
                    and source_text_length(
                        content[line_start:tok["start"]] + group_single,
                        rule_config,
                    ) <= max_length
                ):
                    for index in range(i + 1, close_idx):
                        item = tokens[index]
                        if (
                            item["type"] == "WHITESPACE"
                            and item["value"]
                            != (
                                ""
                                if index in {i + 1, close_idx - 1}
                                else " "
                            )
                        ):
                            replacement = (
                                "" if index in {i + 1, close_idx - 1} else " "
                            )
                            violations.append({
                                "token": item,
                                "ws_start": item["start"],
                                "ws_end": item["end"],
                                "replacement": replacement,
                            })
                    continue
                
                # Check first active token inside parenthesis
                first_tok_idx = next_active(i + 1)
                if first_tok_idx < close_idx:
                    first_tok = tokens[first_tok_idx]
                    ws_before = None
                    if first_tok_idx - 1 >= 0 and tokens[first_tok_idx - 1]["type"] == "WHITESPACE":
                        ws_before = tokens[first_tok_idx - 1]
                    expected_ws = "\n" + expected_content_indent
                    if not ws_before or ws_before["value"] != expected_ws:
                        violations.append({
                            "token": first_tok,
                            "ws_start": ws_before["start"] if ws_before else first_tok["start"],
                            "ws_end": first_tok["start"],
                            "replacement": expected_ws
                        })
                        
                # Check subsequent top-level logical check keywords inside
                for kw, kw_idx in inner_keywords:
                    ws_before = None
                    if kw_idx - 1 >= 0 and tokens[kw_idx - 1]["type"] == "WHITESPACE":
                        ws_before = tokens[kw_idx - 1]
                    expected_ws = "\n" + expected_content_indent
                    if not ws_before or ws_before["value"] != expected_ws:
                        violations.append({
                            "token": kw,
                            "ws_start": ws_before["start"] if ws_before else kw["start"],
                            "ws_end": kw["start"],
                            "replacement": expected_ws
                        })

                    next_boolean = min(
                        (index for index in boolean_indices if index > kw_idx),
                        default=close_idx,
                    )
                    arm_tokens = tokens[kw_idx:next_boolean]
                    if not any(
                        item["type"] == "COMMENT" for item in arm_tokens
                    ):
                        arm_single = "".join(
                            " " if item["type"] == "WHITESPACE" else item["value"]
                            for item in arm_tokens
                        ).strip()
                        if source_text_length(
                            expected_content_indent + arm_single,
                            rule_config,
                        ) <= max_length:
                            last_active = next(
                                (
                                    index
                                    for index in range(next_boolean - 1, kw_idx, -1)
                                    if tokens[index]["type"]
                                    not in {"WHITESPACE", "COMMENT"}
                                ),
                                None,
                            )
                            if last_active is not None:
                                for index in range(kw_idx + 1, last_active):
                                    item = tokens[index]
                                    if (
                                        item["type"] == "WHITESPACE"
                                        and item["value"] != " "
                                    ):
                                        violations.append({
                                            "token": item,
                                            "ws_start": item["start"],
                                            "ws_end": item["end"],
                                            "replacement": " ",
                                        })

                # A long comparison inside the group may wrap after its
                # operator. Its operand is a single continuation level from
                # the comparison, never column-aligned to legacy source text.
                for token_index in range(i + 1, close_idx - 1):
                    operator = tokens[token_index]
                    whitespace = tokens[token_index + 1]
                    if (
                        operator["type"] != "OPERATOR"
                        or operator["value"]
                        not in {"=", "!=", "<>", "<", ">", "<=", ">="}
                        or whitespace["type"] != "WHITESPACE"
                        or "\n" not in whitespace["value"]
                    ):
                        continue
                    operator_line_start = content.rfind(
                        "\n", 0, operator["start"]
                    ) + 1
                    operator_prefix = content[
                        operator_line_start:operator["start"]
                    ]
                    operator_indent = operator_prefix[
                        : len(operator_prefix)
                        - len(operator_prefix.lstrip(" \t"))
                    ]
                    expected_operand_ws = "\n" + operator_indent + "    "
                    if whitespace["value"] != expected_operand_ws:
                        violations.append({
                            "token": operator,
                            "ws_start": whitespace["start"],
                            "ws_end": whitespace["end"],
                            "replacement": expected_operand_ws,
                        })
                        
                # Check closing parenthesis
                ws_before_close = None
                if close_idx - 1 >= 0 and tokens[close_idx - 1]["type"] == "WHITESPACE":
                    ws_before_close = tokens[close_idx - 1]
                expected_ws = "\n" + expected_close_indent
                if not ws_before_close or ws_before_close["value"] != expected_ws:
                    violations.append({
                        "token": tokens[close_idx],
                        "ws_start": ws_before_close["start"] if ws_before_close else tokens[close_idx]["start"],
                        "ws_end": tokens[close_idx]["start"],
                        "replacement": expected_ws
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
                    message="Logical condition parenthesis block inside WHERE/ON should be split to separate lines.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content, rule_config)
        if not offending:
            return content
            
        edits = {}
        for item in offending:
            edits[(item["ws_start"], item["ws_end"])] = item["replacement"]
            
        edits = sorted(
            edits.items(), key=lambda item: item[0][0], reverse=True
        )
        chars = list(content)
        for (start, end), new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
