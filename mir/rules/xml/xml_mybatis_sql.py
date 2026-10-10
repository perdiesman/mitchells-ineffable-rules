from bisect import bisect_right
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.rules_loader import load_rules_for_language
from mir.rules.xml.xml_utils import tokenize_xml
from mir.engine.embedded_bridge import check_embedded_content, fix_embedded_content


def mapped_offsets_in_ranges(mapping: List[int], ranges: List[tuple]) -> set[int]:
    if not ranges:
        return set()
    ordered = sorted(ranges)
    starts = [start for start, _ in ordered]
    result = set()
    for index, source_offset in enumerate(mapping):
        range_index = bisect_right(starts, source_offset) - 1
        if range_index >= 0 and source_offset < ordered[range_index][1]:
            result.add(index)
    return result


def mapping_boundary_offsets(
    mapping: List[int], tag_ranges: List[tuple]
) -> set[int]:
    if not tag_ranges:
        return set()
    ordered = sorted(tag_ranges)
    starts = [start for start, _ in ordered]
    result = set()
    for index in range(1, len(mapping)):
        previous = mapping[index - 1]
        current = mapping[index]
        if current <= previous + 1:
            continue
        range_index = bisect_right(starts, previous) - 1
        if range_index >= 0 and ordered[range_index][1] > previous:
            result.add(index)
            continue
        next_index = range_index + 1
        if next_index < len(ordered) and ordered[next_index][0] < current:
            result.add(index)
    return result

def parse_xml_elements(tokens: List[dict]) -> List[dict]:
    """Build the XML element tree in one token pass.

    Element token indexes remain relative to the original document.  The old
    recursive slice parser repeatedly rescanned large mapper bodies and gave
    nested elements slice-relative indexes that callers treated as global.
    """
    roots = []
    stack = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token["type"] == "TAG_OPEN_START":
            tag_end = index + 1
            attrs = {}
            while tag_end < len(tokens) and tokens[tag_end]["type"] != "TAG_END":
                current = tokens[tag_end]
                if current["type"] == "ATTR_NAME":
                    value_index = tag_end + 2
                    if (
                        value_index < len(tokens)
                        and tokens[tag_end + 1]["type"] == "EQUAL"
                        and tokens[value_index]["type"] == "ATTR_VALUE"
                    ):
                        value = tokens[value_index]["value"]
                        if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
                            value = value[1:-1]
                        attrs[current["value"]] = value
                tag_end += 1
            if tag_end >= len(tokens):
                break
            frame = {
                "tag": token["value"][1:].lower(),
                "attrs": attrs,
                "start_idx": index,
                "open_end_idx": tag_end,
                "children": [],
                "start_offset": token["start"],
            }
            if tokens[tag_end]["value"] == "/>":
                frame.update({
                    "end_idx": tag_end,
                    "inner_tokens": [],
                    "end_offset": tokens[tag_end]["end"],
                })
                (stack[-1]["children"] if stack else roots).append(frame)
            else:
                stack.append(frame)
            index = tag_end
        elif token["type"] == "TAG_CLOSE_START" and stack:
            close_name = token["value"][2:].lower()
            close_end = index + 1
            while close_end < len(tokens) and tokens[close_end]["type"] != "TAG_END":
                close_end += 1
            if close_end < len(tokens) and stack[-1]["tag"] == close_name:
                frame = stack.pop()
                frame.update({
                    "end_idx": close_end,
                    "inner_tokens": tokens[frame["open_end_idx"] + 1:index],
                    "end_offset": tokens[close_end]["end"],
                })
                (stack[-1]["children"] if stack else roots).append(frame)
                index = close_end
        index += 1
    return roots

def get_all_elements_recursively(elements: List[dict]) -> List[dict]:
    res = []
    for el in elements:
        res.append(el)
        res.extend(get_all_elements_recursively(el.get("children", [])))
    return res


def _tokens_start_with_select(tokens: List[dict]) -> bool:
    """Return whether a dynamic branch starts with a complete SELECT."""
    for token in tokens:
        if token["type"] in {"TEXT", "WHITESPACE"}:
            stripped = token["value"].lstrip()
            if stripped:
                return stripped.upper().startswith("SELECT")
        elif token["type"] == "TAG_OPEN_START":
            return False
    return False


def _next_dynamic_body_starts_select(
    tokens: List[dict], start_index: int
) -> bool:
    index = start_index
    while index < len(tokens):
        token = tokens[index]
        if token["type"] == "WHITESPACE" or (
            token["type"] == "TEXT" and not token["value"].strip()
        ):
            index += 1
            continue
        break
    if index >= len(tokens) or tokens[index]["type"] != "TAG_OPEN_START":
        return False
    tag_name = tokens[index]["value"][1:].lower()
    if tag_name not in {"if", "when", "otherwise"}:
        return False
    tag_end = index + 1
    while tag_end < len(tokens) and tokens[tag_end]["type"] != "TAG_END":
        tag_end += 1
    if tag_end >= len(tokens) or tokens[tag_end]["value"] == "/>":
        return False
    return _tokens_start_with_select(tokens[tag_end + 1 :])

def expand_tokens(inner_tokens: List[dict], sql_defs: Dict[str, List[dict]], expanded_chars: List[str], mapping: List[int], is_after_tag: List[bool], state: dict = None):
    if state is None:
        state = {
            "last_tag_line": -1,
            "last_tag_type": None,
            "dynamic_depth": 0,
        }
    n_tok = len(inner_tokens)
    i = 0
    while i < n_tok:
        tok = inner_tokens[i]
        
        if tok["type"] == "TAG_OPEN_START" and tok["value"][1:].lower() == "include":
            tag_end_idx = -1
            refid = None
            j = i + 1
            while j < n_tok:
                if inner_tokens[j]["type"] == "TAG_END":
                    tag_end_idx = j
                    break
                if inner_tokens[j]["type"] == "ATTR_NAME" and inner_tokens[j]["value"] == "refid":
                    if j + 2 < n_tok and inner_tokens[j+1]["type"] == "EQUAL" and inner_tokens[j+2]["type"] == "ATTR_VALUE":
                        refid = inner_tokens[j+2]["value"]
                        if len(refid) >= 2 and refid[0] in ("'", '"') and refid[-1] == refid[0]:
                            refid = refid[1:-1]
                j += 1
                
            if tag_end_idx != -1:
                state["last_tag_line"] = inner_tokens[tag_end_idx]["line"]
                state["last_tag_type"] = "include"
                if refid:
                    short_refid = refid.split(".")[-1]
                    matched_tokens = None
                    if refid in sql_defs:
                        matched_tokens = sql_defs[refid]
                    elif short_refid in sql_defs:
                        matched_tokens = sql_defs[short_refid]
                        
                    if matched_tokens:
                        expand_tokens(matched_tokens, sql_defs, expanded_chars, mapping, is_after_tag, state)
                    else:
                        refid_lower = refid.lower()
                        if "column" in refid_lower or "col" in refid_lower or "list" in refid_lower:
                            placeholder = "dummy_column"
                        elif "where" in refid_lower or "clause" in refid_lower or "cond" in refid_lower or "example" in refid_lower:
                            placeholder = "1 = 1"
                        else:
                            placeholder = "1 = 1"
                            
                        for char in placeholder:
                            expanded_chars.append(char)
                            mapping.append(tok["start"])
                            is_after_tag.append(False)
                i = tag_end_idx + 1
                continue
                
        if tok["type"] in ("TEXT", "WHITESPACE"):
            val = tok["value"]
            start_offset = tok["start"]
            start_line = tok["line"] - val.count('\n')
            
            # Fast path for tokens without entities
            if not any(ent in val for ent in ("&gt;", "&lt;", "&amp;", "&quot;", "&apos;")):
                len_val = len(val)
                expanded_chars.extend(val)
                mapping.extend(range(start_offset, start_offset + len_val))

                inside_dynamic = state.get("dynamic_depth", 0) > 0
                boundary_active = state["last_tag_type"] in (
                    "if", "choose", "when", "otherwise", "include", "case"
                )
                for char in val:
                    is_after_tag.append(inside_dynamic or boundary_active)
                    if char not in " \t\r\n," and boundary_active:
                        boundary_active = False
                        state["last_tag_type"] = None
                
                i += 1
                continue

            entity_map = {
                "&gt;": ">",
                "&lt;": "<",
                "&amp;": "&",
                "&quot;": '"',
                "&apos;": "'"
            }
            
            offset_in_val = 0
            len_val = len(val)
            while offset_in_val < len_val:
                matched_entity = None
                for ent, dec in entity_map.items():
                    if val[offset_in_val:offset_in_val + len(ent)] == ent:
                        matched_entity = (ent, dec)
                        break
                        
                if matched_entity:
                    ent_str, dec_char = matched_entity
                    expanded_chars.append(dec_char)
                    mapping.append(start_offset + offset_in_val)
                    
                    after = state.get("dynamic_depth", 0) > 0
                    if state["last_tag_type"] in ("if", "choose", "when", "otherwise", "include", "case"):
                        char_line = start_line + val[:offset_in_val].count('\n')
                        if char_line <= state["last_tag_line"] + 1:
                            after = True
                    is_after_tag.append(after)
                    
                    if dec_char not in " \t\r\n," and after:
                        state["last_tag_type"] = None
                        
                    offset_in_val += len(ent_str)
                else:
                    char = val[offset_in_val]
                    expanded_chars.append(char)
                    mapping.append(start_offset + offset_in_val)
                    
                    after = state.get("dynamic_depth", 0) > 0
                    if state["last_tag_type"] in ("if", "choose", "when", "otherwise", "include", "case"):
                        char_line = start_line + val[:offset_in_val].count('\n')
                        if char_line <= state["last_tag_line"] + 1:
                            after = True
                    is_after_tag.append(after)
                    
                    if char not in " \t\r\n," and after:
                        state["last_tag_type"] = None
                        
                    offset_in_val += 1
            i += 1
            continue
            
        if tok["type"] == "TAG_OPEN_START":
            tag_name = tok["value"][1:].lower()
            tag_end_idx = -1
            
            attrs = {}
            j = i + 1
            while j < n_tok:
                if inner_tokens[j]["type"] == "TAG_END":
                    tag_end_idx = j
                    break
                if inner_tokens[j]["type"] == "ATTR_NAME":
                    if j + 2 < n_tok and inner_tokens[j+1]["type"] == "EQUAL" and inner_tokens[j+2]["type"] == "ATTR_VALUE":
                        attr_val = inner_tokens[j+2]["value"]
                        if len(attr_val) >= 2 and attr_val[0] in ("'", '"') and attr_val[-1] == attr_val[0]:
                            attr_val = attr_val[1:-1]
                        attrs[inner_tokens[j]["value"].lower()] = attr_val
                j += 1
                
            if tag_end_idx != -1:
                is_self_closing = inner_tokens[tag_end_idx]["value"] == "/>"
                if is_self_closing:
                    state["last_tag_line"] = inner_tokens[tag_end_idx]["line"]
                    state["last_tag_type"] = tag_name
                    i = tag_end_idx + 1
                    continue
                    
                depth = 1
                close_idx = -1
                k = tag_end_idx + 1
                while k < n_tok:
                    if inner_tokens[k]["type"] == "TAG_OPEN_START":
                        if inner_tokens[k]["value"][1:].lower() == tag_name:
                            depth += 1
                    elif inner_tokens[k]["type"] == "TAG_CLOSE_START":
                        if inner_tokens[k]["value"][2:].lower() == tag_name:
                            depth -= 1
                            if depth == 0:
                                close_idx = k
                                break
                    k += 1
                    
                if close_idx != -1:
                    state["last_tag_line"] = inner_tokens[tag_end_idx]["line"]
                    state["last_tag_type"] = tag_name
                    
                    prefix_to_add = None
                    if tag_name == "where":
                        prefix_to_add = "WHERE "
                    elif tag_name == "set":
                        prefix_to_add = "SET "
                    elif tag_name == "trim":
                        prefix = attrs.get("prefix", "").strip().upper()
                        if prefix in ("WHERE", "SET"):
                            prefix_to_add = prefix + " "
                            
                    if prefix_to_add:
                        for char in prefix_to_add:
                            expanded_chars.append(char)
                            mapping.append(tok["start"])
                            is_after_tag.append(False)
                            
                    dynamic_tags = {
                        "if", "foreach", "choose", "when", "otherwise",
                        "trim", "where", "set",
                    }
                    if tag_name in dynamic_tags:
                        state["dynamic_depth"] = state.get("dynamic_depth", 0) + 1
                    expand_tokens(inner_tokens[tag_end_idx + 1 : close_idx], sql_defs, expanded_chars, mapping, is_after_tag, state)
                    if tag_name in dynamic_tags:
                        state["dynamic_depth"] -= 1
                    close_end_idx = -1
                    for m in range(close_idx + 1, n_tok):
                        if inner_tokens[m]["type"] == "TAG_END":
                            close_end_idx = m
                            break
                    if close_end_idx != -1:
                        body_tokens = inner_tokens[tag_end_idx + 1 : close_idx]
                        if (
                            tag_name in {"if", "when", "otherwise"}
                            and _tokens_start_with_select(body_tokens)
                            and _next_dynamic_body_starts_select(
                                inner_tokens, close_end_idx + 1
                            )
                        ):
                            # Adjacent mutually exclusive query branches are
                            # invalid SQL when simply concatenated.  A
                            # source-unmappable separator lets guest rules
                            # parse each complete SELECT independently.  The
                            # same synthetic token participates in all
                            # protected-signature checks and can never be
                            # written across the XML tag boundary.
                            for char in ";\n":
                                expanded_chars.append(char)
                                mapping.append(inner_tokens[close_end_idx]["start"])
                                is_after_tag.append(True)
                        # Punctuation after a dynamic block belongs to the
                        # surrounding MyBatis structure. Mark it as crossing
                        # a tag boundary so SQL rules such as comma-style do
                        # not move it into text on the other side of the tag.
                        state["last_tag_line"] = inner_tokens[close_end_idx]["line"]
                        state["last_tag_type"] = tag_name
                        i = close_end_idx + 1
                        continue
        i += 1
