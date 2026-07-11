from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_datatype_token_groups

class DataTypeFormatRule(BaseRule):
    rule_id = "IR-datatype-format"
    description = "Standardize SQL data types to use their long format (character varying instead of varchar, timestamp with time zone instead of timestamptz)."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT 1::varchar, '2026-07-11'::timestamptz;",
            "correct": "SELECT 1::character varying, '2026-07-11'::timestamp with time zone;"
        }
    ]
    additional_validations = [
        "SELECT 1::character varying(255);"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        groups = find_datatype_token_groups(tokens, content)
        violations = []
        
        for g in groups:
            first_tok = g[0]
            val_lower = first_tok["value"].lower()
            
            if val_lower in ("varchar", "timestamptz"):
                # Determine correct long format casing matching the original
                is_upper = first_tok["value"].isupper()
                if val_lower == "varchar":
                    replacement = "CHARACTER VARYING" if is_upper else "character varying"
                else:
                    replacement = "TIMESTAMP WITH TIME ZONE" if is_upper else "timestamp with time zone"
                    
                violations.append({
                    "start_offset": first_tok["start"],
                    "end_offset": first_tok["end"],
                    "replacement": replacement,
                    "original": first_tok["value"],
                    "line": first_tok["line"]
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
                    message=f"Data type '{item['original']}' should be written in long format '{item['replacement']}'.",
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
