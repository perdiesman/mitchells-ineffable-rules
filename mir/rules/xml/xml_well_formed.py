import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class XmlWellFormedRule(BaseRule):
    rule_id = "IR-xml-well-formed"
    description = "Ensure that XML content is well-formed."
    category = "general"
    is_fixable = "no"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "<root>\n    <child>\n</root>",
            "correct": "<root>\n    <child />\n</root>"
        }
    ]
    additional_validations = [
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<root />"
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        try:
            ET.fromstring(content)
        except ET.ParseError as e:
            line_num = 1
            col_num = 1
            if hasattr(e, "position") and e.position:
                line_num = e.position[0]
                col_num = e.position[1]
            
            lines = content.splitlines()
            line_idx = line_num - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=line_num,
                message=f"XML parsing error: {e}",
                offending_lines=[offending_line],
                is_fixable=False
            ))
        return violations
