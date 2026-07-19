import re
from typing import List, Dict, Optional
from functools import lru_cache

SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "NATURAL", "ON", "USING",
    "UNION", "INTERSECT", "EXCEPT", "AND", "OR", "NOT", "IN", "EXISTS", "IS", "NULL",
    "AS", "CREATE", "VIEW", "MATERIALIZED", "TABLE", "INSERT", "INTO", "VALUES", "UPDATE",
    "SET", "DELETE", "WITH", "CASE", "WHEN", "THEN", "ELSE", "END", "COALESCE",
    "RECURSIVE", "ASC", "DESC", "DISTINCT"
}

OPERATORS = {
    "=", "<>", "<=", ">=", "!=", "<", ">", "+", "-", "*", "/", "%", "||", "~*"
}

@lru_cache(maxsize=1024)
def _tokenize_sql_impl(content: str) -> List[dict]:
    n = len(content)
    i = 0
    tokens = []
    line_number = 1
    
    while i < n:
        c = content[i]
        
        # Whitespace
        if c.isspace():
            start = i
            while i < n and content[i].isspace():
                if content[i] == '\n':
                    line_number += 1
                i += 1
            tokens.append({
                "type": "WHITESPACE",
                "value": content[start:i],
                "start": start,
                "end": i,
                "line": line_number
            })
            continue
            
        # Single-line comment
        if c == '-' and i + 1 < n and content[i + 1] == '-':
            start = i
            i += 2
            while i < n and content[i] != '\n':
                i += 1
            tokens.append({
                "type": "COMMENT",
                "value": content[start:i],
                "start": start,
                "end": i,
                "line": line_number
            })
            continue
            
        # Multi-line comment
        if c == '/' and i + 1 < n and content[i + 1] == '*':
            start = i
            i += 2
            while i < n:
                if content[i] == '\n':
                    line_number += 1
                if content[i] == '*' and i + 1 < n and content[i + 1] == '/':
                    i += 2
                    break
                i += 1
            tokens.append({
                "type": "COMMENT",
                "value": content[start:i],
                "start": start,
                "end": i,
                "line": line_number
            })
            continue
            
        # Single-quoted string
        if c == "'":
            start = i
            i += 1
            while i < n:
                if content[i] == '\n':
                    line_number += 1
                if content[i] == "'":
                    if i + 1 < n and content[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            tokens.append({
                "type": "STRING",
                "value": content[start:i],
                "start": start,
                "end": i,
                "line": line_number
            })
            continue
            
        # Double-quoted identifier
        if c == '"':
            start = i
            i += 1
            while i < n:
                if content[i] == '\n':
                    line_number += 1
                if content[i] == '"':
                    if i + 1 < n and content[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            tokens.append({
                "type": "IDENTIFIER",
                "value": content[start:i],
                "start": start,
                "end": i,
                "line": line_number
            })
            continue
            
        # Dollar-quoted string
        if c == '$':
            match = re.match(r'^\$[a-zA-Z0-9_]*\$', content[i:])
            if match:
                tag = match.group(0)
                start = i
                i += len(tag)
                while i < n:
                    if content[i] == '\n':
                        line_number += 1
                    if content[i] == '$' and content[i:i + len(tag)] == tag:
                        i += len(tag)
                        break
                    i += 1
                tokens.append({
                    "type": "STRING",
                    "value": content[start:i],
                    "start": start,
                    "end": i,
                    "line": line_number
                })
                continue
                
        # Cast operator ::
        if c == ':' and i + 1 < n and content[i + 1] == ':':
            tokens.append({
                "type": "CAST",
                "value": "::",
                "start": i,
                "end": i + 2,
                "line": line_number
            })
            i += 2
            continue
            
        # Paren
        if c in ('(', ')'):
            tokens.append({
                "type": "PAREN",
                "value": c,
                "start": i,
                "end": i + 1,
                "line": line_number
            })
            i += 1
            continue
            
        # Comma
        if c == ',':
            tokens.append({
                "type": "COMMA",
                "value": ",",
                "start": i,
                "end": i + 1,
                "line": line_number
            })
            i += 1
            continue
            
        # Semicolon
        if c == ';':
            tokens.append({
                "type": "SEMI",
                "value": ";",
                "start": i,
                "end": i + 1,
                "line": line_number
            })
            i += 1
            continue
            
        # Dot
        if c == '.':
            tokens.append({
                "type": "DOT",
                "value": ".",
                "start": i,
                "end": i + 1,
                "line": line_number
            })
            i += 1
            continue
            
        # Check operators
        matched_op = None
        for op in sorted(OPERATORS, key=len, reverse=True):
            if content[i:i + len(op)] == op:
                matched_op = op
                break
        if matched_op:
            tokens.append({
                "type": "OPERATOR",
                "value": matched_op,
                "start": i,
                "end": i + len(matched_op),
                "line": line_number
            })
            i += len(matched_op)
            continue
            
        # Numbers
        if c.isdigit():
            start = i
            while i < n and (content[i].isdigit() or content[i] == '.' or content[i].lower() in ('e', 'x', 'a', 'b', 'c', 'd', 'e', 'f', 'p')):
                i += 1
            tokens.append({
                "type": "NUMBER",
                "value": content[start:i],
                "start": start,
                "end": i,
                "line": line_number
            })
            continue
            
        # Bare words (Keywords and identifiers)
        if c.isalpha() or c == '_':
            start = i
            while i < n and (content[i].isalnum() or content[i] == '_'):
                i += 1
            value = content[start:i]
            upper_val = value.upper()
            if upper_val in SQL_KEYWORDS:
                tokens.append({
                    "type": "KEYWORD",
                    "value": value,
                    "start": start,
                    "end": i,
                    "line": line_number
                })
            else:
                tokens.append({
                    "type": "IDENTIFIER",
                    "value": value,
                    "start": start,
                    "end": i,
                    "line": line_number
                })
            continue
            
        # Fallback single char
        tokens.append({
            "type": "OTHER",
            "value": c,
            "start": i,
            "end": i + 1,
            "line": line_number
        })
        i += 1
        
    return tokens

def find_matching_paren(tokens: List[dict], open_idx: int) -> Optional[int]:
    if tokens[open_idx]["type"] != "PAREN" or tokens[open_idx]["value"] != "(":
        return None
    depth = 0
    for idx in range(open_idx, len(tokens)):
        tok = tokens[idx]
        if tok["type"] == "PAREN":
            if tok["value"] == "(":
                depth += 1
            elif tok["value"] == ")":
                depth -= 1
                if depth == 0:
                    return idx
    return None

def get_token_depths(tokens: List[dict]) -> List[int]:
    depths = []
    current_depth = 0
    for tok in tokens:
        if tok["type"] == "PAREN" and tok["value"] == ")":
            current_depth -= 1
        depths.append(current_depth)
        if tok["type"] == "PAREN" and tok["value"] == "(":
            current_depth += 1
    return depths

def find_clause_end(tokens: List[dict], depths: List[int], start_idx: int, clause_keywords: List[str]) -> int:
    n = len(tokens)
    outer_depth = depths[start_idx]
    paren_depth = 0
    
    for idx in range(start_idx + 1, n):
        t = tokens[idx]
        d = depths[idx]
        if t["type"] == "PAREN":
            if t["value"] == "(":
                paren_depth += 1
            elif t["value"] == ")":
                paren_depth -= 1
                if paren_depth < 0:
                    return idx
        elif paren_depth == 0 and d == outer_depth:
            if t["type"] == "KEYWORD" and t["value"].upper() in clause_keywords:
                return idx
            if t["type"] == "SEMI":
                return idx
    return n


def find_datatype_token_groups(tokens: List[dict], content: str) -> List[List[dict]]:
    # Returns a list of list of tokens representing types: e.g. [[t1, t2], [t3]]
    active_tokens = [t for t in tokens if t["type"] not in ("WHITESPACE", "COMMENT")]
    token_to_active_idx = {id(t): idx for idx, t in enumerate(active_tokens)}
    
    type_groups = []
    n_active = len(active_tokens)
    
    # Helper to parse type starting at active index
    def try_parse_type_at(start_idx):
        if start_idx >= n_active:
            return None
            
        # Match multi-word types first
        multi_words = [
            ("timestamp", "with", "time", "zone"),
            ("timestamp", "without", "time", "zone"),
            ("time", "with", "time", "zone"),
            ("time", "without", "time", "zone"),
            ("double", "precision"),
            ("character", "varying"),
        ]
        for words in multi_words:
            k = len(words)
            if start_idx + k <= n_active:
                match = True
                for offset, w in enumerate(words):
                    if active_tokens[start_idx + offset]["value"].lower() != w:
                        match = False
                        break
                if match:
                    group = active_tokens[start_idx : start_idx + k]
                    next_idx = start_idx + k
                    if next_idx < n_active and active_tokens[next_idx]["type"] == "PAREN" and active_tokens[next_idx]["value"] == "(":
                        # Consume parenthesis
                        p_level = 0
                        for p_idx in range(next_idx, n_active):
                            t_p = active_tokens[p_idx]
                            if t_p["type"] == "PAREN" and t_p["value"] == "(":
                                p_level += 1
                            elif t_p["type"] == "PAREN" and t_p["value"] == ")":
                                p_level -= 1
                                if p_level == 0:
                                    group.extend(active_tokens[next_idx : p_idx + 1])
                                    break
                    return group
                    
        # Match single-word types
        single_types = {
            "timestamp", "timestamptz", "time", "timetz", "varchar", "integer", "int",
            "bigint", "smallint", "text", "boolean", "bool", "numeric", "decimal",
            "json", "jsonb", "uuid", "date", "geometry", "real", "char", "character"
        }
        first_val = active_tokens[start_idx]["value"].lower()
        if first_val in single_types:
            group = [active_tokens[start_idx]]
            next_idx = start_idx + 1
            if next_idx < n_active and active_tokens[next_idx]["type"] == "PAREN" and active_tokens[next_idx]["value"] == "(":
                # Consume parenthesis
                p_level = 0
                for p_idx in range(next_idx, n_active):
                    t_p = active_tokens[p_idx]
                    if t_p["type"] == "PAREN" and t_p["value"] == "(":
                        p_level += 1
                    elif t_p["type"] == "PAREN" and t_p["value"] == ")":
                        p_level -= 1
                        if p_level == 0:
                            group.extend(active_tokens[next_idx : p_idx + 1])
                            break
            return group
        return None

    # Context 1: Cast ::
    for idx, t in enumerate(active_tokens):
        if t["type"] == "CAST" and t["value"] == "::":
            group = try_parse_type_at(idx + 1)
            if group:
                type_groups.append(group)
                
    # Context 2: CAST(expr AS type)
    for idx, t in enumerate(active_tokens):
        if t["type"] == "KEYWORD" and t["value"].upper() == "CAST":
            # Find AS keyword
            # CAST is followed by '('
            if idx + 1 < n_active and active_tokens[idx + 1]["value"] == "(":
                # Scan until matching ')'
                p_level = 0
                for sub_idx in range(idx + 1, n_active):
                    sub_tok = active_tokens[sub_idx]
                    if sub_tok["type"] == "PAREN" and sub_tok["value"] == "(":
                        p_level += 1
                    elif sub_tok["type"] == "PAREN" and sub_tok["value"] == ")":
                        p_level -= 1
                        if p_level == 0:
                            break
                    elif p_level == 1 and sub_tok["type"] == "KEYWORD" and sub_tok["value"].upper() == "AS":
                        group = try_parse_type_at(sub_idx + 1)
                        if group:
                            type_groups.append(group)
                            
    # Context 3: Function/Procedure Parameters and Returns
    # Find CREATE FUNCTION or CREATE PROCEDURE
    for idx, t in enumerate(active_tokens):
        if t["type"] == "KEYWORD" and t["value"].upper() == "CREATE":
            is_func = False
            for offset in range(1, 5):
                if idx + offset < n_active:
                    val = active_tokens[idx + offset]["value"].upper()
                    if val in ("FUNCTION", "PROCEDURE"):
                        is_func = True
                        break
            if is_func:
                # Find the parameter list parenthesis '('
                params_start = None
                for sub_idx in range(idx + 1, n_active):
                    if active_tokens[sub_idx]["value"] == "(":
                        params_start = sub_idx
                        break
                if params_start is not None:
                    # Scan until matching ')'
                    p_level = 0
                    params_end = None
                    for sub_idx in range(params_start, n_active):
                        sub_tok = active_tokens[sub_idx]
                        if sub_tok["value"] == "(":
                            p_level += 1
                        elif sub_tok["value"] == ")":
                            p_level -= 1
                            if p_level == 0:
                                params_end = sub_idx
                                break
                    if params_end is not None:
                        # Inside parameters: separate by commas at level 1
                        param_tokens = active_tokens[params_start + 1 : params_end]
                        # Let's split parameter tokens by comma at level 0 (relative to parameter list)
                        p_level = 0
                        current_param = []
                        params = []
                        for pt in param_tokens:
                            if pt["value"] == "(":
                                p_level += 1
                            elif pt["value"] == ")":
                                p_level -= 1
                            if p_level == 0 and pt["type"] == "COMMA":
                                if current_param:
                                    params.append(current_param)
                                    current_param = []
                            else:
                                current_param.append(pt)
                        if current_param:
                            params.append(current_param)
                            
                        for param in params:
                            # Format of param: [IN/OUT/INOUT/VARIADIC] name type [DEFAULT ...]
                            # First, filter out any direction keywords
                            start_pt_idx = 0
                            if param[0]["value"].upper() in ("IN", "OUT", "INOUT", "VARIADIC"):
                                start_pt_idx = 1
                            if start_pt_idx < len(param):
                                # The second token is name. The token after name starts the type!
                                type_start_pt = start_pt_idx + 1
                                if type_start_pt < len(param):
                                    # Parse type starting at type_start_pt
                                    global_active_idx = token_to_active_idx[id(param[type_start_pt])]
                                    group = try_parse_type_at(global_active_idx)
                                    if group:
                                        type_groups.append(group)
                                        
                # Also handle RETURNS clause for functions
                for sub_idx in range(idx + 1, n_active):
                    if active_tokens[sub_idx]["value"].upper() == "RETURNS":
                        # RETURNS can be:
                        # 1. RETURNS type
                        # 2. RETURNS TABLE ( columns )
                        next_tok = active_tokens[sub_idx + 1]
                        if next_tok["value"].upper() == "TABLE":
                            # Find matching parenthesis
                            table_start = sub_idx + 2
                            if table_start < n_active and active_tokens[table_start]["value"] == "(":
                                p_level = 0
                                table_end = None
                                for p_idx in range(table_start, n_active):
                                    sub_tok = active_tokens[p_idx]
                                    if sub_tok["value"] == "(":
                                        p_level += 1
                                    elif sub_tok["value"] == ")":
                                        p_level -= 1
                                        if p_level == 0:
                                            table_end = p_idx
                                            break
                                if table_end is not None:
                                    # Columns inside TABLE (col type, col2 type)
                                    col_tokens = active_tokens[table_start + 1 : table_end]
                                    p_level = 0
                                    current_col = []
                                    cols = []
                                    for ct in col_tokens:
                                        if ct["value"] == "(":
                                            p_level += 1
                                        elif ct["value"] == ")":
                                            p_level -= 1
                                        if p_level == 0 and ct["type"] == "COMMA":
                                            if current_col:
                                                cols.append(current_col)
                                                current_col = []
                                        else:
                                            current_col.append(ct)
                                    if current_col:
                                        cols.append(current_col)
                                        
                                    for col in cols:
                                        if len(col) >= 2:
                                            # First is name, second is type
                                            global_active_idx = token_to_active_idx[id(col[1])]
                                            group = try_parse_type_at(global_active_idx)
                                            if group:
                                                type_groups.append(group)
                        else:
                            group = try_parse_type_at(sub_idx + 1)
                            if group:
                                type_groups.append(group)
                                
    # Context 4: DECLARE variable declarations
    # Find DECLARE keyword
    for idx, t in enumerate(active_tokens):
        if t["value"].upper() == "DECLARE":
            # Variables are declared until BEGIN or EXCEPTION
            declare_end = None
            for sub_idx in range(idx + 1, n_active):
                if active_tokens[sub_idx]["value"].upper() in ("BEGIN", "EXCEPTION"):
                    declare_end = sub_idx
                    break
            if declare_end is not None:
                declare_tokens = active_tokens[idx + 1 : declare_end]
                # Split by semicolon
                current_decl = []
                decls = []
                for dt in declare_tokens:
                    if dt["type"] == "SEMI":
                        if current_decl:
                            decls.append(current_decl)
                            current_decl = []
                    else:
                        current_decl.append(dt)
                if current_decl:
                    decls.append(current_decl)
                    
                for decl in decls:
                    if len(decl) >= 2:
                        # First is variable name, second starts type
                        global_active_idx = token_to_active_idx[id(decl[1])]
                        group = try_parse_type_at(global_active_idx)
                        if group:
                            type_groups.append(group)
                            
    # Context 5: CREATE [TEMP/TEMPORARY] TABLE table_name ( columns )
    for idx, t in enumerate(active_tokens):
        if t["type"] == "KEYWORD" and t["value"].upper() == "CREATE":
            is_table = False
            table_idx = None
            for offset in range(1, 4):
                if idx + offset < n_active:
                    val = active_tokens[idx + offset]["value"].upper()
                    if val == "TABLE":
                        is_table = True
                        table_idx = idx + offset
                        break
                    elif val in ("TEMP", "TEMPORARY"):
                        if idx + offset + 1 < n_active and active_tokens[idx + offset + 1]["value"].upper() == "TABLE":
                            is_table = True
                            table_idx = idx + offset + 1
                            break
            if is_table:
                # Find the column list parenthesis '('
                col_start = None
                for sub_idx in range(table_idx + 1, n_active):
                    if active_tokens[sub_idx]["value"] == "(":
                        col_start = sub_idx
                        break
                if col_start is not None:
                    # Scan until matching ')'
                    p_level = 0
                    col_end = None
                    for sub_idx in range(col_start, n_active):
                        sub_tok = active_tokens[sub_idx]
                        if sub_tok["value"] == "(":
                            p_level += 1
                        elif sub_tok["value"] == ")":
                            p_level -= 1
                            if p_level == 0:
                                col_end = sub_idx
                                break
                    if col_end is not None:
                        col_tokens = active_tokens[col_start + 1 : col_end]
                        p_level = 0
                        current_col = []
                        cols = []
                        for ct in col_tokens:
                            if ct["value"] == "(":
                                p_level += 1
                            elif ct["value"] == ")":
                                p_level -= 1
                            if p_level == 0 and ct["type"] == "COMMA":
                                if current_col:
                                    cols.append(current_col)
                                    current_col = []
                            else:
                                current_col.append(ct)
                        if current_col:
                            cols.append(current_col)
                            
                        for col in cols:
                            if col and col[0]["value"].upper() not in ("CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK"):
                                if len(col) >= 2:
                                    global_active_idx = token_to_active_idx[id(col[1])]
                                    group = try_parse_type_at(global_active_idx)
                                    if group:
                                        type_groups.append(group)
                            
    return type_groups


def is_values_multi(tokens: List[dict], open_idx: int) -> bool:
    # Check if the preceding active token is VALUES
    prev_tok = None
    for p_idx in range(open_idx - 1, -1, -1):
        if tokens[p_idx]["type"] not in ("WHITESPACE", "COMMENT"):
            prev_tok = tokens[p_idx]
            break
    if not prev_tok or prev_tok["value"].upper() != "VALUES":
        return False
        
    close_idx = find_matching_paren(tokens, open_idx)
    if close_idx is None:
        return False
        
    next_tok = None
    for n_idx in range(close_idx + 1, len(tokens)):
        if tokens[n_idx]["type"] not in ("WHITESPACE", "COMMENT"):
            next_tok = tokens[n_idx]
            break
            
    if next_tok and next_tok["type"] == "COMMA":
        return True
    return False

import functools

@functools.lru_cache(maxsize=4096)
def _tokenize_sql_cached(content: str) -> List[dict]:
    return _tokenize_sql_impl(content)

def tokenize_sql(content: str) -> List[dict]:
    return _tokenize_sql_cached(content)
