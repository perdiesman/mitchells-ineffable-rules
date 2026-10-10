import re
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.case_when_wrap import CaseWhenWrapRule
from mir.rules.sql.sql_utils import (
    find_boolean_operator_indices,
    get_token_depths,
    source_text_length,
    tokenize_sql,
)
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.line_length import LineLengthRule

class CaseLayoutRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-case"
    description = (
        "CASE statements should be formatted with WHEN/THEN on separate lines "
        "unless the block is simple (exactly one WHEN condition and an optional ELSE clause) "
        "and fits on a single line within length constraints."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT CASE WHEN x = 1 THEN 'a' WHEN x = 2 THEN 'b' ELSE 'c' END FROM users;",
            "correct": "SELECT \n    CASE\n        WHEN x = 1 THEN 'a'\n        WHEN x = 2 THEN 'b'\n        ELSE 'c'\n    END FROM users;"
        }
    ]
    additional_validations = [
        "SELECT CASE WHEN x = 1 THEN 'a' END FROM users;",
        "SELECT CASE WHEN x = 1 THEN 'a' ELSE 'b' END FROM users;",
        "SELECT \n    CASE\n        WHEN x = 1 THEN 'a'\n        WHEN x = 2 THEN 'b'\n        ELSE 'c'\n    END;",
        "SELECT CASE WHEN x IS NULL THEN NULL ELSE CASE WHEN y = 1 THEN true ELSE false END END FROM users;",
    ]

    def _find_case_blocks(self, tokens: List[dict]) -> List[dict]:
        n = len(tokens)
        case_stack = []
        blocks = []
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD":
                val_upper = tok["value"].upper()
                if val_upper == "CASE":
                    case_stack.append(i)
                elif val_upper == "END":
                    if case_stack:
                        start_idx = case_stack.pop()
                        blocks.append({
                            "start_idx": start_idx,
                            "end_idx": i,
                            "case_tok": tokens[start_idx],
                            "end_tok": tok
                        })
        return blocks

    def _find_violations(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        line_max_len = self.get_config_value(
            rule_config,
            "max_length",
            default_value=120,
            fallbacks=[(LineLengthRule, "max_length")]
        )
        case_max_len = self.get_config_value(
            rule_config,
            "max_line_length",
            default_value=110,
            fallbacks=[(CaseWhenWrapRule, "max_line_length")],
        )
        max_len = min(line_max_len, case_max_len)
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        blocks = self._find_case_blocks(tokens)
        violations = []
        
        # Resolve base_indent
        base_indent_opt = self.get_config_value(
            rule_config,
            "base_indent",
            default_value=0,
            fallbacks=[(IndentRule, "base_indent")]
        )
        indent_size = 4
        all_configs = rule_config.get("_all_configs", {})
        lang = rule_config.get("_lang")
        indent_config = all_configs.get(f"{lang}:IR-indent", all_configs.get("IR-indent", {}))
        if isinstance(indent_config, dict):
            indent_size = indent_config.get("indent_size", 4)
            
        if isinstance(base_indent_opt, str):
            base_indent_spaces = len(base_indent_opt.replace("\t", " " * indent_size))
        elif isinstance(base_indent_opt, int):
            base_indent_spaces = base_indent_opt
        else:
            base_indent_spaces = 0
        if "original_xml" in rule_config:
            # MyBatis line limits apply to the physical XML line, matching
            # IR-line-length rather than discounting the statement indent.
            base_indent_spaces = 0
            
        for block in blocks:
            start_idx = block["start_idx"]
            end_idx = block["end_idx"]
            case_tok = block["case_tok"]
            end_tok = block["end_tok"]
            if any(
                token["type"] == "STRING" and "\n" in token["value"]
                for token in tokens[start_idx:end_idx + 1]
            ):
                # Collapsing or rebuilding the CASE would normalize bytes
                # inside a dynamic SQL string literal. Its contents are data,
                # not layout owned by this rule.
                continue
            if any(
                token["type"] == "SEMI"
                for token in tokens[start_idx:end_idx + 1]
            ):
                # A CASE containing complete statements is a procedural
                # PL/pgSQL control-flow block, not a scalar SQL expression.
                # Its THEN bodies belong to the nested statement rules.
                continue
            effective_max_len = max_len
            has_additive_expression = any(
                token["type"] == "OPERATOR"
                and token["value"] in {"+", "||"}
                for token in tokens[start_idx:end_idx + 1]
            )
            if (
                has_additive_expression
                and case_tok["line"] != end_tok["line"]
            ):
                # Additive and WHEN/THEN rules own line breaks inside an
                # already-multiline CASE. Rebuilding the whole block would
                # compact their stricter expression layout on the next pass.
                continue
            if has_additive_expression:
                from mir.rules.sql.additive_wrap import AdditiveWrapRule

                additive_max_len = self.get_config_value(
                    rule_config,
                    "additive_max_line_length",
                    default_value=100,
                    fallbacks=[(AdditiveWrapRule, "max_line_length")],
                )
                effective_max_len = min(
                    effective_max_len, additive_max_len
                )
            effective_base_indent = (
                0 if has_additive_expression else base_indent_spaces
            )
            
            original_text = content[case_tok["start"]:end_tok["end"]]
            
            base_depth = depths[start_idx]
            if any(
                nested["start_idx"] > start_idx
                and nested["end_idx"] < end_idx
                for nested in blocks
            ):
                # Rebuilding an outer block must not reinterpret a nested
                # CASE's WHEN/THEN/ELSE tokens as arms of the outer block.
                # The nested block is discovered independently and may still
                # be formatted when its own structure is safe.
                continue
            when_count = 0
            has_else = False
            
            for idx in range(start_idx, end_idx + 1):
                t = tokens[idx]
                d = depths[idx]
                if d == base_depth and t["type"] == "KEYWORD":
                    val_upper = t["value"].upper()
                    if val_upper == "WHEN":
                        when_count += 1
                    elif val_upper == "ELSE":
                        has_else = True
                        
            line_start = content.rfind("\n", 0, case_tok["start"]) + 1
            line_prefix = content[line_start:case_tok["start"]]
            line_end = content.find("\n", end_tok["end"])
            if line_end == -1:
                line_end = len(content)
            line_suffix = content[end_tok["end"]:line_end]
            # Simple inline allows exactly one WHEN condition and optional ELSE
            is_simple_inline = (
                case_tok["line"] == end_tok["line"]
                and when_count == 1
                and (
                    source_text_length(
                        line_prefix + original_text.strip() + line_suffix,
                        rule_config,
                    )
                    - effective_base_indent
                ) <= effective_max_len
            )
            
            if is_simple_inline:
                continue

            compact_text = " ".join(original_text.split())
            can_compact_multiline = (
                case_tok["line"] != end_tok["line"]
                and when_count == 1
                and not has_additive_expression
                and not any(
                    token["type"] in {"COMMENT", "COMMA"}
                    for token in tokens[start_idx:end_idx + 1]
                )
                and (
                    source_text_length(
                        line_prefix + compact_text + line_suffix,
                        rule_config,
                    )
                    - effective_base_indent
                ) <= effective_max_len
            )
            if can_compact_multiline:
                violations.append({
                    "case_tok": case_tok,
                    "end_tok": end_tok,
                    "replacement": compact_text,
                })
                continue
                
            select_indent = ""
            for char in line_prefix:
                if char in (" ", "\t"):
                    select_indent += char
                else:
                    break
                    
            prefix_body = line_prefix.strip()
            is_additive_continuation = prefix_body in {"+", "-", "*", "/", "||"}
            follows_inline_operator = bool(
                re.search(r"(?:\+|-|\*|/|\|\|)\s*$", prefix_body)
            )
            is_inline = prefix_body != "" and not is_additive_continuation
            if is_inline and not follows_inline_operator:
                case_indent = select_indent + "    "
            else:
                case_indent = select_indent
                
            inner_tokens = tokens[start_idx:end_idx + 1]
            
            parts = []
            current_keyword = None
            current_start = None
            
            for idx, tok in enumerate(inner_tokens):
                d = depths[start_idx + idx]
                if d == base_depth and tok["type"] == "KEYWORD":
                    val_upper = tok["value"].upper()
                    if val_upper in ("CASE", "WHEN", "THEN", "ELSE", "END"):
                        if current_keyword:
                            parts.append((current_keyword, current_start, start_idx + idx))
                        current_keyword = tok
                        current_start = start_idx + idx + 1
                        
            needs_fix = False
            rebuilt_parts = []
            
            if is_inline and not follows_inline_operator:
                rebuilt_parts.append("\n" + case_indent + "CASE")
                needs_fix = True
            else:
                rebuilt_parts.append("CASE")

            if len(parts) > 0 and parts[0][0]["value"].upper() == "CASE":
                case_tokens = tokens[parts[0][1]:parts[0][2]]
                case_extra = "".join([t["value"] for t in case_tokens]).strip()
                if case_extra:
                    for line in case_extra.splitlines():
                        if line.strip():
                            rebuilt_parts.append(f"\n{case_indent}    {line.strip()}")
                
            i_idx = 0
            while i_idx < len(parts):
                kw_tok, start_c, end_c = parts[i_idx]
                val_upper = kw_tok["value"].upper()
                
                if val_upper == "WHEN":
                    then_part = None
                    if i_idx + 1 < len(parts) and parts[i_idx + 1][0]["value"].upper() == "THEN":
                        then_part = parts[i_idx + 1]
                        
                    if then_part:
                        then_keyword_idx = then_part[1] - 1
                        cond_tokens = tokens[start_c:then_keyword_idx]
                        
                        res_tokens = tokens[then_part[1]:then_part[2]]
                        res_text = "".join([t["value"] for t in res_tokens]).strip()
                        
                        # Split condition tokens on boolean AND/OR at depth 0;
                        # BETWEEN's delimiter AND belongs to the same condition.
                        cond_parts = []
                        current_part = []
                        cond_depths = get_token_depths(cond_tokens)
                        boolean_indices = set(find_boolean_operator_indices(
                            cond_tokens, cond_depths, 0
                        ))
                        for cond_index, t_c in enumerate(cond_tokens):
                            if cond_index in boolean_indices:
                                if current_part:
                                    cond_parts.append(current_part)
                                current_part = [t_c]
                            else:
                                current_part.append(t_c)
                        if current_part:
                            cond_parts.append(current_part)
                            
                        cond_strs = []
                        condition_has_subquery = any(
                            token["type"] == "KEYWORD"
                            and token["value"].upper() == "SELECT"
                            for token in cond_tokens
                        )
                        for part in cond_parts:
                            part_str = "".join([t["value"] for t in part]).strip()
                            if "\n" in part_str and not condition_has_subquery:
                                condition_fragments = [
                                    line.rstrip()
                                    for line in part_str.splitlines()
                                    if line.strip()
                                ]
                                continuation_indents = [
                                    len(line) - len(line.lstrip(" \t"))
                                    for line in condition_fragments[1:]
                                ]
                                common_indent = (
                                    min(continuation_indents)
                                    if continuation_indents
                                    else 0
                                )
                                part_str = condition_fragments[0].strip()
                                normalized_lines = []
                                previous_relative_indent = 0
                                previous_starts_with_operator = False
                                for line in condition_fragments[1:]:
                                    relative_indent = max(
                                        0,
                                        len(line)
                                        - len(line.lstrip(" \t"))
                                        - common_indent,
                                    )
                                    body = line.lstrip(" \t")
                                    starts_with_operator = bool(
                                        re.match(r"(?:\+|-|\*|/|\|\|)\s", body)
                                    )
                                    if starts_with_operator:
                                        operator_indent = (
                                            previous_relative_indent
                                            if previous_starts_with_operator
                                            else previous_relative_indent + 4
                                        )
                                        relative_indent = max(
                                            relative_indent, operator_indent
                                        )
                                    normalized_lines.append(
                                        "\n"
                                        + case_indent
                                        + "        "
                                        + " " * relative_indent
                                        + body
                                    )
                                    previous_relative_indent = relative_indent
                                    previous_starts_with_operator = (
                                        starts_with_operator
                                    )
                                part_str += "".join(normalized_lines)
                            elif "\n" not in part_str:
                                part_str = re.sub(r"\s+", " ", part_str)
                            cond_strs.append(part_str)
                            
                        compact_condition = " ".join(cond_strs)
                        condition_line = (
                            f"{case_indent}    WHEN {compact_condition}"
                        )
                        inline_arm = f"{condition_line} THEN {res_text}"
                        inline_arm_for_length = (
                            f"{condition_line} THEN "
                            + re.sub(r"\s+", " ", res_text)
                        )
                        has_additive_condition_break = (
                            any(
                                token["type"] == "WHITESPACE"
                                and "\n" in token["value"]
                                for token in cond_tokens
                            )
                            and any(
                                token["type"] == "OPERATOR"
                                and token["value"] in {"+", "||"}
                                for token in cond_tokens
                            )
                        )

                        if has_additive_condition_break:
                            condition_lines = [
                                line.strip()
                                for line in compact_condition.splitlines()
                                if line.strip()
                            ]
                            line_text = (
                                f"\n{case_indent}    WHEN "
                                + condition_lines[0]
                                + "".join(
                                    f"\n{case_indent}        {line}"
                                    for line in condition_lines[1:]
                                )
                                + f"\n{case_indent}        THEN {res_text}"
                            )
                        elif source_text_length(
                            inline_arm_for_length, rule_config
                        ) > effective_max_len:
                            if source_text_length(
                                condition_line, rule_config
                            ) <= effective_max_len:
                                first_line = f"\n{condition_line}"
                                remaining_conditions = []
                            else:
                                first_line = f"\n{case_indent}    WHEN {cond_strs[0]}"
                                remaining_conditions = cond_strs[1:]
                            subsequent_lines = []
                            for cs in remaining_conditions:
                                subsequent_lines.append(f"\n{case_indent}        {cs}")
                            then_line = f"\n{case_indent}        THEN {res_text}"
                            line_text = first_line + "".join(subsequent_lines) + then_line
                        else:
                            line_text = f"\n{inline_arm}"
                            
                        rebuilt_parts.append(line_text)
                        
                        kw_token_idx = tokens.index(kw_tok)
                        ws_tok = None
                        if kw_token_idx - 1 >= 0 and tokens[kw_token_idx - 1]["type"] == "WHITESPACE":
                            ws_tok = tokens[kw_token_idx - 1]
                        
                        # Re-calculate expectations: for multi-line conditions, original spaces might span multiple lines.
                        # We trigger format correction if original text didn't match the new formatted layout.
                        orig_sub_block = content[kw_tok["start"]:tokens[then_part[2]]["start"]]
                        formatted_sub_block = line_text.lstrip("\n")
                        if orig_sub_block.strip() != formatted_sub_block.strip():
                            needs_fix = True
                            
                        i_idx += 2
                        continue
                elif val_upper == "ELSE":
                    else_tokens = tokens[start_c:end_c]
                    else_text = "".join([t["value"] for t in else_tokens]).strip()
                    preserve_additive_break = (
                        "\n" in else_text
                        and any(
                            token["type"] == "OPERATOR"
                            and token["value"] in {"+", "||"}
                            for token in else_tokens
                        )
                    )
                    if preserve_additive_break:
                        else_lines = [
                            line.strip()
                            for line in else_text.splitlines()
                            if line.strip()
                        ]
                        line_text = (
                            f"\n{case_indent}    ELSE {else_lines[0]}"
                            + "".join(
                                f"\n{case_indent}        {line}"
                                for line in else_lines[1:]
                            )
                        )
                    else:
                        else_text = " ".join(else_text.split())
                        line_text = f"\n{case_indent}    ELSE {else_text}"
                    rebuilt_parts.append(line_text)
                    
                    kw_token_idx = tokens.index(kw_tok)
                    ws_tok = None
                    if kw_token_idx - 1 >= 0 and tokens[kw_token_idx - 1]["type"] == "WHITESPACE":
                        ws_tok = tokens[kw_token_idx - 1]
                    expected_ws = f"\n{case_indent}    "
                    if not ws_tok or ws_tok["value"] != expected_ws:
                        needs_fix = True
                    original_else = content[kw_tok["start"]:tokens[end_c]["start"]]
                    if original_else.strip() != line_text.strip():
                        needs_fix = True
                        
                i_idx += 1
                
            rebuilt_parts.append(f"\n{case_indent}END")
            
            end_token_idx = tokens.index(end_tok)
            ws_tok = None
            if end_token_idx - 1 >= 0 and tokens[end_token_idx - 1]["type"] == "WHITESPACE":
                ws_tok = tokens[end_token_idx - 1]
            expected_ws = f"\n{case_indent}"
            if not ws_tok or ws_tok["value"] != expected_ws:
                needs_fix = True
                
            if needs_fix:
                violations.append({
                    "case_tok": case_tok,
                    "end_tok": end_tok,
                    "replacement": "".join(rebuilt_parts)
                })
                
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        
        for item in offending:
            tok = item["case_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="CASE statement should be formatted with WHEN/THEN on separate lines.",
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
            edits.append((item["case_tok"]["start"], item["end_tok"]["end"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
