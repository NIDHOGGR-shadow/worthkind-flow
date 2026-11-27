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
    def select_module(label):
        selector = page.locator("#staff-module-select")
        if selector.is_visible():
            selector.select_option(label=label)
        else:
            page.locator(".staff-v1-nav").get_by_role("button", name=label, exact=True).click()
        expect(page.locator(".staff-v1-nav button[aria-pressed=true]")).to_have_text(label)
        expect(page.locator("#staff-current-module")).to_have_text("Selected module: " + label)
        active = page.locator(".staff-v1-nav button[aria-pressed=true]").get_attribute("aria-controls")
        expect(page.locator("#" + active)).to_be_visible()

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
        if path == "/api/v1/properties/hotel-a/vacancies":
            assert request.headers.get("authorization") is None
            route.fulfill(json={"vacancies":[{"id":MEMBER_ID,"title":"Synthetic vacancy","description":"Published fixture vacancy","deadline":"2026-12-01"}]})
            return
        if path == "/api/v1/properties/hotel-a/menu":
            assert request.headers.get("authorization") is None
            route.fulfill(json={"items":[{"id":TICKET_ID,"name":"Synthetic meal","price_minor":250000,"currency":"NGN"}]})
            return
        assert request.headers.get("authorization") == "Bearer fixture.token.value"
        if path == "/api/v1/staff/properties":
            route.fulfill(json={"properties":[{"id":MEMBER_ID,"slug":"hotel-a","display_name":"Synthetic Hotel A","role":"manager","time_zone":"Africa/Lagos","membership_state":"active"}],"next_cursor":None})
            return
        if "/hotel-b/" in path:
            route.fulfill(status=403, json={"detail": "Access denied"})
            return
        prefix = "/api/v1/properties/hotel-a/staff"
        if path == "/api/v1/properties/hotel-a/vacancies":
            route.fulfill(json={"vacancies":[{"id":MEMBER_ID,"title":"Synthetic vacancy","description":"Published fixture vacancy","deadline":"2026-12-01"}]})
        elif path == prefix + "/content":
            if request.method == "POST":
                state["content"]="draft"
                route.fulfill(json={"id":CASE_ID,"state":"draft"})
            else:
                route.fulfill(json={"content":[{"id":CASE_ID,"key":"hotel-information","version":1,"content":{"title":"Synthetic hotel content","body":"Approved fixture body"},"source_reference":"Fixture source","state":state.get("content","draft")}]})
        elif path == prefix + "/content/" + CASE_ID + "/decision":
            assert request.post_data_json == {"action":"publish"}
            state["content"]="published"
            route.fulfill(json={"id":CASE_ID,"state":"published"})
        elif path == prefix + "/ai/policy":
            if request.method == "PUT":
                assert request.post_data_json["revision"] == 1
                assert request.post_data_json["staff_assist"] is True
                state["ai_policy"] = {**request.post_data_json,"revision":2}
            route.fulfill(json=state.get("ai_policy",{"revision":1,"guest_chat":False,"staff_assist":False,"autonomous_alerts":False,"voice_enabled":False,"max_calls_per_day":20}))
        elif path == prefix + "/ai/sources":
            route.fulfill(json={"sources":[{"id":CASE_ID,"content_key":"hotel","title":"Synthetic approved source","version":1,"state":"published","ai_allowed":True}]})
        elif path == prefix + "/ai/usage":
            route.fulfill(json={"window_hours":24,"used_units":3,"channels":[{"channel":"guest_chat","state":"answered","calls":2,"units":3}]})
        elif path == prefix + "/ai/insights":
            route.fulfill(json={"ticket_counts":[{"category":"maintenance","open_count":2,"overdue_count":1}],"alerts":[{"id":CASE_ID,"ticket_id":TICKET_ID,"category":"maintenance","priority":"high","due_at":"2026-11-26T00:00:00Z","state":state.get("alert","open")}]})
        elif path == prefix + "/ai/alerts/" + CASE_ID + "/acknowledge":
            state["alert"]="acknowledged"
            route.fulfill(json={"acknowledged":True})
        elif path == prefix + "/ai/ticket-proposals":
            if request.method == "POST":
                assert request.post_data_json["subject"] == "Synthetic proposal"
                state["proposal"]="pending"
                route.fulfill(status=201,json={"id":CASE_ID,"approval_required":True})
            else:
                route.fulfill(json={"proposals":[{"id":CASE_ID,"category":"maintenance","priority":"normal","state":state["proposal"],"subject":"Synthetic proposal","description":"Synthetic proposal description","expires_at":"2026-12-01T00:00:00Z","ticket_id":TICKET_ID if state["proposal"]=="executed" else None}] if "proposal" in state else []})
        elif path == prefix + "/ai/ticket-proposals/" + CASE_ID + "/decision":
            assert request.post_data_json == {"approve":True}
            state["proposal"]="executed"
            route.fulfill(json={"id":CASE_ID,"state":"executed","ticket_id":TICKET_ID})
        elif path == prefix + "/ai/chat":
            assert request.post_data_json["consent_to_model_processing"] is True
            route.fulfill(json={"status":"answered","answer":"Synthetic approved hotel information","answer_type":"approved_content_excerpt","sources":[{"id":CASE_ID,"key":"hotel","title":"Synthetic source","version":1}],"action_executed":False})
        elif path == prefix + "/documents" and request.method == "POST":
            assert request.headers.get("content-type") == "application/octet-stream"
            assert request.post_data_buffer == b"fixture bytes"
            route.fulfill(status=201,json={"document_id":CASE_ID,"size":13})
        elif path == prefix + "/documents/" + CASE_ID:
            route.fulfill(status=200,body=b"fixture bytes",headers={"Content-Type":"application/octet-stream","Content-Disposition":"attachment"})
        elif path == prefix + "/purchase-batches":
            if request.method == "POST":
                assert len(request.post_data_json["lines"]) == 1
                state["batch"] = True
                route.fulfill(json={"id":CASE_ID})
            else:
                route.fulfill(json={"batches":[{"id":CASE_ID,"supplier_id":MEMBER_ID,"currency":"NGN","lines":[{"order_id":CASE_ID,"item_id":TICKET_ID,"quantity":"2","received_quantity":"0","unit_price_minor":10000,"state":"requested"}]}] if state.get("batch") else []})
        elif path == prefix + "/pms/reservation-evidence":
            route.fulfill(json={"source":"last_verified_cloudbeds_readback","reservations":[{"id":CASE_ID,"external_reservation_id":"PMS-TEST","provider_state":"confirmed","arrival":"2026-12-01","departure":"2026-12-03","retrieved_at":"2026-11-25T22:00:00Z"}]})
        elif path == prefix + "/pos/reconciliation":
            route.fulfill(json={"source":"loyverse","receipts":[{"id":CASE_ID,"order_id":TICKET_ID,"receipt_number":"POS-TEST","matched":True,"amount_minor":500000,"currency":"NGN","recorded_at":"2026-11-25T22:00:00Z"}]})
        elif path == prefix + "/pms/commands":
            route.fulfill(json={"commands":[{"id":CASE_ID,"operation":"create","state":"unknown","created_at":"2026-11-25T22:00:00Z"}]})
        elif path == prefix + "/native-bookings":
            route.fulfill(json={"source":"native_inventory","bookings":[{"id":CASE_ID,"state":"confirmed","arrival":"2026-12-01","departure":"2026-12-03","room_count":1,"currency":"NGN","total_minor":5000000,"revision":2}]})
        elif path == prefix + "/native-bookings/" + CASE_ID + "/folio":
            route.fulfill(json={"booking_id":CASE_ID,"booking_state":"confirmed","arrival":"2026-12-01","departure":"2026-12-03","currency":"NGN","contract_total_minor":5000000,"rooms":[],"stay":None,"invoice":None,"unlinked_service_charges_excluded":True})
        elif path == prefix + "/procurement":
            route.fulfill(json={"items":[{"id":TICKET_ID,"sku":"TEST","name":"Synthetic stock","unit":"kg","balance":state.get("balance","2.000"),"reorder_level":"3.000","active":True}],"suppliers":[{"id":MEMBER_ID,"name":"Synthetic supplier","external_reference":"fixture","state":"approved"}],"orders":[]})
        elif path == prefix + "/stock/movements":
            assert request.post_data_json["quantity_delta"] == "-1.000"
            assert request.post_data_json["item_id"] == TICKET_ID
            state["balance"]="1.000"
            route.fulfill(json={"id":CASE_ID,"balance":"1.000","duplicate":False})
        elif path == prefix + "/applications":
            route.fulfill(json={"applications":[{"id":CASE_ID,"vacancy_id":MEMBER_ID,"case_id":CASE_ID,"state":state.get("application","submitted"),"statement":"Synthetic statement","qualifications":"Fixture qualifications"}]})
        elif path == prefix + "/applications/" + CASE_ID + "/decision":
            assert request.post_data_json == {"action":"review"}
            state["application"]="reviewing"
            route.fulfill(json={"id":CASE_ID,"state":"reviewing"})
        elif path == prefix + "/feedback":
            route.fulfill(json={"feedback":[{"id":CASE_ID,"case_id":CASE_ID,"rating":4,"state":state.get("feedback","new"),"comment":"Synthetic feedback"}]})
        elif path == prefix + "/feedback/" + CASE_ID + "/review":
            assert request.post_data_json == {"action":"review"}
            state["feedback"]="reviewed"
            route.fulfill(json={"id":CASE_ID,"state":"reviewed"})
        elif path == prefix + "/reservation-intents":
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
        elif path == prefix + "/reports/operations":
            if not state.get("native_report"):
                route.fulfill(status=404,json={"detail":"Fixture fallback"})
            else:
                route.fulfill(json={"scope":"native_property_records","as_of":"2026-11-26T15:00:00Z","cases":{"open":7,"queued":3,"escalated":1,"staff_resolved":2},"tickets":{"open":4,"overdue":1,"urgent_open":1},"rooms":{"registered":12,"out_of_service":1,"dirty":2,"native_occupied":5},"bookings":{"unexpired_holds":1,"confirmed":6},"dining":{"awaiting_acceptance":2,"in_service":1},"stock":{"active_items":5,"at_or_below_reorder":1},"handover_pending":1,"venue_requests_pending":2,"notification_outbox":{"pending":1,"failed":0,"dead_letter":0}})
        elif path == prefix + "/reports/payment-evidence":
            route.fulfill(json={"scope":"cumulative_verified_provider_evidence","as_of":"2026-11-26T15:00:00Z","settlement_verified":False,"open_exceptions":0,"groups":[{"mode":"test","currency":"NGN","payment_count":1,"verified_gross_minor":"500000","processed_refunds_minor":"100000","net_after_refunds_minor":"400000"}]})
        elif path == prefix + "/platform-subscription":
            route.fulfill(json={"status":"contract_recorded","payment_verified":False,"usage_allowance_enforced":True,"used_ai_units":3,"remaining_ai_units":97,"term":{"id":CASE_ID,"plan_name":"Synthetic plan","plan_code":"test","plan_version":1,"currency":"NGN","monthly_price_minor":"1000000","starts_at":"2026-11-01T00:00:00Z","ends_at":"2026-12-01T00:00:00Z","included_ai_calls":100}})
        elif path == prefix + "/finance" and state.get("overview_finance_denied"):
            route.fulfill(status=403,json={"detail":"Finance access denied"})
        elif path == prefix + "/finance":
            route.fulfill(json={"invoices":[{"id":CASE_ID,"dining_order_id":TICKET_ID,"amount_minor":500000,"currency":"NGN","state":"issued"}],"payments":[{"id":TICKET_ID,"invoice_id":CASE_ID,"amount_minor":500000,"currency":"NGN","mode":"test","state":state.get("payment","pending"),"reference":"wf-"+TICKET_ID}],"refunds":[],"exceptions":[]})
        elif path == prefix + "/finance/invoices/" + CASE_ID + "/checkout":
            route.fulfill(json={"id":TICKET_ID,"reference":"wf-"+TICKET_ID,"state":"pending","mode":"test","checkout_url":"https://checkout.paystack.com/synthetic","payment_confirmed":False})
        elif path == prefix + "/finance/payments/" + TICKET_ID + "/verify":
            state["payment"]="verified"
            route.fulfill(json={"id":TICKET_ID,"state":"verified","mode":"test","payment_confirmed":False})
        elif path == prefix + "/cases":
            route.fulfill(json={"property": "hotel-a", "staff_role": "manager",
                               "cases": [{"id": CASE_ID, "status": state["case"], "kind": "human",
                                          "customer_name": "Synthetic guest", "contact": "guest@example.invalid",
                                          "details": "<img src=x>"}]})
        elif path == prefix + "/cases/" + CASE_ID + "/claim":
            state["case"] = "claimed"
            route.fulfill(json={"property": "hotel-a", "case_id": CASE_ID, "status": "claimed"})
        elif path == prefix + "/cases/" + CASE_ID + "/notifications":
            if request.method=="POST":
                assert request.post_data_json=={"event_id":TICKET_ID,"verification_reference":"Verified contact reference"}
                state["email_state"]="pending"
                route.fulfill(json={"id":MEMBER_ID,"state":"pending","duplicate":False})
            else:
                route.fulfill(json={"notifications":[{"event_id":TICKET_ID,"event_type":"case_responded","created_at":"2026-11-26T15:00:00Z","notification_id":MEMBER_ID if state.get("email_state") else None,"state":state.get("email_state","not_queued")}]})
        elif path == prefix + "/cases/" + CASE_ID + "/respond":
            assert request.post_data_json["message"] == "Synthetic response"
            state["case"] = "responded"
            route.fulfill(json={"property": "hotel-a", "case_id": CASE_ID, "status": "responded"})
        elif path == prefix + "/cases/" + CASE_ID + "/control":
            action = request.post_data_json["action"]
            assert action in ("escalate","transfer")
            if action == "transfer":
                assert request.post_data_json["target_membership_id"] == MEMBER_ID
            state["case"] = "claimed" if action == "transfer" else "escalated"
            route.fulfill(json={"case_id": CASE_ID, "state": state["case"]})
        elif path == prefix + "/handover-recipients":
            route.fulfill(json={"recipients":[{"membership_id":MEMBER_ID,"role":"reception","display_name":"Synthetic staff"}],"next_cursor":None})
        elif path == prefix + "/handovers" and request.method == "POST":
            body=request.post_data_json
            assert body["recipient_id"]==MEMBER_ID and body["case_id"]==CASE_ID and body["note"]=="Follow up with the guest"
            state["handover"]={"id":TICKET_ID,"sender_id":CASE_ID,"recipient_id":MEMBER_ID,"case_id":CASE_ID,"note":body["note"],"state":"pending","created_at":"2026-11-26T15:00:00Z","decided_at":None,"decided_by":None}
            route.fulfill(json={"id":TICKET_ID,"state":"pending","duplicate":False})
        elif path == prefix + "/handovers":
            h=state.get("handover")
            route.fulfill(json={"handovers":[h] if h and (h["state"]=="pending" or "pending=false" in request.url) else [],"next_cursor":None})
        elif path == prefix + "/handovers/" + TICKET_ID + "/decision":
            assert request.post_data_json=={"action":"acknowledge"}
            state["handover"].update(state="acknowledged",decided_at="2026-11-26T15:01:00Z",decided_by=MEMBER_ID)
            route.fulfill(json={"id":TICKET_ID,"state":"acknowledged","duplicate":False})
        elif path == prefix + "/attendance":
            attendance={"shift_id":TICKET_ID,"membership_id":MEMBER_ID,"starts_at":"2026-11-25T08:00:00Z","ends_at":"2026-11-25T16:00:00Z","checked_in_at":state.get("checked_in_at"),"checked_out_at":state.get("checked_out_at")}
            route.fulfill(json={"attendance":[attendance],"next_cursor":None})
        elif path == prefix + "/shifts/" + TICKET_ID + "/attendance":
            action=request.post_data_json["action"]
            if action=="check_in":
                state["checked_in_at"]="2026-11-25T08:00:00Z"
            else:
                assert action=="check_out"
                state["checked_out_at"]="2026-11-25T16:00:00Z"
            route.fulfill(json={"shift_id":TICKET_ID,"checked_in_at":state.get("checked_in_at"),"checked_out_at":state.get("checked_out_at"),"duplicate":False})
        elif path == prefix + "/leave" and request.method == "POST":
            body=request.post_data_json
            state["leave"]={"id":TICKET_ID,"membership_id":MEMBER_ID,"starts_at":body["starts_at"],"ends_at":body["ends_at"],"leave_kind":body["leave_kind"],"state":"requested","created_at":"2026-11-26T16:00:00Z"}
            route.fulfill(json={"id":TICKET_ID,"state":"requested","duplicate":False})
        elif path == prefix + "/leave":
            route.fulfill(json={"requests":[state["leave"]] if state.get("leave") else [],"next_cursor":None})
        elif path == prefix + "/leave/" + TICKET_ID + "/decision":
            assert request.post_data_json["action"]=="withdraw"
            state["leave"]["state"]="withdrawn"
            route.fulfill(json={"id":TICKET_ID,"state":"withdrawn","duplicate":False})
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
    page.route("**/api/v1/staff/properties?**", api)
    page.goto(base + "/static/staff-v1.html")
    expect(page.locator("#login")).to_be_enabled()
    page.locator("#email").fill("staff@example.invalid")
    page.locator("#password").fill("synthetic-password")
    page.locator("#login").click()
    expect(page.locator("#staff-workspace")).to_be_visible()
    expect(page.locator("#password")).to_have_value("")
    page.get_by_role("button",name="Find my hotels").click()
    expect(page.locator("#property-discovery-list")).to_contain_text("Synthetic Hotel A")
    page.get_by_role("button",name="Open hotel",exact=True).click()
    expect(page.locator("#property-label")).to_contain_text("Synthetic Hotel A")
    select_module("Communication Hub")
    page.locator("#load-cases").click()
    expect(page.locator(".communication-detail h3")).to_have_text("Synthetic guest")
    expect(page.locator(".communication-entry")).to_have_attribute("aria-pressed","true")
    expect(page.locator("[data-view=ai-studio]")).to_have_count(0)
    expect(page.locator(".communication-detail").get_by_text("<img src=x>", exact=True)).to_be_visible()
    expect(page.locator("#v1-cases img")).to_have_count(0)
    page.locator("#case-search").fill("no-matching-synthetic-record")
    expect(page.locator("#v1-cases")).to_contain_text("No matching cases")
    page.locator("#case-search").fill(CASE_ID)
    expect(page.locator("#case-summary")).to_contain_text("1 of 1")
    page.locator("#case-search").fill("")
    page.get_by_role("button", name="Claim case", exact=True).click()
    expect(page.get_by_role("button", name="Record response", exact=True)).to_be_visible()
    page.locator("#reply-" + CASE_ID).fill("Synthetic response")
    page.get_by_role("button", name="Record response", exact=True).click()
    expect(page.locator("#v1-cases")).to_contain_text("responded")
    page.get_by_text("Service email notifications",exact=True).click()
    page.get_by_role("button",name="Refresh notification records").click()
    page.locator("#email-evidence-"+TICKET_ID).fill("Verified contact reference")
    page.get_by_role("button",name="Queue service email").click()
    expect(page.locator("#v1-cases")).to_contain_text("Queued, not sent")
    page.get_by_text("Case controls", exact=True).click()
    page.locator("#reason-" + CASE_ID).fill("Manager review requested")
    page.get_by_role("button", name="Escalate", exact=True).click()
    expect(page.locator("#v1-cases")).to_contain_text("escalated")
    page.get_by_text("Case controls", exact=True).click()
    page.get_by_role("button",name="Find colleagues",exact=True).click()
    expect(page.locator("#target-"+CASE_ID)).to_contain_text("Synthetic staff")
    page.locator("#target-"+CASE_ID).select_option(MEMBER_ID)
    page.locator("#reason-"+CASE_ID).fill("Transfer to named colleague")
    page.get_by_role("button",name="Transfer",exact=True).click()
    expect(page.locator("#v1-cases")).to_contain_text("claimed")
    page.get_by_role("button",name="Prepare handover",exact=True).click()
    expect(page.locator("#handover-case")).to_have_value(CASE_ID)
    page.get_by_role("button",name="Find handover colleagues",exact=True).click()
    page.locator("#handover-recipient").select_option(MEMBER_ID)
    page.locator("#handover-note").fill("Follow up with the guest")
    page.locator("#handover-submit").click()
    expect(page.locator("#handover-list")).to_contain_text("Follow up with the guest")
    page.get_by_role("button",name="Acknowledge handover",exact=True).click()
    expect(page.locator("#handover-result")).to_contain_text("acknowledged")
    page.locator("#handover-pending").uncheck()
    expect(page.locator("#handover-list")).to_contain_text("acknowledged")
    page.get_by_role("button",name="Create linked department task",exact=True).click()
    expect(page.locator("#tickets-view")).to_be_visible()
    expect(page.locator("#ticket-origin")).to_have_value(CASE_ID)
    expect(page.locator("#ticket-description")).to_have_value("<img src=x>")
    page.locator("#create-ticket").evaluate("(form) => form.reset()")
    select_module("Department work")
    page.locator("#load-tickets").click()
    expect(page.locator("#v1-tickets")).to_contain_text("Overdue")
    page.locator("#ticket-search").fill("no-matching-synthetic-ticket")
    expect(page.locator("#v1-tickets")).to_contain_text("No matching department tickets")
    page.locator("#ticket-search").fill(TICKET_ID)
    expect(page.locator("#ticket-summary")).to_contain_text("1 of 1")
    page.locator("#ticket-search").fill("")
    page.get_by_role("button", name="Claim", exact=True).click()
    expect(page.locator("#v1-tickets")).to_contain_text("assigned")
    page.get_by_role("button", name="Load ticket history").click()
    expect(page.locator("#v1-tickets")).to_contain_text("Synthetic history entry")
    select_module("Memberships")
    page.locator("#accept-membership").click()
    expect(page.locator("#membership-result")).to_contain_text("active")
    select_module("Hotel settings")
    page.locator("#load-settings").click()
    expect(page.locator("#guest-enabled")).to_be_checked()
    page.locator("#guest-enabled").uncheck()
    page.get_by_role("button", name="Save settings", exact=True).click()
    expect(page.locator("#settings-version")).to_have_text("Revision 2")
    select_module("Staff schedule")
    page.locator("#schedule-start").fill("2026-11-24T00:00")
    page.locator("#schedule-end").fill("2026-11-27T00:00")
    page.get_by_role("button", name="Load schedule", exact=True).click()
    expect(page.locator("#staff-roster")).to_contain_text("Synthetic staff")
    expect(page.locator("#profile-member")).to_contain_text("Synthetic staff")
    expect(page.locator("#shift-member")).to_contain_text("Synthetic staff")
    page.get_by_role("button", name="Use for profile or shift").click()
    page.locator("summary").filter(has_text="Schedule a shift").click()
    page.locator("#shift-start").fill("2026-11-25T08:00")
    page.locator("#shift-end").fill("2026-11-25T16:00")
    page.get_by_role("button", name="Schedule shift", exact=True).click()
    expect(page.locator("#staff-shifts")).to_contain_text("scheduled")
    page.get_by_role("button", name="Cancel shift").click()
    expect(page.locator("#staff-shifts")).to_contain_text("cancelled")
    page.locator("#attendance-load").click()
    page.get_by_role("button",name="Check in (own shift)",exact=True).click()
    expect(page.locator("#attendance-list")).to_contain_text("Checked in")
    page.get_by_role("button",name="Check out (own shift)",exact=True).click()
    expect(page.locator("#attendance-list")).to_contain_text("Checked out")
    page.locator("summary").filter(has_text="Request leave").click()
    page.locator("#leave-start").fill("2026-12-02T08:00")
    page.locator("#leave-end").fill("2026-12-03T08:00")
    page.locator("#leave-send").click()
    expect(page.locator("#leave-list")).to_contain_text("requested")
    page.get_by_role("button",name="Withdraw own request",exact=True).click()
    expect(page.locator("#leave-list")).to_contain_text("withdrawn")
    select_module("Room readiness")
    page.locator("#load-rooms").click()
    expect(page.locator("#staff-rooms")).to_contain_text("dirty")
    page.locator("#room-" + TICKET_ID).select_option("inspecting")
    page.get_by_role("button", name="Update room condition").click()
    expect(page.locator("#staff-rooms")).to_contain_text("Revision 2")
    select_module("Reservations")
    page.locator("#load-reservations").click()
    expect(page.locator("#reservation-queue")).to_contain_text("requested")
    page.locator("#reservation-queue").get_by_role("button", name="review", exact=True).click()
    expect(page.locator("#reservation-queue")).to_contain_text("under review")
    page.locator("#pms-start").fill("2026-12-01")
    page.locator("#pms-end").fill("2026-12-03")
    page.get_by_role("button", name="Check provider availability").click()
    expect(page.locator("#pms-availability-result")).to_contain_text("Inventory not held")
    select_module("Dining")
    page.locator("#load-order-menu").click()
    expect(page.locator("#order-menu")).to_contain_text("Synthetic meal")
    page.locator("#order-menu input[data-menu-id]").fill("2")
    page.locator("#dining-submit").click()
    expect(page.locator("#dining-queue")).to_contain_text("submitted")
    page.locator("#dining-queue").get_by_role("button", name="accept", exact=True).click()
    expect(page.locator("#dining-queue")).to_contain_text("accepted")
    select_module("Events")
    page.locator("#load-events").click()
    page.locator("#events-queue").get_by_role("button", name="review", exact=True).click()
    expect(page.locator("#events-queue")).to_contain_text("reviewed")
    select_module("Finance")
    page.locator("#load-finance").click()
    expect(page.locator("#finance-invoices")).to_contain_text("issued")
    page.locator("#finance-invoices input[type=email]").fill("payer@example.invalid")
    page.get_by_role("button", name="Prepare Paystack checkout").click()
    expect(page.get_by_role("link", name="Open test Paystack checkout")).to_have_attribute("href","https://checkout.paystack.com/synthetic")
    page.get_by_role("button", name="Verify provider payment").click()
    expect(page.locator("#finance-payments")).to_contain_text("verified")
    expect(page.locator("#finance-payments")).to_contain_text("Mode: test")
    select_module("Website content")
    page.locator("#load-content-versions").click()
    expect(page.locator("#content-records")).to_contain_text("Synthetic hotel content")
    page.locator("#content-records").get_by_role("button", name="publish", exact=True).click()
    expect(page.locator("#content-records")).to_contain_text("published")
    select_module("Procurement")
    page.locator("#load-procurement").click()
    expect(page.locator("#procurement-records")).to_contain_text("At or below reorder level")
    page.locator("#procurement-forms summary").filter(has_text="Record stock movement").click()
    movement = page.locator("#procurement-forms details").filter(has_text="Record stock movement")
    movement.get_by_label("Stock item ID", exact=True).fill(TICKET_ID)
    movement.get_by_label("Quantity change (negative for consumption)").fill("-1.000")
    movement.get_by_label("Reason", exact=True).fill("Synthetic consumption")
    movement.get_by_role("button", name="Record stock movement", exact=True).click()
    expect(page.locator("#procurement-records")).to_contain_text("Balance: 1.000")
    select_module("Careers")
    page.locator("#load-vacancies").click()
    expect(page.locator("#vacancy-records")).to_contain_text("Synthetic vacancy")
    page.locator("#load-applications").click()
    expect(page.locator("#application-records")).to_contain_text("Synthetic statement")
    page.locator("#application-records").get_by_role("button", name="review", exact=True).click()
    expect(page.locator("#application-records")).to_contain_text("reviewing")
    select_module("Guest feedback")
    page.locator("#load-feedback").click()
    page.locator("#feedback-records").get_by_role("button", name="review", exact=True).click()
    expect(page.locator("#feedback-records")).to_contain_text("reviewed")
    select_module("Management")
    page.locator("#management-refresh").click()
    expect(page.locator("#management-summary")).to_contain_text("Items at/below reorder level")
    expect(page.locator("#management-summary")).to_contain_text("Overdue work")
    expect(page.locator("#management-summary")).to_contain_text("Clean rooms")
    state["overview_finance_denied"] = True
    page.locator("#management-refresh").click()
    expect(page.locator("#management-summary")).to_contain_text("Showing 7 verified sections")
    expect(page.locator("#management-summary")).not_to_contain_text("Issued invoices")
    state["overview_finance_denied"] = False
    state["native_report"] = True
    page.locator("#management-refresh").click()
    expect(page.locator("#management-summary")).to_contain_text("Property-wide native records")
    expect(page.locator("#management-summary")).to_contain_text("Native occupied rooms")
    page.get_by_text("Verified payment evidence",exact=True).click()
    page.locator("#payment-report-load").click()
    expect(page.locator("#payment-report-records")).to_contain_text("Test provider evidence")
    expect(page.locator("#payment-report-records")).to_contain_text("NGN 4,000.00")
    page.get_by_text("Worthkind subscription and usage",exact=True).click()
    page.locator("#subscription-load").click()
    expect(page.locator("#subscription-records")).to_contain_text("Remaining units: 97")
    page.get_by_role("button",name="Open procurement",exact=True).click()
    expect(page.locator("#procurement-view")).to_be_visible()
    select_module("Procurement")
    page.locator("#batch-supplier").fill(MEMBER_ID)
    page.locator("#batch-lines [data-field=item_id]").fill(TICKET_ID)
    page.locator("#batch-lines [data-field=quantity]").fill("2")
    page.locator("#batch-lines [data-field=unit_price_minor]").fill("10000")
    page.locator("#batch-submit").click()
    expect(page.locator("#purchase-batch-records")).to_contain_text("Purchase batch")
    select_module("Native bookings")
    page.locator("#native-staff-load").click()
    page.get_by_role("button", name="Load stay and folio").click()
    expect(page.locator("#native-staff-list")).to_contain_text("Unlinked service charges are excluded")
    select_module("Integrations")
    page.locator("#pms-evidence-load").click()
    expect(page.locator("#pms-evidence-list")).to_contain_text("PMS-TEST")
    page.locator("#pos-evidence-load").click()
    expect(page.locator("#pos-evidence-list")).to_contain_text("Receipt matched")
    page.locator("#pms-command-load").click()
    expect(page.locator("#pms-command-list")).to_contain_text("Investigate provider outcome")
    select_module("Hotel settings")
    page.get_by_text("Assistant settings",exact=True).click()
    page.locator("#ai-policy-load").click()
    expect(page.locator("#ai-policy-form")).to_be_visible()
    page.locator("#ai-staff-assist").check()
    page.get_by_role("button", name="Save AI policy").click()
    expect(page.locator("#ai-policy-revision")).to_contain_text("Revision 2")
    select_module("Communication Hub")
    page.get_by_text("Staff information assistant",exact=True).click()
    page.locator("#ai-staff-question").fill("What hotel information is approved?")
    page.locator("#ai-staff-consent").check()
    page.get_by_role("button", name="Ask assistant", exact=True).click()
    expect(page.locator("#ai-staff-answer")).to_contain_text("Synthetic approved hotel information")
    select_module("Hotel settings")
    page.locator("#ai-sources-load").click()
    expect(page.locator("#ai-source-list")).to_contain_text("Retrieval allowed")
    page.locator("#ai-usage-load").click()
    expect(page.locator("#ai-usage-list")).to_contain_text("Used units: 3")
    select_module("Department work")
    page.get_by_text("Operational alerts and approvals",exact=True).click()
    page.locator("#ai-insights-load").click()
    expect(page.locator("#ai-insights-list")).to_contain_text("1 overdue")
    page.get_by_role("button",name="Acknowledge alert").click()
    expect(page.locator("#ai-insights-list")).to_contain_text("acknowledged")
    page.locator("#ai-proposal-category").select_option("maintenance")
    page.locator("#ai-proposal-subject").fill("Synthetic proposal")
    page.locator("#ai-proposal-description").fill("Synthetic proposal description")
    page.locator("#ai-proposal-submit").click()
    expect(page.locator("#ai-proposals-list")).to_contain_text("pending")
    page.get_by_role("button",name="Approve proposal and create ticket").click()
    expect(page.locator("#ai-proposals-list")).to_contain_text("Created ticket")
    select_module("Documents")
    page.locator("#document-file").set_input_files({"name":"fixture.bin","mimeType":"application/octet-stream","buffer":b"fixture bytes"})
    page.locator("#document-upload-submit").click()
    expect(page.locator("#document-id")).to_have_value(CASE_ID)
    page.locator("#document-download-submit").click()
    expect(page.locator("#document-download-link")).to_be_visible()
    expect(page.locator("#document-download-link")).to_have_attribute("download","private-document-"+CASE_ID+".bin")
    for label in ("Communication Hub", "Department work", "Memberships", "Staff schedule", "Room readiness", "Hotel settings","Reservations","Catalog","Dining","Events","Finance","Management","Website content","Procurement","Careers","Guest feedback","Native bookings","Integrations","Documents"):
        select_module(label)
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
    expect(page.locator("#attendance-list")).to_be_empty()
    expect(page.locator("#leave-list")).to_be_empty()
    expect(page.locator("#handover-list")).to_be_empty()
    expect(page.locator("#handover-recipient option")).to_have_count(1)
    expect(page.locator("#profile-member option")).to_have_count(1)
    expect(page.locator("#shift-member option")).to_have_count(1)
    expect(page.locator("#case-search")).to_have_value("")
    expect(page.locator("#ticket-search")).to_have_value("")
    expect(page.locator("#staff-rooms")).to_be_empty()
    expect(page.locator("#finance-payments")).to_be_empty()
    expect(page.locator("#dining-queue")).to_be_empty()
    expect(page.locator("#reservation-queue")).to_be_empty()
    expect(page.locator("#application-records")).to_be_empty()
    expect(page.locator("#management-summary")).to_be_empty()
    expect(page.locator("#procurement-records")).to_be_empty()
    expect(page.locator("#ai-staff-answer")).to_be_empty()
    expect(page.locator("#document-download-link")).to_be_hidden()
    expect(page.locator("#document-id")).to_have_value("")
    select_module("Communication Hub")
    page.locator("#load-cases").click()
    expect(page.locator("#staff-message")).to_contain_text("not authorized")
    expect(page.locator("#v1-cases")).to_be_empty()
    page.locator("#signout").click()
    expect(page.locator("#login-panel")).to_be_visible()
    expect(page.locator("#staff-workspace")).to_be_hidden()
    expect(page.locator("#property-discovery-list")).to_be_empty()
    assert all(path.startswith("/api/v1/") for _, path in calls)
    page.close()
    check_platform_crm(browser, base)
    print("PASS: staff v1 Chromium fixture journey and 114 authenticated-layout checks")

