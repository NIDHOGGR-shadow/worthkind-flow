"""Chromium UI contract tests with isolated network fixtures.
These tests do not contact Supabase or establish a working hosted staff integration.
The surrounding browser journey separately exercises real local API routes.
"""
import json
import os
from pathlib import Path
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
    state = {"case": "queued", "ticket": "open", "settings": True, "revision": 1, "shift": None, "room": "dirty", "room_revision": 1}
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
        if path == "/api/v1/properties/hotel-a/menu":
            assert request.headers.get("authorization") is None
            route.fulfill(json={"items":[{"id":TICKET_ID,"name":"Synthetic meal","price_minor":250000,"currency":"NGN"}]})
            return
        assert request.headers.get("authorization") == "Bearer fixture.token.value"
        if "/hotel-b/" in path:
            route.fulfill(status=403, json={"detail": "Access denied"})
            return
        prefix = "/api/v1/properties/hotel-a/staff"
        if path == prefix + "/reservation-intents":
            route.fulfill(json={"intents":[{"id":CASE_ID,"case_id":CASE_ID,"state":state.get("stay","requested"),"arrival":"2026-12-01","departure":"2026-12-03","adults":2,"children":0,"room_count":1}]})
        elif path == prefix + "/reservation-intents/" + CASE_ID + "/review":
            assert request.post_data_json["action"] == "review"
            state["stay"]="under_review"
            route.fulfill(json={"id":CASE_ID,"state":"under_review","booking_confirmed":False})
        elif path == prefix + "/pms/availability":
            route.fulfill(json={"provider":"cloudbeds","inventory_held":False,"rates_binding":False,"retrieved_at":"2026-11-25T20:00:00Z","room_types":[{"room_type_id":"SYNTHETIC","rooms_available":2}]})
        elif path == prefix + "/dining/orders":
            if request.method == "POST":
                assert request.post_data_json["lines"] == [{"item_id":TICKET_ID,"quantity":2}]
                state["order"]="submitted"
                route.fulfill(json={"id":TICKET_ID,"state":"submitted","total_minor":500000,"currency":"NGN","payment_confirmed":False})
            else:
                route.fulfill(json={"orders":[{"id":TICKET_ID,"state":state["order"],"total_minor":500000,"currency":"NGN","lines":[{"name":"Synthetic meal","quantity":2}]}] if "order" in state else []})
        elif path == prefix + "/dining/orders/" + TICKET_ID + "/transition":
            assert request.post_data_json["action"] == "accept"
            state["order"]="accepted"
            route.fulfill(json={"id":TICKET_ID,"state":"accepted","payment_confirmed":False})
        elif path == prefix + "/venue-requests":
            route.fulfill(json={"requests":[{"id":CASE_ID,"venue_id":TICKET_ID,"state":state.get("venue","requested"),"starts_at":"2026-12-01T08:00:00Z","ends_at":"2026-12-01T12:00:00Z","attendance":20}]})
        elif path == prefix + "/venue-requests/" + CASE_ID + "/decision":
            state["venue"]="reviewed"
            route.fulfill(json={"id":CASE_ID,"state":"reviewed"})
        elif path == prefix + "/finance":
            route.fulfill(json={"invoices":[{"id":CASE_ID,"dining_order_id":TICKET_ID,"amount_minor":500000,"currency":"NGN","state":"issued"}],"payments":[{"id":TICKET_ID,"invoice_id":CASE_ID,"amount_minor":500000,"currency":"NGN","mode":"test","state":state.get("payment","pending"),"reference":"wf-"+TICKET_ID}],"refunds":[],"exceptions":[]})
        elif path == prefix + "/finance/invoices/" + CASE_ID + "/checkout":
            route.fulfill(json={"id":TICKET_ID,"reference":"wf-"+TICKET_ID,"state":"pending","mode":"test","checkout_url":"https://checkout.paystack.com/synthetic","payment_confirmed":False})
        elif path == prefix + "/finance/payments/" + TICKET_ID + "/verify":
            state["payment"]="verified"
            route.fulfill(json={"id":TICKET_ID,"state":"verified","mode":"test","payment_confirmed":False})
        elif path == prefix + "/cases":
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
        elif path == prefix + "/cases/" + CASE_ID + "/control":
            assert request.post_data_json["action"] == "escalate"
            state["case"] = "escalated"
            route.fulfill(json={"case_id": CASE_ID, "state": "escalated"})
        elif path == prefix + "/schedule":
            route.fulfill(json={"members": [{"membership_id": MEMBER_ID, "role": "reception",
                                           "state": "active", "display_name": "Synthetic staff"}],
                               "shifts": [] if state["shift"] is None else [{
                                   "id": TICKET_ID, "membership_id": MEMBER_ID, "state": state["shift"],
                                   "starts_at": "2026-11-25T08:00:00Z", "ends_at": "2026-11-25T16:00:00Z"}]})
        elif path == prefix + "/shifts":
            assert request.post_data_json["membership_id"] == MEMBER_ID
            state["shift"] = "scheduled"
            route.fulfill(json={"id": TICKET_ID, "state": "scheduled"})
        elif path == prefix + "/shifts/" + TICKET_ID + "/cancel":
            state["shift"] = "cancelled"
            route.fulfill(json={"id": TICKET_ID, "state": "cancelled"})
        elif path == prefix + "/rooms":
            route.fulfill(json={"rooms": [{"id": TICKET_ID, "room_type_id": CASE_ID,
                                         "label": "312", "operational_state": state["room"],
                                         "revision": state["room_revision"]}], "occupancy_verified": False})
        elif path == prefix + "/rooms/" + TICKET_ID + "/state":
            assert request.post_data_json == {"state": "inspecting", "revision": 1}
            state["room"] = "inspecting"
            state["room_revision"] = 2
            route.fulfill(json={"id": TICKET_ID, "operational_state": "inspecting", "revision": 2})
        elif path == prefix + "/tickets" and request.method == "GET":
            route.fulfill(json={"tickets": [{"id": TICKET_ID, "status": state["ticket"], "category": "maintenance",
                                            "priority": "high", "subject": "Synthetic maintenance issue",
                                            "description": "Test only", "due_at": "2026-11-25T12:00:00Z",
                                            "overdue": True, "assignee": None}]})
        elif path == prefix + "/tickets/" + TICKET_ID and request.method == "GET":
            route.fulfill(json={"id": TICKET_ID, "status": state["ticket"],
                                "origin_case_id": CASE_ID, "history": [{"actor": MEMBER_ID,
                                "action": "note", "note": "Synthetic history entry",
                                "created_at": "2026-11-25T10:00:00Z"}]})
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
    page.get_by_text("Case controls", exact=True).click()
    page.locator("#reason-" + CASE_ID).fill("Manager review requested")
    page.get_by_role("button", name="Escalate", exact=True).click()
    expect(page.locator("#v1-cases")).to_contain_text("escalated")
    page.get_by_role("button", name="Department work", exact=True).click()
    page.locator("#load-tickets").click()
    expect(page.locator("#v1-tickets")).to_contain_text("Overdue")
    page.get_by_role("button", name="Claim", exact=True).click()
    expect(page.locator("#v1-tickets")).to_contain_text("assigned")
    page.get_by_role("button", name="Load ticket history").click()
    expect(page.locator("#v1-tickets")).to_contain_text("Synthetic history entry")
    page.get_by_role("button", name="Memberships", exact=True).click()
    page.locator("#accept-membership").click()
    expect(page.locator("#membership-result")).to_contain_text("active")
    page.get_by_role("button", name="Hotel settings", exact=True).click()
    page.locator("#load-settings").click()
    expect(page.locator("#guest-enabled")).to_be_checked()
    page.locator("#guest-enabled").uncheck()
    page.get_by_role("button", name="Save settings", exact=True).click()
    expect(page.locator("#settings-version")).to_have_text("Revision 2")
    page.get_by_role("button", name="Staff schedule", exact=True).click()
    page.locator("#schedule-start").fill("2026-11-24T00:00")
    page.locator("#schedule-end").fill("2026-11-27T00:00")
    page.get_by_role("button", name="Load schedule", exact=True).click()
    expect(page.locator("#staff-roster")).to_contain_text("Synthetic staff")
    page.get_by_role("button", name="Use for profile or shift").click()
    page.locator("summary").filter(has_text="Schedule a shift").click()
    page.locator("#shift-start").fill("2026-11-25T08:00")
    page.locator("#shift-end").fill("2026-11-25T16:00")
    page.get_by_role("button", name="Schedule shift", exact=True).click()
    expect(page.locator("#staff-shifts")).to_contain_text("scheduled")
    page.get_by_role("button", name="Cancel shift").click()
    expect(page.locator("#staff-shifts")).to_contain_text("cancelled")
    page.get_by_role("button", name="Room readiness", exact=True).click()
    page.locator("#load-rooms").click()
    expect(page.locator("#staff-rooms")).to_contain_text("dirty")
    page.locator("#room-" + TICKET_ID).select_option("inspecting")
    page.get_by_role("button", name="Update room condition").click()
    expect(page.locator("#staff-rooms")).to_contain_text("Revision 2")
    page.get_by_role("button", name="Reservations", exact=True).click()
    page.locator("#load-reservations").click()
    expect(page.locator("#reservation-queue")).to_contain_text("requested")
    page.locator("#reservation-queue").get_by_role("button", name="review", exact=True).click()
    expect(page.locator("#reservation-queue")).to_contain_text("under review")
    page.locator("#pms-start").fill("2026-12-01")
    page.locator("#pms-end").fill("2026-12-03")
    page.get_by_role("button", name="Check provider availability").click()
    expect(page.locator("#pms-availability-result")).to_contain_text("Inventory not held")
    page.get_by_role("button", name="Dining", exact=True).click()
    page.locator("#load-order-menu").click()
    expect(page.locator("#order-menu")).to_contain_text("Synthetic meal")
    page.locator("#order-menu input[data-menu-id]").fill("2")
    page.locator("#dining-submit").click()
    expect(page.locator("#dining-queue")).to_contain_text("submitted")
    page.locator("#dining-queue").get_by_role("button", name="accept", exact=True).click()
    expect(page.locator("#dining-queue")).to_contain_text("accepted")
    page.get_by_role("button", name="Events", exact=True).click()
    page.locator("#load-events").click()
    page.locator("#events-queue").get_by_role("button", name="review", exact=True).click()
    expect(page.locator("#events-queue")).to_contain_text("reviewed")
    page.get_by_role("button", name="Finance", exact=True).click()
    page.locator("#load-finance").click()
    expect(page.locator("#finance-invoices")).to_contain_text("issued")
    page.locator("#finance-invoices input[type=email]").fill("payer@example.invalid")
    page.get_by_role("button", name="Prepare Paystack checkout").click()
    expect(page.get_by_role("link", name="Open test Paystack checkout")).to_have_attribute("href","https://checkout.paystack.com/synthetic")
    page.get_by_role("button", name="Verify provider payment").click()
    expect(page.locator("#finance-payments")).to_contain_text("verified")
    expect(page.locator("#finance-payments")).to_contain_text("Mode: test")
    for label in ("Reception", "Department work", "Memberships", "Staff schedule", "Room readiness", "Hotel settings","Reservations","Catalog","Dining","Events","Finance"):
        page.get_by_role("button", name=label, exact=True).click()
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            actual = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            assert actual <= width + 2, f"Staff {label}: overflow at {width}px ({actual}px)"
            if width in (390, 1440) and os.getenv("WF_BROWSER_SCREENSHOT_DIR"):
                output = Path(os.environ["WF_BROWSER_SCREENSHOT_DIR"])
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / ("staff-" + label.lower().replace(" ", "-") + "-" + str(width) + ".png")), full_page=True)
    page.locator("#staff-slug").fill("hotel-b")
    page.get_by_role("button", name="Select property").click()
    expect(page.locator("#v1-cases")).to_be_empty()
    expect(page.locator("#v1-tickets")).to_be_empty()
    expect(page.locator("#staff-roster")).to_be_empty()
    expect(page.locator("#staff-rooms")).to_be_empty()
    expect(page.locator("#finance-payments")).to_be_empty()
    expect(page.locator("#dining-queue")).to_be_empty()
    expect(page.locator("#reservation-queue")).to_be_empty()
    page.get_by_role("button", name="Reception", exact=True).click()
    page.locator("#load-cases").click()
    expect(page.locator("#staff-message")).to_contain_text("not authorized")
    expect(page.locator("#v1-cases")).to_be_empty()
    page.locator("#signout").click()
    expect(page.locator("#login-panel")).to_be_visible()
    expect(page.locator("#staff-workspace")).to_be_hidden()
    assert all(path.startswith("/api/v1/") for _, path in calls)
    page.close()
    print("PASS: staff v1 Chromium fixture journey and 66 authenticated-layout checks")
