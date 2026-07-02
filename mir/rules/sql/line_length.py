from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.indent import IndentRule

class LineLengthRule(BaseRule):
    rule_id = "IR-line-length"
    description = "Lines must not exceed the configured maximum length."
    category = "general"
    is_fixable = "no"
    
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
            "violating": "SELECT first_name, last_name, email, phone_number, mailing_address, date_of_birth, join_date, status, premium_member_flag FROM accounts_primary_table WHERE status = 'active';",
            "correct": "SELECT\n    first_name,\n    last_name,\n    email\nFROM accounts_primary_table\nWHERE status = 'active';"
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
                        is_fixable=self.is_fixable
                    )
                )
                
        return violations