def check_platform_crm(browser, base):
    page=browser.new_page(viewport={"width":390,"height":900})
    page.on("dialog",lambda d:d.accept())
    state={"authorized":False,"row":None}
    page.route("**/staff-auth-config.json",lambda r:r.fulfill(json={"enabled":True,"provider":"supabase","url":PROVIDER,"publishableKey":"sb_publishable_fixture"}))
    page.route(PROVIDER+"/auth/v1/**",lambda r:r.fulfill(json={"access_token":"fixture.token.value","expires_in":3600,"user":{"role":"authenticated","is_anonymous":False,"email_confirmed_at":"2026-11-26"}}))
    def api(route):
        req=route.request
        assert req.headers.get("authorization")=="Bearer fixture.token.value"
        if not state["authorized"]:
            route.fulfill(status=403,json={"detail":"Denied"})
        elif req.method=="GET":
            route.fulfill(json={"prospects":[state["row"]] if state["row"] else [],"next_cursor":None})
        elif urlsplit(req.url).path.endswith("/change"):
            body=req.post_data_json
            assert body["action"]=="stage" and body["value"]=="discovery" and body["revision"]==1
            state["row"].update(stage="discovery",revision=2)
            route.fulfill(json={"id":CASE_ID,"stage":"discovery","revision":2,"duplicate":False,"outreach_allowed":False})
        else:
            state["row"]={**req.post_data_json,"id":CASE_ID,"stage":"prospect","revision":1,"outreach_allowed":False,"created_at":"2026-11-26T15:00:00Z"}
            route.fulfill(json={"id":CASE_ID,"stage":"prospect","revision":1,"duplicate":False})
    page.route("**/api/v1/platform/crm/prospects**",api)
    page.goto(base+"/static/platform-crm.html")
    def login():
        page.locator("#platform-email").fill("fixture@example.invalid")
        page.locator("#platform-password").fill("fixture-password")
        page.locator("#platform-login-button").click()
    login()
    expect(page.locator("#platform-login-status")).to_contain_text("access denied")
    expect(page.locator("#platform-workspace")).to_be_hidden()
    state["authorized"]=True
    login()
    expect(page.locator("#platform-workspace")).to_be_visible()
    page.locator("#platform-key").fill("hotel-fixture")
    page.locator("#platform-name").fill("Synthetic hotel prospect")
    page.locator("#platform-source").fill("Fixture business enquiry")
    page.locator("#platform-create-send").click()
    expect(page.locator("#platform-list")).to_contain_text("Synthetic hotel prospect")
    page.locator("#platform-action").select_option("stage:discovery")
    page.locator("#platform-evidence").fill("Discovery meeting reference")
    page.locator("#platform-change-send").click()
    expect(page.locator("#platform-detail-status")).to_contain_text("Discovery")
    for width in WIDTHS:
        page.set_viewport_size({"width":width,"height":900})
        assert page.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")<=width+2
    page.locator("#platform-signout").click()
    expect(page.locator("#platform-workspace")).to_be_hidden()
    expect(page.locator("#platform-list")).to_be_empty()
    page.close()
    print("PASS: platform CRM independent access, evidenced decision and six viewport checks")
