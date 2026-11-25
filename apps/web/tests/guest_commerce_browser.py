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
            route.fulfill(json={"content":[{"key":"hotel","version":1,"content":{"title":"Synthetic hotel","body":"Approved fixture content"}},{"key":"privacy-policy","version":1,"content":{"title":"Synthetic privacy policy","body":"Fixture policy for consent tests only."}}]})
        elif path == prefix + "/ai/chat":
            assert req.post_data_json["consent_to_model_processing"] is True
            route.fulfill(json={"status":"handoff","reason":"model_unavailable","answer":None,"sources":[],"action_executed":False,"human_contact_available_via_property":True})
        elif path == prefix + "/rooms":
            route.fulfill(json={"rooms":[{"id":ROOM,"name":"Synthetic deluxe","max_guests":2,"description":"Fixture room","display_rates":[{"amount_minor":5000000,"currency":"NGN","start_date":"2026-12-01","end_date":"2026-12-31"}]}]})
        elif path == prefix + "/menu":
            route.fulfill(json={"items":[{"id":ROOM,"name":"Synthetic meal","price_minor":250000,"currency":"NGN"}]})
        elif path == prefix + "/venues":
            route.fulfill(json={"venues":[{"id":VENUE,"name":"Synthetic hall","capacity":50}]})
        elif path == prefix + "/vacancies":
            route.fulfill(json={"vacancies":[{"id":VENUE,"title":"Synthetic vacancy","description":"Published fixture vacancy","deadline":"2026-12-01"}]})
        elif path == prefix + "/enquiries" and req.method == "POST":
            state["token"] = req.post_data_json["receipt_token"]
            state["kind"] = req.post_data_json["kind"]
            route.fulfill(json={"case_id":CASE,"receipt_token":state["token"],"status":"queued","kind":state["kind"]})
        elif path.startswith(private):
            assert req.headers.get("x-receipt-token") == state["token"]
            assert state["token"] not in req.url
            if path == private + "/preferences":
                if req.method == "PUT":
                    assert req.post_data_json["revision"] == 0
                    assert req.post_data_json["language"] == "English"
                    route.fulfill(json={"revision":1})
                else:
                    route.fulfill(json={"preferences":None,"revision":0})
            elif path == private + "/consent":
                assert req.post_data_json == {"purpose":"marketing","granted":False,"policy_version":"privacy-policy:1"}
                route.fulfill(json={"id":INTENT,"purpose":"marketing","granted":False})
            elif path == private + "/feedback":
                assert req.post_data_json["rating"] == 4
                route.fulfill(json={"id":INTENT,"state":"new"})
            elif path == private + "/applications":
                assert state["kind"] == "careers"
                assert req.post_data_json["consent"] is True
                assert req.post_data_json["vacancy_id"] == VENUE
                route.fulfill(json={"id":INTENT,"state":"submitted"})
            elif path == private + "/reservation-intents" and req.method == "GET":
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
    page.locator("#load-preferences").click()
    expect(page.locator("#preferences-form")).to_be_visible()
    page.locator("#guest-language").fill("English")
    page.get_by_role("button", name="Save preferences").click()
    expect(page.locator("#guest-records-message")).to_contain_text("Revision 1")
    page.locator("#load-consent-policy").click()
    expect(page.locator("#consent-policy-text")).to_contain_text("Synthetic privacy policy")
    page.locator("#consent-purpose").select_option("marketing")
    page.locator("#consent-choice").select_option("deny")
    page.locator("#consent-reviewed").check()
    page.get_by_role("button", name="Record my choice").click()
    expect(page.locator("#consent-result")).to_contain_text("not granted")
    page.locator("#guest-rating").select_option("4")
    page.locator("#guest-feedback-comment").fill("Synthetic feedback")
    page.get_by_role("button", name="Submit feedback").click()
    expect(page.locator("#guest-records-message")).to_contain_text("recorded by server")
    expect(page.get_by_role("button", name="Submit feedback")).to_be_disabled()
    expect(page.locator("#guest-application-form")).to_be_hidden()
    for width in (320,360,390,768,1024,1440):
        page.set_viewport_size({"width":width,"height":900})
        actual = page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
        assert actual <= width + 2, f"Guest commerce overflow at {width}px ({actual}px)"
    page.locator("#v1-new").click()
    expect(page.locator("#guest-commerce")).to_be_hidden()
    expect(page.locator("#guest-records")).to_be_hidden()
    expect(page.locator("#application-receipt")).to_be_empty()
    expect(page.locator("#guest-intents")).to_be_empty()
    expect(page.locator("#guest-venue-requests")).to_be_empty()
    page.locator("#v1-hotel").fill("hotel-a")
    page.locator("#v1-kind").select_option("careers")
    page.locator("#v1-name").fill("Synthetic applicant")
    page.locator("#v1-contact").fill("applicant@example.invalid")
    page.locator("#v1-details").fill("Synthetic careers enquiry")
    page.locator("#v1-submit").click()
    expect(page.locator("#guest-application-form")).to_be_visible()
    page.locator("#load-application-vacancies").click()
    page.locator("#application-vacancy").select_option(VENUE)
    page.locator("#application-statement").fill("Synthetic application statement")
    page.locator("#application-consent").check()
    page.get_by_role("button", name="Submit application").click()
    expect(page.locator("#application-receipt")).to_contain_text("submitted")
    expect(page.get_by_role("button", name="Submit application")).to_be_disabled()
    page.locator("#guest-ai-hotel").fill("hotel-a")
    page.locator("#guest-ai-question").fill("What amenities are available?")
    page.locator("#guest-ai-consent").check()
    page.locator("#guest-ai-submit").click()
    expect(page.locator("#guest-ai-answer")).to_contain_text("Contact hotel staff")
    expect(page.locator("#guest-ai-answer")).to_contain_text("did not send a message")
    page.close()
    print("PASS: guest commerce catalog, receipt-scoped stay retry, withdrawal, venue request, preferences, feedback, application, and six viewport checks")
