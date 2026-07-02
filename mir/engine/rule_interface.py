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
    examples: List[Dict[str, str]] = []

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
