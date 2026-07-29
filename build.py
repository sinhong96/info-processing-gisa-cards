#!/usr/bin/env python3
"""Assemble cards.json + scenes/*.svg into a single self-contained index.html."""
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
        f'<svg viewBox="0 0 720 {h + HEADER_H}" '
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
    out = os.path.join(HERE, "index.html")
    html = build(cards, subject)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    total = len([c for c in cards if c["subject"] == subject])
    drawn = sum(1 for c in cards if c["subject"] == subject
                and os.path.exists(os.path.join(HERE, "scenes", c["id"] + ".svg")))
    print(f"wrote {out}: {drawn}/{total} cards have scenes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
