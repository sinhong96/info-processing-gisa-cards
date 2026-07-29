# Phase 2 Fidelity Check — 2과목 소프트웨어 개발

**Date:** 2026-07-29
**Method:** `cards.json` records for IDs 056–100 compared against pages 9–15
of the master PDF, rendered visually (Read tool, `pages: "9-15"`, plus a
focused re-render of page 11), not re-extracted. All 45 titles and all 45
bullet sets were read against the rendered pages, not just the 12 flagged
by the initial heuristic scan.

**Result:** 38 of 45 correct as extracted. 7 corrections applied, all via
`bullet_overrides.json` (no `extract.py` bug found in this range — every
discrepancy traces to content that is drawn as a graphic in the source PDF,
not present as parseable text, or to a PDF-authoring quirk where the answer
key has no id marker of its own; see "Judgment calls" below).

## Corrections applied

| ID | Field | Extracted | Correct | Fix |
| --- | --- | --- | --- | --- |
| 059 | bullets | POP bullet had the practice question and a garbled box-diagram dump appended (`...명령 예제 순서가... PUSH A PUSH B POP B ... A A A A A A A B BC BCD BCDA`) — the PUSH/POP box-and-arrow diagram has no clean text-stream form | 4 bullets: PUSH def, POP def, the question as its own bullet, and `연산 순서 : PUSH A → PUSH B → POP B → PUSH C → POP C → PUSH D → POP D → POP A` | `bullet_overrides.json` |
| 061 | bullets | Definition bullet had the tree-diagram's scrambled label dump appended (`...특수한 형태이다. Level 1 Level 2 Level 3 Level 4 → DepthK G C I L F H M J DB E A`), **and** the terminal-node bullet had all of card 062's worked traversal solution (Preorder/Inorder/Postorder steps, `∴ 방문 순서 : ABDHIECFG` etc.) appended | 3 bullets: definition (diagram noise dropped), Degree example, Terminal Node example — the misattributed 062 content removed entirely | `bullet_overrides.json` |
| 062 | bullets | Existing override had only the practice question, missing its worked solution | Question + 3 bullets giving each traversal's rule and result: `Preorder 운행법(Root → Left → Right)의 방문 순서 : ABDHIECFG`, `Inorder ... : HDIBEAFCG`, `Postorder ... : HIDEBFGCA` | `bullet_overrides.json` (existing 062 entry corrected, see below) |
| 066 | bullets | Array-state transitions had no `→` between before/after states (e.g. `1회전 : 8 5 6 2 4 5 8 6 2 4 두 번째 값을...`) — the arrow is a drawn glyph, not a text character, in this box style | `→` inserted between each pair of states, e.g. `1회전 : 8 5 6 2 4 → 5 8 6 2 4 두 번째 값을...` | `bullet_overrides.json` |
| 067 | bullets | Same missing-arrow problem across all 4 rounds' multi-state chains | `→` inserted between all chained states | `bullet_overrides.json` |
| 068 | bullets | Same missing-arrow problem across all 4 rounds' multi-state chains | `→` inserted between all chained states | `bullet_overrides.json` |
| 091 | bullets | Two-row complexity table merged into one 205-char run-on bullet (`O(1) 입력값(n)... O(nlog2n) 문제 해결에...`) — no `•` between rows in source | Split into 2 bullets, one per row, each ending with its example in parentheses | `bullet_overrides.json` |

## 062 override, before and after

Before (already present from Phase 1, unchanged since):
```json
"062": ["다음 트리를 Inorder, Preorder, Postorder 방법으로 운행했을 때 각 노드를 방문한 순서는?"]
```
After:
```json
"062": [
  "다음 트리를 Inorder, Preorder, Postorder 방법으로 운행했을 때 각 노드를 방문한 순서는?",
  "Preorder 운행법(Root → Left → Right)의 방문 순서 : ABDHIECFG",
  "Inorder 운행법(Left → Root → Right)의 방문 순서 : HDIBEAFCG",
  "Postorder 운행법(Left → Right → Root)의 방문 순서 : HIDEBFGCA"
]
```
The existing override was itself verified against the rendered page (page 9)
and the question text was already byte-correct — it was simply incomplete.

