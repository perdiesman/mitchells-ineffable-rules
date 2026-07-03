from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren, get_token_depths
from mir.rules.sql.indent import IndentRule

class SubqueryCompactRule(BaseRule):
    rule_id = "IR-subquery-compact"
    description = "Multiline subquery sources inside FROM or JOIN clauses should be compacted to a single line if they fit within 140 characters."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM (\n    SELECT a FROM t\n) sub;",
            "correct": "SELECT * FROM (SELECT a FROM t) sub;"
        }
    ]
    additional_validations = [
        'SELECT * FROM (\n    SELECT a FROM t -- keep comments\n) sub;'
    ]

    def _compact_tokens(self, tokens: List[dict]) -> str:
        parts = []
        n = len(tokens)
        
        for idx, t in enumerate(tokens):
            if t["type"] == "WHITESPACE":
                continue
                
            val = t["value"]
            if t["type"] in ("COMMA", "PAREN") and val == ")":
                if parts and parts[-1] == " ":
                    parts.pop()
                    
            parts.append(val)
            
            if not (t["type"] == "PAREN" and val == "(") and not t["type"] == "DOT":
                next_t = None
                for n_idx in range(idx + 1, n):
                    if tokens[n_idx]["type"] != "WHITESPACE":
                        next_t = tokens[n_idx]
                        break
                if next_t and next_t["value"] not in (",", ")", "."):
                    parts.append(" ")
                    
        return "".join(parts).strip()

    def _find_violations(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
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
            
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() in ("FROM", "JOIN"):
                outer_depth = depths[i]
                
                next_paren_idx = None
                for idx in range(i + 1, n):
                    if tokens[idx]["type"] == "WHITESPACE":
                        continue
                    if tokens[idx]["type"] == "PAREN" and tokens[idx]["value"] == "(":
                        next_paren_idx = idx
                    break
                    
                if next_paren_idx is not None:
                    close_idx = find_matching_paren(tokens, next_paren_idx)
                    if close_idx is None:
                        continue
                        
                    paren_tok = tokens[next_paren_idx]
                    close_tok = tokens[close_idx]
                    
                    if paren_tok["line"] != close_tok["line"]:
                        sub_tokens = tokens[next_paren_idx + 1:close_idx]
                        has_comments = any(t["type"] == "COMMENT" for t in sub_tokens)
                        if has_comments:
                            continue
                            
                        compacted_inner = self._compact_tokens(sub_tokens)
                        compacted_full = f"({compacted_inner})"
                        
                        line_start = content.rfind("\n", 0, paren_tok["start"]) + 1
                        line_prefix = content[line_start:paren_tok["start"]]
                        effective_prefix_len = max(0, len(line_prefix) - base_indent_spaces)
                        
                        if effective_prefix_len + len(compacted_full) <= 140:
                            violations.append({
                                "open_tok": paren_tok,
                                "close_tok": close_tok,
                                "replacement": compacted_full
                            })
                            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        
        for item in offending:
            tok = item["open_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="Multiline subquery source inside FROM/JOIN should be compacted to a single line.",
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
            edits.append((item["open_tok"]["start"], item["close_tok"]["end"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
