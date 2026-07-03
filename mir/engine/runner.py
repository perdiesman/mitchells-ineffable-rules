import os
import sys
import select
import difflib
from typing import List, Dict, Set, Tuple
from mir.engine.config import Config
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.rules_loader import load_rules_for_language
from mir.engine.disabler import get_disabled_rules_map, get_file_language
from mir.engine.rules_help import get_supported_languages

def resolve_rule_config(config: Config, rule_id: str, lang: str, detected_base_indent: str = None) -> dict:
    global_config = config.rule_configs.get(rule_id, {})
    lang_config = config.rule_configs.get(f"{lang}:{rule_id}", {})
    
    rule_config = {}
    if isinstance(global_config, dict):
        rule_config.update(global_config)
    if isinstance(lang_config, dict):
        rule_config.update(lang_config)
        
    rule_config["_all_configs"] = config.rule_configs
    rule_config["_lang"] = lang
    
    if "base_indent" not in rule_config and detected_base_indent is not None:
        rule_config["base_indent"] = detected_base_indent
        
    return rule_config

def detect_base_indent(content: str) -> str:
    for line in content.splitlines():
        if line.strip():
            indent = ""
            for char in line:
                if char in (" ", "\t"):
                    indent += char
                else:
                    break
            return indent
    return ""


