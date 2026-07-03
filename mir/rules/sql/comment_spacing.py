from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class CommentSpacingRule(BaseRule):
    rule_id = "IR-comment-spacing"
    description = "Enforce a single space after the double-dash comment prefix."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "--todo: clean up old table\nSELECT * FROM users;",
            "correct": "-- todo: clean up old table\nSELECT * FROM users;"
        }
    ]
    additional_validations = [
        "-- already spaced comment",
        "--- divider comment line",
        "SELECT * FROM users; -- inline comment"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        
        for tok in tokens:
            if tok["type"] == "COMMENT" and tok["value"].startswith("--"):
                val = tok["value"]
                if not val.startswith("---"):
                    if len(val) > 2 and val[2] not in (" ", "\t", "\n", "\r"):
                        violations.append({
                            "start_offset": tok["start"],
                            "end_offset": tok["end"],
                            "replacement": "-- " + val[2:],
                            "line": tok["line"]
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
                    message="Inline comments should have a single space after the '--' prefix.",
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
