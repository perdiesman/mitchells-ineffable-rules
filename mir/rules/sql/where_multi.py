from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import (
    find_between_delimiter_indices,
    find_boolean_operator_indices,
    get_token_depths,
    tokenize_sql,
)

class WhereMultiRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-where-multi"
    description = "Keep a multi-condition WHERE clause inline when it fits; otherwise put each condition on its own indented line."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT id FROM users WHERE some_long_column_identifier_active = true AND another_long_column_identifier_type = 'admin' OR age_greater_than_limit > 21;",
            "correct": "SELECT id FROM users WHERE\n    some_long_column_identifier_active = true\n    AND another_long_column_identifier_type = 'admin'\n    OR age_greater_than_limit > 21;"
        },
        {
            "violating": "SELECT item_id FROM sample_item WHERE recorded_at BETWEEN :start\n    AND :end AND owning_organization_identifier = :owning_organization_identifier AND processing_status = :processing_status;",
            "correct": "SELECT item_id FROM sample_item WHERE\n    recorded_at BETWEEN :start AND :end\n    AND owning_organization_identifier = :owning_organization_identifier\n    AND processing_status = :processing_status;"
        }
    ]
    additional_validations = [
        "SELECT id FROM users WHERE active = true;",
        "SELECT id FROM users WHERE active = true AND retired = false;",
        "SELECT id FROM users WHERE created_at BETWEEN :start AND :end;",
    ]

    def _find_violations(self, content: str, rule_config: Dict[str, Any] = None) -> List[dict]:
        if rule_config is None:
            rule_config = {}
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        trellis_ranges = []
        mybatis_dynamic_offsets = rule_config.get("mybatis_dynamic_offsets", set())
        if rule_config.get("_template_dialect") == "trellis":
            from mir.rules.sql.trellis_utils import analyze_trellis

            _, _, trellis_ranges = analyze_trellis(content)

        def is_trellis_controlled(token: dict) -> bool:
            return any(start < token["line"] < end for start, end in trellis_ranges)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "WHERE":
                outer_depth = depths[i]
                
                line_start = content.rfind("\n", 0, tok["start"]) + 1
                line_prefix = content[line_start:tok["start"]]
                where_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        where_indent += char
                    else:
                        break

                base_indent = rule_config.get("base_indent")
                if (
                    "mybatis_dynamic_offsets" in rule_config
                    and isinstance(base_indent, str)
                ):
                    where_indent = base_indent

                expected_indent = where_indent + "    "
                
                clause_end = n
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if d < outer_depth:
                        clause_end = idx
                        break
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "GROUP", "ORDER", "LIMIT", "HAVING", "OFFSET", "RETURNING",
                            "UNION", "INTERSECT", "EXCEPT"
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
                boolean_indices = [
                    index for index in boolean_indices if not is_trellis_controlled(tokens[index])
                ]
                dynamic_boolean_indices = {
                    index
                    for index in boolean_indices
                    if tokens[index]["start"] in mybatis_dynamic_offsets
                }
                for delimiter_idx in find_between_delimiter_indices(
                    tokens, depths, outer_depth, i + 1, clause_end
                ):
                    delimiter = tokens[delimiter_idx]
                    if is_trellis_controlled(delimiter):
                        continue
                    ws_before = (
                        tokens[delimiter_idx - 1]
                        if delimiter_idx and tokens[delimiter_idx - 1]["type"] == "WHITESPACE"
                        else None
                    )
                    if not ws_before or ws_before["value"] != " ":
                        violations.append({
                            "token": delimiter,
                            "ws_start": ws_before["start"] if ws_before else delimiter["start"],
                            "ws_end": delimiter["start"],
                            "replacement": " ",
                        })
                has_multi = bool(boolean_indices)
                        
                if has_multi:
                    where_clause_tokens = tokens[i : clause_end]
                    where_clause_single = "".join(
                        " " if t["type"] == "WHITESPACE" else t["value"]
                        for t in where_clause_tokens
                    )
                    estimated_line_len = len(where_indent) + len(where_clause_single)
                    
                    from mir.rules.sql.line_length import LineLengthRule
                    max_len = self.get_config_value(rule_config, "max_line_length", 100, fallbacks=[(LineLengthRule, "max_length")])
                    
                    if estimated_line_len <= max_len and not dynamic_boolean_indices:
                        # A short predicate has one canonical compact form. Only
                        # edit whitespace tokens so strings and parameters stay
                        # byte-for-byte intact, and leave the separator before
                        # the following clause alone.
                        if any(t["type"] == "COMMENT" for t in clause_tokens):
                            continue
                        last_active_idx = None
                        for idx in range(clause_end - 1, i, -1):
                            if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                                last_active_idx = idx
                                break
                        if last_active_idx is not None:
                            for idx in range(i + 1, last_active_idx):
                                t = tokens[idx]
                                if t["type"] == "WHITESPACE" and t["value"] != " ":
                                    violations.append({
                                        "token": t,
                                        "ws_start": t["start"],
                                        "ws_end": t["end"],
                                        "replacement": " ",
                                    })
                        continue
                    # 1. Format the first condition after WHERE onto its own line
                    first_cond_idx = None
                    for idx in range(i + 1, clause_end):
                        if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                            first_cond_idx = idx
                            break
                            
                    if first_cond_idx is not None:
                        fc_tok = tokens[first_cond_idx]
                        ws_before = None
                        if first_cond_idx - 1 >= 0 and tokens[first_cond_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[first_cond_idx - 1]
                            
                        first_condition_indent = expected_indent
                        if fc_tok["start"] in mybatis_dynamic_offsets:
                            first_condition_indent += "    "
                        expected_replacement = "\n" + first_condition_indent
                        if not ws_before or ws_before["value"] != expected_replacement:
                            violations.append({
                                "token": fc_tok,
                                "ws_start": ws_before["start"] if ws_before else fc_tok["start"],
                                "ws_end": fc_tok["start"],
                                "replacement": expected_replacement
                            })
                            
                    # 2. Format subsequent AND/OR keywords onto their own lines
                    for actual_idx in boolean_indices:
                        t = tokens[actual_idx]
                        ws_tok = None
                        if actual_idx - 1 >= 0 and tokens[actual_idx - 1]["type"] == "WHITESPACE":
                            ws_tok = tokens[actual_idx - 1]

                        boolean_indent = expected_indent
                        if actual_idx in dynamic_boolean_indices:
                            boolean_indent += "    "
                        expected_replacement = "\n" + boolean_indent
                        whitespace_matches = bool(
                            ws_tok
                            and (
                                ws_tok["value"] == expected_replacement
                                or (
                                    actual_idx in dynamic_boolean_indices
                                    and ws_tok["value"].endswith(expected_replacement)
                                )
                            )
                        )
                        if not whitespace_matches:
                            violations.append({
                                "token": t,
                                "ws_start": ws_tok["start"] if ws_tok else t["start"],
                                "ws_end": t["start"],
                                "replacement": expected_replacement
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
                    message="Logical check operators (AND/OR) in multi-condition WHERE clauses must start on their own lines with 4 spaces of indentation.",
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
            
        ordered_edits = sorted(edits.items(), key=lambda item: item[0][0], reverse=True)
        chars = list(content)
        for (start, end), new_text in ordered_edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
