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


def read_js(name):
    """Inline a templates/*.js source, minus its node-only CommonJS tail."""
    path = os.path.join(HERE, "templates", name)
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    # The `if (typeof module !== "undefined")` block exists only so node --test
    # can require the file. It is dead weight in the browser, so drop it.
    return re.split(r'\nif \(typeof module !== "undefined"', src)[0].rstrip() + "\n"


def read_supabase():
    """Project credentials, or None when the deck is built offline-only.

    The anon key is safe to publish: the `own row` RLS policy is what enforces
    per-user isolation, not the secrecy of this key.
    """
    path = os.path.join(HERE, "supabase.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    missing = [k for k in ("url", "anonKey") if not cfg.get(k)]
    if missing:
        raise SystemExit(f"supabase.json is missing: {', '.join(missing)}")
    # The dashboard's "Data API" panel shows the REST endpoint, not the project
    # origin, so pasting it verbatim is the obvious mistake. Trim it rather than
    # letting requests land on /rest/v1/rest/v1/progress.
    url = re.sub(r"/(rest|auth)/v1/?$", "", cfg["url"].strip().rstrip("/"))
    if not url.startswith("https://"):
        raise SystemExit(f"supabase.json url must start with https:// — got {url!r}")
    if cfg["anonKey"].startswith("sb_secret_") or ".service_role." in cfg["anonKey"]:
        raise SystemExit(
            "supabase.json holds a SECRET key. That key bypasses row-level "
            "security and index.html is public — use the publishable/anon key.")
    return {"url": url, "anonKey": cfg["anonKey"].strip()}


def build(cards, subjects, supa=None):
    """subjects: a subject number, or an iterable of them."""
    wanted = {subjects} if isinstance(subjects, int) else set(subjects)
    payload = []
    for c in sorted((c for c in cards if c["subject"] in wanted),
                    key=lambda c: int(c["id"])):
        svg = load_scene(c["id"])
        if svg is None:
            continue
        payload.append({
            "id": c["id"], "title": c["title"], "bullets": c["bullets"],
            "kind": c["kind"], "hook": c["hook"],
            "subject": c["subject"], "subjectName": c["subjectName"],
            "svg": wrap_scene(c, svg),
        })
    tmpl = open(os.path.join(HERE, "templates", "app.html"), encoding="utf-8").read()
    data = json.dumps(payload, ensure_ascii=False)
    # </script> inside data would close the tag early.
    data = data.replace("</", "<\\/")
    out = tmpl.replace("/*__CARDS__*/", data)
    out = out.replace("/*__SYNC__*/", read_js("sync.js"))
    out = out.replace("/*__CLOUD__*/", read_js("cloud.js"))
    return out.replace("/*__SUPABASE__*/",
                       json.dumps(supa) if supa else "null")


def subjects_with_scenes(cards):
    return sorted({c["subject"] for c in cards
                   if os.path.exists(os.path.join(HERE, "scenes", c["id"] + ".svg"))})


def main():
    cards = json.load(open(os.path.join(HERE, "cards.json"), encoding="utf-8"))
    args = sys.argv[1:]

    # -o/--out writes somewhere other than index.html, so parallel workers can
    # each build and screenshot their own subject without fighting over one file.
    out = os.path.join(HERE, "index.html")
    for flag in ("-o", "--out"):
        if flag in args:
            k = args.index(flag)
            try:
                out = os.path.abspath(args[k + 1])
            except IndexError:
                raise SystemExit(f"{flag} needs a path")
            del args[k:k + 2]

    # No remaining args: build every subject that has at least one scene authored.
    subjects = sorted({int(a) for a in args}) if args else subjects_with_scenes(cards)
    if not subjects:
        raise SystemExit("no subjects have scenes yet — author some scenes/NNN.svg first")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build(cards, subjects, read_supabase()))

    print(f"wrote {out}")
    for s in subjects:
        total = len([c for c in cards if c["subject"] == s])
        drawn = sum(1 for c in cards if c["subject"] == s
                    and os.path.exists(os.path.join(HERE, "scenes", c["id"] + ".svg")))
        name = next((c["subjectName"] for c in cards if c["subject"] == s), "?")
        flag = "" if drawn == total else "   <-- incomplete"
        print(f"  {s}과목 {name}: {drawn}/{total} cards have scenes{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
