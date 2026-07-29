import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import extract

PDF = ("/Users/sinhongtan/Documents/HONG_PERSONAL/5. HONG_Documents/"
       "5. Certificate /정보처리기사/1_정보처리기사_필기/요약집/"
       "핵심요약집_2026_정보처리기사필기핵심요약.pdf")


class TestHelpers(unittest.TestCase):
    def test_normalize_replaces_bel_with_space(self):
        self.assertEqual(extract.normalize("가\x07나"), "가 나")

    def test_join_wrapped_merges_hangul_midword_without_space(self):
        # Source wraps 확실히 across a line break with no trailing space.
        self.assertEqual(extract.join_wrapped("각 단계를 확\n실히 매듭짓고"),
                         "각 단계를 확실히 매듭짓고")

    def test_join_wrapped_keeps_space_when_line_ends_with_space(self):
        self.assertEqual(extract.join_wrapped("Interaction Overview \nDiagram)"),
                         "Interaction Overview Diagram)")

    def test_split_bullets_splits_on_bullet_char(self):
        self.assertEqual(extract.split_bullets("•가나\n•다라"), ["가나", "다라"])

    def test_split_bullets_falls_back_to_lines_when_no_bullets(self):
        self.assertEqual(extract.split_bullets("도출\n(Elicitation)"),
                         ["도출 (Elicitation)"])

    def test_subject_for_boundaries(self):
        self.assertEqual(extract.subject_for(1),   (1, "소프트웨어 설계"))
        self.assertEqual(extract.subject_for(55),  (1, "소프트웨어 설계"))
        self.assertEqual(extract.subject_for(56),  (2, "소프트웨어 개발"))
        self.assertEqual(extract.subject_for(154), (3, "데이터베이스 구축"))
        self.assertEqual(extract.subject_for(155), (4, "프로그래밍 언어 활용"))
        self.assertEqual(extract.subject_for(216), (5, "정보시스템 구축 관리"))
        self.assertEqual(extract.subject_for(324), (5, "정보시스템 구축 관리"))


class TestExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = extract.extract(PDF)
        cls.by_id = {c["id"]: c for c in cls.cards}

    def test_finds_exactly_324_cards(self):
        self.assertEqual(len(self.cards), 324)

    def test_ids_are_contiguous_with_no_gaps_or_duplicates(self):
        ids = sorted(int(c["id"]) for c in self.cards)
        self.assertEqual(ids, list(range(1, 325)))

    def test_subject_one_has_55_cards(self):
        self.assertEqual(len([c for c in self.cards if c["subject"] == 1]), 55)

    def test_card_002_matches_source_exactly(self):
        c = self.by_id["002"]
        self.assertEqual(c["title"], "폭포수 모형")
        self.assertEqual(c["bullets"], [
            "이전 단계로 돌아갈 수 없다는 전제하에 각 단계를 확실히 매듭짓고 다음 단계를 진행하는 개발 방법론이다.",
            "보헴이 제시한 고전적 생명 주기 모형이다.",
            "요구사항을 반영하기 어렵다.",
        ])

    def test_card_001_last_bullet_is_not_truncated(self):
        # Regression: the next card's title used to eat the tail of this bullet.
        self.assertEqual(
            self.by_id["001"]["bullets"][2],
            "소프트웨어 개발 관련 사항 및 결과에 대한 명확한 기록을 유지해야 한다.")

    def test_two_line_title_is_rejoined(self):
        self.assertEqual(self.by_id["016"]["title"], "행위(Behavioral) 다이어그램의 종류")
        self.assertEqual(self.by_id["019"]["title"], "순차(Sequence) 다이어그램의 구성 요소")

    def test_no_card_body_leaks_the_next_cards_title(self):
        self.assertEqual(self.by_id["019"]["bullets"][-1], "메시지(Message)")

    def test_no_subject_marker_leaks_into_bullets(self):
        for c in self.cards:
            for b in c["bullets"]:
                self.assertNotRegex(b, r"\d과목")

    def test_no_control_or_private_use_characters_survive(self):
        # \x07 alone isn't enough: PDF extraction also leaves other C0
        # control bytes (mis-decoded graphics, e.g. card 204's Gantt
        # chart) and Private Use Area glyphs (decorative icon stand-ins,
        # e.g. the "예제" badge) embedded in title/bullet text.
        def offenders(s):
            return [ch for ch in s
                    if (ord(ch) < 0x20 and ch != "\n")
                    or 0xE000 <= ord(ch) <= 0xF8FF]

        bad = []
        for c in self.cards:
            if offenders(c["title"]):
                bad.append((c["id"], "title", c["title"]))
            for b in c["bullets"]:
                if offenders(b):
                    bad.append((c["id"], "bullet", b))
        self.assertEqual(bad, [], f"control/PUA characters survived: {bad}")

    def test_card_204_bullets_are_clean_and_nonempty(self):
        # Regression: card 204's Gantt-chart example mis-decodes as control
        # byte soup with no recoverable text (analogous to id 142's title
        # rendering as a graphic). Not parseable; bullet_overrides.json
        # supplies a hand-read replacement.
        bullets = self.by_id["204"]["bullets"]
        self.assertTrue(bullets)
        for b in bullets:
            self.assertTrue(b.strip())
            for ch in b:
                self.assertFalse(ord(ch) < 0x20 and ch != "\n")
                self.assertFalse(0xE000 <= ord(ch) <= 0xF8FF)

    def test_every_card_has_a_nonempty_title(self):
        empty = [c["id"] for c in self.cards if not c["title"].strip()]
        self.assertEqual(empty, [], f"cards with empty titles: {empty}")

    def test_title_does_not_leak_previous_cards_bullet_tail(self):
        # Regression: title_span could not tell a wrapped title from the
        # tail of the previous card's last bullet using text alone (e.g.
        # a bullet ending in '-함' or an arrow-diagram fragment doesn't
        # match any of its stop conditions). Font metadata fixes this.
        # Titles confirmed against the rendered PDF (pages 1-8, 20-22).
        self.assertEqual(self.by_id["014"]["title"], "UML의 주요 관계")
        self.assertEqual(self.by_id["022"]["title"], "사용자 인터페이스의 기본 원칙")
        self.assertEqual(self.by_id["039"]["title"], "모듈(Module)")
        self.assertEqual(self.by_id["055"]["title"], "미들웨어의 종류")
        self.assertEqual(self.by_id["146"]["title"], "CREATE TABLE")

    def test_kind_and_hook_start_null(self):
        self.assertIsNone(self.by_id["002"]["kind"])
        self.assertIsNone(self.by_id["002"]["hook"])

    def test_phase2_graphic_overrides_are_applied(self):
        # Regression: 059's PUSH/POP box diagram, 061's tree diagram, and
        # 066-068's sort-trace boxes draw their state transitions as
        # vector arrows with no text-stream representation; 062's worked
        # solution has no id marker of its own and, due to this PDF's
        # non-visual marker stream order on pages 9-10 (062's marker
        # precedes 061's, and the untagged solution text that follows
        # 061 in the stream actually belongs to 062's box), the raw
        # extractor misattributes it to 061. bullet_overrides.json
        # supplies hand-read replacements for all of these (same
        # mechanism as 062's original override and 204's Gantt chart).
        self.assertIn("PUSH A → PUSH B", self.by_id["059"]["bullets"][-1])
        self.assertNotIn("Preorder", " ".join(self.by_id["061"]["bullets"]))
        self.assertIn("ABDHIECFG", " ".join(self.by_id["062"]["bullets"]))
        self.assertIn("8 5 6 2 4 → 5 8 6 2 4", self.by_id["066"]["bullets"][2])
        self.assertIn("→", self.by_id["067"]["bullets"][2])
        self.assertIn("→", self.by_id["068"]["bullets"][2])


class TestMergeSafety(unittest.TestCase):
    def test_rerun_preserves_authored_kind_and_hook(self):
        existing = [{"id": "002", "kind": "mnemonic", "hook": "폭포는 되돌아 흐르지 않는다"}]
        fresh = [{"id": "002", "title": "폭포수 모형", "bullets": ["x"],
                  "kind": None, "hook": None}]
        merged = extract.merge(fresh, existing)
        self.assertEqual(merged[0]["kind"], "mnemonic")
        self.assertEqual(merged[0]["hook"], "폭포는 되돌아 흐르지 않는다")
        self.assertEqual(merged[0]["title"], "폭포수 모형")  # fresh title still wins


if __name__ == "__main__":
    unittest.main()