## Judgment calls (flagging per instructions, not blocking on them)

- **059, 066, 067, 068 arrows**: the `→` between array/stack states is a
  drawn arrow glyph in the source, absent from the text stream entirely
  (confirmed by dumping the raw stream between markers — no `→` or
  similar character present). Since the numbers alone read as an
  undifferentiated run of digits, I inserted `→` by hand to match what is
  visually printed, using the same "graphic that cannot be parsed" bucket
  the design doc already uses for 062/204. I did not fabricate content —
  every number was already present and correct; only the separator was
  added.
- **061/062 cross-contamination**: this is the one genuinely structural
  finding. On pages 9–10, `extract.py`'s marker-stream order is
  `..., 060, 062, 061, 063, ...` — id 062's marker physically precedes
  061's in the underlying PDF content stream, even though 061 is printed
  above 062 on the page. Card 062's worked solution (the Preorder/
  Inorder/Postorder steps) is printed as unheaded continuation text that
  spills onto page 10, with **no id marker of its own** separating it from
  061's box. Since `extract()` bounds each card's body using the *next
  marker in stream order*, and there is no marker between 061 and 063 in
  the stream, all of that unheaded solution text gets swept into 061's
  body — a real card-boundary bug, but one a text-position or font-metadata
  rule cannot resolve (there is no signal in the stream distinguishing
  "062's orphaned continuation" from "061's own content" — both are plain
  body-font prose with no marker). I judged this unfixable in `extract.py`
  without a fragile, single-purpose special case, and handled it via
  `bullet_overrides.json` for both ids instead, matching how 062's original
  override and 204's Gantt chart already handle unparseable/misattributed
  graphics. Flagging this explicitly per the "ask if ambiguous" instruction
  — I did not stop and ask because the resolution mechanism (hand override)
  is the one the project already established for structurally identical
  cases, but the underlying cause (stream order β‰  visual order across a
  page break, with an unmarked continuation) is worth knowing about.
- **066's missing "3회전" label**: the source PDF itself never prints a
  "3회전 :" label — the transition from `5 6 8 2 4` to `2 5 6 8 4` (which is
  logically the 3rd pass) appears directly under "2회전"'s explanation with
  no label of its own, then "4회전" follows. This matches the flag's
  suspicion exactly, but it is a defect in the **source material**, not in
  extraction — `cards.json` now reproduces exactly what is printed,
  including the omission. Not corrected, since inventing a "3회전" label
  that was never printed would violate "never paraphrase a bullet that
  extracted correctly" applied to a hand-read entry.

## Confirmed correct (checked against rendered pages, no changes)

056, 057, 058, 060, 063, 064, 065, 069, 070, 071, 072, 073, 074, 075, 076,
077, 078, 079, 080, 081, 082, 083, 084, 085, 086, 087, 088, 089, 090, 092,
093, 094, 095, 096, 097, 098, 099, 100

Notes on specific cases from the original 12-card flag list:
- **063, 064, 065** ("run-on >200 chars"): confirmed correct as single
  long bullets — the source has no `•` bullet characters in these three
  boxes at all, just continuous prose with inline `①②③` step markers, so
  `split_bullets`'s single-bullet fallback is the faithful result, not a
  bug.
- **080, 084, 093** ("single very short bullet"): confirmed legitimately
  terse — each source box is one plain, undotted sentence with no further
  bullets. `cards.json` matches byte-for-byte.

## Commands run

```
$ python3 extract.py
wrote 324 cards to /Users/sinhongtan/Claude/Projects/InformationProcess-gisa-Cards/cards.json
  1과목 소프트웨어 설계: 55
  2과목 소프트웨어 개발: 45
  3과목 데이터베이스 구축: 54
  4과목 프로그래밍 언어 활용: 61
  5과목 정보시스템 구축 관리: 109

$ python3 -m unittest discover -s tests -v
...
Ran 41 tests in 2.121s
OK
```
