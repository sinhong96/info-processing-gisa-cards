# InformationProcess-gisa-Cards Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working offline flashcard deck for 1과목 소프트웨어 설계 — 55 cards, each with a hand-authored SVG scene — as a single `study.html` file.

**Architecture:** Three separated stages. `extract.py` parses the master PDF into `cards.json` (deterministic, no creative content). `scenes/NNN.svg` holds one hand-authored scene body per point (creative, not templated). `build.py` wraps each scene in a shared header and inlines everything into one self-contained `study.html`.

**Tech Stack:** Python 3.14, `pypdf` (already installed), `unittest` (stdlib). Vanilla HTML/CSS/JS — no framework, no bundler, no CDN. Headless Chrome for render verification.

## Global Constraints

- **Python 3.14.** Dependencies limited to `pypdf` plus the standard library. Do not add `pytest`, `lxml`, `jinja2`, or any other package.
- **Tests run with `python3 -m unittest discover -s tests -v`.** No pytest.
- **Source PDF path** (note the space before `/정보처리기사`, it is real):
  `/Users/sinhongtan/Documents/HONG_PERSONAL/5. HONG_Documents/5. Certificate /정보처리기사/1_정보처리기사_필기/요약집/핵심요약집_2026_정보처리기사필기핵심요약.pdf`
- **324 points total, IDs 001–324, contiguous, no gaps, no duplicates.** Any code or test asserting missing IDs is wrong.
- **1과목 소프트웨어 설계 = IDs 001–055 = 55 cards.** Phase 1 authors scenes for these only.
- **`study.html` must be fully self-contained.** No `<script src>`, no `<link href>`, no webfonts, no network requests of any kind. It must work with Wi-Fi off and after AirDrop to an iPhone.
- **Korean text is preserved byte-exactly** from the source. Never paraphrase, abbreviate, or "clean up" a bullet.
- **`extract.py` must be safe to re-run.** It merges by `id` and never overwrites an authored `kind`, `hook`, or a title present in `title_overrides.json`.
- **Fixed palette** — every scene uses only these:
  | Role | Hex |
  | --- | --- |
  | Primary blue (badge, arrows, borders) | `#0b8ad4` |
  | Deep blue (text on light blue) | `#0a3d5c` |
  | Light blue fill | `#e8f4fc` |
  | Title bar gray | `#d3d5d8` |
  | Dark slate (structure, ground) | `#4a5560` |
  | Neutral fill | `#eef1f4` |
  | Neutral stroke | `#9aa4ae` |
  | Accent red (negation, hooks) | `#e03131` |
  | Warm fill / stroke (mnemonic medallions) | `#fff3d6` / `#e8b33a` |
  | Body text | `#1a1a1a` |
  | Text on dark fills | `#fff` |
- **Fixed card geometry.** All scenes are `viewBox="0 0 720 H"`. The header occupies the top 76px and is drawn by `build.py`, never by the scene file. Scene coordinates start at y=0 *below* the header.
- **Font stack in all SVG text:** `-apple-system, "Apple SD Gothic Neo", sans-serif`.

## Deferred from the spec

The spec lists **"Filter by 과목"** as a study-app feature. Phase 1 builds only 1과목, so a
subject filter would be a control with one option. `build.py` already takes the subject as
an argument and each card carries `subject` and `subjectName`, so the filter is a header
control added in Phase 2 when there is a second subject to switch to. Nothing in Phase 1
blocks it.

Everything else in the spec is covered by the tasks below.

---

### Task 1: `extract.py` — PDF to `cards.json`

