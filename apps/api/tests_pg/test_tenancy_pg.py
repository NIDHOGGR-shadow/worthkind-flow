"""Real PostgreSQL tests for M1-A tenancy/RLS.

Run only against a disposable postgres database with a role-creating
administrator. This test module is intentionally separate from the SQLite
FastAPI suite and never targets a real hotel database.
"""
from contextlib import contextmanager
import json
import base64
import sys
import time
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pathlib import Path
from uuid import uuid4
import os

import psycopg
from psycopg import errors
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest


MIGRATIONS = [
    Path(__file__).resolve().parents[3] / "db" / "migrations" / name
    for name in ("001_tenant_staff_foundation.sql", "002_atomic_case_commands.sql", "003_verified_staff_lookup.sql", "004_encrypted_guest_case.sql", "005_suspended_organization_read_boundary.sql")
]


@pytest.fixture(scope="session")
def pg():
    dsn = os.environ.get("WF_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Requires an isolated PostgreSQL service and WF_TEST_POSTGRES_DSN")
    params = conninfo_to_dict(dsn)
    assert params.get("host") in ("localhost", "127.0.0.1") and params.get("dbname") == "worthkind_ci", (
        "Tenancy tests only run against the disposable local worthkind_ci database"
    )
    with psycopg.connect(dsn, autocommit=True) as conn:
        for migration in MIGRATIONS:
            conn.execute(migration.read_text())
        # Test-only NOINHERIT login roles; never provision real credentials here.
        conn.execute(
            "CREATE ROLE wf_ci_guest LOGIN NOINHERIT PASSWORD 'worthkind_ci_guest_only'"
        )
        conn.execute("GRANT wf_guest_api TO wf_ci_guest")
        conn.execute(
            "CREATE ROLE wf_ci_staff LOGIN NOINHERIT PASSWORD 'worthkind_ci_staff_only'"
        )
        conn.execute(
            "GRANT wf_auth_lookup,wf_staff_runtime,wf_staff_commands TO wf_ci_staff"
        )
        yield conn


@pytest.fixture
def seeded(pg):
    # Test runs are serial in one disposable GitHub Actions postgres instance.
    pg.execute(
        "TRUNCATE worthkind_flow.event_outbox, worthkind_flow.case_audit_events, "
        "worthkind_flow.guest_cases, worthkind_flow.staff_memberships, "
        "worthkind_flow.staff_identities, worthkind_flow.properties, "
        "worthkind_flow.organizations CASCADE"
    )
    organization_a, organization_b = uuid4(), uuid4()
    property_a, property_b = uuid4(), uuid4()
    owner, receptionist, housekeeper, outsider, invited, suspended = [uuid4() for _ in range(6)]
    members = {
        "owner": uuid4(),
        "receptionist": uuid4(),
        "housekeeper": uuid4(),
        "outsider": uuid4(),
        "invited": uuid4(),
        "suspended": uuid4(),
    }
    case_a, case_b = uuid4(), uuid4()
    for oid, name in ((organization_a, "A Organization"), (organization_b, "B Organization")):
        pg.execute(
            "INSERT INTO worthkind_flow.organizations(id, legal_name, status) "
            "VALUES (%s,%s,'verified')", (oid, name)
        )
    for pid, oid, slug in (
        (property_a, organization_a, "hotel-a"),
        (property_b, organization_b, "hotel-b")
    ):
        pg.execute(
            "INSERT INTO worthkind_flow.properties(id, organization_id, slug, display_name, status) "
            "VALUES (%s,%s,%s,%s,'active')", (pid, oid, slug, slug.upper())
        )
    for uid, subject, state in (
        (owner, "idp:hotel-a-owner", "active"),
        (receptionist, "idp:hotel-a-reception", "active"),
        (housekeeper, "idp:hotel-a-housekeeper", "active"),
        (outsider, "idp:hotel-b-reception", "active"),
        (invited, "idp:hotel-a-invited", "active"),
        (suspended, "idp:hotel-a-suspended", "suspended"),
    ):
        pg.execute(
            "INSERT INTO worthkind_flow.staff_identities(id,provider_subject,state) "
            "VALUES (%s,%s,%s)", (uid, subject, state)
        )
    for member, pid, oid, uid, role, status in (
        (members["owner"], property_a, organization_a, owner, "owner", "active"),
        (members["receptionist"], property_a, organization_a, receptionist, "reception", "active"),
        (members["housekeeper"], property_a, organization_a, housekeeper, "housekeeping", "active"),
        (members["outsider"], property_b, organization_b, outsider, "reception", "active"),
        (members["invited"], property_a, organization_a, invited, "reception", "invited"),
        (members["suspended"], property_a, organization_a, suspended, "reception", "active"),
    ):
        pg.execute(
            "INSERT INTO worthkind_flow.staff_memberships"
            "(id, organization_id, property_id, identity_id, role, state, activated_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,CASE WHEN %s = 'active' THEN now() ELSE NULL END)",
            (member, oid, pid, uid, role, status, status)
        )
    for cid, pid, key in (
        (case_a, property_a, "request-key-for-hotel-a"),
        (case_b, property_b, "request-key-for-hotel-b"),
    ):
        pg.execute(
            "INSERT INTO worthkind_flow.guest_cases "
            "(id,property_id,request_key,payload_hash,receipt_hash,kind) "
            "VALUES (%s,%s,%s,%s,%s,'booking')",
            (cid, pid, key, "a" * 64, "b" * 64)
        )
    return {
        "org_a": organization_a, "org_b": organization_b,
        "property_a": property_a, "property_b": property_b,
        "case_a": case_a, "case_b": case_b,
        "owner": owner, "receptionist": receptionist,
        "housekeeper": housekeeper, "outsider": outsider,
        "invited": invited, "suspended": suspended,
        "members": members,
    }


