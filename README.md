# Toxic Chemical Compliance

Prototype of a compliance app for Toxic Chemical Industrie A/S: safe storage of class A, B and C chemicals across EU depots. Exam project for **Development Environments** and **Databases 2** at EK.

## Stack

- **App:** Python + Flask, pages rendered with Jinja templates
- **Database:** MariaDB
- **Dev environment:** Docker Compose (2 containers: `app` and `db`)

## Run it locally

1. Install Docker Desktop.
2. Copy the example settings and change the passwords:
   ```bash
   cp .env.example .env
   ```
3. Start everything:
   ```bash
   docker compose up --build
   ```
4. Open http://localhost:5000. You should see 4 sites with 5 warehouses each.

### Reset the database

The files in `db/` only run the first time the database starts. To run them again (for example after changing the schema), delete the volume:

```bash
docker compose down -v
docker compose up --build
```

## Project structure

```
app/                 Flask app (Dockerfile, code, templates)
db/01_schema.sql     Tables and indexes
db/02_seed.sql       Test data
db/03_app_user.sh    Creates the app's limited database account
docker-compose.yml   Development environment
.env.example         Settings template (copy to .env)
```

## Database accounts

| Account | Rights | Used by |
|---|---|---|
| root | Everything | Nobody, day to day |
| `tc_admin` | All rights on `toxic_chemical` | Developers / maintenance |
| `tc_app` | Only what the app needs; `audit_log` is INSERT + SELECT only | The Flask app |

## Branching

GitHub Flow: `main` is always working. New work goes on a feature branch and is merged to `main` with a pull request.
