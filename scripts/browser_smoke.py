#!/usr/bin/env python3
"""Chromium smoke journey against a REAL local FastAPI server and isolated SQLite.

This tests a normal web application with a LOCAL development database; it does
NOT impose an offline-first requirement. No Supabase, real hotel or provider
credentials are needed. No production service is called.

Run after:
  pip install -r projects/worthkind-flow/apps/api/requirements-dev.txt
  pip install "playwright>=1.50,<2"
  python -m playwright install chromium
  python projects/worthkind-flow/scripts/browser_smoke.py

Real browser coverage does not equal independent WCAG/screen reader, load,
security, production identity, deployment or provider verification.
"""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


PROJECT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT / "scripts" / "local_dev.py"
LABEL = "Synthetic Chromium Guest"
DETAILS = "A synthetic room inspection request for the hotel maintenance desk."


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(url: str, child: subprocess.Popen, log_path: Path):
    for _ in range(100):
        if child.poll() is not None:
            raise RuntimeError(
                f"Development server exited early ({child.returncode}); inspect {log_path}"
            )
        try:
            with urlopen(url + "/health", timeout=1.0) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f"Local server never started; inspect {log_path}")


def assert_no_horizontal_overflow(page, label):
    dimensions = page.evaluate("""() => ({
      scroll: document.documentElement.scrollWidth,
      client: document.documentElement.clientWidth
    })""")
    assert dimensions["scroll"] <= dimensions["client"] + 4, (
        f"{label}: horizontal scroll {dimensions['scroll']}px at viewport "
        f"{dimensions['client']}px"
    )


def check_guest_flow(page, url):
    page.goto(url + "/", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name=re.compile("Hotel help", re.I))).to_be_visible()
    page.locator("#hotel").select_option("demo-hotel")
    page.locator("#category").select_option("support")
    page.locator("#name").fill(LABEL)
    page.locator("#contact").fill("chromium-smoke@example.invalid")
    page.locator("#details").fill(DETAILS)
    page.locator("#enquiry-form button[type=submit]").click()
    page.locator("#track").wait_for(state="visible")
    receipt_text = page.locator("#receipt").inner_text()
    match_id = re.search(r"Case ID:\s*([0-9a-f-]{36})", receipt_text)
    match_token = re.search(r"Receipt token \(keep private\):\s*([a-f0-9]{64})", receipt_text)
    assert match_id and match_token, "Guest case ID and secret receipt must be displayed"
    case_id, token = match_id.group(1), match_token.group(1)

    # Full JS page restart: guest recovers without cookie/localStorage URL token.
    page.reload(wait_until="domcontentloaded")
    assert page.locator("#track").is_hidden()
    page.locator("#recover-hotel").select_option("demo-hotel")
    page.locator("#recover-case-id").fill(case_id)
    page.locator("#recover-token").fill(token)
    page.locator("#recover-submit").click()
    page.locator("#track").wait_for(state="visible")
    expect(page.locator("#case-status")).to_contain_text("queued")
    assert "receipt" not in page.url.lower()
    assert token not in page.url
    return case_id, token


def check_staff_handoff(page, url, key, case_id):
    page.goto(url + "/staff", wait_until="domcontentloaded")
    page.locator("#p").select_option("demo-hotel")
    page.locator("#key").fill(key)
    page.locator("#load").click()
    page.locator("#cases .case-card").first.wait_for()
    card = page.locator(".case-card").filter(
        has=page.get_by_role("heading", name=LABEL, exact=True)
    )
    assert card.count() == 1
    card.get_by_role("button", name="Claim this case").click()
    card.locator(".case-ticket-form").wait_for()
    card.locator(".case-ticket-form select").first.select_option("maintenance")
    card.locator(".case-ticket-form input").fill("Inspect synthetic room fixture")
    card.locator(".case-ticket-form textarea").fill(
        "Inspect the synthetic room fixture for a demonstration only."
    )
    card.get_by_role("button", name="Create linked department ticket").click()
    card.get_by_text("Linked ticket:", exact=False).wait_for()

    page.goto(url + "/staff/tickets", wait_until="domcontentloaded")
    page.locator("#property").select_option("demo-hotel")
    page.locator("#staff-key").fill(key)
    page.locator("#refresh").click()
    page.locator("#ticket-list").get_by_role(
        "heading", name="Inspect synthetic room fixture"
    ).wait_for()

    page.goto(url + "/staff/operations", wait_until="domcontentloaded")
    page.locator("#property").select_option("demo-hotel")
    page.locator("#staff-key").fill(key)
    page.locator("#load-overview").click()
    page.locator("#overview").wait_for(state="visible")
    assert int(page.locator("#case-total").inner_text()) >= 9
    assert int(page.locator("#ticket-unresolved").inner_text()) >= 1
    expect(page.locator("#message")).to_contain_text("local SQLite")


