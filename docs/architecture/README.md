# Architecture (C4 model)

Three levels of the [C4 model](https://c4model.com), from the big picture down to the code. The diagrams are Mermaid, so GitHub draws them from the `.mmd` files below; the PNG files are the same diagrams for the report.

## Level 1: System context

Who uses the system and what it connects to. Informing the fire brigade and handing records to an inspector happen outside the system: the system gives the warning and the data, people act on them.

```mermaid
%% C4 level 1: System context
flowchart TB
    gate["<b>Gate staff</b><br/><i>[Person]</i><br/>Register deliveries and dispatches from drivers' tickets"]
    wh["<b>Warehouse staff</b><br/><i>[Person]</i><br/>Check shipments, move barrels and confirm jobs"]
    comp["<b>Compliance team</b><br/><i>[Person]</i><br/>Watch the storage rules, read the inventory and audit log"]

    sys["<b>Toxic Chemical Compliance</b><br/><i>[Software system]</i><br/>Records every delivery, dispatch and stored barrel, enforces the storage rules and keeps an append-only audit log"]

    insp["<b>External inspector</b><br/><i>[Person, external]</i><br/>Checks that storage follows the regulations"]
    fire["<b>Local fire brigade</b><br/><i>[External organisation]</i><br/>Must be told when a site holds more than 15K units of class A"]

    gate -- "Raises jobs<br/>[HTTP]" --> sys
    wh -- "Confirms jobs<br/>[HTTP]" --> sys
    comp -- "Reads inventory, audit log<br/>and fire brigade warnings<br/>[HTTP]" --> sys
    comp -. "Hands over audit records" .-> insp
    comp -. "Informs when warned<br/>(manual, outside the system)" .-> fire

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef system fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#999999,stroke:#6b6b6b,color:#fff
    class gate,wh,comp person
    class sys system
    class insp,fire external
```

Image: [`c4-1-context.png`](c4-1-context.png) · source: [`c4-1-context.mmd`](c4-1-context.mmd)

## Level 2: Containers

What runs where in production. Two Docker containers on one Hetzner VPS; the database is only reachable inside the Docker network, and the app uses the limited `tc_app` account. The backup runs from cron on the server itself.

```mermaid
%% C4 level 2: Containers
flowchart TB
    staff["<b>Staff</b><br/><i>[Person]</i><br/>Gate, warehouse and compliance roles"]

    subgraph vps["Hetzner Cloud VPS (Ubuntu 24.04) · firewall: only 22 and 80 open"]
        subgraph compose["Docker Compose · network: backend"]
            app["<b>Web application</b><br/><i>[Container: Python 3.12, Flask, gunicorn]</i><br/>Login, roles, raising and confirming jobs, storage rules, inventory, audit log pages"]
            db[("<b>Database</b><br/><i>[Container: MariaDB 11.4]</i><br/>Sites, warehouses, stock, jobs, users, audit_log Volume: db_data")]
        end
        backup["<b>Nightly backup</b><br/><i>[cron + scripts/backup.sh]</i><br/>mariadb-dump at 02:30, keeps 7 days in ~/backups"]
    end

    staff -- "Uses<br/>[HTTP, port 80]" --> app
    app -- "Reads and writes as tc_app<br/>(audit_log: INSERT + SELECT only)<br/>[SQL over TCP 3306, inside the network]" --> db
    backup -- "Dumps the whole database<br/>[docker compose exec]" --> db

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef container fill:#438dd5,stroke:#2e6295,color:#fff
    classDef support fill:#85bbf0,stroke:#5d82a8,color:#000
    class staff person
    class app,db container
    class backup support
    style vps fill:#ffffff,stroke:#444,stroke-dasharray: 6 4
    style compose fill:#f4f8fc,stroke:#438dd5
```

Image: [`c4-2-container.png`](c4-2-container.png) · source: [`c4-2-container.mmd`](c4-2-container.mmd)

## Level 3: Components of the web application

How the Flask app is split up. The storage rules live in `rules.py` with no database code, so they can be unit tested on their own (`app/tests/test_rules.py`).

```mermaid
%% C4 level 3: Components of the web application
flowchart TB
    staff["<b>Staff</b><br/><i>[Person]</i>"]

    subgraph appb["Web application · Flask (pages rendered with Jinja templates, auto-escaped)"]
        auth["<b>Login and roles</b><br/><i>[app.py: login, logout, login_required]</i><br/>Checks scrypt hashes, keeps the session, refuses pages the role may not use"]
        jobs["<b>Jobs</b><br/><i>[app.py: new_job, confirm_job]</i><br/>Raises and confirms jobs, each in one transaction with SELECT … FOR UPDATE"]
        views["<b>Read pages</b><br/><i>[app.py: index, inventory, audit_log]</i><br/>Overview with fire warning, filtered inventory, audit log"]
        dbmod["<b>Database access</b><br/><i>[db.py: get_connection]</i><br/>PyMySQL, settings from environment, autocommit off"]
        rules["<b>Storage rules</b><br/><i>[rules.py]</i><br/>Capacity, A/B apart, no A next to A, dispatch stock, 15K fire limit"]
    end

    db[("<b>Database</b><br/><i>[MariaDB 11.4]</i>")]

    staff -- "[HTTP]" --> auth
    staff -- "[HTTP]" --> jobs
    staff -- "[HTTP]" --> views
    auth --> dbmod
    jobs --> dbmod
    jobs -- "checks every job" --> rules
    views -- "fire limit" --> rules
    views --> dbmod
    dbmod -- "[SQL, %s parameters]" --> db

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef component fill:#85bbf0,stroke:#5d82a8,color:#000
    classDef container fill:#438dd5,stroke:#2e6295,color:#fff
    class staff person
    class auth,jobs,views,rules,dbmod component
    class db container
    style appb fill:#ffffff,stroke:#438dd5,stroke-dasharray: 6 4
```

Image: [`c4-3-component.png`](c4-3-component.png) · source: [`c4-3-component.mmd`](c4-3-component.mmd)
