import re
from typing import List, Dict, Optional

SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "NATURAL", "ON", "USING",
    "UNION", "INTERSECT", "EXCEPT", "AND", "OR", "NOT", "IN", "EXISTS", "IS", "NULL",
    "AS", "CREATE", "VIEW", "MATERIALIZED", "TABLE", "INSERT", "INTO", "VALUES", "UPDATE",
    "SET", "DELETE", "WITH", "CASE", "WHEN", "THEN", "ELSE", "END", "COALESCE",
    "RECURSIVE", "ASC", "DESC"
}

OPERATORS = {
    "=", "<>", "<=", ">=", "!=", "<", ">", "+", "-", "*", "/", "%", "||", "~*"
}

def tokenize_sql(content: str) -> List[dict]:
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
