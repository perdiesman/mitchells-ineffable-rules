from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class UpdateLayoutRule(BaseRule):
    rule_id = "IR-update-layout"
    description = "Format and wrap long UPDATE statements: align SET and WHERE with UPDATE, indent assignments."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "max_length": 120
    }
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length before wrapping UPDATE statements."
        }
    }
    
    examples = [
        {
            "violating": "UPDATE my_schema.my_very_long_table_name SET is_active = false WHERE user_id = NEW.user_id AND type_id = NEW.type_id AND id != NEW.id;",
            "correct": "UPDATE my_schema.my_very_long_table_name\nSET is_active = false\nWHERE user_id = NEW.user_id AND type_id = NEW.type_id AND id != NEW.id;"
        },
        {
            "violating": "UPDATE my_very_long_table SET my_first_very_long_field_with_very_long_value = 1, my_second_very_long_field_with_very_long_value = 2 WHERE some_condition;",
            "correct": "UPDATE my_very_long_table\nSET\n    my_first_very_long_field_with_very_long_value = 1,\n    my_second_very_long_field_with_very_long_value = 2\nWHERE some_condition;"
        }
    ]
    additional_validations = [
        "UPDATE t SET a = 1 WHERE b = 2;"
    ]

    def _find_violations(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_len = self.get_config_value(rule_config, "max_length", 120)
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        i = 0
        while i < n:
            t = tokens[i]
            if t["type"] == "KEYWORD" and t["value"].upper() == "UPDATE":
                # Find ending semicolon
                semi_idx = None
                for idx in range(i + 1, n):
                    if tokens[idx]["type"] == "KEYWORD" and tokens[idx]["value"].upper() in ("CREATE", "ALTER", "DROP", "UPDATE"):
                        break
                    if tokens[idx]["type"] == "SEMI":
                        semi_idx = idx
                        break
                        
                if semi_idx is None:
                    i += 1
                    continue
                    
                stmt_tokens = tokens[i : semi_idx + 1]
                active_tokens = [tok for tok in stmt_tokens if tok["type"] not in ("WHITESPACE", "COMMENT")]
                
                # Locate SET keyword
                set_tok = None
                for tok in active_tokens:
                    if tok["type"] == "KEYWORD" and tok["value"].upper() == "SET":
                        set_tok = tok
                        break
                        
                if not set_tok:
                    i = semi_idx + 1
                    continue
                    
                # Locate WHERE or RETURNING keyword
                where_tok = None
                for tok in active_tokens:
                    if tok["type"] == "KEYWORD" and tok["value"].upper() in ("WHERE", "RETURNING"):
                        where_tok = tok
                        break
                        
                # Split fields list on commas at parenthesis level 0
                fields_start = set_tok["end"]
                fields_end = where_tok["start"] if where_tok else tokens[semi_idx]["start"]
                
                # Find tokens in the fields zone
                fields_tokens = []
                for tok in stmt_tokens:
                    if tok["start"] >= fields_start and tok["end"] <= fields_end:
                        fields_tokens.append(tok)
                        
                # Split fields by commas
                fields = []
                paren_level = 0
                
                if fields_tokens:
                    for tok in fields_tokens:
                        if tok["type"] == "PAREN" and tok["value"] == "(":
                            paren_level += 1
                        elif tok["type"] == "PAREN" and tok["value"] == ")":
                            paren_level = max(0, paren_level - 1)
                            
                        if paren_level == 0 and tok["type"] == "COMMA":
                            f_str = content[fields_start:tok["start"]].strip()
                            fields_start = tok["end"]
                            if f_str:
                                fields.append(f_str)
                        elif tok == fields_tokens[-1]:
                            f_str = content[fields_start:fields_end].strip()
                            if f_str:
                                fields.append(f_str)
                else:
                    f_str = content[fields_start:fields_end].strip()
                    if f_str:
                        fields.append(f_str)
                            
                if not fields:
                    i = semi_idx + 1
                    continue
                    
                c1_str = content[t["start"] : set_tok["start"]].strip()
                c4_str = content[where_tok["start"] : tokens[semi_idx]["end"]].strip() if where_tok else ";"
                
                # Base indentation
                line_start = content.rfind("\n", 0, t["start"]) + 1
                line_prefix = content[line_start:t["start"]]
                base_indent = ""
                for char in line_prefix:
                    if char in (" ", "\t"):
                        base_indent += char
                    else:
                        break
                        
                # Check if it fits on a single line
                single_line = c1_str + " SET " + ", ".join(fields) + (" " + c4_str if where_tok else ";")
                if len(base_indent + single_line) <= max_len:
                    expected = single_line
                else:
                    if len(fields) > 1:
                        expected = (
                            c1_str + "\n" +
                            base_indent + "SET\n" +
                            "\n".join(base_indent + "    " + f + "," for f in fields[:-1]) + "\n" +
                            base_indent + "    " + fields[-1] + "\n" +
                            base_indent + c4_str
                        )
                    else:
                        expected = (
                            c1_str + "\n" +
                            base_indent + "SET " + fields[0] + "\n" +
                            base_indent + c4_str
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
                    message="Long UPDATE statement should be split onto multiple lines.",
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