def get_element_base_indent(el: dict, tokens: List[dict], content: str, rule_config: Dict[str, Any]) -> str:
    tag_start_offset = el.get("start_offset", 0)
    line_start = content.rfind("\n", 0, tag_start_offset) + 1
    tag_line_prefix = content[line_start:tag_start_offset]
    tag_indent = ""
    for char in tag_line_prefix:
        if char in (" ", "\t"):
            tag_indent += char
        else:
            break
            
    xml_indent_config = rule_config.get("_all_configs", {}).get("IR-xml-indent", {})
    if isinstance(xml_indent_config, bool):
        xml_indent_size = 4
    else:
        xml_indent_size = xml_indent_config.get("indent_size", 4)
        
    return tag_indent + " " * xml_indent_size


def get_dynamic_indent_ranges(
    elements: List[dict], content: str, rule_config: Dict[str, Any]
) -> List[tuple]:
    xml_indent_config = rule_config.get("_all_configs", {}).get("IR-xml-indent", {})
    indent_size = (
        4
        if isinstance(xml_indent_config, bool)
        else xml_indent_config.get("indent_size", 4)
    )
    dynamic_tags = {
        "if", "foreach", "choose", "when", "otherwise", "trim", "where", "set",
    }
    ranges = []
    for element in elements:
        if element["tag"] not in dynamic_tags:
            continue
        line_start = content.rfind("\n", 0, element["start_offset"]) + 1
        prefix = content[line_start:element["start_offset"]]
        parent_indent = len(prefix) - len(prefix.lstrip(" \t"))
        ranges.append((
            element["start_offset"],
            element["end_offset"],
            parent_indent + indent_size,
        ))
    return ranges


def get_mybatis_protected_signatures(
    content: str, target: tuple[str, str] | None = None
) -> tuple:
    """Describe protected SQL syntax for embedded MyBatis statements.

    ``target`` limits expansion to one ``(tag, id)`` pair.  Source-mapping
    validation calls this once per changed statement; expanding every other
    mapper statement there made large files effectively quadratic.
    """
    from mir.rules.sql.sql_utils import protected_sql_signature

    tokens = tokenize_xml(content)
    elements = get_all_elements_recursively(parse_xml_elements(tokens))
    sql_defs = {}
    for element in elements:
        if element["tag"] == "sql" and "id" in element["attrs"]:
            sql_id = element["attrs"]["id"]
            sql_defs[sql_id] = element["inner_tokens"]
            if "." in sql_id:
                sql_defs[sql_id.split(".")[-1]] = element["inner_tokens"]

    signatures = []
    target_tags = {"select", "insert", "update", "delete", "sql"}
    for element in elements:
        if element["tag"] not in target_tags or "id" not in element["attrs"]:
            continue
        statement_key = (element["tag"], element["attrs"]["id"])
        if target is not None and statement_key != target:
            continue
        expanded_chars = []
        mapping = []
        is_after_tag = []
        expand_tokens(
            element["inner_tokens"], sql_defs, expanded_chars, mapping, is_after_tag
        )
        signatures.append((
            element["tag"],
            element["attrs"]["id"],
            protected_sql_signature("".join(expanded_chars)),
        ))
    return tuple(signatures)


def get_mybatis_fragment_protected_signature(
    fragment: str,
    sql_defs: Dict[str, List[dict]],
    target: tuple[str, str],
):
    """Return one statement signature without reparsing its whole mapper."""
    from mir.rules.sql.sql_utils import protected_sql_signature

    tokens = tokenize_xml(fragment)
    elements = get_all_elements_recursively(parse_xml_elements(tokens))
    target_tag, target_id = target
    element = next(
        (
            item
            for item in elements
            if item["tag"] == target_tag and item["attrs"].get("id") == target_id
        ),
        None,
    )
    if element is None:
        return None
    expanded_chars = []
    mapping = []
    is_after_tag = []
    expand_tokens(
        element["inner_tokens"],
        sql_defs,
        expanded_chars,
        mapping,
        is_after_tag,
    )
    return protected_sql_signature("".join(expanded_chars))


def dynamic_column_layout_edits(
    sql_text: str,
    mapping: List[int],
    boundary_offsets: set[int],
    tag_ranges: List[tuple[int, int]],
    dynamic_ranges: List[tuple[int, int, int]],
    content: str,
    rule_config: dict,
) -> List[tuple[int, int, str]]:
    """Map safe multiline dynamic column indentation straight to XML.

    Dynamic tags are absent from the expanded SQL document, so a normal text
    diff cannot reliably place structural column-list edits in a large mapper
    with repeated expressions. This helper changes only source-contiguous
    whitespace and leaves every SQL and XML token in place.
    """
    from mir.rules.sql.column_layout import ColumnLayoutRule
    from mir.rules.sql.line_length import LineLengthRule
    from mir.rules.sql.sql_utils import source_text_length

    column_rule = ColumnLayoutRule()
    clauses = column_rule._parse_clauses(sql_text)
    max_length = column_rule.get_config_value(
        rule_config,
        "max_length",
        default_value=120,
        fallbacks=[(LineLengthRule, "max_length")],
    )
    indent_size = column_rule.get_config_value(
        rule_config,
        "indent_size",
        default_value=4,
    )
    edits: List[tuple[int, int, str]] = []

    def source_span(guest_start: int, guest_end: int):
        if guest_start >= guest_end or guest_end > len(mapping):
            return None
        if any(
            mapping[index] - mapping[index - 1] != 1
            for index in range(guest_start + 1, guest_end)
        ):
            return None
        return mapping[guest_start], mapping[guest_end - 1] + 1

    for clause in clauses:
        if not clause["keyword"].startswith(
            ("SELECT", "GROUP BY", "ORDER BY")
        ):
            continue
        points = sorted(
            offset
            for offset in boundary_offsets
            if clause["list_start"] <= offset < clause["list_end"]
        )
        if not points:
            continue
        # Every transition must follow an existing comma. This accepts an
        # optional group of complete list items and rejects mutually exclusive
        # branches whose expanded expressions sit beside one another.
        comma_boundaries = 0
        for offset in points:
            cursor = offset - 1
            while cursor >= clause["list_start"] and sql_text[cursor].isspace():
                cursor -= 1
            if cursor >= clause["list_start"] and sql_text[cursor] == ",":
                comma_boundaries += 1
        # A boundary immediately after a comma proves that the dynamic block
        # contributes complete list items. Other points may be the close/open
        # transition between mutually exclusive blocks and need not themselves
        # follow commas.
        if not comma_boundaries or not clause["expression_ranges"]:
            continue

        prefix = column_rule._format_prefix(
            clause, max_length, indent_size, 0
        )
        single_line = f"{prefix} {', '.join(clause['expressions'])}"
        fits_single_line = source_text_length(
            clause["indentation"] + single_line, rule_config
        ) <= max_length
        dynamic_group_is_already_multiline = (
            clause["keyword"].startswith("GROUP BY")
            and "\n" in sql_text[clause["keyword_start"]:clause["list_end"]]
        )
        if fits_single_line and not dynamic_group_is_already_multiline:
            continue

        inner_indent = clause["indentation"] + (" " * indent_size)
        ranges = clause["expression_ranges"]
        for index, (guest_start, guest_end) in enumerate(ranges):
            source_start = mapping[guest_start]
            if any(
                start < source_start < end
                for start, end, _ in dynamic_ranges
            ):
                continue
            line_start = content.rfind("\n", 0, source_start) + 1
            prefix_text = content[line_start:source_start]
            if not prefix_text.strip():
                if prefix_text != inner_indent:
                    edits.append((line_start, source_start, inner_indent))
                continue

            separator_start = (
                clause["keyword_end"]
                if index == 0
                else ranges[index - 1][1] + 1
            )
            span = source_span(separator_start, guest_start)
            if span is None:
                continue
            source_separator = content[span[0]:span[1]]
            if source_separator.strip():
                continue
            edits.append((span[0], span[1], "\n" + inner_indent))

    return edits


