import re
from typing import List, Dict, Optional

def _tokenize_xml_impl(content: str) -> List[dict]:
    n = len(content)
    i = 0
    tokens = []
    line_number = 1
    inside_tag = False
    
    while i < n:
        c = content[i]
        
        # Line number tracking
        if c == '\n':
            tokens.append({
                "type": "WHITESPACE",
                "value": "\n",
                "start": i,
                "end": i + 1,
                "line": line_number
            })
            line_number += 1
            i += 1
            continue

        # XML Comment
        if content[i:i+4] == "<!--":
            start = i
            idx = content.find("-->", i + 4)
            if idx == -1:
                val = content[i:]
                i = n
            else:
                val = content[i:idx + 3]
                i = idx + 3
            start_line = line_number
            line_number += val.count('\n')
            tokens.append({
                "type": "COMMENT",
                "value": val,
                "start": start,
                "end": i,
                "line": start_line
            })
            continue

        # XML Declaration or Processing Instruction
        if content[i:i+2] == "<?":
            start = i
            idx = content.find("?>", i + 2)
            if idx == -1:
                val = content[i:]
                i = n
            else:
                val = content[i:idx + 2]
                i = idx + 2
            start_line = line_number
            line_number += val.count('\n')
            tokens.append({
                "type": "DECLARATION",
                "value": val,
                "start": start,
                "end": i,
                "line": start_line
            })
            continue

        # DocType
        if content[i:i+9].upper() == "<!DOCTYPE":
            start = i
            idx = content.find(">", i + 9)
            if idx == -1:
                val = content[i:]
                i = n
            else:
                val = content[i:idx + 1]
                i = idx + 1
            start_line = line_number
            line_number += val.count('\n')
            tokens.append({
                "type": "DECLARATION",
                "value": val,
                "start": start,
                "end": i,
                "line": start_line
            })
            continue

        if inside_tag:
            # Inside a tag, we parse whitespace, attribute names, equals, and attribute values
            if c.isspace():
                start = i
                start_line = line_number
                while i < n and content[i].isspace():
                    if content[i] == '\n':
                        line_number += 1
                    i += 1
                tokens.append({
                    "type": "WHITESPACE",
                    "value": content[start:i],
                    "start": start,
                    "end": i,
                    "line": start_line
                })
                continue
            
            # Tag end or self-closing tag end
            if content[i:i+2] == "/>":
                tokens.append({
                    "type": "TAG_END",
                    "value": "/>",
                    "start": i,
                    "end": i + 2,
                    "line": line_number
                })
                inside_tag = False
                i += 2
                continue
            if c == ">":
                tokens.append({
                    "type": "TAG_END",
                    "value": ">",
                    "start": i,
                    "end": i + 1,
                    "line": line_number
                })
                inside_tag = False
                i += 1
                continue
                
            # Equals
            if c == "=":
                tokens.append({
                    "type": "EQUAL",
                    "value": "=",
                    "start": i,
                    "end": i + 1,
                    "line": line_number
                })
                i += 1
                continue
                
            # Attribute values (quoted string)
            if c in ("'", '"'):
                start = i
                start_line = line_number
                quote = c
                i += 1
                while i < n and content[i] != quote:
                    if content[i] == '\n':
                        line_number += 1
                    i += 1
                if i < n:
                    i += 1
                tokens.append({
                    "type": "ATTR_VALUE",
                    "value": content[start:i],
                    "start": start,
                    "end": i,
                    "line": start_line
                })
                continue
                
            # Attribute names
            match = re.match(r'^[a-zA-Z0-9_:-]+', content[i:])
            if match:
                val = match.group(0)
                tokens.append({
                    "type": "ATTR_NAME",
                    "value": val,
                    "start": i,
                    "end": i + len(val),
                    "line": line_number
                })
                i += len(val)
                continue
                
            # Fallback in tag
            tokens.append({
                "type": "OTHER",
                "value": c,
                "start": i,
                "end": i + 1,
                "line": line_number
            })
            i += 1
        else:
            # Outside tags, we parse text, close tags, and open tags
            if content[i:i+2] == "</":
                # Close tag start
                match = re.match(r'^</[a-zA-Z0-9_:-]+', content[i:])
                if match:
                    val = match.group(0)
                    tokens.append({
                        "type": "TAG_CLOSE_START",
                        "value": val,
                        "start": i,
                        "end": i + len(val),
                        "line": line_number
                    })
                    inside_tag = True
                    i += len(val)
                    continue
            
            if c == "<":
                # Open tag start
                match = re.match(r'^<[a-zA-Z0-9_:-]+', content[i:])
                if match:
                    val = match.group(0)
                    tokens.append({
                        "type": "TAG_OPEN_START",
                        "value": val,
                        "start": i,
                        "end": i + len(val),
                        "line": line_number
                    })
                    inside_tag = True
                    i += len(val)
                    continue
                    
            # Whitespace
            if c.isspace():
                start = i
                start_line = line_number
                while i < n and content[i].isspace():
                    if content[i] == '\n':
                        line_number += 1
                    i += 1
                tokens.append({
                    "type": "WHITESPACE",
                    "value": content[start:i],
                    "start": start,
                    "end": i,
                    "line": start_line
                })
                continue
                
            # Text content
            start = i
            start_line = line_number
            while i < n and content[i] != "<":
                if content[i] == '\n':
                    line_number += 1
                i += 1
            tokens.append({
                "type": "TEXT",
                "value": content[start:i],
                "start": start,
                "end": i,
                "line": start_line
            })

    return tokens

import functools

@functools.lru_cache(maxsize=1024)
def _tokenize_xml_cached(content: str) -> List[dict]:
    return _tokenize_xml_impl(content)

def tokenize_xml(content: str) -> List[dict]:
    return _tokenize_xml_cached(content)
