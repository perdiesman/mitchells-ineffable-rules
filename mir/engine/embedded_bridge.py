from typing import List, Dict, Any, Tuple
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.rules_loader import load_rules_for_language
from mir.rules.sql.sql_utils import tokenize_sql
import difflib

def xml_encode(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def find_single_difference(s1: str, s2: str) -> Tuple[int, int, int, int]:
    n1, n2 = len(s1), len(s2)
    prefix_len = 0
    while prefix_len < n1 and prefix_len < n2 and s1[prefix_len] == s2[prefix_len]:
        prefix_len += 1
    suffix_len = 0
    while (suffix_len < n1 - prefix_len and 
           suffix_len < n2 - prefix_len and 
           s1[n1 - 1 - suffix_len] == s2[n2 - 1 - suffix_len]):
        suffix_len += 1
    return (prefix_len, n1 - suffix_len, prefix_len, n2 - suffix_len)

def get_guest_rules(guest_language: str, rule_config: Dict[str, Any], excluded_rule_ids: set = None) -> List[BaseRule]:
    all_rules = load_rules_for_language(guest_language)
    all_configs = rule_config.get("_all_configs", {})
    rules_to_disable = rule_config.get("_rules_to_disable", set())
    rules_to_enable = rule_config.get("_rules_to_enable", set())
    disable_all = rule_config.get("_disable_all", False)
    
    filtered = []
    for rule in all_rules:
        if excluded_rule_ids and rule.rule_id in excluded_rule_ids:
            continue
            
        if rule.rule_id in rules_to_disable or f"{guest_language}:{rule.rule_id}" in rules_to_disable:
            continue
            
        individual_cfg = all_configs.get(rule.rule_id, {})
        if isinstance(individual_cfg, dict) and individual_cfg.get("enabled") is False:
            continue
            
        is_enabled = True
        if isinstance(individual_cfg, dict) and "enabled" in individual_cfg:
            is_enabled = individual_cfg["enabled"]
        else:
            is_enabled = rule.enabled_by_default
            
        if disable_all:
            is_enabled = (
                (is_enabled is True and isinstance(individual_cfg, dict) and individual_cfg.get("enabled") is True) or
                (rule.rule_id in rules_to_enable) or
                (f"{guest_language}:{rule.rule_id}" in rules_to_enable)
            )
            
        if is_enabled:
            filtered.append(rule)
            
    return filtered

def check_embedded_content(
    guest_language: str,
    guest_text: str,
    mapping: List[int],
    file_path: str,
    rule_config: Dict[str, Any],
    excluded_rule_ids: set = None,
    extra_check_args: Dict[str, Any] = None
) -> List[dict]:
    guest_rules = get_guest_rules(guest_language, rule_config, excluded_rule_ids)
    violations = []
    
    all_configs = rule_config.get("_all_configs", {})
    
    for rule in guest_rules:
        guest_rule_config = {}
        global_config = all_configs.get(rule.rule_id, {})
        lang_config = all_configs.get(f"{guest_language}:{rule.rule_id}", {})
        
        if isinstance(global_config, dict):
            guest_rule_config.update(global_config)
        if isinstance(lang_config, dict):
            guest_rule_config.update(lang_config)
            
        guest_rule_config["_all_configs"] = all_configs
        guest_rule_config["_lang"] = guest_language
        guest_rule_config["_rules_to_disable"] = rule_config.get("_rules_to_disable", set())
        guest_rule_config["_rules_to_enable"] = rule_config.get("_rules_to_enable", set())
        guest_rule_config["_disable_all"] = rule_config.get("_disable_all", False)
        
        if extra_check_args:
            guest_rule_config.update(extra_check_args)
            
        if rule.rule_id == "IR-comma-style":
            ignored_comma_offsets = set()
            tag_ranges = extra_check_args.get("tag_ranges") if extra_check_args else None
            if tag_ranges and mapping:
                tokens = tokenize_sql(guest_text)
                active = [t for t in tokens if t["type"] not in ("WHITESPACE", "COMMENT")]
                for a_idx, t in enumerate(active):
                    if t["value"] == "," and a_idx > 0:
                        prev_active = active[a_idx - 1]
                        start_orig = mapping[prev_active["end"]] if prev_active["end"] < len(mapping) else mapping[-1]
                        end_orig = mapping[t["start"]] if t["start"] < len(mapping) else mapping[-1]
                        
                        for t_start, t_end in tag_ranges:
                            if max(start_orig, t_start) < min(end_orig, t_end):
                                ignored_comma_offsets.add(t["start"])
                                break
            if ignored_comma_offsets:
                guest_rule_config["ignored_comma_offsets"] = ignored_comma_offsets
            
        try:
            sql_violations = rule.check(guest_text, file_path, guest_rule_config)
            for sv in sql_violations:
                guest_lines = guest_text.splitlines()
                char_offset = 0
                for line_idx in range(sv.line_number - 1):
                    if line_idx < len(guest_lines):
                        char_offset += len(guest_lines[line_idx]) + 1
                        
                if char_offset < len(mapping):
                    mapped_idx = mapping[char_offset]
                    violations.append({
                        "rule_id": rule.rule_id,
                        "mapped_offset": mapped_idx,
                        "message": sv.message,
                        "is_fixable": sv.is_fixable
                    })
        except Exception:
            pass
            
    return violations

def is_fixed_text_xml_safe(original_xml: str, tag_ranges: List[Tuple[int, int]], edits: List[Tuple[int, int, str]]) -> bool:
    if not tag_ranges:
        return True
        
    sorted_edits_asc = sorted(edits, key=lambda x: x[0])
    structural_chars = {",", "(", ")", "+", "-", "*", "/", "=", "<", ">", "!", "|", "&", ";", "."}
    
    # 1. Apply edits to get fixed_xml
    chars = list(original_xml)
    sorted_edits_desc = sorted(edits, key=lambda x: x[0], reverse=True)
    for start, end, new_text in sorted_edits_desc:
        chars[start:end] = list(new_text)
    fixed_xml = "".join(chars)
    
    # 2. Compute new tag offsets in fixed_xml
    def get_new_offset(pos, is_end=False):
        shift = 0
        for start, end, new_text in sorted_edits_asc:
            if is_end:
                if pos <= start:
                    break
            else:
                if pos < start:
                    break
            shift += len(new_text) - (end - start)
        return pos + shift
        
    fixed_tag_ranges = []
    for t_start, t_end in tag_ranges:
        fixed_tag_ranges.append((get_new_offset(t_start, False), get_new_offset(t_end, True)))
        
    def get_zone(pos, t_start, t_end):
        if pos < t_start:
            return 0
        elif pos >= t_end:
            return 2
        else:
            return 1
            
    import bisect
    
    # Check each structural character type for crossing migrations
    for char_type in structural_chars:
        orig_offsets = []
        for idx, c in enumerate(original_xml):
            if c == char_type:
                orig_offsets.append(idx)
                
        fixed_offsets = []
        for idx, c in enumerate(fixed_xml):
            if c == char_type:
                fixed_offsets.append(idx)
                
        # Pre-compute character count modifications per edit using C-speed .count()
        edit_counts = []
        for start, end, replacement in edits:
            del_cnt = original_xml[start:end].count(char_type)
            ins_cnt = replacement.count(char_type)
            edit_counts.append((start, end, del_cnt, ins_cnt))
                
        for tag_idx, (t_start, t_end) in enumerate(tag_ranges):
            t_start_new, t_end_new = fixed_tag_ranges[tag_idx]
            
            # O(log N) binary search instead of O(N) generator sums
            orig_left = bisect.bisect_left(orig_offsets, t_start)
            orig_inside = bisect.bisect_left(orig_offsets, t_end) - orig_left
            
            fixed_left = bisect.bisect_left(fixed_offsets, t_start_new)
            fixed_inside = bisect.bisect_left(fixed_offsets, t_end_new) - fixed_left
            
            del_left = 0
            ins_left = 0
            del_inside = 0
            ins_inside = 0
            total_del_char = 0
            total_ins_char = 0
            
            for start, end, del_cnt, ins_cnt in edit_counts:
                total_del_char += del_cnt
                total_ins_char += ins_cnt
                
                if end <= t_start:
                    del_left += del_cnt
                    ins_left += ins_cnt
                elif start >= t_end:
                    pass
                else:
                    del_inside += del_cnt
                    ins_inside += ins_cnt
                    
            if total_del_char == total_ins_char:
                if fixed_left != orig_left or fixed_inside != orig_inside:
                    return False
            else:
                expected_left = orig_left - del_left + ins_left
                expected_inside = orig_inside - del_inside + ins_inside
                if fixed_left != expected_left or fixed_inside != expected_inside:
                    return False
                                
    return True

def fix_embedded_content(
    guest_language: str,
    guest_text: str,
    mapping: List[int],
    file_path: str,
    rule_config: Dict[str, Any],
    excluded_rule_ids: set = None,
    extra_fix_args: Dict[str, Any] = None
) -> List[Tuple[int, int, str]]:
    guest_rules = get_guest_rules(guest_language, rule_config, excluded_rule_ids)
    fixed_text = guest_text
    
    all_configs = rule_config.get("_all_configs", {})
    
    for rule in guest_rules:
        if rule.is_fixable in ("yes", "sometimes"):
            guest_rule_config = {}
            global_config = all_configs.get(rule.rule_id, {})
            lang_config = all_configs.get(f"{guest_language}:{rule.rule_id}", {})
            
            if isinstance(global_config, dict):
                guest_rule_config.update(global_config)
            if isinstance(lang_config, dict):
                guest_rule_config.update(lang_config)
                
            guest_rule_config["_all_configs"] = all_configs
            guest_rule_config["_lang"] = guest_language
            guest_rule_config["_rules_to_disable"] = rule_config.get("_rules_to_disable", set())
            guest_rule_config["_rules_to_enable"] = rule_config.get("_rules_to_enable", set())
            guest_rule_config["_disable_all"] = rule_config.get("_disable_all", False)
            
            if extra_fix_args:
                guest_rule_config.update(extra_fix_args)
                
            if rule.rule_id == "IR-comma-style":
                ignored_comma_offsets = set()
                tag_ranges = extra_fix_args.get("tag_ranges") if extra_fix_args else None
                if tag_ranges and mapping:
                    tokens = tokenize_sql(fixed_text)
                    active = [t for t in tokens if t["type"] not in ("WHITESPACE", "COMMENT")]
                    for a_idx, t in enumerate(active):
                        if t["value"] == "," and a_idx > 0:
                            prev_active = active[a_idx - 1]
                            start_orig = mapping[prev_active["end"]] if prev_active["end"] < len(mapping) else mapping[-1]
                            end_orig = mapping[t["start"]] if t["start"] < len(mapping) else mapping[-1]
                            
                            for t_start, t_end in tag_ranges:
                                if max(start_orig, t_start) < min(end_orig, t_end):
                                    ignored_comma_offsets.add(t["start"])
                                    break
                if ignored_comma_offsets:
                    guest_rule_config["ignored_comma_offsets"] = ignored_comma_offsets
                
            try:
                prev_text = fixed_text
                fixed_text = rule.fix(fixed_text, file_path, guest_rule_config)
                if fixed_text != prev_text and extra_fix_args and "applied_rules" in extra_fix_args:
                    extra_fix_args["applied_rules"].add(rule.rule_id)
            except Exception:
                pass
                
    edits = []
    if fixed_text != guest_text:
        guest_line_offsets = []
        offset = 0
        for line in guest_text.splitlines(keepends=True):
            guest_line_offsets.append(offset)
            offset += len(line)
        guest_line_offsets.append(offset)

        guest_lines_stripped = [l.rstrip("\r\n") for l in guest_text.splitlines(keepends=True)]
        fixed_lines_stripped = [l.rstrip("\r\n") for l in fixed_text.splitlines(keepends=True)]

        sm = difflib.SequenceMatcher(None, guest_lines_stripped, fixed_lines_stripped)
        tag_ranges = extra_fix_args.get("tag_ranges") if extra_fix_args else None

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("replace", "delete", "insert"):
                sub_ops = []
                if tag == "replace" and (i2 - i1 == j2 - j1):
                    for k in range(i2 - i1):
                        sub_ops.append((tag, i1 + k, i1 + k + 1, j1 + k, j1 + k + 1))
                else:
                    sub_ops.append((tag, i1, i2, j1, j2))
                    
                for sub_tag, sub_i1, sub_i2, sub_j1, sub_j2 in sub_ops:
                    g_start_char = guest_line_offsets[sub_i1]
                    g_end_char = guest_line_offsets[sub_i2]

                    is_contiguous = True
                    start_orig = mapping[g_start_char] if g_start_char < len(mapping) else (mapping[-1] + 1 if mapping else 0)
                    end_orig = mapping[g_end_char - 1] + 1 if g_end_char <= len(mapping) and g_end_char > 0 else start_orig

                    if tag_ranges is not None:
                        if start_orig < end_orig:
                            for t_start, t_end in tag_ranges:
                                if max(start_orig, t_start) < min(end_orig, t_end):
                                    is_contiguous = False
                                    break
                        else:
                            for t_start, t_end in tag_ranges:
                                if t_start < start_orig < t_end:
                                    is_contiguous = False
                                    break
                    else:
                        if g_start_char < g_end_char:
                            for k in range(g_start_char + 1, g_end_char):
                                if mapping[k] - mapping[k - 1] != 1:
                                    is_contiguous = False
                                    break

                    if is_contiguous:
                        block_fixed_lines = fixed_text.splitlines(keepends=True)[sub_j1:sub_j2]
                        replacement = "".join(block_fixed_lines)
                        if file_path.endswith(".xml"):
                            replacement = xml_encode(replacement)

                        orig_str = guest_text[g_start_char:g_end_char]
                        skip = False
                        if orig_str.strip() == "" and replacement.strip() == "":
                            if all(c in " \t\r\n" for c in orig_str) and all(c in " \t\r\n" for c in replacement):
                                if not (extra_fix_args and "base_indent" in extra_fix_args):
                                    skip = True

                        if not skip:
                            edits.append((start_orig, end_orig, replacement))

    if edits and extra_fix_args and "original_xml" in extra_fix_args and "tag_ranges" in extra_fix_args:
        original_xml = extra_fix_args["original_xml"]
        tag_ranges = extra_fix_args["tag_ranges"]
        if not is_fixed_text_xml_safe(original_xml, tag_ranges, edits):
            return []

    return edits
