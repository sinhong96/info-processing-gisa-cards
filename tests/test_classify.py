import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import classify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestValidate(unittest.TestCase):
    def test_flags_missing_kind(self):
        bad = [{"id": "001", "subject": 1, "kind": None, "hook": "가"}]
        self.assertTrue(any("001" in p and "kind" in p
                            for p in classify.validate(bad, 1)))

    def test_flags_bad_kind_value(self):
        bad = [{"id": "001", "subject": 1, "kind": "picture", "hook": "가"}]
        self.assertTrue(any("001" in p for p in classify.validate(bad, 1)))

    def test_flags_missing_hook(self):
        bad = [{"id": "001", "subject": 1, "kind": "diagram", "hook": ""}]
        self.assertTrue(any("001" in p and "hook" in p
                            for p in classify.validate(bad, 1)))

    def test_flags_overlong_hook(self):
        bad = [{"id": "001", "subject": 1, "kind": "diagram", "hook": "가" * 31}]
        self.assertTrue(any("001" in p for p in classify.validate(bad, 1)))

    def test_accepts_valid_card(self):
        good = [{"id": "001", "subject": 1, "kind": "diagram", "hook": "기술 · 검증 · 기록"}]
        self.assertEqual(classify.validate(good, 1), [])

    def test_ignores_other_subjects(self):
        other = [{"id": "060", "subject": 2, "kind": None, "hook": None}]
        self.assertEqual(classify.validate(other, 1), [])


class TestSubjectOneIsFullyClassified(unittest.TestCase):
    def test_all_55_cards_classified(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        problems = classify.validate(cards, 1)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_drawn_kinds_are_both_used(self):
        """A subject should use both drawn styles, not collapse onto one.

        "image" is also valid — those cards are crops of the source page for
        content the book draws rather than writes — so this checks the two
        hand-drawn kinds are present, not that they are the only ones.
        """
        cards = [c for c in json.load(open(os.path.join(ROOT, "cards.json"),
                                           encoding="utf-8")) if c["subject"] == 1]
        kinds = {c["kind"] for c in cards}
        self.assertLessEqual({"diagram", "mnemonic"}, kinds)
        self.assertLessEqual(kinds, {"diagram", "mnemonic", "image"})


if __name__ == "__main__":
    unittest.main()
