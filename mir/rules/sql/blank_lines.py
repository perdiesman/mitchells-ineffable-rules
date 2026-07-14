from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class BlankLinesRule(BaseRule):
    rule_id = "IR-blank-lines"
    description = "Limit consecutive blank lines to a configurable maximum."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    exclude_recursive = True
    
    default_config = {
        "max_blank_lines": 1
    }
    config_options = {
        "max_blank_lines": {
            "type": "int",
            "description": "Maximum number of consecutive blank lines allowed.",
            "default": 1
        }
    }
    
    examples = [
        {
            "violating": "SELECT * FROM users;\n\n\n\nSELECT * FROM roles;",
            "correct": "SELECT * FROM users;\n\nSELECT * FROM roles;"
        }
    ]
    additional_validations = []

    def _get_max_blank_lines(self, rule_config: Dict[str, Any]) -> int:
        val = rule_config.get("max_blank_lines", 1)
        try:
            return int(val)
        except (ValueError, TypeError):
            return 1

    def _check_and_find(self, content: str, max_blank_lines: int) -> List[int]:
        lines = content.splitlines()
        consecutive_blanks = 0
        violating_lines = []
        
        for idx, line in enumerate(lines):
            if line.strip() == "":
                consecutive_blanks += 1
                if consecutive_blanks > max_blank_lines:
                    violating_lines.append(idx + 1)
            else:
                consecutive_blanks = 0
        return violating_lines

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        max_blank_lines = self._get_max_blank_lines(rule_config)
        violating_line_numbers = self._check_and_find(content, max_blank_lines)
        
        for line_no in violating_line_numbers:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=line_no,
                    message=f"Excessive consecutive blank lines (maximum {max_blank_lines} allowed).",
                    offending_lines=[lines[line_no - 1] if line_no - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        lines = content.splitlines()
        result = []
        consecutive_blanks = 0
        max_blank_lines = self._get_max_blank_lines(rule_config)
        
        for line in lines:
            if line.strip() == "":
                consecutive_blanks += 1
                if consecutive_blanks <= max_blank_lines:
                    result.append(line)
            else:
                consecutive_blanks = 0
                result.append(line)
                
        ending = "\n" if content.endswith("\n") else ""
        return "\n".join(result) + ending
