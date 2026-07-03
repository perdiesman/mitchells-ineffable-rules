from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class DuplicateContentRule(BaseRule):
    rule_id = "IR-duplicate-content"
    description = "Duplicate blocks of SQL of length >= 3 lines should be consolidated or simplified."
    category = "select/view/materialized view"
    is_fixable = "no"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT a, b, c\nFROM t1\nWHERE x = 1;\n\nSELECT a, b, c\nFROM t1\nWHERE x = 1;"
        }
    ]
    additional_validations = [
        "SELECT a, b, c\nFROM t1\nWHERE x = 1;\n\nSELECT a, b, d\nFROM t1\nWHERE x = 1;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        lines = content.splitlines()
        cleaned_lines = []
        for idx, line in enumerate(lines):
            cleaned = line.strip()
            if cleaned == "" or cleaned.startswith("--"):
                continue
            cleaned_lines.append((idx + 1, cleaned))
            
        n = len(cleaned_lines)
        violations = []
        visited_ranges = set()
        
        for i in range(n):
            for j in range(i + 3, n):
                L = 0
                while i + L < j and j + L < n and cleaned_lines[i + L][1] == cleaned_lines[j + L][1]:
                    L += 1
                if L >= 3:
                    is_covered = False
                    for (prev_i, prev_j, prev_L) in visited_ranges:
                        if prev_i <= i and i + L <= prev_i + prev_L and prev_j <= j and j + L <= prev_j + prev_L:
                            is_covered = True
                            break
                    if not is_covered:
                        visited_ranges.add((i, j, L))
                        violations.append({
                            "line": cleaned_lines[i][0],
                            "match_line": cleaned_lines[j][0],
                            "length": L
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
                    message=f"Duplicate SQL block of length {item['length']} lines found (matches block starting at line {item['match_line']}).",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=False
                )
            )
        return violations
