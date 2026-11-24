"""Provider-independent hospitality integration contracts (development).

This module has ZERO network clients and cannot authorize real payments, room
holds, booking confirmations, message delivery or AI answers. Future adapters
must separately verify the actual hotel/provider authority and replace the
disabled registry under a reviewed production identity/permissions boundary.

Never interpret a fixture's simulated result as a real provider outcome.
"""
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Service(str, Enum):
    PMS_AVAILABILITY = "pms_availability"
    PMS_RESERVATION = "pms_reservation"
    HOTEL_PAYMENT = "hotel_payment"
    GUEST_MESSAGING = "guest_messaging"
    OPTIONAL_AI = "optional_ai"


class Action(str, Enum):
    CHECK_AVAILABILITY = "check_availability"
    REQUEST_RESERVATION = "request_reservation"
    VERIFY_HOTEL_PAYMENT = "verify_hotel_payment"
    SEND_GUEST_MESSAGE = "send_guest_message"
    REQUEST_GROUNDED_ANSWER = "request_grounded_answer"


ACTION_SERVICE: dict[Action, Service] = {
    Action.CHECK_AVAILABILITY: Service.PMS_AVAILABILITY,
    Action.REQUEST_RESERVATION: Service.PMS_RESERVATION,
    Action.VERIFY_HOTEL_PAYMENT: Service.HOTEL_PAYMENT,
    Action.SEND_GUEST_MESSAGE: Service.GUEST_MESSAGING,
    Action.REQUEST_GROUNDED_ANSWER: Service.OPTIONAL_AI,
}


class IntegrationNotConnected(RuntimeError):
    """Fail closed instead of falling back to a fake success response."""


class IntegrationConflict(ValueError):
    """Same idempotency key reused with a different request fingerprint."""


class IntegrationRequest(BaseModel):
    """No arbitrary bank/card fields, bearer tokens, guest PII or prompt payloads.

    Full provider-specific requests will require typed, separate models and an
    authorized server-side identity, consent and source-of-truth integration.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    property_slug: str = Field(
        min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]+$"
    )
    action: Action
    idempotency_key: str = Field(
        min_length=12, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )
    reference: str = Field(
        min_length=8, max_length=120, pattern=r"^[A-Za-z0-9:_-]+$"
    )
    # The only payload accepted in this generic contract is an opaque internal
    # reference. No PAN, bank tokens, contact information or model prompts.


class IntegrationOutcome(BaseModel):
    """Only non-authoritative outcomes may be constructed by local adapters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service: Service
    action: Action
    property_slug: str
    state: str = Field(pattern=r"^(not_connected|simulated)$")
    source: str = Field(pattern=r"^(none|synthetic_fixture)$")
    confirmed: bool = False
    delivered: bool = False
    paid: bool = False
    live_room_inventory: bool = False
    detail: str

    @model_validator(mode="after")
    def reject_false_authority(self):
        if (
            self.confirmed or self.delivered or self.paid
            or self.live_room_inventory
        ):
            raise ValueError(
                "Local provider outcomes cannot certify booking/payment/"
                "messaging/inventory; verified provider proof is required"
            )
        if self.service != ACTION_SERVICE[self.action]:
            raise ValueError("Mismatched integration service/action")
        if (self.state, self.source) not in (
            ("not_connected", "none"), ("simulated", "synthetic_fixture")
        ):
            raise ValueError("Invalid local outcome provenance")
        return self


@dataclass(frozen=True, slots=True)
class IntegrationCapability:
    service: Service
    mode: str
    configured: bool
    authoritative: bool
    description: str

    def as_public_dict(self):
        return {
            "service": self.service.value,
            "mode": self.mode,
            "configured": self.configured,
            "authoritative": self.authoritative,
            "description": self.description,
        }


class ProviderAdapter(Protocol):
    """Future real adapters must satisfy this interface; no live impl here."""

    service: Service

    def capability(self) -> IntegrationCapability: ...

    def invoke(self, request: IntegrationRequest) -> IntegrationOutcome: ...


class DisabledAdapter:
    """Safe default; invoking it is always a hard error, never fake success."""

    def __init__(self, service: Service):
        self.service = service

    def capability(self):
        return IntegrationCapability(
            service=self.service,
            mode="disabled",
            configured=False,
            authoritative=False,
            description="No authorized provider connected; this is not live hotel data.",
        )

    def invoke(self, request: IntegrationRequest):
        if ACTION_SERVICE[request.action] is not self.service:
            raise ValueError("Service/action mismatch")
        raise IntegrationNotConnected(
            f"{self.service.value} not connected; do not claim a "
            "booking, payment, guest delivery or AI answer"
        )


class FixtureAdapter:
    """In-memory deterministic contract test only; impossible to return success.

    It cannot call network providers or produce live inventory. The instance is
    scoped to ONE hotel and its request idempotency keys, to prevent fixtures
    accidentally bleeding between tenants in tests.
    """

    def __init__(self, service: Service, property_slug: str):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,79}", property_slug):
            raise ValueError("Invalid synthetic property")
        self.service = service
        self.property_slug = property_slug
        self._seen: dict[str, tuple[str, IntegrationOutcome]] = {}

    def capability(self):
        return IntegrationCapability(
            service=self.service,
            mode="fixture",
            configured=False,
            authoritative=False,
            description="Synthetic integration contract fixture, never a provider connection.",
        )

    def invoke(self, request: IntegrationRequest):
        if ACTION_SERVICE[request.action] is not self.service:
            raise ValueError("Service/action mismatch")
        if request.property_slug != self.property_slug:
            raise PermissionError("Cross-property fixture access denied")

        fingerprint = sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
        previous = self._seen.get(request.idempotency_key)
        if previous:
            if previous[0] != fingerprint:
                raise IntegrationConflict("Idempotency key reused for different synthetic request")
            return previous[1]

        result = IntegrationOutcome(
            service=self.service,
            action=request.action,
            property_slug=self.property_slug,
            state="simulated",
            source="synthetic_fixture",
            detail="Contract exercised with synthetic values; no provider outcome verified.",
        )
        self._seen[request.idempotency_key] = (fingerprint, result)
        return result


class IntegrationRegistry:
    """Explicit default-deny adapter registry; never loads credentials from env."""

    def __init__(self):
        self.adapters = {
            service: DisabledAdapter(service)
            for service in Service
        }

    def capability_summary(self):
        return {
            "source": "disabled_development_adapters",
            "production_connected": False,
            "live_bookings": False,
            "live_payments": False,
            "live_messages": False,
            "live_ai": False,
            "services": [
                self.adapters[service].capability().as_public_dict()
                for service in Service
            ],
        }

    def attempt(self, request: IntegrationRequest):
        adapter = self.adapters[ACTION_SERVICE[request.action]]
        return adapter.invoke(request)


DEFAULT_INTEGRATIONS = IntegrationRegistry()