def dynamic_sql_indent_source_edits(
    sql_text: str,
    mapping: List[int],
    tag_ranges: List[tuple[int, int]],
    dynamic_ranges: List[tuple[int, int, int]],
    rule_config: dict,
) -> List[tuple[int, int, str]]:
    """Map source-contiguous SQL indentation fixes without a text diff."""
    from mir.rules.sql.from_multi import FromMultiRule
    from mir.rules.sql.join_on_multi import JoinOnMultiRule

    edits = []
    items = []
    for rule in (FromMultiRule(), JoinOnMultiRule()):
        active_config = rule_config
        if isinstance(rule, FromMultiRule):
            active_config = dict(rule_config)
            # The host mapper below accepts indentation-only edits, so it can
            # safely see an optional JOIN beyond a tag boundary when deciding
            # that the FROM entry itself needs one continuation level.
            active_config["mybatis_boundary_offsets"] = set()
        items.extend(
            (rule, item)
            for item in rule._find_violations(sql_text, active_config)
        )
    for source_rule, item in items:
        guest_start = item["ws_start"]
        guest_end = item["ws_end"]
        original_whitespace = sql_text[guest_start:guest_end]
        replacement = item["replacement"]
        if (original_whitespace and not original_whitespace.isspace()) or (
            replacement and not replacement.isspace()
        ):
            continue
        if guest_start > guest_end or guest_end > len(mapping):
            continue
        if any(
            mapping[index] - mapping[index - 1] != 1
            for index in range(guest_start + 1, guest_end)
        ):
            continue
        if guest_start == guest_end:
            if guest_start >= len(mapping):
                continue
            source_start = mapping[guest_start]
            source_end = source_start
        else:
            source_start = mapping[guest_start]
            source_end = mapping[guest_end - 1] + 1
        if any(
            max(source_start, tag_start) < min(source_end, tag_end)
            for tag_start, tag_end in tag_ranges
        ):
            continue
        indentation_only = (
            original_whitespace.count("\n")
            == replacement.count("\n")
        )
        if (
            isinstance(source_rule, FromMultiRule)
            and not indentation_only
            and any(
            range_start < source_start < range_end
            or range_start < source_end < range_end
            for range_start, range_end, _ in dynamic_ranges
            )
        ):
            continue
        dynamic_indent = max(
            (
                expected_indent
                for range_start, range_end, expected_indent in dynamic_ranges
                if range_start < source_end <= range_end
            ),
            default=0,
        )
        if "\n" in replacement and dynamic_indent:
            head, tail = replacement.rsplit("\n", 1)
            if not tail.strip() and len(tail) < dynamic_indent:
                replacement = head + "\n" + (" " * dynamic_indent)
        edits.append(
            (source_start, source_end, replacement)
        )
    return edits


def dynamic_subquery_source_edits(
    sql_text: str,
    mapping: List[int],
    content: str,
    rule_config: dict,
) -> List[tuple[int, int, str]]:
    """Map indentation-only subquery repairs to their exact XML lines."""
    from mir.rules.sql.subquery_indent import SubqueryIndentRule
    from mir.rules.sql.sql_utils import (
        find_matching_paren,
        get_token_depths,
        tokenize_sql,
    )

    rule = SubqueryIndentRule()
    lines = sql_text.splitlines(keepends=True)
    line_offsets = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line)

    dynamic_offsets = rule_config.get("mybatis_dynamic_offsets", set())
    dynamic_source_ranges = rule_config.get(
        "mybatis_dynamic_indent_ranges", []
    )

    def is_dynamic_source_offset(guest_offset: int) -> bool:
        if not (0 <= guest_offset < len(mapping)):
            return False
        source_offset = mapping[guest_offset]
        return any(
            range_start < source_offset < range_end
            for range_start, range_end, _ in dynamic_source_ranges
        )

    edits = []
    scan_config = dict(rule_config)
    scan_config.pop("source_mapped_subquery_compaction", None)
    for item in rule._find_violations(sql_text, scan_config):
        if item.get("type") == "compact_join_opener":
            continue
        if item.get("type") == "compact_subquery":
            guest_start = item["ws_start"]
            guest_end = item["ws_end"]
            if not (0 <= guest_start < guest_end <= len(mapping)):
                continue
            if any(
                mapping[index] - mapping[index - 1] != 1
                for index in range(guest_start + 1, guest_end)
            ):
                continue
            source_start = mapping[guest_start]
            source_end = mapping[guest_end - 1] + 1
            source_line_start = content.rfind("\n", 0, source_start) + 1
            source_line_end = content.find("\n", source_end)
            if source_line_end == -1:
                source_line_end = len(content)
            candidate = (
                content[source_line_start:source_start]
                + item["replacement"]
                + content[source_end:source_line_end]
            )
            from mir.rules.sql.line_length import LineLengthRule

            max_length = LineLengthRule().get_config_value(
                rule_config,
                "max_length",
                default_value=120,
            )
            if len(candidate) <= max_length:
                edits.append((source_start, source_end, item["replacement"]))
            continue
        if item["first_sub_tok"]["line"] == item["open_tok"]["line"]:
            continue
        open_guest_offset = item["open_tok"]["start"]
        source_indent_delta = 0
        if open_guest_offset < len(mapping):
            source_open = mapping[open_guest_offset]
            source_open_line = content.rfind("\n", 0, source_open) + 1
            source_prefix = content[source_open_line:source_open]
            source_indent = len(source_prefix) - len(source_prefix.lstrip(" \t"))
            guest_open_line = sql_text.rfind("\n", 0, open_guest_offset) + 1
            guest_prefix = sql_text[guest_open_line:open_guest_offset]
            guest_indent = len(guest_prefix) - len(guest_prefix.lstrip(" \t"))
            source_indent_delta = max(0, source_indent - guest_indent)
        start_line = item["open_line"] + 1
        close_line = item["close_line"]
        clause_lines = item["clause_lines"]
        for line_number in range(start_line, close_line + 1):
            raw_line = lines[line_number - 1].rstrip("\r\n")
            if not raw_line.strip():
                continue
            body = raw_line.lstrip(" \t")
            guest_indent = raw_line[: len(raw_line) - len(body)]
            if line_number == close_line:
                expected = item["close_indent"] + (" " * source_indent_delta)
            elif line_number in clause_lines:
                expected = item["content_indent"] + (" " * source_indent_delta)
            elif guest_indent.startswith(item["content_indent"]):
                expected = guest_indent + (" " * source_indent_delta)
            else:
                expected = item["content_indent"] + (" " * source_indent_delta)
            guest_body_start = line_offsets[line_number - 1] + len(guest_indent)
            if guest_body_start >= len(mapping):
                continue
            if (
                (
                    guest_body_start in dynamic_offsets
                    or is_dynamic_source_offset(guest_body_start)
                )
                and not (
                    open_guest_offset in dynamic_offsets
                    or is_dynamic_source_offset(open_guest_offset)
                )
            ):
                continue
            source_body_start = mapping[guest_body_start]
            # Synthetic SQL separators and repeated fragment expansion can
            # make a guest line number point into the middle of its source
            # token.  Never treat that offset as indentation: doing so would
            # consume the first source character (for example SELECT ->
            # ELECT).  Exact character identity is required before changing
            # the source prefix.
            if (
                source_body_start >= len(content)
                or content[source_body_start] != sql_text[guest_body_start]
            ):
                continue
            source_line_start = content.rfind("\n", 0, source_body_start) + 1
            source_prefix = content[source_line_start:source_body_start]
            if source_prefix.strip():
                continue
            if source_prefix == expected:
                continue
            edits.append(
                (source_line_start, source_body_start, expected)
            )
    # Expanded SQL intentionally hides indentation contributed by XML tags.
    # Reassert the physical source relationship for clause anchors and the
    # closing parenthesis even when the guest view is already logically
    # aligned and therefore reports no violation.
    sql_tokens = tokenize_sql(sql_text)
    depths = get_token_depths(sql_tokens)
    clause_keywords = {
        "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "HAVING",
        "LIMIT", "UNION", "INTERSECT", "EXCEPT",
    }

    def source_indent_edit(guest_offset: int, expected: str):
        if not (0 <= guest_offset < len(mapping)):
            return
        source_offset = mapping[guest_offset]
        if source_offset >= len(content):
            return
        line_start = content.rfind("\n", 0, source_offset) + 1
        prefix = content[line_start:source_offset]
        if prefix.strip() or prefix == expected:
            return
        edits.append((line_start, source_offset, expected))

    for open_index, open_token in enumerate(sql_tokens):
        if open_token["type"] != "PAREN" or open_token["value"] != "(":
            continue
        close_index = find_matching_paren(sql_tokens, open_index)
        if close_index is None:
            continue
        select_index = next(
            (
                index
                for index in range(open_index + 1, close_index)
                if sql_tokens[index]["type"] not in {"WHITESPACE", "COMMENT"}
            ),
            None,
        )
        if (
            select_index is None
            or sql_tokens[select_index]["type"] != "KEYWORD"
            or sql_tokens[select_index]["value"].upper() != "SELECT"
            or sql_tokens[select_index]["line"]
            == sql_tokens[close_index]["line"]
            or open_token["start"] >= len(mapping)
        ):
            continue
        if (
            (
                sql_tokens[select_index]["start"] in dynamic_offsets
                or is_dynamic_source_offset(sql_tokens[select_index]["start"])
            )
            and not (
                open_token["start"] in dynamic_offsets
                or is_dynamic_source_offset(open_token["start"])
            )
        ):
            # A dynamic tag supplies an alternative SELECT inside an outer
            # CTE/derived-table parenthesis. Its extra source indentation is
            # XML nesting, not SQL subquery depth.
            continue
        source_open = mapping[open_token["start"]]
        source_line_start = content.rfind("\n", 0, source_open) + 1
        source_prefix = content[source_line_start:source_open]
        open_indent = source_prefix[: len(source_prefix) - len(source_prefix.lstrip(" \t"))]

        is_from_join = False
        for previous_index in range(open_index - 1, -1, -1):
            previous = sql_tokens[previous_index]
            if previous["line"] != open_token["line"]:
                break
            if previous["type"] in {"WHITESPACE", "COMMENT"}:
                continue
            if previous["type"] == "KEYWORD" and previous["value"].upper() == "LATERAL":
                continue
            is_from_join = bool(
                previous["type"] == "KEYWORD"
                and previous["value"].upper() in {"FROM", "JOIN"}
            )
            break

        close_indent = open_indent + ("    " if is_from_join else "")
        content_indent = close_indent + "    "
        subquery_depth = depths[select_index]
        for token_index in range(select_index, close_index):
            token = sql_tokens[token_index]
            if (
                depths[token_index] == subquery_depth
                and token["type"] == "KEYWORD"
                and token["value"].upper() in clause_keywords
            ):
                if (
                    (
                        token["start"] in dynamic_offsets
                        or is_dynamic_source_offset(token["start"])
                    )
                    and not (
                        open_token["start"] in dynamic_offsets
                        or is_dynamic_source_offset(open_token["start"])
                    )
                ):
                    # The outer CTE/derived-table parenthesis owns its static
                    # clauses, but a nested MyBatis branch owns the additional
                    # source indentation of clauses it contributes later in
                    # that same SQL depth (for example after UNION ALL).
                    continue
                source_indent_edit(token["start"], content_indent)
        source_indent_edit(sql_tokens[close_index]["start"], close_indent)

    edits_by_span = {}
    for start, end, replacement in edits:
        edits_by_span[(start, end)] = replacement
    return [
        (start, end, replacement)
        for (start, end), replacement in edits_by_span.items()
    ]


