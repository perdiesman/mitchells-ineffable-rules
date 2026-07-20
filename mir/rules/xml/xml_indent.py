from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.xml.xml_utils import tokenize_xml
def get_sql_tag_indent(t: dict, active_parents: List[dict], content: str, lines: List[str], indent_size: int) -> str:
    # 1. Find the query tag in active_parents
    query_el = None
    for el in reversed(active_parents):
        if el["tag"] in ("select", "insert", "update", "delete", "sql"):
            query_el = el
            break
            
    if not query_el:
        return None
        
    query_line = query_el["token"]["line"]
    query_tag_indent_size = 0
    # Find query tag's line indentation
    if query_line - 1 < len(lines):
        q_line = lines[query_line - 1]
        for char in q_line:
            if char in (" ", "\t"):
                query_tag_indent_size += 1
            else:
                break
                
    base_query_indent = query_tag_indent_size + indent_size
    
    # 2. If it's a closing tag
    if t["type"] == "TAG_CLOSE_START":
        tag_name = t["value"][2:].lower()
        if tag_name in ("select", "insert", "update", "delete", "sql"):
            return None
        # Find the matching opening tag in active_parents
        matching_el = None
        for el in reversed(active_parents):
            if el["tag"] == tag_name:
                matching_el = el
                break
        if matching_el and matching_el.get("resolved_indent") is not None:
            return matching_el["resolved_indent"]
        # Fallback to base query indent
        return " " * base_query_indent
        
    # 3. If it's an intermediate tag like <when> or <otherwise>
    tag_name = t["value"][1:].lower()
    if tag_name in ("when", "otherwise"):
        # Parent should be <choose>
        choose_el = None
        for el in reversed(active_parents):
            if el["tag"] == "choose":
                choose_el = el
                break
        if choose_el and choose_el.get("resolved_indent") is not None:
            # indent one level relative to choose_indent
            return choose_el["resolved_indent"] + " " * indent_size
            
    # 4. For opening tags (like <if>, <foreach>, <choose>, etc.)
    # Look at preceding lines within the query block
    curr_line = t["line"]
    target_indent = None
    
    for k in range(curr_line - 2, query_line - 1, -1):
        line_text = lines[k]
        if line_text.strip():
            line_indent = ""
            for char in line_text:
                if char in (" ", "\t"):
                    line_indent += char
                else:
                    break
            if len(line_indent) >= query_tag_indent_size:
                target_indent = line_indent
                
                # Check for extra indentation triggers at the end of the line
                clean_line = line_text
                if "--" in clean_line:
                    clean_line = clean_line.split("--", 1)[0]
                clean_line = clean_line.strip()
                if clean_line:
                    ends_with_opening_tag = False
                    if clean_line.endswith(">"):
                        last_open = clean_line.rfind("<")
                        if last_open != -1:
                            tag_str = clean_line[last_open:]
                            if not tag_str.startswith("</") and not tag_str.endswith("/>") and not tag_str.startswith("<!--") and not tag_str.startswith("<?") and not tag_str.startswith("<!"):
                                ends_with_opening_tag = True
                                
                    if ends_with_opening_tag:
                        target_indent += " " * indent_size
                    else:
                        last_char = clean_line[-1]
                        last_word = ""
                        words = clean_line.split()
                        if words:
                            last_word = words[-1].upper()
                            
                        extra_indent_keywords = {
                            "FROM", "WHERE", "SELECT", "HAVING", "ON", "USING", "VALUES", "SET", 
                            "AND", "OR", "JOIN", "LEFT", "RIGHT", "INNER", "CROSS", "FULL", "WITH",
                            "CASE", "THEN", "ELSE", "BEGIN", "EXCEPTION",
                            "(", "+", "-", "/", "||", ","
                        }
                        if last_char in extra_indent_keywords or last_word in extra_indent_keywords:
                            target_indent += " " * indent_size
            break
            
    if target_indent is None:
        target_indent = " " * base_query_indent
    else:
        # If the target indent is less than base query indent, cap it at base query indent
        if len(target_indent) < base_query_indent:
            target_indent = " " * base_query_indent
            
    return target_indent

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
        lines = content.splitlines()
        n = len(tokens)

        # Build line starts mapping
        line_starts = [0]
        for offset, char in enumerate(content):
            if char == '\n':
                line_starts.append(offset + 1)

        depth = 0
        last_open_start = None
        tag_stack = []
        
        # Track line delta and explicit expected indents
        line_cumulative_delta = {}
        explicit_expected_indent = {}
        line_min_parent_indent = {}

        for i, t in enumerate(tokens):
            line = t["line"]
            
            # Record delta at start of line
            if line not in line_cumulative_delta:
                delta = 0
                for el in reversed(tag_stack):
                    if el.get("delta") is not None:
                        delta = el["delta"]
                        break
                line_cumulative_delta[line] = delta
                
                min_parent_indent = 0
                if tag_stack:
                    for j, el in enumerate(reversed(tag_stack)):
                        abs_j = len(tag_stack) - 1 - j
                        if el.get("resolved_indent") is not None:
                            min_parent_indent = len(el["resolved_indent"])
                            break
                        else:
                            min_parent_indent = abs_j * indent_size
                            break
                line_min_parent_indent[line] = min_parent_indent

            # Track depth transitions
            if t["type"] == "TAG_OPEN_START":
                tag_name = t["value"][1:].lower()
                line_delta = line_cumulative_delta.get(line, 0)
                el = {"tag": tag_name, "token": t, "resolved_indent": None, "delta": line_delta}
                tag_stack.append(el)
                last_open_start = t
            elif t["type"] == "TAG_CLOSE_START":
                depth -= 1
                last_open_start = None
            elif t["type"] == "TAG_END":
                if last_open_start is not None:
                    if t["value"] == ">":
                        depth += 1
                    else:  # self closing tag "/>"
                        if tag_stack:
                            tag_stack.pop()
                    last_open_start = None

            # Check if it's the first active token of its line
            if t["type"] not in ("WHITESPACE", "TEXT") or (t["type"] == "TEXT" and t["value"].strip()):
                if t["type"] in ("TAG_OPEN_START", "TAG_CLOSE_START", "COMMENT", "DECLARATION"):
                    if line not in explicit_expected_indent:
                        # Find start of line in content string
                        line_start_idx = t["start"]
                        while line_start_idx > 0 and content[line_start_idx - 1] != '\n':
                            line_start_idx -= 1
                            
                        # Actual indent is the string from line_start_idx to t["start"]
                        actual_indent = content[line_start_idx : t["start"]]
                        
                        if not actual_indent or actual_indent.isspace():
                            # Determine if t is inside a query block
                            is_inside_query = False
                            active_parents = tag_stack[:-1] if t["type"] == "TAG_OPEN_START" else tag_stack
                            for el in active_parents:
                                if el["tag"] in ("select", "insert", "update", "delete", "sql"):
                                    is_inside_query = True
                                    break
                                    
                            sql_indent = None
                            if is_inside_query:
                                sql_indent = get_sql_tag_indent(t, active_parents, content, lines, indent_size)
                                
                            if sql_indent is not None:
                                expected_indent = sql_indent
                            else:
                                expected_depth = max(0, depth)
                                expected_indent = " " * (expected_depth * indent_size)
                                
                            if t["type"] == "TAG_OPEN_START" and tag_stack:
                                tag_stack[-1]["resolved_indent"] = expected_indent
                                
                            explicit_expected_indent[line] = expected_indent
                            
                            delta = len(expected_indent) - len(actual_indent)
                            if t["type"] == "TAG_OPEN_START" and tag_stack:
                                tag_stack[-1]["delta"] = delta

            # Post-check tag stack cleanup for close tags
            if t["type"] == "TAG_CLOSE_START":
                tag_name = t["value"][2:].lower()
                if tag_stack and tag_stack[-1]["tag"] == tag_name:
                    tag_stack.pop()

        # Build violations by checking all non-empty lines
        for idx in range(1, len(lines) + 1):
            line_text = lines[idx - 1]
            if not line_text.strip():
                continue
                
            # Get actual indentation of this line
            actual_indent = ""
            for char in line_text:
                if char in (" ", "\t"):
                    actual_indent += char
                else:
                    break
                    
            if idx in explicit_expected_indent:
                expected_indent = explicit_expected_indent[idx]
            else:
                delta = line_cumulative_delta.get(idx, 0)
                if delta != 0:
                    sign = 1 if delta > 0 else -1
                    abs_delta = abs(delta)
                    remainder = abs_delta % indent_size
                    if remainder != 0:
                        if remainder > (indent_size / 2):
                            abs_delta += (indent_size - remainder)
                        else:
                            abs_delta -= remainder
                    delta = abs_delta * sign
                expected_indent_len = max(0, len(actual_indent) + delta)
                if idx in line_min_parent_indent:
                    min_parent = line_min_parent_indent[idx]
                    expected_indent_len = max(expected_indent_len, min_parent + indent_size)
                expected_indent = " " * expected_indent_len
                
            if actual_indent != expected_indent:
                start_offset = line_starts[idx - 1] if idx - 1 < len(line_starts) else len(content)
                end_offset = start_offset + len(actual_indent)
                
                if start_offset < len(content):
                    violations.append({
                        "line": idx,
                        "start_offset": start_offset,
                        "end_offset": end_offset,
                        "replacement": expected_indent,
                        "message": f"XML indentation on line {idx} should be {len(expected_indent)} spaces, but found {len(actual_indent)} spaces."
                    })
                    
        # Check for collapsable elements that can fit on a single line under 120 chars
        from mir.rules.xml.xml_mybatis_sql import parse_xml_elements, get_all_elements_recursively
        try:
            root_elements = parse_xml_elements(tokens)
            elements = get_all_elements_recursively(root_elements)
            for el in elements:
                if el["tag"] in ("mapper", "select", "insert", "update", "delete", "sql"):
                    continue
                if not el["inner_tokens"]:
                    continue
                has_child_tags = any(t["type"] == "TAG_OPEN_START" for t in el["inner_tokens"])
                if has_child_tags:
                    continue
                
                # Check if it's on multiple lines originally
                start_token = tokens[el["start_idx"]]
                end_token = tokens[el["end_idx"]]
                if start_token["line"] == end_token["line"]:
                    continue
                    
                start_offset = el["start_offset"]
                end_offset = el["end_offset"]
                
                first_inner = el["inner_tokens"][0]["start"]
                last_inner = el["inner_tokens"][-1]["end"]
                
                opening_tag = content[start_offset:first_inner]
                inner_text = content[first_inner:last_inner]
                closing_tag = content[last_inner:end_offset]
                
                collapsed = opening_tag.strip() + inner_text.strip() + closing_tag.strip()
                
                # Resolve indent from start_line
                start_line_idx = start_token["line"] - 1
                expected_indent = explicit_expected_indent.get(start_token["line"])
                if expected_indent is None:
                    start_line = lines[start_line_idx] if start_line_idx < len(lines) else ""
                    indent = ""
                    for char in start_line:
                        if char in (" ", "\t"):
                            indent += char
                        else:
                            break
                    expected_indent = indent
                    
                total_len = len(expected_indent) + len(collapsed)
                if total_len < 120:
                    violations.append({
                        "line": start_token["line"],
                        "start_offset": start_offset,
                        "end_offset": end_offset,
                        "replacement": collapsed,
                        "message": f"XML tag '{el['tag']}' and its text content can be collapsed onto a single line."
                    })
        except Exception:
            pass
            
        collapse_spans = []
        for v in violations:
            if "collapsed" in v.get("message", "") or "collapse" in v.get("message", ""):
                collapse_spans.append((v["start_offset"], v["end_offset"]))
                
        if collapse_spans:
            filtered_violations = []
            for v in violations:
                is_overlapped = False
                if "collapsed" not in v.get("message", "") and "collapse" not in v.get("message", ""):
                    for c_start, c_end in collapse_spans:
                        if c_start <= v["start_offset"] < c_end:
                            is_overlapped = True
                            break
                if not is_overlapped:
                    filtered_violations.append(v)
            violations = filtered_violations
            
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
