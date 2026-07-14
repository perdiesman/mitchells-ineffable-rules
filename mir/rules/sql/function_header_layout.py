from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, find_matching_paren

def split_cols(cols_str: str) -> List[str]:
    parts = []
    current = []
    depth = 0
    for char in cols_str:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]

def format_returns_table(returns_type_str: str, max_len: int = 120) -> str:
    if not returns_type_str.upper().startswith("TABLE"):
        return returns_type_str
        
    open_p = returns_type_str.find("(")
    close_p = returns_type_str.rfind(")")
    if open_p == -1 or close_p == -1:
        return returns_type_str
        
    cols_content = returns_type_str[open_p + 1 : close_p].strip()
    
    # Check if it fits on a single line
    single_line = f"TABLE({cols_content})"
    if len("    RETURNS " + single_line) <= max_len and "\n" not in cols_content:
        return single_line
        
    cols = split_cols(cols_content)
    cleaned_lines = []
    for col in cols:
        cleaned_lines.append("    " + col)
        
    return "TABLE(\n" + ",\n".join(cleaned_lines) + "\n)"

class FunctionHeaderLayoutRule(BaseRule):
    rule_id = "IR-function-header-layout"
    description = "Standardize formatting, line-wrapping, and indentation of function creation headers."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    exclude_recursive = True
    
    default_config = {
        "max_length": 100
    }
    config_options = {
        "max_length": {
            "default": 100,
            "description": "Maximum line length before wrapping clauses."
        }
    }
    
    examples = [
        {
            "violating": "CREATE OR REPLACE FUNCTION my_func()\n RETURNS trigger\n LANGUAGE plpgsql\nAS $function$",
            "correct": "CREATE OR REPLACE FUNCTION my_func() RETURNS trigger LANGUAGE plpgsql AS\n$function$"
        },
        {
            "violating": "CREATE FUNCTION test_func()\nAS $body$\nBEGIN\n    RETURN 1;\nEND;\n$body$ LANGUAGE plpgsql STABLE RETURNS integer;",
            "correct": "CREATE FUNCTION test_func() RETURNS integer LANGUAGE plpgsql STABLE AS\n$body$\nBEGIN\n    RETURN 1;\nEND;\n$body$;"
        }
    ]
    additional_validations = []

    def _find_violations(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_len = self.get_config_value(rule_config, "max_length", 100)
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
                body_tok_idx = None
                for idx in range(close_paren_idx + 1, n):
                    if tokens[idx]["type"] == "STRING" and tokens[idx]["value"].startswith("$"):
                        body_tok = tokens[idx]
                        body_tok_idx = idx
                        break
                        
                if body_tok is None:
                    i = close_paren_idx + 1
                    continue
                    
                # Find the terminating semicolon for the function statement
                semi_tok_idx = n
                for idx in range(body_tok_idx + 1, n):
                    if tokens[idx]["type"] == "SEMI":
                        semi_tok_idx = idx
                        break
                        
                if semi_tok_idx < n:
                    end_offset = tokens[semi_tok_idx]["start"]
                else:
                    end_offset = tokens[-1]["end"]

                # Extract header active tokens and footer active tokens (excluding AS)
                header_tokens = tokens[close_paren_idx + 1 : body_tok_idx]
                header_active = [tok for tok in header_tokens if tok["type"] not in ("WHITESPACE", "COMMENT")]
                
                footer_tokens = tokens[body_tok_idx + 1 : semi_tok_idx]
                footer_active = [tok for tok in footer_tokens if tok["type"] not in ("WHITESPACE", "COMMENT")]
                
                all_active = [tok for tok in header_active + footer_active if tok["value"].upper() != "AS"]
                
                # Option keywords that start a clause at depth 0
                OPTION_START_KEYWORDS = {
                    "RETURNS", "LANGUAGE", "STABLE", "VOLATILE", "IMMUTABLE", "STRICT", "PARALLEL", "SECURITY", "COST", "ROWS"
                }

                returns_str = ""
                lang_name = "plpgsql"
                other_options = []

                idx_opt = 0
                num_tokens = len(all_active)

                while idx_opt < num_tokens:
                    tok = all_active[idx_opt]
                    val_up = tok["value"].upper()
                    
                    if val_up == "RETURNS":
                        clause_toks = [tok]
                        idx_opt += 1
                        depth = 0
                        while idx_opt < num_tokens:
                            t_inner = all_active[idx_opt]
                            if t_inner["type"] == "PAREN" and t_inner["value"] == "(":
                                depth += 1
                            elif t_inner["type"] == "PAREN" and t_inner["value"] == ")":
                                depth -= 1
                                
                            if depth == 0 and t_inner["value"].upper() in OPTION_START_KEYWORDS:
                                break
                            clause_toks.append(t_inner)
                            idx_opt += 1
                        clause_str = content[clause_toks[0]["start"] : clause_toks[-1]["end"]].strip()
                        if clause_str.upper().startswith("RETURNS"):
                            returns_type = clause_str[7:].strip()
                        else:
                            returns_type = clause_str
                        returns_type_str = format_returns_table(returns_type, max_len)
                        returns_str = "RETURNS " + returns_type_str
                        
                    elif val_up == "LANGUAGE":
                        idx_opt += 1
                        if idx_opt < num_tokens:
                            lang_name = all_active[idx_opt]["value"]
                            idx_opt += 1
                        
                    elif val_up in ("STABLE", "VOLATILE", "IMMUTABLE", "STRICT"):
                        other_options.append(tok["value"])
                        idx_opt += 1
                        
                    elif val_up in ("PARALLEL", "SECURITY", "COST", "ROWS"):
                        clause_toks = [tok]
                        idx_opt += 1
                        if idx_opt < num_tokens:
                            clause_toks.append(all_active[idx_opt])
                            idx_opt += 1
                        clause_str = content[clause_toks[0]["start"] : clause_toks[-1]["end"]].strip()
                        other_options.append(clause_str)
                        
                    else:
                        other_options.append(tok["value"])
                        idx_opt += 1

                options_clause = "LANGUAGE " + lang_name
                if other_options:
                    options_clause += " " + " ".join(other_options)
                options_clause += " AS"
                
                if returns_str:
                    clauses = [returns_str, options_clause]
                else:
                    clauses = [options_clause]
                
                base_indent = ""
                line_start_char = content.rfind("\n", 0, t["start"])
                if line_start_char == -1:
                    prefix_str = content[0 : t["start"]]
                else:
                    prefix_str = content[line_start_char + 1 : t["start"]]
                if prefix_str.strip() == "":
                    base_indent = prefix_str
                    
                func_sig_cleaned = content[t["start"] : tokens[close_paren_idx]["end"]].strip()
                
                def indent_clause(clause_text: str) -> str:
                    lines = clause_text.splitlines()
                    res_lines = []
                    for line_idx, line in enumerate(lines):
                        if line_idx == 0:
                            res_lines.append(base_indent + "    " + line.strip())
                        else:
                            # Keep relative indentation of inner lines
                            res_lines.append(base_indent + "    " + line)
                    return "\n".join(res_lines)
                
                # Check if any clause is multiline or if the single line signature is too long
                has_multiline_clause = any("\n" in c for c in clauses)
                header_single = func_sig_cleaned + " " + " ".join(clauses)
                
                if not has_multiline_clause and len(base_indent + header_single) <= max_len and "\n" not in func_sig_cleaned:
                    expected_header = header_single
                else:
                    clauses_line = base_indent + "    " + " ".join(clauses)
                    if not has_multiline_clause and len(clauses_line) <= max_len and "\n" not in func_sig_cleaned:
                        expected_header = func_sig_cleaned + "\n" + clauses_line
                    else:
                        formatted_clauses = [indent_clause(c) for c in clauses]
                        expected_header = func_sig_cleaned + "\n" + "\n".join(formatted_clauses)
                        
                # Compare original text from CREATE start to end_offset with expected
                original_full_text = content[t["start"] : end_offset].rstrip()
                expected_full_text = (expected_header + "\n" + base_indent + body_tok["value"]).rstrip()
                if original_full_text != expected_full_text:
                    violations.append({
                        "start_offset": t["start"],
                        "end_offset": end_offset,
                        "replacement": expected_header + "\n" + base_indent + body_tok["value"],
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
