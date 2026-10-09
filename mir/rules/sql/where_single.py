from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import (
    find_boolean_operator_indices,
    get_token_depths,
    source_text_length,
    tokenize_sql,
)
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.line_length import LineLengthRule

class WhereSingleRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-where-single"
    description = (
        "Keep a single WHERE condition inline when it fits; otherwise place the "
        "condition on the next indented line."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {"max_line_length": 120, "indent_size": 4}
    config_options = {
        "max_line_length": {
            "default": 120,
            "description": "Maximum length for an inline WHERE clause.",
            "fallback": "IR-line-length:max_length",
        },
        "indent_size": {
            "default": 4,
            "description": "Spaces used for a wrapped WHERE condition.",
            "fallback": "IR-indent:indent_size",
        },
    }
    
    examples = [
        {
            "violating": "SELECT id FROM users\nWHERE\n    active = true;",
            "correct": "SELECT id FROM users\nWHERE active = true;"
        },
        {
            "violating": "SELECT item_id FROM sample_item WHERE recorded_timestamp_for_requested_interval BETWEEN timezone('utc', :requested_interval_start) AND timezone('utc', :requested_interval_end);",
            "correct": "SELECT item_id FROM sample_item\nWHERE\n    recorded_timestamp_for_requested_interval BETWEEN timezone('utc', :requested_interval_start) AND timezone('utc', :requested_interval_end);"
        }
    ]
    additional_validations = [
        "SELECT id FROM users WHERE active = true;",
        "SELECT id FROM users WHERE active = true AND age > 21;", # Multi-condition is skipped here
        "SELECT id FROM users WHERE created_at BETWEEN :start AND :end;",
    ]

    def _find_violations(
        self, content: str, rule_config: Dict[str, Any] | None = None
    ) -> List[dict]:
        rule_config = rule_config or {}
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "WHERE":
                outer_depth = depths[i]
                
                # Find end of WHERE clause
                clause_end = n
                for idx in range(i + 1, n):
                    t = tokens[idx]
                    d = depths[idx]
                    if d < outer_depth:
                        clause_end = idx
                        break
                    if d == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in (
                            "GROUP", "ORDER", "LIMIT", "HAVING", "OFFSET", "UNION", "INTERSECT", "EXCEPT"
                        ):
                            clause_end = idx
                            break
                        if t["type"] == "SEMI":
                            clause_end = idx
                            break
                            
                clause_tokens = tokens[i + 1:clause_end]
                clause_depths = depths[i + 1:clause_end]
                
                # Check for AND/OR at depth outer_depth
                has_logical = bool(find_boolean_operator_indices(
                    tokens, depths, outer_depth, i + 1, clause_end
                ))
                first_cond_tok = None
                first_cond_idx = None
                
                for idx, (t, d) in enumerate(
                    zip(clause_tokens, clause_depths), start=i + 1
                ):
                    if d == outer_depth:
                        if t["type"] != "WHITESPACE" and first_cond_tok is None:
                            first_cond_tok = t
                            first_cond_idx = idx
                            
                if first_cond_tok and not has_logical:
                    if any(token["type"] == "COMMENT" for token in clause_tokens):
                        continue
                    clause_single = "".join(
                        " " if token["type"] == "WHITESPACE" else token["value"]
                        for token in tokens[i:clause_end]
                    ).strip()
                    line_start = content.rfind("\n", 0, tok["start"]) + 1
                    where_indent = content[line_start:tok["start"]]
                    where_indent = where_indent[: len(where_indent) - len(where_indent.lstrip())]
                    max_length = self.get_config_value(
                        rule_config,
                        "max_line_length",
                        120,
                        fallbacks=[(LineLengthRule, "max_length")],
                    )
                    indent_size = self.get_config_value(
                        rule_config,
                        "indent_size",
                        4,
                        fallbacks=[(IndentRule, "indent_size")],
                    )
                    should_wrap = (
                        source_text_length(where_indent + clause_single, rule_config)
                        > max_length
                    )
                    prefix_before_where = content[line_start:tok["start"]].rstrip()
                    if prefix_before_where.strip():
                        should_wrap = (
                            source_text_length(
                                prefix_before_where + " " + clause_single,
                                rule_config,
                            )
                            > max_length
                        )
                    expected = (
                        "\n" + where_indent + " " * indent_size
                        if should_wrap
                        else " "
                    )
                    whitespace = (
                        tokens[first_cond_idx - 1]
                        if first_cond_idx > i
                        and tokens[first_cond_idx - 1]["type"] == "WHITESPACE"
                        else None
                    )
                    actual = whitespace["value"] if whitespace else ""
                    if actual != expected:
                        item = {
                            "where_tok": tok,
                            "cond_tok": first_cond_tok,
                            "ws_start": whitespace["start"] if whitespace else tok["end"],
                            "ws_end": first_cond_tok["start"],
                            "replacement": expected,
                        }
                        if should_wrap and prefix_before_where.strip():
                            ws_before_where = (
                                tokens[i - 1]
                                if i > 0 and tokens[i - 1]["type"] == "WHITESPACE"
                                else None
                            )
                            item["pre_where_edit"] = (
                                ws_before_where["start"] if ws_before_where else tok["start"],
                                ws_before_where["end"] if ws_before_where else tok["start"],
                                "\n" + where_indent,
                            )
                        violations.append(item)
                        
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        
        for item in offending:
            tok = item["where_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Single WHERE condition should use the configured fit-or-wrap layout.",
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
            if item.get("pre_where_edit"):
                edits.append(item["pre_where_edit"])
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
