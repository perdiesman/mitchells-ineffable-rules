from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql

PLPGSQL_KEYWORDS = {
    "DECLARE", "BEGIN", "EXCEPTION", "IF", "THEN", "ELSIF", "ELSE", "END",
    "LOOP", "WHILE", "FOR", "REVERSE", "FOREACH", "EXIT", "CONTINUE",
    "RAISE", "NOTICE", "WARNING", "INFO", "DEBUG", "LOG",
    "RETURN", "QUERY", "EXECUTE", "USING", "GET", "DIAGNOSTICS", "ROW_COUNT", "PERFORM",
    "CALL", "FOUND", "RECORD", "CONSTANT", "DEFAULT", "ALIAS",
    "RETURNS", "TRIGGER", "LANGUAGE", "STABLE", "VOLATILE", "IMMUTABLE",
    "LEAKPROOF", "STRICT", "SECURITY", "INVOKER", "DEFINER", "PARALLEL", "UNSAFE",
    "RESTRICTED", "SAFE", "COST", "ROWS", "BEFORE", "AFTER", "INSTEAD",
    "OF", "EACH", "ROW", "STATEMENT", "PROCEDURE", "FUNCTION", "OWNER", "TO", "CASCADE",
    "NEW", "OLD", "TG_OP", "TG_NAME", "TG_WHEN", "TG_LEVEL", "TG_RELID", "TG_RELNAME",
    "TG_TABLE_NAME", "TG_TABLE_SCHEMA", "TG_NARGS", "TG_ARGV"
}
PLPGSQL_MESSAGE_LEVELS = {"NOTICE", "WARNING", "INFO", "DEBUG", "LOG"}

class PlpgsqlKeywordCaseRule(BaseRule):
    embedded_safe = True
    rule_id = "IR-plpgsql-keyword-case"
    description = "Procedural PL/pgSQL keywords and trigger variables must be in uppercase."
    category = "routines"
    is_fixable = "yes"
    enabled_by_default = True
    exclude_recursive = True
    
    default_config = {}
    config_options = {}
    
    examples = [
        {
            "violating": "if new.manager then new.file_uploader = TRUE; end if;",
            "correct": "IF NEW.manager THEN NEW.file_uploader = TRUE; END IF;"
        }
    ]
    additional_validations = [
        "WITH info AS (SELECT item_id FROM sample_item) SELECT * FROM info;"
    ]

    def _check_tokens(self, tokens: List[dict], offset_delta: int, violations: List[dict]):
        previous_active = None
        for t in tokens:
            if t["type"] in ("IDENTIFIER", "KEYWORD"):
                val = t["value"]
                if val.startswith('"') and val.endswith('"'):
                    previous_active = t
                    continue
                upper_val = val.upper()
                # ``OF`` is also a perfectly valid unquoted relation alias.
                # PL/pgSQL only needs it cased as part of trigger syntax such
                # as ``UPDATE OF column_name``; treating every occurrence as
                # procedural syntax corrupts ordinary queries (for example,
                # ``FROM outage_fact of`` and ``of.item_id``).
                if (
                    upper_val == "OF"
                    and (
                        previous_active is None
                        or previous_active["value"].upper() != "UPDATE"
                    )
                ):
                    previous_active = t
                    continue
                if (
                    upper_val in PLPGSQL_MESSAGE_LEVELS
                    and (
                        previous_active is None
                        or previous_active["value"].upper() != "RAISE"
                    )
                ):
                    previous_active = t
                    continue
                if upper_val in PLPGSQL_KEYWORDS and val != upper_val:
                    if upper_val == "PLPGSQL":
                        continue
                    violations.append({
                        "token": t,
                        "start_offset": t["start"] + offset_delta,
                        "end_offset": t["end"] + offset_delta,
                        "replacement": upper_val,
                        "line": t["line"]
                    })
            if t["type"] not in ("WHITESPACE", "COMMENT"):
                previous_active = t

    def _find_violations(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        violations = []
        
        # Check outer tokens
        self._check_tokens(tokens, 0, violations)
        
        # Check tokens inside dollar-quoted function bodies
        for t in tokens:
            if t["type"] == "STRING" and t["value"].startswith("$"):
                val = t["value"]
                dollar_idx = val.find("$", 1)
                if dollar_idx == -1:
                    continue
                tag = val[:dollar_idx + 1]
                if not val.endswith(tag):
                    continue
                    
                body = val[len(tag):-len(tag)]
                body_lines = body.splitlines()
                first_line = None
                for line in body_lines:
                    if line.strip():
                        first_line = line
                        break
                if first_line is None:
                    continue
                    
                first_word = first_line.strip().split()[0].upper() if first_line.strip() else ""
                if first_word not in ("DECLARE", "BEGIN"):
                    continue
                    
                body_tokens = tokenize_sql(body)
                body_violations = []
                self._check_tokens(body_tokens, t["start"] + len(tag), body_violations)
                violations.extend(body_violations)
                    
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
                    message=f"Procedural PL/pgSQL keyword or variable '{item['token']['value']}' should be in uppercase.",
                    offending_lines=[lines[item["line"] - 1] if item["line"] - 1 < len(lines) else ""],
                    is_fixable=True
                )
            )
        return sorted(violations, key=lambda x: x.line_number)

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        offending = self._find_violations(content)
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
