from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class UnionLayoutRule(BaseRule):
    rule_id = "IR-union-layout"
    description = "Enforce that set operators (UNION, UNION ALL, INTERSECT, EXCEPT) are on their own line, aligned with the query block."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT id FROM t1 UNION ALL SELECT id FROM t2;",
            "correct": "SELECT id FROM t1\nUNION ALL\nSELECT id FROM t2;"
        }
    ]
    additional_validations = [
        "SELECT id FROM t1\nUNION\nSELECT id FROM t2;"
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        n = len(tokens)

        # Build map of token ID to index in tokens list
        token_to_idx = {id(t): idx for idx, t in enumerate(tokens)}

        # Filter active tokens
        active = []
        for t in tokens:
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                active.append(t)

        num_active = len(active)
        i = 0
        while i < num_active:
            t = active[i]
            if t["type"] == "KEYWORD" and t["value"].upper() in ("UNION", "INTERSECT", "EXCEPT"):
                # Check for UNION ALL
                is_all = False
                end_token = t
                active_skip = 1
                if t["value"].upper() == "UNION" and i + 1 < num_active:
                    next_active = active[i + 1]
                    if next_active["value"].upper() == "ALL":
                        is_all = True
                        end_token = next_active
                        active_skip = 2

                # Find preceding SELECT at same parenthesis depth
                # To trace depth, let's scan backwards in all tokens
                t_idx = token_to_idx[id(t)]
                depth = 0
                select_token = None
                for k in range(t_idx - 1, -1, -1):
                    tok = tokens[k]
                    if tok["type"] == "PAREN" and tok["value"] == ")":
                        depth += 1
                    elif tok["type"] == "PAREN" and tok["value"] == "(":
                        depth -= 1
                    elif depth == 0 and tok["type"] == "KEYWORD" and tok["value"].upper() == "SELECT":
                        select_token = tok
                        break

                # Determine expected indent of select_token
                indent_str = ""
                if select_token:
                    # Find beginning of line of select_token
                    sel_idx = token_to_idx[id(select_token)]
                    line_start = sel_idx
                    for k in range(sel_idx - 1, -1, -1):
                        if "\n" in tokens[k]["value"]:
                            line_start = k + 1
                            break
                        if k == 0:
                            line_start = 0
                            break
                    # The indent is any leading whitespace on this line
                    leading = []
                    for k in range(line_start, sel_idx):
                        if tokens[k]["type"] == "WHITESPACE":
                            leading.append(tokens[k]["value"])
                        else:
                            break
                    # Extract last line's indent if multiline whitespace
                    indent_parts = "".join(leading).split("\n")
                    indent_str = indent_parts[-1] if indent_parts else ""

                # Check before the operator: is there a newline?
                # We check the tokens between the preceding active token and our operator
                prev_active_idx = token_to_idx[id(active[i - 1])] if i > 0 else 0
                before_tokens = tokens[prev_active_idx + 1 : t_idx]
                before_str = "".join(tok["value"] for tok in before_tokens)
                has_newline_before = "\n" in before_str

                # Check after the operator: is there a newline?
                next_active_idx = token_to_idx[id(active[i + active_skip])] if i + active_skip < num_active else n
                after_tokens = tokens[token_to_idx[id(end_token)] + 1 : next_active_idx]
                after_str = "".join(tok["value"] for tok in after_tokens)
                has_newline_after = "\n" in after_str

                # If either is missing, we flag a violation
                if not has_newline_before or not has_newline_after:
                    # The replacement range goes from preceding active token end to next active token start
                    start_offset = tokens[prev_active_idx]["end"] if i > 0 else 0
                    end_offset = tokens[next_active_idx]["start"] if i + active_skip < num_active else n
                    
                    operator_str = "UNION ALL" if is_all else t["value"]
                    replacement = f"\n{indent_str}{operator_str}\n{indent_str}"

                    violations.append({
                        "token": t,
                        "line": t["line"],
                        "start_offset": start_offset,
                        "end_offset": end_offset,
                        "replacement": replacement,
                        "message": f"Set operator '{operator_str}' on line {t['line']} must be on its own line and aligned."
                    })

                i += active_skip
                continue
            i += 1

        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        for v in offending:
            line_idx = v["line"] - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=v["line"],
                message=v["message"],
                offending_lines=[offending_line],
                is_fixable=True
            ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
        if not offending:
            return content
            
        edits = []
        for item in offending:
            edits.append((item["start_offset"], item["end_offset"], item["replacement"]))
            
        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)
            
        return "".join(chars)
