from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths, find_matching_paren

class ExpressionSplitRule(BaseRule):
    rule_id = "IR-expression-split"
    description = "Long lines should split on function/expression parentheses, and optionally on additive/logical operators if still too long."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "max_line_length": 100
    }
    config_options = {
        "max_line_length": {
            "default": 100,
            "description": "Line length threshold above which long expressions will be split."
        }
    }
    
    examples = [
        {
            "violating": "SELECT min(date_trunc('hour', start_time) + date_part('minutes', start_time)::int / 15 * '15 Minutes'::interval) AS start_time;",
            "correct": "SELECT min(\n    date_trunc('hour', start_time)\n    + date_part('minutes', start_time)::int / 15 * '15 Minutes'::interval\n) AS start_time;"
        }
    ]
    additional_validations = [
        "SELECT min(id) FROM users;"
    ]

    def _find_violations(self, content: str, max_len: int) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        # Calculate line lengths
        lines = content.splitlines()
        
        # We process line-by-line
        for line_no, line in enumerate(lines, start=1):
            if len(line) <= max_len:
                continue
                
            # Find the first open parenthesis ( on this line that is not preceded by another '('
            line_tokens = [tok for tok in tokens if tok["line"] == line_no]
            open_tok = None
            for tok in line_tokens:
                if tok["type"] == "PAREN" and tok["value"] == "(":
                    try:
                        idx = tokens.index(tok)
                        prev_active = None
                        for p_idx in range(idx - 1, -1, -1):
                            if tokens[p_idx]["type"] != "WHITESPACE":
                                prev_active = tokens[p_idx]
                                break
                        if prev_active and prev_active["type"] == "PAREN" and prev_active["value"] == "(":
                            continue
                    except ValueError:
                        pass
                    open_tok = tok
                    break
                    
            if not open_tok:
                continue
                
            # Find matching close parenthesis
            open_idx = tokens.index(open_tok)
            close_idx = find_matching_paren(tokens, open_idx)
            if close_idx is None:
                continue
                
            close_tok = tokens[close_idx]
            
            # Check if it is already multiline
            is_multiline = False
            for idx in range(open_idx + 1, close_idx):
                if "\n" in tokens[idx]["value"] if tokens[idx]["type"] == "WHITESPACE" else False:
                    is_multiline = True
                    break
                    
            if is_multiline:
                # If already multiline, check if any line inside exceeds max_len
                # and contains additive/logical operators that can be split
                has_long_inner = False
                for inner_l_no in range(open_tok["line"] + 1, close_tok["line"]):
                    if inner_l_no - 1 < len(lines) and len(lines[inner_l_no - 1]) > max_len:
                        has_long_inner = True
                        break
                if not has_long_inner:
                    continue
                    
            violations.append({
                "open_tok": open_tok,
                "close_tok": close_tok,
                "open_idx": open_idx,
                "close_idx": close_idx
            })
            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_len = rule_config.get("max_line_length", self.default_config["max_line_length"])
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, max_len)
        
        for item in offending:
            tok = item["open_tok"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message=f"Line exceeds {max_len} characters and can be split on parenthesis or operators.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_len = rule_config.get("max_line_length", self.default_config["max_line_length"])
        offending = self._find_violations(content, max_len)
        if not offending:
            return content
            
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        edits = []
        
        for item in offending:
            open_tok = item["open_tok"]
            close_tok = item["close_tok"]
            open_idx = item["open_idx"]
            close_idx = item["close_idx"]
            
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
            
            # 1. Format parenthesis boundaries
            # Check whitespace after open parenthesis
            ws_after = None
            if open_idx + 1 < len(tokens) and tokens[open_idx + 1]["type"] == "WHITESPACE":
                ws_after = tokens[open_idx + 1]
            # Check whitespace before close parenthesis
            ws_before = None
            if close_idx - 1 >= 0 and tokens[close_idx - 1]["type"] == "WHITESPACE":
                ws_before = tokens[close_idx - 1]
                
            open_replacement = "\n" + content_indent
            close_replacement = "\n" + base_indent
            
            # Apply boundary edits
            edits.append((ws_after["start"] if ws_after else open_tok["end"], ws_after["end"] if ws_after else open_tok["end"], open_replacement))
            edits.append((ws_before["start"] if ws_before else close_tok["start"], ws_before["end"] if ws_before else close_tok["start"], close_replacement))
            
            # 2. Check if inner expression should be split on operators
            # Find operators at base depth inside (depths[open_idx] + 1)
            base_depth = depths[open_idx] + 1
            inner_tokens = tokens[open_idx + 1:close_idx]
            inner_depths = depths[open_idx + 1:close_idx]
            
            # Check if the estimated split line length would exceed max_len
            # Estimate inner expression length
            inner_str = "".join([t["value"] for t in inner_tokens]).strip()
            if len(content_indent + inner_str) > max_len:
                for idx, (t, d) in enumerate(zip(inner_tokens, inner_depths)):
                    if d == base_depth:
                        # Split on operators + - || AND OR
                        is_split_operator = False
                        if t["type"] == "OPERATOR" and t["value"] in ("+", "-", "||"):
                            is_split_operator = True
                        elif t["type"] == "KEYWORD" and t["value"].upper() in ("AND", "OR"):
                            is_split_operator = True
                            
                        if is_split_operator:
                            actual_idx = open_idx + 1 + idx
                            # Check whitespace before this operator
                            op_ws_before = None
                            if actual_idx - 1 >= 0 and tokens[actual_idx - 1]["type"] == "WHITESPACE":
                                op_ws_before = tokens[actual_idx - 1]
                                
                            op_replacement = "\n" + content_indent
                            edits.append((op_ws_before["start"] if op_ws_before else t["start"], op_ws_before["end"] if op_ws_before else t["start"], op_replacement))
                            
        # Sort and apply edits in reverse order
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
