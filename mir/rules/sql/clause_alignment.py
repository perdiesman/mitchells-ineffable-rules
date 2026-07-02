from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class ClauseAlignmentRule(BaseRule):
    rule_id = "IR-clause-alignment"
    description = "Main query clause keywords (SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT) must have the exact same indentation within the same query block when the query spans multiple lines."
    category = "select/view/materialized view"
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
        "SELECT id, name FROM users WHERE active = true;"
    ]

    def _parse_clauses(self, content: str) -> List[dict]:
        n = len(content)
        i = 0
        in_string = False
        string_char = None
        in_single_comment = False
        in_multi_comment = False
        paren_stack = []
        line_number = 1
        line_start_idx = 0
        
        clauses = []
        
        while i < n:
            c = content[i]
            
            if c == '\n':
                line_number += 1
                line_start_idx = i + 1
                i += 1
                continue
                
            # String / comment states
            if in_string:
                if c == string_char:
                    if i + 1 < n and content[i + 1] == string_char:
                        i += 2
                        continue
                    in_string = False
                i += 1
                continue
                
            if in_single_comment:
                i += 1
                continue
                
            if in_multi_comment:
                if c == '*' and i + 1 < n and content[i + 1] == '/':
                    in_multi_comment = False
                    i += 2
                    continue
                i += 1
                continue
                
            if c in ("'", '"'):
                in_string = True
                string_char = c
                i += 1
                continue
                
            if c == '-' and i + 1 < n and content[i + 1] == '-':
                in_single_comment = True
                i += 2
                continue
                
            if c == '/' and i + 1 < n and content[i + 1] == '*':
                in_multi_comment = True
                i += 2
                continue
                
            # Whitespace handling
            if c.isspace():
                i += 1
                continue
                
            # Parenthesis tracking
            if c == '(':
                paren_stack.append(i)
                i += 1
                continue
            if c == ')':
                if paren_stack:
                    paren_stack.pop()
                i += 1
                continue
                
            # Match keywords
            if c.isalpha() or c == '_':
                w_start = i
                while i < n and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[w_start:i]
                word_lower = word.lower()
                
                keyword = None
                keyword_end = i
                
                if word_lower in ("select", "from", "where", "having", "limit"):
                    keyword = word_lower.upper()
                elif word_lower in ("group", "order"):
                    next_idx = i
                    while next_idx < n and content[next_idx].isspace():
                        next_idx += 1
                    w2_start = next_idx
                    while next_idx < n and (content[next_idx].isalnum() or content[next_idx] == '_'):
                        next_idx += 1
                    word2 = content[w2_start:next_idx]
                    if word2.lower() == "by":
                        keyword = f"{word_lower.upper()} BY"
                        keyword_end = next_idx
                        i = next_idx
                
                if keyword:
                    # Check if it is the first token on its line
                    line_text = content[line_start_idx:w_start]
                    is_first_on_line = (line_text.strip() == "")
                    
                    if is_first_on_line:
                        indentation = line_text
                        space_start = w_start
                    else:
                        indentation = ""
                        # Find preceding whitespace index range to replace if we need to put it on a new line
                        space_start = w_start
                        while space_start > line_start_idx and content[space_start - 1].isspace():
                            space_start -= 1
                            
                    clauses.append({
                        "keyword": keyword,
                        "line_number": line_number,
                        "line_start_idx": line_start_idx,
                        "keyword_start": w_start,
                        "keyword_end": keyword_end,
                        "space_start": space_start,
                        "indentation": indentation,
                        "is_first_on_line": is_first_on_line,
                        "scope": tuple(paren_stack)
                    })
                continue
                
            i += 1
            
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
                
            first_clause = group[0]
            expected_indent = first_clause["indentation"]
            
            for cl in group[1:]:
                if not cl["is_first_on_line"]:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            line_number=cl["line_number"],
                            message=f"Query clause {cl['keyword']} must start on a new line and align with the {first_clause['keyword']} clause.",
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
                                f"{first_clause['keyword']} clause (expected indentation: "
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
                
            first_clause = group[0]
            expected_indent = first_clause["indentation"]
            
            for cl in group[1:]:
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
