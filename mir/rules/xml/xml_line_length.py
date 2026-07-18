from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class XmlLineLengthRule(BaseRule):
    rule_id = "IR-xml-line-length"
    description = "XML lines must not exceed the configured maximum length."
    category = "general"
    is_fixable = "no"
    enabled_by_default = True

    default_config = {
        "max_length": 120
    }
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length limit."
        }
    }

    examples = [
        {
            "violating": "<!-- " + ("A" * 120) + " -->",
            "correct": "<!-- Short line -->"
        }
    ]
    additional_validations = [
        "<root />"
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        violations = []
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            if len(line) > max_length:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    line_number=idx,
                    message=f"Line {idx} exceeds maximum length of {max_length} characters (actual length: {len(line)}).",
                    offending_lines=[line],
                    is_fixable=False
                ))
        return violations
