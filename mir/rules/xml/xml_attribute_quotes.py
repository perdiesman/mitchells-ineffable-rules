from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.xml.xml_utils import tokenize_xml

class XmlAttributeQuotesRule(BaseRule):
    rule_id = "IR-xml-attribute-quotes"
    description = "Enforce double quotes around attribute values instead of single quotes."
    category = "attributes"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "<root attr='value' />",
            "correct": "<root attr=\"value\" />"
        }
    ]
    additional_validations = [
        "<root attr=\"value\" />",
        "<root attr=\"val &quot;quote&quot;\" />"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_xml(content)
        violations = []
        for t in tokens:
            if t["type"] == "ATTR_VALUE" and t["value"].startswith("'") and t["value"].endswith("'"):
                inner = t["value"][1:-1]
                replacement = '"' + inner.replace('"', '&quot;') + '"'
                violations.append({
                    "token": t,
                    "line": t["line"],
                    "start_offset": t["start"],
                    "end_offset": t["end"],
                    "replacement": replacement,
                    "message": f"Attribute value on line {t['line']} should use double quotes."
                })
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        for v in offending:
            line_idx = v["line"] - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=v["line"],
                message=v["message"],
                offending_lines=[offending_line],
                is_fixable=True
            ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        edits = []
        for item in offending:
            edits.append((item["start_offset"], item["end_offset"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
