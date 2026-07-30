# Phase 3 Fidelity Check — 3과목/4과목/5과목

**Date:** 2026-07-30
**Method:** Every card's `cards.json` record compared against the rendered
master PDF page (Read tool, `pages` range per subject: 16-22, 23-32, 33-45),
not re-extracted. All flagged cards checked carefully; the rest skimmed
against the rendered pages in the same pass.

## Part 1 — known bugs

### 319's title / 318's bullet (Hanja mixed-font corruption)

Confirmed against page 44. Root cause: 319's title "인증(認證, Authentication)"
sets the Hanja "認證" in a third font (`YDVYGOStd14`, not `TITLE_FONT` and
not `ID_FONT`). `titles_by_font`'s visitor treats any non-title, non-id text
run as "not a title" and clears its accumulation buffer — so encountering
"認證" wiped out the "인증( " already buffered, leaving only ", Authentication)"
to survive as 319's font-derived title. The wiped "인증( 認證" text stayed in
the raw linear text stream, and `title_offset` (searching for the *corrupted*
title's characters) placed 318's body boundary after it, so it leaked into
318's last bullet.

Grepped the whole PDF for CJK Han characters (U+4E00-U+9FFF) and for
titles starting with punctuation or under 4 chars: **319/318 is the only
occurrence** of this bug — the Hanja gloss appears exactly once in the
entire document.

Fixed via `title_overrides.json["319"]` and a trimmed `bullet_overrides.json["318"]`.

### 146's run-on bullet

Confirmed: `표기 형식` box (CREATE TABLE syntax) has no bullet characters
between its 9 indented lines, so `split_bullets`'s single-bullet fallback
produced one long line. Fixed via `bullet_overrides.json` (one bullet per
source line) and additionally cropped as `kind: "image"` (see Part 3) since
the nested-bracket SQL syntax is exactly the kind of content that's
error-prone to hand-redraw.

## Part 2 — corrections table

| ID | Field | Extracted | Correct | Fix |
| --- | --- | --- | --- | --- |
| 319 | title | `", Authentication)"` | `인증(認證, Authentication)` | `title_overrides.json` |
| 318 | bullets | last bullet ended `...SetUID 파일 검사 등인증( 認證` | trimmed to end at `...등` | `bullet_overrides.json` |
| 146 | bullets | 1 run-on 200+ char bullet | split into 10 bullets, one per syntax line | `bullet_overrides.json` |
| 105 | bullets | E-R symbol table's 3 columns glued into one run-on bullet (`기호 기호 이름 의미사각형...`) | 5 bullets, one per symbol row | `bullet_overrides.json` |
| 119 | bullets | `기호 : ` with nothing after — the ⋈ (Join) glyph has no text-stream representation at all (confirmed: raw stream has literally nothing between `:` and the newline) | `기호 : ⋈` | `bullet_overrides.json` |
| 122 | bullets | small ∀/∃ table glued into the definition bullet, producing `주요 기호기호 구성 요소 설명 ∀ ...` | split into 3 bullets; `기호기호` duplication removed | `bullet_overrides.json` |
| 125 | bullets | normalization flow diagram flattened into 1 run-on bullet, losing the step structure | split into 6 bullets, one per NF transition | `bullet_overrides.json` |
| 126 | bullets | had 4 bullets — its own 2, plus 131's 2 orphaned "부분 완료"/"완료" transaction states | trimmed to its own 2 bullets | `bullet_overrides.json` |
| 131 | bullets | only 3 states (Active/Failed/Aborted) — missing Partially Committed/Committed, which had leaked into 126 | 5 bullets (all 5 transaction states) | `bullet_overrides.json` |
| 134 | bullets | had 6 bullets — its own 5, plus 137's orphaned "장애 투명성" (4th transparency type) | trimmed to its own 5 bullets | `bullet_overrides.json` |
| 137 | bullets | only 3 transparency types — missing 장애 투명성 (4th), which had leaked into 134 | 4 bullets (all 4 transparency types) | `bullet_overrides.json` |
| 135 | bullets | had 7 bullets — its own 5 partition types, plus 145's orphaned GRANT/REVOKE | trimmed to its own 5 bullets | `bullet_overrides.json` |
| 145 | bullets | only 3 bullets (intro, COMMIT, ROLLBACK) — missing GRANT/REVOKE, which had leaked into 135 | 5 bullets (intro + all 4 DCL commands) | `bullet_overrides.json` |
| 167 | bullets | its own 3-sentence ternary-operator example, with **all of 168's operator-precedence table** appended after it | trimmed to its own 3 bullets | `bullet_overrides.json` |
| 168 | bullets | **completely empty** — its marker is immediately followed by 169's marker with nothing between; its entire table had been swallowed into 167 | 9 bullets, one per operator-precedence row | `bullet_overrides.json` |
| 170 | bullets | its own printf() example, with **all of 171's 3 JAVA output-method examples** appended after it | trimmed to its own 3 bullets | `bullet_overrides.json` |
| 171 | bullets | **completely empty** — same swallow-into-170 pattern as 168 | 3 bullets (printf/print/println, each with its example) | `bullet_overrides.json` |
| 172 | bullets | both if/if-else code snippets glued onto the *last* bullet (bullet 3), leaving bullet 2 (조건이 참일 때만) with no code at all | bullet 2 and 3 each carry their own code snippet | `bullet_overrides.json` |

### The systemic pattern (flagging per "third bug class" instruction)

Every misattribution above (126/131, 134/137, 135/145, 167/168, 170/171) is
the **same bug class phase 2 already found and named** at 061/062: `extract()`
bounds a card's body using the *next marker in raw PDF content-stream order*,
not visual/reading order. When a card's content overflows its column with no
marker of its own between the overflow and the next card, and the underlying
PDF's stream order doesn't match visual layout at that point (common at
column and page breaks, and apparently more common in 3과목/4과목 than in
1과목/2과목 — 5 more instances found here vs. 1 in phase 2), the overflow
gets swept into whichever card's marker happens to precede it in the stream.
167/168 is the most severe instance found anywhere so far: 168 was left
**completely empty**, not just missing a tail.

I did not treat this as a new/unknown bug requiring escalation — it is the
same mechanism already documented and already has an established fix
pattern (hand override, verified against the rendered page). I checked
every card at a column-break position (last card in a column, first card
of the next) across all three subjects for this pattern; see the confirmed-
correct lists below and the 5과목 section for what else was checked.

## Confirmed correct (checked against rendered pages, no changes)

**3과목 flagged-list judgment calls:**
- **108, 127** ("short single bullet"): confirmed legitimately terse — each
  source box is one plain sentence with no `•` bullet character at all,
  matching `split_bullets`'s single-bullet fallback exactly (same pattern
  phase 2 confirmed for 080/084/093).

