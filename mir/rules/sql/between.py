from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

class BetweenRule(BaseRule):
    commit_profile = True
    commit_semantic_rewrite = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-between"
    description = "Standardize range predicate check of form 'a >= b AND a <= c' to 'a BETWEEN b AND c'."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "SELECT * FROM users WHERE age >= 18 AND age <= 65;",
            "correct": "SELECT * FROM users WHERE age BETWEEN 18 AND 65;"
        },
        {
            "violating": "SELECT * FROM users WHERE age <= 65 AND age >= 18;",
            "correct": "SELECT * FROM users WHERE age BETWEEN 18 AND 65;"
        },
        {
            "violating": "SELECT item_id FROM sample WHERE recorded_at >= timezone('utc', #{start}) AND recorded_at <= timezone('utc', #{end});",
            "correct": "SELECT item_id FROM sample WHERE recorded_at BETWEEN timezone('utc', #{start}) AND timezone('utc', #{end});"
        }
    ]
    additional_validations = [
        "SELECT item_id FROM sample WHERE recorded_at >= #{start} OR recorded_at <= #{end};",
        "SELECT item_id FROM sample WHERE lower_bound >= 1 AND upper_bound <= 10;",
        "SELECT item_id FROM sample WHERE recorded_at >= #{start} AND -- retain rationale\nrecorded_at <= #{end};",
    ]

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        active = [
            token for token in tokens if token["type"] not in ("WHITESPACE", "COMMENT")
        ]
        paren_matches = {}
        paren_stack = []
        for position, token in enumerate(active):
            if token["type"] != "PAREN":
                continue
            if token["value"] == "(":
                paren_stack.append(position)
            elif token["value"] == ")" and paren_stack:
                open_position = paren_stack.pop()
                paren_matches[open_position] = position

        def matching_close(open_position: int) -> int | None:
            return paren_matches.get(open_position)

        def parse_operand(position: int) -> tuple[str | None, int | None, int | None, int | None]:
            if position >= len(active):
                return None, None, None, None
            start_position = position
            if (
                active[position]["type"] == "OPERATOR"
                and active[position]["value"] in {"-", "+"}
            ):
                position += 1
                if position >= len(active) or active[position]["type"] != "NUMBER":
                    return None, None, None, None

            token = active[position]
            if token["type"] == "PAREN" and token["value"] == "(":
                end_position = matching_close(position)
                if end_position is None:
                    return None, None, None, None
            elif token["type"] in {"IDENTIFIER", "KEYWORD"}:
                end_position = position
                while (
                    end_position + 2 < len(active)
                    and active[end_position + 1]["type"] == "DOT"
                    and active[end_position + 2]["type"] in {"IDENTIFIER", "KEYWORD"}
                ):
                    end_position += 2
                if (
                    end_position + 1 < len(active)
                    and active[end_position + 1]["type"] == "PAREN"
                    and active[end_position + 1]["value"] == "("
                ):
                    close_position = matching_close(end_position + 1)
                    if close_position is None:
                        return None, None, None, None
                    end_position = close_position
            elif token["type"] in {"PARAM", "NUMBER", "STRING"}:
                end_position = position
            else:
                return None, None, None, None

            start_offset = active[start_position]["start"]
            end_offset = active[end_position]["end"]
            return (
                content[start_offset:end_offset].strip(),
                end_position + 1,
                start_offset,
                end_offset,
            )

        position = 0
        while position < len(active):
            left, operator_position, start_offset, _ = parse_operand(position)
            if left is None or operator_position is None or operator_position >= len(active):
                position += 1
                continue
            first_operator = active[operator_position]
            if first_operator["type"] != "OPERATOR" or first_operator["value"] not in {
                ">=", "<=",
            }:
                position += 1
                continue
            first_bound, and_position, _, _ = parse_operand(operator_position + 1)
            if first_bound is None or and_position is None or and_position >= len(active):
                position += 1
                continue
            conjunction = active[and_position]
            if conjunction["value"].upper() != "AND":
                position += 1
                continue
            repeated_left, second_operator_position, _, _ = parse_operand(and_position + 1)
            if (
                repeated_left is None
                or second_operator_position is None
                or second_operator_position >= len(active)
                or " ".join(repeated_left.lower().split()) != " ".join(left.lower().split())
            ):
                position += 1
                continue
            second_operator = active[second_operator_position]
            expected_second = "<=" if first_operator["value"] == ">=" else ">="
            if second_operator["type"] != "OPERATOR" or second_operator["value"] != expected_second:
                position += 1
                continue
            second_bound, next_position, _, end_offset = parse_operand(
                second_operator_position + 1
            )
            if second_bound is None or next_position is None or end_offset is None:
                position += 1
                continue
            if any(
                token["type"] == "COMMENT"
                and start_offset < token["end"]
                and token["start"] < end_offset
                for token in tokens
            ):
                position += 1
                continue
            lower = first_bound if first_operator["value"] == ">=" else second_bound
            upper = second_bound if first_operator["value"] == ">=" else first_bound
            violations.append({
                "start_offset": start_offset,
                "end_offset": end_offset,
                "line": active[position]["line"],
                "replacement": f"{left} BETWEEN {lower} AND {upper}",
            })
            position = next_position
            
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content)
        
        for item in offending:
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    line_number=item["line"],
                    message="Standardize range check to BETWEEN operator.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
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
