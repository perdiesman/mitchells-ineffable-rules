import re
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.xml.xml_utils import tokenize_xml


def _unbreakable_single_attribute_tag(line: str, max_length: int) -> bool:
    """Return whether XML syntax cannot wrap the only attribute any shorter."""
    match = re.match(
        r'^(?P<indent>[ \t]*)<[A-Za-z_:][\w:.-]*\s+'
        r'(?P<attribute>[A-Za-z_:][\w:.-]*="[^"]*")\s*/>\s*$',
        line,
    )
    if match is None:
        return False
    shortest_attribute_line = (
        len(match.group("indent")) + 4 + len(match.group("attribute"))
    )
    return shortest_attribute_line > max_length

class XmlLineLengthRule(BaseRule):
    commit_profile = True
    rule_id = "IR-xml-line-length"
    description = (
        "XML lines must not exceed the configured maximum length, and repeated "
        "MyBatis foreach forms use the same expanded layout; overlong inline "
        "dynamic SQL blocks expand without changing their expressions."
    )
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
            "correct": '<myTag firstAttribute="some_long_value_to_exceed_one_hundred_and_twenty_characters"\n        secondAttribute="another_value_to_be_sure" />'
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
            if (
                len(line) > max_length
                and not _unbreakable_single_attribute_tag(line, max_length)
            ):
                violations.append(Violation(
                    rule_id=self.rule_id,
                    line_number=idx,
                    message=f"Line {idx} exceeds maximum length of {max_length} characters (actual length: {len(line)}).",
                    offending_lines=[line],
                    is_fixable=True
                ))
        from mir.rules.xml.xml_mybatis_sql import (
            get_all_elements_recursively,
            parse_xml_elements,
        )

        elements = get_all_elements_recursively(
            parse_xml_elements(tokenize_xml(content))
        )
        multiline_signatures = {
            content[element["start_offset"]:element["inner_tokens"][0]["start"]].strip()
            for element in elements
            if element["tag"] == "foreach"
            and element["inner_tokens"]
            and content.count("\n", 0, element["start_offset"])
            != content.count("\n", 0, element["end_offset"])
        }
        for element in elements:
            if element["tag"] != "foreach" or not element["inner_tokens"]:
                continue
            line_index = content.count("\n", 0, element["start_offset"])
            end_line = content.count("\n", 0, element["end_offset"])
            signature = content[
                element["start_offset"]:element["inner_tokens"][0]["start"]
            ].strip()
            if line_index == end_line and signature in multiline_signatures:
                violations.append(Violation(
                    rule_id=self.rule_id,
                    line_number=line_index + 1,
                    message=(
                        "Repeated MyBatis foreach forms should use the same "
                        "expanded layout."
                    ),
                    offending_lines=[lines[line_index]],
                    is_fixable=True,
                ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        lines = content.splitlines()
        
        tokens = tokenize_xml(content)
        n = len(tokens)

        from mir.rules.xml.xml_mybatis_sql import parse_xml_elements, get_all_elements_recursively

        elements = get_all_elements_recursively(parse_xml_elements(tokens))
        multiline_foreach_signatures = set()
        for element in elements:
            if element["tag"] != "foreach" or not element["inner_tokens"]:
                continue
            start_line = content.count("\n", 0, element["start_offset"])
            end_line = content.count("\n", 0, element["end_offset"])
            if start_line == end_line:
                continue
            first_inner = element["inner_tokens"][0]["start"]
            multiline_foreach_signatures.add(
                content[element["start_offset"]:first_inner].strip()
            )

        any_violating = any(len(line) > max_length for line in lines)
        has_inconsistent_foreach = any(
            element["tag"] == "foreach"
            and element["inner_tokens"]
            and content.count("\n", 0, element["start_offset"])
            == content.count("\n", 0, element["end_offset"])
            and content[
                element["start_offset"]:element["inner_tokens"][0]["start"]
            ].strip() in multiline_foreach_signatures
            for element in elements
        )
        if not any_violating and not has_inconsistent_foreach:
            return content

        # Two individually compact dynamic tags can make their shared physical
        # line overlong. Split the whitespace between sibling tags first; on
        # the next pass each tag can remain in its readable inline form.
        adjacent_tag_edits = []
        ordered_elements = sorted(elements, key=lambda item: item["start_offset"])
        for current, following in zip(ordered_elements, ordered_elements[1:]):
            if (
                current["tag"] not in {"foreach", "if", "when", "otherwise"}
                or following["tag"] not in {"foreach", "if", "when", "otherwise"}
                or current["end_offset"] > following["start_offset"]
            ):
                continue
            current_line = content.count("\n", 0, current["start_offset"])
            following_line = content.count("\n", 0, following["start_offset"])
            if (
                current_line != following_line
                or current_line >= len(lines)
                or len(lines[current_line]) <= max_length
            ):
                continue
            gap = content[current["end_offset"]:following["start_offset"]]
            if not gap or not gap.isspace() or "\n" in gap:
                continue
            line = lines[current_line]
            indent = line[: len(line) - len(line.lstrip(" \t"))]
            adjacent_tag_edits.append(
                (current["end_offset"], following["start_offset"], "\n" + indent)
            )
        if adjacent_tag_edits:
            chars = list(content)
            for start, end, replacement in sorted(adjacent_tag_edits, reverse=True):
                chars[start:end] = list(replacement)
            return "".join(chars)

        block_edits = []
        for element in elements:
            if (
                element["tag"] not in {"foreach", "if", "when", "otherwise"}
                or not element["inner_tokens"]
            ):
                continue
            if any(token["type"] == "TAG_OPEN_START" for token in element["inner_tokens"]):
                continue
            start_line = content.count("\n", 0, element["start_offset"])
            end_line = content.count("\n", 0, element["end_offset"])
            first_inner = element["inner_tokens"][0]["start"]
            signature = content[element["start_offset"]:first_inner].strip()
            repeated_foreach = (
                element["tag"] == "foreach"
                and signature in multiline_foreach_signatures
            )
            if (
                start_line != end_line
                or start_line >= len(lines)
                or (
                    len(lines[start_line]) <= max_length
                    and not repeated_foreach
                )
            ):
                continue
            last_inner = element["inner_tokens"][-1]["end"]
            opening = content[element["start_offset"]:first_inner]
            inner = content[first_inner:last_inner]
            closing = content[last_inner:element["end_offset"]]
            if "\n" in opening or not inner.strip():
                continue
            line = lines[start_line]
            indent = line[: len(line) - len(line.lstrip(" \t"))]
            line_start = content.rfind("\n", 0, element["start_offset"]) + 1
            line_end = content.find("\n", element["end_offset"])
            if line_end == -1:
                line_end = len(content)
            prefix = content[line_start:element["start_offset"]]
            suffix = content[element["end_offset"]:line_end]
            edit_start = element["start_offset"]
            edit_end = element["end_offset"]
            tag_indent = indent
            leading = ""
            trailing = ""
            if prefix.strip():
                gap_start = element["start_offset"]
                while gap_start > line_start and content[gap_start - 1] in " \t":
                    gap_start -= 1
                edit_start = gap_start
                tag_indent = indent + "    "
                leading = "\n" + tag_indent
            if suffix.strip():
                gap_end = element["end_offset"]
                while gap_end < line_end and content[gap_end] in " \t":
                    gap_end += 1
                edit_end = gap_end
                trailing = "\n" + tag_indent
            replacement = (
                leading
                + opening.rstrip()
                + "\n"
                + tag_indent
                + "    "
                + inner.strip()
                + "\n"
                + tag_indent
                + closing.lstrip()
                + trailing
            )
            block_edits.append((edit_start, edit_end, replacement))

        if block_edits:
            chars = list(content)
            for start, end, replacement in sorted(block_edits, reverse=True):
                chars[start:end] = list(replacement)
            return "".join(chars)
        
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
                    
            xml_indent_config = rule_config.get("_all_configs", {}).get("IR-xml-indent", {})
            if isinstance(xml_indent_config, bool):
                indent_size = 4
            elif isinstance(xml_indent_config, dict):
                indent_size = xml_indent_config.get("indent_size", 4)
            else:
                indent_size = 4
            attr_indent = indent + " " * (2 * indent_size)
            
            pre_first_attr = "".join(t["value"] for t in tag_toks[:attr_indices[0]])
            
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
                    option_a_parts.append("\n" + attr_indent + attr_text)
            if tag_toks[-1]["type"] == "TAG_END":
                option_a_parts.append(tag_toks[-1]["value"])
            formatted_a = "".join(option_a_parts)
            
            option_b_parts = [tag_toks[0]["value"]]
            # If the tag has multiple attributes, we can strip any trailing space from the tag open start token
            if len(attr_indices) > 0:
                option_b_parts = [tag_toks[0]["value"].rstrip("\r\n\t ")]
                
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
            for line_index, a_line in enumerate(formatted_a.splitlines()):
                physical_length = len(a_line) + (
                    len(indent) if line_index == 0 else 0
                )
                if physical_length > max_length:
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