@contextmanager
def actor_session(pg, actor=None):
    """Mimic a trusted API which verified the identity BEFORE setting it."""
    with pg.transaction():
        pg.execute("SET LOCAL ROLE wf_staff_runtime")
        if actor is not None:
            pg.execute(
                "SELECT set_config('wf.actor_id', %s, true)",
                (str(actor),)
            )
        yield pg


def rows(pg, table):
    return pg.execute(f"SELECT * FROM worthkind_flow.{table}").fetchall()


def test_active_owner_and_reception_can_only_read_own_property_cases(pg, seeded):
    with actor_session(pg, seeded["owner"]):
        assert len(rows(pg, "organizations")) == 1
        assert len(rows(pg, "properties")) == 1
        cases = rows(pg, "guest_cases")
        assert len(cases) == 1 and cases[0][0] == seeded["case_a"]
        assert len(rows(pg, "staff_memberships")) == 1  # self only
        assert len(rows(pg, "staff_identities")) == 1
    with actor_session(pg, seeded["receptionist"]):
        assert len(rows(pg, "guest_cases")) == 1
        assert rows(pg, "guest_cases")[0][0] == seeded["case_a"]
    with actor_session(pg, seeded["outsider"]):
        assert len(rows(pg, "guest_cases")) == 1
        assert rows(pg, "guest_cases")[0][0] == seeded["case_b"]


def test_no_actor_invited_suspended_and_non_reception_are_denied(pg, seeded):
    with actor_session(pg):
        for table in ("organizations", "properties", "staff_memberships", "guest_cases"):
            assert rows(pg, table) == []
    for user in ("invited", "suspended"):
        with actor_session(pg, seeded[user]):
            assert rows(pg, "guest_cases") == []
            assert rows(pg, "properties") == []
    with actor_session(pg, seeded["housekeeper"]):
        assert len(rows(pg, "properties")) == 1
        assert rows(pg, "guest_cases") == []  # least-privilege dept scope


def test_revocation_and_property_pause_take_effect_on_next_transaction(pg, seeded):
    with actor_session(pg, seeded["receptionist"]):
        assert len(rows(pg, "guest_cases")) == 1
    pg.execute(
        "UPDATE worthkind_flow.staff_memberships SET state='revoked',revoked_at=now() "
        "WHERE id=%s", (seeded["members"]["receptionist"],)
    )
    with actor_session(pg, seeded["receptionist"]):
        assert rows(pg, "guest_cases") == []
        assert rows(pg, "properties") == []
    with actor_session(pg, seeded["owner"]):
        assert len(rows(pg, "guest_cases")) == 1
    pg.execute(
        "UPDATE worthkind_flow.properties SET status='suspended' WHERE id=%s",
        (seeded["property_a"],)
    )
    with actor_session(pg, seeded["owner"]):
        assert rows(pg, "guest_cases") == []


