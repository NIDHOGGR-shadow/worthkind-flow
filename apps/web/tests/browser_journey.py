"""Real Chromium + loopback FastAPI + isolated SQLite frontend journey.
Uses synthetic records only; does not test or invoke live hotel providers.
Run after installing playwright and API dev dependencies:
    python apps/web/tests/browser_journey.py
"""
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:8765"
WIDTHS = (320, 360, 390, 768, 1024, 1440)


def await_server(process):
    for _ in range(80):
        if process.poll() is not None:
            raise RuntimeError("Development API stopped before becoming ready")
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=1) as response:
                if json.load(response).get("status") == "ok":
                    return
        except OSError:
            time.sleep(.25)
    raise RuntimeError("Development API did not become ready")


def main():
    with tempfile.TemporaryDirectory(prefix="wf-browser-") as folder:
        state = Path(folder) / "state"
        command = [sys.executable, str(ROOT / "scripts/local_dev.py"), "start",
                   "--state-dir", str(state), "--port", "8765"]
        # Generated test staff keys must not appear in CI logs.
        with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL) as server:
            try:
                await_server(server)
                keys = json.loads((state / "staff-keys.json").read_text())
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    guest = browser.new_page(viewport={"width": 390, "height": 844})
                    guest.goto(BASE)
                    expect(guest.locator("#property-capability")).to_have_attribute("data-state", "ready")
                    expect(guest.locator("#property-capability")).to_contain_text("not confirmed")
                    # Real property lookup: no injected API responses.
                    guest.locator("#hotel").select_option("demo-hotel-two")
                    expect(guest.locator("#property-capability")).to_have_attribute("data-state", "ready")
                    guest.locator("#hotel").select_option("demo-hotel")
                    expect(guest.locator("#property-capability")).to_have_attribute("data-state", "ready")
                    guest.get_by_role("button", name="Message reception", exact=True).click()
                    expect(guest.locator("#category")).to_have_value("human")
                    marker = "Browser synthetic " + uuid.uuid4().hex[:12]
                    guest.locator("#name").fill(marker)
                    guest.locator("#contact").fill("browser-guest@example.invalid")
                    guest.locator("#details").fill("Please record a synthetic reception response.")
                    guest.locator("#enquiry-form button[type=submit]").click()
                    expect(guest.locator("#track")).to_be_visible()
                    expect(guest.locator("#case-status")).to_contain_text("queued")
                    receipt = guest.locator("#receipt").inner_text().splitlines()
                    case_id = next(line.split(": ", 1)[1] for line in receipt if line.startswith("Case ID: "))
                    token = next(line.split(": ", 1)[1] for line in receipt if line.startswith("Private receipt token"))
                    staff = browser.new_page(viewport={"width": 1440, "height": 900})
                    staff.goto(BASE + "/staff")
                    staff.locator("#p").select_option("demo-hotel")
                    staff.locator("#key").fill(keys["demo-hotel"])
                    staff.locator("#load").click()
                    case = staff.locator(".case-card").filter(has_text=marker)
                    expect(case).to_have_count(1)
                    case.get_by_role("button", name="Claim this case").click()
                    expect(case.get_by_role("button", name="Record response")).to_be_visible()
                    reply = "Synthetic browser journey: response recorded."
                    case.locator(".case-reply-form textarea").fill(reply)
                    case.get_by_role("button", name="Record response").click()
                    expect(case).to_contain_text(reply)
                    guest.locator("#refresh").click()
                    expect(guest.locator("#case-status")).to_contain_text(reply)
                    guest.reload()
                    guest.locator("#recover-hotel").select_option("demo-hotel")
                    guest.locator("#recover-case-id").fill(case_id)
                    guest.locator("#recover-token").fill(token)
                    guest.locator("#recover-submit").click()
                    expect(guest.locator("#case-status")).to_contain_text(reply)
                    staff.locator("#p").select_option("demo-hotel-two")
                    expect(staff.locator(".case-card").filter(has_text=marker)).to_have_count(0)
                    staff.locator("#key").fill(keys["demo-hotel-two"])
                    staff.locator("#load").click()
                    expect(staff.locator("#visible-count")).not_to_have_text("No cases loaded")
                    expect(staff.locator(".case-card").filter(has_text=marker)).to_have_count(0)
                    # The versioned page must never silently fall back to SQLite.
                    # On this legacy-only branch its v1 endpoint returns 404;
                    # on the combined backend branch an unknown property or missing
                    # configured storage must still reject the request.
                    v1 = browser.new_page(viewport={"width": 390, "height": 844})
                    requests = []
                    v1.on("request", lambda req: requests.append(req.url))
                    v1.goto(BASE + "/static/guest-v1.html")
                    v1.get_by_role("button", name="Contact reception", exact=True).click()
                    expect(v1.locator("#v1-kind")).to_have_value("human")
                    v1.locator("#v1-hotel").fill("unconfigured-browser-test-property")
                    v1.locator("#v1-name").fill("Synthetic test")
                    v1.locator("#v1-contact").fill("guest@example.invalid")
                    v1.locator("#v1-details").fill("This synthetic request must not fall back.")
                    v1.locator("#v1-submit").click()
                    expect(v1.locator("#v1-submit")).to_have_text("Retry unchanged request")
                    expect(v1.locator("#request-fields")).to_be_disabled()
                    expect(v1.locator("#v1-track")).to_be_hidden()
                    assert any("/api/v1/properties/" in url for url in requests)
                    assert not any("/api/properties/" in url for url in requests)
                    v1.on("dialog", lambda dialog: dialog.accept())
                    v1.locator("#v1-discard").click()
                    expect(v1.locator("#request-fields")).to_be_enabled()
                    v1.close()
                    for route in ("/", "/staff", "/staff/tickets", "/staff/operations", "/staff/knowledge", "/static/guest-v1.html"):
                        page = browser.new_page()
                        page.goto(BASE + route)
                        for width in WIDTHS:
                            page.set_viewport_size({"width": width, "height": 900})
                            # Actual rendered DOM geometry, not CSS string assertions.
                            actual = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
                            if actual > width + 2:
                                raise AssertionError(f"{route}: horizontal overflow at {width}px ({actual}px)")
                        page.close()
                    browser.close()
                print("PASS: browser guest/reception/receipt/property journey and 36 responsive route checks")
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    main()
