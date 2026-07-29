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


def make_flipped_probe(src_html, dest_html):
    """Copy index.html with the initial render forced to the back face."""
    src = open(src_html, encoding="utf-8").read()
    probe = src.replace("\nrender();", "\nflipped=true;render();")
    if probe == src:
        raise SystemExit("could not build flipped probe: 'render();' call not found")
    open(dest_html, "w", encoding="utf-8").write(probe)
    return dest_html


def main():
    html = os.path.join(HERE, "index.html")
    if not os.path.exists(html):
        raise SystemExit("index.html not found — run build.py first")
    os.makedirs(OUT_DIR, exist_ok=True)

    front = shoot(html, os.path.join(OUT_DIR, "render-front.png"))
    print(f"front OK -> {front} ({os.path.getsize(front)} bytes)")

    probe = os.path.join(OUT_DIR, "_flipped.html")
    try:
        make_flipped_probe(html, probe)
        back = shoot(probe, os.path.join(OUT_DIR, "render-back.png"))
        print(f"back  OK -> {back} ({os.path.getsize(back)} bytes)")
    finally:
        if os.path.exists(probe):
            os.remove(probe)

    print("Look at both PNGs. Emoji must be in color, not tofu boxes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