def test_staff_role_cannot_mutate_or_inspect_outbox_and_audit(pg, seeded):
    with pytest.raises(errors.InsufficientPrivilege):
        with actor_session(pg, seeded["owner"]):
            rows(pg, "case_audit_events")
    with pytest.raises(errors.InsufficientPrivilege):
        with actor_session(pg, seeded["owner"]):
            pg.execute(
                "UPDATE worthkind_flow.guest_cases SET state='claimed' WHERE id=%s",
                (seeded["case_a"],)
            )
    with pytest.raises(errors.InsufficientPrivilege):
        with actor_session(pg, seeded["owner"]):
            pg.execute(
                "DELETE FROM worthkind_flow.staff_memberships WHERE id=%s",
                (seeded["members"]["owner"],)
            )
    with actor_session(pg, seeded["owner"]):
        assert rows(pg, "guest_cases")[0][0] == seeded["case_a"]


def test_cross_tenant_member_link_and_assignment_rejected(pg, seeded):
    with pytest.raises(errors.ForeignKeyViolation):
        with pg.transaction():
            pg.execute(
                "INSERT INTO worthkind_flow.staff_memberships "
                "(organization_id,property_id,identity_id,role,state,activated_at) "
                "VALUES (%s,%s,%s,'manager','active',now())",
                (seeded["org_b"], seeded["property_a"], seeded["outsider"])
            )
    with pytest.raises(errors.ForeignKeyViolation):
        with pg.transaction():
            pg.execute(
                "UPDATE worthkind_flow.guest_cases SET assigned_membership_id=%s "
                "WHERE id=%s", (seeded["members"]["outsider"], seeded["case_a"])
            )


def test_property_scoped_request_key_uniqueness_and_no_seed_fixture(pg, seeded):
    with pytest.raises(errors.UniqueViolation):
        with pg.transaction():
            pg.execute(
                "INSERT INTO worthkind_flow.guest_cases "
                "(property_id,request_key,payload_hash,receipt_hash,kind) "
                "VALUES (%s,%s,%s,%s,'booking')",
                (seeded["property_a"], "request-key-for-hotel-a", "a"*64, "b"*64)
            )
    # Same client key in the other property is allowed (key scoped by property).
    pg.execute(
        "INSERT INTO worthkind_flow.guest_cases "
        "(property_id,request_key,payload_hash,receipt_hash,kind) "
        "VALUES (%s,%s,%s,%s,'booking')",
        (seeded["property_b"], "request-key-for-hotel-a", "a"*64, "b"*64)
    )
    assert pg.execute(
        "SELECT COUNT(*) FROM worthkind_flow.guest_cases"
    ).fetchone()[0] == 3


def test_identity_membership_date_and_role_validation(pg, seeded):
    with pytest.raises(errors.CheckViolation):
        with pg.transaction():
            pg.execute(
                "INSERT INTO worthkind_flow.staff_memberships "
                "(organization_id,property_id,identity_id,role,state) "
                "VALUES (%s,%s,%s,'superadmin','invited')",
                (seeded["org_a"], seeded["property_a"], seeded["owner"])
            )
    with pytest.raises(errors.CheckViolation):
        with pg.transaction():
            pg.execute(
                "UPDATE worthkind_flow.staff_memberships "
                "SET state='active', activated_at=NULL WHERE id=%s",
                (seeded["members"]["owner"],)
            )


@contextmanager
def command_session(pg, role, actor=None):
    assert role in {"wf_guest_api", "wf_staff_commands"}
    with pg.transaction():
        pg.execute(f"SET LOCAL ROLE {role}")
        if actor is not None:
            pg.execute("SELECT set_config('wf.actor_id', %s, true)", (str(actor),))
        yield pg


def create_guest(pg, key, slug="hotel-a", payload="a" * 64, proof="b" * 64):
    return pg.execute(
        "SELECT * FROM worthkind_flow.create_guest_case(%s,%s,%s,%s,'booking')",
        (slug, key, payload, proof),
    ).fetchone()


def count_events(pg, case_id):
    return (
        pg.execute(
            "SELECT COUNT(*) FROM worthkind_flow.case_audit_events WHERE case_id=%s",
            (case_id,),
        ).fetchone()[0],
        pg.execute(
            "SELECT COUNT(*) FROM worthkind_flow.event_outbox WHERE case_id=%s",
            (case_id,),
        ).fetchone()[0],
    )


