# InformationProcess-gisa-Cards

Visual flashcards for the 정보처리기사 필기 exam.

Every numbered point in the official 핵심요약집 becomes one card: the number and Korean
title on the front, a hand-drawn SVG scene plus the source bullets on the back. Structured
points (processes, taxonomies, comparisons) get a diagram; definition-only points get a
mnemonic scene with a memory hook.

**Live deck:** https://sinhong96.github.io/info-processing-gisa-cards/

## Studying

Open `index.html` in any browser. It is a single self-contained file — no server, no
network, no install. It works with Wi-Fi off.

To study on a phone: AirDrop `index.html` to it and open in Safari.

| Input | Action |
| --- | --- |
| `space` or tap the card | flip |
| `→` / `←`, or swipe | next / previous |
| 😵 어려움 | mark as hard, advance |
| ✅ 암기함 | mark as memorized, advance |
| 😵 어려운 것만 | drill only the cards marked hard |
| 🔀 섞기 | shuffle (the 목차 index stays in id order) |
| ☰ 목차 | open the table of contents; click any card to jump to it |
| 과목 selector | study one 과목, or 전체 for everything |
| ↺ 초기화 | clear all marks |

The 목차 panel lists every card with its number, title, and 😵/✅ mark, so you can see
what a 과목 contains and jump straight to a card. On a phone it collapses behind the
☰ 목차 button. Clicking an entry clears whatever filter would otherwise hide it.

Progress is kept in the browser's `localStorage` under `gisa-cards-v1`, and the selected
과목 under `gisa-cards-subject`. Clearing site data
resets it. There is no account and nothing is uploaded.

## Status

324 points total, IDs 001–324, contiguous with no gaps. All 324 are already extracted and
cleaned in `cards.json`; what remains per subject is authoring the scenes.

| 과목 | Name | Cards | Scenes |
| --- | --- | --- | --- |
| 1 | 소프트웨어 설계 | 55 | ✅ 55 |
| 2 | 소프트웨어 개발 | 45 | ✅ 45 |
| 3 | 데이터베이스 구축 | 54 | — |
| 4 | 프로그래밍 언어 활용 | 61 | — |
| 5 | 정보시스템 구축 관리 | 109 | — |

## How it works

Three stages, deliberately separated so a bad picture is a one-file fix:

```
master PDF ──extract.py──> cards.json ──┐
                                        ├──build.py──> index.html
            scenes/NNN.svg ─────────────┘
```

- **`extract.py`** parses the master PDF into `cards.json`. It derives titles from the
  PDF's *font metadata* — titles are set in `S-CoreDream-7ExtraBold`, ids in `DIN-Bold` —
  rather than guessing from text position. An earlier text-position heuristic silently
  corrupted 13+ titles by absorbing the tail of the previous card's last bullet.
- **`scenes/NNN.svg`** is one hand-authored scene per card. Scene files contain **no
  header** — `build.py` draws the number badge and title bar so every card matches.
  Coordinates start at y=0 below the 76px header, and the viewBox is always
  `0 0 720 H`.
- **`build.py`** inlines everything into `index.html`. No CDN, no bundler, no framework.

### Rebuilding

```bash
python3 extract.py         # master PDF  -> cards.json
python3 classify.py 2      # check one subject's kind/hook are complete
python3 build.py           # every subject that has scenes -> index.html
python3 verify_render.py   # screenshot front and back in headless Chrome
python3 -m unittest discover -s tests -v
```

`build.py` with no arguments includes every 과목 that has at least one scene authored, and
flags any that are incomplete. Pass subject numbers (`python3 build.py 1 2`) to restrict it.

`extract.py` is safe to re-run. It merges by `id` and never overwrites an authored `kind`
or `hook`, nor anything in `title_overrides.json` / `bullet_overrides.json`.

### Editing a card's picture

Every scene is one file: `scenes/NNN.svg`. Edit it, re-run `python3 build.py <subject>`.
Nothing else is touched.

## Source data quirks

The source PDF fights back in specific ways, all handled in `extract.py` and worth knowing
before trusting a card:

- **BEL (`\x07`) stands in for a narrow space** and must be normalized first.
- **Korean wraps mid-word** (`확`/`실히`). Joining wrapped lines with a space corrupts the
  text, so the join is Hangul-aware: no separator between two Hangul characters, a space
  otherwise.
- **Private-use glyphs** (the book's "예제" badge, `U+E000`–`U+F8FF`) and stray C0 control
  bytes are stripped.
- **Some content is a graphic, not text.** Those cards cannot be parsed and carry
  hand-written entries instead:
  - `title_overrides.json` — ID 142, whose title renders as an image.
  - `bullet_overrides.json` — IDs 045, 046, 050, 052, 059, 061, 062, 066, 067, 068, 091,
    204. Mostly worked examples, sorting traces, a tree-traversal diagram, a complexity
    table, and a Gantt chart — content the PDF draws rather than writes.

  Anything in these files was read off the rendered page by hand. If a card looks wrong,
  check here first, then `docs/verification/phase*-fidelity.md` for what was checked and
  why.

  Two known source defects are reproduced faithfully rather than silently corrected: the
  book itself omits a "3회전" label on card 066, and card 061's degree figures refer to a
  tree that is not recoverable from the page, so its scene shows a generic tree.

## Repository layout

```
extract.py               PDF -> cards.json
classify.py              validates that a subject's kind/hook are authored
build.py                 cards.json + scenes -> index.html
verify_render.py         headless-Chrome screenshot check
cards.json               all 324 extracted points
title_overrides.json     hand-read titles for graphic-rendered cards
bullet_overrides.json    hand-read bullets for graphic-rendered cards
scenes/NNN.svg           one scene per card (no header — build.py adds it)
templates/app.html       the study app shell
tests/                   unittest suite (stdlib only, no pytest)
docs/superpowers/        design spec and implementation plan
docs/verification/       verification records
```

## Requirements

Python 3.14 and `pypdf`. Nothing else — the test suite uses stdlib `unittest`, and the
study app has no build step or dependencies at all.
