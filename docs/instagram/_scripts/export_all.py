"""Universal exporter for instagram card HTML files."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / "output"
OUT_ROOT.mkdir(exist_ok=True)
SCALE = 2

TOPIC_DIRS = [
    "00_brand", "01_earnings", "02_weekly_calendar",
    "03_quant_basics", "04_market_recap", "05_strategy",
]


def discover_targets(arg: str | None) -> list[Path]:
    if arg:
        c = ROOT / arg
        if c.is_file() and c.suffix == ".html":
            return [c]
        if c.is_dir():
            return [f for f in c.glob("*.html") if not f.name.startswith("_")]
    files = []
    for d in TOPIC_DIRS:
        topic = ROOT / d
        if topic.is_dir():
            files.extend(f for f in topic.glob("*.html") if not f.name.startswith("_"))
    return sorted(files)


def export_html(p, html: Path) -> int:
    rel = html.relative_to(ROOT)
    topic = rel.parts[0]
    out_dir = OUT_ROOT / topic / html.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[{topic}/{html.stem}]")

    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 900},
                               device_scale_factor=SCALE)
    page = ctx.new_page()
    page.goto(html.as_uri(), wait_until="networkidle")
    page.wait_for_timeout(1500)

    wraps = page.locator(".card-wrap").all()
    if not wraps:
        if "profile" in html.stem.lower():
            svg = page.locator("svg").first
            if svg.count() > 0:
                out = out_dir / "profile.png"
                svg.scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                svg.screenshot(path=str(out))
                print(f"  profile.png (SVG)")
                browser.close()
                return 1
        print("  WARN: no .card-wrap found")
        browser.close()
        return 0

    saved = 0
    for wrap in wraps:
        try:
            label = wrap.locator(".card-label").inner_text()
        except Exception:
            label = ""
        m = re.search(r"CARD\s*(\d+)", label)
        name = f"card_{m.group(1)}.png" if m else f"card_{saved+1}.png"
        card = wrap.locator(".card").first
        out = out_dir / name
        card.scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        card.screenshot(path=str(out))
        print(f"  {name}")
        saved += 1

    browser.close()
    return saved


def main(argv):
    arg = argv[1] if len(argv) > 1 else None
    targets = discover_targets(arg)
    if not targets:
        print(f"No HTML files found")
        return 1
    print(f"Found {len(targets)} HTML file(s)")
    with sync_playwright() as p:
        total = sum(export_html(p, h) for h in targets)
    print(f"\nDone. {total} PNGs in {OUT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