def test_guest_case_command_commits_case_audit_outbox_once(pg, seeded):
    with command_session(pg, "wf_guest_api"):
        first = create_guest(pg, "new-case-key-11111111")
    assert first[1:] == ("queued", False)
    assert count_events(pg, first[0]) == (1, 1)
    with command_session(pg, "wf_guest_api"):
        again = create_guest(pg, "new-case-key-11111111")
    assert again[0] == first[0]
    assert again[1:] == ("queued", True)
    assert count_events(pg, first[0]) == (1, 1)
    with pytest.raises(errors.UniqueViolation):
        with command_session(pg, "wf_guest_api"):
            create_guest(pg, "new-case-key-11111111", proof="f" * 64)
    assert count_events(pg, first[0]) == (1, 1)


def test_guest_command_rejects_unknown_inactive_and_invalid(pg, seeded):
    for slug in ("nonexistent-hotel", "hotel-bad"):
        with pytest.raises(errors.NoDataFound):
            with command_session(pg, "wf_guest_api"):
                create_guest(pg, "different-valid-key-123", slug)
    with pytest.raises(errors.InvalidParameterValue):
        with command_session(pg, "wf_guest_api"):
            create_guest(pg, "x")
    pg.execute(
        "UPDATE worthkind_flow.organizations SET status='suspended' WHERE id=%s",
        (seeded["org_a"],)
    )
    with pytest.raises(errors.NoDataFound):
        with command_session(pg, "wf_guest_api"):
            create_guest(pg, "inactive-property-key-123")


def test_claim_and_reply_are_atomic_and_explicitly_pending_delivery(pg, seeded):
    with command_session(pg, "wf_guest_api"):
        new_case = create_guest(pg, "claim-and-reply-key-123")[0]
    with command_session(pg, "wf_staff_commands", seeded["receptionist"]):
        claim = pg.execute(
            "SELECT * FROM worthkind_flow.claim_guest_case(%s,%s)",
            (seeded["property_a"], new_case)
        ).fetchone()
    assert claim == (new_case, "claimed")
    with command_session(pg, "wf_staff_commands", seeded["receptionist"]):
        reply = pg.execute(
            "SELECT * FROM worthkind_flow.record_case_reply(%s,%s,%s,%s)",
            (seeded["property_a"], new_case, bytes(range(32)), "c" * 64)
        ).fetchone()
    assert reply == (new_case, "responded")
    assert count_events(pg, new_case) == (3, 3)
    states = pg.execute(
        "SELECT action FROM worthkind_flow.case_audit_events "
        "WHERE case_id=%s ORDER BY created_at, id", (new_case,)
    ).fetchall()
    assert {s[0] for s in states} == {"case_created", "case_claimed", "case_responded"}
    outbox_states = pg.execute(
        "SELECT DISTINCT event_state FROM worthkind_flow.event_outbox WHERE case_id=%s",
        (new_case,)
    ).fetchall()
    assert outbox_states == [("pending",)]  # No real messages sent


def test_commands_reject_cross_hotel_and_unauthorized_staff(pg, seeded):
    for actor in ("outsider", "housekeeper", "invited", "suspended"):
        with pytest.raises(errors.InsufficientPrivilege):
            with command_session(pg, "wf_staff_commands", seeded[actor]):
                pg.execute(
                    "SELECT * FROM worthkind_flow.claim_guest_case(%s,%s)",
                    (seeded["property_a"], seeded["case_a"])
                )
    with command_session(pg, "wf_staff_commands", seeded["owner"]):
        assert pg.execute(
            "SELECT * FROM worthkind_flow.claim_guest_case(%s,%s)",
            (seeded["property_a"], seeded["case_a"])
        ).fetchone()[1] == "claimed"
    with pytest.raises(errors.NoDataFound):
        with command_session(pg, "wf_staff_commands", seeded["owner"]):
            pg.execute(
                "SELECT * FROM worthkind_flow.claim_guest_case(%s,%s)",
                (seeded["property_a"], seeded["case_a"])
            )
    assert count_events(pg, seeded["case_a"]) == (1, 1)


