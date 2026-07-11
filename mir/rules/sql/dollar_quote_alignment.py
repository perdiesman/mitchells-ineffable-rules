import re
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class DollarQuoteAlignmentRule(BaseRule):
    rule_id = "IR-dollar-quote-alignment"
    description = "Align the closing dollar quote ($function$, $$, etc.) with its opening tag."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "CREATE FUNCTION f() RETURNS void AS\n$function$\n    SELECT 1;\n        $function$;",
            "correct": "CREATE FUNCTION f() RETURNS void AS\n$function$\n    SELECT 1;\n$function$;"
        }
    ]
    additional_validations = [
        "SELECT 'hello';"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        
        for t in tokens:
            if t["type"] == "STRING" and t["value"].startswith("$"):
                val = t["value"]
                match = re.match(r'^\$[a-zA-Z0-9_]*\$', val)
                if not match:
                    continue
                tag = match.group(0)
                
                # Check if multi-line
                inner_body = val[len(tag) : -len(tag)]
                last_newline = inner_body.rfind("\n")
                if last_newline == -1:
                    continue
                    
                # Find opening indentation
                line_start = content.rfind("\n", 0, t["start"]) + 1
                line_prefix = content[line_start:t["start"]]
                opening_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        opening_indent += char
                    else:
                        break
                        
                pre_body = inner_body[:last_newline]
                expected_val = tag + pre_body + "\n" + opening_indent + tag
                
                if val != expected_val:
                    violations.append({
                        "start_offset": t["start"],
                        "end_offset": t["end"],
                        "replacement": expected_val,
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
                    message="Closing dollar quote is not aligned with its opening tag.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
        offending.sort(key=lambda x: x["start_offset"], reverse=True)
        chars = list(content)
        for item in offending:
            start = item["start_offset"]
            end = item["end_offset"]
            repl = item["replacement"]
            chars[start:end] = list(repl)
        return "".join(chars)
