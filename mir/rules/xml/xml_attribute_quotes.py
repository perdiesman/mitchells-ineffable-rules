from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.xml.xml_utils import tokenize_xml

class XmlAttributeQuotesRule(BaseRule):
    commit_profile = True
    rule_id = "IR-xml-attribute-quotes"
    description = (
        "Enforce double quotes around attribute values and encode greater-than "
        "comparisons inside attributes."
    )
    category = "attributes"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "<root attr='value' />",
            "correct": "<root attr=\"value\" />"
        },
        {
            "violating": '<if test="count > 0">value</if>',
            "correct": '<if test="count &gt; 0">value</if>',
        }
    ]
    additional_validations = [
        "<root attr=\"value\" />",
        "<root attr=\"val &quot;quote&quot;\" />",
        '<if test="count &gt; 0">value</if>',
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_xml(content)
        violations = []
        for t in tokens:
            if t["type"] != "ATTR_VALUE" or len(t["value"]) < 2:
                continue
            quote = t["value"][0]
            if quote not in {"'", '"'} or t["value"][-1] != quote:
                continue
            inner = t["value"][1:-1]
            if quote == "'" or ">" in inner:
                replacement = (
                    '"'
                    + inner.replace('"', '&quot;').replace(">", "&gt;")
                    + '"'
                )
                violations.append({
                    "token": t,
                    "line": t["line"],
                    "start_offset": t["start"],
                    "end_offset": t["end"],
                    "replacement": replacement,
                    "message": (
                        f"Attribute value on line {t['line']} should use double "
                        "quotes and encoded comparison operators."
                    )
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
