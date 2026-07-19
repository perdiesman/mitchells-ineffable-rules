from typing import List, Dict, Any, Tuple
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.rules_loader import load_rules_for_language
import difflib

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
                (is_enabled is True) or
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
    
    check_args = {}
    if extra_check_args:
        check_args.update(extra_check_args)
        
    for rule in guest_rules:
        try:
            sql_violations = rule.check(guest_text, file_path, check_args)
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
    
    fix_args = {}
    if extra_fix_args:
        fix_args.update(extra_fix_args)
        
    for rule in guest_rules:
        if rule.is_fixable in ("yes", "sometimes"):
            try:
                fixed_text = rule.fix(fixed_text, file_path, fix_args)
            except Exception:
                pass
                
    edits = []
    if fixed_text != guest_text:
        guest_lines = guest_text.splitlines(keepends=True)
        fixed_lines = fixed_text.splitlines(keepends=True)
        
        if len(guest_lines) == len(fixed_lines):
            guest_offset = 0
            for gl, fl in zip(guest_lines, fixed_lines):
                if gl != fl:
                    gl_stripped = gl.rstrip("\r\n")
                    fl_stripped = fl.rstrip("\r\n")
                    
                    sm = difflib.SequenceMatcher(None, gl_stripped, fl_stripped)
                    for tag, i1, i2, j1, j2 in sm.get_opcodes():
                        if tag in ("replace", "delete", "insert"):
                            g_i1 = guest_offset + i1
                            g_i2 = guest_offset + i2
                            
                            is_contiguous = True
                            if g_i1 < g_i2:
                                for k in range(g_i1 + 1, g_i2):
                                    if mapping[k] - mapping[k - 1] != 1:
                                        is_contiguous = False
                                        break
                                        
                            if is_contiguous:
                                start_orig = mapping[g_i1] if g_i1 < len(mapping) else (mapping[-1] + 1 if mapping else 0)
                                end_orig = mapping[g_i2 - 1] + 1 if g_i2 <= len(mapping) and g_i2 > 0 else start_orig
                                replacement = fl_stripped[j1:j2]
                                orig_str = gl_stripped[i1:i2]
                                
                                if orig_str.strip() == "" and replacement.strip() == "":
                                    if all(c in " \t\r\n" for c in orig_str) and all(c in " \t\r\n" for c in replacement):
                                        continue
                                        
                                edits.append((start_orig, end_orig, replacement))
                guest_offset += len(gl)
        else:
            sm = difflib.SequenceMatcher(None, guest_text, fixed_text)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag in ("replace", "delete", "insert"):
                    is_contiguous = True
                    if i1 < i2:
                        for k in range(i1 + 1, i2):
                            if mapping[k] - mapping[k - 1] != 1:
                                is_contiguous = False
                                break
                                
                    if is_contiguous:
                        start_orig = mapping[i1] if i1 < len(mapping) else (mapping[-1] + 1 if mapping else 0)
                        end_orig = mapping[i2 - 1] + 1 if i2 <= len(mapping) and i2 > 0 else start_orig
                        replacement = fixed_text[j1:j2]
                        orig_str = guest_text[i1:i2]
                        
                        if orig_str.strip() == "" and replacement.strip() == "":
                            if all(c in " \t\r\n" for c in orig_str) and all(c in " \t\r\n" for c in replacement):
                                continue
                                
                        edits.append((start_orig, end_orig, replacement))
                        
    return edits
