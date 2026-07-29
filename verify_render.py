#!/usr/bin/env python3
"""Screenshot index.html in headless Chrome to prove it actually renders.

Writing the file is not evidence that it renders. This takes two shots: the
card front, and a probe copy forced to its flipped state so the SVG scene,
the bullets, and the hook line are all exercised.
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT_DIR = os.path.join(HERE, "docs", "verification")


def shoot(html_path, out_png, size="900,1300"):
    """Screenshot one file. Chrome often writes the PNG then fails to exit,
    so a timeout is not treated as failure — the PNG itself is the verdict."""
    if not os.path.exists(CHROME):
        raise SystemExit(f"Chrome not found at {CHROME}")
    if os.path.exists(out_png):
        os.remove(out_png)
    with tempfile.TemporaryDirectory() as profile:
        try:
            subprocess.run([
                CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                f"--user-data-dir={profile}",
                f"--screenshot={out_png}", f"--window-size={size}",
                "--virtual-time-budget=2000",
                "file://" + html_path,
            ], check=True, capture_output=True, timeout=45)
        except subprocess.TimeoutExpired:
            pass  # Chrome hung on exit; the screenshot is usually already written.
        except subprocess.CalledProcessError as e:
            raise SystemExit(f"Chrome failed: {e.stderr.decode(errors='replace')[:400]}")
    if not os.path.exists(out_png) or os.path.getsize(out_png) < 5000:
        raise SystemExit(f"screenshot missing or suspiciously small: {out_png}")
    return out_png


def make_flipped_probe(src_html, dest_html, card=None):
    """Copy the built page with its first render forced to the back face.

    Pass a card id to open on that specific card instead of the first one.
    """
    src = open(src_html, encoding="utf-8").read()
    jump = f'i=CARDS.findIndex(c=>c.id==="{card}");' if card else ""
    probe = src.replace("\nrender();", f"\n{jump}flipped=true;render();")
    if probe == src:
        raise SystemExit("could not build flipped probe: 'render();' call not found")
    open(dest_html, "w", encoding="utf-8").write(probe)
    return dest_html


def main():
    # Optional args so parallel workers can point at their own build and output
    # directory instead of contending for index.html and docs/verification/.
    #   verify_render.py [HTML] [OUT_DIR] [--card NNN]
    argv = sys.argv[1:]
    card = None
    if "--card" in argv:
        k = argv.index("--card")
        card = argv[k + 1] if len(argv) > k + 1 else None
        del argv[k:k + 2]
    html = os.path.abspath(argv[0]) if argv else os.path.join(HERE, "index.html")
    out_dir = os.path.abspath(argv[1]) if len(argv) > 1 else OUT_DIR

    if not os.path.exists(html):
        raise SystemExit(f"{html} not found — run build.py first")
    os.makedirs(out_dir, exist_ok=True)

    front = shoot(html, os.path.join(out_dir, "render-front.png"))
    print(f"front OK -> {front} ({os.path.getsize(front)} bytes)")

    probe = os.path.join(out_dir, "_flipped.html")
    try:
        make_flipped_probe(html, probe, card)
        back = shoot(probe, os.path.join(out_dir, "render-back.png"))
        print(f"back  OK -> {back} ({os.path.getsize(back)} bytes)")
    finally:
        if os.path.exists(probe):
            os.remove(probe)

    print("Look at both PNGs. Emoji must be in color, not tofu boxes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
