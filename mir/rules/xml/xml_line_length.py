from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.xml.xml_utils import tokenize_xml

class XmlLineLengthRule(BaseRule):
    rule_id = "IR-xml-line-length"
    description = "XML lines must not exceed the configured maximum length."
    category = "general"
    is_fixable = "yes"
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
            "violating": '<myTag firstAttribute="some_long_value_to_exceed_one_hundred_and_twenty_characters" secondAttribute="another_value_to_be_sure" />',
            "correct": '<myTag firstAttribute="some_long_value_to_exceed_one_hundred_and_twenty_characters"\n       secondAttribute="another_value_to_be_sure" />'
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
                    is_fixable=True
                ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        lines = content.splitlines()
        
        any_violating = False
        for line in lines:
            if len(line) > max_length:
                any_violating = True
                break
                
        if not any_violating:
            return content
            
        tokens = tokenize_xml(content)
        n = len(tokens)
        
        tag_declarations = []
        i = 0
        while i < n:
            tok = tokens[i]
            if tok["type"] == "TAG_OPEN_START":
                j = i + 1
                tag_end_idx = -1
                while j < n:
                    if tokens[j]["type"] == "TAG_END":
                        tag_end_idx = j
                        break
                    if tokens[j]["type"] == "TAG_OPEN_START":
                        break
                    j += 1
                    
                if tag_end_idx != -1:
                    tag_declarations.append(tokens[i : tag_end_idx + 1])
                    i = tag_end_idx + 1
                    continue
            i += 1
            
        edits = []
        for tag_toks in tag_declarations:
            line_numbers = {t["line"] for t in tag_toks}
            has_violation = False
            for ln in line_numbers:
                if ln - 1 < len(lines) and len(lines[ln - 1]) > max_length:
                    has_violation = True
                    break
                    
            if not has_violation:
                continue
                
            attr_indices = []
            for idx, t in enumerate(tag_toks):
                if t["type"] == "ATTR_NAME":
                    attr_indices.append(idx)
                    
            if not attr_indices:
                continue
                
            start_line_idx = tag_toks[0]["line"] - 1
            start_line = lines[start_line_idx] if start_line_idx < len(lines) else ""
            indent = ""
            for char in start_line:
                if char in (" ", "\t"):
                    indent += char
                else:
                    break
                    
            pre_first_attr = "".join(t["value"] for t in tag_toks[:attr_indices[0]])
            first_attr_col = len(indent) + len(pre_first_attr.lstrip("\r\n\t "))
            
            option_a_parts = [pre_first_attr]
            for idx, attr_idx in enumerate(attr_indices):
                next_attr_idx = attr_indices[idx + 1] if idx + 1 < len(attr_indices) else len(tag_toks)
                end_bound = next_attr_idx
                if next_attr_idx == len(tag_toks) and tag_toks[-1]["type"] == "TAG_END":
                    end_bound = len(tag_toks) - 1
                    
                attr_text = "".join(tag_toks[m]["value"] for m in range(attr_idx, end_bound))
                if idx < len(attr_indices) - 1:
                    attr_text = attr_text.rstrip("\r\n\t ")
                    
                if idx == 0:
                    option_a_parts.append(attr_text)
                else:
                    option_a_parts.append("\n" + (" " * first_attr_col) + attr_text)
            if tag_toks[-1]["type"] == "TAG_END":
                option_a_parts.append(tag_toks[-1]["value"])
            formatted_a = "".join(option_a_parts)
            
            option_b_parts = [tag_toks[0]["value"]]
            # If the tag has multiple attributes, we can strip any trailing space from the tag open start token
            if len(attr_indices) > 0:
                option_b_parts = [tag_toks[0]["value"].rstrip("\r\n\t ")]
                
            attr_indent = indent + "    "
            for idx, attr_idx in enumerate(attr_indices):
                next_attr_idx = attr_indices[idx + 1] if idx + 1 < len(attr_indices) else len(tag_toks)
                end_bound = next_attr_idx
                if next_attr_idx == len(tag_toks) and tag_toks[-1]["type"] == "TAG_END":
                    end_bound = len(tag_toks) - 1
                    
                attr_text = "".join(tag_toks[m]["value"] for m in range(attr_idx, end_bound))
                if idx < len(attr_indices) - 1:
                    attr_text = attr_text.rstrip("\r\n\t ")
                    
                option_b_parts.append("\n" + attr_indent + attr_text)
            if tag_toks[-1]["type"] == "TAG_END":
                option_b_parts.append(tag_toks[-1]["value"])
            formatted_b = "".join(option_b_parts)
            
            a_fits = True
            for a_line in formatted_a.splitlines():
                if len(a_line) > max_length:
                    a_fits = False
                    break
                    
            chosen_text = formatted_a if a_fits else formatted_b
            
            orig_text = "".join(t["value"] for t in tag_toks)
            if chosen_text != orig_text:
                edits.append((tag_toks[0]["start"], tag_toks[-1]["end"], chosen_text))
                
        if not edits:
            return content
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