def dynamic_projection_subquery_source_edits(
    sql_text: str,
    mapping: List[int],
    content: str,
    dynamic_ranges: List[tuple[int, int, int]],
) -> List[tuple[int, int, str]]:
    """Anchor a derived query whose SELECT list crosses dynamic XML tags."""
    from mir.rules.sql.sql_utils import (
        find_matching_paren,
        get_token_depths,
        tokenize_sql,
    )

    tokens = tokenize_sql(sql_text)
    depths = get_token_depths(tokens)
    clause_keywords = {
        "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "HAVING",
        "LIMIT", "UNION", "INTERSECT", "EXCEPT",
    }
    edits = []

    def source_offset(guest_offset: int) -> int | None:
        if 0 <= guest_offset < len(mapping):
            return mapping[guest_offset]
        return None

    def inside_dynamic(source: int) -> bool:
        return any(start < source < end for start, end, _ in dynamic_ranges)

    def indent_edit(token: dict, expected: str) -> None:
        source = source_offset(token["start"])
        if source is None or inside_dynamic(source):
            return
        line_start = content.rfind("\n", 0, source) + 1
        prefix = content[line_start:source]
        if not prefix.strip():
            edits.append((line_start, source, expected))
            if token["value"].upper() == "FROM" and line_start > 0:
                previous_line_start = content.rfind(
                    "\n", 0, max(0, line_start - 1)
                ) + 1
                if not content[previous_line_start:line_start].strip():
                    edits.append((previous_line_start, line_start, ""))

    for open_index, opening in enumerate(tokens):
        if opening["type"] != "PAREN" or opening["value"] != "(":
            continue
        close_index = find_matching_paren(tokens, open_index)
        if close_index is None:
            continue
        select_index = next(
            (
                index
                for index in range(open_index + 1, close_index)
                if tokens[index]["type"] not in {"WHITESPACE", "COMMENT"}
            ),
            None,
        )
        if (
            select_index is None
            or tokens[select_index]["type"] != "KEYWORD"
            or tokens[select_index]["value"].upper() != "SELECT"
            or tokens[select_index]["line"] == tokens[close_index]["line"]
        ):
            continue
        subquery_depth = depths[select_index]
        first_from = next(
            (
                index
                for index in range(select_index + 1, close_index)
                if depths[index] == subquery_depth
                and tokens[index]["type"] == "KEYWORD"
                and tokens[index]["value"].upper() == "FROM"
            ),
            None,
        )
        if first_from is None:
            continue
        select_source = source_offset(tokens[select_index]["start"])
        from_source = source_offset(tokens[first_from]["start"])
        if select_source is None or from_source is None or not any(
            select_source < start < from_source
            for start, _, _ in dynamic_ranges
        ):
            continue

        open_source = source_offset(opening["start"])
        if open_source is None:
            continue
        line_start = content.rfind("\n", 0, open_source) + 1
        prefix = content[line_start:open_source]
        open_indent = prefix[: len(prefix) - len(prefix.lstrip(" \t"))]
        owner_is_relation = False
        for previous_index in range(open_index - 1, -1, -1):
            previous = tokens[previous_index]
            if previous["line"] != opening["line"]:
                break
            if previous["type"] in {"WHITESPACE", "COMMENT"}:
                continue
            if previous["type"] == "KEYWORD" and previous["value"].upper() == "LATERAL":
                continue
            owner_is_relation = bool(
                previous["type"] == "KEYWORD"
                and previous["value"].upper() in {"FROM", "JOIN"}
            )
            break
        close_indent = open_indent + ("    " if owner_is_relation else "")
        content_indent = close_indent + "    "
        for index in range(select_index, close_index):
            token = tokens[index]
            if (
                depths[index] == subquery_depth
                and token["type"] == "KEYWORD"
                and token["value"].upper() in clause_keywords
            ):
                indent_edit(token, content_indent)
        indent_edit(tokens[close_index], close_indent)

    return edits


def post_choose_clause_source_edits(
    content: str,
    source_range: tuple[int, int],
) -> List[tuple[int, int, str]]:
    """Anchor shared JOIN and clause lines after mutually exclusive sources."""
    import re

    start, end = source_range
    fragment = content[start:end]
    lines = fragment.splitlines(keepends=True)
    offsets = []
    offset = start
    for line in lines:
        offsets.append(offset)
        offset += len(line)

    join_pattern = re.compile(
        r"^(?:(?:LEFT|RIGHT|FULL|INNER|OUTER|CROSS|NATURAL)\s+)?JOIN\b",
        re.IGNORECASE,
    )
    clause_pattern = re.compile(
        r"^(?:WHERE|GROUP\s+BY|ORDER\s+BY|HAVING)\b",
        re.IGNORECASE,
    )
    edits: List[tuple[int, int, str]] = []
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        close_match = re.match(r"^([ \t]*)</choose>[ \t]*$", line)
        if close_match is None:
            continue
        base_indent = close_match.group(1)
        nesting = 1
        open_index = index - 1
        while open_index >= 0:
            body = lines[open_index].strip().lower()
            if body.startswith("</choose"):
                nesting += 1
            elif body.startswith("<choose"):
                nesting -= 1
                if nesting == 0:
                    break
            open_index -= 1
        previous_index = open_index - 1
        while previous_index >= 0 and not lines[previous_index].strip():
            previous_index -= 1
        follows_shared_from = bool(
            previous_index >= 0
            and re.match(
                r"^FROM[ \t]*$",
                lines[previous_index].strip(),
                re.IGNORECASE,
            )
        )
        follows_derived_from = bool(
            previous_index >= 0
            and re.search(
                r"\bFROM[ \t]*\([ \t]*$",
                lines[previous_index].strip(),
                re.IGNORECASE,
            )
        )
        join_indent = base_indent + ("    " if follows_derived_from else "")
        clause_indent = (
            base_indent[:-4]
            if follows_shared_from and base_indent.endswith("    ")
            else base_indent
        )
        candidate_index = index + 1
        while candidate_index < len(lines) and not lines[candidate_index].strip():
            candidate_index += 1
        if candidate_index >= len(lines):
            continue
        if not join_pattern.match(lines[candidate_index].lstrip(" \t")):
            continue

        in_join = True
        for line_index in range(candidate_index, len(lines)):
            candidate = lines[line_index].rstrip("\r\n")
            body = candidate.lstrip(" \t")
            if not body:
                continue
            if body.startswith("<") or body.startswith(")"):
                break
            if join_pattern.match(body):
                expected = join_indent
                in_join = True
            elif clause_pattern.match(body):
                expected = clause_indent
                in_join = False
            elif in_join and re.match(r"^(?:AND|OR)\b", body, re.IGNORECASE):
                expected = join_indent + "    "
            elif not in_join and re.match(r"^(?:AND|OR)\b", body, re.IGNORECASE):
                expected = clause_indent + "    "
            else:
                break
            line_start = offsets[line_index]
            indent_end = line_start + len(candidate) - len(body)
            actual_indent = content[line_start:indent_end]
            is_boolean_continuation = bool(
                re.match(r"^(?:AND|OR)\b", body, re.IGNORECASE)
            )
            if not is_boolean_continuation or actual_indent != expected:
                edits.append((line_start, indent_end, expected))
    return edits


def dynamic_body_indent_source_edits(
    content: str,
    source_range: tuple[int, int],
    dynamic_ranges: List[tuple[int, int, int]],
) -> List[tuple[int, int, str]]:
    """Keep SQL text at least one level inside its dynamic XML block."""
    source_start, source_end = source_range
    edits_by_span: dict[tuple[int, int], str] = {}
    for range_start, range_end, expected_width in dynamic_ranges:
        if not (
            source_start < range_start < range_end < source_end
        ):
            continue
        cursor = content.find("\n", range_start, range_end)
        while cursor != -1 and cursor + 1 < range_end:
            line_start = cursor + 1
            line_end = content.find("\n", line_start, range_end)
            if line_end == -1:
                line_end = range_end
            line = content[line_start:line_end]
            body = line.lstrip(" \t")
            indent_width = len(line) - len(body)
            first_word = body.split(None, 1)[0].upper() if body else ""
            protects_direct_clause = first_word in {
                "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "HAVING",
                "UNION", "INTERSECT", "EXCEPT", "UPDATE", "INSERT",
                "DELETE", "VALUES", "SET", "RETURNING",
            }
            if (
                body
                and not body.startswith("<")
                and (
                    indent_width < expected_width
                    or (
                        indent_width == expected_width
                        and protects_direct_clause
                    )
                )
            ):
                span = (line_start, line_start + indent_width)
                replacement = " " * expected_width
                if len(replacement) > len(edits_by_span.get(span, "")):
                    edits_by_span[span] = replacement
            if line_end >= range_end:
                break
            cursor = line_end
    return [
        (start, end, replacement)
        for (start, end), replacement in edits_by_span.items()
    ]


def resolve_source_edits(
    edits: List[tuple[int, int, str]],
) -> List[tuple[int, int, str]]:
    """Deduplicate edits and reject overlaps the same way for validation and output."""
    seen = set()
    unique_edits = []
    for edit in edits:
        if edit not in seen:
            seen.add(edit)
            unique_edits.append(edit)
    unique_edits.sort(key=lambda item: (item[0], item[1]))
    resolved = []
    last_end = -1
    for start, end, replacement in unique_edits:
        if start == end:
            if start > last_end:
                resolved.append((start, end, replacement))
                last_end = end
        elif start >= last_end:
            resolved.append((start, end, replacement))
            last_end = end
    return resolved


def dynamic_null_coalesce_source_edits(
    sql_text: str,
    mapping: List[int],
    tag_ranges: List[tuple[int, int]],
) -> tuple[List[tuple[int, int, str]], str]:
    """Map nullable-equality rewrites that stay inside one XML text span.

    A general line diff can pair repeated predicates across MyBatis branches
    and produce a partial semantic rewrite.  The rule already exposes exact
    guest offsets, so map only ranges whose source offsets are contiguous and
    do not intersect markup.  Statements with such edits take a semantic-only
    pass; normal layout resumes on the next convergence round.
    """
    from mir.rules.sql.null_coalesce import NullCoalesceRule

    rule = NullCoalesceRule()
    violations = rule._find_violations(sql_text)
    edits = []
    for item in violations:
        guest_start = item["start_offset"]
        guest_end = item["end_offset"]
        if not (0 <= guest_start < guest_end <= len(mapping)):
            continue
        if any(
            mapping[index] - mapping[index - 1] != 1
            for index in range(guest_start + 1, guest_end)
        ):
            continue
        source_start = mapping[guest_start]
        source_end = mapping[guest_end - 1] + 1
        if any(
            max(source_start, tag_start) < min(source_end, tag_end)
            for tag_start, tag_end in tag_ranges
        ):
            continue
        edits.append((source_start, source_end, item["replacement"]))
    return edits, rule.fix(sql_text, "embedded.sql", {})


