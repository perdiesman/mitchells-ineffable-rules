from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class JoinNullCoalesceRule(BaseRule):
    rule_id = "IR-join-null-coalesce"
    description = "Standardize predicate checks of form 'x = v OR x IS NULL' to COALESCE(x, -1) = v."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE active = true OR active IS NULL;",
            "correct": "SELECT * FROM users WHERE COALESCE(active, -1) = true;"
        },
        {
            "violating": "SELECT * FROM users WHERE active IS NULL OR active = true;",
            "correct": "SELECT * FROM users WHERE COALESCE(active, -1) = true;"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        active = []
        for idx, t in enumerate(tokens):
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)
                
        num_active = len(active)
        i = 0
        while i < num_active:
            if i + 6 < num_active:
                t1 = active[i]
                t2 = active[i + 1]
                t3 = active[i + 2]
                t4 = active[i + 3]
                t5 = active[i + 4]
                t6 = active[i + 5]
                t7 = active[i + 6]
                
                is_pattern_a = (
                    t1["type"] == "IDENTIFIER"
                    and t2["type"] == "OPERATOR" and t2["value"] == "="
                    and t3["type"] in ("IDENTIFIER", "STRING", "NUMBER", "KEYWORD")
                    and t4["type"] == "KEYWORD" and t4["value"].upper() == "OR"
                    and t5["type"] == "IDENTIFIER" and t5["value"].lower() == t1["value"].lower()
                    and t6["type"] == "KEYWORD" and t6["value"].upper() == "IS"
                    and t7["type"] == "KEYWORD" and t7["value"].upper() == "NULL"
                )
                if is_pattern_a:
                    violations.append({
                        "start_offset": t1["start"],
                        "end_offset": t7["end"],
                        "line": t1["line"],
                        "replacement": f"COALESCE({t1['value']}, -1) = {t3['value']}"
                    })
                    i += 7
                    continue
                    
            if i + 6 < num_active:
                t1 = active[i]
                t2 = active[i + 1]
                t3 = active[i + 2]
                t4 = active[i + 3]
                t5 = active[i + 4]
                t6 = active[i + 5]
                t7 = active[i + 6]
                
                is_pattern_b = (
                    t1["type"] == "IDENTIFIER"
                    and t2["type"] == "KEYWORD" and t2["value"].upper() == "IS"
                    and t3["type"] == "KEYWORD" and t3["value"].upper() == "NULL"
                    and t4["type"] == "KEYWORD" and t4["value"].upper() == "OR"
                    and t5["type"] == "IDENTIFIER" and t5["value"].lower() == t1["value"].lower()
                    and t6["type"] == "OPERATOR" and t6["value"] == "="
                    and t7["type"] in ("IDENTIFIER", "STRING", "NUMBER", "KEYWORD")
                )
                if is_pattern_b:
                    violations.append({
                        "start_offset": t1["start"],
                        "end_offset": t7["end"],
                        "line": t1["line"],
                        "replacement": f"COALESCE({t1['value']}, -1) = {t7['value']}"
                    })
                    i += 7
                    continue
                    
            i += 1
            
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
                    message="Predicate structure should be standardized to COALESCE format.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        edits = []
        for item in offending:
            edits.append((item["start_offset"], item["end_offset"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
