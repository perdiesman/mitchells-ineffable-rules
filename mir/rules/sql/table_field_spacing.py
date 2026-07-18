from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class TableFieldSpacingRule(BaseRule):
    rule_id = "IR-table-field-spacing"
    description = "Enforce exactly one space between column/field name and its data type."
    category = "schema-definition"
    is_fixable = "yes"
    enabled_by_default = True
    
    examples = [
        {
            "violating": "CREATE TEMP TABLE t (\n    a      integer,\n    b          text\n);",
            "correct": "CREATE TEMP TABLE t (\n    a integer,\n    b text\n);"
        }
    ]
    additional_validations = [
        "CREATE TABLE t (a INTEGER);"
    ]

    def _find_field_pairs(self, tokens: List[dict]) -> List[tuple]:
        active_tokens = [t for t in tokens if t["type"] not in ("WHITESPACE", "COMMENT")]
        token_to_active_idx = {id(t): idx for idx, t in enumerate(active_tokens)}
        n_active = len(active_tokens)
        pairs = []
        
        single_types = {
            "timestamp", "timestamptz", "time", "timetz", "varchar", "integer", "int",
            "bigint", "smallint", "text", "boolean", "bool", "numeric", "decimal",
            "json", "jsonb", "uuid", "date", "geometry", "real", "char", "character"
        }
        multi_words_start = {"timestamp", "time", "double", "character"}
        
        def is_type_start(tok):
            val = tok["value"].lower()
            return val in single_types or val in multi_words_start

        # Context 1: Function/Procedure Parameters and Returns
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
                    # Find parameter list
                    params_start = None
                    for sub_idx in range(idx + 1, n_active):
                        if active_tokens[sub_idx]["value"] == "(":
                            params_start = sub_idx
                            break
                    if params_start is not None:
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
                            param_tokens = active_tokens[params_start + 1 : params_end]
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
                                start_pt_idx = 0
                                if param[0]["value"].upper() in ("IN", "OUT", "INOUT", "VARIADIC"):
                                    start_pt_idx = 1
                                if start_pt_idx < len(param):
                                    type_start_pt = start_pt_idx + 1
                                    if type_start_pt < len(param):
                                        if is_type_start(param[type_start_pt]):
                                            pairs.append((param[type_start_pt - 1], param[type_start_pt]))
                                            
                    # Returns TABLE
                    for sub_idx in range(idx + 1, n_active):
                        if active_tokens[sub_idx]["value"].upper() == "RETURNS":
                            next_tok = active_tokens[sub_idx + 1]
                            if next_tok["value"].upper() == "TABLE":
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
                                                if is_type_start(col[1]):
                                                    pairs.append((col[0], col[1]))
                                                    
        # Context 2: DECLARE variable declarations
        for idx, t in enumerate(active_tokens):
            if t["value"].upper() == "DECLARE":
                declare_end = None
                for sub_idx in range(idx + 1, n_active):
                    if active_tokens[sub_idx]["value"].upper() in ("BEGIN", "EXCEPTION"):
                        declare_end = sub_idx
                        break
                if declare_end is not None:
                    declare_tokens = active_tokens[idx + 1 : declare_end]
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
                            if is_type_start(decl[1]):
                                pairs.append((decl[0], decl[1]))
                                
        # Context 3: CREATE [TEMP/TEMPORARY] TABLE table_name ( columns )
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
                    col_start = None
                    for sub_idx in range(table_idx + 1, n_active):
                        if active_tokens[sub_idx]["value"] == "(":
                            col_start = sub_idx
                            break
                    if col_start is not None:
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
                                        if is_type_start(col[1]):
                                            pairs.append((col[0], col[1]))
                                            
        return pairs

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        tokens = tokenize_sql(content)
        pairs = self._find_field_pairs(tokens)
        
        for name_tok, type_tok in pairs:
            start = name_tok["end"]
            end = type_tok["start"]
            spaces = content[start:end]
            if spaces != " ":
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        line_number=name_tok["line"],
                        message="There should be exactly one space between column/field name and its data type.",
                        offending_lines=[lines[name_tok["line"] - 1] if name_tok["line"] - 1 < len(lines) else ""],
                        is_fixable=True
                    )
                )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        tokens = tokenize_sql(content)
        pairs = self._find_field_pairs(tokens)
        if not pairs:
            return content
            
        edits = []
        for name_tok, type_tok in pairs:
            start = name_tok["end"]
            end = type_tok["start"]
            spaces = content[start:end]
            if spaces != " ":
                edits.append((start, end, " "))
                
        if not edits:
            return content
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, val in edits:
            chars[start:end] = list(val)
        return "".join(chars)