def dynamic_paren_single_source_edits(
    sql_text: str,
    mapping: List[int],
    tag_ranges: List[tuple[int, int]],
) -> tuple[List[tuple[int, int, str]], str]:
    """Remove each redundant parenthesis pair atomically in dynamic SQL."""
    from mir.rules.sql.paren_single import ParenSingleRule
    from mir.rules.sql.sql_utils import tokenize_sql

    rule = ParenSingleRule()
    tokens = tokenize_sql(sql_text)
    guest_groups = []
    for pair in rule._find_violations(sql_text):
        open_tok = pair["open_tok"]
        close_tok = pair["close_tok"]
        open_index = tokens.index(open_tok)
        close_index = tokens.index(close_tok)
        open_end = open_tok["end"]
        open_replacement = ""

        next_token = tokens[open_index + 1] if open_index + 1 < len(tokens) else None
        if next_token and next_token["type"] == "WHITESPACE":
            open_end = next_token["end"]
            next_token = (
                tokens[open_index + 2]
                if open_index + 2 < len(tokens)
                else None
            )
        previous_token = tokens[open_index - 1] if open_index else None

        def is_word_like(token):
            return bool(
                token
                and (
                    token["type"] in {
                        "KEYWORD", "IDENTIFIER", "NUMBER", "OPERATOR"
                    }
                    or (
                        token["type"] == "OTHER"
                        and token["value"].isalnum()
                    )
                )
            )

        if (
            previous_token
            and previous_token["type"] != "WHITESPACE"
            and is_word_like(previous_token)
            and is_word_like(next_token)
        ):
            open_replacement = " "

        close_start = close_tok["start"]
        if close_index and tokens[close_index - 1]["type"] == "WHITESPACE":
            close_start = tokens[close_index - 1]["start"]
        guest_groups.append([
            (open_tok["start"], open_end, open_replacement),
            (close_start, close_tok["end"], ""),
        ])

    source_edits = []
    accepted_guest_edits = []
    for group in guest_groups:
        mapped_group = []
        for guest_start, guest_end, replacement in group:
            if not (0 <= guest_start < guest_end <= len(mapping)):
                mapped_group = []
                break
            if any(
                mapping[index] - mapping[index - 1] != 1
                for index in range(guest_start + 1, guest_end)
            ):
                mapped_group = []
                break
            source_start = mapping[guest_start]
            source_end = mapping[guest_end - 1] + 1
            if any(
                max(source_start, tag_start) < min(source_end, tag_end)
                for tag_start, tag_end in tag_ranges
            ):
                mapped_group = []
                break
            mapped_group.append((source_start, source_end, replacement))
        if mapped_group:
            source_edits.extend(mapped_group)
            accepted_guest_edits.extend(group)

    chars = list(sql_text)
    for start, end, replacement in sorted(accepted_guest_edits, reverse=True):
        chars[start:end] = list(replacement)
    return source_edits, "".join(chars)


def compact_dynamic_order_by_edits(
    content: str,
    source_range: tuple[int, int],
    rule_config: dict,
) -> List[tuple[int, int, str]]:
    """Compact a trailing optional ORDER BY suffix when its XML line fits."""
    import re

    from mir.rules.sql.line_length import LineLengthRule
    from mir.rules.sql.sql_utils import source_text_length, tokenize_sql

    start, end = source_range
    fragment = content[start:end]
    pattern = re.compile(
        r"(?m)^([ \t]*)ORDER[ \t]+BY[ \t]+([^\n<;]+?)[ \t]*\n"
        r"[ \t]*(<if\b[^>]*>)(.*?)(</if>)[ \t]*\n[ \t]*;",
        re.DOTALL,
    )
    max_length = LineLengthRule().get_config_value(
        rule_config,
        "max_length",
        default_value=120,
    )
    edits = []
    for match in pattern.finditer(fragment):
        body = match.group(4)
        if "<" in body or "--" in body or "/*" in body:
            continue
        body_tokens = tokenize_sql(body)
        compact_body = "".join(
            " " if token["type"] == "WHITESPACE" else token["value"]
            for token in body_tokens
        ).strip()
        replacement = (
            match.group(1)
            + "ORDER BY "
            + match.group(2).strip()
            + " "
            + match.group(3)
            + compact_body
            + match.group(5)
            + ";"
        )
        if source_text_length(replacement, rule_config) > max_length:
            continue
        edits.append((
            start + match.start(),
            start + match.end(),
            replacement,
        ))
    return edits


def dynamic_window_source_edits(
    content: str,
    source_range: tuple[int, int],
    rule_config: dict,
) -> List[tuple[int, int, str]]:
    """Format window ORDER BY clauses whose fields come from MyBatis tags."""
    import re

    from mir.rules.sql.line_length import LineLengthRule
    from mir.rules.sql.sql_utils import (
        get_token_depths,
        source_text_length,
        tokenize_sql,
    )

    start, end = source_range
    fragment = content[start:end]
    lines = fragment.splitlines(keepends=True)
    offsets = []
    offset = start
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    max_length = LineLengthRule().get_config_value(
        rule_config,
        "max_length",
        default_value=120,
    )
    opening = re.compile(
        r"\bOVER[ \t]*\((?P<inside>[ \t]*)ORDER[ \t]+BY"
        r"(?P<after>[ \t]*\r?\n)(?P<choose_indent>[ \t]*)(?=<choose\b)",
        re.IGNORECASE,
    )
    edits = []
    for match in opening.finditer(fragment):
        line_index = fragment.count("\n", 0, match.start())
        line = lines[line_index].rstrip("\r\n")
        base_indent = line[: len(line) - len(line.lstrip(" \t"))]
        window_indent = base_indent + "    "
        choose_indent = window_indent + "    "
        when_indent = choose_indent + "    "
        body_indent = when_indent + "    "

        edits.append((
            start + match.start("inside"),
            start + match.end("inside"),
            "\n" + window_indent,
        ))
        edits.append((
            start + match.start("after"),
            start + match.end("choose_indent"),
            "\n" + choose_indent,
        ))

        choose_line = line_index + 1
        depth = 0
        in_multiline_when = False
        close_line = None
        for candidate_index in range(choose_line, len(lines)):
            raw = lines[candidate_index].rstrip("\r\n")
            body = raw.lstrip(" \t")
            if not body:
                continue
            lower = body.lower()
            expected = None
            if lower.startswith("<choose"):
                depth += 1
                expected = choose_indent if depth == 1 else when_indent
            elif lower.startswith("</choose"):
                expected = choose_indent if depth == 1 else when_indent
                depth -= 1
                if depth == 0:
                    close_line = candidate_index
            elif depth == 1 and lower.startswith("<when"):
                expected = when_indent
                in_multiline_when = not lower.rstrip().endswith("</when>")
            elif depth == 1 and lower.startswith("</when"):
                expected = when_indent
                in_multiline_when = False
            elif depth == 1 and in_multiline_when and not body.startswith("<"):
                expected = body_indent

            if expected is not None:
                line_start = offsets[candidate_index]
                indent_end = line_start + len(raw) - len(body)
                if content[line_start:indent_end] != expected:
                    edits.append((line_start, indent_end, expected))

            if (
                depth == 1
                and in_multiline_when
                and not body.startswith("<")
                and source_text_length(body_indent + body, rule_config) > max_length
            ):
                body_tokens = tokenize_sql(body)
                body_depths = get_token_depths(body_tokens)
                for token_index, token in enumerate(body_tokens):
                    if token["type"] != "COMMA" or body_depths[token_index] != 0:
                        continue
                    next_index = token_index + 1
                    while (
                        next_index < len(body_tokens)
                        and body_tokens[next_index]["type"] == "WHITESPACE"
                    ):
                        next_index += 1
                    next_start = (
                        body_tokens[next_index]["start"]
                        if next_index < len(body_tokens)
                        else token["end"]
                    )
                    source_body_start = offsets[candidate_index] + len(raw) - len(body)
                    edits.append((
                        source_body_start + token["end"],
                        source_body_start + next_start,
                        "\n" + body_indent,
                    ))

            if close_line is not None:
                next_index = close_line + 1
                while next_index < len(lines) and not lines[next_index].strip():
                    next_index += 1
                if next_index < len(lines):
                    closing = lines[next_index].rstrip("\r\n")
                    closing_body = closing.lstrip(" \t")
                    if closing_body.startswith(")"):
                        line_start = offsets[next_index]
                        indent_end = line_start + len(closing) - len(closing_body)
                        if content[line_start:indent_end] != base_indent:
                            edits.append((line_start, indent_end, base_indent))
                break
    return edits


def compact_static_order_by_edits(
    content: str,
    source_range: tuple[int, int],
    rule_config: dict,
) -> List[tuple[int, int, str]]:
    """Compact a static multiline ORDER BY list when the source line fits."""
    import re

    from mir.rules.sql.line_length import LineLengthRule
    from mir.rules.sql.sql_utils import source_text_length

    start, end = source_range
    fragment = content[start:end]
    lines = fragment.splitlines(keepends=True)
    line_offsets = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line)
    max_length = LineLengthRule().get_config_value(
        rule_config,
        "max_length",
        default_value=120,
    )
    edits = []
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n")
        match = re.match(r"^([ \t]*)ORDER[ \t]+BY[ \t]*$", line, re.IGNORECASE)
        if match is None:
            continue
        continuation_indent = match.group(1) + "    "
        items = []
        final_index = index
        for candidate_index in range(index + 1, len(lines)):
            candidate = lines[candidate_index].rstrip("\r\n")
            if not candidate.startswith(continuation_indent):
                break
            body = candidate[len(continuation_indent):]
            if not body or body.startswith("<") or "--" in body or "/*" in body:
                break
            items.append(body.strip())
            final_index = candidate_index
            if not body.rstrip().endswith(","):
                break
        if not items or final_index == index or items[-1].endswith(","):
            continue
        replacement = match.group(1) + "ORDER BY " + " ".join(items)
        if source_text_length(replacement, rule_config) > max_length:
            continue
        edit_start = start + line_offsets[index]
        edit_end = start + line_offsets[final_index] + len(
            lines[final_index].rstrip("\r\n")
        )
        edits.append((edit_start, edit_end, replacement))
    return edits


