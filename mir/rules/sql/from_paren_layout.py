from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths, find_matching_paren

class FromParenLayoutRule(BaseRule):
    rule_id = "IR-from-paren-layout"
    description = "Parenthesized column alias lists in FROM/JOIN clauses should format entries one per line if the line exceeds max length."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "max_line_length": 140
    }
    config_options = {
        "max_line_length": {
            "default": 140,
            "description": "Line length threshold above which paren lists will be split.",
            "fallback": "IR-line-length:max_line_length"
        }
    }
    
    examples = [
        {
            "violating": "SELECT * FROM func() alias(col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11, col12, col13, col14, col15, col16, col17, col18);",
            "correct": "SELECT * FROM func() alias(\n    col1,\n    col2,\n    col3,\n    col4,\n    col5,\n    col6,\n    col7,\n    col8,\n    col9,\n    col10,\n    col11,\n    col12,\n    col13,\n    col14,\n    col15,\n    col16,\n    col17,\n    col18\n);"
        }
    ]
    additional_validations = [
        "SELECT * FROM func() alias(col1, col2);"
    ]

    def _find_violations(self, content: str, max_len: int) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        # Calculate line lengths to quickly check which lines exceed max_len
        lines = content.splitlines()
        
        for i, tok in enumerate(tokens):
            # Check if this token starts a line exceeding max_len
            line_idx = tok["line"] - 1
            if line_idx >= len(lines) or len(lines[line_idx]) <= max_len:
                continue
                
            if tok["type"] == "PAREN" and tok["value"] == "(":
                # Must be inside FROM or JOIN clause
                in_from_or_join = False
                outer_depth = depths[i]
                for idx in range(i - 1, -1, -1):
                    t = tokens[idx]
                    if depths[idx] == outer_depth:
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("FROM", "JOIN"):
                            in_from_or_join = True
                            break
                        if t["type"] == "KEYWORD" and t["value"].upper() in ("SELECT", "WHERE", "GROUP", "ORDER", "LIMIT"):
                            break
                            
                if not in_from_or_join:
                    continue
                    
                # Must follow an identifier (the alias or function name)
                prev_active = None
                for idx in range(i - 1, -1, -1):
                    if tokens[idx]["type"] not in ("WHITESPACE", "COMMENT"):
                        prev_active = tokens[idx]
                        break
                        
                if not prev_active or prev_active["type"] not in ("IDENTIFIER", "KEYWORD"):
                    continue
                    
                close_idx = find_matching_paren(tokens, i)
                if close_idx is None:
                    continue
                    
                # Count commas at depth outer_depth + 1 inside
                inner_tokens = tokens[i + 1:close_idx]
                inner_depths = depths[i + 1:close_idx]
                has_commas = False
                for t, d in zip(inner_tokens, inner_depths):
                    if d == outer_depth + 1 and t["type"] == "COMMA":
                        has_commas = True
                        break
                        
                if not has_commas:
                    continue
                    
                # Check if it is already formatted (contains newlines)
                is_already_multiline = False
                for t in inner_tokens:
                    if t["type"] == "WHITESPACE" and "\n" in t["value"]:
                        is_already_multiline = True
                        break
                        
                if is_already_multiline:
                    continue
                    
                violations.append({
                    "open_tok": tok,
                    "close_tok": tokens[close_idx],
                    "inner_tokens": inner_tokens,
                    "inner_depths": inner_depths,
                    "base_depth": outer_depth
                })
                
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_len = rule_config.get("max_line_length", self.default_config["max_line_length"])
        # Resolve fallback from IR-line-length if configured
        if "max_line_length" not in rule_config and "IR-line-length" in rule_config:
            max_len = rule_config["IR-line-length"].get("max_line_length", max_len)
            
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, max_len)
        
        for item in offending:
            tok = item["open_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message=f"Parenthesized column alias list exceeds {max_len} characters and should be formatted with one column per line.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_len = rule_config.get("max_line_length", self.default_config["max_line_length"])
        if "max_line_length" not in rule_config and "IR-line-length" in rule_config:
            max_len = rule_config["IR-line-length"].get("max_line_length", max_len)
            
        offending = self._find_violations(content, max_len)
        if not offending:
            return content
            
        edits = []
        for item in offending:
            open_tok = item["open_tok"]
            close_tok = item["close_tok"]
            inner_tokens = item["inner_tokens"]
            inner_depths = item["inner_depths"]
            base_depth = item["base_depth"]
            
            # Find base indentation
            line_start = content.rfind("\n", 0, open_tok["start"]) + 1
            line_prefix = content[line_start:open_tok["start"]]
            base_indent = ""
            for char in line_prefix:
                if char in (" ", "\t"):
                    base_indent += char
                else:
                    break
                    
            content_indent = base_indent + "    "
            
            # Split inner tokens by comma at depth base_depth + 1
            cols = []
            current_col = []
            for t, d in zip(inner_tokens, inner_depths):
                if d == base_depth + 1 and t["type"] == "COMMA":
                    cols.append(current_col)
                    current_col = []
                else:
                    current_col.append(t)
            if current_col:
                cols.append(current_col)
                
            # Build new list text
            new_lines = []
            for idx, col in enumerate(cols):
                # Clean leading/trailing whitespace from col
                col_active = [t for t in col if t["type"] not in ("WHITESPACE", "COMMENT")]
                if not col_active:
                    continue
                start_pos = col_active[0]["start"] - col[0]["start"]
                # Reconstruct string
                col_str = "".join([t["value"] for t in col]).strip()
                suffix = "," if idx < len(cols) - 1 else ""
                new_lines.append(content_indent + col_str + suffix)
                
            replacement = "\n" + "\n".join(new_lines) + "\n" + base_indent
            edits.append((open_tok["end"], close_tok["start"], replacement))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
