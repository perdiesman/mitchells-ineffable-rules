from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class TriggerLayoutRule(BaseRule):
    rule_id = "IR-trigger-layout"
    description = "Format and wrap long CREATE TRIGGER statements to standard multiline layout."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "max_length": 120
    }
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length before wrapping trigger statements."
        }
    }
    
    examples = [
        {
            "violating": "CREATE TRIGGER update_user_access BEFORE UPDATE OF manager ON community.community_user_xref FOR EACH ROW EXECUTE FUNCTION community.community_user_manager_access_function();",
            "correct": "CREATE TRIGGER update_user_access\n    BEFORE UPDATE OF manager ON community.community_user_xref\n    FOR EACH ROW\n    EXECUTE FUNCTION community.community_user_manager_access_function();"
        }
    ]
    additional_validations = [
        "CREATE TRIGGER short_trigger BEFORE INSERT ON t FOR EACH ROW EXECUTE FUNCTION f();"
    ]

    def _indent_clause(self, clause_str: str, indent: str) -> str:
        lines = clause_str.splitlines()
        if not lines:
            return ""
        return lines[0].strip() + "".join("\n" + indent + line.strip() for line in lines[1:])

    def _find_violations(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_len = self.get_config_value(rule_config, "max_length", 120)
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        i = 0
        while i < n:
            t = tokens[i]
            if t["type"] == "KEYWORD" and t["value"].upper() == "CREATE":
                # Look ahead for TRIGGER
                is_trigger = False
                trigger_idx = None
                for idx in range(i + 1, min(i + 5, n)):
                    if tokens[idx]["type"] == "WHITESPACE":
                        continue
                    if tokens[idx]["value"].upper() == "TRIGGER":
                        is_trigger = True
                        trigger_idx = idx
                        break
                    if tokens[idx]["value"].upper() not in ("OR", "REPLACE"):
                        break
                        
                if not is_trigger:
                    i += 1
                    continue
                    
                # Find the ending semicolon of this statement
                semi_idx = None
                for idx in range(trigger_idx + 1, n):
                    # But stop if we see another CREATE/ALTER/DROP statement
                    if tokens[idx]["type"] == "KEYWORD" and tokens[idx]["value"].upper() in ("CREATE", "ALTER", "DROP"):
                        break
                    if tokens[idx]["type"] == "SEMI":
                        semi_idx = idx
                        break
                        
                if semi_idx is None:
                    i = trigger_idx + 1
                    continue
                    
                stmt_tokens = tokens[i : semi_idx + 1]
                active_tokens = [tok for tok in stmt_tokens if tok["type"] not in ("WHITESPACE", "COMMENT")]
                
                # Locate key trigger keywords
                event_tok = None
                for_tok = None
                when_tok = None
                execute_tok = None
                
                # Find event keyword: BEFORE, AFTER, INSTEAD
                for tok in active_tokens:
                    val_up = tok["value"].upper()
                    if val_up in ("BEFORE", "AFTER", "INSTEAD"):
                        event_tok = tok
                        break
                        
                # Find FOR (if followed by EACH)
                for idx, tok in enumerate(active_tokens):
                    val_up = tok["value"].upper()
                    if val_up == "FOR" and idx + 1 < len(active_tokens):
                        if active_tokens[idx + 1]["value"].upper() == "EACH":
                            for_tok = tok
                            break
                            
                # Find WHEN
                for tok in active_tokens:
                    val_up = tok["value"].upper()
                    if val_up == "WHEN":
                        when_tok = tok
                        break
                        
                # Find EXECUTE (if followed by FUNCTION/PROCEDURE)
                for idx, tok in enumerate(active_tokens):
                    val_up = tok["value"].upper()
                    if val_up == "EXECUTE" and idx + 1 < len(active_tokens):
                        if active_tokens[idx + 1]["value"].upper() in ("FUNCTION", "PROCEDURE"):
                            execute_tok = tok
                            break
                            
                if not (event_tok and for_tok and execute_tok):
                    i = semi_idx + 1
                    continue
                    
                # Slices for clauses
                c1_start = t["start"]
                c1_end = event_tok["start"]
                
                c2_start = event_tok["start"]
                c2_end = for_tok["start"]
                
                c3_start = for_tok["start"]
                c3_end = when_tok["start"] if when_tok else execute_tok["start"]
                
                c4_start = when_tok["start"] if when_tok else None
                c4_end = execute_tok["start"] if when_tok else None
                
                c5_start = execute_tok["start"]
                c5_end = tokens[semi_idx]["end"]
                
                c1_str = content[c1_start:c1_end].strip()
                c2_str = content[c2_start:c2_end].strip()
                c3_str = content[c3_start:c3_end].strip()
                c4_str = content[c4_start:c4_end].strip() if when_tok else ""
                c5_str = content[c5_start:c5_end].strip()
                
                # Check base indentation of CREATE trigger statement
                line_start = content.rfind("\n", 0, t["start"]) + 1
                line_prefix = content[line_start:t["start"]]
                base_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        base_indent += char
                    else:
                        break
                clause_indent = base_indent + "    "
                
                import re
                c2_flat = re.sub(r"\s+", " ", c2_str)
                c3_flat = re.sub(r"\s+", " ", c3_str)
                c4_flat = re.sub(r"\s+", " ", c4_str)
                c5_flat = re.sub(r"\s+", " ", c5_str)
                single_line = c1_str + " " + c2_flat + " " + c3_flat + (" " + c4_flat if c4_flat else "") + " " + c5_flat
                if len(base_indent + single_line) <= max_len:
                    expected = single_line
                else:
                    expected = (
                        c1_str + "\n" +
                        clause_indent + self._indent_clause(c2_str, clause_indent) + "\n" +
                        clause_indent + self._indent_clause(c3_str, clause_indent) +
                        ("\n" + clause_indent + self._indent_clause(c4_str, clause_indent) if c4_str else "") + "\n" +
                        clause_indent + self._indent_clause(c5_str, clause_indent)
                    )
                    
                original = content[t["start"] : tokens[semi_idx]["end"]].strip()
                if original != expected:
                    violations.append({
                        "start_offset": t["start"],
                        "end_offset": tokens[semi_idx]["end"],
                        "replacement": expected,
                        "line": t["line"]
                    })
                    
                i = semi_idx + 1
                continue
                
            i += 1
            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        for item in offending:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message="Long CREATE TRIGGER statement should be split onto multiple lines.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content, rule_config)
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
