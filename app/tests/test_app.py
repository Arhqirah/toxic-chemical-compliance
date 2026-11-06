"""Integration tests: the real Flask app against the real MariaDB.

They log in as the seeded test users and click through the app with
Flask's test client, using the limited tc_app database account.

They expect the FRESH test data from db/ and change it as they go
(raise jobs, confirm them), so they run in order and are skipped
unless RUN_DB_TESTS=1. CI starts a new database for every run.
Locally:
    docker compose down -v
    docker compose up -d --build
    docker compose exec -e RUN_DB_TESTS=1 app python -m pytest
"""
import os
import re

import pytest

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(os.environ.get("RUN_DB_TESTS") != "1", reason="needs MariaDB; set RUN_DB_TESTS=1"),
]

PASSWORD = "Password123!"


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def query(sql, args=()):
    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def login(client, username, password=PASSWORD):
    client.get("/logout")
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


def raise_job(client, **fields):
    data = {"type": "IN", "ticket_ref": "T-TEST", "site_id": "1", "warehouse": "1",
            "chemical_class": "C", "units": "1"}
    data.update({k: str(v) for k, v in fields.items()})
    return client.post("/jobs/new", data=data, follow_redirects=True)


def flashes(html):
    return re.findall(r'class="flash (\w+)">(.*?)</div>', html)


def table_rows(html):
    return len(re.findall(r"<tr>\s*<td>", html))


# ---------------------------------------------------------------- login and security

def test_pages_need_login(client):
    client.get("/logout")
    assert client.get("/").status_code == 302


def test_wrong_password_is_rejected(client):
    r = login(client, "anna.gate", "wrong")
    assert "Wrong username or password" in r.text


def test_sql_injection_in_username_is_rejected(client):
    r = login(client, "' OR 1=1 -- ", "x")
    assert "Wrong username or password" in r.text


def test_correct_login(client):
    r = login(client, "anna.gate")
    assert "anna.gate (gate)" in r.text


# ---------------------------------------------------------------- raising jobs (logged in as gate)

def test_class_a_next_to_class_a_is_blocked(client):
    # Hamburg (site 2) has class A in warehouses 1, 3 and 5
    r = raise_job(client, site_id=2, warehouse=2, chemical_class="A")
    assert any("Neighbouring warehouse" in m for _, m in flashes(r.text))


def test_class_b_with_class_a_is_blocked(client):
    # Køge (site 1) warehouse 1 holds class A
    r = raise_job(client, site_id=1, warehouse=1, chemical_class="B")
    assert any("may not be stored together" in m for _, m in flashes(r.text))


def test_over_capacity_is_blocked(client):
    # Køge warehouse 4: capacity 3, holds 2
    r = raise_job(client, site_id=1, warehouse=4, chemical_class="B", units=2)
    assert any("only has" in m for _, m in flashes(r.text))


def test_valid_delivery_is_accepted(client):
    # Køge warehouse 5: capacity 9, holds 5 + an open delivery of 3 -> 1 more fits
    r = raise_job(client, site_id=1, warehouse=5, chemical_class="C", units=1, ticket_ref="T-IN-OK")
    assert any(kind == "ok" for kind, _ in flashes(r.text))


def test_open_jobs_reserve_space(client):
    # Same warehouse is now full, counting the open job from the test above
    r = raise_job(client, site_id=1, warehouse=5, chemical_class="C", units=1)
    assert any("only has 0" in m for _, m in flashes(r.text))


def test_dispatch_more_than_available_is_blocked(client):
    # Rotterdam (site 3) warehouse 3: 4K class B, 1K already promised to an open dispatch
    r = raise_job(client, type="OUT", site_id=3, warehouse=3, chemical_class="B", units=4)
    assert any("Only 3" in m for _, m in flashes(r.text))


def test_valid_dispatch_is_accepted(client):
    r = raise_job(client, type="OUT", site_id=3, warehouse=3, chemical_class="B", units=2, ticket_ref="T-OUT-OK")
    assert any(kind == "ok" for kind, _ in flashes(r.text))


def test_bad_input_returns_400(client):
    assert raise_job(client, units="abc").status_code == 400


def test_raising_a_job_writes_the_audit_log(client):
    job_id = query("SELECT id FROM job WHERE ticket_ref = 'T-IN-OK'")[0]["id"]
    assert query("SELECT id FROM audit_log WHERE job_id = %s", (job_id,))


