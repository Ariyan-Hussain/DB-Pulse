# DB-Pulse — MySQL Monitoring & Database Operations Toolkit

**DB-Pulse** is a Python-based database monitoring and operations toolkit built with FastAPI and MySQL. It provides database monitoring metrics, transaction and lock visibility, query performance analysis, schema drift detection, connection pool monitoring, threshold-based alerts, and backup verification preflight checks through a REST API.

The project is designed to make common database administration and diagnostic tasks easier to inspect and demonstrate through a single API interface.

## Key Features

### 1. Database Monitoring
- Retrieves MySQL server metrics and global status counters.
- Reports connection information, server uptime, and connection utilization.
- Exposes monitoring information through REST API endpoints.

### 2. Transaction and Lock Monitoring
- Provides visibility into available MySQL transaction and lock information.
- Helps investigate potential blocking and database contention.
- Supports database troubleshooting and diagnostics.

### 3. Slow Query Analysis
- Analyzes submitted query text using heuristic checks.
- Identifies potential performance concerns and query-pattern issues.
- Does not execute submitted SQL as part of the heuristic analysis.

### 4. Query Execution Plan Analysis
- Provides a dedicated endpoint for MySQL `EXPLAIN` estimates.
- Accepts a conservative subset of single `SELECT` statements.
- Rejects unsupported query patterns and multiple statements.
- Does not use `EXPLAIN ANALYZE`.

**Note:** `EXPLAIN` provides an estimated execution plan; it does not guarantee actual query performance.

### 5. Schema Drift Detection
- Captures versioned database schema metadata baselines.
- Compares the current schema against a saved baseline.
- Reports detected structural differences.
- Requires explicit confirmation before replacing an existing baseline with a new version.

The schema-drift baseline table must be initialized before using the audit endpoint.

### 6. Connection Pool Monitoring
- Reports supported SQLAlchemy connection pool statistics.
- Tracks checked-out connections and related pool information where supported.
- Evaluates configured thresholds to help identify possible connection pressure.

### 7. Backup Verification Preflight
- Checks backup-file prerequisites within a configured backup directory.
- Validates file size and basic SQL text format.
- Checks whether the MySQL client is available.

**Current limitation:** This feature performs preflight checks only. It does not restore a backup or verify that a restored database is functional.

### 8. Alerts and Historical Metrics
- Evaluates configured thresholds for supported monitoring metrics.
- Exposes database alerts through the API.
- Stores metric snapshots for historical inspection.
- Supports manually triggered snapshots; automatic scheduled collection is not currently implemented.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| FastAPI | REST API framework |
| MySQL 8 | Database server and metadata source |
| SQLAlchemy | Database connectivity and connection pooling |
| PyMySQL | MySQL driver |
| python-dotenv | Local environment configuration |
| Pytest | Automated testing |
| HTTPX | API testing support |

## Project Structure

```text
DB-Pulse/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── metrics.py
│   ├── models.py
│   ├── schemas.py
│   ├── alerting.py
│   ├── query_explain.py
│   ├── schema_drift.py
│   ├── pool_monitor.py
│   ├── backup_verification.py
│   └── routes/
│       ├── alerts.py
│       ├── history.py
│       ├── locks.py
│       ├── monitoring.py
│       ├── partitions.py
│       ├── slow_queries.py
│       ├── query_explain.py
│       ├── schema_drift.py
│       ├── pool_monitor.py
│       └── backup_verification.py
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
├── DEMO_GUIDE.md
└── README.md
```

## Getting Started

### Prerequisites

Install the following before running DB-Pulse:

- Python 3.11 or another Python version supported by the installed dependencies.
- MySQL 8.x.
- Git.
- A MySQL account with the permissions required by the endpoints you intend to use.

### 1. Clone the repository

```bash
git clone https://github.com/Ariyan-Hussain/DB-Pulse.git
cd DB-Pulse
```

To try the latest advanced features before they are merged into `main`:

```bash
git switch feature/advanced-db-ops
```

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use the environment's Python executable directly instead.

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file based on `.env.example` and fill in the appropriate local values.

