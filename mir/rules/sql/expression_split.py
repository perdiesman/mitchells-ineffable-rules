from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql, get_token_depths, find_matching_paren, is_values_multi

class ExpressionSplitRule(BaseRule):
    rule_id = "IR-expression-split"
    description = "Long lines should split on function/expression parentheses, and optionally on additive/logical operators if still too long."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {
        "max_line_length": 100
    }
    config_options = {
        "max_line_length": {
            "default": 100,
            "description": "Line length threshold above which long expressions will be split."
        }
    }
    
    examples = [
        {
            "violating": "SELECT (date_trunc('hour', start_time) + date_part('minutes', start_time)::int / 15 * '15 Minutes'::interval) AS start_time;",
            "correct": "SELECT\n(\n    date_trunc('hour', start_time)\n    + date_part('minutes', start_time)::int\n    / 15\n    * '15 Minutes'::interval\n) AS start_time;"
        },
        {
            "violating": "SELECT min(date_trunc('hour', start_time) + date_part('minutes', start_time)::int / 15 * '15 Minutes'::interval) AS start_time;",
            "correct": "SELECT min(\n        date_trunc('hour', start_time)\n        + date_part('minutes', start_time)::int\n        / 15\n        * '15 Minutes'::interval\n    ) AS start_time;"
        },
        {
            "violating": "INSERT INTO t (c) VALUES (1), (2);",
            "correct": "INSERT INTO t (c) VALUES\n    (1),\n    (2);"
        }
    ]
    additional_validations = [
        "SELECT min(id) FROM users;",
        "SELECT (id) FROM users;",
        "INSERT INTO t (c) VALUES (1);",
        "INSERT INTO t (c) VALUES\n    (1),\n    (2);"
    ]

    def _get_edits(self, content: str, max_len: int) -> List[tuple]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        lines = content.splitlines()
        edits = []
        
        for line_no in range(1, len(lines) + 1):
            line = lines[line_no - 1]
            line_tokens = [t for t in tokens if t["line"] == line_no]
            active_tokens = [t for t in line_tokens if t["type"] not in ("WHITESPACE", "COMMENT")]
            if not active_tokens:
                continue
                
            is_line_val_multi = False
            for t in active_tokens:
                if t["type"] == "PAREN" and t["value"] == "(":
                    o_idx = tokens.index(t)
                    if is_values_multi(tokens, o_idx):
                        is_line_val_multi = True
                        break
                        
            if len(line) <= max_len and not is_line_val_multi:
                continue
                
            # Find base indent
            line_prefix = line[:len(line) - len(line.lstrip())]
            base_indent = line_prefix
            
            # Case 1: Split on first non-empty open parenthesis on this line
            open_tok = None
            for t in active_tokens:
                if t["type"] == "PAREN" and t["value"] == "(":
                    idx = tokens.index(t)
                    close_idx = find_matching_paren(tokens, idx)
                    if close_idx is not None:
                        active_between = [
                            tokens[k] for k in range(idx + 1, close_idx)
                            if tokens[k]["type"] not in ("WHITESPACE", "COMMENT")
                        ]
                        if active_between:
                            if len(line) <= max_len:
                                if is_values_multi(tokens, idx):
                                    open_tok = t
                                    break
                            else:
                                open_tok = t
                                break
                            
            if open_tok:
                open_idx = tokens.index(open_tok)
                close_idx = find_matching_paren(tokens, open_idx)
                if close_idx is not None:
                    # Detect if the parenthesis is function-like
                    prev_tok = None
                    for p_idx in range(open_idx - 1, -1, -1):
                        if tokens[p_idx]["type"] not in ("WHITESPACE", "COMMENT"):
                            prev_tok = tokens[p_idx]
                            break
                    is_func_like = False
                    is_val_multi = False
                    is_subquery = False
                    if prev_tok:
                        val_up = prev_tok["value"].upper()
                        if prev_tok["type"] == "IDENTIFIER" or val_up in ("VALUES", "TABLE", "COALESCE", "ROW_NUMBER", "NULLIF", "GREATEST", "LEAST", "IN", "ANY", "SOME"):
                            is_func_like = True
                        elif prev_tok["type"] == "KEYWORD" and val_up in ("JOIN", "FROM"):
                            is_subquery = True
                        is_val_multi = (val_up == "VALUES" and is_values_multi(tokens, open_idx))
                            
                    if is_subquery:
                        p_line_no = prev_tok["line"]
                        p_line = lines[p_line_no - 1]
                        p_base_indent = p_line[:len(p_line) - len(p_line.lstrip())]
                        content_indent = p_base_indent + "    "
                        close_indent = p_base_indent
                    elif is_func_like:
                        p_line_no = prev_tok["line"]
                        p_line = lines[p_line_no - 1]
                        p_base_indent = p_line[:len(p_line) - len(p_line.lstrip())]
                        content_indent = p_base_indent + "        "
                        close_indent = p_base_indent + "    "
                    else:
                        content_indent = base_indent + "    "
                        close_indent = base_indent
                        
                    # Split before open paren
                    ws_before_open = None
                    if open_idx - 1 >= 0 and tokens[open_idx - 1]["type"] == "WHITESPACE":
                        ws_before_open = tokens[open_idx - 1]
                    if is_subquery:
                        replacement = " "
                        if ws_before_open:
                            edits.append((ws_before_open["start"], ws_before_open["end"], replacement, line_no))
                        else:
                            edits.append((open_tok["start"], open_tok["start"], " ", line_no))
                    elif is_val_multi:
                        v_line_no = prev_tok["line"]
                        v_line = lines[v_line_no - 1]
                        val_base_indent = v_line[:len(v_line) - len(v_line.lstrip())]
                        edit_start_pre = ws_before_open["start"] if ws_before_open else open_tok["start"]
                        edit_end_pre = ws_before_open["end"] if ws_before_open else open_tok["start"]
                        edits.append((edit_start_pre, edit_end_pre, "\n" + val_base_indent + "    ", line_no))
                    else:
                        if is_func_like:
                            is_keyword_op = prev_tok["value"].upper() in ("VALUES", "TABLE", "IN", "ANY", "SOME")
                            replacement = " " if is_keyword_op else ""
                            if ws_before_open:
                                edits.append((ws_before_open["start"], ws_before_open["end"], replacement, line_no))
                            elif is_keyword_op:
                                edits.append((open_tok["start"], open_tok["start"], " ", line_no))
                        else:
                            edit_start_pre = ws_before_open["start"] if ws_before_open else open_tok["start"]
                            edit_end_pre = ws_before_open["end"] if ws_before_open else open_tok["start"]
                            edits.append((edit_start_pre, edit_end_pre, "\n" + base_indent, line_no))

                    if not is_val_multi:
                        # Split after open paren
                        ws_after = None
                        if open_idx + 1 < len(tokens) and tokens[open_idx + 1]["type"] == "WHITESPACE":
                            ws_after = tokens[open_idx + 1]
                        edit_start = open_tok["end"]
                        edit_end = ws_after["end"] if ws_after else open_tok["end"]
                        edits.append((edit_start, edit_end, "\n" + content_indent, line_no))
                        
                        # Split before close paren
                        close_tok = tokens[close_idx]
                        ws_before = None
                        if close_idx - 1 >= 0 and tokens[close_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[close_idx - 1]
                        edit_start = ws_before["start"] if ws_before else close_tok["start"]
                        edit_end = ws_before["end"] if ws_before else close_tok["start"]
                        edits.append((edit_start, edit_end, "\n" + close_indent, line_no))

                        # Check if we should also split operators/keywords/commas inside this parenthesis
                        base_depth = depths[open_idx] + 1
                        inner_str = "".join([tokens[idx]["value"] for idx in range(open_idx + 1, close_idx)]).strip()
                        if len(content_indent + inner_str) > max_len:
                            keywords = []
                            commas = []
                            operators = []
                            for idx in range(open_idx + 1, close_idx):
                                t = tokens[idx]
                                if depths[idx] == base_depth:
                                    if t["type"] == "OPERATOR" and t["value"] in ("+", "-", "||", "*", "/"):
                                        operators.append(t)
                                    elif t["type"] == "KEYWORD" and t["value"].upper() in ("AND", "OR", "ORDER", "PARTITION", "BY"):
                                        if t["value"].upper() == "BY":
                                            prev_active = None
                                            for p_idx in range(idx - 1, open_idx, -1):
                                                if tokens[p_idx]["type"] not in ("WHITESPACE", "COMMENT"):
                                                    prev_active = tokens[p_idx]
                                                    break
                                            if prev_active and prev_active["value"].upper() in ("ORDER", "GROUP", "PARTITION"):
                                                pass
                                            else:
                                                keywords.append(t)
                                        else:
                                            keywords.append(t)
                                    elif t["type"] == "COMMA":
                                        commas.append(t)
                                        
                            if keywords:
                                targets = [(t, "keyword") for t in keywords]
                            elif commas:
                                targets = [(t, "comma") for t in commas]
                            else:
                                targets = [(t, "operator") for t in operators]
                                
                            for op, t_type in targets:
                                op_idx = tokens.index(op)
                                if t_type == "keyword":
                                    ws_before = None
                                    if op_idx - 1 >= 0 and tokens[op_idx - 1]["type"] == "WHITESPACE":
                                        ws_before = tokens[op_idx - 1]
                                    edit_start_op = ws_before["start"] if ws_before else op["start"]
                                    edit_end_op = ws_before["end"] if ws_before else op["start"]
                                    edits.append((edit_start_op, edit_end_op, "\n" + content_indent, line_no))
                                elif t_type == "comma":
                                    ws_after = None
                                    if op_idx + 1 < len(tokens) and tokens[op_idx + 1]["type"] == "WHITESPACE":
                                        ws_after = tokens[op_idx + 1]
                                    edit_start_op = op["end"]
                                    edit_end_op = ws_after["end"] if ws_after else op["end"]
                                    edits.append((edit_start_op, edit_end_op, "\n" + content_indent, line_no))
                                else:
                                    ws_before = None
                                    if op_idx - 1 >= 0 and tokens[op_idx - 1]["type"] == "WHITESPACE":
                                        ws_before = tokens[op_idx - 1]
                                    edit_start_op = ws_before["start"] if ws_before else op["start"]
                                    edit_end_op = ws_before["end"] if ws_before else op["start"]
                                    edits.append((edit_start_op, edit_end_op, "\n" + content_indent, line_no))
                    if not is_val_multi:
                        continue
                    
            # Case 2: Split on operators/keywords/commas
            # Find enclosing parenthesis active at this line
            enclosing_open = None
            first_tok_idx = tokens.index(active_tokens[0])
            for idx in range(first_tok_idx - 1, -1, -1):
                t = tokens[idx]
                if t["type"] == "PAREN" and t["value"] == "(":
                    c_idx = find_matching_paren(tokens, idx)
                    if c_idx is not None and tokens[c_idx]["line"] >= line_no:
                        enclosing_open = t
                        break
                        
            if enclosing_open:
                eo_idx = tokens.index(enclosing_open)
                base_depth = depths[eo_idx] + 1
                
                prev_tok_eo = None
                for p_idx in range(eo_idx - 1, -1, -1):
                    if tokens[p_idx]["type"] not in ("WHITESPACE", "COMMENT"):
                        prev_tok_eo = tokens[p_idx]
                        break
                is_eo_func_like = False
                if prev_tok_eo:
                    val_up = prev_tok_eo["value"].upper()
                    if prev_tok_eo["type"] == "IDENTIFIER" or val_up in ("VALUES", "TABLE", "COALESCE", "ROW_NUMBER", "NULLIF", "GREATEST", "LEAST", "IN", "ANY", "SOME"):
                        is_eo_func_like = True
                        
                if is_eo_func_like:
                    eo_line_no = prev_tok_eo["line"]
                    eo_line = lines[eo_line_no - 1]
                    eo_base_indent = eo_line[:len(eo_line) - len(eo_line.lstrip())]
                    content_indent = eo_base_indent + "        "
                else:
                    eo_line_no = enclosing_open["line"]
                    eo_line = lines[eo_line_no - 1]
                    eo_base_indent = eo_line[:len(eo_line) - len(eo_line.lstrip())]
                    content_indent = eo_base_indent + "    "
            else:
                base_depth = 0
                content_indent = base_indent + "    "
                
            # Find operators/keywords/commas at base_depth on this line
            keywords = []
            commas = []
            operators = []
            for t in active_tokens[:-1]:
                t_idx = tokens.index(t)
                if depths[t_idx] == base_depth:
                    if t["type"] == "OPERATOR" and t["value"] in ("+", "-", "||", "*", "/"):
                        operators.append(t)
                    elif t["type"] == "KEYWORD" and t["value"].upper() in ("AND", "OR", "ORDER", "PARTITION", "BY"):
                        if t["value"].upper() == "BY":
                            prev_active = None
                            for prev_idx in range(t_idx - 1, -1, -1):
                                if tokens[prev_idx]["type"] not in ("WHITESPACE", "COMMENT"):
                                    prev_active = tokens[prev_idx]
                                    break
                            if prev_active and prev_active["value"].upper() in ("ORDER", "GROUP", "PARTITION"):
                                pass
                            else:
                                keywords.append(t)
                        else:
                            keywords.append(t)
                    elif t["type"] == "COMMA":
                         commas.append(t)
                         
            if keywords:
                targets = [(t, "keyword") for t in keywords]
            elif commas:
                targets = [(t, "comma") for t in commas]
            else:
                targets = [(t, "operator") for t in operators]
                
            if targets:
                for op, t_type in targets:
                    op_idx = tokens.index(op)
                    if t_type == "keyword":
                        ws_before = None
                        if op_idx - 1 >= 0 and tokens[op_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[op_idx - 1]
                        edit_start = ws_before["start"] if ws_before else op["start"]
                        edit_end = ws_before["end"] if ws_before else op["start"]
                        edits.append((edit_start, edit_end, "\n" + base_indent, line_no))
                    elif t_type == "comma":
                        ws_after = None
                        if op_idx + 1 < len(tokens) and tokens[op_idx + 1]["type"] == "WHITESPACE":
                            ws_after = tokens[op_idx + 1]
                        edit_start = op["end"]
                        edit_end = ws_after["end"] if ws_after else op["end"]
                        
                        is_values_comma = False
                        values_indent = ""
                        for p_idx in range(op_idx - 1, -1, -1):
                            if depths[p_idx] < base_depth:
                                break
                            if tokens[p_idx]["type"] == "KEYWORD" and tokens[p_idx]["value"].upper() == "VALUES":
                                v_tok = tokens[p_idx]
                                v_line_no = v_tok["line"]
                                v_line = lines[v_line_no - 1]
                                values_indent = v_line[:len(v_line) - len(v_line.lstrip())]
                                is_values_comma = True
                                break
                                
                        indent = values_indent + "    " if is_values_comma else content_indent
                        edits.append((edit_start, edit_end, "\n" + indent, line_no))
                    else:
                        ws_before = None
                        if op_idx - 1 >= 0 and tokens[op_idx - 1]["type"] == "WHITESPACE":
                            ws_before = tokens[op_idx - 1]
                        edit_start = ws_before["start"] if ws_before else op["start"]
                        edit_end = ws_before["end"] if ws_before else op["start"]
                        
                        line_starts_with_op = False
                        if active_tokens:
                            first_tok = active_tokens[0]
                            if first_tok["type"] == "OPERATOR" and first_tok["value"] in ("+", "-", "||", "*", "/"):
                                line_starts_with_op = True
                                
                        if line_starts_with_op:
                            edits.append((edit_start, edit_end, "\n" + base_indent, line_no))
                        else:
                            edits.append((edit_start, edit_end, "\n" + content_indent + "    ", line_no))
                    
        return [e for e in edits if content[e[0]:e[1]] != e[2]]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        max_len = rule_config.get("max_line_length", self.default_config["max_line_length"])
        violations = []
        lines = content.splitlines()
        edits = self._get_edits(content, max_len)
        
        reported_lines = set()
        for start, end, rep, line_no in edits:
            if line_no not in reported_lines:
                reported_lines.add(line_no)
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=line_no,
                        message=f"Line exceeds {max_len} characters and can be split on parenthesis or operators.",
                        offending_lines=[lines[line_no - 1] if line_no - 1 < len(lines) else ""],
                        is_fixable=True
                    )
                )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        max_len = rule_config.get("max_line_length", self.default_config["max_line_length"])
        edits = self._get_edits(content, max_len)
        if not edits:
            return content
            
        unique_edits = {}
        for start, end, rep, line_no in edits:
            unique_edits[(start, end)] = rep
            
        sorted_edits = sorted(
            [(start, end, rep) for (start, end), rep in unique_edits.items()],
            key=lambda x: x[0],
            reverse=True
        )
        
        chars = list(content)
        for start, end, new_text in sorted_edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
