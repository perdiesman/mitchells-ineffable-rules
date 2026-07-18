from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class CommaStyleRule(BaseRule):
    rule_id = "IR-comma-style"
    description = "Enforce trailing commas in multiline listings and forbid leading commas."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT id\n    , name\nFROM users;",
            "correct": "SELECT id,\n     name\nFROM users;"
        }
    ]
    additional_validations = [
        "SELECT id, name FROM users;"
    ]

    def _find_violations(self, content: str, rule_config: Dict[str, Any] = None) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)

        # Filter active tokens
        active = []
        for t in tokens:
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)

        num_active = len(active)
        # Find map of token ID to index in tokens
        token_to_idx = {id(t): idx for idx, t in enumerate(tokens)}

        ignored_offsets = set()
        if rule_config and "ignored_comma_offsets" in rule_config:
            ignored_offsets = rule_config["ignored_comma_offsets"]

        for idx, t in enumerate(active):
            if t["value"] == ",":
                if t["start"] in ignored_offsets:
                    continue
                if idx > 0:
                    prev_active = active[idx - 1]
                    prev_active_idx = token_to_idx[id(prev_active)]
                    curr_idx = token_to_idx[id(t)]
                    
                    # Get whitespace/comments between prev_active and comma
                    between = tokens[prev_active_idx + 1 : curr_idx]
                    between_str = "".join(tok["value"] for tok in between)
                    
                    if "\n" in between_str:
                        # Comma is leading (separated by newline from previous item)
                        start_offset = prev_active["end"]
                        end_offset = t["end"]
                        replacement = "," + between_str

                        violations.append({
                            "token": t,
                            "line": t["line"],
                            "start_offset": start_offset,
                            "end_offset": end_offset,
                            "replacement": replacement,
                            "message": f"Leading comma on line {t['line']} should be trailing."
                        })

        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        for v in offending:
            line_idx = v["line"] - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=v["line"],
                message=v["message"],
                offending_lines=[offending_line],
                is_fixable=True
            ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content, rule_config)
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
