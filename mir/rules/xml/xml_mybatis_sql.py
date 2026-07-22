from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.rules_loader import load_rules_for_language
from mir.rules.xml.xml_utils import tokenize_xml
from mir.engine.embedded_bridge import check_embedded_content, fix_embedded_content

def parse_xml_elements(tokens: List[dict]) -> List[dict]:
    elements = []
    n = len(tokens)
    i = 0
    while i < n:
        t = tokens[i]
        if t["type"] == "TAG_OPEN_START":
            tag_name = t["value"][1:].lower()
            
            tag_end_idx = -1
            attrs = {}
            j = i + 1
            while j < n:
                if tokens[j]["type"] == "TAG_END":
                    tag_end_idx = j
                    break
                if tokens[j]["type"] == "ATTR_NAME":
                    attr_name = tokens[j]["value"]
                    if j + 2 < n and tokens[j+1]["type"] == "EQUAL" and tokens[j+2]["type"] == "ATTR_VALUE":
                        val = tokens[j+2]["value"]
                        if len(val) >= 2 and val[0] in ("'", '"') and val[-1] == val[0]:
                            val = val[1:-1]
                        attrs[attr_name] = val
                        j += 3
                        continue
                j += 1
                
            if tag_end_idx != -1:
                is_self_closing = tokens[tag_end_idx]["value"] == "/>"
                if is_self_closing:
                    elements.append({
                        "tag": tag_name,
                        "attrs": attrs,
                        "start_idx": i,
                        "end_idx": tag_end_idx,
                        "inner_tokens": [],
                        "start_offset": tokens[i]["start"],
                        "end_offset": tokens[tag_end_idx]["end"]
                    })
                    i = tag_end_idx + 1
                    continue
                
                depth = 1
                close_idx = -1
                k = tag_end_idx + 1
                while k < n:
                    if tokens[k]["type"] == "TAG_OPEN_START":
                        if tokens[k]["value"][1:].lower() == tag_name:
                            depth += 1
                    elif tokens[k]["type"] == "TAG_CLOSE_START":
                        if tokens[k]["value"][2:].lower() == tag_name:
                            depth -= 1
                            if depth == 0:
                                close_idx = k
                                break
                    k += 1
                
                if close_idx != -1:
                    close_end_idx = -1
                    for m in range(close_idx + 1, n):
                        if tokens[m]["type"] == "TAG_END":
                            close_end_idx = m
                            break
                    
                    if close_end_idx != -1:
                        elements.append({
                            "tag": tag_name,
                            "attrs": attrs,
                            "start_idx": i,
                            "end_idx": close_end_idx,
                            "inner_tokens": tokens[tag_end_idx + 1 : close_idx],
                            "start_offset": tokens[i]["start"],
                            "end_offset": tokens[close_end_idx]["end"]
                        })
                        i = close_end_idx + 1
                        continue
        i += 1
    return elements

def get_all_elements_recursively(elements: List[dict]) -> List[dict]:
    res = []
    for el in elements:
        res.append(el)
        inner_el = parse_xml_elements(el["inner_tokens"])
        res.extend(get_all_elements_recursively(inner_el))
    return res

def expand_tokens(inner_tokens: List[dict], sql_defs: Dict[str, List[dict]], expanded_chars: List[str], mapping: List[int], is_after_tag: List[bool], state: dict = None):
    if state is None:
        state = {"last_tag_line": -1, "last_tag_type": None}
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
                
                after = False
                if state["last_tag_type"] in ("if", "choose", "when", "otherwise", "include", "case"):
                    after = True
                is_after_tag.extend([after] * len_val)
                
                if tok["type"] == "TEXT":
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
                    
                    after = False
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
                    
                    after = False
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
                            
                    expand_tokens(inner_tokens[tag_end_idx + 1 : close_idx], sql_defs, expanded_chars, mapping, is_after_tag, state)
                    close_end_idx = -1
                    for m in range(close_idx + 1, n_tok):
                        if inner_tokens[m]["type"] == "TAG_END":
                            close_end_idx = m
                            break
                    if close_end_idx != -1:
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

