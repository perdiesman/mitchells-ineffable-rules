from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class IndentRule(BaseRule):
    rule_id = "IR-indent"
    description = "Indent should be equal amounts of spaces (default 4)."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "indent_size": 4,
        "base_indent": 0
    }
    config_options = {
        "indent_size": {
            "default": 4,
            "description": "Indentation size in spaces."
        },
        "base_indent": {
            "default": 0,
            "description": "Base indentation level (in spaces or leading space string) to expect for all lines."
        }
    }
    
    examples = [
        {
            "violating": "SELECT\n  id,\n   name\nFROM users;",
            "correct": "SELECT\n    id,\n    name\nFROM users;"
        }
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        indent_size = rule_config.get("indent_size", self.default_config["indent_size"])
        base_indent_opt = rule_config.get("base_indent", self.default_config["base_indent"])
        if isinstance(base_indent_opt, str):
            base_indent_spaces = len(base_indent_opt.replace("\t", " " * indent_size))
        elif isinstance(base_indent_opt, int):
            base_indent_spaces = base_indent_opt
        else:
            base_indent_spaces = 0
            
        violations = []
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
            relative_spaces = num_spaces - base_indent_spaces
            if relative_spaces < 0:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=idx,
                        message=f"Line {idx} indentation is {num_spaces} spaces, which is less than the base indentation of {base_indent_spaces} spaces.",
                        offending_lines=[line],
                        is_fixable=True
                    )
                )
            elif relative_spaces % indent_size != 0:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=idx,
                        message=f"Line {idx} indentation is {num_spaces} spaces. Expected a multiple of {indent_size} spaces relative to base indentation {base_indent_spaces}.",
                        offending_lines=[line],
                        is_fixable=True
                    )
                )
                
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        indent_size = rule_config.get("indent_size", self.default_config["indent_size"])
        base_indent_opt = rule_config.get("base_indent", self.default_config["base_indent"])
        if isinstance(base_indent_opt, str):
            base_indent_spaces = len(base_indent_opt.replace("\t", " " * indent_size))
        elif isinstance(base_indent_opt, int):
            base_indent_spaces = base_indent_opt
        else:
            base_indent_spaces = 0
            
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
            
            relative_spaces = num_spaces - base_indent_spaces
            if relative_spaces < 0:
                relative_spaces = 0
                
            remainder = relative_spaces % indent_size
            if remainder != 0:
                if remainder >= (indent_size / 2):
                    relative_spaces += (indent_size - remainder)
                else:
                    relative_spaces -= remainder
                    
            final_spaces = base_indent_spaces + relative_spaces
            fixed_lines.append(" " * final_spaces + content_part)
            
        ending = "\r\n" if "\r\n" in content else "\n"
        eof_ending = ending if content.endswith(ending) else ""
        return ending.join(fixed_lines) + eof_ending
