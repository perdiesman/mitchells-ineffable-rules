import re
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql
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
    if tag_name in {"if", "when", "otherwise"}:
        opening_end = content.find(">", t["start"])
        closing_start = content.find(f"</{tag_name}", opening_end + 1)
        if opening_end != -1 and closing_start != -1:
            dynamic_text = content[opening_end + 1:closing_start].strip().upper()
            if re.match(
                r"(?:(?:LEFT|RIGHT|FULL)(?:\s+OUTER)?|INNER|CROSS)?\s*JOIN\b",
                dynamic_text,
            ):
                for k in range(t["line"] - 2, query_line - 1, -1):
                    previous = lines[k]
                    if not previous.strip():
                        continue
                    previous_text = previous.strip().upper()
                    if previous_text.startswith(("AND ", "OR ")):
                        previous_indent = previous[
                            : len(previous) - len(previous.lstrip(" \t"))
                        ]
                        if len(previous_indent) >= indent_size:
                            return previous_indent[:-indent_size]
                    break
            if dynamic_text in {"LEFT", "RIGHT", "INNER", "FULL", "CROSS"}:
                for k in range(t["line"] - 2, query_line - 1, -1):
                    candidate = lines[k]
                    candidate_text = candidate.strip().upper()
                    if re.match(
                        r"(?:(?:LEFT|RIGHT|FULL)(?:\s+OUTER)?|INNER|CROSS)?\s*JOIN\b",
                        candidate_text,
                    ):
                        return candidate[: len(candidate) - len(candidate.lstrip(" \t"))]

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
                            "IN", "JOIN", "LEFT", "RIGHT", "INNER", "CROSS", "FULL", "WITH",
                            "CASE", "THEN", "ELSE", "BEGIN", "EXCEPTION",
                            "(", "+", "-", "/", "||"
                        }
                        if last_char in extra_indent_keywords or last_word in extra_indent_keywords:
                            target_indent += " " * indent_size
                            if (
                                last_char == "("
                                and re.search(
                                    r"\bJOIN\s+[A-Z_][A-Z0-9_.]*\s*\($",
                                    clean_line,
                                    re.IGNORECASE,
                                )
                            ):
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
    commit_profile = True
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

        from mir.rules.xml.xml_mybatis_sql import parse_xml_elements, get_all_elements_recursively

        elements = get_all_elements_recursively(parse_xml_elements(tokens))
        query_ranges = [
            (el["start_offset"], el["end_offset"])
            for el in elements
            if el["tag"] in ("select", "insert", "update", "delete", "sql")
        ]
        for element in elements:
            if element["tag"] != "delete":
                continue
            body_start = tokens[element["open_end_idx"]]["end"]
            body_end = tokens[element["end_idx"]]["start"]
            body = content[body_start:body_end]
            delete_from = re.search(
                r"(?mi)^([ \t]*)DELETE([ \t]+)FROM\b", body
            )
            if delete_from is None:
                continue
            indent = delete_from.group(1)
            gap_start = body_start + delete_from.start(2)
            gap_end = body_start + delete_from.end(2)
            violations.append({
                "line": content.count("\n", 0, gap_start) + 1,
                "start_offset": gap_start,
                "end_offset": gap_end,
                "replacement": "\n" + indent,
                "message": "MyBatis delete statements should place FROM on the next line.",
            })
        for element in elements:
            if element["tag"] not in {"select", "sql"}:
                continue
            body_start = tokens[element["open_end_idx"]]["end"]
            body_end = tokens[element["end_idx"]]["start"]
            body = content[body_start:body_end]
            for match in re.finditer(
                r"(?i)\bSELECT\s+DISTINCT\s+ON\s*\(", body
            ):
                select_start = body_start + match.start()
                open_paren = body_start + match.end() - 1
                depth = 1
                quote = None
                cursor = open_paren + 1
                close_paren = None
                while cursor < body_end:
                    char = content[cursor]
                    if char == "<":
                        tag_end = content.find(">", cursor, body_end)
                        if tag_end == -1:
                            break
                        cursor = tag_end + 1
                        continue
                    if quote:
                        if char == quote:
                            if cursor + 1 < body_end and content[cursor + 1] == quote:
                                cursor += 2
                                continue
                            quote = None
                    elif char in ("'", '"'):
                        quote = char
                    elif char == "(":
                        depth += 1
                    elif char == ")":
                        depth -= 1
                        if depth == 0:
                            close_paren = cursor
                            break
                    cursor += 1
                if close_paren is None:
                    continue
                inner = content[open_paren + 1:close_paren]
                if "<if" not in inner.lower():
                    continue
                suffix = re.match(r"\s*\*", content[close_paren + 1:body_end])
                if suffix is None:
                    continue
                projection_end = close_paren + 1 + suffix.end()

                parts = []
                segment_start = 0
                inner_depth = 0
                inner_quote = None
                index = 0
                while index < len(inner):
                    char = inner[index]
                    if char == "<" and inner[index:index + 3].lower() == "<if":
                        if inner[segment_start:index].strip():
                            parts.append((inner[segment_start:index], False))
                        close_tag = inner.lower().find("</if>", index)
                        if close_tag == -1:
                            break
                        close_tag += len("</if>")
                        parts.append((inner[index:close_tag], False))
                        index = close_tag
                        segment_start = index
                        continue
                    if inner_quote:
                        if char == inner_quote:
                            if index + 1 < len(inner) and inner[index + 1] == inner_quote:
                                index += 2
                                continue
                            inner_quote = None
                    elif char in ("'", '"'):
                        inner_quote = char
                    elif char == "(":
                        inner_depth += 1
                    elif char == ")":
                        inner_depth -= 1
                    elif char == "," and inner_depth == 0:
                        parts.append((inner[segment_start:index], True))
                        segment_start = index + 1
                    index += 1
                if inner[segment_start:].strip():
                    parts.append((inner[segment_start:], False))

                normalized_parts = []
                for part, had_comma in parts:
                    stripped = part.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("<"):
                        normalized = re.sub(r">\s+", ">", stripped)
                        normalized = re.sub(r"\s+<", "<", normalized)
                    else:
                        sql_tokens = tokenize_sql(stripped)
                        normalized = "".join(
                            " " if item["type"] == "WHITESPACE" else item["value"]
                            for item in sql_tokens
                        ).strip()
                    if had_comma:
                        normalized += ","
                    normalized_parts.append(normalized)
                if not normalized_parts:
                    continue

                line_start = content.rfind("\n", 0, select_start) + 1
                prefix = content[line_start:select_start]
                indent = prefix[: len(prefix) - len(prefix.lstrip(" \t"))]
                distinct_indent = indent + " " * indent_size
                inner_indent = distinct_indent + " " * indent_size
                expected = (
                    "SELECT\n"
                    + distinct_indent
                    + "DISTINCT ON (\n"
                    + "\n".join(inner_indent + part for part in normalized_parts)
                    + "\n"
                    + distinct_indent
                    + ") *"
                )
                original = content[select_start:projection_end]
                if original != expected:
                    violations.append({
                        "line": content.count("\n", 0, select_start) + 1,
                        "start_offset": select_start,
                        "end_offset": projection_end,
                        "replacement": expected,
                        "message": "Dynamic DISTINCT ON keys should use multiline column layout.",
                        "structural": True,
                    })
        for token_index, token in enumerate(tokens):
            if token["type"] != "TAG_OPEN_START" or token["value"][1:].lower() != "include":
                continue
            if not any(start < token["start"] < end for start, end in query_ranges):
                continue
            line_start = content.rfind("\n", 0, token["start"]) + 1
            prefix = content[line_start:token["start"]]
            sql_prefix = prefix.rstrip(" \t")
            if not sql_prefix or sql_prefix.split()[-1].upper() != "SELECT":
                continue
            select_indent = prefix[: len(prefix) - len(prefix.lstrip(" \t"))]
            violations.append({
                "line": token["line"],
                "start_offset": line_start + len(sql_prefix),
                "end_offset": token["start"],
                "replacement": "\n" + select_indent + " " * indent_size,
                "message": "MyBatis SELECT includes should use column-list indentation.",
            })
            tag_end = next(
                (
                    item
                    for item in tokens[token_index + 1:]
                    if item["type"] == "TAG_END"
                ),
                None,
            )
            if tag_end is None:
                continue
            next_line_start = content.find("\n", tag_end["end"])
            if next_line_start == -1:
                continue
            next_line_start += 1
            next_line_end = content.find("\n", next_line_start)
            if next_line_end == -1:
                next_line_end = len(content)
            next_line = content[next_line_start:next_line_end]
            next_text = next_line.lstrip(" \t")
            if not next_text or next_text.split(None, 1)[0].upper() == "FROM":
                continue
            expected_indent = select_indent + " " * indent_size
            actual_indent = next_line[: len(next_line) - len(next_text)]
            if actual_indent != expected_indent:
                violations.append({
                    "line": token["line"] + 1,
                    "start_offset": next_line_start,
                    "end_offset": next_line_start + len(actual_indent),
                    "replacement": expected_indent,
                    "message": "Columns after a MyBatis SELECT include should stay aligned.",
                })
        for token in tokens:
            if token["type"] != "TAG_OPEN_START" or token["value"][1:].lower() != "foreach":
                continue
            if not any(start < token["start"] < end for start, end in query_ranges):
                continue
            line_start = content.rfind("\n", 0, token["start"]) + 1
            prefix = content[line_start:token["start"]]
            sql_prefix = prefix.rstrip(" \t")
            same_line = bool(sql_prefix)
            if same_line:
                in_line = sql_prefix
                gap_start = line_start + len(sql_prefix)
                gap_replacement_prefix = "\n"
            else:
                previous_line_end = line_start - 1
                previous_line_start = content.rfind(
                    "\n", 0, previous_line_end
                ) + 1
                in_line = content[previous_line_start:previous_line_end].rstrip(
                    " \t"
                )
                gap_start = line_start
                gap_replacement_prefix = ""
            if not in_line or in_line.split()[-1].upper() != "IN":
                continue
            line_indent = in_line[: len(in_line) - len(in_line.lstrip(" \t"))]
            foreach_indent = line_indent + " " * indent_size
            inline_where = re.match(
                r"(?i)^([ \t]*)WHERE([ \t]+)(.+\bIN)$", in_line
            )
            if inline_where is not None:
                in_line_start = line_start if same_line else previous_line_start
                where_gap_start = in_line_start + inline_where.start(2)
                where_gap_end = in_line_start + inline_where.end(2)
                condition_indent = line_indent + " " * indent_size
                where_replacement = "\n" + condition_indent
                if content[where_gap_start:where_gap_end] != where_replacement:
                    violations.append({
                        "line": token["line"],
                        "start_offset": where_gap_start,
                        "end_offset": where_gap_end,
                        "replacement": where_replacement,
                        "message": "A WHERE condition continued by foreach should start on its own line.",
                    })
                foreach_indent = condition_indent + " " * indent_size
            foreach_replacement = gap_replacement_prefix + foreach_indent
            if content[gap_start:token["start"]] != foreach_replacement:
                violations.append({
                    "line": token["line"],
                    "start_offset": gap_start,
                    "end_offset": token["start"],
                    "replacement": foreach_replacement,
                    "message": "MyBatis foreach continuation should start on the line after IN.",
                })

        dynamic_join_modifier = re.compile(
            r"(?im)^([ \t]*)<if\b[^>\n]*>\s*"
            r"(?:LEFT|RIGHT|FULL|INNER|CROSS)\s*</if>([ \t]+)(?=JOIN\b)"
        )
        for match in dynamic_join_modifier.finditer(content):
            if not any(start < match.start() < end for start, end in query_ranges):
                continue
            violations.append({
                "line": content.count("\n", 0, match.start()) + 1,
                "start_offset": match.start(2),
                "end_offset": match.end(2),
                "replacement": "\n" + match.group(1),
                "message": "A JOIN controlled by a dynamic modifier should start on its own line.",
            })

        # Source-mapped SQL can contain repeated CASE branches on opposite
        # sides of dynamic tags. Keep boolean continuations anchored to their
        # WHEN line even when the embedded diff cannot identify the repeated
        # whitespace span unambiguously.
        active_case_indent = None
        case_continuation_lines = set()
        case_line_starts = [0]
        case_line_starts.extend(
            offset + 1 for offset, char in enumerate(content) if char == "\n"
        )
        for line_index, line_text in enumerate(lines):
            line_start = case_line_starts[line_index]
            if not any(start < line_start < end for start, end in query_ranges):
                active_case_indent = None
                continue
            stripped = line_text.strip()
            if not stripped or stripped.startswith("<"):
                continue
            upper = stripped.upper()
            actual_indent = line_text[: len(line_text) - len(line_text.lstrip(" \t"))]
            if upper.startswith("WHEN "):
                active_case_indent = (
                    None if " THEN " in f" {upper} " else actual_indent
                )
                continue
            if active_case_indent is None:
                continue
            if upper.startswith(("AND ", "OR ")):
                case_continuation_lines.add(line_index + 1)
                expected_indent = active_case_indent + " " * indent_size
                if actual_indent != expected_indent:
                    violations.append({
                        "line": line_index + 1,
                        "start_offset": line_start,
                        "end_offset": line_start + len(actual_indent),
                        "replacement": expected_indent,
                        "message": "Multiline CASE conditions should align one indent beyond WHEN.",
                    })
                continue
            if upper.startswith(("THEN ", "ELSE", "END", "WHEN ")):
                active_case_indent = None

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
        line_is_inside_query = {}

        for i, t in enumerate(tokens):
            line = t["line"]
            val = t.get("value", "")
            end_line = line + val.count('\n')
            
            # Record delta at start of line and all spanned lines for multiline tokens
            for l in range(line, end_line + 1):
                if l not in line_cumulative_delta:
                    query_el = None
                    for el in reversed(tag_stack):
                        if el["tag"] in ("select", "insert", "update", "delete", "sql"):
                            query_el = el
                            break
                    
                    if query_el is not None:
                        # SQL indentation is owned by the embedded SQL rules.
                        # Moving a query tag must not shift every text line in
                        # its body and then fight the SQL formatter next pass.
                        delta = 0
                    else:
                        delta = 0
                        for el in reversed(tag_stack):
                            if el.get("delta") is not None:
                                delta = el["delta"]
                                break
                    line_cumulative_delta[l] = delta
                    
                    line_is_inside_query[l] = query_el is not None
                    
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
                    line_min_parent_indent[l] = min_parent_indent

            if t["type"] == "TEXT" and t["value"].strip():
                dynamic_parent = next(
                    (
                        parent
                        for parent in reversed(tag_stack)
                        if parent["tag"] in {
                            "if", "foreach", "choose", "when", "otherwise",
                            "trim", "where", "set",
                        }
                    ),
                    None,
                )
                if dynamic_parent is not None:
                    parent_indent = dynamic_parent.get("resolved_indent")
                    if parent_indent is None:
                        parent_line = lines[dynamic_parent["token"]["line"] - 1]
                        parent_indent = parent_line[: len(parent_line) - len(parent_line.lstrip(" \t"))]
                    minimum_indent = parent_indent + " " * indent_size
                    token_line_start = content.rfind("\n", 0, t["start"]) + 1
                    starts_inline = bool(
                        content[token_line_start:t["start"]].strip()
                    )
                    for text_line in range(line, end_line + 1):
                        if text_line < 1 or text_line > len(lines):
                            continue
                        text_line_start = line_starts[text_line - 1]
                        line_text = lines[text_line - 1]
                        if not line_text.strip() or line_text.lstrip().startswith("<"):
                            continue
                        if text_line == line and starts_inline:
                            # The dynamic tag starts in an existing SQL line;
                            # its text must not redefine that whole line's
                            # indentation.
                            continue
                        actual_indent = line_text[: len(line_text) - len(line_text.lstrip(" \t"))]
                        first_word = line_text.strip().split(None, 1)[0].upper()
                        is_bind_body = line_text.strip().startswith(("#{", "${", ":"))
                        is_logical_continuation = first_word in {"AND", "OR"}
                        open_parenthesis_depth = 0
                        has_local_logical_clause = False
                        if is_logical_continuation:
                            opening_tag_end = content.find(
                                ">", dynamic_parent["token"]["start"]
                            )
                            if 0 <= opening_tag_end < text_line_start:
                                prefix_tokens = tokenize_sql(
                                    content[opening_tag_end + 1:text_line_start]
                                )
                                has_local_logical_clause = any(
                                    item["type"] == "KEYWORD"
                                    and item["value"].upper() in {"WHERE", "ON", "HAVING"}
                                    for item in prefix_tokens
                                )
                                open_parenthesis_depth = sum(
                                    1 if item["value"] == "(" else -1
                                    for item in prefix_tokens
                                    if item["type"] == "PAREN"
                                )
                        malformed_dynamic_indent = (
                            len(actual_indent) % indent_size != 0
                        )
                        if (
                            is_bind_body
                            or (
                                is_logical_continuation
                                and text_line not in case_continuation_lines
                                and open_parenthesis_depth <= 0
                                and not has_local_logical_clause
                                and actual_indent != minimum_indent
                            )
                            or malformed_dynamic_indent
                            or len(actual_indent) < len(minimum_indent)
                        ):
                            explicit_expected_indent[text_line] = minimum_indent

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
                if idx in line_min_parent_indent and not line_is_inside_query.get(idx, False):
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
        try:
            for el in elements:
                if el["tag"] in ("mapper", "select", "insert", "update", "delete", "sql"):
                    continue
                if not el["inner_tokens"]:
                    continue
                has_child_tags = any(t["type"] == "TAG_OPEN_START" for t in el["inner_tokens"])
                if has_child_tags:
                    continue
                
                # Check if it's on multiple lines originally
                start_line_number = content.count("\n", 0, el["start_offset"]) + 1
                end_line_number = content.count("\n", 0, el["end_offset"]) + 1
                start_offset = el["start_offset"]
                end_offset = el["end_offset"]
                
                first_inner = el["inner_tokens"][0]["start"]
                last_inner = el["inner_tokens"][-1]["end"]
                
                opening_tag = content[start_offset:first_inner]
                inner_text = content[first_inner:last_inner]
                closing_tag = content[last_inner:end_offset]
                inner_lines = [
                    line.strip()
                    for line in inner_text.splitlines()
                    if line.strip()
                ]
                if start_line_number == end_line_number:
                    continue
                if el["tag"] in {"if", "when", "otherwise"} and len(inner_lines) > 1:
                    continue
                
                collapsed = opening_tag.strip() + inner_text.strip() + closing_tag.strip()
                
                # Resolve indent from start_line
                start_line_idx = start_line_number - 1
                expected_indent = explicit_expected_indent.get(start_line_number)
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
                        "line": start_line_number,
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
            
        structural_spans = [
            (item["start_offset"], item["end_offset"])
            for item in violations
            if item.get("structural")
        ]
        if structural_spans:
            violations = [
                item
                for item in violations
                if item.get("structural")
                or not any(
                    start <= item["start_offset"] < end
                    for start, end in structural_spans
                )
            ]
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
            
        edits_by_range = {}
        for item in offending:
            key = (item["start_offset"], item["end_offset"])
            edits_by_range.setdefault(key, item["replacement"])
        edits = [
            (start, end, replacement)
            for (start, end), replacement in edits_by_range.items()
        ]
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