def test_gate_cannot_confirm_jobs(client):
    job_id = query("SELECT id FROM job WHERE ticket_ref = 'T-OUT-OK'")[0]["id"]
    r = client.post(f"/jobs/{job_id}/confirm", follow_redirects=True)
    assert "have access to that page" in r.text


# ---------------------------------------------------------------- confirming jobs (logged in as warehouse)

def test_warehouse_cannot_raise_jobs(client):
    login(client, "hans.warehouse")
    r = client.get("/jobs/new", follow_redirects=True)
    assert "have access to that page" in r.text


def test_confirming_delivery_adds_stock(client):
    job_id = query("SELECT id FROM job WHERE ticket_ref = 'T-IN-OK'")[0]["id"]
    before = query("SELECT COUNT(*) AS n FROM stock")[0]["n"]
    client.post(f"/jobs/{job_id}/confirm")
    assert query("SELECT COUNT(*) AS n FROM stock")[0]["n"] == before + 1


def test_job_cannot_be_confirmed_twice(client):
    job_id = query("SELECT id FROM job WHERE ticket_ref = 'T-IN-OK'")[0]["id"]
    r = client.post(f"/jobs/{job_id}/confirm", follow_redirects=True)
    assert "is already confirmed" in r.text


def test_confirming_dispatch_removes_exactly_the_ordered_amount(client):
    job = query("SELECT id, warehouse_id FROM job WHERE ticket_ref = 'T-OUT-OK'")[0]
    sql = "SELECT SUM(units_k) AS s FROM stock WHERE warehouse_id = %s AND chemical_class = 'B'"
    before = query(sql, (job["warehouse_id"],))[0]["s"]
    client.post(f"/jobs/{job['id']}/confirm")
    after = query(sql, (job["warehouse_id"],))[0]["s"]
    assert before - after == 2
    assert query("SELECT status FROM job WHERE id = %s", (job["id"],))[0]["status"] == "confirmed"


def test_fire_brigade_warning_when_confirming_at_hamburg(client):
    login(client, "anna.gate")
    raise_job(client, site_id=2, warehouse=2, chemical_class="C", units=1, ticket_ref="T-HAMBURG")
    job_id = query("SELECT id FROM job WHERE ticket_ref = 'T-HAMBURG'")[0]["id"]
    login(client, "hans.warehouse")
    r = client.post(f"/jobs/{job_id}/confirm", follow_redirects=True)
    assert "fire brigade must be informed" in r.text


# ---------------------------------------------------------------- overview, inventory, audit log

def test_overview_shows_fire_banner_for_hamburg_only(client):
    r = client.get("/")
    assert "Hamburg Depot holds 16.00K" in r.text
    assert r.text.count("Fire brigade must be informed") == 1


def test_inventory_filter_by_class(client):
    r = client.get("/inventory?chemical_class=A")
    assert table_rows(r.text) > 0
    assert "<td>B</td>" not in r.text and "<td>C</td>" not in r.text


def test_inventory_filter_by_site_and_class(client):
    r = client.get("/inventory?site_id=2&chemical_class=A")
    assert "16.00K units in total" in r.text


def test_inventory_filter_by_date(client):
    r = client.get("/inventory?from=2026-09-10&to=2026-09-20")
    dates = re.findall(r"<td>(2026-\d\d-\d\d) \d\d:\d\d</td>", r.text)
    assert dates
    assert all("2026-09-10" <= d <= "2026-09-20" for d in dates)


def test_inventory_ignores_bad_date(client):
    r = client.get("/inventory?from=31-10-2026")
    assert "Ignored the" in r.text


def test_inventory_ignores_sql_injection_in_filters(client):
    everything = table_rows(client.get("/inventory").text)
    assert table_rows(client.get("/inventory?site_id=1%20OR%201=1").text) == everything
    assert table_rows(client.get("/inventory?chemical_class=A%27%20OR%20%271%27=%271").text) == everything


def test_only_compliance_sees_audit_log(client):
    r = client.get("/audit", follow_redirects=True)
    assert "have access to that page" in r.text
    login(client, "peter.compliance")
    r = client.get("/audit")
    assert table_rows(r.text) >= 63
