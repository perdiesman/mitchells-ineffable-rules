from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class CreateViewIndentRule(BaseRule):
    rule_id = "IR-create-view-indent"
    description = "SELECT statements under a CREATE VIEW should be indented 4 spaces relative to the CREATE VIEW statement."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "CREATE VIEW v AS\nSELECT * FROM users;",
            "correct": "CREATE VIEW v AS\n    SELECT * FROM users;"
        }
    ]
    additional_validations = [
        'CREATE MATERIALIZED VIEW mv AS\n    SELECT * FROM users;'
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        for i, tok in enumerate(tokens):
            if tok["type"] == "KEYWORD" and tok["value"].upper() == "CREATE":
                is_view = False
                view_tok_idx = None
                for idx in range(i + 1, min(i + 4, n)):
                    if tokens[idx]["type"] == "KEYWORD" and tokens[idx]["value"].upper() == "VIEW":
                        is_view = True
                        view_tok_idx = idx
                        break
                        
                if is_view:
                    line_start = content.rfind("\n", 0, tok["start"]) + 1
                    line_prefix = content[line_start:tok["start"]]
                    create_indent = ""
                    for char in line_prefix:
                        if char in (" ", "\t"):
                            create_indent += char
                        else:
                            break
                            
                    expected_indent = create_indent + "    "
                    
                    as_tok_idx = None
                    for idx in range(view_tok_idx + 1, n):
                        t = tokens[idx]
                        d = depths[idx]
                        if d == depths[i]:
                            if t["type"] == "KEYWORD" and t["value"].upper() == "AS":
                                as_tok_idx = idx
                                break
                            elif t["type"] == "SEMI":
                                break
                                
                    if as_tok_idx is not None:
                        next_active_idx = None
                        ws_tok = None
                        for idx in range(as_tok_idx + 1, n):
                            if tokens[idx]["type"] == "WHITESPACE":
                                ws_tok = tokens[idx]
                            elif tokens[idx]["type"] != "COMMENT":
                                next_active_idx = idx
                                break
                                
                        if next_active_idx is not None:
                            next_tok = tokens[next_active_idx]
                            if next_tok["type"] == "KEYWORD" and next_tok["value"].upper() == "SELECT":
                                expected_replacement = "\n" + expected_indent
                                if not ws_tok or ws_tok["value"] != expected_replacement:
                                    violations.append({
                                        "token": next_tok,
                                        "ws_start": ws_tok["start"] if ws_tok else as_tok_idx["end"],
                                        "ws_end": next_tok["start"],
                                        "replacement": expected_replacement
                                    })
                                    
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            tok = item["token"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=tok["line"],
                    message="SELECT statement under CREATE VIEW should be indented by 4 spaces.",
                    offending_lines=[lines[tok["line"] - 1] if tok["line"] - 1 < len(lines) else ""],
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
            edits.append((item["ws_start"], item["ws_end"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
