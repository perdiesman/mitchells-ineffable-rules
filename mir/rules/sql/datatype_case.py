from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_datatype_token_groups

class DataTypeCaseRule(BaseRule):
    rule_id = "IR-datatype-case"
    description = "Standardize SQL data types to be uppercase."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT 1::text, '2026-07-11'::timestamp with time zone;",
            "correct": "SELECT 1::TEXT, '2026-07-11'::TIMESTAMP WITH TIME ZONE;"
        }
    ]
    additional_validations = [
        "SELECT 1::INTEGER;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        groups = find_datatype_token_groups(tokens, content)
        violations = []
        
        for g in groups:
            # We want to check all alphabetic identifiers or keywords in the type group
            # and verify if they are uppercase
            non_uppercase = []
            for tok in g:
                if tok["type"] in ("IDENTIFIER", "KEYWORD"):
                    val = tok["value"]
                    if val.isalpha() and not val.isupper():
                        non_uppercase.append(tok)
            if non_uppercase:
                violations.append({
                    "tokens": g,
                    "line": g[0]["line"]
                })
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        for item in offending:
            g = item["tokens"]
            type_str = "".join(t["value"] for t in g)
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message=f"Data type '{type_str}' should be uppercase.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        offending.sort(key=lambda x: x["tokens"][0]["start"], reverse=True)
        chars = list(content)
        
        for item in offending:
            g = item["tokens"]
            # We perform fixes token-by-token in reverse order of the groups
            # to avoid offset shifting issues
            for tok in reversed(g):
                if tok["type"] in ("IDENTIFIER", "KEYWORD"):
                    val = tok["value"]
                    if val.isalpha() and not val.isupper():
                        start = tok["start"]
                        end = tok["end"]
                        chars[start:end] = list(val.upper())
                        
        return "".join(chars)
