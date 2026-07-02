import re
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class ColumnLayoutRule(BaseRule):
    rule_id = "IR-column-layout"
    description = "On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line."
    category = "select/view/materialized view"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "max_length": 120,
        "indent_size": 4
    }
    
    examples = [
        {
            "violating": "SELECT\n    id,\n    name\nFROM users;",
            "correct": "SELECT id, name\nFROM users;"
        },
        {
            "violating": "SELECT first_name, last_name, email, phone_number, mailing_address, date_of_birth, join_date, another_long_column_name, yet_another_one_to_be_sure FROM users;",
            "correct": "SELECT\n    first_name,\n    last_name,\n    email,\n    phone_number,\n    mailing_address,\n    date_of_birth,\n    join_date,\n    another_long_column_name,\n    yet_another_one_to_be_sure FROM users;"
        }
    ]

    def _parse_clauses(self, content: str) -> List[dict]:
        """
        Parses all SELECT, ORDER BY, GROUP BY clauses.
        Returns a list of dicts.
        """
        n = len(content)
        i = 0
        in_string = False
        string_char = None
        in_single_comment = False
        in_multi_comment = False
        paren_level = 0
        line_number = 1
        line_start_idx = 0
        
        clauses = []
        
        while i < n:
            c = content[i]
            
            if c == '\n':
                line_number += 1
                line_start_idx = i + 1
                
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
                if c == '\n':
                    in_single_comment = False
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
                
            # Parenthesis tracking
            if c == '(':
                paren_level += 1
                i += 1
                continue
            if c == ')':
                paren_level = max(0, paren_level - 1)
                i += 1
                continue
                
            # Match keywords at top level
            if paren_level == 0 and (c.isalpha() or c == '_'):
                w_start = i
                w_line = line_number
                while i < n and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[w_start:i]
                
                keyword = None
                keyword_end = i
                word_lower = word.lower()
                
                if word_lower == "select":
                    keyword = "SELECT"
                elif word_lower in ("group", "order"):
                    next_idx = i
                    while next_idx < n and content[next_idx].isspace():
                        next_idx += 1
                    w2_start = next_idx
                    while next_idx < n and (content[next_idx].isalnum() or content[next_idx] == '_'):
                        next_idx += 1
                    word2 = content[w2_start:next_idx]
                    if word2.lower() == "by":
                        keyword = "GROUP BY" if word_lower == "group" else "ORDER BY"
                        keyword_end = next_idx
                        i = next_idx
                        
                if keyword:
                    # Resolve indentation of keyword line
                    line_text = content[line_start_idx:w_start]
                    indentation = ""
                    for char in line_text:
                        if char in (" ", "\t"):
                            indentation += char
                        else:
                            indentation = ""
                            
                    # Parse the list of expressions starting immediately after the keyword
                    list_start = keyword_end
                    expressions = []
                    
                    list_paren = 0
                    list_string = False
                    list_str_char = None
                    list_single_comment = False
                    list_multi_comment = False
                    
                    j = list_start
                    current_expr_start = list_start
                    last_non_space_idx = list_start
                    
                    while j < n:
                        jc = content[j]
                        
                        if list_string:
                            if jc == list_str_char:
                                if j + 1 < n and content[j + 1] == list_str_char:
                                    j += 2
                                    last_non_space_idx = j
                                    continue
                                list_string = False
                            if not jc.isspace():
                                last_non_space_idx = j + 1
                            j += 1
                            continue
                        if list_single_comment:
                            if jc == '\n':
                                list_single_comment = False
                            j += 1
                            continue
                        if list_multi_comment:
                            if jc == '*' and j + 1 < n and content[j + 1] == '/':
                                list_multi_comment = False
                                j += 2
                                last_non_space_idx = j
                                continue
                            j += 1
                            continue
                            
                        if jc in ("'", '"'):
                            list_string = True
                            list_str_char = jc
                            last_non_space_idx = j + 1
                            j += 1
                            continue
                        if jc == '-' and j + 1 < n and content[j + 1] == '-':
                            list_single_comment = True
                            j += 2
                            continue
                        if jc == '/' and j + 1 < n and content[j + 1] == '*':
                            list_multi_comment = True
                            j += 2
                            continue
                            
                        if jc == '(':
                            list_paren += 1
                            last_non_space_idx = j + 1
                            j += 1
                            continue
                        if jc == ')':
                            if list_paren == 0:
                                break
                            list_paren -= 1
                            last_non_space_idx = j + 1
                            j += 1
                            continue
                            
                        if list_paren == 0 and (jc.isalpha() or jc == '_'):
                            jw_start = j
                            while j < n and (content[j].isalnum() or content[j] == '_'):
                                j += 1
                            j_word = content[jw_start:j].lower()
                            
                            if keyword.startswith("SELECT"):
                                boundaries = {"from", "where", "group", "order", "limit", "offset", "union", "intersect", "except"}
                            else:
                                boundaries = {"limit", "offset", "union", "intersect", "except"}
                                
                            if j_word in boundaries:
                                j = jw_start
                                break
                            
                            last_non_space_idx = j
                            continue
                            
                        if list_paren == 0 and jc == ';':
                            break
                            
                        if list_paren == 0 and jc == ',':
                            expr = content[current_expr_start:j].strip()
                            expr = re.sub(r"\s+", " ", expr)
                            if expr:
                                expressions.append(expr)
                            last_non_space_idx = j + 1
                            j += 1
                            current_expr_start = j
                            continue
                            
                        if not jc.isspace():
                            last_non_space_idx = j + 1
                        j += 1
                        
                    expr = content[current_expr_start:j].strip()
                    expr = re.sub(r"\s+", " ", expr)
                    if expr:
                        if keyword == "SELECT":
                            match_distinct = re.match(r"^(distinct|all)\b\s*(.*)$", expr, re.IGNORECASE)
                            if match_distinct:
                                keyword = f"SELECT {match_distinct.group(1).upper()}"
                                expr = match_distinct.group(2).strip()
                                
                        if expr:
                            expressions.append(expr)
                            
                    list_end = last_non_space_idx
                    
                    # Prevent formatting if there is an inline comment inside the clause text
                    clause_text = content[w_start:list_end]
                    if "--" in clause_text or "/*" in clause_text:
                        i = list_end
                        continue
                        
                    clauses.append({
                        "keyword": keyword,
                        "keyword_start": w_start,
                        "keyword_end": keyword_end,
                        "list_start": list_start,
                        "list_end": list_end,
                        "expressions": expressions,
                        "line_number": w_line,
                        "indentation": indentation
                    })
                    i = list_end
                    continue
                    
            i += 1
            
        return clauses

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        indent_size = rule_config.get("indent_size", self.default_config["indent_size"])
        violations = []
        
        clauses = self._parse_clauses(content)
        lines = content.splitlines()
        
        for cl in clauses:
            keyword = cl["keyword"]
            expressions = cl["expressions"]
            indentation = cl["indentation"]
            
            if not expressions:
                continue
                
            # 1. Determine if it fits on a single line
            single_line_clause = f"{keyword} {', '.join(expressions)}"
            total_len = len(indentation) + len(single_line_clause)
            
            current_clause_text = content[cl["keyword_start"]:cl["list_end"]]
            
            if total_len <= max_length:
                # Expect single-line format
                expected = single_line_clause
                if current_clause_text != expected:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            line_number=cl["line_number"],
                            message=f"Columns fit on a single line. Expected single-line layout for {keyword} clause.",
                            offending_lines=[lines[cl["line_number"] - 1] if cl["line_number"] - 1 < len(lines) else ""],
                            is_fixable=True
                        )
                    )
            else:
                # Expect multi-line format
                inner_indent = indentation + (" " * indent_size)
                expected = f"{keyword}\n" + ",\n".join(f"{inner_indent}{expr}" for expr in expressions)
                
                # Normalize line endings for comparison
                current_normalized = current_clause_text.replace("\r\n", "\n")
                expected_normalized = expected.replace("\r\n", "\n")
                
                if current_normalized != expected_normalized:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            line_number=cl["line_number"],
                            message=f"Columns exceed max line length. Expected multi-line (one per line) layout for {keyword} clause.",
                            offending_lines=[lines[cl["line_number"] - 1] if cl["line_number"] - 1 < len(lines) else ""],
                            is_fixable=True
                        )
                    )
                    
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_length = rule_config.get("max_length", self.default_config["max_length"])
        indent_size = rule_config.get("indent_size", self.default_config["indent_size"])
        
        clauses = self._parse_clauses(content)
        if not clauses:
            return content
            
        fixed_chunks = []
        last_idx = 0
        
        ending = "\r\n" if "\r\n" in content else "\n"
        
        for cl in clauses:
            keyword = cl["keyword"]
            expressions = cl["expressions"]
            indentation = cl["indentation"]
            
            if not expressions:
                continue
                
            single_line_clause = f"{keyword} {', '.join(expressions)}"
            total_len = len(indentation) + len(single_line_clause)
            
            if total_len <= max_length:
                formatted = single_line_clause
            else:
                inner_indent = indentation + (" " * indent_size)
                formatted = f"{keyword}{ending}" + f",{ending}".join(f"{inner_indent}{expr}" for expr in expressions)
                
            fixed_chunks.append(content[last_idx:cl["keyword_start"]])
            fixed_chunks.append(formatted)
            last_idx = cl["list_end"]
            
        fixed_chunks.append(content[last_idx:])
        return "".join(fixed_chunks)
