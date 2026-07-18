from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren

class BooleanDefaultRule(BaseRule):
    rule_id = "IR-boolean-default"
    description = "Enforce that boolean columns in table definitions explicitly define a DEFAULT constraint."
    category = "schema-definition"
    is_fixable = "no"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "CREATE TABLE users (\n    is_active BOOLEAN\n);",
            "correct": "CREATE TABLE users (\n    is_active BOOLEAN DEFAULT false\n);"
        }
    ]
    additional_validations = [
        "CREATE TABLE users (is_active BOOLEAN DEFAULT true);",
        "CREATE TABLE users (id INTEGER, is_active BOOL NOT NULL DEFAULT false);"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)

        # Build map of token ID to index in tokens
        token_to_idx = {id(t): idx for idx, t in enumerate(tokens)}

        # Filter active tokens
        active = []
        for t in tokens:
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)

        num_active = len(active)
        i = 0
        while i < num_active:
            t = active[i]
            if t["type"] == "KEYWORD" and t["value"].upper() == "CREATE":
                # Check for TABLE
                is_table = False
                tbl_idx = i + 1
                if tbl_idx < num_active and active[tbl_idx]["value"].upper() in ("TEMP", "TEMPORARY"):
                    tbl_idx += 1
                if tbl_idx < num_active and active[tbl_idx]["value"].upper() == "TABLE":
                    is_table = True
                
                if is_table:
                    # Find open parenthesis of column list
                    open_paren_idx = None
                    for k in range(tbl_idx + 1, num_active):
                        if active[k]["type"] == "PAREN" and active[k]["value"] == "(":
                            open_paren_idx = token_to_idx[id(active[k])]
                            break
                    
                    if open_paren_idx is not None:
                        close_paren_idx = find_matching_paren(tokens, open_paren_idx)
                        if close_paren_idx is not None:
                            # Collect active tokens inside table definition
                            inside_active = []
                            for k in range(tbl_idx + 1, num_active):
                                t_k = active[k]
                                t_k_idx = token_to_idx[id(t_k)]
                                if t_k_idx > open_paren_idx and t_k_idx < close_paren_idx:
                                    inside_active.append(t_k)
                            
                            # Split by commas at depth 0
                            elements = []
                            current = []
                            depth = 0
                            for ta in inside_active:
                                if ta["type"] == "PAREN" and ta["value"] == "(":
                                    depth += 1
                                elif ta["type"] == "PAREN" and ta["value"] == ")":
                                    depth -= 1
                                
                                if ta["value"] == "," and depth == 0:
                                    elements.append(current)
                                    current = []
                                else:
                                    current.append(ta)
                            if current or len(elements) > 0:
                                elements.append(current)
                            
                            # Check each element (column definition)
                            for element in elements:
                                if not element:
                                    continue
                                
                                # Skip table constraints
                                first_val_upper = element[0]["value"].upper()
                                if first_val_upper in ("CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK"):
                                    continue
                                
                                # Check if this is a boolean column
                                is_boolean = False
                                bool_token = None
                                for el_tok in element:
                                    if el_tok["type"] in ("IDENTIFIER", "KEYWORD") and el_tok["value"].upper() in ("BOOLEAN", "BOOL"):
                                        is_boolean = True
                                        bool_token = el_tok
                                        break
                                
                                if is_boolean:
                                    # Check for DEFAULT constraint
                                    has_default = False
                                    for el_tok in element:
                                        if el_tok["value"].upper() == "DEFAULT":
                                            has_default = True
                                            break
                                    
                                    if not has_default:
                                        violations.append({
                                            "token": element[0],
                                            "line": element[0]["line"],
                                            "message": f"Boolean column '{element[0]['value']}' on line {element[0]['line']} is missing an explicit DEFAULT constraint."
                                        })
            i += 1

        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        for v in offending:
            line_idx = v["line"] - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=v["line"],
                message=v["message"],
                offending_lines=[offending_line],
                is_fixable=False
            ))
        return violations
