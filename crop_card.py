#!/usr/bin/env python3
"""Build a scene from the source page itself, for cards the PDF draws rather than writes.

Some cards are a table, a Gantt chart, or a tree diagram. Their content is not in
the text stream, and hand-redrawing them is both slow and a chance to introduce
errors. For those, crop the region straight off the rendered page and embed it.

    python3 crop_card.py 204            # write scenes/204.svg
    python3 crop_card.py 204 --dpi 220  # sharper, larger file

The crop starts below the card's title bar, because build.py draws the number
badge and title bar itself so every card in the deck keeps the same header.
Cards built this way get kind "image"; the study app then skips its own bullet
list, since the cropped picture already contains the printed bullets.
"""
import argparse, base64, io, json, os, re, subprocess, sys, tempfile
import pypdf
from PIL import Image

import extract

HERE = os.path.dirname(os.path.abspath(__file__))
PDFTOPPM = "/opt/homebrew/bin/pdftoppm"

# Page geometry in PDF points, measured from the master PDF (612.283 x 858.898).
COLUMN_SPLIT = 306.0          # x below this is the left column
LEFT_COL = (40.0, 302.0)
RIGHT_COL = (316.0, 578.0)
HEADER_DROP = 20.0            # start the crop this far below the title baseline
BOTTOM_MARGIN = 50.0          # clears the printed page number in the bottom corner
GAP_ABOVE_NEXT = 14.0         # leave this much clear of the next card's badge


def locate(card_id):
    """Return (page_index, (x0, y0, x1, y1)) in PDF points for one card's body."""
    reader = pypdf.PdfReader(extract.PDF)
    for page_index, page in enumerate(reader.pages):
        runs = []

        def visit(text, cm, tm, font_dict, font_size):
            if text.strip():
                runs.append((tm[4], tm[5], (font_dict or {}).get("/BaseFont", ""), text.strip()))

        page.extract_text(visitor_text=visit)
        badges = [(x, y, t) for x, y, f, t in runs
                  if "DIN-Bold" in f and re.fullmatch(r"\d{3}", t)]
        me = [(x, y) for x, y, t in badges if t == card_id]
        if not me:
            continue
        bx, by = me[0]
        left = bx < COLUMN_SPLIT
        x0, x1 = LEFT_COL if left else RIGHT_COL

        # The card ends where the next badge down the same column begins.
        below = [y for x, y, t in badges
                 if (x < COLUMN_SPLIT) == left and y < by - 1]
        y_bottom = (max(below) + GAP_ABOVE_NEXT) if below else BOTTOM_MARGIN
        y_top = by - HEADER_DROP
        page_h = float(page.mediabox.height)
        return page_index, (x0, y_bottom, x1, y_top), page_h
    raise SystemExit(f"card {card_id} not found in the PDF")


def render_page(page_index, dpi, out_dir):
    """Rasterise one page with pdftoppm. Returns the PNG path."""
    if not os.path.exists(PDFTOPPM):
        raise SystemExit(
            f"pdftoppm not found at {PDFTOPPM}. Install poppler, or render the page "
            "another way and pass --png.")
    prefix = os.path.join(out_dir, "page")
    n = page_index + 1
    subprocess.run([PDFTOPPM, "-png", "-r", str(dpi), "-f", str(n), "-l", str(n),
                    extract.PDF, prefix], check=True, capture_output=True, timeout=120)
    hits = [f for f in os.listdir(out_dir) if f.startswith("page") and f.endswith(".png")]
    if not hits:
        raise SystemExit("pdftoppm produced no PNG")
    return os.path.join(out_dir, hits[0])


def crop(png_path, box_pt, page_h_pt, dpi):
    """Crop a PDF-point box out of a rendered page. PDF y is bottom-up; images are top-down."""
    x0, y0, x1, y1 = box_pt
    s = dpi / 72.0
    im = Image.open(png_path)
    px = (int(x0 * s), int((page_h_pt - y1) * s), int(x1 * s), int((page_h_pt - y0) * s))
    px = (max(0, px[0]), max(0, px[1]), min(im.width, px[2]), min(im.height, px[3]))
    return im.crop(px)


def to_scene_svg(img, card_id):
    """Wrap a cropped image as a scene: 720 wide, height set by the aspect ratio."""
    height = round(720 * img.height / img.width)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 720 {height}">\n'
        f'  <!-- Cropped from the source page: this card is a graphic, not text. -->\n'
        f'  <image x="0" y="0" width="720" height="{height}" '
        f'xlink:href="data:image/png;base64,{b64}"/>\n'
        f'</svg>\n'), height, len(b64)


def set_kind_image(card_id, hook):
    path = os.path.join(HERE, "cards.json")
    cards = json.load(open(path, encoding="utf-8"))
    hit = next((c for c in cards if c["id"] == card_id), None)
    if hit is None:
        raise SystemExit(f"card {card_id} not in cards.json")
    hit["kind"] = "image"
    if hook:
        hit["hook"] = hook
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cards, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("card_id")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--hook", default=None, help="set the card's hook while we're here")
    ap.add_argument("--keep-header", action="store_true",
                    help="include the source title bar (normally build.py draws it)")
    args = ap.parse_args()
    cid = args.card_id.zfill(3)

    page_index, box, page_h = locate(cid)
    if args.keep_header:
        x0, y0, x1, y1 = box
        box = (x0, y0, x1, y1 + HEADER_DROP + 26)
    with tempfile.TemporaryDirectory() as tmp:
        png = render_page(page_index, args.dpi, tmp)
        img = crop(png, box, page_h, args.dpi)
    svg, height, b64len = to_scene_svg(img, cid)

    out = os.path.join(HERE, "scenes", f"{cid}.svg")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    card = set_kind_image(cid, args.hook)
    print(f"page {page_index + 1}, crop {img.width}x{img.height}px at {args.dpi}dpi")
    print(f"wrote {out}  (viewBox 0 0 720 {height}, {b64len // 1024} KB base64)")
    print(f"cards.json: {cid} kind=image hook={card['hook']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
