#!/usr/bin/env python3
"""Generate the screenshots for the in-app guide (#157).

Starts the app locally on a free port, plays a short example competition in
headless Chromium and photographs it in German and English:

- ``judge-reason.webp``: the chief referee's phone with yellow and a reason
  picked, not yet locked in (#158)
- ``result-reasons.webp``: a "No Lift" with the judges' reasons shown
- ``layout-editor.webp``: the same display in the layout editor (block
  frames, toolbar, the timer hidden to show the hide toggles)

The images are written as ``<out>/<lang>/<motif>.webp`` (default
``src/iron_verdict/static/img/guide``) and committed. They contain example
data only: a made-up session name and no VPortal athlete data.

Usage: python scripts/guide_screenshots.py [--out DIR]
"""

import argparse
import base64
import os
import pathlib
import socket
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "src" / "iron_verdict" / "static" / "img" / "guide"
# Rendered like a Full HD hall display, stored at a smaller size.
VIEWPORT = {"width": 1920, "height": 1080}
IMAGE_SIZE = (1280, 720)
# Rendered like a phone (CSS pixels at twice the density), stored at 4/3 of
# the CSS size: sharp at the narrow width the guide shows it.
PHONE_VIEWPORT = {"width": 390, "height": 840}
PHONE_SCALE = 2
PHONE_IMAGE_SIZE = (520, 1120)
WEBP_QUALITY = 0.8
SESSION_NAMES = {"de": "Beispiel-Meisterschaft", "en": "Example Championship"}
LOCALES = {"de": "de-DE", "en": "en-US"}


def start_server():
    """Run the app in a background thread; return its base URL."""
    # Same settings as the E2E tests: any origin, session snapshot in a
    # throwaway directory instead of /data.
    os.environ["ALLOWED_ORIGIN"] = "*"
    os.environ["SNAPSHOT_PATH"] = os.path.join(tempfile.mkdtemp(), "sessions.json")
    sys.path.insert(0, str(ROOT / "src"))
    import httpx
    import uvicorn
    from iron_verdict.main import app

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(f"{url}/health", timeout=1.0)
            return url
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError("server failed to start")


def open_page(browser, url, lang, phone=False):
    if phone:
        ctx = browser.new_context(locale=LOCALES[lang], viewport=PHONE_VIEWPORT,
                                  device_scale_factor=PHONE_SCALE)
    else:
        ctx = browser.new_context(locale=LOCALES[lang], viewport=VIEWPORT)
    page = ctx.new_page()
    page.goto(url)
    return page


def join(browser, url, code, role_selector):
    page = open_page(browser, url, "en")
    page.get_by_test_id("join-code-input").fill(code)
    page.get_by_test_id("join-code-input").press("Enter")
    page.locator(role_selector).click()
    return page


def vote(page, color, with_reason):
    page.locator(f".vote-btn.vote-{color}").click()
    if with_reason:
        page.locator(".reason-item").first.click()
    page.locator(".lock-btn").click()
    page.locator(".locked-status").wait_for(state="visible")


def to_webp(page, png, size):
    """Scale a PNG screenshot to ``size`` and encode it as WebP with
    Chromium's own encoder."""
    data_url = page.evaluate(
        """async ([src, [width, height], quality]) => {
            const img = new Image();
            img.src = src;
            await img.decode();
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(img, 0, 0, width, height);
            return canvas.toDataURL('image/webp', quality);
        }""",
        ["data:image/png;base64," + base64.b64encode(png).decode(), size, WEBP_QUALITY],
    )
    if not data_url.startswith("data:image/webp;base64,"):
        raise RuntimeError("Chromium did not encode WebP")
    return base64.b64decode(data_url.split(",", 1)[1])


def shoot(page, path, size=IMAGE_SIZE):
    page.mouse.move(0, 0)
    # Finite animations jump to their end, infinite ones are stopped, so the
    # image never catches a half-finished transition.
    png = page.screenshot(animations="disabled")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(to_webp(page, png, size))
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def check_language(page, lang):
    # The session names differ per language, so a wrong UI language would
    # not show up as identical images; check it directly.
    shown = page.evaluate("document.documentElement.lang")
    if shown != lang:
        raise RuntimeError(f"page shows language {shown!r}, expected {lang!r}")


def generate(browser, url, lang, out):
    head = open_page(browser, url, lang, phone=True)
    head.get_by_test_id("session-name-input").fill(SESSION_NAMES[lang])
    head.get_by_test_id("session-name-input").press("Enter")
    head.locator(".role-wrap").wait_for(state="visible")
    code = head.locator(".session-tag .code").text_content()
    head.locator(".role-btn").nth(1).click()  # chief referee (centre)
    head.get_by_test_id("judge-screen").wait_for(state="visible")
    check_language(head, lang)
    left = join(browser, url, code, '.role-btn:has-text("Left")')
    right = join(browser, url, code, '.role-btn:has-text("Right")')

    display = open_page(browser, url, lang)
    display.get_by_test_id("join-code-input").fill(code)
    display.get_by_test_id("join-code-input").press("Enter")
    display.locator(".role-display-btn").click()
    display.locator(".display-full").wait_for(state="visible")
    check_language(display, lang)

    # Squat (the default lift): yellow, "skipped signal" (second reason) picked.
    head.locator(".vote-btn.vote-yellow").click()
    head.locator(".reason-item").nth(1).click()
    head.locator(".reason-item.selected").wait_for(state="visible")
    head.locator(".lock-btn").wait_for(state="visible")
    shoot(head, out / lang / "judge-reason.webp", PHONE_IMAGE_SIZE)
    head.locator(".back-btn").click()

    vote(left, "red", with_reason=True)
    vote(head, "white", with_reason=False)
    vote(right, "blue", with_reason=True)
    display.locator(".verdict-stamp").wait_for(state="visible")
    display.locator(".display-full .display-orb-reason").nth(2).wait_for(state="visible")
    shoot(display, out / lang / "result-reasons.webp")

    display.get_by_test_id("display-settings-gear").click()
    display.get_by_test_id("display-layout-edit").click()
    display.get_by_test_id("layout-toolbar").wait_for(state="visible")
    display.get_by_test_id("layout-hide-timer").click()
    shoot(display, out / lang / "layout-editor.webp")

    # The example session lives only in this run's server.
    for page in (head, left, right, display):
        page.context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT,
                        help=f"output directory (default: {DEFAULT_OUT.relative_to(ROOT)})")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    url = start_server()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for lang in ("de", "en"):
                generate(browser, url, lang, args.out)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