def test_reply_must_be_by_claiming_member_with_valid_encrypted_metadata(pg, seeded):
    with command_session(pg, "wf_staff_commands", seeded["receptionist"]):
        pg.execute(
            "SELECT * FROM worthkind_flow.claim_guest_case(%s,%s)",
            (seeded["property_a"], seeded["case_a"])
        )
    with pytest.raises(errors.NoDataFound):
        with command_session(pg, "wf_staff_commands", seeded["owner"]):
            pg.execute(
                "SELECT * FROM worthkind_flow.record_case_reply(%s,%s,%s,%s)",
                (seeded["property_a"], seeded["case_a"], bytes(range(32)), "c" * 64)
            )
    with pytest.raises(errors.InvalidParameterValue):
        with command_session(pg, "wf_staff_commands", seeded["receptionist"]):
            pg.execute(
                "SELECT * FROM worthkind_flow.record_case_reply(%s,%s,%s,%s)",
                (seeded["property_a"], seeded["case_a"], b"plain", "c" * 64)
            )
    pg.execute(
        "UPDATE worthkind_flow.staff_memberships SET state='revoked',revoked_at=now() "
        "WHERE id=%s", (seeded["members"]["receptionist"],)
    )
    with pytest.raises(errors.InsufficientPrivilege):
        with command_session(pg, "wf_staff_commands", seeded["receptionist"]):
            pg.execute(
                "SELECT * FROM worthkind_flow.record_case_reply(%s,%s,%s,%s)",
                (seeded["property_a"], seeded["case_a"], bytes(range(32)), "c" * 64)
            )
    assert count_events(pg, seeded["case_a"]) == (1, 1)


def test_command_roles_cannot_bypass_to_base_tables_or_other_commands(pg, seeded):
    with pytest.raises(errors.InsufficientPrivilege):
        with command_session(pg, "wf_guest_api"):
            pg.execute(
                "SELECT * FROM worthkind_flow.claim_guest_case(%s,%s)",
                (seeded["property_a"], seeded["case_a"])
            )
    with pytest.raises(errors.InsufficientPrivilege):
        with command_session(pg, "wf_staff_commands", seeded["owner"]):
            create_guest(pg, "staff-cannot-create-case")
    with pytest.raises(errors.InsufficientPrivilege):
        with command_session(pg, "wf_guest_api"):
            pg.execute("SELECT COUNT(*) FROM worthkind_flow.guest_cases")


def test_audit_or_outbox_insert_failure_rolls_back_entire_guest_command(pg, seeded):
    before = pg.execute(
        "SELECT COUNT(*) FROM worthkind_flow.guest_cases"
    ).fetchone()[0]
    with pytest.raises(errors.CheckViolation):
        with pg.transaction():
            # Local test-only constraint is rolled back with the command error.
            pg.execute(
                "ALTER TABLE worthkind_flow.event_outbox "
                "ADD CONSTRAINT wf_ci_force_failure CHECK (false) NOT VALID"
            )
            pg.execute("SET LOCAL ROLE wf_guest_api")
            create_guest(pg, "rollback-case-120122300")
    assert pg.execute(
        "SELECT COUNT(*) FROM worthkind_flow.guest_cases"
    ).fetchone()[0] == before
    assert pg.execute(
        "SELECT COUNT(*) FROM worthkind_flow.case_audit_events "
        "WHERE action='case_created'"
    ).fetchone()[0] == 0


def test_parallel_claim_permits_one_reception_owner(pg, seeded):
    from concurrent.futures import ThreadPoolExecutor
    dsn = os.environ["WF_TEST_POSTGRES_DSN"]
    def claim(actor):
        try:
            with psycopg.connect(dsn, autocommit=True) as connection:
                with command_session(connection, "wf_staff_commands", actor):
                    return connection.execute(
                        "SELECT * FROM worthkind_flow.claim_guest_case(%s,%s)",
                        (seeded["property_a"], seeded["case_a"]),
                    ).fetchone()[1]
        except errors.NoDataFound:
            return "already_claimed"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, (seeded["owner"], seeded["receptionist"])))
    assert sorted(outcomes) == ["already_claimed", "claimed"]
    assert count_events(pg, seeded["case_a"]) == (1, 1)


