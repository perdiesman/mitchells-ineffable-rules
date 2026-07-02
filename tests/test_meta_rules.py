import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.rules_loader import load_rules_for_language
from mir.engine.rules_help import get_supported_languages

class TestMetaRules(unittest.TestCase):
    def test_all_rules_examples(self):
        """
        Dynamically imports all rules across all discovered languages and verifies
        their violating and correct code examples self-contained in their class definition.
        """
        languages = get_supported_languages()
        self.assertTrue(len(languages) > 0, "No supported languages discovered.")
        
        rules_checked_count = 0
        
        for lang in languages:
            rules = load_rules_for_language(lang)
            for rule in rules:
                rule_id = rule.rule_id
                rule_config = dict(rule.default_config)
                
                # 1. Verify Violating Examples: check() must yield at least one violation
                for idx, example in enumerate(rule.examples_violating, start=1):
                    violations = rule.check(example, f"test_violating_{idx}.{lang}", rule_config)
                    self.assertTrue(
                        len(violations) > 0,
                        f"Expected at least one violation for rule '{rule_id}' ({lang}) in violating example #{idx}, but found none.\nCode:\n{example}"
                    )
                    
                    # If the rule is fixable, verify that calling fix() yields compliant code
                    if rule.is_fixable in ("yes", "sometimes"):
                        try:
                            fixed_content = rule.fix(example, f"test_violating_{idx}.{lang}", rule_config)
                            post_fix_violations = rule.check(fixed_content, f"test_violating_{idx}.{lang}", rule_config)
                            self.assertEqual(
                                len(post_fix_violations), 0,
                                f"Expected zero violations after running fix() on violating example #{idx} for rule '{rule_id}', but found {len(post_fix_violations)}.\nFixed Code:\n{fixed_content}"
                            )
                        except NotImplementedError:
                            # If is_fixable is 'sometimes' and the rule raises NotImplementedError for this specific example, that's fine.
                            pass
                
                # 2. Verify Correct Examples: check() must yield zero violations
                for idx, example in enumerate(rule.examples_correct, start=1):
                    violations = rule.check(example, f"test_correct_{idx}.{lang}", rule_config)
                    self.assertEqual(
                        len(violations), 0,
                        f"Expected zero violations for rule '{rule_id}' ({lang}) in correct example #{idx}, but found {len(violations)}.\nCode:\n{example}"
                    )
                    
                rules_checked_count += 1
                
        print(f"\n[Meta-Testing] Dynamically validated {rules_checked_count} rules using embedded class examples.")
