"""Guest commerce Chromium contract test; network responses are synthetic fixtures."""
from urllib.parse import urlsplit
from playwright.sync_api import expect

CASE = "12345678-1234-1234-1234-123456789abc"
ROOM = "22345678-1234-1234-1234-123456789abc"
VENUE = "32345678-1234-1234-1234-123456789abc"
INTENT = "42345678-1234-1234-1234-123456789abc"


def check_guest_commerce(browser, base):
    page = browser.new_page(viewport={"width": 390, "height": 900})
    page.on("dialog", lambda d: d.accept())
    prefix = "/api/v1/properties/hotel-a"
    private = prefix + "/guest/cases/" + CASE
    state = {"token": None, "intent": None, "attempts": []}

    def api(route):
        req = route.request
        path = urlsplit(req.url).path
        assert req.headers.get("authorization") is None
        if path == prefix + "/content":
            route.fulfill(json={"content":[{"key":"hotel","content":{"title":"Synthetic hotel","body":"Approved fixture content"}}]})
        elif path == prefix + "/rooms":
            route.fulfill(json={"rooms":[{"id":ROOM,"name":"Synthetic deluxe","max_guests":2,"description":"Fixture room","display_rates":[{"amount_minor":5000000,"currency":"NGN","start_date":"2026-12-01","end_date":"2026-12-31"}]}]})
        elif path == prefix + "/menu":
            route.fulfill(json={"items":[{"id":ROOM,"name":"Synthetic meal","price_minor":250000,"currency":"NGN"}]})
        elif path == prefix + "/venues":
            route.fulfill(json={"venues":[{"id":VENUE,"name":"Synthetic hall","capacity":50}]})
        elif path == prefix + "/enquiries" and req.method == "POST":
            state["token"] = req.post_data_json["receipt_token"]
            route.fulfill(json={"case_id":CASE,"receipt_token":state["token"],"status":"queued"})
        elif path.startswith(private):
            assert req.headers.get("x-receipt-token") == state["token"]
            assert state["token"] not in req.url
            if path == private + "/reservation-intents" and req.method == "GET":
                route.fulfill(json={"intents":[state["intent"]] if state["intent"] else [],"booking_confirmed":False,"inventory_held":False})
            elif path == private + "/reservation-intents" and req.method == "POST":
                body = req.post_data_json
                state["attempts"].append(body)
                if len(state["attempts"]) == 1:
                    route.fulfill(status=503,json={"detail":"Outcome unknown"})
                    return
                assert state["attempts"][0] == body
                assert body["room_type_id"] == ROOM
                state["intent"] = {**body,"id":INTENT,"state":"requested"}
                route.fulfill(json={"id":INTENT,"state":"requested","booking_confirmed":False,"inventory_held":False})
            elif path == private + "/reservation-intents/" + INTENT + "/withdraw":
                state["intent"]["state"]="withdrawn"
                route.fulfill(json={"id":INTENT,"state":"withdrawn","booking_confirmed":False})
            elif path == private + "/venue-requests":
                assert req.post_data_json["venue_id"] == VENUE
                route.fulfill(json={"id":VENUE,"state":"requested"})
            else:
                route.fulfill(status=404,json={"detail":"Not found"})
        else:
            route.fulfill(status=404,json={"detail":"Not found"})

    page.route("**/api/v1/properties/**", api)
    page.goto(base + "/static/guest-v1.html")
    page.locator("#catalog-slug").fill("hotel-a")
    page.get_by_role("button", name="Load hotel", exact=True).click()
    expect(page.locator("#catalog-content")).to_contain_text("Synthetic deluxe")
    expect(page.locator("#catalog-content")).to_contain_text("nonbinding display rate")
    page.get_by_role("button", name="Send an enquiry to this hotel").click()
    expect(page.locator("#v1-hotel")).to_have_value("hotel-a")
    page.locator("#v1-name").fill("Synthetic guest")
    page.locator("#v1-contact").fill("guest@example.invalid")
    page.locator("#v1-details").fill("Synthetic room enquiry")
    page.locator("#v1-submit").click()
    expect(page.locator("#guest-commerce")).to_be_visible()
    page.locator("#commerce-refresh").click()
    expect(page.locator("#stay-room option").filter(has_text="Synthetic deluxe")).to_have_count(1)
    page.locator("#stay-room").select_option(ROOM)
    page.locator("#stay-arrival").fill("2026-12-01")
    page.locator("#stay-departure").fill("2026-12-03")
    page.locator("#stay-send").click()
    expect(page.locator("#stay-send")).to_have_text("Retry unchanged request")
    expect(page.locator("#stay-arrival")).to_be_disabled()
    page.locator("#stay-send").click()
    expect(page.locator("#guest-intents")).to_contain_text(INTENT)
    page.get_by_role("button", name="Withdraw request").click()
    expect(page.locator("#guest-intents")).to_contain_text("withdrawn")
    page.locator("#venue-id").select_option(VENUE)
    page.locator("#venue-start").fill("2026-12-01T10:00")
    page.locator("#venue-end").fill("2026-12-01T14:00")
    page.locator("#venue-attendance").fill("20")
    page.locator("#venue-send").click()
    expect(page.locator("#guest-venue-requests")).to_contain_text(VENUE)
    for width in (320,360,390,768,1024,1440):
        page.set_viewport_size({"width":width,"height":900})
        actual = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
        assert actual <= width + 2, f"Guest commerce overflow at {width}px ({actual}px)"
    page.locator("#v1-new").click()
    expect(page.locator("#guest-commerce")).to_be_hidden()
    expect(page.locator("#guest-intents")).to_be_empty()
    expect(page.locator("#guest-venue-requests")).to_be_empty()
    page.close()
    print("PASS: guest commerce catalog, receipt-scoped stay retry, withdrawal, venue request, and six viewport checks")
