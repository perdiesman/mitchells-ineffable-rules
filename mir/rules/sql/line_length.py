from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class LineLengthRule(BaseRule):
    rule_id = "IR-line-length"
    description = "Lines must not exceed the configured maximum length."
    category = "general"
    is_fixable = "no"  # Line wrapping is complex and subjective, so it's not auto-fixable by default.
    default_config = {
        "max_length": 120
    }
    examples_violating = [
        "SELECT first_name, last_name, email, phone_number, mailing_address, date_of_birth, join_date, status, premium_member_flag FROM accounts_primary_table WHERE status = 'active';"
    ]
    examples_correct = [
        "SELECT\n    first_name,\n    last_name,\n    email\nFROM accounts_primary_table\nWHERE status = 'active';"
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        violations = []
        
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            if len(line) > max_length:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=idx,
                        message=f"Line exceeds maximum length of {max_length} characters (actual: {len(line)}).",
                        offending_lines=[line],
                        is_fixable=self.is_fixable
                    )
                )
                
        return violations
