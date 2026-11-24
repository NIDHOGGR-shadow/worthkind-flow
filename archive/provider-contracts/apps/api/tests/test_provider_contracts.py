"""Fail-closed local integration contracts: no hotel, messaging or money calls."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from provider_contracts import (
    Action, ACTION_SERVICE, DEFAULT_INTEGRATIONS, DisabledAdapter,
    FixtureAdapter, IntegrationConflict, IntegrationNotConnected,
    IntegrationOutcome, IntegrationRequest, Service,
)


def request_for(action, *, property_slug="demo-hotel", request_key="local-contract-key-001",
                reference="synthetic-internal-reference-1"):
    return IntegrationRequest(
        property_slug=property_slug, action=action, idempotency_key=request_key,
        reference=reference,
    )


@pytest.mark.parametrize("action", list(Action))
def test_all_live_provider_actions_fail_closed_when_not_connected(action):
    result = DEFAULT_INTEGRATIONS.capability_summary()
    assert result["production_connected"] is False
    assert result["live_bookings"] is False
    assert result["live_payments"] is False
    assert result["live_messages"] is False
    assert result["live_ai"] is False
    assert len(result["services"]) == len(Service)
    for item in result["services"]:
        assert item["configured"] is False
        assert item["authoritative"] is False
        assert item["mode"] == "disabled"
    with pytest.raises(IntegrationNotConnected, match="not connected"):
        DEFAULT_INTEGRATIONS.attempt(request_for(action))


@pytest.mark.parametrize("action", list(Action))
def test_fixture_is_simulation_only_idempotent_and_property_scoped(action):
    service = ACTION_SERVICE[action]
    adapter = FixtureAdapter(service, "demo-hotel")
    query = request_for(action)
    response = adapter.invoke(query)
    assert adapter.invoke(query) == response
    assert response.service is service
    assert response.action is action
    assert response.property_slug == "demo-hotel"
    assert response.state == "simulated"
    assert response.source == "synthetic_fixture"
    assert response.confirmed is False
    assert response.paid is False
    assert response.delivered is False
    assert response.live_room_inventory is False
    assert adapter.capability().configured is False
    assert adapter.capability().authoritative is False
    assert adapter.capability().mode == "fixture"

    with pytest.raises(IntegrationConflict):
        adapter.invoke(request_for(action, reference="different-synthetic-source"))
    with pytest.raises(PermissionError, match="Cross-property"):
        adapter.invoke(request_for(action, property_slug="demo-hotel-two"))


def test_service_action_crossing_is_rejected_for_fixtures_and_disabled():
    request = request_for(Action.VERIFY_HOTEL_PAYMENT)
    disabled = DisabledAdapter(Service.PMS_AVAILABILITY)
    fixture = FixtureAdapter(Service.PMS_AVAILABILITY, "demo-hotel")
    with pytest.raises(ValueError, match="Service/action"):
        disabled.invoke(request)
    with pytest.raises(ValueError, match="Service/action"):
        fixture.invoke(request)


@pytest.mark.parametrize("fake_truth", [
    {"confirmed": True},
    {"paid": True},
    {"delivered": True},
    {"live_room_inventory": True},
])
def test_simulated_outcome_cannot_fake_real_authority(fake_truth):
    with pytest.raises(ValidationError):
        IntegrationOutcome(
            service=Service.HOTEL_PAYMENT,
            action=Action.VERIFY_HOTEL_PAYMENT,
            property_slug="demo-hotel",
            state="simulated",
            source="synthetic_fixture",
            detail="synthetic-only",
            **fake_truth,
        )


def test_invalid_provenance_and_service_mismatch_are_rejected():
    base = dict(
        service=Service.HOTEL_PAYMENT,
        action=Action.VERIFY_HOTEL_PAYMENT,
        property_slug="demo-hotel", detail="unverified",
    )
    for changes in (
        {"state": "verified", "source": "synthetic_fixture"},
        {"state": "simulated", "source": "none"},
        {"state": "not_connected", "source": "synthetic_fixture"},
        {"state": "simulated", "source": "synthetic_fixture",
         "service": Service.PMS_RESERVATION},
    ):
        with pytest.raises(ValidationError):
            IntegrationOutcome(**(base | changes))


@pytest.mark.parametrize("bad_field", [
    {"card_number": "4111111111111111"},
    {"bank_token": "secret"},
    {"recipient_contact": "guest@example.invalid"},
    {"model_prompt": "Invent a payment confirmation."},
])
def test_generic_provider_contract_refuses_secret_and_customer_fields(bad_field):
    with pytest.raises(ValidationError):
        IntegrationRequest(
            property_slug="demo-hotel",
            action=Action.SEND_GUEST_MESSAGE,
            idempotency_key="non-network-key-001",
            reference="synthetic-case-0123456789",
            **bad_field,
        )


def test_invalid_property_and_key_are_rejected():
    with pytest.raises(ValidationError):
        request_for(Action.CHECK_AVAILABILITY, property_slug="../../hotel")
    with pytest.raises(ValidationError):
        request_for(Action.REQUEST_RESERVATION, request_key="short")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_DATABASE_PATH", str(tmp_path / "providers.sqlite3"))
    monkeypatch.setenv(
        "WF_DEV_STAFF_KEYS_JSON",
        json.dumps({"demo-hotel": "key-one", "demo-hotel-two": "key-two"})
    )
    with TestClient(main.app) as live:
        yield live


def test_integration_readiness_is_real_api_protected_and_never_claims_delivery(client):
    uri = "/api/properties/demo-hotel/staff/integrations/readiness"
    denied = client.get(uri)
    foreign_key = client.get(uri, headers={"X-Staff-Key": "key-two"})
    assert denied.status_code == 401
    assert foreign_key.status_code == 401
    assert denied.headers["Cache-Control"] == "no-store"
    assert foreign_key.headers["Cache-Control"] == "no-store"

    response = client.get(uri, headers={"X-Staff-Key": "key-one"})
    assert response.status_code == 200
    data = response.json()
    assert data["property"] == "demo-hotel"
    assert data["source"] == "disabled_development_adapters"
    assert data["production_connected"] is False
    assert len(data["services"]) == 5
    assert not any(item["configured"] for item in data["services"])
    assert response.headers["Cache-Control"] == "no-store"

    other = client.get(
        "/api/properties/demo-hotel-two/staff/integrations/readiness",
        headers={"X-Staff-Key": "key-two"},
    )
    assert other.status_code == 200
    assert other.json()["property"] == "demo-hotel-two"
    assert other.json()["services"] == data["services"]


def test_unconfigured_provider_never_changes_booking_capabilities(client):
    booking = client.get("/api/properties/demo-hotel/booking-capabilities")
    assert booking.status_code == 200
    data = booking.json()
    assert data["availability"] is False
    assert data["payments"] is False
    assert data["confirmed_reservations"] is False
