import re
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

EXCLUDED_WORDS = {
    "in", "values", "exists", "join", "using", "on",
    "and", "or", "not", "select", "from", "where",
    "having", "between", "like", "as", "over", "partition",
    "by", "window", "group", "order", "limit", "offset",
    "union", "all", "intersect", "except", "distinct",
    "with", "recursive", "case", "when", "then", "else", "end"
}

class FunctionCaseRule(BaseRule):
    rule_id = "IR-function-case"
    description = "Function names should be the same case (default lowercase)."
    category = "function/procedure"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "case": "lowercase"  # "lowercase" or "uppercase"
    }
    
    examples_violating = [
        "SELECT COUNT(id), Sum(price) FROM orders;"
    ]
    examples_correct = [
        "SELECT count(id), sum(price) FROM orders;"
    ]

    def _find_function_calls(self, content: str) -> List[tuple]:
        """
        Scans content character-by-character to locate function names outside strings and comments.
        Returns a list of tuples: (start_idx, end_idx, function_name, line_number)
        """
        n = len(content)
        i = 0
        in_string = False
        string_char = None
        in_single_comment = False
        in_multi_comment = False
        
        # Track line number
        line_number = 1
        
        matches = []
        
        while i < n:
            c = content[i]
            
            if c == '\n':
                line_number += 1
                
            # String handling
            if in_string:
                if c == string_char:
                    # check escape
                    if i + 1 < n and content[i + 1] == string_char:
                        i += 2
                        continue
                    in_string = False
                i += 1
                continue
                
            # Comment handling
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
                
            # Transitions
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
                
            # Match identifier word
            if c.isalpha() or c == '_':
                w_start = i
                # Track line number of word start
                w_line = line_number
                while i < n and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[w_start:i]
                
                # Peek next non-whitespace char
                peek_idx = i
                while peek_idx < n and content[peek_idx].isspace():
                    if content[peek_idx] == '\n':
                        line_number += 1
                    peek_idx += 1
                    
                if peek_idx < n and content[peek_idx] == '(':
                    # Is it in exclusions?
                    if word.lower() not in EXCLUDED_WORDS:
                        matches.append((w_start, i, word, w_line))
                # Do not increment i further as we already advanced past the word
                continue
                
            i += 1
            
        return matches

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        target_case = rule_config.get("case", self.default_config["case"])
        violations = []
        
        calls = self._find_function_calls(content)
        lines = content.splitlines()
        
        for start, end, name, line_num in calls:
            # Check casing
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
        calls = self._find_function_calls(content)
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
