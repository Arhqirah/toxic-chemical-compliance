"""Database connection helper.

All settings come from environment variables (set in docker-compose.yml),
so no passwords are written in the code.
"""
import os

import pymysql
import pymysql.cursors


def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        # Rows come back as dicts: row["number"] instead of row[1]
        cursorclass=pymysql.cursors.DictCursor,
        # We commit ourselves, so several queries can form ONE transaction
        autocommit=False,
    )
