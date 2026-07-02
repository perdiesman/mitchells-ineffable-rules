import os
import re
from typing import Dict, Set, List, Tuple

# Regexes to find IR rules in comments
START_RE = re.compile(r"IR-start-([a-zA-Z0-9_-]+)")
END_RE = re.compile(r"IR-end-([a-zA-Z0-9_-]+)")
SINGLE_RE = re.compile(r"IR-([a-zA-Z0-9_-]+)")

def get_file_language(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".sql":
        return "sql"
    elif ext in (".java", ".jav"):
        return "java"
    elif ext == ".xml":
        return "xml"
    return "unknown"

def extract_comments_and_code_lines(content: str, lang: str) -> Tuple[List[str], Dict[int, List[str]], Set[int]]:
    """
    Scans the file character-by-character to extract comments and identify code/comment lines.
    Returns:
      - lines: List[str] of original file lines (0-indexed list, but we use 1-indexed line numbers in return values).
      - line_comments: Dict[int, List[str]] mapping 1-indexed line number to a list of comment strings found on that line.
      - comment_only_lines: Set[int] of 1-indexed line numbers that contain ONLY comments and whitespace.
    """
    lines = content.splitlines()
    line_comments: Dict[int, List[str]] = {}
    comment_only_lines: Set[int] = set()
    
    # We will track which characters belong to comments or code
    # For simplicity, we can do a state machine scan of the entire content
    # to extract comments and associate them with lines.
    
    n = len(content)
    i = 0
    current_line = 1
    
    # State flags
    in_string = False
    string_char = None
    in_single_comment = False
    in_multi_comment = False
    
    # XML specific state
    in_xml_comment = False
    
    # To reconstruct comments and their lines
    active_comment = []
    active_comment_start_line = 1
    
    # Keep track of characters that are "code" vs "comment" per line
    # line_has_code[line_num] = True/False
    line_has_code: Dict[int, bool] = {l: False for l in range(1, len(lines) + 2)}
    
    while i < n:
        c = content[i]
        
        # Track line number
        if c == '\n':
            if in_single_comment:
                # End of single line comment
                comment_text = "".join(active_comment)
                line_comments.setdefault(active_comment_start_line, []).append(comment_text)
                active_comment = []
                in_single_comment = False
            
            current_line += 1
            i += 1
            continue
            
        if in_single_comment:
            active_comment.append(c)
            i += 1
            continue
            
        if in_multi_comment:
            active_comment.append(c)
            # Check for end of multi-line comment */
            if lang in ("java", "sql") and c == '*' and i + 1 < n and content[i + 1] == '/':
                active_comment.append('/')
                comment_text = "".join(active_comment)
                # Multi-line comment might span lines, associate with start line or all lines?
                # Usually, we associate comments with the lines they appear on.
                # Let's associate it with all lines it spans.
                for l in range(active_comment_start_line, current_line + 1):
                    line_comments.setdefault(l, []).append(comment_text)
                active_comment = []
                in_multi_comment = False
                i += 2
                continue
            i += 1
            continue
            
        if in_xml_comment:
            active_comment.append(c)
            # Check for end of XML comment -->
            if c == '-' and i + 2 < n and content[i+1] == '-' and content[i+2] == '>':
                active_comment.append('-')
                active_comment.append('>')
                comment_text = "".join(active_comment)
                for l in range(active_comment_start_line, current_line + 1):
                    line_comments.setdefault(l, []).append(comment_text)
                active_comment = []
                in_xml_comment = False
                i += 3
                continue
            i += 1
            continue
            
        if in_string:
            if c == string_char:
                # Check for escaped quotes (SQL uses '', Java uses \")
                if lang == "sql" and i + 1 < n and content[i + 1] == "'":
                    # Escaped quote in SQL
                    line_has_code[current_line] = True
                    i += 2
                    continue
                elif lang == "java" and content[i - 1] == '\\':
                    # Escaped quote in Java (if previous char was backslash, and not escaped backslash itself)
                    # Let's do a simple check
                    backslash_count = 0
                    k = i - 1
                    while k >= 0 and content[k] == '\\':
                        backslash_count += 1
                        k -= 1
                    if backslash_count % 2 == 1:
                        # Escaped quote
                        line_has_code[current_line] = True
                        i += 1
                        continue
                in_string = False
                string_char = None
            line_has_code[current_line] = True
            i += 1
            continue
            
        # Normal State: look for transitions
        if lang == "xml":
            if c == '<' and i + 3 < n and content[i+1:i+4] == "!--":
                in_xml_comment = True
                active_comment_start_line = current_line
                active_comment = ["<!--"]
                i += 4
                continue
            elif not c.isspace():
                line_has_code[current_line] = True
                
        elif lang in ("java", "sql"):
            # String literals
            if c in ("'", '"'):
                # In SQL, only single quotes are strings (double quotes are identifiers, but let's treat both as string/code)
                in_string = True
                string_char = c
                line_has_code[current_line] = True
                i += 1
                continue
                
            # Single line comments
            if lang == "java" and c == '/' and i + 1 < n and content[i + 1] == '/':
                in_single_comment = True
                active_comment_start_line = current_line
                active_comment = ["//"]
                i += 2
                continue
            elif lang == "sql" and c == '-' and i + 1 < n and content[i + 1] == '-':
                in_single_comment = True
                active_comment_start_line = current_line
                active_comment = ["--"]
                i += 2
                continue
                
            # Multi line comments
            if c == '/' and i + 1 < n and content[i + 1] == '*':
                in_multi_comment = True
                active_comment_start_line = current_line
                active_comment = ["/*"]
                i += 2
                continue
            
            if not c.isspace():
                line_has_code[current_line] = True
                
        else:
            # Unknown language: treat non-space as code
            if not c.isspace():
                line_has_code[current_line] = True
                
        i += 1

    # Flush remaining single line comment if file didn't end with newline
    if in_single_comment:
        comment_text = "".join(active_comment)
        line_comments.setdefault(active_comment_start_line, []).append(comment_text)

    # Determine comment-only lines:
    # A line is comment-only if we found a comment on it, AND it has line_has_code == False
    for l in range(1, len(lines) + 1):
        if not line_has_code[l] and l in line_comments:
            comment_only_lines.add(l)
            
    return lines, line_comments, comment_only_lines


def get_disabled_rules_map(content: str, file_path: str) -> Dict[str, Set[int]]:
    """
    Parses comment blocks and single-line disables to build a map of:
      rule_id -> Set of 1-indexed line numbers where the rule is disabled.
    """
    lang = get_file_language(file_path)
    if lang == "unknown":
        return {}
        
    lines, line_comments, comment_only_lines = extract_comments_and_code_lines(content, lang)
    
    disabled_lines: Dict[str, Set[int]] = {}
    active_blocks: Set[str] = set()
    pending_single_line: Set[str] = set()
    
    # Go through each line (1-indexed)
    for l in range(1, len(lines) + 1):
        # Apply current active blocks to this line
        for rule_id in active_blocks:
            disabled_lines.setdefault(rule_id, set()).add(l)
            
        # Parse any comments on this line to update state
        comments = line_comments.get(l, [])
        line_has_start_or_end = False
        
        for comment in comments:
            # 1. Parse start block
            starts = START_RE.findall(comment)
            for s in starts:
                rule_id = f"IR-{s}"
                active_blocks.add(rule_id)
                line_has_start_or_end = True
                
            # 2. Parse end block
            ends = END_RE.findall(comment)
            for e in ends:
                rule_id = f"IR-{e}"
                if rule_id in active_blocks:
                    active_blocks.remove(rule_id)
                line_has_start_or_end = True
                
            # 3. Parse single line disables
            # We want to match IR-<rule> but only if it's not start-<rule> or end-<rule>
            # Let's find all occurrences of IR-<rule>
            singles = SINGLE_RE.findall(comment)
            for s in singles:
                if s.startswith("start-") or s.startswith("end-"):
                    continue
                rule_id = f"IR-{s}"
                pending_single_line.add(rule_id)

        # Determine if this line counts as a code line (or if we carry forward the single-line disable)
        # If a line only contains comments (e.g. comment-only line) or is completely empty:
        is_empty = len(lines[l-1].strip()) == 0
        is_comment_only = l in comment_only_lines
        
        if is_empty or is_comment_only:
            # It's not a code line. Carry forward the pending single-line disables.
            # (Do not apply pending_single_line to this line, unless it was already applied)
            continue
        else:
            # It is a code line. Apply any pending single-line disables to this line, then clear them.
            for rule_id in pending_single_line:
                disabled_lines.setdefault(rule_id, set()).add(l)
            pending_single_line = set()
            
    return disabled_lines
