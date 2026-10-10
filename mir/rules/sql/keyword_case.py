from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

KEYWORDS = [
    "select", "from", "where", "join", "on", "and", "or", "limit",
    "group by", "order by", "insert", "into", "values", "update",
    "set", "delete", "create", "table", "drop", "alter", "index",
    "left", "right", "inner", "outer", "as", "having", "union",
    "with", "distinct", "recursive", "case", "when", "then", "else", "end",
    "lateral", "is", "is null", "in", "over", "partition"
]

FUNCTION_KEYWORD_AMBIGUITIES = {"left", "right"}

class KeywordCaseRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-keyword-case"
    description = "SQL keywords must be in uppercase."
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
        },
        {
            "violating": "SELECT item_id FROM sample_item WHERE owner_id is null;",
            "correct": "SELECT item_id FROM sample_item WHERE owner_id IS NULL;",
        },
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

    def _find_keyword_tokens(self, content: str, keywords: List[str]) -> List[dict]:
        tokens = tokenize_sql(content)
        active = [
            token for token in tokens
            if token["type"] not in {"WHITESPACE", "COMMENT", "STRING", "PARAM"}
        ]
        keyword_sequences = [tuple(keyword.split()) for keyword in keywords]
        sequences_by_first: Dict[str, List[tuple[str, ...]]] = {}
        for sequence in keyword_sequences:
            if sequence:
                sequences_by_first.setdefault(sequence[0], []).append(sequence)

        found = {}
        for index, token in enumerate(active):
            if token["type"] not in {"KEYWORD", "IDENTIFIER"}:
                continue
            for sequence in sequences_by_first.get(token["value"].lower(), ()):
                end = index + len(sequence)
                if end > len(active):
                    continue
                candidates = active[index:end]
                if not all(
                    candidate["type"] in {"KEYWORD", "IDENTIFIER"}
                    and candidate["value"].lower() == word
                    for candidate, word in zip(candidates, sequence)
                ):
                    continue
                for candidate_offset, candidate in enumerate(candidates):
                    active_index = index + candidate_offset
                    if (
                        candidate["value"].lower() in FUNCTION_KEYWORD_AMBIGUITIES
                        and active_index + 1 < len(active)
                        and active[active_index + 1]["type"] == "PAREN"
                        and active[active_index + 1]["value"] == "("
                    ):
                        continue
                    if candidate["value"] != candidate["value"].upper():
                        found[candidate["start"]] = candidate
        return [found[start] for start in sorted(found)]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        keywords = self._get_keywords(rule_config)
        violations_found = self._find_keyword_tokens(content, keywords)
        
        by_line: Dict[int, List[str]] = {}
        for token in violations_found:
            by_line.setdefault(token["line"], []).append(token["value"])
            
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
        tokens = self._find_keyword_tokens(content, self._get_keywords(rule_config))
        if not tokens:
            return content
        chars = list(content)
        for token in reversed(tokens):
            chars[token["start"]:token["end"]] = token["value"].upper()
        return "".join(chars)
