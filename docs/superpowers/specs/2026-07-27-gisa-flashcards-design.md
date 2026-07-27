# InformationProcess-gisa-Cards — Design

**Date:** 2026-07-27
**Status:** Approved

## Problem

Sin Hong is preparing for the 정보처리기사 필기 exam. He has the official 핵심요약집
cheatsheets as PDFs, but they are dense walls of Korean bullet text. Text-only bullets are
hard to memorize; he wants a visual hook for every numbered point, packaged as flashcards
he can actually study with.

## Source Material

Located at:

```
/Users/sinhongtan/Documents/HONG_PERSONAL/5. HONG_Documents/5. Certificate /정보처리기사/1_정보처리기사_필기/요약집/
```

| File | Pages | Role |
| --- | --- | --- |
| `핵심요약집_2026_정보처리기사필기핵심요약.pdf` | 45 | **Master — canonical source.** Contains all 5 과목. |
| `1_소프트웨어_설계_핵심요약집.pdf` | 4 | Subject extract (001–055) |
| `2_소프트웨어_개발_핵심요약집.pdf` | 4 | Subject extract (056–100) |
| `3_데이터베이스_구축_핵심요약집.pdf` | 4 | Subject extract (101–162) |
| `4_프로그램_언어_활용_핵심요약집.pdf` | 6 | Subject extract (155–222) |

The master PDF is the single source of truth. The four subject PDFs are redundant extracts
and are not read by the pipeline.

**Content inventory:** 320 numbered points, IDs 001–324. IDs 149, 150, 151, and 196 do not
exist in the source — this is a property of the book, not an extraction failure, and the
pipeline must treat these gaps as expected.

| 과목 | Name | Points | Range |
| --- | --- | --- | --- |
| 1 | 소프트웨어 설계 | 55 | 001–055 |
| 2 | 소프트웨어 개발 | 45 | 056–100 |
| 3 | 데이터베이스 구축 | ~54 | 101–154 |
| 4 | 프로그래밍 언어 활용 | ~68 | 155–222 |
| 5 | 정보시스템 구축 관리 | ~98 | 223–324 |

Subject boundaries for 과목 3/4/5 are approximate in this table because the subject PDFs
overlap. `extract.py` determines the true boundaries from the `N과목` headings in the
master PDF, and the counts in `cards.json` are authoritative.

Text extracts cleanly with `pypdf` (already installed). Note: the extractor emits `\x07`
(BEL) where the source uses a narrow space — this must be normalized to a regular space.

## Architecture

Three stages, cleanly separated:

```
master PDF ──extract.py──> cards.json ──┐
                                        ├──build.py──> study.html
            scenes/NNN.svg ─────────────┘
```

### 1. `extract.py` — PDF to structured data

Parses the master PDF into `cards.json`. Deterministic, re-runnable, no creative content.

Each record:

```json
{
  "id": "002",
  "subject": 1,
  "subjectName": "소프트웨어 설계",
  "title": "폭포수 모형",
  "bullets": [
    "이전 단계로 돌아갈 수 없다는 전제하에 각 단계를 확실히 매듭짓고 다음 단계를 진행하는 개발 방법론이다.",
    "보헴이 제시한 고전적 생명 주기 모형이다.",
    "요구사항을 반영하기 어렵다."
  ],
  "kind": "mnemonic",
  "hook": "폭포는 되돌아 흐르지 않는다"
}
```

`kind` and `hook` are authored, not extracted. `extract.py` writes `kind: null` and
`hook: null` on first run and **must never overwrite** an already-authored value on
re-run — it merges by `id`.

### 2. `scenes/NNN.svg` — the visual layer

One hand-authored SVG per point. This is the creative core and is not templated.

Every scene shares a fixed header so the deck feels like the same 요약집:
a blue `#0b8ad4` badge with the 3-digit number, and a gray `#d3d5d8` bar with the Korean
title. Below that, the scene.

Two scene types:

- **`diagram`** — for points with inherent structure. Processes become box-and-arrow
  chains, cycles become rings, taxonomies become trees, comparisons become split panels.
- **`mnemonic`** — for definition-only points. A metaphor scene (the waterfall with a
  crossed-out upward arrow), plus an initial-letter hook line at the bottom
  (e.g. `도 · 분 · 명 · 확`).

Scenes use emoji glyphs as icons, which render in color in Safari and Chrome on macOS and
iOS. Korean text inside the SVG stays real text — searchable and editable, never
rasterized.

Because each scene is an isolated file, a metaphor that does not click can be fixed by
editing one file and rebuilding. Nothing else is affected.

### 3. `build.py` — assembly

Reads `cards.json`, inlines every matching `scenes/NNN.svg`, and emits a single
self-contained `study.html`. No external requests, no CDN, no build toolchain. The file
opens offline by double-click on macOS and works after AirDrop to iPhone.

## The Study App

Single HTML file. Front of card is title-only; the visual is the reward for recalling.

- **Front:** 3-digit number + Korean title. Nothing else.
- **Back:** the SVG scene + the full bullet text from the source.
- **Flip:** spacebar or click/tap.
- **Navigate:** ← / → on Mac, swipe on phone.
- **Filter:** by 과목.
- **Order:** sequential or shuffled.
- **Marking:** 😵 어려움 / ✅ 암기함, persisted to `localStorage` keyed by card id.
- **Drill mode:** "어려운 것만" — restricts the deck to cards marked 어려움.
- **Progress:** current position and 암기함 count, per 과목.

State lives in `localStorage` under a single namespaced key. Clearing it resets progress;
there is no server and no account.

## Scope and Phasing

The SVG scenes are hand-authored, so quality is gated on human review of the style. Doing
all 320 in one pass risks discovering a style problem at card 300.

- **Phase 1 — 1과목 only (55 cards), complete end to end.** `extract.py`, all 55 scenes,
  `build.py`, and the full study app. Delivered as something he actually studies with.
- **Review gate.** He studies Phase 1 and reports what is wrong with the style.
- **Phases 2–5 — remaining 265 cards,** one 과목 per phase, with Phase 1 corrections
  applied.

Each phase ships a working `study.html`. There is no phase that leaves the deck unusable.

## Verification

Before any phase is called complete:

1. **Coverage:** every card in `cards.json` for that 과목 has a matching `scenes/NNN.svg`.
2. **Gaps:** no unexpected ID gaps beyond the known-absent 149, 150, 151, 196.
3. **Fidelity:** bullet text in `cards.json` matches the PDF source — spot-checked against
   the rendered PDF, not just the extracted stream.
4. **Render:** `study.html` is loaded in headless Chrome and screenshotted, confirming
   cards actually display. Writing the file is not evidence that it renders.
5. **Interaction:** flip, navigate, filter, and mark are exercised in the browser, not
   assumed to work.

Claims of completion cite the command output. No "should work."

## Explicitly Out of Scope

- Anki export. The web deck is the deliverable; `cards.json` keeps an export path open if
  he wants it later, but nothing is built for it now.
- AI-generated illustrations. No image API key is configured. The SVG scene format keeps
  the image slot swappable if he adds one later.
- Practice questions, mock exams, or scoring. This is a memorization aid for the cheatsheet
  points, nothing more.
- Any server, account, sync, or hosting. The deck is a local file.

## Repository Layout

```
InformationProcess-gisa-Cards/
├── extract.py
├── build.py
├── cards.json
├── scenes/
│   ├── 001.svg
│   └── ...
├── study.html          # generated
└── docs/superpowers/specs/
    └── 2026-07-27-gisa-flashcards-design.md
```
