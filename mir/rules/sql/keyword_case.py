import re
from typing import List, Dict, Any, Tuple
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.disabler import extract_comments_and_code_lines

KEYWORDS = [
    "select", "from", "where", "join", "on", "and", "or", "limit",
    "group by", "order by", "insert", "into", "values", "update",
    "set", "delete", "create", "table", "drop", "alter", "index",
    "left", "right", "inner", "outer", "as", "having", "union",
    "with", "select", "distinct", "into", "update", "delete"
]

# Compile case-insensitive keyword regexes matching word boundaries
# e.g., \b(select)\b case-insensitively
KEYWORD_PATTERNS = [
    (kw, re.compile(rf"\b({re.escape(kw)})\b", re.IGNORECASE))
    for kw in KEYWORDS
]

class KeywordCaseRule(BaseRule):
    rule_id = "IR-keyword-case"
    description = "SQL keywords must be in uppercase."
    category = "general"
    is_fixable = "yes"
    examples = [
        {
            "violating": "select id, username from users where active = true;",
            "correct": "SELECT id, username FROM users WHERE active = true;"
        }
    ]

    def _find_violations_in_text(self, text: str, line_offset: int) -> List[Tuple[int, str]]:
        # Returns list of (line_num, matched_word)
        violations = []
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            # We want to match keyword case.
            # To be simple and robust, we check each keyword pattern.
            for kw, pattern in KEYWORD_PATTERNS:
                matches = pattern.finditer(line)
                for m in matches:
                    matched_val = m.group(1)
                    if matched_val != matched_val.upper():
                        violations.append((line_offset + idx + 1, matched_val))
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        # We need to scan code portions (ignoring comments and strings)
        # To do this perfectly, we can use the extract_comments_and_code_lines
        # but let's do a simple code extractor: replace comments and strings with spaces
        # of the same length to preserve line numbers and columns!
        clean_content = self._mask_comments_and_strings(content)
        violations_found = self._find_violations_in_text(clean_content, 0)
        
        # Group violations by line number to report once per line or multiple times
        by_line: Dict[int, List[str]] = {}
        for line_num, kw in violations_found:
            by_line.setdefault(line_num, []).append(kw)
            
        lines = content.splitlines()
        violations = []
        for line_num, kws in by_line.items():
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=line_num,
                    message=f"Keywords {', '.join(repr(k) for k in kws)} should be uppercase.",
                    offending_lines=[lines[line_num - 1]],
                    is_fixable=self.is_fixable
                )
            )
            
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        # To fix, we replace the lowercase keywords with uppercase.
        # But we must NOT modify comments or string literals.
        # We scan character-by-character and perform replacements only in code sections.
        # An easier way is to tokenize or do a selective replace.
        # Let's do a state-machine replacement to preserve comments and strings:
        
        n = len(content)
        i = 0
        in_string = False
        string_char = None
        in_single_comment = False
        in_multi_comment = False
        
        fixed_chunks = []
        chunk_start = 0
        
        while i < n:
            c = content[i]
            
            # String handling
            if in_string:
                if c == string_char:
                    # check escape
                    if i + 1 < n and content[i + 1] == "'":
                        i += 2
                        continue
                    in_string = False
                i += 1
                continue
                
            # Comment handling
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
                
            # Transition to string/comment
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
                
            # If in normal code, let's see if we match a keyword starting at i
            # To do this, we can extract the alphanumeric word at i
            if c.isalpha() or c == '_':
                w_start = i
                while i < n and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[w_start:i]
                # Check group by / order by (two words)
                # Let's peek if the next word makes it "group by" or "order by"
                peek_word = word.lower()
                next_i = i
                if peek_word in ("group", "order"):
                    # skip spaces
                    while next_i < n and content[next_i].isspace():
                        next_i += 1
                    # check next word
                    w2_start = next_i
                    while next_i < n and (content[next_i].isalnum() or content[next_i] == '_'):
                        next_i += 1
                    word2 = content[w2_start:next_i]
                    if word2.lower() == "by":
                        word = content[w_start:next_i]
                        peek_word = f"{peek_word} by"
                        i = next_i
                
                if peek_word in KEYWORDS:
                    if word != word.upper():
                        # We have a keyword to uppercase!
                        # Add everything before this word
                        fixed_chunks.append(content[chunk_start:w_start])
                        fixed_chunks.append(word.upper())
                        chunk_start = i
                continue
                
            i += 1
            
        fixed_chunks.append(content[chunk_start:])
        return "".join(fixed_chunks)

    def _mask_comments_and_strings(self, content: str) -> str:
        """
        Replaces comments and strings with spaces to keep same lengths and indices.
        """
        n = len(content)
        masked = list(content)
        i = 0
        in_string = False
        string_char = None
        in_single_comment = False
        in_multi_comment = False
        
        while i < n:
            c = content[i]
            
            if in_string:
                if c == string_char:
                    if i + 1 < n and content[i + 1] == "'":
                        i += 2
                        continue
                    in_string = False
                elif c != '\n':
                    masked[i] = ' '
                i += 1
                continue
                
            if in_single_comment:
                if c == '\n':
                    in_single_comment = False
                else:
                    masked[i] = ' '
                i += 1
                continue
                
            if in_multi_comment:
                if c == '*' and i + 1 < n and content[i + 1] == '/':
                    in_multi_comment = False
                    i += 2
                    continue
                elif c != '\n':
                    masked[i] = ' '
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
                
            i += 1
            
        return "".join(masked)
