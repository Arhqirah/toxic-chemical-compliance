"""Toxic Chemical Industrie A/S - compliance app.

Flow from the brief:
  1. A lorry arrives. Gate staff raise a job from the driver's ticket
     (IN = delivery, OUT = dispatch). The storage rules are checked here.
  2. Warehouse staff move the barrels and confirm the job.
     Only then does the stock change.
Every step is written to the audit log.
"""
import os
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

import rules
from db import get_connection

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only")
# Session cookie can't be read by JavaScript (HttpOnly is Flask's default)
# and isn't sent along with forms posted from other sites (SameSite=Lax),
# which blocks most cross-site request forgery.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ---------------------------------------------------------------- login

def login_required(*roles):
    """Decorator: the user must be logged in, and have one of `roles` if given."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if roles and session["role"] not in roles:
                flash("Your role doesn't have access to that page.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # %s placeholder: the driver sends the username separately from
                # the SQL, so input like  ' OR 1=1 --  is just a weird username.
                cur.execute(
                    "SELECT id, username, password_hash, role FROM users WHERE username = %s",
                    (request.form["username"],),
                )
                user = cur.fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()  # start a fresh session (prevents session fixation)
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("index"))
        # Same message whether the username or the password was wrong,
        # so the page doesn't reveal which usernames exist.
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- overview

@app.route("/")
@login_required()
def index():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.name AS site, s.country, w.number, w.capacity_k,
                       COALESCE(SUM(st.units_k), 0) AS used_k,
                       GROUP_CONCAT(DISTINCT st.chemical_class) AS classes
                FROM warehouse w
                JOIN site s ON s.id = w.site_id
                LEFT JOIN stock st ON st.warehouse_id = w.id
                GROUP BY w.id, s.name, s.country, w.number, w.capacity_k
                ORDER BY s.name, w.number
                """
            )
            warehouses = cur.fetchall()
    finally:
        conn.close()
    return render_template("index.html", warehouses=warehouses)


# ---------------------------------------------------------------- jobs

def load_site_state(cur, site_id):
    """Everything the rules need to know about one site, as dicts.

    Locks the site's warehouse rows (FOR UPDATE) until the transaction ends,
    so two people raising jobs for the same site at the same moment are
    handled one after the other instead of both using the last free space.
    """
    cur.execute(
        "SELECT id, number, capacity_k FROM warehouse WHERE site_id = %s ORDER BY number FOR UPDATE",
        (site_id,),
    )
    warehouses = {
        row["number"]: {"id": row["id"], "capacity": row["capacity_k"], "used": Decimal("0"), "classes": set()}
        for row in cur.fetchall()
    }
    available = {}  # (warehouse number, class) -> units that can still be dispatched

    # What's on the shelves now
    cur.execute(
        """SELECT w.number, st.chemical_class, SUM(st.units_k) AS units
           FROM stock st JOIN warehouse w ON w.id = st.warehouse_id
           WHERE w.site_id = %s GROUP BY w.number, st.chemical_class""",
        (site_id,),
    )
    for row in cur.fetchall():
        w = warehouses[row["number"]]
        w["used"] += row["units"]
        w["classes"].add(row["chemical_class"])
        available[(row["number"], row["chemical_class"])] = row["units"]

    # Open jobs: deliveries already promised space, dispatches already promised stock
    cur.execute(
        """SELECT w.number, j.type, j.chemical_class, SUM(j.units_k) AS units
           FROM job j JOIN warehouse w ON w.id = j.warehouse_id
           WHERE j.site_id = %s AND j.status = 'open'
           GROUP BY w.number, j.type, j.chemical_class""",
        (site_id,),
    )
    for row in cur.fetchall():
        key = (row["number"], row["chemical_class"])
        if row["type"] == "IN":
            warehouses[row["number"]]["used"] += row["units"]
            warehouses[row["number"]]["classes"].add(row["chemical_class"])
        else:
            available[key] = available.get(key, Decimal("0")) - row["units"]

    return warehouses, available


def class_a_on_site(cur, site_id):
    cur.execute(
        """SELECT COALESCE(SUM(st.units_k), 0) AS units
           FROM stock st JOIN warehouse w ON w.id = st.warehouse_id
           WHERE w.site_id = %s AND st.chemical_class = 'A'""",
        (site_id,),
    )
    return cur.fetchone()["units"]


def audit(cur, job_id, action):
    cur.execute(
        "INSERT INTO audit_log (job_id, user_id, action) VALUES (%s, %s, %s)",
        (job_id, session["user_id"], action),
    )


