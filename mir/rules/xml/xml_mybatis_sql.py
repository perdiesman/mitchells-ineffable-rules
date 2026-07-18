from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.rules_loader import load_rules_for_language
from mir.rules.xml.xml_utils import tokenize_xml

class XmlMybatisSqlRule(BaseRule):
    rule_id = "IR-xml-mybatis-sql"
    description = "Format embedded SQL inside MyBatis XML mapper files using SQL rules."
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="gov.ornl.gist.location.CountyMapper">\n    <select id="selectListByQuery">\n        select county.id from outage_data.county county\n    </select>\n</mapper>',
            "correct": '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="gov.ornl.gist.location.CountyMapper">\n    <select id="selectListByQuery">\n        SELECT county.id FROM outage_data.county county\n    </select>\n</mapper>'
        }
    ]
    additional_validations = [
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="gov.ornl.gist.location.CountyMapper">\n    <select id="selectListByQuery">\n        SELECT county.id FROM outage_data.county county\n    </select>\n</mapper>'
    ]

    def __init__(self) -> None:
        super().__init__()
        # Exclude structure-level and layout-level rules
        self.excluded_rule_ids = {
            "IR-indent", "IR-eof-newline", "IR-trailing-semicolon", 
            "IR-statement-semicolon", "IR-clause-alignment", 
            "IR-blank-lines", "IR-statement-blank-lines",
            "IR-from-multi", "IR-from-single", "IR-from-paren-layout",
            "IR-where-multi", "IR-where-single", "IR-column-layout",
            "IR-subquery-indent", "IR-subquery-compact", "IR-dollar-quote-alignment",
            "IR-table-field-spacing", "IR-trigger-layout", "IR-create-view-indent",
            "IR-function-body-indent", "IR-function-header-layout", "IR-raise-layout",
            "IR-plpgsql-block-indent", "IR-update-layout", "IR-case-layout",
            "IR-join-on-multi"
        }
        self.sql_rules = None

    def _get_sql_rules(self) -> List[BaseRule]:
        if self.sql_rules is None:
            all_rules = load_rules_for_language("sql")
            self.sql_rules = [r for r in all_rules if r.rule_id not in self.excluded_rule_ids]
        return self.sql_rules

    def _is_mybatis_file(self, content: str) -> bool:
        lower_content = content.lower()
        return "mybatis.org" in lower_content or "<mapper" in lower_content

    def _find_violations(self, content: str, file_path: str) -> List[dict]:
        if not self._is_mybatis_file(content):
            return []

        tokens = tokenize_xml(content)
        violations = []
        sql_rules_to_run = self._get_sql_rules()

        # Track tag stack to identify embedded SQL blocks
        tag_stack = []
        sql_tags = {"select", "insert", "update", "delete", "sql"}
        last_open_start = None

        for t in tokens:
            if t["type"] == "TAG_OPEN_START":
                # Extract tag name (strip leading '<')
                tag_name = t["value"][1:].lower()
                tag_stack.append(tag_name)
                last_open_start = tag_name
            elif t["type"] == "TAG_CLOSE_START":
                if tag_stack:
                    tag_stack.pop()
                last_open_start = None
            elif t["type"] == "TAG_END":
                if last_open_start is not None and t["value"] == "/>":
                    if tag_stack:
                        tag_stack.pop()
                last_open_start = None
            elif t["type"] == "TEXT":
                # Check if we are inside a target SQL tag
                is_embedded_sql = any(tag in sql_tags for tag in tag_stack)
                if is_embedded_sql and t["value"].strip():
                    sql_text = t["value"]
                    
                    # Run SQL rules on this block
                    for rule in sql_rules_to_run:
                        try:
                            sql_violations = rule.check(sql_text, file_path, {})
                            for sv in sql_violations:
                                # Map relative line of SQL text back to absolute line of XML file
                                abs_line = t["line"] + sv.line_number - 1
                                violations.append({
                                    "rule_id": rule.rule_id,
                                    "line": abs_line,
                                    "message": f"[Embedded SQL: {rule.rule_id}] {sv.message}",
                                    "is_fixable": sv.is_fixable
                                })
                        except Exception:
                            pass
        return violations

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        lines = content.splitlines()
        offending = self._find_violations(content, file_path)
        for v in offending:
            line_idx = v["line"] - 1
            offending_line = lines[line_idx] if line_idx < len(lines) else ""
            violations.append(Violation(
                rule_id=self.rule_id,
                line_number=v["line"],
                message=v["message"],
                offending_lines=[offending_line],
                is_fixable=v["is_fixable"]
            ))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        if not self._is_mybatis_file(content):
            return content

        tokens = tokenize_xml(content)
        sql_rules_to_run = self._get_sql_rules()
        edits = []

        tag_stack = []
        sql_tags = {"select", "insert", "update", "delete", "sql"}
        last_open_start = None

        for t in tokens:
            if t["type"] == "TAG_OPEN_START":
                tag_name = t["value"][1:].lower()
                tag_stack.append(tag_name)
                last_open_start = tag_name
            elif t["type"] == "TAG_CLOSE_START":
                if tag_stack:
                    tag_stack.pop()
                last_open_start = None
            elif t["type"] == "TAG_END":
                if last_open_start is not None and t["value"] == "/>":
                    if tag_stack:
                        tag_stack.pop()
                last_open_start = None
            elif t["type"] == "TEXT":
                is_embedded_sql = any(tag in sql_tags for tag in tag_stack)
                if is_embedded_sql and t["value"].strip():
                    sql_text = t["value"]
                    
                    fixed_sql = sql_text
                    for rule in sql_rules_to_run:
                        if rule.is_fixable in ("yes", "sometimes"):
                            try:
                                fixed_sql = rule.fix(fixed_sql, file_path, {})
                            except Exception:
                                pass
                    
                    if fixed_sql != sql_text:
                        edits.append((t["start"], t["end"], fixed_sql))

        if not edits:
            return content

        edits.sort(key=lambda x: x[0], reverse=True)
        chars = list(content)
        for start, end, new_text in edits:
            chars[start:end] = list(new_text)

        return "".join(chars)
