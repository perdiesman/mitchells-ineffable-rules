from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths

class StatementSemicolonRule(BaseRule):
    rule_id = "IR-statement-semicolon"
    description = "Enforce that all top-level statements end with a trailing semicolon."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "CREATE TRIGGER trig1 BEFORE INSERT ON t1 FOR EACH ROW EXECUTE FUNCTION f1()\nCREATE TRIGGER trig2 BEFORE INSERT ON t2 FOR EACH ROW EXECUTE FUNCTION f2()",
            "correct": "CREATE TRIGGER trig1 BEFORE INSERT ON t1 FOR EACH ROW EXECUTE FUNCTION f1();\nCREATE TRIGGER trig2 BEFORE INSERT ON t2 FOR EACH ROW EXECUTE FUNCTION f2();"
        }
    ]
    additional_validations = [
        "ALTER FUNCTION my_func OWNER TO eiadmin;\nCREATE TRIGGER trig1 BEFORE INSERT ON t1 FOR EACH ROW EXECUTE FUNCTION f1();"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        violations = []
        n = len(tokens)
        
        statement_starters = {
            "DROP", "CREATE", "ALTER", "INSERT", "UPDATE", "DELETE", "SELECT", "GRANT", "REVOKE"
        }
        
        active_tokens_info = []
        for idx, t in enumerate(tokens):
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active_tokens_info.append({
                    "token": t,
                    "depth": depths[idx],
                    "idx": idx
                })
                
        # Traverse active tokens and check statement boundaries
        m = len(active_tokens_info)
        for i in range(m):
            info = active_tokens_info[i]
            t = info["token"]
            
            # If this starts a new top-level statement, check the preceding active token
            if info["depth"] == 0 and t["type"] == "KEYWORD":
                val_upper = t["value"].upper()
                is_starter = False
                if val_upper in ("DROP", "CREATE", "ALTER", "GRANT", "REVOKE"):
                    is_starter = True
                elif val_upper in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    if i == 0 or active_tokens_info[i - 1]["token"]["value"] == ";":
                        is_starter = True
                        
                if is_starter:
                    if i > 0:
                        prev_info = active_tokens_info[i - 1]
                        prev_tok = prev_info["token"]
                        if prev_tok["value"] != ";":
                            # The preceding statement is missing a semicolon!
                            violations.append({
                                "type": "missing",
                                "token": prev_tok,
                                "insert_pos": prev_tok["end"],
                                "line": prev_tok["line"]
                            })
                        
        # Also check the very last active token in the file
        if m > 0:
            last_info = active_tokens_info[-1]
            last_tok = last_info["token"]
            if last_tok["value"] != ";":
                violations.append({
                    "type": "missing",
                    "token": last_tok,
                    "insert_pos": last_tok["end"],
                    "line": last_tok["line"]
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
                    line_number=item["line"],
                    message="Top-level statement is missing a trailing semicolon.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        # Apply edits in reverse order
        fixed_content = content
        # Filter duplicates in case the same token is flagged twice
        seen_positions = set()
        unique_offending = []
        for item in offending:
            pos = item["insert_pos"]
            if pos not in seen_positions:
                seen_positions.add(pos)
                unique_offending.append(item)
                
        for item in sorted(unique_offending, key=lambda x: x["insert_pos"], reverse=True):
            pos = item["insert_pos"]
            fixed_content = fixed_content[:pos] + ";" + fixed_content[pos:]
            
        return fixed_content