**3과목, all other cards (101-104, 106, 107, 109-118, 120, 121, 123, 124,
126-134 post-fix, 136, 138-145 post-fix, 147-152, 154):** read against
pages 16-22, byte-exact.

## 4과목 (pages 23-32)

The hard subject, as warned. 13 cards were flagged; the rest were skimmed
against the rendered pages, and I additionally checked **every card at a
page-column-break position** by hand (see "systemic pattern" above) since
that is exactly where 3과목's bugs clustered. This found 3 more
misattribution instances beyond the 13 flagged, two of which left the
swallowed card **completely empty** — the worst fidelity defects found in
this entire pass.

### Corrections table

| ID | Field | Extracted | Correct | Fix |
| --- | --- | --- | --- | --- |
| 167 | bullets | own 3-sentence ternary example, with all of 168's operator-precedence table appended | trimmed to own 3 bullets | `bullet_overrides.json` |
| 168 | bullets | **completely empty** (marker immediately followed by 169's marker) | 9 bullets, one per precedence row | `bullet_overrides.json`; cropped as `image` |
| 170 | bullets | own printf() example, with all of 171's 3 JAVA output-method examples appended | trimmed to own 3 bullets | `bullet_overrides.json` |
| 171 | bullets | **completely empty**, same pattern as 168 | 3 bullets (printf/print/println) | `bullet_overrides.json` |
| 172 | bullets | both if/if-else code snippets glued onto bullet 3; bullet 2 had no code at all | each bullet carries its own snippet | `bullet_overrides.json`; cropped as `image` |
| 189 | bullets | only the range-based for-loop example; the list-based example (189's own 2nd method) had leaked into 190 | 2 bullets (both for-loop methods) | `bullet_overrides.json` |
| 190 | bullets | had 2 bullets — its own while-loop example, plus 189's leaked list-based for-loop example | trimmed to its own 1 bullet | `bullet_overrides.json` |
| 180 | scene | `crop_card.py`'s single-page crop stopped at the bottom of page 26, missing the worked example (main() program + result) that overflows onto page 27's next column | hand-stitched a second crop from page 27's overflow region beneath the first, same technique `crop_card.py` uses | one-off script using `crop_card`'s own helpers (`render_page`/`crop`/`to_scene_svg`/`set_kind_image`); no hand-authored SVG |
| 201 | scene | same single-page-crop limitation — the ❶❷❸ trace explanation overflows onto page 31's next column | same stitching technique | same |

### The systemic pattern, continued

167/168 and 170/171 are **not** page-boundary overflows like 3과목's
instances — they're *same-page* stream-order scrambles (167 and 168 are
both on page 24's right column; the table's own marker/title text
apparently sits later in the raw content stream than the table's cells,
so `title_offset` never finds a stopping point and the whole table gets
swallowed by the preceding card, leaving 168 with zero body). 189/190 is
the page-boundary flavor (189 is the last card in page 28's right column;
its second example overflows onto page 29's left column, ahead of 190's
own badge).

I checked **every right-column-last card** in this subject (162, 169, 174,
180, 184, 189, 193, 201, 207) against the top of the next page's left
column for this exact overflow signature — 180, 189, and 201 had it; the
rest (162, 169, 174, 184, 193, 207) start their next page cleanly with no
stray text before the following badge.

`crop_card.py` itself has a real limitation surfaced by this: it locates
a card by its badge on a single page and can't see a continuation that
prints on the next page. For 180 and 201 (both chosen as `image` for
independent reasons — a worked program, and a worked numeric trace) I
wrote a one-off script reusing `crop_card`'s own `render_page`/`crop`/
`to_scene_svg`/`set_kind_image` helpers to crop both pages and stitch them
vertically, rather than hand-authoring an SVG. `crop_card.py` itself was
not modified.

### Confirmed correct (checked against rendered pages, no changes)

- **202, 214** ("short single bullet"): confirmed legitimately
  one-sentence definitions (스래싱, MQTT), no bullet character in the
  source box, matching the established single-bullet-fallback pattern.
- **173, 181, 186, 187, 191, 192** (flagged as code/worked-example heavy):
  all confirmed byte-correct as extracted — no misattribution — and
  classified `image` (see Part 3) given their content is a real code
  listing or worked trace with box diagrams.
- **All other cards (155-158, 160-166, 169, 174-179, 182-188, 190,
  193-200, 202-204, 206-215):** read against pages 23-32, byte-exact.
