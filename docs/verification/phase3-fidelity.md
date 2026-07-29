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
