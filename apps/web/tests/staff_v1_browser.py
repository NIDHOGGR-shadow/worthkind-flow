"""Chromium UI contract tests with isolated network fixtures.
These tests do not contact Supabase or establish a working hosted staff integration.
The surrounding browser journey separately exercises real local API routes.
"""
import json
from urllib.parse import urlsplit
from playwright.sync_api import expect

WIDTHS = (320, 360, 390, 768, 1024, 1440)
CASE_ID = "12345678-1234-1234-1234-123456789abc"
TICKET_ID = "22345678-1234-1234-1234-123456789abc"
MEMBER_ID = "32345678-1234-1234-1234-123456789abc"
PROVIDER = "https://abcdefghijklmnopqrst.supabase.co"


def check_staff_v1(browser, base):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(base + "/static/staff-v1.html")
    expect(page.locator("#login-status")).to_contain_text("unavailable until")
    expect(page.locator("#login")).to_be_disabled()
    expect(page.locator("#staff-workspace")).to_be_hidden()
    page.close()

    page = browser.new_page(viewport={"width": 390, "height": 844})
    calls = []
    state = {"case": "queued", "ticket": "open", "settings": True, "revision": 1}
    page.on("dialog", lambda dialog: dialog.accept())
    page.route("**/staff-auth-config.json", lambda route: route.fulfill(json={
        "enabled": True, "provider": "supabase", "url": PROVIDER,
        "publishableKey": "sb_publishable_ui_fixture_only"
    }))

    def auth(route):
        # All provider traffic stays inside Chromium test routing.
        headers = {"Access-Control-Allow-Origin": "*",
                   "Access-Control-Allow-Headers": "apikey,content-type,authorization",
                   "Access-Control-Allow-Methods": "POST,OPTIONS"}
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers=headers)
        elif "/token?" in route.request.url:
            route.fulfill(json={"access_token": "fixture.token.value", "expires_in": 600,
                               "user": {"role": "authenticated", "is_anonymous": False,
                                        "email_confirmed_at": "2026-11-25"}}, headers=headers)
        elif "/logout?" in route.request.url:
            route.fulfill(status=204, headers=headers)
        else:
            route.fulfill(status=404, headers=headers)

    page.route(PROVIDER + "/**", auth)

    def api(route):
        request = route.request
        path = urlsplit(request.url).path
        calls.append((request.method, path))
        assert request.headers.get("authorization") == "Bearer fixture.token.value"
        if "/hotel-b/" in path:
            route.fulfill(status=403, json={"detail": "Access denied"})
            return
        prefix = "/api/v1/properties/hotel-a/staff"
        if path == prefix + "/cases":
            route.fulfill(json={"property": "hotel-a", "staff_role": "reception",
                               "cases": [{"id": CASE_ID, "status": state["case"], "kind": "human",
                                          "customer_name": "Synthetic guest", "contact": "guest@example.invalid",
                                          "details": "<img src=x>"}]})
        elif path == prefix + "/cases/" + CASE_ID + "/claim":
            state["case"] = "claimed"
            route.fulfill(json={"property": "hotel-a", "case_id": CASE_ID, "status": "claimed"})
        elif path == prefix + "/cases/" + CASE_ID + "/respond":
            assert request.post_data_json["message"] == "Synthetic response"
            state["case"] = "responded"
            route.fulfill(json={"property": "hotel-a", "case_id": CASE_ID, "status": "responded"})
        elif path == prefix + "/tickets" and request.method == "GET":
            route.fulfill(json={"tickets": [{"id": TICKET_ID, "status": state["ticket"], "category": "maintenance",
                                            "priority": "high", "subject": "Synthetic maintenance issue",
                                            "description": "Test only", "due_at": "2026-11-25T12:00:00Z",
                                            "overdue": True, "assignee": None}]})
        elif path == prefix + "/tickets/" + TICKET_ID + "/transition":
            assert request.post_data_json["action"] == "claim"
            state["ticket"] = "assigned"
            route.fulfill(json={"ticket_id": TICKET_ID, "status": "assigned"})
        elif path == prefix + "/memberships/accept":
            route.fulfill(json={"membership_id": MEMBER_ID, "state": "active", "role": "reception"})
        elif path == prefix + "/settings":
            if request.method == "PUT":
                assert request.post_data_json == {"revision": 1, "guest_enquiries_enabled": False}
                state["settings"] = False
                state["revision"] = 2
            route.fulfill(json={"guest_enquiries_enabled": state["settings"],
                               "ai_enabled": False, "revision": state["revision"]})
        else:
            route.fulfill(status=404, json={"detail": "Not found"})

    page.route("**/api/v1/properties/**", api)
    page.goto(base + "/static/staff-v1.html")
    expect(page.locator("#login")).to_be_enabled()
    page.locator("#email").fill("staff@example.invalid")
    page.locator("#password").fill("synthetic-password")
    page.locator("#login").click()
    expect(page.locator("#staff-workspace")).to_be_visible()
    expect(page.locator("#password")).to_have_value("")
    page.locator("#staff-slug").fill("hotel-a")
    page.get_by_role("button", name="Select property").click()
    page.locator("#load-cases").click()
    expect(page.get_by_text("Synthetic guest", exact=True)).to_be_visible()
    expect(page.get_by_text("<img src=x>", exact=True)).to_be_visible()
    expect(page.locator("#v1-cases img")).to_have_count(0)
    page.get_by_role("button", name="Claim case", exact=True).click()
    expect(page.get_by_role("button", name="Record response", exact=True)).to_be_visible()
    page.locator("#reply-" + CASE_ID).fill("Synthetic response")
    page.get_by_role("button", name="Record response", exact=True).click()
    expect(page.locator("#v1-cases")).to_contain_text("responded")
    page.get_by_role("button", name="Department work", exact=True).click()
    page.locator("#load-tickets").click()
    expect(page.locator("#v1-tickets")).to_contain_text("Overdue")
    page.get_by_role("button", name="Claim", exact=True).click()
    expect(page.locator("#v1-tickets")).to_contain_text("assigned")
    page.get_by_role("button", name="Memberships", exact=True).click()
    page.locator("#accept-membership").click()
    expect(page.locator("#membership-result")).to_contain_text("active")
    page.get_by_role("button", name="Hotel settings", exact=True).click()
    page.locator("#load-settings").click()
    expect(page.locator("#guest-enabled")).to_be_checked()
    page.locator("#guest-enabled").uncheck()
    page.get_by_role("button", name="Save settings", exact=True).click()
    expect(page.locator("#settings-version")).to_have_text("Revision 2")
    for label in ("Reception", "Department work", "Memberships", "Hotel settings"):
        page.get_by_role("button", name=label, exact=True).click()
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            actual = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            assert actual <= width + 2, f"Staff {label}: overflow at {width}px ({actual}px)"
    page.locator("#staff-slug").fill("hotel-b")
    page.get_by_role("button", name="Select property").click()
    expect(page.locator("#v1-cases")).to_be_empty()
    expect(page.locator("#v1-tickets")).to_be_empty()
    page.get_by_role("button", name="Reception", exact=True).click()
    page.locator("#load-cases").click()
    expect(page.locator("#staff-message")).to_contain_text("not authorized")
    expect(page.locator("#v1-cases")).to_be_empty()
    page.locator("#signout").click()
    expect(page.locator("#login-panel")).to_be_visible()
    expect(page.locator("#staff-workspace")).to_be_hidden()
    assert all(path.startswith("/api/v1/") for _, path in calls)
    page.close()
    print("PASS: staff v1 Chromium fixture journey and 24 authenticated-layout checks")