def preserve_inline_dynamic_from_edits(
    content: str,
    source_range: tuple[int, int],
    dynamic_ranges: List[tuple[int, int, int]],
    rule_config: dict,
) -> List[tuple[int, int, str]]:
    """Keep a fitting one-relation FROM inline inside a dynamic branch."""
    import re

    from mir.rules.sql.line_length import LineLengthRule
    from mir.rules.sql.sql_utils import get_token_depths, source_text_length, tokenize_sql

    source_start, source_end = source_range
    max_length = LineLengthRule().get_config_value(
        rule_config, "max_length", default_value=120
    )
    edits = []
    for range_start, range_end, _ in dynamic_ranges:
        if not (
            source_start < range_start < range_end < source_end
        ):
            continue
        cursor = content.rfind("\n", 0, range_start) + 1
        while cursor < range_end:
            line_end = content.find("\n", cursor, range_end)
            if line_end == -1:
                line_end = range_end
            line = content[cursor:line_end]
            match = re.match(
                r"^([ \t]*)FROM[ \t]+([^<\n]+?)$", line, re.IGNORECASE
            )
            edit_start = cursor
            edit_end = line_end
            replacement = line
            relation = match.group(2) if match is not None else None
            relation_end = line_end
            if relation is None:
                standalone = re.match(
                    r"^([ \t]*)FROM[ \t]*$", line, re.IGNORECASE
                )
                next_start = line_end + 1
                next_end = content.find("\n", next_start, range_end)
                if next_end == -1:
                    next_end = range_end
                next_line = content[next_start:next_end]
                next_body = next_line.strip()
                if (
                    standalone is not None
                    and next_start < range_end
                    and next_body
                    and not next_body.startswith("<")
                ):
                    relation = next_body
                    relation_end = next_end
                    edit_end = next_end
                    replacement = standalone.group(1) + "FROM " + relation
            if (
                relation is not None
                and source_text_length(replacement, rule_config) <= max_length
            ):
                relation_tokens = tokenize_sql(relation)
                depths = get_token_depths(relation_tokens)
                has_top_level_comma = any(
                    token["type"] == "COMMA" and depths[index] == 0
                    for index, token in enumerate(relation_tokens)
                )
                has_top_level_join = any(
                    token["type"] == "KEYWORD"
                    and token["value"].upper() == "JOIN"
                    and depths[index] == 0
                    for index, token in enumerate(relation_tokens)
                )
                following_join = False
                scan_cursor = relation_end + 1
                while scan_cursor < range_end:
                    scan_end = content.find("\n", scan_cursor, range_end)
                    if scan_end == -1:
                        scan_end = range_end
                    following_body = content[scan_cursor:scan_end].strip()
                    if following_body.startswith("<"):
                        if re.search(
                            r">[ \t]*(?:(?:LEFT|RIGHT|FULL|INNER|CROSS|NATURAL)"
                            r"(?:[ \t]+OUTER)?[ \t]+)?JOIN\b",
                            following_body,
                            re.IGNORECASE,
                        ):
                            following_join = True
                            break
                        scan_cursor = scan_end + 1
                        continue
                    if not following_body:
                        scan_cursor = scan_end + 1
                        continue
                    if re.match(
                        r"^(?:LEFT|RIGHT|FULL|INNER|CROSS|NATURAL)?"
                        r"(?:[ \t]+OUTER)?[ \t]+JOIN\b|^JOIN\b",
                        following_body,
                        re.IGNORECASE,
                    ):
                        following_join = True
                    break
                if (
                    not has_top_level_comma
                    and not has_top_level_join
                    and not following_join
                    and "--" not in relation
                    and "/*" not in relation
                ):
                    edits.append((edit_start, edit_end, replacement))
            if line_end >= range_end:
                break
            cursor = line_end + 1
    return edits


def compact_static_select_edits(
    content: str,
    source_range: tuple[int, int],
    rule_config: dict,
) -> List[tuple[int, int, str]]:
    """Compact one static SELECT expression after embedded rules simplify it."""
    import re

    from mir.rules.sql.line_length import LineLengthRule
    from mir.rules.sql.sql_utils import source_text_length, tokenize_sql

    start, end = source_range
    fragment = content[start:end]
    max_length = LineLengthRule().get_config_value(
        rule_config, "max_length", default_value=120
    )
    edits = []
    pattern = re.compile(
        r"(?m)^(?P<indent>[ \t]*)SELECT(?P<gap>[ \t]*\n[ \t]+)"
        r"(?P<expression>[^\n<]+)\n(?P=indent)(?P<clause>FROM|INTO)\b"
    )
    for match in pattern.finditer(fragment):
        expression = match.group("expression").strip()
        expression_tokens = tokenize_sql(expression)
        depth = 0
        has_top_level_comma = False
        for token in expression_tokens:
            if token["type"] == "PAREN":
                depth += 1 if token["value"] == "(" else -1
            elif token["type"] == "COMMA" and depth == 0:
                has_top_level_comma = True
                break
        candidate = match.group("indent") + "SELECT " + expression
        if (
            not has_top_level_comma
            and source_text_length(candidate, rule_config) <= max_length
        ):
            gap_start = start + match.start("gap")
            gap_end = start + match.start("expression")
            edits.append((gap_start, gap_end, " "))
    return edits


def sql_trailing_whitespace_source_edits(
    content: str,
    sql_text: str,
    mapping: List[int],
    tag_ranges: List[tuple[int, int]],
) -> List[tuple[int, int, str]]:
    """Remove end-of-line SQL whitespace through contiguous source mappings."""
    import re

    from mir.rules.sql.sql_utils import tokenize_sql

    edits = []
    for token in tokenize_sql(sql_text):
        if token["type"] != "WHITESPACE":
            continue
        for match in re.finditer(r"[ \t]+(?=\r?\n)", token["value"]):
            guest_start = token["start"] + match.start()
            guest_end = token["start"] + match.end()
            if not (0 <= guest_start < guest_end <= len(mapping)):
                continue
            if any(
                mapping[index] - mapping[index - 1] != 1
                for index in range(guest_start + 1, guest_end)
            ):
                continue
            source_start = mapping[guest_start]
            source_end = mapping[guest_end - 1] + 1
            if source_end >= len(content) or content[source_end] not in "\r\n":
                continue
            if any(
                max(source_start, tag_start) < min(source_end, tag_end)
                for tag_start, tag_end in tag_ranges
            ):
                continue
            edits.append((source_start, source_end, ""))
    return edits


def remove_mybatis_sql_trailing_whitespace(content: str) -> str:
    """Remove SQL-only trailing whitespace introduced by mapped formatting."""
    import re

    if re.search(r"[ \t]+(?=\r?\n)", content) is None:
        return content

    tokens = tokenize_xml(content)
    elements = get_all_elements_recursively(parse_xml_elements(tokens))
    sql_defs = {}
    for element in elements:
        if element["tag"] == "sql" and "id" in element["attrs"]:
            sql_id = element["attrs"]["id"]
            sql_defs[sql_id] = element["inner_tokens"]
            if "." in sql_id:
                sql_defs[sql_id.split(".")[-1]] = element["inner_tokens"]

    edits = []
    for element in elements:
        if element["tag"] not in {"select", "insert", "update", "delete", "sql"}:
            continue
        expanded_chars: List[str] = []
        mapping: List[int] = []
        is_after_tag: List[bool] = []
        expand_tokens(
            element["inner_tokens"],
            sql_defs,
            expanded_chars,
            mapping,
            is_after_tag,
        )
        edits.extend(
            sql_trailing_whitespace_source_edits(
                content,
                "".join(expanded_chars),
                mapping,
                [],
            )
        )
    chars = list(content)
    for start, end, replacement in sorted(
        resolve_source_edits(edits),
        reverse=True,
    ):
        chars[start:end] = list(replacement)
    return "".join(chars)


