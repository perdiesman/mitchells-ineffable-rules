from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.indent import IndentRule

def wrap_comment_line(line: str, max_length: int) -> List[str]:
    # Find leading indentation
    indent = line[:len(line) - len(line.lstrip())]
    stripped = line.lstrip()
    
    if not stripped.startswith("--"):
        return [line]
        
    if stripped.startswith("-- "):
        comment_prefix = "-- "
        comment_text = stripped[3:]
    else:
        comment_prefix = "--"
        comment_text = stripped[2:]
        
    prefix = indent + comment_prefix
    
    if len(line) <= max_length:
        return [line]
        
    max_text_len = max(1, max_length - len(prefix))
    
    words = comment_text.split(" ")
    wrapped_lines = []
    current_line_words = []
    current_line_len = 0
    
    for word in words:
        word_len = len(word)
        space_len = 1 if current_line_words else 0
        if current_line_len + space_len + word_len > max_text_len:
            if current_line_words:
                wrapped_lines.append(prefix + " ".join(current_line_words))
                current_line_words = [word]
                current_line_len = word_len
            else:
                wrapped_lines.append(prefix + word)
                current_line_words = []
                current_line_len = 0
        else:
            current_line_words.append(word)
            current_line_len += space_len + word_len
            
    if current_line_words:
        wrapped_lines.append(prefix + " ".join(current_line_words))
        
    return wrapped_lines

class LineLengthRule(BaseRule):
    rule_id = "IR-line-length"
    description = "Lines must not exceed the configured maximum length."
    category = "general"
    is_fixable = "sometimes"
    exclude_recursive = True
    
    default_config = {
        "max_length": 120,
        "base_indent": 0
    }
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length limit."
        },
        "base_indent": {
            "default": 0,
            "description": "Base indentation offset (in spaces or leading space string) to subtract before checking line lengths.",
            "fallback": "IR-indent:base_indent"
        }
    }
    
    examples = [
        {
            "violating": "-- This is a very long comment line that exceeds the maximum line length limit of 120 characters to demonstrate how the comment wrapping works.",
            "correct": "-- This is a very long comment line that exceeds the maximum line length limit of 120 characters to demonstrate how the\n-- comment wrapping works."
        }
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        base_indent_opt = self.get_config_value(
            rule_config,
            "base_indent",
            default_value=0,
            fallbacks=[(IndentRule, "base_indent")]
        )
        # Handle string or integer base_indent
        if isinstance(base_indent_opt, str):
            # To get indent_size for normalizing tabs, look up IndentRule.indent_size default
            indent_size = 4
            all_configs = rule_config.get("_all_configs", {})
            lang = rule_config.get("_lang")
            indent_config = all_configs.get(f"{lang}:IR-indent", all_configs.get("IR-indent", {}))
            if isinstance(indent_config, dict):
                indent_size = indent_config.get("indent_size", 4)
            base_indent_spaces = len(base_indent_opt.replace("\t", " " * indent_size))
        elif isinstance(base_indent_opt, int):
            base_indent_spaces = base_indent_opt
        else:
            base_indent_spaces = 0
            
        violations = []
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            effective_len = len(line) - base_indent_spaces
            if effective_len > max_length:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=idx,
                        message=f"Line exceeds maximum length of {max_length} characters (actual effective length: {effective_len}, total length: {len(line)}).",
                        offending_lines=[line],
                        is_fixable=True
                    )
                )
                
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        
        # 1. Run function call splitting on SQL code lines
        from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren
        try:
            tokens = tokenize_sql(content)
            lines = content.splitlines()
            
            # Find all function calls
            all_calls = []
            for i, tok in enumerate(tokens):
                if tok["type"] in ("IDENTIFIER", "KEYWORD"):
                    next_act_idx = None
                    for j in range(i + 1, len(tokens)):
                        if tokens[j]["type"] not in ("WHITESPACE", "COMMENT"):
                            next_act_idx = j
                            break
                    if next_act_idx is not None and tokens[next_act_idx]["type"] == "PAREN" and tokens[next_act_idx]["value"] == "(":
                        open_idx = next_act_idx
                        close_idx = find_matching_paren(tokens, open_idx)
                        if close_idx is not None:
                            all_calls.append({
                                "start": tokens[open_idx]["start"],
                                "end": tokens[close_idx]["end"],
                                "open_idx": open_idx,
                                "close_idx": close_idx,
                                "name_token": tok
                            })
                            
            # Filter out nested calls
            outer_calls = []
            for i, call_a in enumerate(all_calls):
                is_nested = False
                for j, call_b in enumerate(all_calls):
                    if i != j:
                        if call_b["start"] <= call_a["start"] and call_a["end"] <= call_b["end"]:
                            is_nested = True
                            break
                if not is_nested:
                    outer_calls.append(call_a)
                    
            # Generate edits for long lines
            edits = []
            indent_size = 4
            all_configs = rule_config.get("_all_configs", {})
            lang = rule_config.get("_lang")
            indent_config = all_configs.get(f"{lang}:IR-indent", all_configs.get("IR-indent", {}))
            if isinstance(indent_config, dict):
                indent_size = indent_config.get("indent_size", 4)
                
            for call in outer_calls:
                line_idx = call["name_token"]["line"] - 1
                line = lines[line_idx] if line_idx < len(lines) else ""
                if len(line) > max_length:
                    # Parse arguments
                    args = []
                    current_arg = []
                    depth = 0
                    for k in range(call["open_idx"] + 1, call["close_idx"]):
                        t = tokens[k]
                        if t["type"] == "PAREN" and t["value"] == "(":
                            depth += 1
                            current_arg.append(t)
                        elif t["type"] == "PAREN" and t["value"] == ")":
                            depth -= 1
                            current_arg.append(t)
                        elif t["type"] == "COMMA" and depth == 0:
                            args.append(current_arg)
                            current_arg = []
                        else:
                            current_arg.append(t)
                    if current_arg or not args:
                        args.append(current_arg)
                        
                    arg_strings = []
                    for a_toks in args:
                        if a_toks:
                            s = a_toks[0]["start"]
                            e = a_toks[-1]["end"]
                            arg_strings.append(content[s:e].strip())
                    arg_strings = [s for s in arg_strings if s]
                    
                    if arg_strings:
                        indent = ""
                        for char in line:
                            if char in (" ", "\t"):
                                indent += char
                            else:
                                break
                        arg_indent = indent + " " * indent_size
                        
                        replacement = "(\n"
                        for idx, arg_str in enumerate(arg_strings):
                            comma = "," if idx < len(arg_strings) - 1 else ""
                            replacement += arg_indent + arg_str + comma + "\n"
                        replacement += indent + ")"
                        
                        edits.append((call["start"], call["end"], replacement))
                        
            if edits:
                chars = list(content)
                for s, e, rep in sorted(edits, key=lambda x: x[0], reverse=True):
                    chars[s:e] = list(rep)
                content = "".join(chars)
        except Exception:
            pass
            
        # 2. Wrap comment lines (original logic)
        lines = content.splitlines()
        fixed_lines = []
        for line in lines:
            if line.lstrip().startswith("--"):
                fixed_lines.extend(wrap_comment_line(line, max_length))
            else:
                fixed_lines.append(line)
                
        return "\n".join(fixed_lines) + ("\n" if content.endswith("\n") else "")
