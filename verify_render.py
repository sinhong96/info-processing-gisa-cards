#!/usr/bin/env python3
"""Screenshot study.html in headless Chrome to prove it actually renders."""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def shoot(html_path, out_png, size="900,1200"):
    if not os.path.exists(CHROME):
        raise SystemExit(f"Chrome not found at {CHROME}")
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([
            CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
            f"--user-data-dir={profile}",
            f"--screenshot={out_png}", f"--window-size={size}",
            "--virtual-time-budget=3000",
            "file://" + html_path,
        ], check=True, capture_output=True, timeout=90)
    if not os.path.exists(out_png) or os.path.getsize(out_png) < 5000:
        raise SystemExit(f"screenshot missing or suspiciously small: {out_png}")
    return out_png


def main():
    html = os.path.join(HERE, "study.html")
    if not os.path.exists(html):
        raise SystemExit("study.html not found — run build.py first")
    out = os.path.join(HERE, "docs", "verification", "render-front.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shoot(html, out)
    print(f"rendered OK -> {out} ({os.path.getsize(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
