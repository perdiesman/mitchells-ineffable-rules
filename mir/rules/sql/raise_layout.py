from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class RaiseLayoutRule(BaseRule):
    rule_id = "IR-raise-layout"
    description = "Format and wrap long RAISE statements onto multiple lines."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "max_length": 120
    }
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length before wrapping RAISE statements."
        }
    }
    
    examples = [
        {
            "violating": "RAISE unique_violation USING MESSAGE = 'id: ' || NEW.id::text || ' already exists in outage_data.coverage_geometry_bypass_table_and_other_fields';",
            "correct": "RAISE unique_violation\n    USING MESSAGE = 'id: '\n        || NEW.id::text\n        || ' already exists in outage_data.coverage_geometry_bypass_table_and_other_fields';"
        }
    ]
    additional_validations = [
        "RAISE NOTICE 'short';"
    ]

    def _find_violations(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_len = self.get_config_value(rule_config, "max_length", 120)
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        i = 0
        while i < n:
            t = tokens[i]
            if t["value"].upper() == "RAISE":
                # Find ending semicolon
                semi_idx = None
                for idx in range(i + 1, n):
                    if tokens[idx]["value"].upper() in ("CREATE", "ALTER", "DROP", "UPDATE", "INSERT", "DELETE", "BEGIN", "DECLARE", "IF"):
                        break
                    if tokens[idx]["type"] == "SEMI":
                        semi_idx = idx
                        break
                        
                if semi_idx is None:
                    i += 1
                    continue
                    
                stmt_tokens = tokens[i : semi_idx + 1]
                active_tokens = [tok for tok in stmt_tokens if tok["type"] not in ("WHITESPACE", "COMMENT")]
                
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
                original_stmt = content[t["start"] : tokens[semi_idx]["end"]].strip()
                if len(base_indent + original_stmt) <= max_len:
                    i = semi_idx + 1
                    continue
                    
                # Locate USING keyword
                using_tok = None
                for tok in active_tokens:
                    if tok["value"].upper() == "USING":
                        using_tok = tok
                        break
                        
                if not using_tok:
                    i = semi_idx + 1
                    continue
                    
                # We have USING. First part is RAISE <exception>
                first_part = content[t["start"] : using_tok["start"]].strip()
                
                # Check if there is MESSAGE =
                using_content = content[using_tok["start"] : tokens[semi_idx]["end"]].strip()
                
                # Let's locate '=' after USING and MESSAGE
                eq_tok = None
                for idx, tok in enumerate(active_tokens):
                    if tok == using_tok:
                        # Scan next tokens for MESSAGE and =
                        for sub_idx in range(idx + 1, len(active_tokens)):
                            sub_tok = active_tokens[sub_idx]
                            if sub_tok["type"] == "OPERATOR" and sub_tok["value"] == "=":
                                eq_tok = sub_tok
                                break
                        break
                        
                if not eq_tok:
                    # If no =, just wrap on USING
                    expected = first_part + "\n" + base_indent + "    " + using_content
                else:
                    using_prefix = content[using_tok["start"] : eq_tok["end"]].strip()
                    expr_str = content[eq_tok["end"] : tokens[semi_idx]["start"]].strip()
                    
                    # Split expr_str by || at paren level 0
                    expr_tokens = []
                    for tok in stmt_tokens:
                        if tok["start"] >= eq_tok["end"] and tok["end"] <= tokens[semi_idx]["start"]:
                            expr_tokens.append(tok)
                            
                    parts = []
                    current_part_start = eq_tok["end"]
                    paren_level = 0
                    
                    if expr_tokens:
                        for tok in expr_tokens:
                            if tok["type"] == "PAREN" and tok["value"] == "(":
                                paren_level += 1
                            elif tok["type"] == "PAREN" and tok["value"] == ")":
                                paren_level = max(0, paren_level - 1)
                                
                            if paren_level == 0 and tok["type"] == "OPERATOR" and tok["value"] == "||":
                                part = content[current_part_start : tok["start"]].strip()
                                parts.append(part)
                                current_part_start = tok["end"]
                            elif tok == expr_tokens[-1]:
                                part = content[current_part_start : tokens[semi_idx]["start"]].strip()
                                parts.append(part)
                    else:
                        part = content[current_part_start : tokens[semi_idx]["start"]].strip()
                        if part:
                            parts.append(part)
                            
                    # Filter empty parts
                    parts = [p for p in parts if p]
                    
                    if len(parts) > 1:
                        # Format with split ||
                        expected = (
                            first_part + "\n" +
                            base_indent + "    " + using_prefix + " " + parts[0] + "\n" +
                            "\n".join(base_indent + "        || " + p for p in parts[1:]) + ";"
                        )
                    else:
                        expected = (
                            first_part + "\n" +
                            base_indent + "    " + using_content
                        )
                        
                if original_stmt != expected:
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
                    message="Long RAISE statement should be split onto multiple lines.",
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
