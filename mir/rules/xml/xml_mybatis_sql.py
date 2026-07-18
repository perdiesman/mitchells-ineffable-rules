from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.rules_loader import load_rules_for_language
from mir.rules.xml.xml_utils import tokenize_xml

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
                        "inner_tokens": []
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
                            "inner_tokens": tokens[tag_end_idx + 1 : close_idx]
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

def expand_tokens(inner_tokens: List[dict], sql_defs: Dict[str, List[dict]], expanded_chars: List[str], mapping: List[int]):
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
                # Find local def
                if refid:
                    # Strip mapper namespace prefixes if present (e.g. namespace.id)
                    short_refid = refid.split(".")[-1]
                    matched_tokens = None
                    if refid in sql_defs:
                        matched_tokens = sql_defs[refid]
                    elif short_refid in sql_defs:
                        matched_tokens = sql_defs[short_refid]
                        
                    if matched_tokens:
                        expand_tokens(matched_tokens, sql_defs, expanded_chars, mapping)
                i = tag_end_idx + 1
                continue
                
        if tok["type"] == "TEXT":
            val = tok["value"]
            start_offset = tok["start"]
            for offset_in_val, char in enumerate(val):
                expanded_chars.append(char)
                mapping.append(start_offset + offset_in_val)
            i += 1
            continue
            
        if tok["type"] == "TAG_OPEN_START":
            tag_name = tok["value"][1:].lower()
            tag_end_idx = -1
            j = i + 1
            while j < n_tok:
                if inner_tokens[j]["type"] == "TAG_END":
                    tag_end_idx = j
                    break
                j += 1
                
            if tag_end_idx != -1:
                is_self_closing = inner_tokens[tag_end_idx]["value"] == "/>"
                if is_self_closing:
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
                    expand_tokens(inner_tokens[tag_end_idx + 1 : close_idx], sql_defs, expanded_chars, mapping)
                    close_end_idx = -1
                    for m in range(close_idx + 1, n_tok):
                        if inner_tokens[m]["type"] == "TAG_END":
                            close_end_idx = m
                            break
                    if close_end_idx != -1:
                        i = close_end_idx + 1
                        continue
        i += 1

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
        }
    ]
    additional_validations = [
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT my_column FROM my_schema.my_table t\n    </select>\n</mapper>'
    ]

    def __init__(self) -> None:
        super().__init__()
        # Exclude structure-level and layout-level rules
        self.excluded_rule_ids = {
            "IR-indent", "IR-eof-newline", "IR-trailing-semicolon", 
            "IR-statement-semicolon", "IR-clause-alignment", 
            "IR-blank-lines", "IR-statement-blank-lines",
            "IR-from-multi", "IR-from-single", "IR-from-paren-layout",
            "IR-where-multi", "IR-where-single", "IR-column-layout",
            "IR-subquery-indent", "IR-subquery-compact", "IR-dollar-quote-alignment",
            "IR-table-field-spacing", "IR-trigger-layout", "IR-create-view-indent",
            "IR-function-body-indent", "IR-function-header-layout", "IR-raise-layout",
            "IR-plpgsql-block-indent", "IR-update-layout", "IR-case-layout",
            "IR-join-on-multi"
        }
        self.sql_rules = None

    def _get_sql_rules(self, rule_config: Dict[str, Any]) -> List[BaseRule]:
        all_rules = load_rules_for_language("sql")
        all_configs = rule_config.get("_all_configs", {})
        rules_to_disable = rule_config.get("_rules_to_disable", set())
        rules_to_enable = rule_config.get("_rules_to_enable", set())
        
        filtered = []
        for rule in all_rules:
            if rule.rule_id in self.excluded_rule_ids:
                continue
                
            if rule.rule_id in rules_to_disable or f"sql:{rule.rule_id}" in rules_to_disable:
                continue
                
            individual_cfg = all_configs.get(rule.rule_id, {})
            if isinstance(individual_cfg, dict) and individual_cfg.get("enabled") is False:
                continue
                
            is_enabled = True
            if isinstance(individual_cfg, dict) and "enabled" in individual_cfg:
                is_enabled = individual_cfg["enabled"]
            else:
                is_enabled = rule.enabled_by_default
                    
            if is_enabled:
                filtered.append(rule)
                
        return filtered

    def _is_mybatis_file(self, content: str) -> bool:
        lower_content = content.lower()
        return "mybatis.org" in lower_content or "<mapper" in lower_content

    def _find_violations(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[dict]:
        if not self._is_mybatis_file(content):
            return []

        tokens = tokenize_xml(content)
        root_elements = parse_xml_elements(tokens)
        elements = get_all_elements_recursively(root_elements)
        sql_rules_to_run = self._get_sql_rules(rule_config)

        # Build sql_defs mapping local SQL ids
        sql_defs = {}
        for el in elements:
            if el["tag"] == "sql" and "id" in el["attrs"]:
                sql_id = el["attrs"]["id"]
                sql_defs[sql_id] = el["inner_tokens"]
                # Also index by short ID
                if "." in sql_id:
                    sql_defs[sql_id.split(".")[-1]] = el["inner_tokens"]

        violations = []
        target_tags = {"select", "insert", "update", "delete"}

        for el in elements:
            if el["tag"] in target_tags and "id" in el["attrs"]:
                expanded_chars = []
                mapping = []
                expand_tokens(el["inner_tokens"], sql_defs, expanded_chars, mapping)
                sql_text = "".join(expanded_chars)
                
                if not sql_text.strip():
                    continue
                    
                # Run SQL rules on this block
                for rule in sql_rules_to_run:
                    try:
                        sql_violations = rule.check(sql_text, file_path, {})
                        for sv in sql_violations:
                            # Map line relative to sql block start line in XML file
                            # Find line number of the start character of this violation
                            start_exp = None
                            # We search for the first character of the offending range that has a mapping
                            # (usually sv.line_number tells us the line number inside sql_text)
                            sql_lines = sql_text.splitlines()
                            # Estimate start character offset for this line
                            char_offset = 0
                            for line_idx in range(sv.line_number - 1):
                                if line_idx < len(sql_lines):
                                    char_offset += len(sql_lines[line_idx]) + 1
                                    
                            if char_offset < len(mapping):
                                abs_line = tokens[0]["line"] # default fallback
                                # Find first text token mapped to this range
                                mapped_idx = mapping[char_offset]
                                # Find line number corresponding to this original character index
                                # by scanning XML tokens
                                for tok in tokens:
                                    if tok["start"] <= mapped_idx <= tok["end"]:
                                        abs_line = tok["line"]
                                        break
                            else:
                                abs_line = el["inner_tokens"][0]["line"] if el["inner_tokens"] else el["start_idx"]
                                
                            violations.append({
                                "rule_id": rule.rule_id,
                                "line": abs_line,
                                "message": f"[MyBatis SQL: {rule.rule_id}] {sv.message}",
                                "is_fixable": sv.is_fixable
                            })
                    except Exception:
                        pass
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, file_path, rule_config)
        for v in offending:
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
        root_elements = parse_xml_elements(tokens)
        elements = get_all_elements_recursively(root_elements)
        sql_rules_to_run = self._get_sql_rules(rule_config)

        # Build sql_defs mapping local SQL ids
        sql_defs = {}
        for el in elements:
            if el["tag"] == "sql" and "id" in el["attrs"]:
                sql_id = el["attrs"]["id"]
                sql_defs[sql_id] = el["inner_tokens"]
                if "." in sql_id:
                    sql_defs[sql_id.split(".")[-1]] = el["inner_tokens"]

        target_tags = {"select", "insert", "update", "delete"}
        all_xml_edits = []

        for el in elements:
            if el["tag"] in target_tags and "id" in el["attrs"]:
                expanded_chars = []
                mapping = []
                expand_tokens(el["inner_tokens"], sql_defs, expanded_chars, mapping)
                sql_text = "".join(expanded_chars)
                
                if not sql_text.strip():
                    continue
                    
                # Run fixes on the expanded SQL
                fixed_sql = sql_text
                for rule in sql_rules_to_run:
                    if rule.is_fixable in ("yes", "sometimes"):
                        try:
                            fixed_sql = rule.fix(fixed_sql, file_path, {})
                        except Exception:
                            pass
                
                if fixed_sql != sql_text:
                    # Compute diff / edits between sql_text and fixed_sql
                    # Since they can differ, we can do a simple character diff or use a sequence matcher.
                    # A robust character-by-character replacement works if we do it segment by segment.
                    # But simpler: if the rules only made small changes, we can find the changed parts.
                    # Or we can do a standard python difflib SequenceMatcher!
                    import difflib
                    sm = difflib.SequenceMatcher(None, sql_text, fixed_sql)
                    for tag, i1, i2, j1, j2 in sm.get_opcodes():
                        if tag in ("replace", "delete", "insert"):
                            # Translate expanded SQL range [i1:i2] to original XML offsets
                            # Check if the range is contiguous in the original XML content
                            is_contiguous = True
                            if i1 < i2:
                                for k in range(i1 + 1, i2):
                                    if mapping[k] - mapping[k - 1] != 1:
                                        is_contiguous = False
                                        break
                                        
                            if is_contiguous:
                                start_orig = mapping[i1] if i1 < len(mapping) else (mapping[-1] + 1 if mapping else 0)
                                end_orig = mapping[i2 - 1] + 1 if i2 <= len(mapping) and i2 > 0 else start_orig
                                replacement = fixed_sql[j1:j2]
                                all_xml_edits.append((start_orig, end_orig, replacement))

        if not all_xml_edits:
            return content

        # Deduplicate identical edits
        seen_edits = set()
        unique_edits = []
        for start, end, replacement in all_xml_edits:
            key = (start, end, replacement)
            if key not in seen_edits:
                seen_edits.add(key)
                unique_edits.append((start, end, replacement))

        # Resolve overlapping edits (including multiple insertions at the same point)
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

        # Apply edits in reverse order
        resolved_edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in resolved_edits:
            chars[start:end] = list(new_text)

        return "".join(chars)