**Files:**
- Create: `extract.py`
- Create: `tests/test_extract.py`
- Create: `title_overrides.json`
- Generate: `cards.json`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `extract.py::normalize(raw: str) -> str`
  - `extract.py::find_markers(text: str) -> list[re.Match]`
  - `extract.py::title_span(text: str, m: re.Match) -> tuple[str, int]`
  - `extract.py::join_wrapped(body: str) -> str`
  - `extract.py::split_bullets(body: str) -> list[str]`
  - `extract.py::subject_for(card_id: int) -> tuple[int, str]`
  - `extract.py::extract(pdf_path: str) -> list[dict]`
  - `cards.json`: a JSON array of dicts with keys `id` (str, zero-padded 3 digits), `subject` (int), `subjectName` (str), `title` (str), `bullets` (list[str]), `kind` (null), `hook` (null).

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract.py`:

```python
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

    def test_no_control_characters_survive(self):
        for c in self.cards:
            self.assertNotIn("\x07", c["title"])
            for b in c["bullets"]:
                self.assertNotIn("\x07", b)

    def test_every_card_has_a_nonempty_title(self):
        empty = [c["id"] for c in self.cards if not c["title"].strip()]
        self.assertEqual(empty, [], f"cards with empty titles: {empty}")

    def test_kind_and_hook_start_null(self):
        self.assertIsNone(self.by_id["002"]["kind"])
        self.assertIsNone(self.by_id["002"]["hook"])


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
```

Create `title_overrides.json` with the one title extraction cannot recover (ID 142 renders its title as a graphic). Its value is confirmed in Task 2; seed it now so the schema exists:

```json
{
  "142": "SAN(Storage Area Network)"
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'extract'`

- [ ] **Step 3: Write the implementation**

Create `extract.py`:

```python
#!/usr/bin/env python3
"""Parse the 정보처리기사 핵심요약집 master PDF into cards.json.

Deterministic. Contains no authored content. Safe to re-run: authored
fields (kind, hook) and title_overrides.json always win over fresh output.
"""
import json, os, re, sys
import pypdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = ("/Users/sinhongtan/Documents/HONG_PERSONAL/5. HONG_Documents/"
       "5. Certificate /정보처리기사/1_정보처리기사_필기/요약집/"
       "핵심요약집_2026_정보처리기사필기핵심요약.pdf")

# Page furniture that appears on every page and is never card content.
NOISE = {"초", "치기", "정보처리기사 핵심 요약", "시험에", "나오는 것만", "공부한다!"}

# Each point is anchored by its 3-digit id glued to the title, followed by
# the 초치기 logo. Matching bare \d{3} silently misses points.
MARKER = re.compile(r"(\d{3})\n초\n치기\n")

SUBJECT_RANGES = [
    (1, "소프트웨어 설계",      1,   55),
    (2, "소프트웨어 개발",      56,  100),
    (3, "데이터베이스 구축",    101, 154),
    (4, "프로그래밍 언어 활용", 155, 215),
    (5, "정보시스템 구축 관리", 216, 324),
]


def is_hangul(ch):
    return "가" <= ch <= "힣"


def normalize(raw):
    """The extractor emits BEL where the source uses a narrow space."""
    return raw.replace("\x07", " ")


def is_noise(line):
    s = re.sub(r"\s+", " ", line).strip()
    return (not s or s in NOISE or s.startswith("•")
            or bool(re.fullmatch(r"\d+", s)) or bool(re.search(r"\d과목$", s)))


def find_markers(text):
    return list(MARKER.finditer(text))


def title_span(text, m):
    """Return (title, offset_where_title_starts).

    Titles wrap onto at most two lines. Walk backwards from the id, stopping
    at page furniture, at a bullet, or at a line ending in '.', '다', or '음'
    — those endings mark body prose, not a title.
    """
    head = text[:m.start()]
    lines = head.split("\n")
    took, off = [], len(head)
    for ln in reversed(lines[-3:]):
        s = re.sub(r"\s+", " ", ln).strip()
        if is_noise(ln) or s.endswith(".") or s.endswith("다") or s.endswith("음"):
            break
        took.insert(0, s)
        off -= len(ln) + 1
        if len(took) == 2:
            break
    return " ".join(took).strip(), (off + 1 if took else len(head))


def join_wrapped(body):
    """Rejoin lines the PDF wrapped.

    Korean wraps mid-word, so joining with a space corrupts it. If the line
    already ends in whitespace, join with a space; else if both sides of the
    break are Hangul, join with nothing; else join with a space.
    """
    out = ""
    for ln in body.split("\n"):
        if not out:
            out = ln
        elif out.endswith(" "):
            out += ln
        elif out and ln and is_hangul(out[-1]) and is_hangul(ln[0]):
            out += ln
        else:
            out += " " + ln
    return out


def split_bullets(body):
    joined = join_wrapped(body)
    parts = [re.sub(r"\s+", " ", p).strip() for p in joined.split("•")]
    parts = [p for p in parts if p]
    return parts or [re.sub(r"\s+", " ", joined).strip()]


def subject_for(card_id):
    for num, name, lo, hi in SUBJECT_RANGES:
        if lo <= card_id <= hi:
            return num, name
    raise ValueError(f"id {card_id} outside all subject ranges")


def read_text(pdf_path):
    reader = pypdf.PdfReader(pdf_path)
    return normalize("\n".join((p.extract_text() or "") for p in reader.pages))


def extract(pdf_path=PDF):
    text = read_text(pdf_path)
    marks = find_markers(text)
    overrides = load_json(os.path.join(HERE, "title_overrides.json"), {})
    cards = []
    for i, m in enumerate(marks):
        # Body ends where the NEXT card's title begins, not at its id.
        end = title_span(text, marks[i + 1])[1] if i + 1 < len(marks) else len(text)
        body = text[m.end():end]
        keep = [l for l in body.split("\n")
                if l.strip().startswith("•") or not is_noise(l)]
        keep = [l for l in keep if not re.search(r"[가-힣 ]+\d과목\s*$", l)]
        cid = m.group(1)
        num, name = subject_for(int(cid))
        cards.append({
            "id": cid,
            "subject": num,
            "subjectName": name,
            "title": overrides.get(cid) or title_span(text, m)[0],
            "bullets": split_bullets("\n".join(keep)),
            "kind": None,
            "hook": None,
        })
    cards.sort(key=lambda c: int(c["id"]))
    return cards


def merge(fresh, existing):
    """Fresh extraction wins for title/bullets; authored fields are preserved."""
    prior = {c["id"]: c for c in existing}
    for c in fresh:
        old = prior.get(c["id"])
        if old:
            if old.get("kind") is not None:
                c["kind"] = old["kind"]
            if old.get("hook") is not None:
                c["hook"] = old["hook"]
    return fresh


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    out = os.path.join(HERE, "cards.json")
    cards = merge(extract(), load_json(out, []))
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(cards, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    per = {}
    for c in cards:
        per[c["subject"]] = per.get(c["subject"], 0) + 1
    print(f"wrote {len(cards)} cards to {out}")
    for num, name, _, _ in SUBJECT_RANGES:
        print(f"  {num}과목 {name}: {per.get(num, 0)}")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS, all tests, zero failures.

If `test_every_card_has_a_nonempty_title` fails on an id other than 142, add that id to `title_overrides.json` with the correct title read from the PDF, and re-run.

- [ ] **Step 5: Generate `cards.json` and confirm the counts**

Run: `python3 extract.py`
Expected output:

```
wrote 324 cards to .../cards.json
  1과목 소프트웨어 설계: 55
  2과목 소프트웨어 개발: 45
  3과목 데이터베이스 구축: 54
  4과목 프로그래밍 언어 활용: 61
  5과목 정보시스템 구축 관리: 109
```

- [ ] **Step 6: Verify re-running is non-destructive**

Run:
```bash
python3 -c "
import json
c=json.load(open('cards.json'))
c[1]['kind']='mnemonic'; c[1]['hook']='테스트'
json.dump(c,open('cards.json','w'),ensure_ascii=False,indent=2)
"
python3 extract.py
python3 -c "
import json
c={x['id']:x for x in json.load(open('cards.json'))}
assert c['002']['kind']=='mnemonic', 'kind was clobbered'
assert c['002']['hook']=='테스트', 'hook was clobbered'
print('merge is safe')
"
```
Expected: `merge is safe`

Then reset the probe: `python3 -c "
import json
c=json.load(open('cards.json'))
for x in c:
    if x['id']=='002': x['kind']=None; x['hook']=None
json.dump(c,open('cards.json','w'),ensure_ascii=False,indent=2)
"`

- [ ] **Step 7: Commit**

```bash
git add extract.py tests/test_extract.py title_overrides.json cards.json
git commit -m "feat: extract 324 cheatsheet points from master PDF into cards.json"
```

---

### Task 2: Verify 1과목 fidelity against the rendered PDF

**Files:**
- Modify: `title_overrides.json`
- Modify: `cards.json` (regenerated)
- Create: `docs/verification/phase1-fidelity.md`

**Interfaces:**
- Consumes: `cards.json` from Task 1.
- Produces: a `cards.json` whose 55 1과목 records are confirmed correct against the rendered pages, and `docs/verification/phase1-fidelity.md` recording what was checked.

This task exists because extracted text and rendered pages can disagree, and every downstream scene is authored *from* this text. An error here propagates into a card he memorizes wrong.

- [ ] **Step 1: Print the extracted 1과목 records for review**

Run:
```bash
python3 -c "
import json
for c in json.load(open('cards.json')):
    if c['subject']!=1: continue
    print(f\"[{c['id']}] {c['title']}\")
    for b in c['bullets']: print('   -', b)
    print()
" > /tmp/subject1.txt
wc -l /tmp/subject1.txt && head -40 /tmp/subject1.txt
```

- [ ] **Step 2: Read the rendered source pages**

1과목 occupies pages 1–8 of the master PDF. Use the Read tool on the PDF with `pages: "1-8"` — this renders the pages visually rather than re-extracting the text stream, which is the whole point of the check.

Compare every one of the 55 titles and their bullets against what is printed on the page.

- [ ] **Step 3: Record every discrepancy**

Create `docs/verification/phase1-fidelity.md`:

```markdown
# Phase 1 Fidelity Check — 1과목 소프트웨어 설계

**Date:** <fill in>
**Method:** `cards.json` records for IDs 001–055 compared against pages 1–8
of the master PDF, rendered visually (Read tool, `pages: "1-8"`), not
re-extracted.

**Result:** <N> of 55 correct. <M> corrections applied.

## Corrections applied

| ID | Field | Extracted | Correct | Fix |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... |

## Confirmed correct

IDs: <list>
```

Fill in the table with every discrepancy found. If a title is wrong, add it to `title_overrides.json`. If a *bullet* is wrong, that is an `extract.py` bug — fix the parser and add a regression test to `tests/test_extract.py`, do not hand-patch `cards.json`.

- [ ] **Step 4: Re-run extraction and tests**

Run:
```bash
python3 extract.py && python3 -m unittest discover -s tests -v
```
Expected: PASS, and the 1과목 count still reads 55.

- [ ] **Step 5: Commit**

```bash
git add title_overrides.json cards.json extract.py tests/test_extract.py docs/verification/phase1-fidelity.md
git commit -m "verify: confirm 1과목 titles and bullets against rendered PDF pages"
```

---

### Task 3: Classify the 55 cards and write their hooks

**Files:**
- Modify: `cards.json`
- Create: `classify.py`
- Create: `tests/test_classify.py`

**Interfaces:**
- Consumes: `cards.json` from Task 2.
- Produces: `cards.json` where all 55 1과목 records have `kind` set to `"diagram"` or `"mnemonic"` and a non-empty `hook` string.
- `classify.py::validate(cards: list[dict], subject: int) -> list[str]` returns a list of human-readable problems; empty list means valid.

`kind` and `hook` are authorship decisions, not computable. This task writes them by hand into `cards.json`; `classify.py` only *validates* that the authoring is complete and well-formed.

**Classification rule:**
- `diagram` — the point has inherent structure: an ordered process, a cycle, a hierarchy, a comparison, or a set of named components that relate to each other. Examples: 008 요구사항 개발 프로세스 (ordered process), 016 행위 다이어그램의 종류 (flat taxonomy).
- `mnemonic` — the point is a definition or a list of unrelated properties, with no structure to draw. Examples: 002 폭포수 모형, 001 소프트웨어 공학의 기본 원칙.

**Hook rule:** a short Korean memory aid, max 30 characters. For list-type points use interpunct-separated initial syllables (`의 · 단 · 용 · 존 · 피`). For definition points use a one-line image (`폭포는 되돌아 흐르지 않는다`). Never leave it empty.

- [ ] **Step 1: Write the failing test**

Create `tests/test_classify.py`:

```python
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

    def test_both_kinds_are_used(self):
        cards = [c for c in json.load(open(os.path.join(ROOT, "cards.json"),
                                           encoding="utf-8")) if c["subject"] == 1]
        kinds = {c["kind"] for c in cards}
        self.assertEqual(kinds, {"diagram", "mnemonic"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'classify'`

- [ ] **Step 3: Write `classify.py`**

```python
#!/usr/bin/env python3
"""Validate that a subject's cards are fully and correctly classified.

kind and hook are authored by hand in cards.json. This module does not
author them; it only reports what is missing or malformed.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VALID_KINDS = {"diagram", "mnemonic"}
MAX_HOOK = 30


def validate(cards, subject):
    problems = []
    for c in cards:
        if c.get("subject") != subject:
            continue
        cid = c.get("id", "???")
        kind = c.get("kind")
        if kind is None:
            problems.append(f"{cid}: kind is not set")
        elif kind not in VALID_KINDS:
            problems.append(f"{cid}: kind {kind!r} is not one of {sorted(VALID_KINDS)}")
        hook = (c.get("hook") or "").strip()
        if not hook:
            problems.append(f"{cid}: hook is empty")
        elif len(hook) > MAX_HOOK:
            problems.append(f"{cid}: hook is {len(hook)} chars, max is {MAX_HOOK}")
    return problems


def main():
    subject = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cards = json.load(open(os.path.join(HERE, "cards.json"), encoding="utf-8"))
    problems = validate(cards, subject)
    if problems:
        print(f"{len(problems)} problem(s) in {subject}과목:")
        for p in problems:
            print("  -", p)
        return 1
    n = len([c for c in cards if c["subject"] == subject])
    kinds = {}
    for c in cards:
        if c["subject"] == subject:
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print(f"{subject}과목: all {n} cards classified — {kinds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Author `kind` and `hook` for all 55 cards**

Read every 1과목 record in `cards.json` and set both fields by hand, applying the classification and hook rules above. Work through IDs 001–055 in order so none is skipped.

Three worked examples to match in style:

```json
{ "id": "001", "kind": "mnemonic", "hook": "기술 · 검증 · 기록" }
{ "id": "002", "kind": "mnemonic", "hook": "폭포는 되돌아 흐르지 않는다" }
{ "id": "008", "kind": "diagram",  "hook": "도 · 분 · 명 · 확" }
```

- [ ] **Step 5: Run the validator and the tests**

Run: `python3 classify.py 1 && python3 -m unittest discover -s tests -v`
Expected: `1과목: all 55 cards classified — {...}` followed by all tests passing.

- [ ] **Step 6: Commit**

```bash
git add classify.py tests/test_classify.py cards.json
git commit -m "feat: classify all 55 1과목 cards as diagram or mnemonic with memory hooks"
```

---

### Task 4: `build.py` and eight pilot scenes

**Files:**
- Create: `build.py`
- Create: `tests/test_build.py`
- Create: `scenes/001.svg`, `scenes/002.svg`, `scenes/006.svg`, `scenes/008.svg`, `scenes/016.svg`, `scenes/019.svg`, `scenes/021.svg`, `scenes/022.svg`
- Create: `templates/app.html`
- Generate: `study.html`

**Interfaces:**
- Consumes: `cards.json` from Task 3.
- Produces:
  - `build.py::scene_height(svg: str) -> int` — reads the height from the scene's `viewBox`.
  - `build.py::scene_inner(svg: str) -> str` — the markup between the outer `<svg>` tags.
  - `build.py::wrap_scene(card: dict, svg: str) -> str` — a complete `<svg>` with the standard header drawn on top and the scene body translated down by `HEADER_H`.
  - `build.py::build(cards: list[dict], subject: int) -> str` — the full `study.html` text.
  - `HEADER_H = 76` — every scene file's coordinates start below this.

Eight scenes, not one, because a single scene cannot prove the format works for both `kind` values, for short and tall scenes, and for a title long enough to test overflow.

**Scene file contract.** Each `scenes/NNN.svg` contains *only* the scene body — no header, no number badge, no title bar. `build.py` draws those. The outer element declares the scene's own height:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 300">
  <!-- scene content; y=0 is the top of the scene area, below the header -->
</svg>
```

- [ ] **Step 1: Write the failing test**

Create `tests/test_build.py`:

```python
import json, os, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOTS = ["001", "002", "006", "008", "016", "019", "021", "022"]


class TestSceneParsing(unittest.TestCase):
    SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 300">'
           '<rect x="1" y="2"/></svg>')

    def test_scene_height_read_from_viewbox(self):
        self.assertEqual(build.scene_height(self.SVG), 300)

    def test_scene_inner_strips_outer_svg_tags(self):
        self.assertEqual(build.scene_inner(self.SVG), '<rect x="1" y="2"/>')

    def test_wrap_scene_adds_header_height(self):
        card = {"id": "002", "title": "폭포수 모형"}
        out = build.wrap_scene(card, self.SVG)
        self.assertIn(f'viewBox="0 0 720 {300 + build.HEADER_H}"', out)

    def test_wrap_scene_translates_body_below_header(self):
        card = {"id": "002", "title": "폭포수 모형"}
        out = build.wrap_scene(card, self.SVG)
        self.assertIn(f'<g transform="translate(0,{build.HEADER_H})">', out)

    def test_wrap_scene_draws_id_and_title(self):
        card = {"id": "002", "title": "폭포수 모형"}
        out = build.wrap_scene(card, self.SVG)
        self.assertIn(">002<", out)
        self.assertIn("폭포수 모형", out)

    def test_wrap_scene_escapes_xml_special_chars_in_title(self):
        card = {"id": "017", "title": "겹화살괄호(<< >>)"}
        out = build.wrap_scene(card, self.SVG)
        self.assertIn("&lt;&lt; &gt;&gt;", out)
        self.assertNotIn("(<< >>)", out)


class TestPilotScenes(unittest.TestCase):
    def test_pilot_scene_files_exist(self):
        for cid in PILOTS:
            path = os.path.join(ROOT, "scenes", f"{cid}.svg")
            self.assertTrue(os.path.exists(path), f"missing {path}")

    def test_every_pilot_scene_declares_width_720(self):
        for cid in PILOTS:
            svg = open(os.path.join(ROOT, "scenes", f"{cid}.svg"), encoding="utf-8").read()
            self.assertRegex(svg, r'viewBox="0 0 720 \d+"', f"{cid} has a bad viewBox")

    def test_no_scene_draws_its_own_header(self):
        # The header is build.py's job. A scene drawing #0b8ad4 at y=14 is
        # duplicating it and will double up in the output.
        for cid in PILOTS:
            svg = open(os.path.join(ROOT, "scenes", f"{cid}.svg"), encoding="utf-8").read()
            self.assertNotIn('y="14" width="72" height="46"', svg,
                             f"{cid} draws its own number badge")

    def test_scenes_use_only_the_approved_palette(self):
        allowed = {"#0b8ad4", "#0a3d5c", "#e8f4fc", "#d3d5d8", "#4a5560",
                   "#eef1f4", "#9aa4ae", "#e03131", "#fff3d6", "#e8b33a",
                   "#1a1a1a", "#fff", "#ffffff"}
        for cid in PILOTS:
            svg = open(os.path.join(ROOT, "scenes", f"{cid}.svg"), encoding="utf-8").read()
            for hexcode in re.findall(r"#[0-9a-fA-F]{3,6}", svg):
                self.assertIn(hexcode.lower(), allowed, f"{cid} uses {hexcode}")


class TestBuild(unittest.TestCase):
    def test_build_emits_self_contained_html(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        self.assertNotIn("<script src", html)
        self.assertNotIn("<link ", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_build_includes_every_pilot_card_title(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        by_id = {c["id"]: c for c in cards}
        for cid in PILOTS:
            self.assertIn(by_id[cid]["title"], html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build'`

- [ ] **Step 3: Write `build.py`**

```python
#!/usr/bin/env python3
"""Assemble cards.json + scenes/*.svg into a single self-contained study.html."""
import html as html_mod
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HEADER_H = 76
FONT = "-apple-system,'Apple SD Gothic Neo',sans-serif"


def scene_height(svg):
    m = re.search(r'viewBox="0 0 720 (\d+)"', svg)
    if not m:
        raise ValueError("scene is missing a 'viewBox=\"0 0 720 H\"' attribute")
    return int(m.group(1))


def scene_inner(svg):
    m = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    if not m:
        raise ValueError("scene has no <svg> element")
    return m.group(1).strip()


def wrap_scene(card, svg):
    h = scene_height(svg)
    title = html_mod.escape(card["title"])
    return (
        f'<svg viewBox="0 0 720 {h + HEADER_H}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="{FONT}">'
        f'<rect x="24" y="14" width="72" height="46" rx="4" fill="#0b8ad4"/>'
        f'<text x="60" y="47" font-size="27" font-weight="800" fill="#fff" '
        f'text-anchor="middle" font-family="Helvetica">{card["id"]}</text>'
        f'<rect x="100" y="14" width="596" height="46" rx="4" fill="#d3d5d8"/>'
        f'<text x="122" y="46" font-size="24" font-weight="800" fill="#1a1a1a">{title}</text>'
        f'<g transform="translate(0,{HEADER_H})">{scene_inner(svg)}</g>'
        f'</svg>')


def load_scene(card_id):
    path = os.path.join(HERE, "scenes", f"{card_id}.svg")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def build(cards, subject):
    payload = []
    for c in sorted((c for c in cards if c["subject"] == subject),
                    key=lambda c: int(c["id"])):
        svg = load_scene(c["id"])
        if svg is None:
            continue
        payload.append({
            "id": c["id"], "title": c["title"], "bullets": c["bullets"],
            "kind": c["kind"], "hook": c["hook"],
            "subjectName": c["subjectName"], "svg": wrap_scene(c, svg),
        })
    tmpl = open(os.path.join(HERE, "templates", "app.html"), encoding="utf-8").read()
    data = json.dumps(payload, ensure_ascii=False)
    # </script> inside data would close the tag early.
    data = data.replace("</", "<\\/")
    return tmpl.replace("/*__CARDS__*/", data)


def main():
    subject = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cards = json.load(open(os.path.join(HERE, "cards.json"), encoding="utf-8"))
    out = os.path.join(HERE, "study.html")
    html = build(cards, subject)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    total = len([c for c in cards if c["subject"] == subject])
    drawn = html.count('<svg viewBox="0 0 720')
    print(f"wrote {out}: {drawn}/{total} cards have scenes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write `templates/app.html`**

```html
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>정보처리기사 암기 카드</title>
<style>
  :root{--bg:#f2f3f5;--fg:#1a1a1a;--card:#fff;--muted:#7a828a;--line:#e2e5e8;--blue:#0b8ad4}
  @media (prefers-color-scheme:dark){
    :root{--bg:#16181c;--fg:#e8eaed;--card:#1f2227;--muted:#9aa4ae;--line:#2c3036}
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,"Apple SD Gothic Neo",sans-serif;
       display:flex;flex-direction:column;min-height:100vh;min-height:100dvh}
  header{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
  header b{font-size:15px}
  .count{color:var(--muted);font-size:13px;margin-left:auto;font-variant-numeric:tabular-nums}
  button{font:inherit;font-size:13px;padding:6px 12px;border-radius:8px;border:1px solid var(--line);
         background:var(--card);color:var(--fg);cursor:pointer}
  button.on{background:var(--blue);border-color:var(--blue);color:#fff}
  main{flex:1;display:flex;align-items:center;justify-content:center;padding:16px}
  .card{background:var(--card);border-radius:16px;box-shadow:0 2px 18px rgba(0,0,0,.12);
        width:100%;max-width:760px;padding:22px;cursor:pointer;user-select:none}
  .front{text-align:center;padding:64px 20px}
  .front .num{font-size:44px;font-weight:800;color:var(--blue);font-variant-numeric:tabular-nums}
  .front .ttl{font-size:26px;font-weight:800;margin-top:10px;line-height:1.35}
  .front .tap{margin-top:32px;color:var(--muted);font-size:13px}
  .card svg{width:100%;height:auto;display:block}
  ul{margin:16px 0 0;padding-left:20px;line-height:1.65;font-size:15px}
  li{margin-bottom:7px}
  .hook{margin-top:14px;text-align:center;color:#e03131;font-weight:800;font-size:15px}
  footer{display:flex;gap:8px;padding:12px 16px;border-top:1px solid var(--line);justify-content:center;
         padding-bottom:calc(12px + env(safe-area-inset-bottom))}
  .empty{color:var(--muted);text-align:center;padding:60px 20px;line-height:1.7}
</style>

<header>
  <b id="subj">—</b>
  <button id="shuffle">🔀 섞기</button>
  <button id="hardonly">😵 어려운 것만</button>
  <button id="reset">↺ 초기화</button>
  <span class="count" id="count"></span>
</header>

<main><div class="card" id="card"></div></main>

<footer>
  <button id="prev">← 이전</button>
  <button id="flip">뒤집기 (space)</button>
  <button id="hard">😵 어려움</button>
  <button id="known">✅ 암기함</button>
  <button id="next">다음 →</button>
</footer>

<script>
const CARDS = /*__CARDS__*/;
const KEY = "gisa-cards-v1";
let mark = {};
try { mark = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { mark = {}; }
const save = () => localStorage.setItem(KEY, JSON.stringify(mark));

let deck = CARDS.slice(), i = 0, flipped = false, hardOnly = false;

function activeDeck() {
  return hardOnly ? deck.filter(c => mark[c.id] === "hard") : deck;
}

function render() {
  const d = activeDeck(), el = document.getElementById("card");
  if (!d.length) {
    el.innerHTML = '<div class="empty">어려움으로 표시한 카드가 없습니다.<br>“어려운 것만”을 다시 눌러 전체 카드로 돌아가세요.</div>';
    document.getElementById("count").textContent = "0 / 0";
    return;
  }
  if (i >= d.length) i = 0;
  if (i < 0) i = d.length - 1;
  const c = d[i];
  el.innerHTML = flipped
    ? c.svg + "<ul>" + c.bullets.map(b => "<li>" + esc(b) + "</li>").join("") + "</ul>"
        + (c.hook ? '<div class="hook">' + esc(c.hook) + "</div>" : "")
    : '<div class="front"><div class="num">' + c.id + '</div><div class="ttl">'
        + esc(c.title) + '</div><div class="tap">탭하거나 space를 눌러 뒤집기</div></div>';
  const known = CARDS.filter(x => mark[x.id] === "known").length;
  const badge = mark[c.id] === "hard" ? " 😵" : mark[c.id] === "known" ? " ✅" : "";
  document.getElementById("count").textContent =
    (i + 1) + " / " + d.length + badge + "   ·   암기 " + known + "/" + CARDS.length;
  document.getElementById("subj").textContent =
    CARDS.length ? CARDS[0].subjectName : "—";
}

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function go(n) { i += n; flipped = false; render(); }
function setMark(v) {
  const d = activeDeck(); if (!d.length) return;
  const id = d[i].id;
  mark[id] = mark[id] === v ? undefined : v;
  if (mark[id] === undefined) delete mark[id];
  save(); go(1);
}

document.getElementById("card").onclick = () => { flipped = !flipped; render(); };
document.getElementById("flip").onclick = e => { e.stopPropagation(); flipped = !flipped; render(); };
document.getElementById("next").onclick = () => go(1);
document.getElementById("prev").onclick = () => go(-1);
document.getElementById("hard").onclick = () => setMark("hard");
document.getElementById("known").onclick = () => setMark("known");
document.getElementById("shuffle").onclick = function () {
  for (let k = deck.length - 1; k > 0; k--) {
    const j = Math.floor(Math.random() * (k + 1));
    [deck[k], deck[j]] = [deck[j], deck[k]];
  }
  i = 0; flipped = false; render();
};
document.getElementById("hardonly").onclick = function () {
  hardOnly = !hardOnly; this.classList.toggle("on", hardOnly);
  i = 0; flipped = false; render();
};
document.getElementById("reset").onclick = function () {
  mark = {}; save(); deck = CARDS.slice(); i = 0; flipped = false;
  hardOnly = false; document.getElementById("hardonly").classList.remove("on");
  render();
};
addEventListener("keydown", e => {
  if (e.key === " ") { e.preventDefault(); flipped = !flipped; render(); }
  else if (e.key === "ArrowRight") go(1);
  else if (e.key === "ArrowLeft") go(-1);
});
let tx = 0;
addEventListener("touchstart", e => { tx = e.changedTouches[0].clientX; }, {passive: true});
addEventListener("touchend", e => {
  const dx = e.changedTouches[0].clientX - tx;
  if (Math.abs(dx) > 60) go(dx < 0 ? 1 : -1);
}, {passive: true});

render();
</script>
```

- [ ] **Step 5: Author the eight pilot scenes**

Create each file under `scenes/`. Header is omitted — `build.py` draws it. Coordinates start at y=0 below the header.

`scenes/002.svg` (mnemonic, tall) — the waterfall, already validated visually:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 354">
  <g>
    <rect x="60"  y="42"  width="118" height="17" rx="3" fill="#4a5560"/>
    <rect x="178" y="96"  width="118" height="17" rx="3" fill="#4a5560"/>
    <rect x="296" y="150" width="118" height="17" rx="3" fill="#4a5560"/>
    <rect x="414" y="204" width="118" height="17" rx="3" fill="#4a5560"/>
    <rect x="532" y="258" width="118" height="17" rx="3" fill="#4a5560"/>
  </g>
  <g fill="#0b8ad4" opacity=".45">
    <path d="M178 59 h20 v37 h-20 z"/>
    <path d="M296 113 h20 v37 h-20 z"/>
    <path d="M414 167 h20 v37 h-20 z"/>
    <path d="M532 221 h20 v37 h-20 z"/>
  </g>
  <text x="188" y="86"  font-size="17">💧</text>
  <text x="306" y="140" font-size="17">💧</text>
  <text x="424" y="194" font-size="17">💧</text>
  <text x="542" y="248" font-size="17">💧</text>
  <text x="119" y="35"  font-size="14" fill="#1a1a1a" text-anchor="middle" font-weight="700">요구분석</text>
  <text x="237" y="89"  font-size="14" fill="#1a1a1a" text-anchor="middle" font-weight="700">설계</text>
  <text x="355" y="143" font-size="14" fill="#1a1a1a" text-anchor="middle" font-weight="700">구현</text>
  <text x="473" y="197" font-size="14" fill="#1a1a1a" text-anchor="middle" font-weight="700">시험</text>
  <text x="591" y="251" font-size="14" fill="#1a1a1a" text-anchor="middle" font-weight="700">유지보수</text>
  <defs>
    <marker id="rb002" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
      <path d="M0,0 L9,4.5 L0,9 z" fill="#e03131"/>
    </marker>
  </defs>
  <path d="M600 240 C 470 174, 300 114, 150 24" stroke="#e03131" stroke-width="3.5"
        stroke-dasharray="9 7" fill="none" marker-end="url(#rb002)" opacity=".9"/>
  <text x="366" y="74" font-size="34" text-anchor="middle">🚫</text>
  <text x="366" y="21" font-size="17" fill="#e03131" text-anchor="middle" font-weight="800">이전 단계로 돌아갈 수 없다</text>
  <text x="52"  y="316" font-size="30">👴</text>
  <text x="92"  y="310" font-size="16" fill="#1a1a1a" font-weight="700">보헴(Boehm)</text>
  <text x="92"  y="332" font-size="14" fill="#9aa4ae">고전적 생명 주기 모형</text>
  <text x="470" y="310" font-size="16" fill="#1a1a1a" font-weight="700">🔒 요구사항 반영 어려움</text>
  <text x="470" y="332" font-size="14" fill="#9aa4ae">각 단계를 확실히 매듭짓고 진행</text>
</svg>
```

`scenes/008.svg` (diagram, short) — the four-stage process:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 190">
  <defs>
    <marker id="ab008" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
      <path d="M0,0 L9,4.5 L0,9 z" fill="#0b8ad4"/>
    </marker>
  </defs>
  <g>
    <rect x="40"  y="36" width="140" height="112" rx="10" fill="#e8f4fc" stroke="#0b8ad4" stroke-width="2.5"/>
    <text x="110" y="80"  font-size="30" text-anchor="middle">🔍</text>
    <text x="110" y="112" font-size="20" font-weight="800" text-anchor="middle" fill="#0a3d5c">도출</text>
    <text x="110" y="133" font-size="12" text-anchor="middle" fill="#9aa4ae">Elicitation</text>

    <rect x="212" y="36" width="140" height="112" rx="10" fill="#e8f4fc" stroke="#0b8ad4" stroke-width="2.5"/>
    <text x="282" y="80"  font-size="30" text-anchor="middle">🧩</text>
    <text x="282" y="112" font-size="20" font-weight="800" text-anchor="middle" fill="#0a3d5c">분석</text>
    <text x="282" y="133" font-size="12" text-anchor="middle" fill="#9aa4ae">Analysis</text>

    <rect x="384" y="36" width="140" height="112" rx="10" fill="#e8f4fc" stroke="#0b8ad4" stroke-width="2.5"/>
    <text x="454" y="80"  font-size="30" text-anchor="middle">📝</text>
    <text x="454" y="112" font-size="20" font-weight="800" text-anchor="middle" fill="#0a3d5c">명세</text>
    <text x="454" y="133" font-size="12" text-anchor="middle" fill="#9aa4ae">Specification</text>

    <rect x="556" y="36" width="140" height="112" rx="10" fill="#e8f4fc" stroke="#0b8ad4" stroke-width="2.5"/>
    <text x="626" y="80"  font-size="30" text-anchor="middle">✅</text>
    <text x="626" y="112" font-size="20" font-weight="800" text-anchor="middle" fill="#0a3d5c">확인</text>
    <text x="626" y="133" font-size="12" text-anchor="middle" fill="#9aa4ae">Validation</text>
  </g>
  <path d="M184 92 h22" stroke="#0b8ad4" stroke-width="3" marker-end="url(#ab008)"/>
  <path d="M356 92 h22" stroke="#0b8ad4" stroke-width="3" marker-end="url(#ab008)"/>
  <path d="M528 92 h22" stroke="#0b8ad4" stroke-width="3" marker-end="url(#ab008)"/>
</svg>
```

`scenes/001.svg` (mnemonic, three pillars):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 250">
  <path d="M70 56 L368 8 L666 56 Z" fill="#0b8ad4"/>
  <text x="368" y="46" font-size="18" font-weight="800" fill="#fff" text-anchor="middle">품질 좋은 소프트웨어</text>
  <rect x="112" y="64" width="124" height="140" rx="5" fill="#eef1f4" stroke="#9aa4ae" stroke-width="2"/>
  <text x="174" y="112" font-size="34" text-anchor="middle">🔧</text>
  <text x="174" y="146" font-size="16" font-weight="800" text-anchor="middle" fill="#1a1a1a">최신 기술</text>
  <text x="174" y="169" font-size="13" text-anchor="middle" fill="#9aa4ae">계속 적용</text>
  <rect x="306" y="64" width="124" height="140" rx="5" fill="#eef1f4" stroke="#9aa4ae" stroke-width="2"/>
  <text x="368" y="112" font-size="34" text-anchor="middle">🔬</text>
  <text x="368" y="146" font-size="16" font-weight="800" text-anchor="middle" fill="#1a1a1a">품질 검증</text>
  <text x="368" y="169" font-size="13" text-anchor="middle" fill="#9aa4ae">지속 검증</text>
  <rect x="500" y="64" width="124" height="140" rx="5" fill="#eef1f4" stroke="#9aa4ae" stroke-width="2"/>
  <text x="562" y="112" font-size="34" text-anchor="middle">📋</text>
  <text x="562" y="146" font-size="16" font-weight="800" text-anchor="middle" fill="#1a1a1a">명확한 기록</text>
  <text x="562" y="169" font-size="13" text-anchor="middle" fill="#9aa4ae">유지</text>
  <rect x="70" y="204" width="596" height="14" rx="3" fill="#4a5560"/>
</svg>
```

`scenes/006.svg` (mnemonic, five medallions) — this is the reference implementation of the medallion-row pattern that Task 6 reuses, so it is given in full:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 180">
  <circle cx="102" cy="74" r="42" fill="#fff3d6" stroke="#e8b33a" stroke-width="2.5"/>
  <text x="102" y="87"  font-size="36" text-anchor="middle">📢</text>
  <text x="102" y="140" font-size="17" font-weight="800" text-anchor="middle" fill="#1a1a1a">의사소통</text>
  <text x="102" y="160" font-size="11" text-anchor="middle" fill="#9aa4ae">Communication</text>

  <circle cx="235" cy="74" r="42" fill="#fff3d6" stroke="#e8b33a" stroke-width="2.5"/>
  <text x="235" y="87"  font-size="36" text-anchor="middle">🧊</text>
  <text x="235" y="140" font-size="17" font-weight="800" text-anchor="middle" fill="#1a1a1a">단순성</text>
  <text x="235" y="160" font-size="11" text-anchor="middle" fill="#9aa4ae">Simplicity</text>

  <circle cx="368" cy="74" r="42" fill="#fff3d6" stroke="#e8b33a" stroke-width="2.5"/>
  <text x="368" y="87"  font-size="36" text-anchor="middle">🦁</text>
  <text x="368" y="140" font-size="17" font-weight="800" text-anchor="middle" fill="#1a1a1a">용기</text>
  <text x="368" y="160" font-size="11" text-anchor="middle" fill="#9aa4ae">Courage</text>

  <circle cx="501" cy="74" r="42" fill="#fff3d6" stroke="#e8b33a" stroke-width="2.5"/>
  <text x="501" y="87"  font-size="36" text-anchor="middle">🙇</text>
  <text x="501" y="140" font-size="17" font-weight="800" text-anchor="middle" fill="#1a1a1a">존중</text>
  <text x="501" y="160" font-size="11" text-anchor="middle" fill="#9aa4ae">Respect</text>

  <circle cx="634" cy="74" r="42" fill="#fff3d6" stroke="#e8b33a" stroke-width="2.5"/>
  <text x="634" y="87"  font-size="36" text-anchor="middle">🔄</text>
  <text x="634" y="140" font-size="17" font-weight="800" text-anchor="middle" fill="#1a1a1a">피드백</text>
  <text x="634" y="160" font-size="11" text-anchor="middle" fill="#9aa4ae">Feedback</text>
</svg>
```

Author the remaining four (`016`, `019`, `021`, `022`) using the same two patterns:
- `016` 행위 다이어그램의 종류 — 7 items, so use a two-row grid of labelled chips rather than a single medallion row.
- `019` 순차 다이어그램의 구성 요소 — 5 medallions.
- `021` 사용자 인터페이스의 구분 — 3 wide panels (CLI / GUI / NUI), each with an icon and its one-line description.
- `022` 사용자 인터페이스의 기본 원칙 — 3 medallions (직관성 / 유효성 / 학습성).

`022` is included specifically because its bullets contain a `:` separator (`직관성 : 누구나 쉽게…`), which the front/back rendering must not mangle.

- [ ] **Step 6: Run the tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS, all tests.

- [ ] **Step 7: Build and confirm the count**

Run: `python3 build.py 1`
Expected: `wrote .../study.html: 8/55 cards have scenes`

- [ ] **Step 8: Commit**

```bash
git add build.py templates/app.html tests/test_build.py scenes/ study.html
git commit -m "feat: add build pipeline and eight pilot scenes for 1과목"
```

---

### Task 5: Verify the pilot renders in a real browser

**Files:**
- Create: `verify_render.py`
- Create: `docs/verification/phase1-render.md`

**Interfaces:**
- Consumes: `study.html` from Task 4.
- Produces: `verify_render.py` — screenshots `study.html` in headless Chrome and fails loudly if the page errors.

Writing a file is not evidence that it renders. This task exists so that "it works" is backed by a screenshot.

- [ ] **Step 1: Write `verify_render.py`**

```python
#!/usr/bin/env python3
"""Screenshot study.html in headless Chrome to prove it actually renders."""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def shoot(html_path, out_png, size="900,1200"):
    if not os.path.exists(CHROME):
        raise SystemExit(f"Chrome not found at {CHROME}")
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([
            CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
            f"--user-data-dir={profile}",
            f"--screenshot={out_png}", f"--window-size={size}",
            "--virtual-time-budget=3000",
            "file://" + html_path,
        ], check=True, capture_output=True, timeout=90)
    if not os.path.exists(out_png) or os.path.getsize(out_png) < 5000:
        raise SystemExit(f"screenshot missing or suspiciously small: {out_png}")
    return out_png


def main():
    html = os.path.join(HERE, "study.html")
    if not os.path.exists(html):
        raise SystemExit("study.html not found — run build.py first")
    out = os.path.join(HERE, "docs", "verification", "render-front.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shoot(html, out)
    print(f"rendered OK -> {out} ({os.path.getsize(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it**

Run: `python3 verify_render.py`
Expected: `rendered OK -> .../render-front.png (NNNNN bytes)`

- [ ] **Step 3: Look at the screenshot**

Use the Read tool on `docs/verification/render-front.png`. Confirm by eye:
- the card front shows the number and Korean title, not boxes or `?` glyphs
- no raw `&lt;` or `\x07` artifacts anywhere
- the footer buttons are visible and not overlapping

- [ ] **Step 4: Verify the flipped back and the emoji**

Run:
```bash
python3 - <<'EOF'
import os, re, verify_render
HERE=os.path.dirname(os.path.abspath(verify_render.__file__))
src=open(os.path.join(HERE,'study.html'),encoding='utf-8').read()
probe=src.replace('render();','flipped=true;render();')
p=os.path.join(HERE,'docs','verification','_flipped.html')
open(p,'w',encoding='utf-8').write(probe)
verify_render.shoot(p, os.path.join(HERE,'docs','verification','render-back.png'))
os.remove(p)
print('flipped screenshot OK')
EOF
```
Expected: `flipped screenshot OK`

Read `docs/verification/render-back.png` and confirm the SVG scene, the bullet list, and the red hook line all appear, and that the emoji render in color rather than as tofu boxes.

- [ ] **Step 5: Confirm the file is genuinely offline-safe**

Run:
```bash
grep -nE 'src=|href=|https?://|fetch\(|XMLHttpRequest' study.html || echo "no external references"
```
Expected: `no external references`

- [ ] **Step 6: Record the result**

Create `docs/verification/phase1-render.md` stating the Chrome version used (`"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version`), which screenshots were taken, and what was confirmed by eye. Embed both PNGs.

- [ ] **Step 7: Commit**

```bash
git add verify_render.py docs/verification/
git commit -m "verify: confirm study.html renders in headless Chrome with working emoji"
```

---

### Task 6: Author the remaining 47 scenes

**Files:**
- Create: `scenes/NNN.svg` for every 1과목 id not already done — that is 001–055 minus 001, 002, 006, 008, 016, 019, 021, 022.
- Modify: `tests/test_build.py`
- Generate: `study.html`

**Interfaces:**
- Consumes: `build.py`, `cards.json`, and the scene conventions established in Task 4.
- Produces: a complete `scenes/` directory for 1과목 — 55 files — and a `study.html` reporting `55/55`.

Work in batches of roughly ten, rebuilding and screenshotting after each batch. A malformed `viewBox` or an unbalanced tag in one file is far cheaper to find at card 12 than at card 55.

- [ ] **Step 1: Tighten the test to demand all 55**

In `tests/test_build.py`, replace the `PILOTS` list with a list derived from `cards.json`, and add a coverage test:

```python
PILOTS = [c["id"] for c in json.load(
    open(os.path.join(ROOT, "cards.json"), encoding="utf-8")) if c["subject"] == 1]


class TestFullCoverage(unittest.TestCase):
    def test_every_subject_one_card_has_a_scene(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        missing = [c["id"] for c in cards if c["subject"] == 1
                   and not os.path.exists(os.path.join(ROOT, "scenes", c["id"] + ".svg"))]
        self.assertEqual(missing, [], f"{len(missing)} scenes missing: {missing}")

    def test_every_scene_is_well_formed_xml(self):
        import xml.etree.ElementTree as ET
        for name in sorted(os.listdir(os.path.join(ROOT, "scenes"))):
            if not name.endswith(".svg"):
                continue
            path = os.path.join(ROOT, "scenes", name)
            try:
                ET.parse(path)
            except ET.ParseError as e:
                self.fail(f"{name} is not well-formed XML: {e}")

    def test_no_scene_is_absurdly_tall(self):
        for name in sorted(os.listdir(os.path.join(ROOT, "scenes"))):
            if not name.endswith(".svg"):
                continue
            svg = open(os.path.join(ROOT, "scenes", name), encoding="utf-8").read()
            h = build.scene_height(svg)
            self.assertLessEqual(h, 500, f"{name} is {h}px tall; keep scenes under 500")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `47 scenes missing: ['003', '004', ...]`

- [ ] **Step 3: Author scenes in batches of ten**

For each card, read its `title`, `bullets`, `kind`, and `hook` from `cards.json`, then draw it using the established patterns:

| Content shape | Pattern | Reference |
| --- | --- | --- |
| Ordered process (3–5 stages) | Box-and-arrow chain | `008` |
| Flat list of 3–5 named items | Medallion row | `006` |
| Flat list of 6–8 named items | Two-row chip grid | `016` |
| 2–4 items each with a description | Wide panel stack | `021` |
| Definition with a negation or constraint | Metaphor scene with 🚫 / 🔒 | `002` |
| Set of supporting principles | Pillars under a roof | `001` |
| Cycle that repeats | Ring of 4 arrows | new — follow `008` styling, arranged in a circle |

Rules that apply to every scene:
- `viewBox="0 0 720 H"` with H between 150 and 500.
- No header markup; `build.py` draws it.
- Every `<marker>` / `<defs>` id must be suffixed with the card id (`ab008`, `rb002`). Duplicate ids across inlined SVGs collide in a single HTML document and silently break arrowheads.
- Palette restricted to the approved list.
- Korean labels come verbatim from the card's bullets — do not invent terminology.

- [ ] **Step 4: Rebuild and screenshot after each batch**

Run:
```bash
python3 -m unittest discover -s tests -v && python3 build.py 1 && python3 verify_render.py
```
Expected after the final batch: tests pass, and `wrote .../study.html: 55/55 cards have scenes`

- [ ] **Step 5: Commit after each batch**

```bash
git add scenes/ study.html tests/test_build.py
git commit -m "feat: add scenes for 1과목 cards NNN-NNN"
```

---

### Task 7: End-to-end acceptance

**Files:**
- Create: `README.md`
- Modify: `docs/verification/phase1-render.md`

**Interfaces:**
- Consumes: everything above.
- Produces: a `README.md` explaining how to rebuild and how to get the deck onto a phone, and a verification record covering every interactive control.

- [ ] **Step 1: Exercise every control in a real browser**

Open the deck: `open study.html`

Confirm each of these by hand, and note the result:

| Control | Expected |
| --- | --- |
| Click card | flips front ↔ back |
| `space` | flips |
| `→` / `←` | moves forward / back, always landing on the front face |
| 🔀 섞기 | order changes, counter resets to 1 |
| 😵 어려움 | marks card, advances, badge shows 😵 |
| ✅ 암기함 | marks card, advances, 암기 count increases |
| 😵 어려운 것만 | deck shrinks to marked cards; button highlights |
| 어려운 것만 with nothing marked | shows the empty-state message, does not crash |
| ↺ 초기화 | clears all marks, restores full deck |
| Reload page | marks persist |

- [ ] **Step 2: Confirm persistence survives a reload**

In the browser console:
```js
localStorage.getItem("gisa-cards-v1")
```
Expected: a JSON object containing the ids marked in Step 1.

- [ ] **Step 3: Confirm it works with the network off**

Turn Wi-Fi off, reload `study.html`, and page through several cards. Everything must still render, including emoji and SVG scenes.

- [ ] **Step 4: Write `README.md`**

```markdown
# InformationProcess-gisa-Cards

Visual flashcards for the 정보처리기사 필기 exam. Each numbered point from the
핵심요약집 becomes a card: title on the front, a hand-drawn SVG scene plus the
source bullets on the back.

## Studying

Open `study.html` in any browser. It is fully self-contained and works offline.

To study on a phone: AirDrop `study.html` to it and open in Safari.

| Key | Action |
| --- | --- |
| space / tap | flip |
| → / ← , swipe | next / previous |

Progress is stored in the browser's `localStorage`. Clearing site data resets it.

## Rebuilding

```bash
python3 extract.py        # master PDF  -> cards.json
python3 classify.py 1     # check 1과목 kind/hook are complete
python3 build.py 1        # cards.json + scenes/ -> study.html
python3 verify_render.py  # screenshot it in headless Chrome
python3 -m unittest discover -s tests -v
```

`extract.py` is safe to re-run: it preserves authored `kind`/`hook` values and
applies `title_overrides.json`.

## Editing a card's picture

Every scene is one file: `scenes/NNN.svg`. Edit it and re-run `build.py`.
Nothing else is affected. Scene files contain no header — `build.py` draws the
number badge and title bar.

## Status

| 과목 | Cards | Scenes |
| --- | --- | --- |
| 1 소프트웨어 설계 | 55 | 55 ✅ |
| 2 소프트웨어 개발 | 45 | — |
| 3 데이터베이스 구축 | 54 | — |
| 4 프로그래밍 언어 활용 | 61 | — |
| 5 정보시스템 구축 관리 | 109 | — |
```

- [ ] **Step 5: Record the acceptance results**

Append the Step 1 table to `docs/verification/phase1-render.md` with a pass/fail against each row and the date.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/verification/phase1-render.md
git commit -m "docs: add README and Phase 1 acceptance results"
```

---

## Phase 1 Done Means

All of the following are true and were observed, not assumed:

1. `python3 -m unittest discover -s tests -v` passes with zero failures.
2. `python3 extract.py` reports 324 cards, 55 in 1과목.
3. `python3 classify.py 1` reports all 55 classified.
4. `python3 build.py 1` reports `55/55 cards have scenes`.
5. `python3 verify_render.py` produces a screenshot that was looked at.
6. `grep -nE 'src=|href=|https?://' study.html` finds nothing.
7. Every row of the Task 7 control table passed by hand.
8. `docs/verification/phase1-fidelity.md` records the title/bullet check against the rendered PDF.