class XmlMybatisSqlRule(BaseRule):
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
            "correct": '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT id,\n            name\n        FROM users\n        <if test="distinct">\n            , distinct_val\n        </if>\n    </select>\n</mapper>'
        }
    ]
    additional_validations = [
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT my_column FROM my_schema.my_table t\n    </select>\n</mapper>',
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT id,\n            name\n        FROM users\n        <if test="distinct">\n            , distinct_val\n        </if>\n    </select>\n</mapper>'
    ]

    def __init__(self) -> None:
        super().__init__()
        # Exclude structural/layout rules that can modify query token-to-line boundaries, but ALLOW indentation/alignment rules
        self.excluded_rule_ids = {
            "IR-eof-newline", "IR-trailing-semicolon", "IR-statement-semicolon",
            "IR-blank-lines", "IR-statement-blank-lines",
            "IR-from-multi", "IR-from-single", "IR-from-paren-layout",
            "IR-where-multi", "IR-where-single", "IR-column-layout",
            "IR-subquery-indent", "IR-subquery-compact", "IR-dollar-quote-alignment",
            "IR-table-field-spacing", "IR-trigger-layout", "IR-create-view-indent",
            "IR-function-body-indent", "IR-function-header-layout", "IR-raise-layout",
            "IR-plpgsql-block-indent", "IR-update-layout", "IR-case-layout",
            "IR-join-on-multi", "IR-cte-format",
            "IR-paren-content-indent", "IR-paren-multi",
            "IR-paren-single", "IR-join-parens", "IR-union-layout"
        }
        self.sql_rules = None
        self._expansion_cache = {}

    def _is_mybatis_file(self, content: str) -> bool:
        lower_content = content.lower()
        return "mybatis.org" in lower_content or "<mapper" in lower_content

    def _find_violations(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[dict]:
        if not self._is_mybatis_file(content):
            return []

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
                
                inner_config = dict(rule_config)
                if "_lines" in inner_config:
                    del inner_config["_lines"]

                embedded_violations = check_embedded_content(
                    guest_language="sql",
                    guest_text=sql_text,
                    mapping=mapping,
                    file_path=file_path,
                    rule_config=inner_config,
                    excluded_rule_ids=self.excluded_rule_ids,
                    extra_check_args={
                        "ignored_comma_offsets": ignored_comma_offsets,
                        "base_indent": base_indent,
                        "tag_ranges": tag_ranges,
                        "original_xml": content
                    }
                )
                
                for ev in embedded_violations:
                    abs_line = content[:ev["mapped_offset"]].count('\n') + 1
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

        sql_defs = {}
        for el in elements:
            if el["tag"] == "sql" and "id" in el["attrs"]:
                sql_id = el["attrs"]["id"]
                sql_defs[sql_id] = el["inner_tokens"]
                if "." in sql_id:
                    sql_defs[sql_id.split(".")[-1]] = el["inner_tokens"]

        target_tags = {"select", "insert", "update", "delete", "sql"}
        all_xml_edits = []
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
                
                inner_config = dict(rule_config)
                if "_lines" in inner_config:
                    del inner_config["_lines"]

                applied_rules = set()
                from mir.engine.embedded_bridge import fix_embedded_content
                edits = fix_embedded_content(
                    guest_language="sql",
                    guest_text=sql_text,
                    mapping=mapping,
                    file_path=file_path,
                    rule_config=inner_config,
                    excluded_rule_ids=self.excluded_rule_ids,
                    extra_fix_args={
                        "ignored_comma_offsets": ignored_comma_offsets,
                        "base_indent": base_indent,
                        "tag_ranges": tag_ranges,
                        "original_xml": content,
                        "applied_rules": applied_rules
                    }
                )
                if edits:
                    all_xml_edits.extend(edits)
                    rules_fixed_set = rule_config.get("rules_fixed")
                    if rules_fixed_set is not None:
                        rules_fixed_set.update(applied_rules)

        if not all_xml_edits:
            return content

        seen_edits = set()
        unique_edits = []
        for start, end, replacement in all_xml_edits:
            key = (start, end, replacement)
            if key not in seen_edits:
                seen_edits.add(key)
                unique_edits.append((start, end, replacement))

        unique_edits.sort(key=lambda x: (x[0], x[1]))
        resolved_edits = []
        last_end = -1
        for start, end, replacement in unique_edits:
            if start == end:
                if start > last_end:
                    resolved_edits.append((start, end, replacement))
                    last_end = end
            else:
                if start >= last_end:
                    resolved_edits.append((start, end, replacement))
                    last_end = end

        resolved_edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in resolved_edits:
            chars[start:end] = list(new_text)

        return "".join(chars)
