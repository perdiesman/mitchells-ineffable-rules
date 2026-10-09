from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class ClauseAlignmentRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-clause-alignment"
    description = "Main query clause keywords (SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT) must have the exact same indentation within the same query block when the query spans multiple lines."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT id, name FROM users\nWHERE active = true;",
            "correct": "SELECT id, name\nFROM users\nWHERE active = true;"
        },
        {
            "violating": "SELECT id\nFROM users\nWHERE id IN (\n    SELECT user_id\n      FROM roles\n    WHERE role_name = 'admin'\n);",
            "correct": "SELECT id\nFROM users\nWHERE id IN (\n    SELECT user_id\n    FROM roles\n    WHERE role_name = 'admin'\n);"
        }
    ]
    additional_validations = [
        "SELECT id, name FROM users WHERE active = true;",
        "SELECT item_id\nFROM sample_item\nWHERE parent_id IS NOT DISTINCT FROM :parent_id;",
    ]

    def _parse_clauses(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        paren_stack: List[int] = []
        statement_number = 0
        clauses = []
        active_indices: List[int] = []

        for index, token in enumerate(tokens):
            if token["type"] in ("WHITESPACE", "COMMENT"):
                continue
            if token["type"] == "PAREN":
                if token["value"] == "(":
                    paren_stack.append(index)
                elif paren_stack:
                    paren_stack.pop()
                active_indices.append(index)
                continue
            if token["type"] == "SEMI" and not paren_stack:
                statement_number += 1
                active_indices.append(index)
                continue
            if token["type"] != "KEYWORD":
                active_indices.append(index)
                continue

            word = token["value"].upper()
            keyword = None
            keyword_end = token["end"]
            if word == "FROM":
                previous_words = [
                    tokens[active_index]["value"].upper()
                    for active_index in active_indices[-3:]
                ]
                if (
                    previous_words[-1:] == ["DELETE"]
                    or previous_words[-2:] == ["IS", "DISTINCT"]
                    or previous_words[-3:] == ["IS", "NOT", "DISTINCT"]
                ):
                    active_indices.append(index)
                    continue
                keyword = word
            elif word in ("SELECT", "WHERE", "HAVING", "LIMIT"):
                keyword = word
            elif word in ("GROUP", "ORDER"):
                next_index = index + 1
                while next_index < len(tokens) and tokens[next_index]["type"] in (
                    "WHITESPACE", "COMMENT"
                ):
                    next_index += 1
                if (
                    next_index < len(tokens)
                    and tokens[next_index]["type"] == "KEYWORD"
                    and tokens[next_index]["value"].upper() == "BY"
                ):
                    keyword = f"{word} BY"
                    keyword_end = tokens[next_index]["end"]

            if keyword:
                line_start_idx = content.rfind("\n", 0, token["start"]) + 1
                line_text = content[line_start_idx : token["start"]]
                is_first_on_line = line_text.strip() == ""
                indentation = line_text if is_first_on_line else ""
                space_start = token["start"]
                if not is_first_on_line:
                    while (
                        space_start > line_start_idx
                        and content[space_start - 1].isspace()
                    ):
                        space_start -= 1
                clauses.append({
                    "keyword": keyword,
                    "line_number": content.count("\n", 0, token["start"]) + 1,
                    "line_start_idx": line_start_idx,
                    "keyword_start": token["start"],
                    "keyword_end": keyword_end,
                    "space_start": space_start,
                    "indentation": indentation,
                    "is_first_on_line": is_first_on_line,
                    "scope": (statement_number, *paren_stack),
                })
            active_indices.append(index)

        return clauses

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        clauses = self._parse_clauses(content)
        lines = content.splitlines()
        
        scope_groups = {}
        for cl in clauses:
            scope = cl["scope"]
            if scope not in scope_groups:
                scope_groups[scope] = []
            scope_groups[scope].append(cl)
            
        for scope, group in scope_groups.items():
            if len(group) < 2:
                continue
                
            # Determine if the query spans multiple lines
            line_numbers = [cl["line_number"] for cl in group]
            if max(line_numbers) == min(line_numbers):
                continue
                
            ref_clause = None
            for cl in group:
                if cl["is_first_on_line"]:
                    ref_clause = cl
                    break
            if not ref_clause:
                continue
                
            expected_indent = ref_clause["indentation"]
            
            for cl in group:
                if cl == ref_clause:
                    continue
                if not cl["is_first_on_line"]:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            line_number=cl["line_number"],
                            message=f"Query clause {cl['keyword']} must start on a new line and align with the {ref_clause['keyword']} clause.",
                            offending_lines=[lines[cl["line_number"] - 1] if cl["line_number"] - 1 < len(lines) else ""],
                            is_fixable=True
                        )
                    )
                elif cl["indentation"] != expected_indent:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            line_number=cl["line_number"],
                            message=(
                                f"Query clause {cl['keyword']} must align with the query's "
                                f"{ref_clause['keyword']} clause (expected indentation: "
                                f"{len(expected_indent)} spaces, actual: {len(cl['indentation'])} spaces)."
                            ),
                            offending_lines=[lines[cl["line_number"] - 1] if cl["line_number"] - 1 < len(lines) else ""],
                            is_fixable=True
                        )
                    )
                    
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        clauses = self._parse_clauses(content)
        if not clauses:
            return content
            
        scope_groups = {}
        for cl in clauses:
            scope = cl["scope"]
            if scope not in scope_groups:
                scope_groups[scope] = []
            scope_groups[scope].append(cl)
            
        replacements = []
        for scope, group in scope_groups.items():
            if len(group) < 2:
                continue
                
            line_numbers = [cl["line_number"] for cl in group]
            if max(line_numbers) == min(line_numbers):
                continue
                
            ref_clause = None
            for cl in group:
                if cl["is_first_on_line"]:
                    ref_clause = cl
                    break
            if not ref_clause:
                continue
                
            expected_indent = ref_clause["indentation"]
            
            for cl in group:
                if cl == ref_clause:
                    continue
                if not cl["is_first_on_line"]:
                    replacements.append((
                        cl["space_start"],
                        cl["keyword_start"],
                        "\n" + expected_indent
                    ))
                elif cl["indentation"] != expected_indent:
                    replacements.append((
                        cl["line_start_idx"],
                        cl["line_start_idx"] + len(cl["indentation"]),
                        expected_indent
                    ))
                    
        if not replacements:
            return content
            
        replacements.sort(key=lambda x: x[0], reverse=True)
        
        chars = list(content)
        for start, end, new_text in replacements:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