Example configuration format:

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=db_pulse_meta
```

Use your actual local configuration values. Never commit `.env` or publish database credentials.

Some optional features may require additional environment variables. Refer to the corresponding sections below and `DEMO_GUIDE.md`.

### 5. Create the metadata database

Create the database configured by `DB_NAME` in your local MySQL instance if it does not already exist.

For example:

```sql
CREATE DATABASE IF NOT EXISTS db_pulse_meta;
```

Use an appropriately permissioned database account. Some monitoring endpoints may need read access to MySQL performance or metadata views, while historical snapshots require write access to the DB-Pulse metadata tables.

### 6. Run the application

```powershell
python -m uvicorn app.main:app --reload
```

The API will normally be available at:

- **API root:** http://127.0.0.1:8000/
- **Health check:** http://127.0.0.1:8000/health
- **Interactive API documentation:** http://127.0.0.1:8000/docs

Use the Swagger UI to inspect endpoints and submit test requests.

## API Endpoints

The following endpoints are exposed by the application.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Application information |
| `GET` | `/health` | Health check |
| `GET` | `/monitoring` | Database monitoring metrics |
| `GET` | `/locks` | Lock and transaction information |
| `GET` | `/partitions` | Partition metadata |
| `GET` | `/alerts` | Current threshold-based alerts |
| `GET` | `/history/snapshots` | Historical metric snapshots |
| `POST` | `/history/snapshots` | Store a metric snapshot |
| `POST` | `/slow-queries/analyze` | Analyze query text heuristically |
| `POST` | `/queries/explain` | Retrieve MySQL `EXPLAIN` estimates |
| `POST` | `/schema-drift/baseline` | Save a versioned schema baseline |
| `GET` | `/schema-drift/audit` | Compare current schema with the baseline |
| `GET` | `/pool/status` | Inspect connection pool statistics |
| `POST` | `/backups/verify` | Run backup verification preflight checks |

Exact response fields and request schemas are available in `/docs`.

## Feature Setup Notes

### Schema Drift

Before running a schema audit, initialize the baseline storage table using the SQL documented in this repository's setup instructions.

Then:

1. Call `POST /schema-drift/baseline` to capture the initial schema baseline.
2. Call `GET /schema-drift/audit` to compare the current schema with the saved baseline.
3. Review the reported structural differences.

Creating a baseline changes DB-Pulse metadata. Follow the endpoint's confirmation requirements before recording a replacement baseline.

### Backup Preflight

Configure `DB_PULSE_BACKUP_DIR` locally to point to a dedicated directory containing disposable test backups. Use a small UTF-8 `.sql` fixture to test the endpoint.

A successful preflight does not prove that a backup can be restored. Do not use production backups or production databases for experiments.

### Connection Pool Monitoring

Use `GET /pool/status` to inspect the application's SQLAlchemy connection pool. Interpret pool metrics in the context of current application activity; a high checked-out count alone does not prove that connections are leaking.

## Running Tests

Activate the virtual environment and run:

```powershell
python -m pytest -q
```

The advanced-feature development run completed with **60 passing tests**. Test results may change as the project evolves.

Check the working tree for whitespace issues with:

```powershell
Set-Location 'C:\path\to\DB-Pulse'
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Use your local MySQL host, port, username, and password in `.env`; set `DB_NAME=db_pulse_meta`. Do not share `.env` or commit it. `.env.example` contains placeholders only. If `.venv` already exists, skip the `py -m venv .venv` line. The requirements include the runtime packages and pytest for project tests.

Initialize the history table only if it is not already present. The SQL shown earlier in this README is scoped to `db_pulse_meta.db_pulse_metric_snapshots` and uses `CREATE TABLE IF NOT EXISTS`; it does not drop or alter anything. Use an account that has permission to read monitoring metadata and `SELECT`/`INSERT` on this table for the corresponding history operations.

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. Stop the server with Ctrl+C. To run the full automated suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### Endpoint guide and example calls