def check_knowledge(page, url, key):
    page.goto(url + "/staff/knowledge", wait_until="domcontentloaded")
    page.locator("#property").select_option("demo-hotel")
    page.locator("#staff-key").fill(key)
    page.locator("#load-knowledge").click()
    page.locator("#knowledge-data").wait_for(state="visible")
    page.locator("#question-key").select_option("parking")
    page.locator("#draft-answer").fill(
        "Synthetic parking information for browser smoke verification only."
    )
    page.locator("#source-reference").fill("Synthetic browser test source only")
    page.locator("#draft-submit").click()
    page.get_by_role("button", name="Approve local version").first.wait_for()
    page.get_by_role("button", name="Approve local version").first.click()
    page.locator("#facts").get_by_text(
        "Synthetic parking information for browser smoke verification only."
    ).wait_for()
    page.locator("#preview-question").fill("Is parking available?")
    page.locator("#preview-button").click()
    expect(page.locator("#preview-result")).to_contain_text(
        "Synthetic parking information"
    )

    # Changing tenant clears previous property details and staff credential.
    page.locator("#property").select_option("demo-hotel-two")
    assert page.locator("#staff-key").input_value() == ""
    assert page.locator("#knowledge-data").is_hidden()
    assert page.locator("#facts").inner_text() == ""


def main():
    with tempfile.TemporaryDirectory(prefix="worthkind-browser-synthetic-") as tmp:
        state = Path(tmp) / "sqlite-state"
        log_path = Path(tmp) / "local-server.log"
        port = available_port()
        url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.pop("WF_DATABASE_PATH", None)
        env.pop("WF_DEV_STAFF_KEYS_JSON", None)
        env["WF_ENV"] = "development"

        keys = {}
        with log_path.open("w", encoding="utf-8") as logfile:
            child = subprocess.Popen(
                [sys.executable, str(RUNNER), "start", "--seed-demo",
                 "--state-dir", str(state), "--port", str(port)],
                cwd=str(PROJECT),
                env=env,
                stdout=logfile, stderr=subprocess.STDOUT,
            )
            try:
                wait_for_server(url, child, log_path)
                keys = json.loads((state / "staff-keys.json").read_text(encoding="utf-8"))
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        for width, height in ((390, 844), (1280, 800)):
                            page = browser.new_page(
                                viewport={"width": width, "height": height},
                                device_scale_factor=1,
                            )
                            errors = []
                            unexpected_requests = []
                            page.on("pageerror", lambda error: errors.append(str(error)))

                            # A fixture test must not unexpectedly contact a real
                            # hotel, a CDN, a third-party AI provider or PSP.
                            def only_local(route):
                                target = urlparse(route.request.url)
                                if target.scheme in ("http", "https") and target.hostname in ("127.0.0.1", "localhost") and target.port == port:
                                    route.continue_()
                                else:
                                    unexpected_requests.append(target.scheme + "://" + str(target.hostname))
                                    route.abort()

                            page.route("**/*", only_local)
                            case_id, token = check_guest_flow(page, url)
                            assert_no_horizontal_overflow(page, f"guest {width}")
                            check_staff_handoff(page, url, keys["demo-hotel"], case_id)
                            assert_no_horizontal_overflow(page, f"operations {width}")
                            check_knowledge(page, url, keys["demo-hotel"])
                            assert_no_horizontal_overflow(page, f"knowledge {width}")
                            assert errors == [], (
                                f"Uncaught JS errors at viewport {width}: {errors}"
                            )
                            assert unexpected_requests == [], (
                                f"External HTTP requests were attempted: {unexpected_requests}"
                            )
                            page.close()
                            print(
                                f"PASS: Chromium {width}x{height} local guest receipt, "
                                "reception, department ticket, management and knowledge"
                            )
                    finally:
                        browser.close()
            except BaseException:
                print("Local browser smoke failed. Server output (synthetic only):", file=sys.stderr)
                if log_path.exists():
                    # The dev runner prints synthetic staff keys for manual
                    # login. Never disclose them to shared CI job logs.
                    output = log_path.read_text(encoding="utf-8")[-6000:]
                    for secret in keys.values():
                        output = output.replace(secret, "[REDACTED DEVELOPMENT KEY]")
                    if not keys:
                        # No key material is known if startup failed early.
                        # Omit logs rather than risk printing generated secrets.
                        output = "(server startup failed before keys could be verified)"
                    print(output, file=sys.stderr)
                raise
            finally:
                child.terminate()
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=8)


if __name__ == "__main__":
    main()
