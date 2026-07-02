import os
import sys
import argparse
import importlib
from typing import List, Dict, Optional
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
    
    for lang in supported_languages:
        rules = load_rules_for_language(lang, include_dirs, rule_mode)
        
        # Group rules by category
        grouped_rules = {}
        for rule in rules:
            grouped_rules.setdefault(rule.category.lower(), []).append(rule)
            
        md_content = []
        md_content.append(f"# {lang.upper()} Style Guide & Rules\n")
        md_content.append(f"This document describes all {lang.upper()} linting rules supported by Mitchell's Ineffable Rules (IR) Linter.\n")
        
        # Load standard categories defined in package init
        lang_cats = get_categories_for_language(lang, include_dirs)
        all_categories = list(lang_cats.keys())
        
        # Add any other categories that were defined in rules but not in list
        for cat in grouped_rules:
            if cat not in all_categories:
                all_categories.append(cat)
            
        for cat in all_categories:
            cat_rules = grouped_rules.get(cat, [])
            cat_title = get_category_title(cat, lang, include_dirs)
            
            md_content.append(f"## {cat_title}\n")
            
            if not cat_rules:
                md_content.append("| Rule Name | Short Description | Fixable | Details |")
                md_content.append("| :--- | :--- | :---: | :---: |")
                md_content.append(f"| *No rules active* | *Future {cat} rules will be listed here* | - | - |\n")
                continue
                
            # Print table
            md_content.append("| Rule Name | Short Description | Fixable | Details |")
            md_content.append("| :--- | :--- | :---: | :---: |")
            for r in cat_rules:
                fixable_str = r.is_fixable.capitalize()
                md_content.append(f"| [`{r.rule_id}`](#{r.rule_id.lower()}) | {r.description} | {fixable_str} | [View Details](#{r.rule_id.lower()}) |")
            md_content.append("")
            
            # Print rule details
            for r in cat_rules:
                md_content.append(f"### {r.rule_id}\n")
                md_content.append(f"{r.description}\n")
                fixable_str = r.is_fixable.capitalize()
                enabled_str = "Yes" if r.enabled_by_default else "No"
                md_content.append(f"- **Auto-Fixable**: {fixable_str}")
                md_content.append(f"- **Enabled by Default**: {enabled_str}")
                md_content.append(f"- **Category**: {get_category_title(r.category, lang, include_dirs)}")
                
                # Default Configuration parameters
                default_opts = {"enabled": r.enabled_by_default}
                default_opts.update(r.default_config)
                md_content.append("- **Default Configuration**:")
                for opt_k, opt_v in default_opts.items():
                    val_str = str(opt_v).lower() if isinstance(opt_v, bool) else str(opt_v)
                    md_content.append(f"  - `{opt_k}`: `{val_str}`")
                md_content.append("")
                
                if r.examples_violating:
                    md_content.append("#### ❌ Violating Example")
                    md_content.append(f"```{lang}")
                    for ex in r.examples_violating:
                        md_content.append(ex)
                    md_content.append("```\n")
                    
                if r.examples_correct:
                    md_content.append("####  Correct Example")
                    md_content.append(f"```{lang}")
                    for ex in r.examples_correct:
                        md_content.append(ex)
                    md_content.append("```\n")
                    
                md_content.append("---")
            md_content.append("")
            
        # Write to file
        file_path = os.path.join(target_path, f"{lang}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))
            
        print(f"Generated docs for {lang} -> {file_path}")

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
    
    # Print default configuration parameters
    print("Default Config:")
    default_opts = {"enabled": rule.enabled_by_default}
    default_opts.update(rule.default_config)
    for opt_k, opt_v in default_opts.items():
        print(f"  {opt_k}: {opt_v}")
    print()
    
    if rule.examples_violating:
        print("Violating Example:")
        print("------------------")
        for ex in rule.examples_violating:
            print(ex)
        print()
        
    if rule.examples_correct:
        print("Correct Example:")
        print("----------------")
        for ex in rule.examples_correct:
            print(ex)
        print()
