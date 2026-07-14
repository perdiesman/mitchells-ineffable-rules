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
                is_comment = line.lstrip().startswith("--")
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=idx,
                        message=f"Line exceeds maximum length of {max_length} characters (actual effective length: {effective_len}, total length: {len(line)}).",
                        offending_lines=[line],
                        is_fixable=is_comment
                    )
                )
                
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        lines = content.splitlines()
        fixed_lines = []
        for line in lines:
            if line.lstrip().startswith("--"):
                fixed_lines.extend(wrap_comment_line(line, max_length))
            else:
                fixed_lines.append(line)
                
        return "\n".join(fixed_lines) + ("\n" if content.endswith("\n") else "")
