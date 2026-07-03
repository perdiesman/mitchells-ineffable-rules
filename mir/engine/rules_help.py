import os
import sys
import re
import argparse
import importlib
from typing import List, Dict, Optional

def slugify(text: str) -> str:
    """
    Convert text to a GitHub markdown compatible anchor slug.
    """
    text = text.lower()
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")
from mir.engine.rules_loader import load_rules_for_language

def get_supported_languages(include_dirs: Optional[List[str]] = None) -> List[str]:
    """
    Discovers all supported languages by scanning built-in rules directory
    and any configured external include directories.
    """
    languages = set()
    
    # 1. Built-in rules directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    builtin_rules_dir = os.path.abspath(os.path.join(current_dir, "..", "rules"))
    if os.path.exists(builtin_rules_dir) and os.path.isdir(builtin_rules_dir):
        for entry in os.listdir(builtin_rules_dir):
            if os.path.isdir(os.path.join(builtin_rules_dir, entry)) and not entry.startswith("_"):
                languages.add(entry.lower())
                
    # 2. External include directories
    if include_dirs:
        for path in include_dirs:
            if os.path.exists(path) and os.path.isdir(path):
                for entry in os.listdir(path):
                    if os.path.isdir(os.path.join(path, entry)) and not entry.startswith("_"):
                        languages.add(entry.lower())
                        
    return sorted(list(languages))