| Endpoint | Database needed? | What to try in Swagger |
| --- | --- | --- |
| `GET /` | No | Basic project welcome response. |
| `GET /health` | No | Confirms the API process responds; it is not a MySQL health check. |
| `GET /monitoring` | Yes | Reads connection counts, uptime, and available cumulative query counters. |
| `GET /locks` | Yes | Reads currently visible transactions and lock waits; results depend on permissions and activity. |
| `POST /slow-queries/analyze` | No | Submit JSON such as `{"query":"SELECT * FROM users"}`; this is text analysis and does not execute SQL. |
| `GET /partitions` | Yes | Reads partition metadata in the selected schema; empty output can be normal. |
| `POST /history/snapshots` | Yes, with insert permission | Explicitly collects metrics and writes one DB-Pulse history row. Returns HTTP 201 on success. |
| `GET /history/snapshots?limit=5` | Yes, with select permission | Lists recent snapshots; `limit` must be 1–100 and defaults to 20. Empty history returns an empty list. |
| `GET /alerts` | Yes | Evaluates configured rules against current metrics and, when possible, the latest snapshot. It does not save history. |

A successful `GET /health` response has `status` and `project` fields. Monitoring, lock, and partition response values are specific to the connected server and schema, so use the live Swagger response rather than memorized sample values. The alert response example above illustrates the documented field meanings; its numbers are illustrative only. Error responses use HTTP validation errors for invalid inputs, HTTP 409 if history is pointed at a different schema, and safe generic HTTP 503 messages for database connectivity or permission failures.

### Feature limitations

- Health is limited to metrics exposed by the current MySQL account and queries. Missing values remain unavailable.
- Several status counters and connection figures are server-wide. Query counters accumulate since server start; a per-minute comparison is only an average across comparable saved snapshots.
- Lock inspection is a point-in-time view and depends on MySQL visibility permissions. It is not a complete historical deadlock report.
- Partition inspection reports metadata, not partition performance. Table statistics may be approximate or stale.
- Slow-query analysis is a simple text heuristic, not an execution plan or SQL parser. It never submits the supplied statement to MySQL.
- History has explicit saves, no scheduler, retention policy, or cleanup endpoint. The only history writes target the DB-Pulse table.
- Alerts are investigation signals, not proof of failure or an automatic repair system.

### Common troubleshooting

- **Cannot connect / HTTP 503:** verify the `MySQL80` service is running, check `DB_HOST`, `DB_PORT`, `DB_NAME`, and `DB_USER` in the local `.env`, and confirm the user/password locally. Do not paste the password into a terminal transcript or issue report.
- **Access denied / missing lock details:** the MySQL account may need additional read or metadata visibility grants. Grant only the minimum access required, through your normal local MySQL administration process; DB-Pulse does not change grants.
- **History table missing:** run the documented `CREATE TABLE IF NOT EXISTS` statement against `db_pulse_meta`. Check `DB_NAME=db_pulse_meta` and the table's `SELECT`/`INSERT` permissions.
- **HTTP 422:** Swagger input or a query parameter failed validation; read the response's field-level explanation and use an allowed value.
- **HTTP 409 on history/alerts:** these operations intentionally require the selected database to be `db_pulse_meta`.
- **Port conflict:** start with `--port 8001` and open `http://127.0.0.1:8001/docs`.
- **PowerShell blocks activation:** skip activation and use the explicit `.\.venv\Scripts\python.exe -m ...` commands above.

### Interview talking points

- **Why FastAPI?** It provides typed request handling, input validation, generated OpenAPI documentation, and a simple way to organize API routes.
- **How is monitoring safe?** Monitoring paths use read-only queries. The one history write is explicit and limited to DB-Pulse's own table.
- **How are alerts evaluated?** The alert route reuses the shared collector, validates thresholds, and compares cumulative query counters only when history provides a usable interval.
- **How are database failures tested?** Automated tests mock database calls to exercise API success and failure paths without depending on a live MySQL server; live permissions still need a separate local check.
- **What would you add next?** A configurable retention policy and an optional scheduler could be considered after the current manual snapshot flow is well tested and clearly documented.

For a timed walkthrough, see [`DEMO_GUIDE.md`](DEMO_GUIDE.md).