@app.route("/jobs")
@login_required()
def jobs():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT j.id, j.type, j.chemical_class, j.units_k, j.ticket_ref, j.status,
                          j.created_at, s.name AS site, w.number AS warehouse
                   FROM job j
                   JOIN site s ON s.id = j.site_id
                   JOIN warehouse w ON w.id = j.warehouse_id
                   ORDER BY j.status = 'open' DESC, j.created_at DESC
                   LIMIT 50"""
            )
            job_list = cur.fetchall()
    finally:
        conn.close()
    return render_template("jobs.html", jobs=job_list)


@app.route("/jobs/new", methods=["GET", "POST"])
@login_required("gate")
def new_job():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM site ORDER BY name")
            sites = cur.fetchall()
    finally:
        conn.close()

    if request.method == "GET":
        return render_template("job_new.html", sites=sites, form={})

    form = request.form
    errors = []
    # Validate the input before it goes anywhere near the database
    try:
        site_id = int(form["site_id"])
        number = int(form["warehouse"])
        units = Decimal(form["units"])
    except (KeyError, ValueError, InvalidOperation):
        errors.append("Site, warehouse and units must be filled in with numbers.")
    job_type = form.get("type")
    chemical_class = form.get("chemical_class")
    ticket = form.get("ticket_ref", "").strip()
    if job_type not in ("IN", "OUT"):
        errors.append("Choose delivery or dispatch.")
    if chemical_class not in ("A", "B", "C"):
        errors.append("Choose chemical class A, B or C.")
    if not ticket:
        errors.append("Enter the ticket number.")
    if not errors and not (1 <= number <= 5 and units > 0):
        errors.append("Warehouse must be 1-5 and units must be more than 0.")
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("job_new.html", sites=sites, form=form), 400

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ---- transaction starts: everything below is saved together or not at all
            warehouses, available = load_site_state(cur, site_id)
            if not warehouses:
                errors = ["Unknown site."]
            elif job_type == "IN":
                errors = rules.check_delivery(warehouses, number, chemical_class, units)
            else:
                errors = rules.check_dispatch(available.get((number, chemical_class), Decimal("0")), units)

            if errors:
                conn.rollback()
                for e in errors:
                    flash(e, "error")
                return render_template("job_new.html", sites=sites, form=form), 400

            cur.execute(
                """INSERT INTO job (site_id, warehouse_id, type, chemical_class, units_k, ticket_ref)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (site_id, warehouses[number]["id"], job_type, chemical_class, units, ticket),
            )
            job_id = cur.lastrowid
            direction = "to" if job_type == "IN" else "from"
            audit(cur, job_id, f"Job raised at gate: {job_type} {units}K class {chemical_class} {direction} warehouse {number}")
        conn.commit()
        # ---- transaction ends
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    flash(f"Job {job_id} raised. Send the lorry to warehouse {number}.", "ok")
    return redirect(url_for("jobs"))


@app.route("/jobs/<int:job_id>/confirm", methods=["POST"])
@login_required("warehouse")
def confirm_job(job_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ---- transaction starts. FOR UPDATE locks the job, so it can't be confirmed twice.
            cur.execute("SELECT * FROM job WHERE id = %s AND status = 'open' FOR UPDATE", (job_id,))
            job = cur.fetchone()
            if not job:
                conn.rollback()
                flash("That job doesn't exist or is already confirmed.", "error")
                return redirect(url_for("jobs"))

            if job["type"] == "IN":
                cur.execute(
                    "INSERT INTO stock (warehouse_id, chemical_class, units_k, delivered_at) VALUES (%s, %s, %s, NOW())",
                    (job["warehouse_id"], job["chemical_class"], job["units_k"]),
                )
                action = "Shipment checked against ticket and stored - job confirmed"
            else:
                # Take the barrels from the oldest deliveries first
                cur.execute(
                    """SELECT id, units_k FROM stock
                       WHERE warehouse_id = %s AND chemical_class = %s
                       ORDER BY delivered_at FOR UPDATE""",
                    (job["warehouse_id"], job["chemical_class"]),
                )
                remaining = job["units_k"]
                for row in cur.fetchall():
                    if remaining <= 0:
                        break
                    take = min(row["units_k"], remaining)
                    if take == row["units_k"]:
                        cur.execute("DELETE FROM stock WHERE id = %s", (row["id"],))
                    else:
                        cur.execute("UPDATE stock SET units_k = units_k - %s WHERE id = %s", (take, row["id"]))
                    remaining -= take
                if remaining > 0:
                    # Should never happen (checked when the job was raised), but if it does,
                    # rollback undoes everything above.
                    conn.rollback()
                    flash("Not enough stock to confirm this dispatch.", "error")
                    return redirect(url_for("jobs"))
                action = "Stock checked, lorry loaded - job confirmed"

            cur.execute("UPDATE job SET status = 'confirmed' WHERE id = %s", (job_id,))
            audit(cur, job_id, action)
            alert = rules.fire_brigade_alert(class_a_on_site(cur, job["site_id"]))
        conn.commit()
        # ---- transaction ends
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    flash(f"Job {job_id} confirmed.", "ok")
    if alert:
        flash("More than 15K units of class A on this site: the fire brigade must be informed.", "error")
    return redirect(url_for("jobs"))