@pytest.fixture
def oidc_rig(pg, seeded, monkeypatch, tmp_path):
    # Signed local test identities. No real IdP or personal identity records used.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "ci-rsa-key-01", "alg": "RS256", "use": "sig"})
    monkeypatch.setenv("WF_OIDC_JWKS_JSON", json.dumps({"keys": [jwk]}))
    monkeypatch.setenv("WF_OIDC_ISSUER", "https://issuer.unit-test.invalid")
    monkeypatch.setenv("WF_OIDC_AUDIENCE", "worthkind-flow-test")
    guest_dsn = make_conninfo(
        os.environ["WF_TEST_POSTGRES_DSN"],
        user="wf_ci_guest", password="worthkind_ci_guest_only",
    )
    staff_dsn = make_conninfo(
        os.environ["WF_TEST_POSTGRES_DSN"],
        user="wf_ci_staff", password="worthkind_ci_staff_only",
    )
    monkeypatch.setenv("WF_GUEST_POSTGRES_DSN", guest_dsn)
    monkeypatch.setenv("WF_STAFF_POSTGRES_DSN", staff_dsn)
    monkeypatch.setenv("WF_DATA_KEY_B64", base64.b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("WF_ENABLE_PG_GUEST_API", "1")
    monkeypatch.setenv("WF_DATABASE_PATH", str(tmp_path / "api.sqlite3"))
    with TestClient(main.app) as client:
        yield client, private_key, seeded


def signed_token(key, subject, *, issuer="https://issuer.unit-test.invalid",
                 audience="worthkind-flow-test", expires=3600, kid="ci-rsa-key-01"):
    now = int(time.time())
    payload = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": now - 5,
        "exp": now + expires,
    }
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


def auth_header(token):
    return {"Authorization": "Bearer " + token}


