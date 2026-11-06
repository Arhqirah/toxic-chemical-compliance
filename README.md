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
db/02_seed.sql       Sites and warehouses
db/03_app_user.sh    Creates the app's limited database account
db/04_seed_data.sql  Test data: users, stock, jobs, audit log
docker-compose.yml   Development environment
.env.example         Settings template (copy to .env)
```

## Using the app

| Role | Example login | Can do |
|---|---|---|
| gate | `anna.gate` | Raise a job from a driver's ticket (delivery or dispatch) |
| warehouse | `hans.warehouse` | Confirm a job once the barrels are moved |
| compliance | `peter.compliance` | View everything, including the audit log |

Everyone logged in can see the overview and the **inventory** (filter by site, class and delivery date; test data is from September 2026). The overview shows a red banner for every site with more than 15K of class A.

The storage rules are checked when a job is raised (`app/rules.py`):
- the warehouse must have room (open deliveries count as already used),
- class A and B never in the same warehouse,
- class A never in neighbouring warehouses (assumption: warehouses stand in a row 1-2-3-4-5),
- a dispatch can't take more than is in stock (minus open dispatches).

Raising and confirming a job each run in **one database transaction**: the job, the stock change and the audit entry are saved together or not at all. The warehouse rows are locked with `SELECT ... FOR UPDATE`, so two lorries can't be given the same free space.

When a job is confirmed and the site holds more than 15K of class A, the app warns that the fire brigade must be informed.

## Database accounts

| Account | Rights | Used by |
|---|---|---|
| root | Everything | Nobody, day to day |
| `tc_admin` | All rights on `toxic_chemical` | Developers / maintenance |
| `tc_app` | Only what the app needs; `audit_log` is INSERT + SELECT only | The Flask app |

### Prove the app account can't change history

Run this with the stack up. It tries to delete from the audit log as `tc_app` (use the `DB_APP_PASSWORD` from your `.env`):

```bash
docker compose exec db mariadb -utc_app -pchange-me-app toxic_chemical -e "DELETE FROM audit_log WHERE id=1"
```

Expected result:

```
ERROR 1142 (42000): DELETE command denied to user 'tc_app'@'localhost' for table `toxic_chemical`.`audit_log`
```

## Test data

| Table | Rows |
|---|---|
| site | 4 |
| warehouse | 20 |
| users | 20 (7 gate, 8 warehouse, 5 compliance) |
| stock | 25 |
| job | 33 (25 deliveries + 5 dispatches confirmed, 3 still open) |
| audit_log | 63 |

All stock follows the storage rules (capacity, A and B never together, A never in neighbouring warehouses). **Hamburg Depot has 16K units of class A on purpose**, so the fire brigade warning has something to show.

All test users log in with the dev-only password `Password123!`, for example `anna.gate`, `hans.warehouse` or `peter.compliance`. The database only stores scrypt hashes.

## Tests and linting

| What | File | Needs the database? |
|---|---|---|
| Unit tests of the storage rules | `app/tests/test_rules.py` | No |
| Integration tests: login, jobs, inventory, audit log, security | `app/tests/test_app.py` | Yes, a **fresh** one |
| Linting (style, bugs, security) with ruff | `app/pyproject.toml` | No |

Run them inside the app container (pytest and ruff are only installed in the dev image):

```bash
# Lint + unit tests
docker compose exec app ruff check .
docker compose exec app python -m pytest

# Integration tests - they change the data, so start from a fresh database
docker compose down -v
docker compose up -d --build
docker compose exec -e RUN_DB_TESTS=1 app python -m pytest -v
```

### CI

`.github/workflows/ci.yml` runs on every pull request and every push to `main`:
1. **lint-and-unit-tests**: `ruff check` and the unit tests on plain Python
2. **integration-tests**: starts the whole system with the same `docker-compose.yml` and runs the integration tests against a fresh MariaDB

Only merge a pull request when both are green.

## Branching

GitHub Flow: `main` is always working. New work goes on a feature branch and is merged to `main` with a pull request.