class XmlMybatisSqlRule(BaseRule):
    commit_profile = True
    rule_id = "IR-xml-mybatis-sql"
    description = "Format embedded SQL inside MyBatis XML mapper files using SQL rules."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        select my_column from my_schema.my_table t\n    </select>\n</mapper>',
            "correct": '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT my_column FROM my_schema.my_table t\n    </select>\n</mapper>'
        },
        {
            "violating": '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT id\n            , name\n        FROM users\n        <if test="distinct">\n            , distinct_val\n        </if>\n    </select>\n</mapper>',
            "correct": '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT\n            id,\n            name\n        FROM users\n        <if test="distinct">\n            , distinct_val\n        </if>\n    </select>\n</mapper>'
        }
    ]
    additional_validations = [
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT my_column FROM my_schema.my_table t\n    </select>\n</mapper>',
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT\n            id,\n            name\n        FROM users\n        <if test="distinct">\n            , distinct_val\n        </if>\n    </select>\n</mapper>'
    ]

    def __init__(self) -> None:
        super().__init__()
        self.sql_rules = None
        self._expansion_cache = {}
        self._cached_content = None

    def _prepare_cache(self, content: str) -> None:
        # Rule instances are shared by the loader. Keep expansions only for the
        # current content value; object ids can be reused after a prior string is
        # released and previously caused fixes from another file to leak here.
        if content != self._cached_content:
            self._expansion_cache.clear()
            self._cached_content = content

    def _is_mybatis_file(self, content: str) -> bool:
        lower_content = content.lower()
        return "mybatis.org" in lower_content or "<mapper" in lower_content

    def _find_violations(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[dict]:
        if not self._is_mybatis_file(content):
            return []

        self._prepare_cache(content)

        tokens = tokenize_xml(content)
        tag_ranges = []
        in_tag = False
        tag_start = None
        for tok in tokens:
            if tok["type"] in ("TAG_OPEN_START", "TAG_CLOSE_START", "XML_DECL_START", "DOCTYPE_START", "COMMENT_START"):
                if not in_tag:
                    in_tag = True
                    tag_start = tok["start"]
            elif tok["type"] in ("TAG_END", "XML_DECL_END", "DOCTYPE_END", "COMMENT_END"):
                if in_tag:
                    tag_ranges.append((tag_start, tok["end"]))
                    in_tag = False
        root_elements = parse_xml_elements(tokens)
        elements = get_all_elements_recursively(root_elements)
        foreach_ranges = [
            (element["start_offset"], element["end_offset"])
            for element in elements
            if element["tag"] == "foreach"
        ]
        dynamic_indent_ranges = get_dynamic_indent_ranges(
            elements, content, rule_config
        )

        sql_defs = {}
        for el in elements:
            if el["tag"] == "sql" and "id" in el["attrs"]:
                sql_id = el["attrs"]["id"]
                sql_defs[sql_id] = el["inner_tokens"]
                if "." in sql_id:
                    sql_defs[sql_id.split(".")[-1]] = el["inner_tokens"]

        violations = []
        target_tags = {"select", "insert", "update", "delete", "sql"}

        lines_filter = rule_config.get("_lines")
        for el in elements:
            if el["tag"] in target_tags and "id" in el["attrs"]:
                if lines_filter:
                    start_line = content[:el["start_offset"]].count('\n') + 1
                    end_tok = tokens[el["end_idx"]]
                    end_line = content[:end_tok["end"]].count('\n') + 1
                    if not any(l in lines_filter for l in range(start_line, end_line + 1)):
                        continue

                cache_key = (id(content), el["start_offset"])
                if cache_key in self._expansion_cache:
                    expanded_chars, mapping, is_after_tag = self._expansion_cache[cache_key]
                else:
                    expanded_chars = []
                    mapping = []
                    is_after_tag = []
                    expand_tokens(el["inner_tokens"], sql_defs, expanded_chars, mapping, is_after_tag)
                    self._expansion_cache[cache_key] = (expanded_chars, mapping, is_after_tag)
                sql_text = "".join(expanded_chars)
                
                if not sql_text.strip():
                    continue
                    
                ignored_comma_offsets = set()
                for idx, char in enumerate(sql_text):
                    if char == "," and idx < len(is_after_tag) and is_after_tag[idx]:
                        ignored_comma_offsets.add(idx)
                        
                base_indent = get_element_base_indent(el, tokens, content, rule_config)
                boundary_offsets = mapping_boundary_offsets(mapping, tag_ranges)
                
                inner_config = dict(rule_config)
                if "_lines" in inner_config:
                    del inner_config["_lines"]

                layout_edits = dynamic_column_layout_edits(
                    sql_text,
                    mapping,
                    boundary_offsets,
                    tag_ranges,
                    dynamic_indent_ranges,
                    content,
                    inner_config,
                )
                if layout_edits:
                    first_start = min(start for start, _, _ in layout_edits)
                    violations.append({
                        "rule_id": "IR-column-layout",
                        "line": content.count("\n", 0, first_start) + 1,
                        "message": (
                            "[MyBatis SQL: IR-column-layout] Align the "
                            "dynamic column list one indentation level below "
                            "its keyword."
                        ),
                        "is_fixable": True,
                    })
                post_choose_edits = post_choose_clause_source_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                )
                changed_post_choose_edits = [
                    edit
                    for edit in post_choose_edits
                    if content[edit[0]:edit[1]] != edit[2]
                ]
                if changed_post_choose_edits:
                    first_start = min(
                        start for start, _, _ in changed_post_choose_edits
                    )
                    violations.append({
                        "rule_id": self.rule_id,
                        "line": content.count("\n", 0, first_start) + 1,
                        "message": (
                            "Shared JOIN and clause lines after <choose> must "
                            "align with their enclosing query."
                        ),
                        "is_fixable": True,
                    })
                dynamic_body_edits = dynamic_body_indent_source_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    dynamic_indent_ranges,
                )
                changed_dynamic_body_edits = [
                    edit
                    for edit in dynamic_body_edits
                    if content[edit[0]:edit[1]] != edit[2]
                ]
                if changed_dynamic_body_edits:
                    first_start = min(
                        start for start, _, _ in changed_dynamic_body_edits
                    )
                    violations.append({
                        "rule_id": self.rule_id,
                        "line": content.count("\n", 0, first_start) + 1,
                        "message": (
                            "SQL text must remain one indentation level inside "
                            "its dynamic XML block."
                        ),
                        "is_fixable": True,
                    })
                order_edits = compact_dynamic_order_by_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    inner_config,
                )
                if order_edits:
                    first_start = min(start for start, _, _ in order_edits)
                    violations.append({
                        "rule_id": self.rule_id,
                        "line": content.count("\n", 0, first_start) + 1,
                        "message": (
                            "Compact the optional ORDER BY suffix when the "
                            "complete XML line fits."
                        ),
                        "is_fixable": True,
                    })
                static_order_edits = compact_static_order_by_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    inner_config,
                )
                if static_order_edits:
                    first_start = min(start for start, _, _ in static_order_edits)
                    violations.append({
                        "rule_id": self.rule_id,
                        "line": content.count("\n", 0, first_start) + 1,
                        "message": "Compact the ORDER BY list when the line fits.",
                        "is_fixable": True,
                    })
                static_select_edits = compact_static_select_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    inner_config,
                )
                if static_select_edits:
                    first_start = min(start for start, _, _ in static_select_edits)
                    violations.append({
                        "rule_id": "IR-column-layout",
                        "line": content.count("\n", 0, first_start) + 1,
                        "message": (
                            "Compact a single static SELECT expression when "
                            "the physical XML line fits."
                        ),
                        "is_fixable": True,
                    })

                embedded_violations = check_embedded_content(
                    guest_language="sql",
                    guest_text=sql_text,
                    mapping=mapping,
                    file_path=file_path,
                    rule_config=inner_config,
                    require_embedded_safe=True,
                    extra_check_args={
                        "ignored_comma_offsets": ignored_comma_offsets,
                        "mybatis_dynamic_offsets": {
                            idx for idx, after_tag in enumerate(is_after_tag) if after_tag
                        },
                        "mybatis_foreach_offsets": mapped_offsets_in_ranges(
                            mapping, foreach_ranges
                        ),
                        "mybatis_boundary_offsets": boundary_offsets,
                        "mybatis_source_mapping": mapping,
                        "base_indent": base_indent,
                        "tag_ranges": tag_ranges,
                        "original_xml": content
                    }
                )
                
                for ev in embedded_violations:
                    abs_line = content[:ev["mapped_offset"]].count('\n') + 1
                    if lines_filter and abs_line not in lines_filter:
                        el_start_line = content[:el["start_offset"]].count('\n') + 1
                        end_tok = tokens[el["end_idx"]]
                        el_end_line = content[:end_tok["end"]].count('\n') + 1
                        matching_lines = [l for l in lines_filter if el_start_line <= l <= el_end_line]
                        if matching_lines:
                            abs_line = matching_lines[0]
                    violations.append({
                        "rule_id": ev["rule_id"],
                        "line": abs_line,
                        "message": f"[MyBatis SQL: {ev['rule_id']}] {ev['message']}",
                        "is_fixable": ev["is_fixable"]
                    })
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, file_path, rule_config)
        seen = set()
        for v in offending:
            key = (v["rule_id"], v["line"])
            if key in seen:
                continue
            seen.add(key)
            line_idx = v["line"] - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            violations.append(Violation(
                rule_id=v["rule_id"],
                line_number=v["line"],
                message=v["message"],
                offending_lines=[offending_line],
                is_fixable=v["is_fixable"]
            ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        if not self._is_mybatis_file(content):
            return content

        self._prepare_cache(content)

        tokens = tokenize_xml(content)
        tag_ranges = []
        in_tag = False
        tag_start = None
        for tok in tokens:
            if tok["type"] in ("TAG_OPEN_START", "TAG_CLOSE_START", "XML_DECL_START", "DOCTYPE_START", "COMMENT_START"):
                if not in_tag:
                    in_tag = True
                    tag_start = tok["start"]
            elif tok["type"] in ("TAG_END", "XML_DECL_END", "DOCTYPE_END", "COMMENT_END"):
                if in_tag:
                    tag_ranges.append((tag_start, tok["end"]))
                    in_tag = False

        root_elements = parse_xml_elements(tokens)
        elements = get_all_elements_recursively(root_elements)
        foreach_ranges = [
            (element["start_offset"], element["end_offset"])
            for element in elements
            if element["tag"] == "foreach"
        ]
        dynamic_indent_ranges = get_dynamic_indent_ranges(
            elements, content, rule_config
        )

        sql_defs = {}
        for el in elements:
            if el["tag"] == "sql" and "id" in el["attrs"]:
                sql_id = el["attrs"]["id"]
                sql_defs[sql_id] = el["inner_tokens"]
                if "." in sql_id:
                    sql_defs[sql_id.split(".")[-1]] = el["inner_tokens"]

        target_tags = {"select", "insert", "update", "delete", "sql"}
        all_xml_edits = []
        expected_signature_updates = {}
        original_signature_map = {}
        lines_filter = rule_config.get("_lines")

        for el in elements:
            if el["tag"] in target_tags and "id" in el["attrs"]:
                if lines_filter:
                    start_line = content[:el["start_offset"]].count('\n') + 1
                    end_tok = tokens[el["end_idx"]]
                    end_line = content[:end_tok["end"]].count('\n') + 1
                    if not any(l in lines_filter for l in range(start_line, end_line + 1)):
                        continue

                cache_key = (id(content), el["start_offset"])
                if cache_key in self._expansion_cache:
                    expanded_chars, mapping, is_after_tag = self._expansion_cache[cache_key]
                else:
                    expanded_chars = []
                    mapping = []
                    is_after_tag = []
                    expand_tokens(el["inner_tokens"], sql_defs, expanded_chars, mapping, is_after_tag)
                    self._expansion_cache[cache_key] = (expanded_chars, mapping, is_after_tag)
                sql_text = "".join(expanded_chars)
                
                if not sql_text.strip():
                    continue
                    
                ignored_comma_offsets = set()
                for idx, char in enumerate(sql_text):
                    if char == "," and idx < len(is_after_tag) and is_after_tag[idx]:
                        ignored_comma_offsets.add(idx)
                        
                base_indent = get_element_base_indent(el, tokens, content, rule_config)
                boundary_offsets = mapping_boundary_offsets(mapping, tag_ranges)
                
                inner_config = dict(rule_config)
                if "_lines" in inner_config:
                    del inner_config["_lines"]

                applied_rules = set()
                bridge_state = {
                    "ignored_comma_offsets": ignored_comma_offsets,
                    "mybatis_dynamic_offsets": {
                        idx for idx, after_tag in enumerate(is_after_tag) if after_tag
                    },
                    "mybatis_foreach_offsets": mapped_offsets_in_ranges(
                        mapping, foreach_ranges
                    ),
                    "mybatis_boundary_offsets": boundary_offsets,
                    "mybatis_source_mapping": mapping,
                    "mybatis_dynamic_indent_ranges": [
                        item
                        for item in dynamic_indent_ranges
                        if el["start_offset"] < item[0] < item[1] < el["end_offset"]
                    ],
                    "base_indent": base_indent,
                    "mybatis_element_tag": el["tag"],
                    "mybatis_element_id": el["attrs"]["id"],
                    "tag_ranges": tag_ranges,
                    "original_xml": content,
                    "source_range": (el["start_offset"], el["end_offset"]),
                    "applied_rules": applied_rules,
                }
                bridge_state["source_mapped_subquery_compaction"] = bool(
                    bridge_state["mybatis_dynamic_indent_ranges"]
                )
                null_source_edits, null_fixed_text = (
                    dynamic_null_coalesce_source_edits(
                        sql_text,
                        mapping,
                        tag_ranges,
                    )
                    if bridge_state["mybatis_dynamic_indent_ranges"]
                    else ([], sql_text)
                )
                null_source_edits = [
                    edit
                    for edit in null_source_edits
                    if el["start_offset"] <= edit[0] <= edit[1] <= el["end_offset"]
                ]
                if not null_source_edits:
                    null_fixed_text = sql_text
                paren_source_edits, paren_fixed_text = (
                    dynamic_paren_single_source_edits(
                        sql_text,
                        mapping,
                        tag_ranges,
                    )
                    if (
                        bridge_state["mybatis_dynamic_indent_ranges"]
                        and not null_source_edits
                    )
                    else ([], sql_text)
                )
                paren_source_edits = [
                    edit
                    for edit in paren_source_edits
                    if el["start_offset"] <= edit[0] <= edit[1] <= el["end_offset"]
                ]
                if not paren_source_edits:
                    paren_fixed_text = sql_text
                from mir.engine.embedded_bridge import fix_embedded_content
                layout_edits = dynamic_column_layout_edits(
                    sql_text,
                    mapping,
                    boundary_offsets,
                    tag_ranges,
                    dynamic_indent_ranges,
                    content,
                    inner_config,
                )
                post_choose_edits = post_choose_clause_source_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                )
                dynamic_body_edits = dynamic_body_indent_source_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    dynamic_indent_ranges,
                )
                layout_edits = (
                    post_choose_edits + dynamic_body_edits + layout_edits
                )
                join_config = dict(inner_config)
                join_config.update(bridge_state)
                layout_edits.extend(
                    dynamic_sql_indent_source_edits(
                        sql_text,
                        mapping,
                        tag_ranges,
                        dynamic_indent_ranges,
                        join_config,
                    )
                )
                subquery_source_edits = dynamic_subquery_source_edits(
                    sql_text,
                    mapping,
                    content,
                    join_config,
                )
                dynamic_projection_edits = (
                    dynamic_projection_subquery_source_edits(
                        sql_text,
                        mapping,
                        content,
                        dynamic_indent_ranges,
                    )
                )
                if subquery_source_edits:
                    layout_edits = [
                        edit
                        for edit in layout_edits
                        if not any(
                            max(edit[0], source_edit[0])
                            < min(edit[1], source_edit[1])
                            for source_edit in subquery_source_edits
                        )
                    ]
                    layout_edits.extend(subquery_source_edits)
                if dynamic_projection_edits:
                    layout_edits = [
                        edit
                        for edit in layout_edits
                        if not any(
                            max(edit[0], source_edit[0])
                            < min(edit[1], source_edit[1])
                            for source_edit in dynamic_projection_edits
                        )
                    ]
                layout_edits.extend(dynamic_projection_edits)
                dynamic_order_edits = compact_dynamic_order_by_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    inner_config,
                )
                layout_edits.extend(dynamic_order_edits)
                dynamic_window_edits = dynamic_window_source_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    inner_config,
                )
                if dynamic_window_edits:
                    layout_edits = [
                        edit
                        for edit in layout_edits
                        if not any(
                            max(edit[0], window_edit[0])
                            < min(edit[1], window_edit[1])
                            or (
                                edit[0] == edit[1]
                                and window_edit[0] <= edit[0] <= window_edit[1]
                            )
                            for window_edit in dynamic_window_edits
                        )
                    ]
                    layout_edits.extend(dynamic_window_edits)
                    applied_rules.add("IR-window-layout")
                static_order_edits = compact_static_order_by_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    inner_config,
                )
                layout_edits.extend(static_order_edits)
                dynamic_from_edits = preserve_inline_dynamic_from_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    dynamic_indent_ranges,
                    inner_config,
                )
                layout_edits.extend(dynamic_from_edits)
                static_select_edits = compact_static_select_edits(
                    content,
                    (el["start_offset"], el["end_offset"]),
                    inner_config,
                )
                layout_edits.extend(static_select_edits)
                layout_edits.extend(
                    sql_trailing_whitespace_source_edits(
                        content,
                        sql_text,
                        mapping,
                        tag_ranges,
                    )
                )
                protected_source_indent_spans = [
                    (start, end)
                    for start, end, _ in post_choose_edits + dynamic_body_edits
                    + dynamic_projection_edits
                    + dynamic_from_edits
                    + dynamic_order_edits
                    + static_order_edits
                ]

                def overlaps_protected_source_indent(edit) -> bool:
                    edit_start, edit_end, _ = edit
                    return any(
                        max(edit_start, span_start) < min(edit_end, span_end)
                        or (
                            edit_start == edit_end
                            and span_start <= edit_start <= span_end
                        )
                        for span_start, span_end in protected_source_indent_spans
                    )

                protected_source_edit_set = set(
                    post_choose_edits
                    + dynamic_body_edits
                    + subquery_source_edits
                    + dynamic_window_edits
                    + dynamic_projection_edits
                    + dynamic_from_edits
                    + dynamic_order_edits
                    + static_order_edits
                )
                layout_edits = [
                    edit
                    for edit in layout_edits
                    if (
                        edit in protected_source_edit_set
                        or not overlaps_protected_source_indent(edit)
                    )
                ]
                # Direct layout helpers are authorized to move only
                # whitespace, except for exact structural compaction that
                # preserves the complete SQL and XML token sequence.
                trusted_structural_edits = set(
                    dynamic_order_edits + static_order_edits
                    + dynamic_from_edits
                )
                layout_edits = [
                    (start, end, replacement)
                    for start, end, replacement in layout_edits
                    if (
                        (start, end, replacement) in trusted_structural_edits
                        or (
                            (start == end or content[start:end].isspace())
                            and (not replacement or replacement.isspace())
                        )
                    )
                ]
                excluded_guest_rule_ids = (
                    {
                        "IR-join-on-multi",
                        "IR-null-coalesce",
                        "IR-paren-single",
                        "IR-subquery-indent",
                    }
                    if bridge_state["mybatis_dynamic_indent_ranges"]
                    else set()
                )
                if any(
                    source_offset < el["start_offset"]
                    or source_offset > el["end_offset"]
                    for source_offset in mapping
                ):
                    # Included SQL definitions are formatted in their own
                    # element pass. Applying a semantic rewrite to their
                    # expansion here cannot map inside the host statement and
                    # would stop all later layout rules for that host.
                    from mir.engine.rules_loader import load_rules_for_language

                    excluded_guest_rule_ids.update(
                        rule.rule_id
                        for rule in load_rules_for_language("sql")
                        if rule.commit_semantic_rewrite
                    )
                edits = fix_embedded_content(
                    guest_language="sql",
                    guest_text=sql_text,
                    mapping=mapping,
                    file_path=file_path,
                    rule_config=inner_config,
                    excluded_rule_ids=excluded_guest_rule_ids or None,
                    require_embedded_safe=True,
                    extra_fix_args=bridge_state,
                )
                # Expanded <include> content maps back to its reusable <sql>
                # definition, which is formatted as its own element. A host
                # statement must never claim those out-of-range edits or let
                # them discard layout changes that belong to the host.
                edits = [
                    edit
                    for edit in edits
                    if el["start_offset"] <= edit[0] <= edit[1] <= el["end_offset"]
                ]
                edits = [
                    edit for edit in edits
                    if not overlaps_protected_source_indent(edit)
                ]
                layout_edits = [
                    edit
                    for edit in layout_edits
                    if el["start_offset"] <= edit[0] <= edit[1] <= el["end_offset"]
                ]
                layout_edits = [
                    edit
                    for edit in layout_edits
                    if content[edit[0]:edit[1]] != edit[2]
                ]
                edits = layout_edits + edits
                if null_source_edits:
                    from mir.rules.sql.sql_utils import protected_sql_signature

                    edits = null_source_edits
                    applied_rules.clear()
                    applied_rules.add("IR-null-coalesce")
                    bridge_state["original_protected_signature"] = (
                        protected_sql_signature(sql_text)
                    )
                    bridge_state["expected_protected_signature"] = (
                        protected_sql_signature(null_fixed_text)
                    )
                elif paren_source_edits:
                    from mir.rules.sql.sql_utils import protected_sql_signature

                    edits = paren_source_edits
                    applied_rules.clear()
                    applied_rules.add("IR-paren-single")
                    bridge_state["original_protected_signature"] = (
                        protected_sql_signature(sql_text)
                    )
                    bridge_state["expected_protected_signature"] = (
                        protected_sql_signature(paren_fixed_text)
                    )
                statement_key = (el["tag"], el["attrs"]["id"])
                original_signature_map[statement_key] = bridge_state[
                    "original_protected_signature"
                ]
                if edits:
                    fragment_start = el["start_offset"]
                    fragment_end = el["end_offset"]
                    fragment_chars = list(content[fragment_start:fragment_end])
                    fragment_edits = [
                        (start, end, replacement)
                        for start, end, replacement in edits
                        if fragment_start <= start <= end <= fragment_end
                    ]
                    if len(fragment_edits) != len(edits):
                        continue
                    fragment_edits = resolve_source_edits(fragment_edits)
                    for start, end, replacement in sorted(fragment_edits, reverse=True):
                        relative_start = start - fragment_start
                        relative_end = end - fragment_start
                        fragment_chars[relative_start:relative_end] = list(replacement)
                    candidate_signature = get_mybatis_fragment_protected_signature(
                        "".join(fragment_chars), sql_defs, statement_key
                    )
                    allowed_signatures = {
                        bridge_state["original_protected_signature"],
                        bridge_state["expected_protected_signature"],
                    }
                    if candidate_signature not in allowed_signatures:
                        # A repeated predicate on opposite sides of a dynamic
                        # tag can make a text diff ambiguous. Reject the whole
                        # statement edit instead of applying only part of it.
                        continue
                    expected_signature_updates[(el["tag"], el["attrs"]["id"])] = (
                        candidate_signature
                    )
                    all_xml_edits.extend(edits)
                    rules_fixed_set = rule_config.get("rules_fixed")
                    if rules_fixed_set is not None:
                        rules_fixed_set.update(applied_rules)

        if not all_xml_edits:
            return content

        resolved_edits = resolve_source_edits(all_xml_edits)
        resolved_edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in resolved_edits:
            chars[start:end] = list(new_text)

        fixed_content = remove_mybatis_sql_trailing_whitespace("".join(chars))
        if lines_filter:
            # A line-restricted pass expands only selected statements above,
            # but final safety validation still covers the entire mapper.
            original_signatures = get_mybatis_protected_signatures(content)
            original_signature_map = {
                (tag, statement_id): signature
                for tag, statement_id, signature in original_signatures
            }
        else:
            original_signatures = tuple(
                (tag, statement_id, signature)
                for (tag, statement_id), signature in original_signature_map.items()
            )
        expected_signatures = tuple(
            (
                tag,
                statement_id,
                expected_signature_updates.get((tag, statement_id), signature),
            )
            for tag, statement_id, signature in original_signatures
        )
        actual_signatures = get_mybatis_protected_signatures(fixed_content)

        changed_fragment_ids = {
            statement_id
            for (tag, statement_id), signature in expected_signature_updates.items()
            if tag == "sql"
            and signature != original_signature_map.get((tag, statement_id))
        }

        def included_fragment_ids(element: dict) -> set[str]:
            references = set()
            inner_tokens = element.get("inner_tokens", [])
            for index, token in enumerate(inner_tokens):
                if token["type"] != "ATTR_NAME" or token["value"] != "refid":
                    continue
                tag_index = index - 1
                while tag_index >= 0 and inner_tokens[tag_index]["type"] == "WHITESPACE":
                    tag_index -= 1
                if tag_index < 0 or inner_tokens[tag_index]["type"] != "TAG_OPEN_START":
                    continue
                if inner_tokens[tag_index]["value"].lower() != "<include":
                    continue
                value_index = index + 2
                if (
                    value_index < len(inner_tokens)
                    and inner_tokens[index + 1]["type"] == "EQUAL"
                    and inner_tokens[value_index]["type"] == "ATTR_VALUE"
                ):
                    value = inner_tokens[value_index]["value"].strip("'\"")
                    references.add(value)
                    references.add(value.split(".")[-1])
            return references

        # A validated edit to a reusable SQL fragment necessarily changes the
        # expanded signature of its include consumers. Propagate that trust
        # only through explicit include dependencies; unrelated statements
        # must still match their independently validated signatures exactly.
        impacted_statement_keys = set()
        if changed_fragment_ids:
            changed_aliases = set(changed_fragment_ids)
            changed_aliases.update(item.split(".")[-1] for item in changed_fragment_ids)
            expanded = True
            while expanded:
                expanded = False
                for element in elements:
                    if element["tag"] != "sql" or "id" not in element["attrs"]:
                        continue
                    if included_fragment_ids(element).intersection(changed_aliases):
                        fragment_id = element["attrs"]["id"]
                        if fragment_id not in changed_aliases:
                            changed_aliases.add(fragment_id)
                            changed_aliases.add(fragment_id.split(".")[-1])
                            expanded = True
            for element in elements:
                if "id" in element["attrs"] and included_fragment_ids(element).intersection(
                    changed_aliases
                ):
                    impacted_statement_keys.add((element["tag"], element["attrs"]["id"]))

        mismatches = [
            (actual, expected)
            for actual, expected in zip(actual_signatures, expected_signatures)
            if actual != expected and actual[:2] not in impacted_statement_keys
        ]
        if len(actual_signatures) != len(expected_signatures) or mismatches:
            mismatch = (
                mismatches[0][0][:2]
                if mismatches
                else ("statement", "unknown")
            )
            raise ValueError(
                "protected MyBatis SQL syntax changed after source mapping for "
                f"<{mismatch[0]}> id={mismatch[1]!r}"
            )
        return fixed_content