def find_files(paths: List[str], include_dirs: List[str] = None) -> List[str]:
    """
    Finds all files to lint recursively from the input paths, dynamically resolving
    supported file extensions from rule directory languages.
    """
    valid_exts = set()
    langs = get_supported_languages(include_dirs)
    for lang in langs:
        if lang == "java":
            valid_exts.add(".java")
            valid_exts.add(".jav")
        else:
            valid_exts.add(f".{lang}")
            
    files_to_lint: List[str] = []
    
    for path in paths:
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in valid_exts:
                files_to_lint.append(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in valid_exts:
                        files_to_lint.append(os.path.join(root, file))
                        
    return sorted(list(set(files_to_lint)))

def format_violation(violation: Violation, file_path: str, verbose: bool, rule_desc: str) -> str:
    """
    Formats a violation according to the verbose flag.
    """
    base_msg = f"{violation.rule_id} {file_path}:{violation.line_number}"
    if not verbose:
        return base_msg
    
    # Verbose format
    lines = []
    lines.append(base_msg)
    lines.append(f"  Description: {rule_desc}")
    if violation.offending_lines:
        lines.append("  Offending line(s):")
        for line in violation.offending_lines:
            lines.append(f"    > {line}")
    return "\n".join(lines)

def run_linter(config: Config) -> int:
    """
    Runs the linting engine based on the given configuration.
    Returns exit code (0 for success, 1 for failures).
    """
    # 1. Check for explicit content parameter or piped stdin
    content = None
    lang = None
    
    if config.content is not None:
        if not config.lang:
            print("Error: Language must be specified when passing raw content (use --lang/--language).", file=sys.stderr)
            return 1
        content = config.content
        lang = config.lang
    else:
        # Check stdin
        stdin_ready = False
        if not sys.stdin.isatty():
            try:
                ready, _, _ = select.select([sys.stdin], [], [], 0.0)
                if ready:
                    stdin_ready = True
            except Exception:
                pass
        if stdin_ready:
            if not config.lang:
                print("Error: Language must be specified when piping input (use --lang/--language).", file=sys.stderr)
                return 1
            content = sys.stdin.read()
            lang = config.lang
            
    if content is not None:
        file_path = "<stdin>"
        detected_base_indent = detect_base_indent(content)
        rules = load_rules_for_language(lang, config.include_dirs, config.rule_mode)
        active_rules = [
            rule for rule in rules
            if rule.rule_id not in config.rules_to_disable and f"{lang}:{rule.rule_id}" not in config.rules_to_disable
        ]
        
        disabled_map = get_disabled_rules_map(content, file_path)
        file_violations = []
        
        for rule in active_rules:
            global_config = config.rule_configs.get(rule.rule_id, {})
            lang_config = config.rule_configs.get(f"{lang}:{rule.rule_id}", {})
            if global_config is False or lang_config is False:
                continue
                
            rule_config = resolve_rule_config(config, rule.rule_id, lang, detected_base_indent)
            if config.disable_all:
                is_enabled = (
                    (rule_config.get("enabled") is True) or
                    (rule.rule_id in config.rules_to_enable) or
                    (f"{lang}:{rule.rule_id}" in config.rules_to_enable)
                )
            else:
                is_enabled = rule_config.get("enabled", rule.enabled_by_default)
                
            if not is_enabled:
                continue
                
            try:
                violations = rule.check(content, file_path, rule_config)
            except Exception as e:
                print(f"Error running rule {rule.rule_id} on {file_path}: {e}", file=sys.stderr)
                continue
                
            rule_disabled_lines = disabled_map.get(rule.rule_id, set())
            for v in violations:
                if v.line_number not in rule_disabled_lines:
                    file_violations.append((v, rule))
                    
        if not file_violations:
            if config.fix:
                print(content, end="")
            return 0
            
        fixable = [item for item in file_violations if item[0].is_fixable and item[1].is_fixable in ("yes", "sometimes")]
        unfixable = [item for item in file_violations if not (item[0].is_fixable and item[1].is_fixable in ("yes", "sometimes"))]
        
        if config.fix:
            current_content = content
            has_changes = True
            pass_num = 0
            max_passes = 5
            unfixable_violations = unfixable
            
            while has_changes and pass_num < max_passes:
                pass_num += 1
                has_changes = False
                
                disabled_map = get_disabled_rules_map(current_content, file_path)
                detected_base_indent = detect_base_indent(current_content)
                
                iter_violations = []
                for rule in active_rules:
                    global_config = config.rule_configs.get(rule.rule_id, {})
                    lang_config = config.rule_configs.get(f"{lang}:{rule.rule_id}", {})
                    if global_config is False or lang_config is False:
                        continue
                        
                    rule_config = resolve_rule_config(config, rule.rule_id, lang, detected_base_indent)
                    if config.disable_all:
                        is_enabled = (
                            (rule_config.get("enabled") is True) or
                            (rule.rule_id in config.rules_to_enable) or
                            (f"{lang}:{rule.rule_id}" in config.rules_to_enable)
                        )
                    else:
                        is_enabled = rule_config.get("enabled", rule.enabled_by_default)
                    if not is_enabled:
                        continue
                        
                    try:
                        violations = rule.check(current_content, file_path, rule_config)
                    except Exception as e:
                        continue
                        
                    rule_disabled_lines = disabled_map.get(rule.rule_id, set())
                    for v in violations:
                        if v.line_number not in rule_disabled_lines:
                            iter_violations.append((v, rule))
                            
                if not iter_violations:
                    break
                    
                fixable = [item for item in iter_violations if item[0].is_fixable and item[1].is_fixable in ("yes", "sometimes")]
                unfixable = [item for item in iter_violations if not (item[0].is_fixable and item[1].is_fixable in ("yes", "sometimes"))]
                
                unfixable_violations = unfixable
                
                if fixable:
                    old_content = current_content
                    rules_to_fix = {item[1] for item in fixable}
                    for rule in rules_to_fix:
                        rule_config = resolve_rule_config(config, rule.rule_id, lang, detected_base_indent)
                        try:
                            current_content = rule.fix(current_content, file_path, rule_config)
                        except Exception as e:
                            pass
                    if current_content != old_content:
                        has_changes = True
                else:
                    break
            
            print(current_content, end="")
            for v, rule in unfixable_violations:
                print(format_violation(v, file_path, config.verbose, rule.description), file=sys.stderr)
            return 1 if unfixable_violations else 0
            
        elif config.dry_run:
            if fixable:
                current_content = content
                rules_to_fix = {item[1] for item in fixable}
                for rule in rules_to_fix:
                    rule_config = resolve_rule_config(config, rule.rule_id, lang, detected_base_indent)
                    try:
                        current_content = rule.fix(current_content, file_path, rule_config)
                    except Exception as e:
                        pass
                if current_content != content:
                    diff = difflib.unified_diff(
                        content.splitlines(keepends=True),
                        current_content.splitlines(keepends=True),
                        fromfile=f"a/{file_path}",
                        tofile=f"b/{file_path}"
                    )
                    sys.stdout.writelines(diff)
                    
            for v, rule in file_violations:
                print(format_violation(v, file_path, config.verbose, rule.description), file=sys.stderr)
            return 1
            
        else:
            for v, rule in file_violations:
                print(format_violation(v, file_path, config.verbose, rule.description))
            return 1

    files = find_files(config.paths, config.include_dirs)
    if not files:
        if config.verbose:
            print("No files found to lint.")
        return 0
        
    # Cache loaded rules per language to avoid reloading
    rules_by_lang: Dict[str, List[BaseRule]] = {}
    
    total_violations_reported = 0
    
    for file_path in files:
        lang = get_file_language(file_path)
        if lang not in rules_by_lang:
            rules_by_lang[lang] = load_rules_for_language(lang, config.include_dirs, config.rule_mode)
            
        # Get active rules for this file (not disabled globally or for this specific language)
        active_rules = [
            rule for rule in rules_by_lang[lang]
            if rule.rule_id not in config.rules_to_disable and f"{lang}:{rule.rule_id}" not in config.rules_to_disable
        ]
        
        if not active_rules:
            continue
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file '{file_path}': {e}")
            continue
            
        # Parse comments to get disabled rules map
        disabled_map = get_disabled_rules_map(content, file_path)
        detected_base_indent = detect_base_indent(content)
        
        # Get rule config mapping
        file_violations: List[Tuple[Violation, BaseRule]] = []
        
        for rule in active_rules:
            # Resolve configuration (language override > global rule config)
            global_config = config.rule_configs.get(rule.rule_id, {})
            lang_config = config.rule_configs.get(f"{lang}:{rule.rule_id}", {})
            
            # If globally or language-specifically disabled via boolean (e.g. IR-rule: false)
            if global_config is False or lang_config is False:
                continue
                
            rule_config = resolve_rule_config(config, rule.rule_id, lang, detected_base_indent)
                 
            # Check for explicit enabled parameter, falling back to rule default
            if config.disable_all:
                is_enabled = (
                    (rule_config.get("enabled") is True) or
                    (rule.rule_id in config.rules_to_enable) or
                    (f"{lang}:{rule.rule_id}" in config.rules_to_enable)
                )
            else:
                is_enabled = rule_config.get("enabled", rule.enabled_by_default)
                
            if not is_enabled:
                continue
            # Run check
            try:
                violations = rule.check(content, file_path, rule_config)
            except Exception as e:
                print(f"Error running rule {rule.rule_id} on {file_path}: {e}")
                continue
                
            # Filter violations based on in-file disable comments
            rule_disabled_lines = disabled_map.get(rule.rule_id, set())
            for v in violations:
                if v.line_number not in rule_disabled_lines:
                    file_violations.append((v, rule))
                    
        if not file_violations:
            continue
            
        # Now handle the results based on dry-run, fix, or check mode
        fixable = [item for item in file_violations if item[0].is_fixable and item[1].is_fixable in ("yes", "sometimes")]
        unfixable = [item for item in file_violations if not (item[0].is_fixable and item[1].is_fixable in ("yes", "sometimes"))]
        
        if config.fix:
            # Fix mode:
            # 1. Apply fixes for fixable rules with convergence looping
            current_content = content
            has_changes = True
            pass_num = 0
            max_passes = 5
            unfixable_violations = unfixable
            
            while has_changes and pass_num < max_passes:
                pass_num += 1
                has_changes = False
                
                disabled_map = get_disabled_rules_map(current_content, file_path)
                detected_base_indent = detect_base_indent(current_content)
                
                iter_violations = []
                for rule in active_rules:
                    global_config = config.rule_configs.get(rule.rule_id, {})
                    lang_config = config.rule_configs.get(f"{lang}:{rule.rule_id}", {})
                    if global_config is False or lang_config is False:
                        continue
                        
                    rule_config = resolve_rule_config(config, rule.rule_id, lang, detected_base_indent)
                    if config.disable_all:
                        is_enabled = (
                            (rule_config.get("enabled") is True) or
                            (rule.rule_id in config.rules_to_enable) or
                            (f"{lang}:{rule.rule_id}" in config.rules_to_enable)
                        )
                    else:
                        is_enabled = rule_config.get("enabled", rule.enabled_by_default)
                    if not is_enabled:
                        continue
                        
                    try:
                        violations = rule.check(current_content, file_path, rule_config)
                    except Exception as e:
                        continue
                        
                    rule_disabled_lines = disabled_map.get(rule.rule_id, set())
                    for v in violations:
                        if v.line_number not in rule_disabled_lines:
                            iter_violations.append((v, rule))
                            
                if not iter_violations:
                    break
                    
                fixable = [item for item in iter_violations if item[0].is_fixable and item[1].is_fixable in ("yes", "sometimes")]
                unfixable = [item for item in iter_violations if not (item[0].is_fixable and item[1].is_fixable in ("yes", "sometimes"))]
                
                unfixable_violations = unfixable
                
                if fixable:
                    old_content = current_content
                    rules_to_fix = {item[1] for item in fixable}
                    for rule in rules_to_fix:
                        rule_config = resolve_rule_config(config, rule.rule_id, lang, detected_base_indent)
                        try:
                            current_content = rule.fix(current_content, file_path, rule_config)
                        except Exception as e:
                            pass
                    if current_content != old_content:
                        has_changes = True
                else:
                    break
            
            # Write back if changed
            if current_content != content:
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(current_content)
                    if config.verbose:
                        print(f"Fixed issues in {file_path}")
                except Exception as e:
                    print(f"Error writing fixed content to '{file_path}': {e}")
            
            # 2. Report unfixable errors
            for v, rule in unfixable_violations:
                print(format_violation(v, file_path, config.verbose, rule.description))
                total_violations_reported += 1
                
        elif config.dry_run:
            # Dry-run mode:
            # 1. Show fixes that would be applied (via diff)
            if fixable:
                current_content = content
                rules_to_fix = {item[1] for item in fixable}
                for rule in rules_to_fix:
                    rule_config = resolve_rule_config(config, rule.rule_id, lang, detected_base_indent)
                    try:
                        current_content = rule.fix(current_content, file_path, rule_config)
                    except Exception as e:
                        pass
                
                if current_content != content:
                    print(f"--- {file_path} (original)")
                    print(f"+++ {file_path} (dry-run fix)")
                    diff = list(difflib.unified_diff(
                        content.splitlines(keepends=True),
                        current_content.splitlines(keepends=True),
                        fromfile=file_path,
                        tofile=file_path + ".fixed",
                        n=2
                    ))
                    # Print diff lines (excluding the header which we customized)
                    for line in diff[2:]:
                        print(line, end="")
                    if not diff[-1].endswith("\n"):
                        print()
                    total_violations_reported += len(fixable)
            
            # 2. Report unfixable errors
            for v, rule in unfixable:
                print(format_violation(v, file_path, config.verbose, rule.description))
                total_violations_reported += 1
                
        else:
            # Check mode (default): report everything
            for v, rule in file_violations:
                print(format_violation(v, file_path, config.verbose, rule.description))
                total_violations_reported += 1
                
    return 1 if total_violations_reported > 0 else 0
