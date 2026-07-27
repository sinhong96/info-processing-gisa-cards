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
