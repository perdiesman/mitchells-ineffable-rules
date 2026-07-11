from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren

def format_returns_table(returns_type_str: str) -> str:
    if not returns_type_str.upper().startswith("TABLE"):
        return returns_type_str
        
    open_p = returns_type_str.find("(")
    close_p = returns_type_str.rfind(")")
    if open_p == -1 or close_p == -1:
        return returns_type_str
        
    cols_content = returns_type_str[open_p + 1 : close_p]
    lines = cols_content.splitlines()
    
    is_multiline = any("\n" in line for line in lines) or len(lines) > 1
    
    if not is_multiline:
        return f"TABLE({cols_content.strip()})"
        
    cleaned_lines = []
    for line in lines:
        if line.strip():
            cleaned_lines.append("    " + line.strip())
            
    return "TABLE(\n" + "\n".join(cleaned_lines) + "\n)"

class FunctionHeaderLayoutRule(BaseRule):
    rule_id = "IR-function-header-layout"
    description = "Standardize formatting, line-wrapping, and indentation of function creation headers."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "max_length": 120
    }
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length before wrapping clauses."
        }
    }
    
    examples = [
        {
            "violating": "CREATE OR REPLACE FUNCTION my_func()\n RETURNS trigger\n LANGUAGE plpgsql\nAS $function$",
            "correct": "CREATE OR REPLACE FUNCTION my_func() RETURNS trigger LANGUAGE plpgsql AS $function$"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_len = self.get_config_value(rule_config, "max_length", 120)
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)
        
        i = 0
        while i < n:
            t = tokens[i]
            if t["type"] == "KEYWORD" and t["value"].upper() == "CREATE":
                # Check for FUNCTION definition
                is_func = False
                func_idx = None
                for idx in range(i + 1, min(i + 10, n)):
                    if tokens[idx]["type"] == "WHITESPACE":
                        continue
                    if tokens[idx]["value"].upper() == "FUNCTION":
                        is_func = True
                        func_idx = idx
                        break
                    if tokens[idx]["value"].upper() not in ("OR", "REPLACE"):
                        break
                        
                if not is_func:
                    i += 1
                    continue
                    
                # Find open paren of parameter list
                open_paren_idx = None
                for idx in range(func_idx + 1, n):
                    if tokens[idx]["type"] == "PAREN" and tokens[idx]["value"] == "(":
                        open_paren_idx = idx
                        break
                    
                if open_paren_idx is None:
                    i = func_idx + 1
                    continue
                    
                close_paren_idx = find_matching_paren(tokens, open_paren_idx)
                if close_paren_idx is None:
                    i = open_paren_idx + 1
                    continue
                    
                # Find next body string token (dollar-quoted string)
                body_tok = None
                for idx in range(close_paren_idx + 1, n):
                    if tokens[idx]["type"] == "STRING" and tokens[idx]["value"].startswith("$"):
                        body_tok = tokens[idx]
                        break
                        
                if body_tok is None:
                    i = close_paren_idx + 1
                    continue
                    
                # Extract header tokens from close_paren_idx + 1 to body_tok's start
                header_tokens = tokens[close_paren_idx + 1 : body_tok["start"]]
                header_active = [tok for tok in header_tokens if tok["type"] not in ("WHITESPACE", "COMMENT")]
                
                # We need RETURNS, LANGUAGE, AS
                returns_tok = None
                language_tok = None
                as_tok = None
                
                for tok in header_active:
                    val_up = tok["value"].upper()
                    if val_up == "RETURNS":
                        returns_tok = tok
                    elif val_up == "LANGUAGE":
                        language_tok = tok
                    elif val_up == "AS":
                        as_tok = tok
                        
                if not (returns_tok and language_tok and as_tok):
                    i = body_tok["start"]
                    continue
                    
                # Group tokens into clauses
                # 1. RETURNS clause
                returns_idx = header_active.index(returns_tok)
                language_idx = header_active.index(language_tok)
                as_idx = header_active.index(as_tok)
                
                # Check expected ordering
                if not (returns_idx < language_idx < as_idx):
                    i = body_tok["start"]
                    continue
                    
                returns_type_tokens = header_active[returns_idx + 1 : language_idx]
                options_tokens = header_active[language_idx + 2 : as_idx]
                
                # Format clauses by keeping their original content and formatting
                returns_type_str = content[returns_type_tokens[0]["start"] : returns_type_tokens[-1]["end"]].strip()
                returns_type_str = format_returns_table(returns_type_str)
                returns_str = "RETURNS " + returns_type_str
                language_str = "LANGUAGE plpgsql"
                
                options_str = ""
                if options_tokens:
                    options_str = content[options_tokens[0]["start"] : options_tokens[-1]["end"]].strip()
                    
                as_str = "AS"
                
                clauses = [returns_str, language_str]
                if options_str:
                    clauses.append(options_str)
                clauses.append(as_str)
                
                func_sig_cleaned = content[t["start"] : tokens[close_paren_idx]["end"]].strip()
                
                def indent_clause(clause_text: str) -> str:
                    lines = clause_text.splitlines()
                    res_lines = []
                    for line_idx, line in enumerate(lines):
                        if line_idx == 0:
                            res_lines.append("    " + line.strip())
                        else:
                            # Keep relative indentation of inner lines
                            res_lines.append("    " + line)
                    return "\n".join(res_lines)
                
                # Check if any clause is multiline or if the single line signature is too long
                has_multiline_clause = any("\n" in c for c in clauses)
                header_single = func_sig_cleaned + " " + " ".join(clauses)
                
                if not has_multiline_clause and len(header_single) <= max_len:
                    expected_header = header_single
                else:
                    clauses_line = "    " + " ".join(clauses)
                    if not has_multiline_clause and len(clauses_line) <= max_len:
                        expected_header = func_sig_cleaned + "\n" + clauses_line
                    else:
                        formatted_clauses = [indent_clause(c) for c in clauses]
                        expected_header = func_sig_cleaned + "\n" + "\n".join(formatted_clauses)
                        
                # Compare original text from CREATE start to body_tok start with expected
                original_header_text = content[t["start"] : body_tok["start"]].rstrip()
                if original_header_text != expected_header:
                    violations.append({
                        "start_offset": t["start"],
                        "end_offset": body_tok["start"],
                        "replacement": expected_header + " ",
                        "line": t["line"]
                    })
                    
                i = body_tok["start"]
                continue
                
            i += 1
            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, rule_config)
        for item in offending:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message="Function definition header formatting/indentation is not standardized.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content, rule_config)
        if not offending:
            return content
        offending.sort(key=lambda x: x["start_offset"], reverse=True)
        chars = list(content)
        for item in offending:
            start = item["start_offset"]
            end = item["end_offset"]
            repl = item["replacement"]
            chars[start:end] = list(repl)
        return "".join(chars)
