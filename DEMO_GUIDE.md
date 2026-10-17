# DB-Pulse Demonstration Guide

This guide walks through a 5–10 minute demonstration of DB-Pulse using the existing API. It does not assume fixed database values or that locks, partitions, or alerts will be present. Show the responses produced by your own MySQL instance.

## Before the demonstration

- Start MySQL 8 and confirm the project `.env` is configured locally with `DB_NAME=db_pulse_meta`. Keep the password private.
- Initialize the DB-Pulse history table by following the safe `CREATE TABLE IF NOT EXISTS` instructions in `README.md` if it does not exist yet.
- Open PowerShell in the project folder.

## 1. Start the API (about 1 minute)

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Leave this terminal open. Open **http://127.0.0.1:8000/docs** in a browser. Swagger is an interactive page for trying the API routes.

If environment activation is blocked, use `python -m uvicorn ...` only if the project virtual environment is active another way, or run the interpreter directly in a second terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## 2. Check app health and database monitoring (1–2 minutes)

In Swagger, expand `GET /health`, choose **Try it out**, and execute it. Explain that this checks whether the FastAPI process responds; it does not prove MySQL is reachable.

Then execute `GET /monitoring`. It reads current metrics and reports the values available to the configured MySQL account. Point out which fields are present or unavailable in the actual response. Some server status counters describe the whole MySQL server, not only `db_pulse_meta`.

## 3. Inspect locks and partitions (1–2 minutes)

Execute `GET /locks`. Describe any visible transactions or waiting/blocking details in the response. An empty result is a valid observation when no visible waits exist. MySQL permissions and server activity affect what can be seen.

Execute `GET /partitions`. This inspects metadata for the selected schema. An empty list does not mean the API failed: a schema with no partitioned tables can return no partition rows. Avoid creating or altering tables during the demo just to produce output.

## 4. Save and retrieve historical metrics (1 minute)

Execute `POST /history/snapshots` once. This explicit action writes one row to the DB-Pulse-owned `db_pulse_metric_snapshots` table in `db_pulse_meta`. Explain that ordinary `GET /monitoring` and `GET /alerts` requests do not save history.

Execute `GET /history/snapshots` to view the saved row. The `limit` query parameter is optional, defaults to 20, and accepts values from 1 to 100. For example, try `limit=5`.

## 5. Evaluate health alerts (about 1 minute)

Execute `GET /alerts`. Explain the alert code, severity, observed metric, threshold, explanation, and suggested action using the actual result. No alert means none of the configured rules fired at that time; it is not a guarantee that all MySQL components are healthy.

A query-counter interval alert requires two comparable saved snapshots separated by time. If demonstrating that comparison, call the snapshot POST endpoint again later. The calculated value is an interval-average increase for the server-wide cumulative counter, not an instantaneous query rate. Do not change server settings or generate artificial load for the demo.

## 6. Explain the design, safety, and tests (1–2 minutes)

Use the README's Mermaid diagram to describe request flow: FastAPI routes use the shared database engine and metric collector; history is written only when explicitly requested; alerts reuse metrics and may read the latest saved snapshot.

Mention the main safety choices: monitoring is read-only, snapshots write only to the DB-Pulse history table, there is no automatic scheduler, and the API does not kill queries, change MySQL settings, or alter partitions. The slow-query endpoint analyzes supplied text heuristically; it does not run that SQL.

In a second PowerShell terminal, run the automated tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

These tests mock database access where applicable and are separate from checking live MySQL permissions. Report the test result from the run you actually performed.

## Troubleshooting during the demo

- **HTTP 503 from database routes:** check that MySQL is running, `.env` is configured locally, and the account has the needed read permissions. Keep credentials out of screenshots and chat.
- **History endpoints return an initialization/permission error:** check that the documented DB-Pulse history table exists in `db_pulse_meta` and that the account can select and insert as needed.
- **No lock rows, partition rows, or alerts:** explain that these describe the current server/schema and rules; empty output can be expected.
- **Port 8000 is occupied:** stop the other local app or start DB-Pulse using `--port 8001`, then use `http://127.0.0.1:8001/docs`.

## Optional advanced-module demo (2–3 minutes)

If time permits, try `GET /pool/status` to show the current application's SQLAlchemy pool; this reads in-process pool counters and does not open another database connection. The EXPLAIN demo accepts only a conservative SELECT subset and returns estimates, not query execution results. If you initialized the schema-baseline table, call `POST /schema-drift/baseline` once, then `GET /schema-drift/audit`; a second baseline requires `{"confirm_replace":true}` and creates a new version.

The backup route is **preflight only**. Configure `DB_PULSE_BACKUP_DIR` to a folder containing a disposable UTF-8 `.sql` fixture, then POST only its filename to `/backups/verify`. The endpoint does not restore or execute the dump. Do not use a valuable or untrusted dump as a demo fixture.
