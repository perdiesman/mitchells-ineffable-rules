from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.line_length import LineLengthRule

class CaseLayoutRule(BaseRule):
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
        "SELECT \n    CASE\n        WHEN x = 1 THEN 'a'\n        ELSE 'b'\n    END;"
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
        max_len = self.get_config_value(
            rule_config,
            "max_length",
            default_value=100,
            fallbacks=[(LineLengthRule, "max_length")]
        )
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
            
        for block in blocks:
            start_idx = block["start_idx"]
            end_idx = block["end_idx"]
            case_tok = block["case_tok"]
            end_tok = block["end_tok"]
            
            original_text = content[case_tok["start"]:end_tok["end"]]
            
            base_depth = depths[start_idx]
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
            effective_prefix_len = max(0, len(line_prefix) - base_indent_spaces)
            
            # Simple inline allows exactly one WHEN condition and optional ELSE
            is_simple_inline = (
                case_tok["line"] == end_tok["line"]
                and when_count == 1
                and (effective_prefix_len + len(original_text.strip())) <= 140
            )
            
            if is_simple_inline:
                continue
                
            select_indent = ""
            for char in line_prefix:
                if char in (" ", "\t"):
                    select_indent += char
                else:
                    break
                    
            is_inline = line_prefix.strip() != ""
            if is_inline:
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
            
            if is_inline:
                rebuilt_parts.append("\n" + case_indent + "CASE")
                needs_fix = True
            else:
                rebuilt_parts.append("CASE")
                
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
                        
                        # Split condition tokens on AND/OR at depth 0
                        import re
                        cond_parts = []
                        current_part = []
                        depth = 0
                        for t_c in cond_tokens:
                            if t_c["type"] == "PAREN" and t_c["value"] == "(":
                                depth += 1
                            elif t_c["type"] == "PAREN" and t_c["value"] == ")":
                                depth -= 1
                                
                            if depth == 0 and t_c["type"] == "KEYWORD" and t_c["value"].upper() in ("AND", "OR"):
                                if current_part:
                                    cond_parts.append(current_part)
                                current_part = [t_c]
                            else:
                                current_part.append(t_c)
                        if current_part:
                            cond_parts.append(current_part)
                            
                        cond_strs = []
                        for part in cond_parts:
                            part_str = "".join([t["value"] for t in part]).strip()
                            if "\n" not in part_str:
                                part_str = re.sub(r"\s+", " ", part_str)
                            cond_strs.append(part_str)
                            
                        is_multiline = len(cond_strs) > 1 or len(f"{case_indent}    WHEN {cond_strs[0]} THEN {res_text}") > max_len
                        
                        if is_multiline:
                            first_line = f"\n{case_indent}    WHEN {cond_strs[0]}"
                            subsequent_lines = []
                            for cs in cond_strs[1:]:
                                subsequent_lines.append(f"\n{case_indent}        {cs}")
                            then_line = f"\n{case_indent}        THEN {res_text}"
                            line_text = first_line + "".join(subsequent_lines) + then_line
                        else:
                            line_text = f"\n{case_indent}    WHEN {cond_strs[0]} THEN {res_text}"
                            
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
                    line_text = f"\n{case_indent}    ELSE {else_text}"
                    rebuilt_parts.append(line_text)
                    
                    kw_token_idx = tokens.index(kw_tok)
                    ws_tok = None
                    if kw_token_idx - 1 >= 0 and tokens[kw_token_idx - 1]["type"] == "WHITESPACE":
                        ws_tok = tokens[kw_token_idx - 1]
                    expected_ws = f"\n{case_indent}    "
                    if not ws_tok or ws_tok["value"] != expected_ws:
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
