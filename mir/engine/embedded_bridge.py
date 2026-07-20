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
    
    # 1. Build original tokens
    tag_starts = {t_start: idx for idx, (t_start, t_end) in enumerate(tag_ranges)}
    orig_tokens = []
    i = 0
    n = len(original_xml)
    while i < n:
        if i in tag_starts:
            tag_idx = tag_starts[i]
            orig_tokens.append(("TAG", tag_idx))
            i = tag_ranges[tag_idx][1]
        else:
            char = original_xml[i]
            if char in structural_chars:
                orig_tokens.append(("CHAR", char))
            i += 1
            
    # 2. Apply edits to get fixed_xml
    chars = list(original_xml)
    sorted_edits_desc = sorted(edits, key=lambda x: x[0], reverse=True)
    for start, end, new_text in sorted_edits_desc:
        chars[start:end] = list(new_text)
    fixed_xml = "".join(chars)
    
    # 3. Compute new tag offsets in fixed_xml
    def get_new_offset(pos):
        shift = 0
        for start, end, new_text in sorted_edits_asc:
            if pos <= start:
                break
            shift += len(new_text) - (end - start)
        return pos + shift
        
    fixed_tag_ranges = []
    for t_start, t_end in tag_ranges:
        fixed_tag_ranges.append((get_new_offset(t_start), get_new_offset(t_end)))
        
    fixed_tag_starts = {f_start: idx for idx, (f_start, f_end) in enumerate(fixed_tag_ranges)}
    
    # 4. Build fixed tokens
    fixed_tokens = []
    i = 0
    n_fixed = len(fixed_xml)
    while i < n_fixed:
        if i in fixed_tag_starts:
            tag_idx = fixed_tag_starts[i]
            fixed_tokens.append(("TAG", tag_idx))
            i = fixed_tag_ranges[tag_idx][1]
        else:
            char = fixed_xml[i]
            if char in structural_chars:
                fixed_tokens.append(("CHAR", char))
            i += 1
            
    return orig_tokens == fixed_tokens

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
                fixed_text = rule.fix(fixed_text, file_path, guest_rule_config)
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
                g_start_char = guest_line_offsets[i1]
                g_end_char = guest_line_offsets[i2]

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
                    block_fixed_lines = fixed_text.splitlines(keepends=True)[j1:j2]
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
