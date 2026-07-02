import os
import glob
import importlib.util
import inspect
from typing import List, Optional, Type
from mir.engine.rule_interface import BaseRule

class RuleValidationError(Exception):
    """
    Exception raised when a custom rule definition fails validation.
    """
    pass

def validate_rule_class(rule_class: Type[BaseRule]) -> None:
    """
    Validates that a rule class is correctly implemented.
    Raises RuleValidationError if validation fails.
    """
    rule_id = getattr(rule_class, "rule_id", None)
    if not isinstance(rule_id, str) or not rule_id or rule_id == "IR-base":
        raise RuleValidationError(
            f"Rule {rule_class.__name__} must define a non-empty string 'rule_id' (cannot be 'IR-base')."
        )
        
    description = getattr(rule_class, "description", None)
    if not isinstance(description, str) or not description or description == "Base rule template":
        raise RuleValidationError(
            f"Rule '{rule_id}' (class {rule_class.__name__}) must define a non-empty string 'description' (cannot be 'Base rule template')."
        )
        
    category = getattr(rule_class, "category", None)
    if not isinstance(category, str) or not category:
        raise RuleValidationError(
            f"Rule '{rule_id}' (class {rule_class.__name__}) must define a non-empty string 'category'."
        )
        
    is_fixable = getattr(rule_class, "is_fixable", None)
    if is_fixable not in ("yes", "no", "sometimes"):
        raise RuleValidationError(
            f"Rule '{rule_id}' (class {rule_class.__name__}) 'is_fixable' must be 'yes', 'no', or 'sometimes'."
        )
        
    # Check if 'check' is implemented (must not be the base check)
    if not hasattr(rule_class, "check") or rule_class.check == BaseRule.check:
        raise RuleValidationError(
            f"Rule '{rule_id}' (class {rule_class.__name__}) must implement the 'check' method."
        )
        
    # Optional fields format check
    default_config = getattr(rule_class, "default_config", None)
    if default_config is not None and not isinstance(default_config, dict):
        raise RuleValidationError(
            f"Rule '{rule_id}' (class {rule_class.__name__}) 'default_config' must be a dictionary."
        )
        
    examples = getattr(rule_class, "examples", None)
    if examples is not None:
        if not isinstance(examples, list):
            raise RuleValidationError(
                f"Rule '{rule_id}' (class {rule_class.__name__}) 'examples' must be a list of dictionaries."
            )
        for idx, ex in enumerate(examples):
            if not isinstance(ex, dict):
                raise RuleValidationError(
                    f"Rule '{rule_id}' (class {rule_class.__name__}) example #{idx + 1} must be a dictionary."
                )
            if "violating" not in ex or not isinstance(ex["violating"], str):
                raise RuleValidationError(
                    f"Rule '{rule_id}' (class {rule_class.__name__}) example #{idx + 1} must have a 'violating' string key."
                )
            # If the rule is fixable=yes, then 'correct' key is required
            is_fixable = getattr(rule_class, "is_fixable", "no")
            if is_fixable == "yes":
                if "correct" not in ex or not isinstance(ex["correct"], str) or not ex["correct"].strip():
                    raise RuleValidationError(
                        f"Rule '{rule_id}' (class {rule_class.__name__}) example #{idx + 1} must have a non-empty 'correct' string key since is_fixable is 'yes'."
                    )
                    
    additional_validations = getattr(rule_class, "additional_validations", None)
    if additional_validations is not None:
        if not isinstance(additional_validations, list):
            raise RuleValidationError(
                f"Rule '{rule_id}' (class {rule_class.__name__}) 'additional_validations' must be a list."
            )
        for idx, val in enumerate(additional_validations):
            if not isinstance(val, str):
                raise RuleValidationError(
                    f"Rule '{rule_id}' (class {rule_class.__name__}) additional_validation #{idx + 1} must be a string."
                )

def load_rules_from_dir(directory: str, language: str, is_external: bool = False) -> List[BaseRule]:
    """
    Helper to load all rules from a single directory.
    Validates imported rules and raises RuleValidationError for external files if they are invalid.
    """
    rules: List[BaseRule] = []
    if not os.path.exists(directory):
        return rules
        
    search_path = os.path.join(directory, "*.py")
    rule_files = glob.glob(search_path)
    
    for file_path in rule_files:
        filename = os.path.basename(file_path)
        if filename.startswith("_"):
            continue
            
        module_name = f"rules.{language.lower()}.{filename[:-3]}"
        
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Scan module for classes that subclass BaseRule
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseRule) and obj is not BaseRule:
                        # Enforce validation
                        if is_external:
                            validate_rule_class(obj)
                        rules.append(obj())
        except Exception as e:
            if is_external or isinstance(e, RuleValidationError):
                raise RuleValidationError(f"Failed loading custom rule '{file_path}': {e}")
            else:
                print(f"Error loading rule file '{file_path}': {e}")
            
    return rules

def load_rules_for_language(
    language: str,
    include_dirs: Optional[List[str]] = None,
    rule_mode: str = "extend"
) -> List[BaseRule]:
    """
    Loads all rules for a given language.
      - rule_mode='extend': Loads built-in rules AND external rules.
      - rule_mode='replace': Loads only external rules if present.
    """
    rules: List[BaseRule] = []
    has_external_rules = False
    
    # 1. Load external rules first to see if any are present (enforcing validation)
    ext_rules: List[BaseRule] = []
    if include_dirs:
        for path in include_dirs:
            ext_rules_dir = os.path.join(path, language.lower())
            if os.path.exists(ext_rules_dir) and os.path.isdir(ext_rules_dir):
                loaded = load_rules_from_dir(ext_rules_dir, language, is_external=True)
                if loaded:
                    ext_rules.extend(loaded)
                    has_external_rules = True
                    
    # 2. Load built-in rules
    builtin_rules: List[BaseRule] = []
    # If mode is extend, or if replace mode is selected but no external rules exist for this lang
    if rule_mode == "extend" or not has_external_rules:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        builtin_rules_dir = os.path.join(current_dir, "..", "rules", language.lower())
        builtin_rules = load_rules_from_dir(builtin_rules_dir, language, is_external=False)
        
    # Combine (builtin first, then external) so external overrides builtin if they share rule_id
    rules = builtin_rules + ext_rules
    
    # Deduplicate rules by rule_id, keeping the last loaded (which allows external override)
    seen = set()
    deduped_rules = []
    for r in reversed(rules):
        if r.rule_id not in seen:
            seen.add(r.rule_id)
            deduped_rules.append(r)
            
    return list(reversed(deduped_rules))
