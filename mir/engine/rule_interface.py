from typing import List, Dict, Any, Optional

class Violation:
    def __init__(
        self,
        rule_id: str,
        line_number: int,
        message: str,
        offending_lines: List[str],
        is_fixable: bool = False
    ):
        self.rule_id = rule_id
        self.line_number = line_number
        self.message = message
        self.offending_lines = offending_lines
        self.is_fixable = is_fixable

    def __repr__(self) -> str:
        return f"Violation({self.rule_id}, line={self.line_number}, fixable={self.is_fixable})"

class BaseRule:
    """
    Base class for all Mitchell's Ineffable Rules.
    Each rule must subclass this and implement `check`.
    Optionally, a rule can override `fix` if `is_fixable` is True.
    """
    rule_id: str = "IR-base"
    description: str = "Base rule template"
    category: str = "general"
    is_fixable: str = "no"  # Must be "yes", "no", or "sometimes"
    enabled_by_default: bool = True
    default_config: Dict[str, Any] = {}
    config_options: Dict[str, Dict[str, Any]] = {}
    examples: List[Dict[str, str]] = []
    additional_validations: List[str] = []

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        """
        Check the content of a file for violations.
        Returns a list of Violation objects.
        """
        raise NotImplementedError("Each rule must implement the check method.")

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        """
        Fix the violations in the file content.
        Returns the modified content as a string.
        Only called if is_fixable is in ("yes", "sometimes").
        """
        if self.is_fixable == "no":
            return content
        raise NotImplementedError("Fixable rules must implement the fix method.")

    def get_config_value(
        self,
        rule_config: Dict[str, Any],
        param_name: str,
        default_value: Any,
        fallbacks: Optional[List[tuple]] = None
    ) -> Any:
        """
        Resolves a config value with support for fallback references to other rules.
        fallbacks: a list of tuples (other_rule_class, other_param_name)
        """
        # 1. Check current rule config
        if param_name in rule_config:
            return rule_config[param_name]
            
        # 2. Check fallback other rules
        if fallbacks:
            all_configs = rule_config.get("_all_configs", {})
            lang = rule_config.get("_lang")
            
            for other_rule_cls, other_param in fallbacks:
                other_id = other_rule_cls.rule_id
                
                # Check lang-specific other config, e.g. "sql:IR-line-length"
                if lang:
                    lang_key = f"{lang}:{other_id}"
                    if lang_key in all_configs and isinstance(all_configs[lang_key], dict):
                        if other_param in all_configs[lang_key]:
                            return all_configs[lang_key][other_param]
                            
                # Check global other config, e.g. "IR-line-length"
                if other_id in all_configs and isinstance(all_configs[other_id], dict):
                    if other_param in all_configs[other_id]:
                        return all_configs[other_id][other_param]
                        
                # Check other rule class defaults
                if hasattr(other_rule_cls, "default_config") and other_param in other_rule_cls.default_config:
                    return other_rule_cls.default_config[other_param]
                    
        # 3. Fall back to current rule defaults
        if hasattr(self, "default_config") and param_name in self.default_config:
            return self.default_config[param_name]
            
        return default_value
