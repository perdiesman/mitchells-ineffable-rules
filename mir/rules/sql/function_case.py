import re
from typing import List, Dict, Any, Set
from mir.engine.rule_interface import BaseRule, Violation

EXCLUDED_WORDS = {
    "in", "values", "exists", "join", "using", "on",
    "and", "or", "not", "select", "from", "where",
    "having", "between", "like", "as", "over", "partition",
    "by", "window", "group", "order", "limit", "offset",
    "union", "all", "intersect", "except", "distinct",
    "with", "recursive", "case", "when", "then", "else", "end",
    "table", "row", "any", "some", "array", "if", "while", "return"
}

class FunctionCaseRule(BaseRule):
    rule_id = "IR-function-case"
    description = "Function names should be the same case (default lowercase)."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "case": "lowercase",
        "additional_exclusions": [],
        "override_exclusions": None
    }
    config_options = {
        "case": {
            "type": "str",
            "description": "Target casing style for function names ('lowercase' or 'uppercase').",
            "default": "lowercase"
        },
        "additional_exclusions": {
            "type": "list",
            "description": "Additional keywords to exclude from function casing checks.",
            "default": []
        },
        "override_exclusions": {
            "type": "list",
            "description": "Override the default list of excluded keywords entirely.",
            "default": None
        }
    }
    
    examples = [
        {
            "violating": "SELECT COUNT(id), Sum(price) FROM orders;",
            "correct": "SELECT count(id), sum(price) FROM orders;"
        }
    ]
    additional_validations = []

    def _get_exclusions(self, rule_config: Dict[str, Any]) -> Set[str]:
        override = rule_config.get("override_exclusions")
        if override is not None:
            if isinstance(override, str):
                override = [x.strip().lower() for x in override.split(",") if x.strip()]
            return {k.lower() for k in override}
            
        additional = rule_config.get("additional_exclusions", [])
        if isinstance(additional, str):
            additional = [x.strip() for x in additional.split(",") if x.strip()]
            
        default_ex = {k.lower() for k in EXCLUDED_WORDS}
        for k in additional:
            default_ex.add(k.lower())
        return default_ex

    def _find_function_calls(self, content: str, exclusions: Set[str]) -> List[tuple]:
        n = len(content)
        i = 0
        in_string = False
        string_char = None
        in_single_comment = False
        in_multi_comment = False
        
        line_number = 1
        matches = []
        
        while i < n:
            c = content[i]
            
            if c == '\n':
                line_number += 1
                
            if in_string:
                if c == string_char:
                    if i + 1 < n and content[i + 1] == string_char:
                        i += 2
                        continue
                    in_string = False
                i += 1
                continue
                
            if in_single_comment:
                if c == '\n':
                    in_single_comment = False
                i += 1
                continue
                
            if in_multi_comment:
                if c == '*' and i + 1 < n and content[i + 1] == '/':
                    in_multi_comment = False
                    i += 2
                    continue
                i += 1
                continue
                
            if c in ("'", '"'):
                in_string = True
                string_char = c
                i += 1
                continue
                
            if c == '-' and i + 1 < n and content[i + 1] == '-':
                in_single_comment = True
                i += 2
                continue
                
            if c == '/' and i + 1 < n and content[i + 1] == '*':
                in_multi_comment = True
                i += 2
                continue
                
            if c.isalpha() or c == '_':
                w_start = i
                w_line = line_number
                while i < n and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[w_start:i]
                
                peek_idx = i
                while peek_idx < n and content[peek_idx].isspace():
                    if content[peek_idx] == '\n':
                        line_number += 1
                    peek_idx += 1
                    
                if peek_idx < n and content[peek_idx] == '(':
                    if word.lower() not in exclusions:
                        matches.append((w_start, i, word, w_line))
                continue
                
            i += 1
            
        return matches

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        target_case = rule_config.get("case", self.default_config["case"])
        exclusions = self._get_exclusions(rule_config)
        violations = []
        
        calls = self._find_function_calls(content, exclusions)
        lines = content.splitlines()
        
        for start, end, name, line_num in calls:
            expected = name.lower() if target_case == "lowercase" else name.upper()
            if name != expected:
                line_content = lines[line_num - 1] if line_num - 1 < len(lines) else ""
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=line_num,
                        message=f"Function name '{name}' must be {target_case}.",
                        offending_lines=[line_content],
                        is_fixable=True
                    )
                )
                
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        target_case = rule_config.get("case", self.default_config["case"])
        exclusions = self._get_exclusions(rule_config)
        calls = self._find_function_calls(content, exclusions)
        if not calls:
            return content
            
        fixed_chunks = []
        last_idx = 0
        
        for start, end, name, _ in calls:
            expected = name.lower() if target_case == "lowercase" else name.upper()
            fixed_chunks.append(content[last_idx:start])
            fixed_chunks.append(expected)
            last_idx = end
            
        fixed_chunks.append(content[last_idx:])
        return "".join(fixed_chunks)
