"""Toxic Chemical Industrie A/S - compliance app.

Phase 1: just proves that the app container can talk to the database
by listing every site and its warehouses.
"""
import os

from flask import Flask, render_template

from db import get_connection

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only")


@app.route("/")
def index():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Placeholders (%s) are how we avoid SQL injection later on.
            # This query has no user input, so it needs none yet.
            cur.execute(
                """
                SELECT s.name AS site, s.country, w.number, w.capacity_k
                FROM warehouse w
                JOIN site s ON s.id = w.site_id
                ORDER BY s.name, w.number
                """
            )
            warehouses = cur.fetchall()
    finally:
        conn.close()
    return render_template("index.html", warehouses=warehouses)