def test_oidc_staff_case_api_reads_only_verified_property_metadata(pg, oidc_rig):
    client, key, source = oidc_rig
    token = signed_token(key, "idp:hotel-a-owner")
    response = client.get("/api/v1/properties/hotel-a/staff/cases", headers=auth_header(token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] == "postgres_case_metadata"
    assert payload["property"] == "hotel-a"
    assert payload["staff_role"] == "owner"
    assert len(payload["cases"]) == 1
    assert payload["cases"][0]["id"] == str(source["case_a"])
    assert "receipt_hash" not in str(payload)
    assert "staff_reply" not in str(payload)
    assert payload["live_notifications"] is False
    assert response.headers["cache-control"] == "no-store"

    foreign = client.get("/api/v1/properties/hotel-b/staff/cases", headers=auth_header(token))
    assert foreign.status_code == 403
    assert foreign.headers["cache-control"] == "no-store"
    assert "hotel-b" not in str(foreign.json())


def test_oidc_staff_claim_api_is_atomic_and_denies_repeat(pg, oidc_rig):
    client, key, source = oidc_rig
    url = f"/api/v1/properties/hotel-a/staff/cases/{source['case_a']}/claim"
    token = signed_token(key, "idp:hotel-a-reception")
    first = client.post(url, headers=auth_header(token))
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "claimed"
    assert first.json()["notification_delivery"] == "not_connected"
    assert count_events(pg, source["case_a"]) == (1, 1)
    second = client.post(url, headers=auth_header(token))
    assert second.status_code == 403
    assert count_events(pg, source["case_a"]) == (1, 1)


def test_oidc_untrusted_tokens_are_rejected_even_with_known_subject(pg, oidc_rig):
    client, key, source = oidc_rig
    base = "/api/v1/properties/hotel-a/staff/cases"
    good = signed_token(key, "idp:hotel-a-owner")
    invalid = [
        None,
        "Bearer definitely-not-a-jwt",
        jwt.encode(
            {"sub": "idp:hotel-a-owner", "iat": int(time.time()),
             "exp": int(time.time())+3600, "iss": "https://issuer.unit-test.invalid",
             "aud": "worthkind-flow-test"},
            "untrusted-shared-key-longer-than-32-bytes", algorithm="HS256",
            headers={"kid": "ci-rsa-key-01"}
        ),
        signed_token(key, "idp:hotel-a-owner", issuer="https://evil.invalid"),
        signed_token(key, "idp:hotel-a-owner", audience="other-service"),
        signed_token(key, "idp:hotel-a-owner", expires=-7200),
        signed_token(key, "idp:hotel-a-owner", kid="unknown-issuer-key"),
        good[:-2] + "xx",
    ]
    for candidate in invalid:
        reply = client.get(base, headers=auth_header(candidate) if candidate else {})
        assert reply.status_code == 401, (candidate, reply.status_code, reply.text)
        assert reply.headers["cache-control"] == "no-store"
    assert client.get(base, headers=auth_header(good)).status_code == 200


def test_oidc_role_invite_revocation_and_suspension_are_database_authoritative(
    pg, oidc_rig
):
    client, key, source = oidc_rig
    base = "/api/v1/properties/hotel-a/staff/cases"
    for subject in ("idp:hotel-a-housekeeper", "idp:hotel-a-invited",
                    "idp:hotel-a-suspended", "idp:hotel-b-reception"):
        reply = client.get(base, headers=auth_header(signed_token(key, subject)))
        assert reply.status_code == 403, (subject, reply.status_code)
    authorized = auth_header(signed_token(key, "idp:hotel-a-reception"))
    assert client.get(base, headers=authorized).status_code == 200
    pg.execute(
        "UPDATE worthkind_flow.staff_memberships SET state='revoked',revoked_at=now() "
        "WHERE id=%s", (source["members"]["receptionist"],)
    )
    assert client.get(base, headers=authorized).status_code == 403


def test_oidc_missing_server_config_fails_closed(pg, oidc_rig, monkeypatch):
    client, key, source = oidc_rig
    token = signed_token(key, "idp:hotel-a-owner")
    path = "/api/v1/properties/hotel-a/staff/cases"
    monkeypatch.delenv("WF_STAFF_POSTGRES_DSN")
    assert client.get(path, headers=auth_header(token)).status_code == 503
    monkeypatch.delenv("WF_OIDC_JWKS_JSON")
    assert client.get(path, headers=auth_header(token)).status_code == 503
    assert client.get(path).status_code == 401


def guest_payload():
    return {
        "request_key": "guest-flow-key-012345",
        "receipt_token": "P" * 43,
        "kind": "booking",
        "name": "Synthetic Guest Person",
        "contact": "guest@example.invalid",
        "details": "A room enquiry for next Friday, not a confirmed booking",
    }


def test_encrypted_guest_to_signed_reception_to_private_response(pg, oidc_rig):
    client, private_key, seed = oidc_rig
    body = guest_payload()
    submitted = client.post("/api/v1/properties/hotel-a/enquiries", json=body)
    assert submitted.status_code == 201, submitted.text
    case_id = submitted.json()["case_id"]
    assert submitted.json()["status"] == "queued"
    assert "no room, order, payment or staff reply is confirmed" in submitted.json()["message"].lower()
    assert submitted.headers["cache-control"] == "no-store"
    assert count_events(pg, case_id) == (1, 1)

    stored = pg.execute(
        "SELECT encrypted_guest_payload,receipt_hash "
        "FROM worthkind_flow.guest_cases WHERE id=%s", (case_id,)
    ).fetchone()
    assert stored and len(stored[0]) >= 29
    assert b"Synthetic Guest" not in bytes(stored[0])
    assert b"guest@example.invalid" not in bytes(stored[0])
    assert stored[1] != body["receipt_token"]

    status_path = f"/api/v1/properties/hotel-a/enquiries/{case_id}"
    assert client.get(status_path).status_code == 404
    assert client.get(status_path, headers={"X-Receipt-Token": "Q" * 43}).status_code == 404
    queued = client.get(status_path, headers={"X-Receipt-Token": body["receipt_token"]})
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"
    assert queued.json()["staff_reply"] is None
    assert queued.json()["booking_confirmed"] is False

    token = signed_token(private_key, "idp:hotel-a-reception")
    staff_base = "/api/v1/properties/hotel-a/staff/cases"
    queue = client.get(staff_base, headers=auth_header(token))
    assert queue.status_code == 200, queue.text
    match = [item for item in queue.json()["cases"] if item["id"] == case_id]
    assert len(match) == 1
    assert match[0]["customer_name"] == body["name"]
    assert match[0]["contact"] == body["contact"]
    assert match[0]["details"] == body["details"]

    claim = client.post(f"{staff_base}/{case_id}/claim", headers=auth_header(token))
    assert claim.status_code == 200, claim.text
    reply_text = "Reception will review the request. The room is not confirmed."
    reply = client.post(
        f"{staff_base}/{case_id}/respond",
        headers=auth_header(token),
        json={"message": reply_text},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["status"] == "responded"
    assert reply.json()["notification_delivery"] == "not_connected"
    assert client.post(
        f"{staff_base}/{case_id}/respond",
        headers=auth_header(token),
        json={"message": reply_text},
    ).status_code == 403
    assert count_events(pg, case_id) == (3, 3)

    response = client.get(status_path, headers={"X-Receipt-Token": body["receipt_token"]})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "responded"
    assert response.json()["staff_reply"] == reply_text
    assert response.json()["delivery_state"] == "not_connected"
    assert response.json()["booking_confirmed"] is False
    assert response.headers["cache-control"] == "no-store"


def test_guest_retry_conflict_tenant_and_encryption_tampering(pg, oidc_rig, monkeypatch):
    client, key, seed = oidc_rig
    base = "/api/v1/properties/hotel-a/enquiries"
    payload = guest_payload()
    first = client.post(base, json=payload)
    assert first.status_code == 201
    case_id = first.json()["case_id"]
    retry = client.post(base, json=payload)
    assert retry.status_code == 201
    assert retry.json()["duplicate"] is True
    assert retry.json()["case_id"] == case_id
    assert count_events(pg, case_id) == (1, 1)

    changed = dict(payload, details="Another changed request needs its own key")
    assert client.post(base, json=changed).status_code == 409
    other_hotel_status = client.get(
        f"/api/v1/properties/hotel-b/enquiries/{case_id}",
        headers={"X-Receipt-Token": payload["receipt_token"]},
    )
    assert other_hotel_status.status_code == 404

    # Changing encryption key prevents plaintext exposure, not silent corruption.
    monkeypatch.setenv("WF_DATA_KEY_B64", base64.b64encode(os.urandom(32)).decode())
    token = signed_token(key, "idp:hotel-a-owner")
    failed_staff_read = client.get(
        "/api/v1/properties/hotel-a/staff/cases", headers=auth_header(token)
    )
    assert failed_staff_read.status_code == 503
    assert payload["contact"] not in failed_staff_read.text


def test_guest_api_feature_and_key_configuration_fail_closed(pg, oidc_rig, monkeypatch):
    client, key, seed = oidc_rig
    payload = guest_payload()
    monkeypatch.delenv("WF_ENABLE_PG_GUEST_API")
    assert client.post("/api/v1/properties/hotel-a/enquiries", json=payload).status_code == 503
    monkeypatch.setenv("WF_ENABLE_PG_GUEST_API", "1")
    monkeypatch.delenv("WF_DATA_KEY_B64")
    assert client.post("/api/v1/properties/hotel-a/enquiries", json=payload).status_code == 503


def test_separate_database_logins_cannot_swap_guest_and_staff_capabilities(pg, seeded):
    guest_dsn = make_conninfo(
        os.environ["WF_TEST_POSTGRES_DSN"],
        user="wf_ci_guest", password="worthkind_ci_guest_only",
    )
    staff_dsn = make_conninfo(
        os.environ["WF_TEST_POSTGRES_DSN"],
        user="wf_ci_staff", password="worthkind_ci_staff_only",
    )
    with psycopg.connect(guest_dsn) as guest:
        with pytest.raises(errors.InsufficientPrivilege):
            with guest.transaction():
                guest.execute("SET LOCAL ROLE wf_staff_commands")
        with pytest.raises(errors.InsufficientPrivilege):
            with guest.transaction():
                guest.execute("SELECT * FROM worthkind_flow.guest_cases")
        with guest.transaction():
            guest.execute("SET LOCAL ROLE wf_guest_api")
            result = create_guest(guest, "guest-login-key-01111")
            assert result[1] == "queued"
    with psycopg.connect(staff_dsn) as staff:
        with pytest.raises(errors.InsufficientPrivilege):
            with staff.transaction():
                staff.execute("SET LOCAL ROLE wf_guest_api")
        with staff.transaction():
            staff.execute("SET LOCAL ROLE wf_auth_lookup")
            row = staff.execute(
                "SELECT * FROM worthkind_flow.resolve_staff_session(%s,%s,%s)",
                ("idp:hotel-a-owner", "hotel-a", "case:read"),
            ).fetchone()
            assert row[2] == seeded["property_a"]


def test_suspended_organization_blocks_direct_runtime_reads(pg, seeded):
    pg.execute("UPDATE worthkind_flow.organizations SET status='suspended' WHERE id=%s", (seeded["org_a"],))
    with actor_session(pg, seeded["owner"]):
        for table in ("organizations", "properties", "guest_cases"):
            assert rows(pg, table) == []
    with actor_session(pg, seeded["outsider"]):
        assert len(rows(pg, "guest_cases")) == 1
        assert rows(pg, "guest_cases")[0][0] == seeded["case_b"]
