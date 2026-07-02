from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class BlankLinesRule(BaseRule):
    rule_id = "IR-blank-lines"
    description = "Limit consecutive blank lines to a maximum of one."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users;\n\n\n\nSELECT * FROM roles;",
            "correct": "SELECT * FROM users;\n\nSELECT * FROM roles;"
        }
    ]
    additional_validations = [
        "SELECT * FROM users;\n\nSELECT * FROM roles;"
    ]

    def _check_and_find(self, content: str) -> List[int]:
        lines = content.splitlines()
        consecutive_blanks = 0
        violating_lines = []
        
        for idx, line in enumerate(lines):
            if line.strip() == "":
                consecutive_blanks += 1
                if consecutive_blanks > 1:
                    violating_lines.append(idx + 1)
            else:
                consecutive_blanks = 0
        return violating_lines

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        violating_line_numbers = self._check_and_find(content)
        
        for line_no in violating_line_numbers:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=line_no,
                    message="Excessive consecutive blank lines (maximum one blank line allowed).",
                    offending_lines=[lines[line_no - 1] if line_no - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        lines = content.splitlines()
        result = []
        consecutive_blanks = 0
        
        for line in lines:
            if line.strip() == "":
                consecutive_blanks += 1
                if consecutive_blanks <= 1:
                    result.append(line)
            else:
                consecutive_blanks = 0
                result.append(line)
                
        # Handle trailing newline
        ending = "\n" if content.endswith("\n") else ""
        return "\n".join(result) + ending
