from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class FunctionBodyIndentRule(BaseRule):
    rule_id = "IR-function-body-indent"
    description = "Standardize indentation of PL/pgSQL function bodies relative to the AS tag."
    category = "routines"
    is_fixable = "yes"
    enabled_by_default = True
    exclude_recursive = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "AS $function$\n    BEGIN\n        RETURN NEW;\n    END;\n$function$;",
            "correct": "AS $function$\nBEGIN\n    RETURN NEW;\nEND;\n$function$;"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        
        for t in tokens:
            if t["type"] == "STRING" and t["value"].startswith("$"):
                val = t["value"]
                # Extract the tag
                dollar_idx = val.find("$", 1)
                if dollar_idx == -1:
                    continue
                tag = val[:dollar_idx + 1]
                
                if not val.endswith(tag):
                    continue
                    
                lines = val.splitlines()
                if len(lines) < 3:
                    continue
                    
                body_lines = lines[1:-1]
                
                # Find first non-empty line to check indentation
                first_line = None
                for line in body_lines:
                    if line.strip():
                        first_line = line
                        break
                        
                if first_line is None:
                    continue
                    
                first_word = first_line.strip().split()[0].upper() if first_line.strip() else ""
                if first_word not in ("DECLARE", "BEGIN"):
                    continue
                    
                leading_spaces = len(first_line) - len(first_line.lstrip())
                if leading_spaces != 0:
                    violations.append({
                        "token": t,
                        "lines": lines,
                        "delta": -leading_spaces,
                        "line": t["line"]
                    })
                    
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        for item in offending:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message="PL/pgSQL function body blocks (DECLARE/BEGIN) should start with 0 indentation relative to the dollar quote.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        offending.sort(key=lambda x: x["token"]["start"], reverse=True)
        chars = list(content)
        
        for item in offending:
            t = item["token"]
            lines = list(item["lines"])
            delta = item["delta"]
            
            # Shift body lines
            for i in range(1, len(lines) - 1):
                line = lines[i]
                if not line.strip():
                    lines[i] = ""
                else:
                    curr_indent = len(line) - len(line.lstrip())
                    new_indent = max(0, curr_indent + delta)
                    lines[i] = (" " * new_indent) + line.lstrip()
                    
            new_val = "\n".join(lines)
            chars[t["start"]:t["end"]] = list(new_val)
            
        return "".join(chars)
