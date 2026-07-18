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
                
                self.assertTrue(hasattr(rule, "examples"), f"Rule '{rule_id}' has no 'examples' property.")
                
                for idx, ex in enumerate(rule.examples, start=1):
                    violating = ex.get("violating")
                    correct = ex.get("correct")
                    
                    self.assertIsNotNone(violating, f"Rule '{rule_id}' example #{idx} must define a 'violating' code block.")
                    
                    # 1. Verify Violating Example: check() must yield at least one violation
                    violations = rule.check(violating, f"test_violating_{idx}.{lang}", rule_config)
                    self.assertTrue(
                        len(violations) > 0,
                        f"Expected at least one violation for rule '{rule_id}' ({lang}) in violating example #{idx}, but found none.\nCode:\n{violating}"
                    )
                    
                    # 2. If the rule is fixable and 'correct' is defined, verify fix() results
                    if rule.is_fixable in ("yes", "sometimes") and correct:
                        try:
                            fixed_content = rule.fix(violating, f"test_violating_{idx}.{lang}", rule_config)
                            # Verify that fixed content matches the correct example exactly
                            self.assertEqual(
                                fixed_content, correct,
                                f"Expected fixed content for rule '{rule_id}' in example #{idx} to match the 'correct' example exactly.\nFixed:\n{fixed_content}\nExpected:\n{correct}"
                            )
                            # Verify that fixed content has 0 violations
                            post_fix_violations = rule.check(fixed_content, f"test_violating_{idx}.{lang}", rule_config)
                            self.assertEqual(
                                len(post_fix_violations), 0,
                                f"Expected zero violations after running fix() on violating example #{idx} for rule '{rule_id}', but found {len(post_fix_violations)}.\nFixed Code:\n{fixed_content}"
                            )
                            # Verify idempotency: running fix() again must yield the exact same content
                            refixed_content = rule.fix(fixed_content, f"test_violating_{idx}.{lang}", rule_config)
                            self.assertEqual(
                                refixed_content, fixed_content,
                                f"Idempotency failure for rule '{rule_id}' in example #{idx}: running fix() on the corrected content modified it again.\nFirst fix:\n{fixed_content}\nSecond fix:\n{refixed_content}"
                            )
                        except NotImplementedError:
                            pass
                            
                    # 3. Verify Correct Example if defined: check() must yield zero violations
                    if correct:
                        violations = rule.check(correct, f"test_correct_{idx}.{lang}", rule_config)
                        self.assertEqual(
                            len(violations), 0,
                            f"Expected zero violations for rule '{rule_id}' ({lang}) in correct example #{idx}, but found {len(violations)}.\nCode:\n{correct}"
                        )
                    
                # 4. Verify Additional Validations: check() must yield zero violations, and fix() must yield same string
                additional_vals = getattr(rule, "additional_validations", [])
                for idx, statement in enumerate(additional_vals, start=1):
                    violations = rule.check(statement, f"test_additional_{idx}.{lang}", rule_config)
                    self.assertEqual(
                        len(violations), 0,
                        f"Expected zero violations for rule '{rule_id}' ({lang}) in additional validation #{idx}, but found {len(violations)}.\nCode:\n{statement}"
                    )
                    if rule.is_fixable in ("yes", "sometimes"):
                        try:
                            fixed_content = rule.fix(statement, f"test_additional_{idx}.{lang}", rule_config)
                            self.assertEqual(
                                fixed_content, statement,
                                f"Expected fix() to leave additional validation #{idx} unchanged for rule '{rule_id}'.\nFixed:\n{fixed_content}\nOriginal:\n{statement}"
                            )
                        except NotImplementedError:
                            pass
                    
                rules_checked_count += 1
                
        print(f"\n[Meta-Testing] Dynamically validated {rules_checked_count} rules using embedded class examples.")

    def test_ruleset_idempotency(self):
        """
        Verifies that running all fixable rules for a language recursively
        on any of the examples or validations is idempotent.
        """
        languages = get_supported_languages()
        
        for lang in languages:
            rules = load_rules_for_language(lang)
            fixable_rules = [r for r in rules if r.is_fixable in ("yes", "sometimes")]
            
            # Helper to run all fixable rules recursively
            def run_fixers(content):
                curr = content
                for r in fixable_rules:
                    try:
                        curr = r.fix(curr, f"test.{lang}", r.default_config)
                    except NotImplementedError:
                        pass
                return curr
                
            for rule in rules:
                all_snippets = []
                for ex in rule.examples:
                    if ex.get("violating"):
                        all_snippets.append(ex["violating"])
                    if ex.get("correct"):
                        all_snippets.append(ex["correct"])
                additional_vals = getattr(rule, "additional_validations", [])
                all_snippets.extend(additional_vals)
                
                for idx, snippet in enumerate(all_snippets):
                    if not snippet.strip():
                        continue
                    
                    # Run fixers until content stabilizes (max 5 passes)
                    curr = snippet
                    for _ in range(5):
                        nxt = run_fixers(curr)
                        if nxt == curr:
                            break
                        curr = nxt
                        
                    # Now curr is the stable state. One more pass must yield the exact same content!
                    final_pass = run_fixers(curr)
                    self.assertEqual(
                        final_pass, curr,
                        f"Ruleset idempotency failure in language '{lang}' for rule '{rule.rule_id}' snippet:\n"
                        f"Stable state:\n{curr}\nNext pass:\n{final_pass}"
                    )

