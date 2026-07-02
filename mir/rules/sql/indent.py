from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class IndentRule(BaseRule):
    rule_id = "IR-indent"
    description = "Indent should be equal amounts of spaces (default 4)."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "indent_size": 4
    }
    
    examples = [
        {
            "violating": "SELECT\n  id,\n   name\nFROM users;",
            "correct": "SELECT\n    id,\n    name\nFROM users;"
        }
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        indent_size = rule_config.get("indent_size", self.default_config["indent_size"])
        violations = []
        
        # We split by lines but handle carrying of disablers if comments exist,
        # but check is purely per-line leading spaces validation.
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            if not line.strip():
                continue # Ignore empty lines
            
            # Count leading spaces and check tabs
            leading_whitespace = ""
            for char in line:
                if char in (" ", "\t"):
                    leading_whitespace += char
                else:
                    break
                    
            if "\t" in leading_whitespace:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=idx,
                        message=f"Line {idx} contains tab characters for indentation. Use spaces.",
                        offending_lines=[line],
                        is_fixable=True
                    )
                )
                continue
                
            num_spaces = len(leading_whitespace)
            if num_spaces % indent_size != 0:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=idx,
                        message=f"Line {idx} indentation is {num_spaces} spaces. Expected a multiple of {indent_size}.",
                        offending_lines=[line],
                        is_fixable=True
                    )
                )
                
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        indent_size = rule_config.get("indent_size", self.default_config["indent_size"])
        lines = content.splitlines()
        fixed_lines = []
        
        for idx, line in enumerate(lines, start=1):
            if not line.strip():
                fixed_lines.append(line)
                continue
                
            # Count leading spaces/tabs
            leading_whitespace = ""
            for char in line:
                if char in (" ", "\t"):
                    leading_whitespace += char
                else:
                    break
                    
            content_part = line[len(leading_whitespace):]
            
            # Replace tabs with spaces (1 tab = indent_size spaces)
            clean_whitespace = leading_whitespace.replace("\t", " " * indent_size)
            num_spaces = len(clean_whitespace)
            
            # Round to the nearest multiple of indent_size
            remainder = num_spaces % indent_size
            if remainder != 0:
                if remainder >= (indent_size / 2):
                    num_spaces += (indent_size - remainder)
                else:
                    num_spaces -= remainder
                    
            fixed_lines.append(" " * num_spaces + content_part)
            
        ending = "\r\n" if "\r\n" in content else "\n"
        return ending.join(fixed_lines)
