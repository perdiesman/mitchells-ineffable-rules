from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.xml.xml_utils import tokenize_xml

class XmlSelfClosingRule(BaseRule):
    rule_id = "IR-xml-self-closing"
    description = "Enforce exactly one space before self-closing tag endings (e.g. <tag />)."
    category = "tags/elements"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "<root/>",
            "correct": "<root />"
        },
        {
            "violating": "<root  />",
            "correct": "<root />"
        }
    ]
    additional_validations = [
        "<root />",
        "<root attr=\"val\" />"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_xml(content)
        violations = []
        n = len(tokens)
        for i, t in enumerate(tokens):
            if t["type"] == "TAG_END" and t["value"] == "/>":
                # Check preceding token
                has_violation = False
                start_offset = t["start"]
                if i > 0:
                    prev = tokens[i - 1]
                    if prev["type"] == "WHITESPACE":
                        if prev["value"] != " ":
                            has_violation = True
                            start_offset = prev["start"]
                    else:
                        has_violation = True
                
                if has_violation:
                    violations.append({
                        "token": t,
                        "line": t["line"],
                        "start_offset": start_offset,
                        "end_offset": t["end"],
                        "replacement": " />",
                        "message": f"Self-closing tag ending on line {t['line']} should have exactly one space before '/>'."
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
