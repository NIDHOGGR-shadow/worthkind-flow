import io
import wave
import os
from pathlib import Path
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
        elif path == prefix + "/ai/voice":
            assert req.headers.get("x-voice-consent") == "true"
            assert req.headers.get("content-type") == "audio/wav"
            assert req.headers.get("authorization") is None
            assert req.post_data_buffer[:4] == b"RIFF"
            route.fulfill(json={"status":"handoff","reason":"voice_unavailable","answer":None,"sources":[],"action_executed":False,"human_handoff_required":True})
        elif path == prefix + "/ai/chat":
            assert req.post_data_json["consent_to_model_processing"] is True
            route.fulfill(json={"status":"handoff","reason":"model_unavailable","answer":None,"sources":[],"action_executed":False,"human_handoff_required":True})
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
            state["case_status"] = "queued"
            state["decision"] = None
            route.fulfill(json={"case_id":CASE,"receipt_token":state["token"],"status":"queued","kind":state["kind"]})
        elif path == prefix + "/enquiries/" + CASE:
            assert req.headers.get("x-receipt-token") == state["token"]
            route.fulfill(json={"case_id":CASE,"status":state["case_status"],"kind":state["kind"],"staff_reply":"Fixture staff response"})
        elif path.startswith(private):
            assert req.headers.get("x-receipt-token") == state["token"]
            assert state["token"] not in req.url
            if path == private + "/resolution":
                if req.method == "POST":
                    assert req.post_data_json["resolution_id"] == INTENT
                    state["decision"] = req.post_data_json["decision"]
                    state["case_status"] = "queued" if state["decision"] == "reopen" else "resolved"
                    route.fulfill(json={"resolution_id":INTENT,"decision":state["decision"],"duplicate":False,"current_case_status":state["case_status"]})
                else:
                    route.fulfill(json={"case_id":CASE,"case_status":state["case_status"],"resolution_id":INTENT,"guest_decision":state["decision"],"guest_confirmed":state["decision"]=="confirm","awaiting_guest_confirmation":state["case_status"]=="resolved" and state["decision"] is None})
            elif path == private + "/dining/orders":
                if req.method == "POST":
                    body=req.post_data_json
                    assert body["room_id"] is None and body["lines"]==[{"item_id":ROOM,"quantity":2}]
                    assert state["kind"]=="booking"
                    state.setdefault("order_attempts",[]).append(body)
                    if len(state["order_attempts"])==1:
                        route.fulfill(status=503,json={"detail":"Outcome unknown"})
                        return
                    assert state["order_attempts"][0]==body
                    state["order"]={"id":INTENT,"state":"submitted","room_id":None,"currency":"NGN","total_minor":500000,"created_at":"2026-11-26T15:00:00Z","lines":[{"name":"Synthetic meal","quantity":2,"unit_price_minor":250000}]}
                    route.fulfill(json={**state["order"],"payment_confirmed":False,"duplicate":False})
                else:
                    route.fulfill(json={"orders":[state["order"]] if state.get("order") else [],"next_cursor":None})
            elif path == private + "/preferences":
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
                if req.method == "POST":
                    assert req.post_data_json["consent"] is True
                    assert req.post_data_json["vacancy_id"] == VENUE
                    state["application"]={"id":INTENT,"vacancy_id":VENUE,"title":"Synthetic vacancy","state":"submitted","created_at":"2026-11-26T15:00:00Z"}
                    route.fulfill(json={"id":INTENT,"state":"submitted"})
                else:
                    route.fulfill(json={"applications":[state["application"]] if state.get("application") else [],"next_cursor":None})
            elif path == private + "/applications/" + INTENT + "/withdraw":
                state["application"]["state"]="withdrawn"
                route.fulfill(json={"id":INTENT,"state":"withdrawn"})
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
                if req.method == "POST":
                    body=req.post_data_json
                    assert body["venue_id"] == VENUE
                    state["venue"]={"id":VENUE,"venue_id":VENUE,"venue_name":"Synthetic hall","starts_at":body["starts_at"],"ends_at":body["ends_at"],"attendance":body["attendance"],"state":"requested"}
                    route.fulfill(json={"id":VENUE,"state":"requested"})
                else:
                    route.fulfill(json={"requests":[state["venue"]] if state.get("venue") else [],"next_cursor":None})
            else:
                route.fulfill(status=404,json={"detail":"Not found"})
        else:
            route.fulfill(status=404,json={"detail":"Not found"})

    page.route("**/api/v1/properties/**", api)
    page.goto(base + "/static/guest-v1.html")
    expect(page.locator("#home")).to_have_attribute("data-guest-view","home")
    page.keyboard.press("Tab")
    expect(page.locator(".skip-link")).to_be_focused()
    for target in page.locator(".guest-service-index a").evaluate_all("(links) => links.map(a => a.getAttribute('href'))"):
        assert page.locator(target).count() == 1
    page.locator(".skip-link").evaluate("(element) => element.blur()")
    if os.getenv("WF_BROWSER_SCREENSHOT_DIR"):
        output = Path(os.environ["WF_BROWSER_SCREENSHOT_DIR"])
        output.mkdir(parents=True, exist_ok=True)
        for width in (390, 1440):
            page.set_viewport_size({"width":width,"height":900})
            page.screenshot(path=str(output / f"guest-home-{width}.png"),full_page=True)
        page.set_viewport_size({"width":390,"height":900})
    expect(page.locator("#request")).to_be_hidden()
    assert page.locator(".guest-hero h1").evaluate("(n) => getComputedStyle(n).color") == "rgb(248, 246, 240)"
    page.locator(".guest-service-index a[href='#hotel-catalog']").click()
    expect(page.locator("#hotel-catalog")).to_be_visible()
    expect(page.locator(".guest-hero")).to_be_hidden()
    page.locator("#catalog-slug").fill("hotel-a")
    page.get_by_role("button", name="Load hotel", exact=True).click()
    expect(page.locator("#catalog-content")).to_contain_text("Synthetic deluxe")
    expect(page.locator("#catalog-content")).to_contain_text("nonbinding display rate")
    page.locator("#catalog-arrival").fill("2026-12-01")
    page.locator("#catalog-departure").fill("2026-12-03")
    page.locator("#catalog-guests").fill("2")
    page.get_by_role("button",name="Load hotel",exact=True).click()
    page.get_by_role("button",name="View room",exact=True).click()
    expect(page.locator("#catalog-room-name")).to_have_text("Synthetic deluxe")
    expect(page.locator("#catalog-room-info")).to_contain_text("nonbinding display rate")
    page.get_by_role("button",name="Review room enquiry",exact=True).click()
    expect(page.locator("#selected-stay-summary")).to_be_visible()
    expect(page.locator("#selected-stay-name")).to_have_text("Synthetic deluxe")
    expect(page.locator("#selected-stay-dates")).to_contain_text("2026-12-01 to 2026-12-03")
    expect(page.locator("#v1-hotel")).to_have_value("hotel-a")
    page.locator("#v1-name").fill("Synthetic guest")
    page.locator("#v1-contact").fill("guest@example.invalid")
    page.locator("#v1-details").fill("Synthetic room enquiry")
    page.locator("#v1-submit").click()
    expect(page.locator("#v1-track")).to_be_visible()
    expect(page.locator("#track-heading")).to_be_focused()
    state["case_status"] = "resolved"
    page.locator("#v1-refresh").click()
    expect(page.locator("#guest-resolution")).to_be_visible()
    page.locator("#resolution-load").click()
    expect(page.locator("#resolution-confirm")).to_be_visible()
    page.locator("#resolution-reopen").click()
    expect(page.locator("#guest-resolution-status")).to_contain_text("You reopened")
    expect(page.locator("#v1-case-status")).to_contain_text("waiting for staff")
    state["case_status"] = "resolved"
    state["decision"] = None
    page.locator("#v1-refresh").click()
    page.locator("#resolution-load").click()
    page.locator("#resolution-confirm").click()
    expect(page.locator("#v1-case-status")).to_have_text("Resolved and confirmed by you.")
    expect(page.locator("#resolution-confirm")).to_be_hidden()

    expect(page.locator("#guest-commerce")).to_be_hidden()
    expect(page.locator("#v1-copy")).to_be_hidden()
    page.locator("#v1-reveal").click()
    expect(page.locator("#v1-copy")).to_be_visible()
    page.evaluate("""() => Object.defineProperty(navigator, 'clipboard', {configurable:true,value:{writeText: async text => { window.__copiedReceipt = text; }}})""")
    page.locator("#v1-copy").click()
    expect(page.locator("#receipt-copy-status")).to_contain_text("Receipt copied")
    assert page.evaluate("window.__copiedReceipt") == page.locator("#v1-receipt").text_content()
    page.evaluate("delete window.__copiedReceipt")
    page.locator("#v1-reveal").click()
    expect(page.locator("#v1-copy")).to_be_hidden()
    page.locator("#guest-journey-bar a[href='#guest-commerce']").click()
    expect(page.locator("#guest-commerce")).to_be_visible()
    state["case_status"]="queued"
    expect(page.locator("#stay-room")).to_have_value(ROOM)
    expect(page.locator("#stay-adults")).to_have_value("2")
    expect(page.locator("#stay-arrival")).to_have_value("2026-12-01")
    page.locator("#guest-dining-menu").click()
    page.locator("#guest-dining-items select").select_option(ROOM)
    page.locator("#guest-dining-items input").fill("2")
    expect(page.locator("#guest-dining-total")).to_contain_text("Menu estimate")
    page.locator("#guest-dining-send").click()
    expect(page.locator("#guest-dining-send")).to_have_text("Retry unchanged order")
    expect(page.locator("#guest-dining-items select")).to_be_disabled()
    page.locator("#guest-dining-send").click()
    expect(page.locator("#guest-dining-orders")).to_contain_text("2 × Synthetic meal")
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
    expect(page.locator("#guest-venue-requests")).to_contain_text("Synthetic hall")
    page.locator("#guest-venue-load").click()
    expect(page.locator("#guest-venue-requests")).to_contain_text("20 attendees")
    page.locator("#guest-journey-bar a[href='#guest-records']").click()
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
        if width in (390,1440) and os.getenv("WF_BROWSER_SCREENSHOT_DIR"):
            page.screenshot(path=str(output / f"guest-active-{width}.png"),full_page=True)
    page.locator("#guest-journey-bar a[href='#v1-track']").click()
    page.locator("#v1-new").click()
    expect(page.locator("#guest-commerce")).to_be_hidden()
    expect(page.locator("#v1-receipt")).to_be_empty()
    expect(page.locator("#receipt-copy-status")).to_be_empty()
    expect(page.locator("#v1-reveal")).to_have_attribute("aria-expanded","false")
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
    page.locator("#guest-journey-bar a[href='#guest-records']").click()
    expect(page.locator("#guest-application-form")).to_be_visible()
    page.locator("#load-application-vacancies").click()
    page.locator("#application-vacancy").select_option(VENUE)
    page.locator("#application-statement").fill("Synthetic application statement")
    page.locator("#application-consent").check()
    page.get_by_role("button", name="Submit application").click()
    expect(page.locator("#application-receipt")).to_contain_text("submitted")
    expect(page.get_by_role("button", name="Submit application")).to_be_disabled()
    page.locator("#guest-applications-load").click()
    expect(page.locator("#guest-applications-list")).to_contain_text("Synthetic vacancy")
    page.get_by_role("button",name="Withdraw application").click()
    expect(page.locator("#guest-applications-list")).to_contain_text("withdrawn")
    page.locator(".guest-nav a[href='#home']").click()
    page.locator(".guest-service-index a[href='#guest-ai']").click()
    page.locator("#guest-ai-hotel").fill("hotel-a")
    page.locator("#guest-ai-question").fill("What amenities are available?")
    page.locator("#guest-ai-consent").check()
    page.locator("#guest-ai-submit").click()
    expect(page.locator("#guest-ai-answer")).to_contain_text("Contact hotel staff")
    expect(page.locator("#guest-ai-answer")).to_contain_text("did not send a message")
    page.locator("#guest-ai-human").click()
    expect(page.locator("#v1-track")).to_be_visible()
    expect(page.locator("#receipt-copy-status")).to_contain_text("existing request")
    audio = io.BytesIO()
    with wave.open(audio, "wb") as sample:
        sample.setnchannels(1)
        sample.setsampwidth(2)
        sample.setframerate(16000)
        sample.writeframes(bytes(3200))
    page.locator(".guest-nav a[href='#home']").click()
    page.locator(".guest-service-index a[href='#guest-voice']").click()
    page.locator("#voice-hotel").fill("hotel-a")
    page.locator("#voice-file").set_input_files({"name":"fixture.wav","mimeType":"audio/wav","buffer":audio.getvalue()})
    page.locator("#voice-consent").check()
    page.locator("#voice-send").click()
    expect(page.locator("#voice-answer")).to_contain_text("Contact hotel staff")
    expect(page.locator("#voice-consent")).not_to_be_checked()
    for view in ("home","hotel-catalog","guest-ai","guest-voice","guest-careers","v1-track","guest-commerce","native-guest","guest-records"):
        page.evaluate("(view) => document.dispatchEvent(new CustomEvent('flow:guest-view', {detail:view}))",view)
        if view == "home":
            expect(page.get_by_role("button",name="View my request")).to_be_enabled()
        for width in (320,390,768,1440):
            page.set_viewport_size({"width":width,"height":900})
            assert page.evaluate("Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)") <= width+2, f"{view}: overflow at {width}"
            if width in (390,1440) and os.getenv("WF_BROWSER_SCREENSHOT_DIR"):
                page.locator("body").evaluate("() => { if(document.activeElement) document.activeElement.blur(); window.scrollTo(0,0); }")
                page.screenshot(path=str(output / f"guest-{'home-with-receipt' if view == 'home' else view}-{width}.png"),full_page=True)
    page.go_back()
    expect(page.locator("#home")).to_have_attribute("data-guest-view","native-guest")
    page.go_forward()
    expect(page.locator("#home")).to_have_attribute("data-guest-view","guest-records")
    page.locator("#guest-journey-bar a[href='#v1-track']").click()
    page.locator("#v1-new").click()
    page.locator(".guest-nav a[href='#home']").click()
    page.locator(".guest-service-index a[href='#guest-ai']").click()
    page.locator("#guest-ai-hotel").fill("hotel-a")
    page.locator("#guest-ai-question").fill("Can reception help with my stay?")
    page.locator("#guest-ai-consent").check()
    page.locator("#guest-ai-submit").click()
    expect(page.locator("#guest-ai-answer")).to_contain_text("Contact hotel staff")
    page.locator("#guest-ai-human").click()
    expect(page.locator("#v1-hotel")).to_have_value("hotel-a")
    expect(page.locator("#v1-kind")).to_have_value("human")
    expect(page.locator("#v1-details")).to_have_value("Can reception help with my stay?")
    expect(page.locator("#v1-submit-status")).to_contain_text("Nothing has been sent yet")
    expect(page.locator("#v1-track")).to_be_hidden()
    page.close()
    print("PASS: guest commerce catalog, receipt-scoped stay retry, withdrawal, venue request, preferences, feedback, application, and six viewport checks")
