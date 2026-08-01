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
| 😵 어려움 | mark as hard, advance (key `1`) |
| 🤔 애매함 | mark as half-known, advance (key `2`) |
| ✅ 암기함 | mark as memorized, advance (key `3`) |
| 🔁 복습할 것만 | drill everything not yet mastered — 어려움 and 애매함 both |
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

**Complete — all 324 cards have scenes.** IDs 001–324, contiguous with no gaps.

| 과목 | Name | Cards | Scenes |
| --- | --- | --- | --- |
| 1 | 소프트웨어 설계 | 55 | ✅ 55 |
| 2 | 소프트웨어 개발 | 45 | ✅ 45 |
| 3 | 데이터베이스 구축 | 54 | ✅ 54 |
| 4 | 프로그래밍 언어 활용 | 61 | ✅ 61 |
| 5 | 정보시스템 구축 관리 | 109 | ✅ 109 |

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

  For cards that are *entirely* a graphic, redrawing them by hand is slow and invites
  errors. Those use `crop_card.py` instead, which crops the region straight off the
  rendered page and embeds it as a data URI:

  ```bash
  python3 crop_card.py 204 --hook "짧은 작업 먼저 (SJF)"
  ```

  It sets the card's `kind` to `"image"`, and the study app then skips its own bullet
  list because the cropped picture already shows the printed bullets. The crop starts
  below the title bar so `build.py` still draws the deck's standard header. Card 204
  (스케줄링 - SJF, a Gantt chart) is built this way.

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
crop_card.py             builds a scene by cropping the source page (graphic cards)
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

## 진도 동기화 (cross-device sync)

카드 상태(😵 / 🤔 / ✅)는 기기의 localStorage에 저장되고, 로그인하면 Supabase의
개인 행(row)과 동기화됩니다. 아이폰에서 표시한 것이 맥북에서도 보입니다.

- **오프라인 우선.** 네트워크가 없어도 앱은 그대로 동작하고, 표시한 내용은
  기기에 저장됩니다. 연결되면 자동으로 합쳐집니다.
- **병합 규칙.** 카드별로 최신 표시가 이깁니다. 시각이 같으면 복습 필요
  (😵 / 🤔)가 암기함(✅)을 이깁니다.
- **헤더의 점.** 🟢 동기화됨 · 🟡 동기화 중 · 🔴 오프라인.
- **로그인 전 기록.** 로그인하면 "합칠까요?"를 묻습니다. 묻지 않고 합치는 일은
  없습니다 — 한 기기를 여러 사람이 쓸 때 남의 기록이 섞이는 것을 막기 위함입니다.

### 처음 설정할 때

```bash
cp supabase.example.json supabase.json   # URL과 publishable key 입력
python3 build.py
```

`supabase.json`이 없으면 동기화 없이 오프라인 전용으로 빌드됩니다.
**secret key를 넣으면 빌드가 거부됩니다** — index.html은 공개되므로 secret key는
RLS를 무력화합니다. publishable(anon) key만 사용하세요.

### 테스트

```bash
python3 -m unittest tests.test_build tests.test_classify tests.test_extract
node --test tests/test_sync.js tests/test_cloud.js
```

## Supabase 운영

### 무료 플랜 일시정지 (founder runbook)

무료 플랜 프로젝트는 약 7일간 활동이 없으면 **일시정지(paused)** 됩니다.
매주 월요일에 도는 `.github/workflows/supabase-keepalive.yml`이 이를 막지만,
저장소 자체가 60일간 조용하면 GitHub이 이 스케줄을 꺼버립니다.

**증상:** 로그인은 되는데 헤더의 점이 계속 🔴 오프라인. 표시한 내용은 기기에
남아 있으므로 데이터가 사라진 것은 아닙니다.

**복구:**

1. https://supabase.com/dashboard 에서 프로젝트를 열고 **Restore project** 클릭
2. 몇 분 후 Actions → supabase-keepalive → Run workflow 로 확인
3. 각 기기에서 새로고침 — 점이 🟢 으로 바뀌고 밀려 있던 표시가 올라갑니다

### 이메일 전송 한도

무료 플랜의 기본 메일 발송은 **시간당 몇 통**으로 제한됩니다. 로그인 링크가
오지 않으면 대부분 이 한도입니다(앱이 "이메일 전송 한도를 초과했습니다"로
알려줍니다). 1시간 후 다시 시도하거나, 자주 겪는다면 Supabase에 custom SMTP를
설정하면 사라집니다.

### 로그인 리디렉션

Authentication → URL Configuration 에 아래가 등록되어 있어야 합니다.
빠지면 링크가 Supabase 기본값(`localhost:3000`)으로 가서 열리지 않습니다.

```
Site URL       https://sinhong96.github.io/info-processing-gisa-cards/
Redirect URLs  https://sinhong96.github.io/info-processing-gisa-cards/
               https://sinhong96.github.io/info-processing-gisa-cards/**
               http://localhost:8765/**
```

### 다른 사용자에게 열어주기

지금은 Supabase 대시보드에서 신규 가입이 꺼져 있어 등록된 계정만 로그인할 수
있습니다. 열어주려면 Authentication → Sign In / Providers → **Allow new users
to sign up** 을 켜면 됩니다. 코드 변경은 필요 없습니다.

RLS 정책(`auth.uid() = user_id`)이 서버에서 사용자별 격리를 보장하고, 기기
쪽에서는 localStorage 키를 사용자별로 나누어(`gisa-cards-v2:<user_id>`) 한
브라우저를 공유해도 기록이 섞이지 않습니다.

### 배포

GitHub Pages는 `.github/workflows/pages.yml`(GitHub Actions)로 배포합니다.
기존 Jekyll 빌더는 로그 없이 "Page build failed"만 남기고 멈춰서 교체했습니다.
`.nojekyll`도 함께 두어 저장소를 그대로 서빙합니다.
