from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.xml.xml_utils import tokenize_xml

class XmlIndentRule(BaseRule):
    rule_id = "IR-xml-indent"
    description = "Enforce correct tag nesting indentation in XML files."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {
        "indent_size": 4
    }
    config_options = {
        "indent_size": {
            "default": 4,
            "description": "Number of spaces for nesting indentation."
        }
    }

    examples = [
        {
            "violating": "<root>\n  <child />\n</root>",
            "correct": "<root>\n    <child />\n</root>"
        }
    ]
    additional_validations = [
        "<root>\n    <child>\n        <grandchild />\n    </child>\n</root>"
    ]

    def _find_violations(self, content: str, indent_size: int) -> List[dict]:
        tokens = tokenize_xml(content)
        violations = []
        n = len(tokens)

        # Group tokens by line
        line_tokens = {}
        for t in tokens:
            line_tokens.setdefault(t["line"], []).append(t)

        depth = 0
        last_open_start = None
        first_active_seen_for_line = {}

        for i, t in enumerate(tokens):
            # Track depth transitions
            if t["type"] == "TAG_OPEN_START":
                last_open_start = t
            elif t["type"] == "TAG_CLOSE_START":
                depth -= 1
                last_open_start = None
            elif t["type"] == "TAG_END":
                if last_open_start is not None:
                    if t["value"] == ">":
                        depth += 1
                    last_open_start = None

            # Check if it's the first active token of its line
            line = t["line"]
            if t["type"] not in ("WHITESPACE", "TEXT") or (t["type"] == "TEXT" and t["value"].strip()):
                if t["type"] in ("TAG_OPEN_START", "TAG_CLOSE_START", "COMMENT", "DECLARATION"):
                    if line not in first_active_seen_for_line:
                        first_active_seen_for_line[line] = t
                        
                        line_toks = line_tokens.get(line, [])
                        t_idx_in_line = line_toks.index(t)
                        
                        actual_indent = ""
                        ws_token = None
                        if t_idx_in_line > 0:
                            prev_tok = line_toks[t_idx_in_line - 1]
                            if prev_tok["type"] == "WHITESPACE":
                                parts = prev_tok["value"].split("\n")
                                actual_indent = parts[-1]
                                ws_token = prev_tok
                        
                        expected_depth = max(0, depth)
                        expected_indent = " " * (expected_depth * indent_size)
                        
                        if actual_indent != expected_indent:
                            if ws_token is not None:
                                ws_parts = ws_token["value"].split("\n")
                                ws_prefix = "\n".join(ws_parts[:-1]) + ("\n" if len(ws_parts) > 1 else "")
                                replacement = ws_prefix + expected_indent
                                start_offset = ws_token["start"]
                                end_offset = ws_token["end"]
                            else:
                                start_offset = t["start"]
                                end_offset = t["start"]
                                replacement = expected_indent
                                
                            violations.append({
                                "token": t,
                                "line": line,
                                "start_offset": start_offset,
                                "end_offset": end_offset,
                                "replacement": replacement,
                                "message": f"XML tag indentation on line {line} should be {expected_depth * indent_size} spaces (depth {expected_depth}), but found {len(actual_indent)} spaces."
                            })

        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        indent_size = self.get_config_value(rule_config, "indent_size", 4)
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, indent_size)
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
        indent_size = self.get_config_value(rule_config, "indent_size", 4)
        offending = self._find_violations(content, indent_size)
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
