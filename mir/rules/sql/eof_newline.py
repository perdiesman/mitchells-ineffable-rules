from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class EofNewlineRule(BaseRule):
    rule_id = "IR-eof-newline"
    description = "Enforce that every SQL file ends with exactly one newline character."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = False
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users;",
            "correct": "SELECT * FROM users;\n"
        },
        {
            "violating": "SELECT * FROM users;\n\n\n",
            "correct": "SELECT * FROM users;\n"
        }
    ]
    additional_validations = [
        "SELECT * FROM users;\n"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        violations = []
        if not content:
            return violations
            
        stripped = content.rstrip()
        expected = stripped + "\n"
        
        if content != expected:
            lines = content.splitlines()
            line_no = len(lines) if lines else 1
            violations.append({
                "line": line_no,
                "replacement": expected
            })
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message="File should end with exactly one newline character.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        return offending[0]["replacement"]
