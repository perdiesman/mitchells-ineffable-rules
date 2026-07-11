from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql
from mir.rules.sql.indent import IndentRule

class PlpgsqlBlockIndentRule(BaseRule):
    rule_id = "IR-plpgsql-block-indent"
    description = "Enforce block structure indentation inside PL/pgSQL procedural code blocks."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "indent_size": 4
    }
    config_options = {
        "indent_size": {
            "default": 4,
            "description": "Indentation size in spaces.",
            "fallback": "IR-indent:indent_size"
        }
    }
    
    examples = [
        {
            "violating": "IF (condition) THEN\nRAISE NOTICE 'HERE';\nEND IF;",
            "correct": "IF (condition) THEN\n    RAISE NOTICE 'HERE';\nEND IF;"
        }
    ]
    additional_validations = [
        "IF (condition) THEN\n    RAISE NOTICE 'HERE';\nEND IF;"
    ]

    def _find_violations(self, content: str, indent_size: int) -> List[dict]:
        tokens = tokenize_sql(content)
        n = len(tokens)
        
        has_blocks = any(
            t["type"] in ("KEYWORD", "IDENTIFIER") and t["value"].upper() in ("DECLARE", "BEGIN", "IF", "LOOP", "WHILE", "FOR", "EXCEPTION")
            for t in tokens
        )
        if not has_blocks:
            return []
            
        lines_tokens = {}
        for t in tokens:
            l = t["line"]
            if l not in lines_tokens:
                lines_tokens[l] = []
            lines_tokens[l].append(t)
            
        # Get active tokens globally (ignoring whitespace and comments)
        active_indices = [idx for idx, t in enumerate(tokens) if t["type"] not in ("WHITESPACE", "COMMENT")]
        # Map token object index to its position in active_indices
        token_to_active_pos = {id(tokens[idx]): pos for pos, idx in enumerate(active_indices)}
        
        stack = []
        violations = []
        
        max_line = max(lines_tokens.keys()) if lines_tokens else 0
        for l in range(1, max_line + 1):
            if l not in lines_tokens:
                continue
            line_toks = lines_tokens[l]
            active_toks = [t for t in line_toks if t["type"] not in ("WHITESPACE", "COMMENT")]
            if not active_toks:
                continue
                
            first_tok = active_toks[0]
            first_val = first_tok["value"].upper()
            
            is_adjusting = False
            
            if first_val == "BEGIN":
                if stack and stack[-1] == "DECLARE":
                    stack.pop()
            elif first_val == "END":
                is_end_if = False
                is_end_loop = False
                if len(active_toks) > 1:
                    next_val = active_toks[1]["value"].upper()
                    if next_val == "IF":
                        is_end_if = True
                    elif next_val == "LOOP":
                        is_end_loop = True
                
                if is_end_if:
                    if stack and stack[-1] == "IF":
                        stack.pop()
                elif is_end_loop:
                    if stack and stack[-1] in ("LOOP", "FOR", "WHILE"):
                        stack.pop()
                else:
                    if stack and stack[-1] in ("BEGIN", "DECLARE", "EXCEPTION"):
                        stack.pop()
            elif first_val in ("ELSIF", "ELSE", "WHEN"):
                is_adjusting = True
                
            expected_level = len(stack)
            if is_adjusting and expected_level > 0:
                expected_level = expected_level - 1
                
            expected_spaces = expected_level * indent_size
            
            leading_ws = ""
            if line_toks and line_toks[0]["type"] == "WHITESPACE":
                leading_ws = line_toks[0]["value"]
            leading_spaces = len(leading_ws.replace("\n", "").replace("\r", "").replace("\t", " " * indent_size))
            
            should_check = False
            exact_enforce = False
            
            if expected_level > 0:
                should_check = True
                # Check if this line is a block keyword or starts a statement
                is_block_keyword = first_val in ("DECLARE", "BEGIN", "EXCEPTION", "IF", "WHILE", "FOR", "LOOP", "ELSIF", "ELSE", "END")
                is_starter = False
                tok_id = id(first_tok)
                if tok_id in token_to_active_pos:
                    pos = token_to_active_pos[tok_id]
                    if pos == 0:
                        is_starter = True
                    else:
                        prev_tok = tokens[active_indices[pos - 1]]
                        if prev_tok["value"].upper() in (";", "BEGIN", "THEN", "ELSE", "EXCEPTION", "LOOP", "DECLARE"):
                            is_starter = True
                exact_enforce = is_block_keyword or is_starter
            elif first_val in ("DECLARE", "BEGIN", "END", "IF", "WHILE", "FOR", "LOOP", "ELSIF", "ELSE"):
                should_check = True
                exact_enforce = True
                
            if should_check:
                is_violation = False
                if exact_enforce:
                    if leading_spaces != expected_spaces:
                        is_violation = True
                else:
                    if leading_spaces < expected_spaces:
                        is_violation = True
                        
                if is_violation:
                    violations.append({
                        "line": l,
                        "expected": expected_spaces,
                        "actual": leading_spaces,
                        "first_token": first_tok
                    })
                
            if first_val == "DECLARE":
                stack.append("DECLARE")
            elif first_val == "BEGIN":
                stack.append("BEGIN")
            elif first_val == "EXCEPTION":
                stack.append("EXCEPTION")
            elif first_val == "IF":
                stack.append("IF")
            elif first_val == "WHILE":
                stack.append("WHILE")
            elif first_val == "FOR":
                has_loop = any(t["value"].upper() == "LOOP" for t in active_toks)
                if has_loop:
                    stack.append("FOR")
            elif first_val == "LOOP":
                has_for_while = any(t["value"].upper() in ("FOR", "WHILE") for t in active_toks)
                if not has_for_while:
                    stack.append("LOOP")
                    
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        indent_size = self.get_config_value(rule_config, "indent_size", 4, fallbacks=[(IndentRule, "indent_size")])
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, indent_size)
        
        for item in offending:
            tok = item["first_token"]
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message=f"Procedural block indentation mismatch. Expected {item['expected']} spaces, got {item['actual']}.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        indent_size = self.get_config_value(rule_config, "indent_size", 4, fallbacks=[(IndentRule, "indent_size")])
        offending = self._find_violations(content, indent_size)
        if not offending:
            return content
            
        lines = content.splitlines()
        for item in offending:
            line_no = item["line"]
            expected_spaces = item["expected"]
            line = lines[line_no - 1]
            
            leading_ws = ""
            for char in line:
                if char in (" ", "\t"):
                    leading_ws += char
                else:
                    break
            cleaned_line = line[len(leading_ws):]
            lines[line_no - 1] = (" " * expected_spaces) + cleaned_line
            
        return "\n".join(lines) + ("\n" if content.endswith("\n") else "")
