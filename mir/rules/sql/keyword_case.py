import re
from typing import List, Dict, Any, Tuple
from mir.engine.rule_interface import BaseRule, Violation

KEYWORDS = [
    "select", "from", "where", "join", "on", "and", "or", "limit",
    "group by", "order by", "insert", "into", "values", "update",
    "set", "delete", "create", "table", "drop", "alter", "index",
    "left", "right", "inner", "outer", "as", "having", "union",
    "with", "distinct", "recursive", "case", "when", "then", "else", "end"
]

class KeywordCaseRule(BaseRule):
    rule_id = "IR-keyword-case"
    description = (
        "SQL keywords must be in uppercase. "
        "Default keywords checked: select, from, where, join, on, and, or, limit, "
        "group by, order by, insert, into, values, update, set, delete, create, "
        "table, drop, alter, index, left, right, inner, outer, as, having, union, "
        "with, distinct, recursive, case, when, then, else, end."
    )
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "additional_keywords": [],
        "override_keywords": None
    }
    config_options = {
        "additional_keywords": {
            "type": "list",
            "description": "Additional SQL keywords to check/uppercase on top of defaults.",
            "default": []
        },
        "override_keywords": {
            "type": "list",
            "description": "Override the default list of SQL keywords entirely.",
            "default": None
        }
    }
    
    examples = [
        {
            "violating": "select id, username from users where active = true;",
            "correct": "SELECT id, username FROM users WHERE active = true;"
        }
    ]
    additional_validations = []

    def _get_keywords(self, rule_config: Dict[str, Any]) -> List[str]:
        override = rule_config.get("override_keywords")
        if override is not None:
            if isinstance(override, str):
                override = [x.strip().lower() for x in override.split(",") if x.strip()]
            return [k.lower() for k in override]
            
        additional = rule_config.get("additional_keywords", [])
        if isinstance(additional, str):
            additional = [x.strip() for x in additional.split(",") if x.strip()]
            
        default_kws = [k.lower() for k in KEYWORDS]
        seen = set(default_kws)
        result = list(default_kws)
        for k in additional:
            k_lower = k.lower()
            if k_lower not in seen:
                seen.add(k_lower)
                result.append(k_lower)
        return result

    def _find_violations_in_text(self, text: str, line_offset: int, keywords: List[str]) -> List[Tuple[int, str]]:
        violations = []
        lines = text.splitlines()
        
        # Compile patterns dynamically
        patterns = [
            (kw, re.compile(rf"\b({re.escape(kw)})\b", re.IGNORECASE))
            for kw in keywords
        ]
        
        for idx, line in enumerate(lines):
            for kw, pattern in patterns:
                matches = pattern.finditer(line)
                for m in matches:
                    matched_val = m.group(1)
                    if matched_val != matched_val.upper():
                        violations.append((line_offset + idx + 1, matched_val))
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        clean_content = self._mask_comments_and_strings(content)
        keywords = self._get_keywords(rule_config)
        violations_found = self._find_violations_in_text(clean_content, 0, keywords)
        
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
        keywords = set(self._get_keywords(rule_config))
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
            
            if in_string:
                if c == string_char:
                    if i + 1 < n and content[i + 1] == "'":
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
                    break
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
                
            if c.isalpha() or c == '_':
                w_start = i
                while i < n and (content[i].isalnum() or content[i] == '_'):
                    i += 1
                word = content[w_start:i]
                
                peek_word = word.lower()
                next_i = i
                if peek_word in ("group", "order"):
                    while next_i < n and content[next_i].isspace():
                        next_i += 1
                    w2_start = next_i
                    while next_i < n and (content[next_i].isalnum() or content[next_i] == '_'):
                        next_i += 1
                    word2 = content[w2_start:next_i]
                    if word2.lower() == "by":
                        word = content[w_start:next_i]
                        peek_word = f"{peek_word} by"
                        i = next_i
                
                if peek_word in keywords:
                    if word != word.upper():
                        fixed_chunks.append(content[chunk_start:w_start])
                        fixed_chunks.append(word.upper())
                        chunk_start = i
                continue
                
            i += 1
            
        fixed_chunks.append(content[chunk_start:])
        return "".join(fixed_chunks)

    def _mask_comments_and_strings(self, content: str) -> str:
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
