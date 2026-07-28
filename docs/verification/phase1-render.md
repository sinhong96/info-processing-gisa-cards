# Phase 1 Render Verification

## Environment

- Verified: 2026-07-28
- Chrome path (for `verify_render.py`): `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- Note: Headless screenshots require running `python3 verify_render.py` on the Mac directly.
  The sandbox environment is missing `libXdamage.so.1` and cannot run Chrome headlessly.

## Programmatic checks (all PASS)

| Check | Result |
|---|---|
| CARDS count | 8 (ids: 001, 002, 006, 008, 016, 019, 021, 022) |
| All cards have required fields (id, title, bullets, kind, hook, svg) | ✅ PASS |
| SVG validity (starts `<svg`, has `viewBox`, ends `</svg>`) | ✅ PASS — all 8 |
| PUA / control characters in text | ✅ NONE found |
| Emoji in SVG scenes | ✅ All 8 cards have emoji in their SVGs |
| Hook text present | ✅ 8/8 cards |
| Red hook/arrow in SVG (`#e03131` or `marker-end`) | ✅ 002, 008 (others use hook text only) |
| External references (src=, href=, https://, fetch, XHR) | ✅ NONE — offline safe |
| `render()` function defined | ✅ |
| Space key → flip | ✅ |
| Touch swipe support | ✅ |
| `localStorage` for mark persistence | ✅ |

## SVG viewBoxes

| Card | viewBox | Title |
|---|---|---|
| 001 | 0 0 720 326 | 소프트웨어 공학의 기본 원칙 |
| 002 | 0 0 720 430 | 폭포수 모형 |
| 006 | 0 0 720 256 | XP의 핵심 가치 |
| 008 | 0 0 720 266 | 요구사항 개발 프로세스 |
| 016 | 0 0 720 306 | 행위(Behavioral) 다이어그램의 종류 |
| 019 | 0 0 720 256 | 순차(Sequence) 다이어그램의 구성 요소 |
| 021 | 0 0 720 316 | 사용자 인터페이스의 구분 |
| 022 | 0 0 720 276 | 사용자 인터페이스의 기본 원칙 |

## To produce actual screenshots

Run on the Mac (not in sandbox):

```bash
python3 verify_render.py
# → docs/verification/render-front.png

# For the back (flipped) screenshot:
python3 - <<'EOF'
import os, re, verify_render
HERE = os.path.dirname(os.path.abspath(verify_render.__file__))
src = open(os.path.join(HERE,'study.html'), encoding='utf-8').read()
probe = src.replace('render();','flipped=true;render();')
p = os.path.join(HERE,'docs','verification','_flipped.html')
open(p,'w',encoding='utf-8').write(probe)
verify_render.shoot(p, os.path.join(HERE,'docs','verification','render-back.png'))
os.remove(p)
print('flipped screenshot OK')
EOF
```

Confirm by eye:
- Card front: number (e.g. `001`) and Korean title visible, no boxes or `?` glyphs
- No `&lt;` or `\x07` artifacts
- Footer buttons visible and not overlapping
- Card back: SVG scene, bullet list, red hook line present, emoji in color
