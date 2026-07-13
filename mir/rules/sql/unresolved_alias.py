from typing import List, Dict, Any, Set
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren

class UnresolvedAliasRule(BaseRule):
    rule_id = "IR-unresolved-alias"
    description = "Detect references to table aliases or qualifiers that are not declared in the query context."
    category = "general"
    is_fixable = "no"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT z.id FROM outage_data.zipcode;\n-- z is not declared",
            "correct": "SELECT z.id FROM outage_data.zipcode z;"
        }
    ]
    additional_validations = [
        "SELECT c.id FROM outage_data.county c;",
        "SELECT NEW.id;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        n = len(tokens)
        
        # 1. Collect valid qualifiers
        valid = {
            "pg_catalog", "information_schema", "public", "outage_data", "utility", "dashboard", "community",
            "new", "old", "tg_op"
        }
        
        # Parse DECLARE block variables
        in_declare = False
        for i, t in enumerate(tokens):
            val_upper = t["value"].upper()
            if val_upper == "DECLARE":
                in_declare = True
                continue
            if val_upper == "BEGIN":
                in_declare = False
                break
            if in_declare and t["type"] == "IDENTIFIER":
                valid.add(t["value"].lower())
                
        # Parse CTE names after WITH
        for i, t in enumerate(tokens):
            if t["type"] == "KEYWORD" and t["value"].upper() == "WITH":
                idx = i + 1
                while idx < n:
                    if tokens[idx]["type"] == "IDENTIFIER":
                        cte_name = tokens[idx]["value"].lower()
                        next_active = None
                        for k in range(idx + 1, n):
                            if tokens[k]["type"] not in ("WHITESPACE", "COMMENT"):
                                next_active = tokens[k]
                                break
                        if next_active and next_active["value"].upper() == "AS":
                            valid.add(cte_name)
                    if tokens[idx]["type"] == "KEYWORD" and tokens[idx]["value"].upper() in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                        break
                    idx += 1
                    
        # Parse FROM, JOIN, UPDATE, INTO, VIEW, TABLE, EXISTS, TRUNCATE, SEQUENCE, INDEX clauses
        for i, t in enumerate(tokens):
            if t["type"] == "KEYWORD" and t["value"].upper() in ("FROM", "JOIN", "UPDATE", "INTO", "VIEW", "TABLE", "EXISTS", "TRUNCATE", "SEQUENCE", "INDEX"):
                idx = i + 1
                while idx < n and tokens[idx]["type"] in ("WHITESPACE", "COMMENT"):
                    idx += 1
                    
                paren_idx = None
                path_tokens = []
                
                # Check if it starts with (
                if idx < n and tokens[idx]["type"] == "PAREN" and tokens[idx]["value"] == "(":
                    paren_idx = idx
                else:
                    # Collect path tokens
                    while idx < n and tokens[idx]["type"] in ("IDENTIFIER", "DOT"):
                        path_tokens.append(tokens[idx])
                        idx += 1
                    # Skip whitespace
                    while idx < n and tokens[idx]["type"] in ("WHITESPACE", "COMMENT"):
                        idx += 1
                    # If followed by ( it is a function call!
                    if idx < n and tokens[idx]["type"] == "PAREN" and tokens[idx]["value"] == "(":
                        paren_idx = idx
                        
                if paren_idx is not None:
                    # Find matching paren
                    close_p = find_matching_paren(tokens, paren_idx)
                    if close_p is not None:
                        idx = close_p + 1
                        
                # Now idx is pointing after the table reference / parenthesis
                while idx < n and tokens[idx]["type"] in ("WHITESPACE", "COMMENT"):
                    idx += 1
                    
                if idx < n and tokens[idx]["value"].upper() == "AS":
                    idx += 1
                    while idx < n and tokens[idx]["type"] in ("WHITESPACE", "COMMENT"):
                        idx += 1
                        
                if idx < n and tokens[idx]["type"] in ("IDENTIFIER", "KEYWORD"):
                    if tokens[idx]["value"].upper() not in ("ON", "USING", "WHERE", "JOIN", "GROUP", "ORDER", "LIMIT", "UNION", "SET"):
                        valid.add(tokens[idx]["value"].lower())
                        
                # Also collect table names from path_tokens
                if path_tokens:
                    ids = [pt for pt in path_tokens if pt["type"] == "IDENTIFIER"]
                    if ids:
                        # If it's a qualified name like schema.table, add the schema parts to valid
                        for schema_id in ids[:-1]:
                            valid.add(schema_id["value"].lower())
                        last_table_id = ids[-1]["value"].lower()
                        valid.add(last_table_id)
                    full_path = "".join(pt["value"].lower() for pt in path_tokens)
                    valid.add(full_path)
                                
        violations = []
        
        # 2. Check qualified identifiers
        for i in range(n - 2):
            if tokens[i]["type"] == "IDENTIFIER" and tokens[i+1]["value"] == "." and tokens[i+2]["type"] in ("IDENTIFIER", "KEYWORD"):
                # Check if it is a function call
                next_active = None
                for k in range(i + 3, n):
                    if tokens[k]["type"] not in ("WHITESPACE", "COMMENT"):
                        next_active = tokens[k]
                        break
                if next_active and next_active["type"] == "PAREN" and next_active["value"] == "(":
                    continue
                    
                # Skip if part of a table name in FROM/JOIN (handled by skip rules)
                is_declaration = False
                prev_active = None
                for k in range(i - 1, -1, -1):
                    if tokens[k]["type"] not in ("WHITESPACE", "COMMENT"):
                        prev_active = tokens[k]
                        break
                if prev_active and prev_active["type"] == "KEYWORD" and prev_active["value"].upper() in ("FROM", "JOIN", "TABLE", "VIEW", "EXISTS", "INTO", "UPDATE", "TRUNCATE", "SEQUENCE", "INDEX"):
                    is_declaration = True
                    
                if is_declaration:
                    continue
                    
                qualifier = tokens[i]["value"].lower()
                if qualifier not in valid:
                    violations.append({
                        "token": tokens[i],
                        "qualifier": tokens[i]["value"],
                        "line": tokens[i]["line"]
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
                    message=f"Unresolved qualifier/alias '{item['qualifier']}' referenced.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=False
                )
            )
        return violations