def get_categories_for_language(lang: str, include_dirs: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Dynamically loads the CATEGORIES dictionary. Checks external packages first, falling back to builtins.
    """
    # Check external folders first
    if include_dirs:
        for path in include_dirs:
            lang_dir = os.path.join(path, lang.lower())
            init_file = os.path.join(lang_dir, "__init__.py")
            if os.path.exists(init_file):
                try:
                    spec = importlib.util.spec_from_file_location(f"ext_categories_{lang}", init_file)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        cats = getattr(module, "CATEGORIES", None)
                        if cats:
                            return cats
                except Exception:
                    pass
                    
    # Check builtins
    try:
        module_name = f"mir.rules.{lang.lower()}"
        module = importlib.import_module(module_name)
        return getattr(module, "CATEGORIES", {})
    except Exception:
        return {}

def get_category_title(cat: str, lang: str, include_dirs: Optional[List[str]] = None) -> str:
    """
    Resolves the category display title for a specific language.
    """
    lang_cats = get_categories_for_language(lang, include_dirs)
    title = lang_cats.get(cat) or lang_cats.get(cat.lower())
    if title:
        return title
    return f"{cat.replace('/', ' / ').title()} Rules"

def generate_docs_to_path(
    target_path: str,
    include_dirs: Optional[List[str]] = None,
    rule_mode: str = "extend"
) -> None:
    """
    Generates markdown style guide documentation files inside the specified target_path directory
    by compiling rule metadata from rule source classes.
    """
    os.makedirs(target_path, exist_ok=True)
    supported_languages = get_supported_languages(include_dirs)
    
    # 1. Build root README.md
    root_md = []
    root_md.append("# Mitchell's Ineffable Rules - Documentation\n")
    root_md.append("Welcome to the style guide and rules catalog for the Mitchell's Ineffable Rules (MIR) Linter.\n")
    root_md.append("## Languages\n")
    
    for lang in supported_languages:
        root_md.append(f"### [{lang.upper()}]({lang}/README.md)")
        
        # Resolve all categories for this language
        lang_cats = get_categories_for_language(lang, include_dirs)
        rules = load_rules_for_language(lang, include_dirs, rule_mode)
        grouped_rules = {}
        for rule in rules:
            grouped_rules.setdefault(rule.category.lower(), []).append(rule)
            
        all_categories = list(lang_cats.keys())
        for cat in grouped_rules:
            if cat not in all_categories:
                all_categories.append(cat)
                
        root_md.append("Categories:")
        for cat in all_categories:
            cat_title = get_category_title(cat, lang, include_dirs)
            slug = slugify(cat_title)
            root_md.append(f"- [{cat_title}]({lang}/README.md#{slug})")
        root_md.append("")
        
    root_md.append("## Additional Guides")
    root_md.append("- [Custom Rules Guide](custom_rules.md)")
    root_md.append("- [PyPI Publishing Guide](publishing.md)\n")
    
    root_path = os.path.join(target_path, "README.md")
    with open(root_path, "w", encoding="utf-8") as f:
        f.write("\n".join(root_md))
    print(f"Generated root README -> {root_path}")
    
    # 2. Build directories and rules for each language
    for lang in supported_languages:
        rules = load_rules_for_language(lang, include_dirs, rule_mode)
        
        # Group rules by category
        grouped_rules = {}
        for rule in rules:
            grouped_rules.setdefault(rule.category.lower(), []).append(rule)
            
        lang_dir = os.path.join(target_path, lang)
        os.makedirs(lang_dir, exist_ok=True)
        
        rules_dir = os.path.join(lang_dir, "rules")
        os.makedirs(rules_dir, exist_ok=True)
        
        # Load standard categories defined in package init
        lang_cats = get_categories_for_language(lang, include_dirs)
        has_categories = len(lang_cats) > 0
        
        # Clean up legacy flat md files if they exist in rules_dir
        if has_categories and os.path.exists(rules_dir):
            for file_name in os.listdir(rules_dir):
                if file_name.endswith(".md") and os.path.isfile(os.path.join(rules_dir, file_name)):
                    try:
                        os.remove(os.path.join(rules_dir, file_name))
                    except Exception:
                        pass
        
        lang_md = []
        lang_md.append(f"# {lang.upper()} Style Guide & Rules\n")
        lang_md.append(f"This document describes all {lang.upper()} linting rules supported by Mitchell's Ineffable Rules (IR) Linter.\n")
        
        # Load standard categories defined in package init
        lang_cats = get_categories_for_language(lang, include_dirs)
        all_categories = list(lang_cats.keys())
        
        # Add any other categories that were defined in rules but not in list
        for cat in grouped_rules:
            if cat not in all_categories:
                all_categories.append(cat)
                
        # Build category anchors Table of Contents
        lang_md.append("## Categories\n")
        for cat in all_categories:
            cat_title = get_category_title(cat, lang, include_dirs)
            slug = slugify(cat_title)
            lang_md.append(f"- [{cat_title}](#{slug})")
        lang_md.append("")
        
        for cat in all_categories:
            cat_rules = grouped_rules.get(cat, [])
            cat_title = get_category_title(cat, lang, include_dirs)
            
            lang_md.append(f"## {cat_title}\n")
            
            if not cat_rules:
                lang_md.append("| Rule Name | Short Description | Fixable | Details |")
                lang_md.append("| :--- | :--- | :---: | :---: |")
                lang_md.append(f"| *No rules active* | *Future {cat} rules will be listed here* | - | - |\n")
                continue
                
            # Print table
            lang_md.append("| Rule Name | Short Description | Fixable | Details |")
            lang_md.append("| :--- | :--- | :---: | :---: |")
            for r in cat_rules:
                fixable_str = r.is_fixable.capitalize()
                if has_categories:
                    link_path = f"rules/{r.category.lower()}/{r.rule_id}.md"
                else:
                    link_path = f"rules/{r.rule_id}.md"
                lang_md.append(f"| [`{r.rule_id}`]({link_path}) | {r.description} | {fixable_str} | [View Details]({link_path}) |")
            lang_md.append("")
            
            # Helper to find category of another rule
            def find_rule_category(rule_id: str) -> str:
                for rule_obj in rules:
                    if rule_obj.rule_id == rule_id:
                        return rule_obj.category.lower()
                return None

            # Write individual rule files
            for r in cat_rules:
                rule_md = []
                rule_md.append(f"# {r.rule_id}\n")
                rule_md.append(f"{r.description}\n")
                
                fixable_str = r.is_fixable.capitalize()
                enabled_str = "Yes" if r.enabled_by_default else "No"
                rule_md.append(f"- **Auto-Fixable**: {fixable_str}")
                rule_md.append(f"- **Enabled by Default**: {enabled_str}")
                rule_md.append(f"- **Category**: {get_category_title(r.category, lang, include_dirs)}")
                
                # Configuration parameters
                rule_md.append("- **Configuration Options**:")
                if getattr(r, "config_options", None):
                    enabled_val = "true" if r.enabled_by_default else "false"
                    rule_md.append(f"  - `enabled` (Default: `{enabled_val}`): Enable or disable this rule.")
                    for opt_k, opt_v in r.config_options.items():
                        desc = opt_v.get("description", "")
                        default_val = opt_v.get("default")
                        default_str = str(default_val).lower() if isinstance(default_val, bool) else str(default_val)
                        fallback = opt_v.get("fallback")
                        
                        opt_line = f"  - `{opt_k}` (Default: `{default_str}`): {desc}"
                        if fallback:
                            parts = fallback.split(":")
                            if len(parts) == 2:
                                if has_categories:
                                    other_cat = find_rule_category(parts[0])
                                    link_to_rule = f"../{other_cat}/{parts[0]}.md" if other_cat else f"{parts[0]}.md"
                                else:
                                    link_to_rule = f"{parts[0]}.md"
                                opt_line += f" *Note: Value dynamically inherited from rule [`{parts[0]}`]({link_to_rule}) -> `{parts[1]}` if not configured.*"
                            else:
                                opt_line += f" *Note: Value dynamically inherited from `{fallback}` if not configured.*"
                        rule_md.append(opt_line)
                else:
                    default_opts = {"enabled": r.enabled_by_default}
                    default_opts.update(r.default_config)
                    for opt_k, opt_v in default_opts.items():
                        val_str = str(opt_v).lower() if isinstance(opt_v, bool) else str(opt_v)
                        rule_md.append(f"  - `{opt_k}`: `{val_str}`")
                rule_md.append("")
                
                # Check for module-level globals (lists/sets/dicts)
                try:
                    module = importlib.import_module(r.__class__.__module__)
                    globals_to_doc = []
                    for attr_name in dir(module):
                        if attr_name.isupper() and not attr_name.startswith("_"):
                            val = getattr(module, attr_name)
                            if isinstance(val, (list, set, dict)):
                                globals_to_doc.append((attr_name, val))
                                
                    if globals_to_doc:
                        for g_name, g_val in sorted(globals_to_doc):
                            rule_md.append(f"#### Default `{g_name}`")
                            if isinstance(g_val, (list, set)):
                                sorted_items = sorted(list(g_val))
                                items_str = ", ".join([f"`{x}`" for x in sorted_items])
                                rule_md.append(items_str)
                            elif isinstance(g_val, dict):
                                for k, v in sorted(g_val.items()):
                                    rule_md.append(f"- `{k}`: `{v}`")
                            rule_md.append("")
                except Exception:
                    pass

                if r.examples:
                    for idx, ex in enumerate(r.examples, start=1):
                        suffix = f" #{idx}" if len(r.examples) > 1 else ""
                        
                        if "violating" in ex and ex["violating"]:
                            rule_md.append(f"#### ❌ Violating Example{suffix}")
                            rule_md.append(f"```{lang}")
                            rule_md.append(ex["violating"])
                            rule_md.append("```\n")
                            
                        if "correct" in ex and ex["correct"]:
                            rule_md.append(f"####  Correct Example{suffix}")
                            rule_md.append(f"```{lang}")
                            rule_md.append(ex["correct"])
                            rule_md.append("```\n")
                            
                additional_vals = getattr(r, "additional_validations", [])
                if additional_vals:
                    rule_md.append("#### Additional Validations")
                    for val in additional_vals:
                        rule_md.append(f"```{lang}")
                        rule_md.append(val)
                        rule_md.append("```\n")
                            
                if has_categories:
                    dest_dir = os.path.join(rules_dir, r.category.lower())
                    os.makedirs(dest_dir, exist_ok=True)
                    rule_file_path = os.path.join(dest_dir, f"{r.rule_id}.md")
                else:
                    rule_file_path = os.path.join(rules_dir, f"{r.rule_id}.md")
                with open(rule_file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(rule_md))
            
        lang_readme_path = os.path.join(lang_dir, "README.md")
        with open(lang_readme_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lang_md))
        print(f"Generated language docs for {lang} -> {lang_dir}")
        
        # Clean up legacy monolithic file if exists
        legacy_file = os.path.join(target_path, f"{lang}.md")
        if os.path.exists(legacy_file):
            try:
                os.remove(legacy_file)
                print(f"Removed legacy monolithic file: {legacy_file}")
            except Exception as e:
                print(f"Warning: could not remove legacy file '{legacy_file}': {e}")

def handle_rule_help(
    help_arg: str,
    parser: argparse.ArgumentParser,
    include_dirs: Optional[List[str]] = None,
    rule_mode: str = "extend"
) -> None:
    """
    Handles custom rule help arguments, resolving dynamic languages and rules.
    """
    supported_languages = get_supported_languages(include_dirs)
    
    if help_arg == "standard":
        parser.print_help()
        sys.exit(0)
        
    if help_arg == "docs":
        generate_docs_to_path("docs", include_dirs, rule_mode)
        sys.exit(0)
        
    if help_arg.startswith("docs:"):
        target_path = help_arg.split(":", 1)[1]
        if not target_path:
            print("Error: Specify a target directory name (e.g., '--help docs:custom_docs').")
            sys.exit(1)
        generate_docs_to_path(target_path, include_dirs, rule_mode)
        sys.exit(0)
        
    if help_arg == "rules":
        # List all rules
        all_rules = []
        for lang in supported_languages:
            rules = load_rules_for_language(lang, include_dirs, rule_mode)
            for rule in rules:
                all_rules.append((lang, rule))
                
        if not all_rules:
            print("No rules configured.")
            sys.exit(0)
            
        print_rules_table(all_rules)
        sys.exit(0)
        
    if help_arg.startswith("rules:"):
        lang = help_arg.split(":", 1)[1].lower()
        if lang not in supported_languages:
            print(f"Error: Unsupported language '{lang}'. Supported languages are: {', '.join(supported_languages)}")
            sys.exit(1)
            
        rules = load_rules_for_language(lang, include_dirs, rule_mode)
        if not rules:
            print(f"No rules configured for language '{lang}'.")
            sys.exit(0)
            
        print_rules_table([(lang, r) for r in rules])
        sys.exit(0)
        
    # Check if format is <lang>:<rule_id>
    if ":" in help_arg:
        parts = help_arg.split(":", 1)
        lang = parts[0].lower()
        rule_id = parts[1]
        
        if lang in supported_languages:
            rules = load_rules_for_language(lang, include_dirs, rule_mode)
            matching_rule = next((r for r in rules if r.rule_id == rule_id), None)
            if matching_rule:
                print_rule_details(lang, matching_rule, include_dirs)
                sys.exit(0)
            else:
                print(f"Error: Rule '{rule_id}' not found for language '{lang}'.")
                sys.exit(1)
                
    # Otherwise, search for <rule_id> across all languages
    rule_id = help_arg
    matches = []
    for lang in supported_languages:
        rules = load_rules_for_language(lang, include_dirs, rule_mode)
        for r in rules:
            if r.rule_id == rule_id:
                matches.append((lang, r))
                
    if matches:
        for idx, (lang, r) in enumerate(matches):
            if idx > 0:
                print("-" * 50)
                print()
            print_rule_details(lang, r, include_dirs)
        sys.exit(0)
        
    print(f"Error: Rule or command '{help_arg}' not recognized.")
    print(f"Run with '--help' to see standard options, or '--help rules' to list all rules.")
    sys.exit(1)

def print_rules_table(rules_data: List[tuple]) -> None:
    # Header
    print(f"{'Language':<10} {'Category':<12} {'Rule ID':<20} {'Fixable':<10} {'Short Description'}")
    print("-" * 92)
    for lang, rule in rules_data:
        fixable_str = rule.is_fixable.capitalize()
        print(f"{lang:<10} {rule.category:<12} {rule.rule_id:<20} {fixable_str:<10} {rule.description}")

def print_rule_details(lang: str, rule, include_dirs: Optional[List[str]] = None) -> None:
    fixable_str = rule.is_fixable.capitalize()
    enabled_str = "Yes" if rule.enabled_by_default else "No"
    print(f"Rule Details: {rule.rule_id} ({lang})")
    print("=" * (len(rule.rule_id) + len(lang) + 17))
    print(f"Language:     {lang}")
    print(f"Category:     {get_category_title(rule.category, lang, include_dirs)}")
    print(f"Fixable:      {fixable_str}")
    print(f"Enabled:      {enabled_str} (by default)")
    print(f"Description:  {rule.description}")
    
    # Print configuration parameters
    print("Configuration Options:")
    if getattr(rule, "config_options", None):
        enabled_val = "true" if rule.enabled_by_default else "false"
        print(f"  enabled (Default: {enabled_val}): Enable or disable this rule.")
        for opt_k, opt_v in rule.config_options.items():
            desc = opt_v.get("description", "")
            default_val = opt_v.get("default")
            fallback = opt_v.get("fallback")
            
            opt_line = f"  {opt_k} (Default: {default_val}): {desc}"
            if fallback:
                parts = fallback.split(":")
                if len(parts) == 2:
                    opt_line += f" (Value dynamically inherited from rule {parts[0]} -> {parts[1]} if not configured)"
                else:
                    opt_line += f" (Value dynamically inherited from {fallback} if not configured)"
            print(opt_line)
    else:
        default_opts = {"enabled": rule.enabled_by_default}
        default_opts.update(rule.default_config)
        for opt_k, opt_v in default_opts.items():
            print(f"  {opt_k}: {opt_v}")
    print()
    
    # Check for module-level globals (lists/sets/dicts)
    try:
        import importlib
        module = importlib.import_module(rule.__class__.__module__)
        globals_to_doc = []
        for attr_name in dir(module):
            if attr_name.isupper() and not attr_name.startswith("_"):
                val = getattr(module, attr_name)
                if isinstance(val, (list, set, dict)):
                    globals_to_doc.append((attr_name, val))
                    
        if globals_to_doc:
            print("Default Values:")
            for g_name, g_val in sorted(globals_to_doc):
                if isinstance(g_val, (list, set)):
                    sorted_items = sorted(list(g_val))
                    items_str = ", ".join([str(x) for x in sorted_items])
                    print(f"  {g_name}: {items_str}")
                elif isinstance(g_val, dict):
                    print(f"  {g_name}:")
                    for k, v in sorted(g_val.items()):
                        print(f"    {k}: {v}")
            print()
    except Exception:
        pass

    if rule.examples:
        for idx, ex in enumerate(rule.examples, start=1):
            suffix = f" #{idx}" if len(rule.examples) > 1 else ""
            if "violating" in ex and ex["violating"]:
                print(f"Violating Example{suffix}:")
                print("-" * (18 + len(suffix)))
                print(ex["violating"])
                print()
            if "correct" in ex and ex["correct"]:
                print(f"Correct Example{suffix}:")
                print("-" * (16 + len(suffix)))
                print(ex["correct"])
                print()
                
    additional_vals = getattr(rule, "additional_validations", [])
    if additional_vals:
        print("Additional Validations:")
        print("----------------------")
        for val in additional_vals:
            print(val)
        print()
