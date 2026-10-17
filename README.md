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
git diff --check
```

## Security Considerations

- Keep `.env`, passwords, and other secrets out of version control.
- Use a dedicated MySQL account with least-privilege permissions.
- Avoid exposing the development API publicly without appropriate authentication and access controls.
- Query analysis and input validation do not replace database permissions or a properly secured environment.
- Treat database metadata and monitoring output as potentially sensitive.
- Keep backup files in a restricted directory and use disposable test data for preflight checks.
- Do not interpret backup preflight success as proof of a successful restore.

## Current Limitations

- Query-plan analysis supports a deliberately restricted SQL subset.
- Slow-query analysis uses heuristics rather than a complete SQL optimizer or live workload profiler.
- Schema audits require an initialized baseline.
- Historical metric snapshots are manually triggered.
- Backup verification is preflight-only; sandbox restore verification is not implemented.
- Monitoring visibility depends on the MySQL permissions and metrics available to the configured account.

## Future Improvements

- Implement a safely isolated sandbox restore-verification workflow.
- Add optional scheduled metric collection.
- Improve query diagnostics with richer execution-plan interpretation.
- Add authentication, role-based access control, and audit logging.
- Expand integration tests against disposable MySQL instances.
- Add deployment guidance and operational monitoring.

## Learning Outcomes

This project demonstrates practical work with:

- REST API development using FastAPI.
- MySQL metadata and server monitoring.
- SQL query analysis and execution-plan inspection.
- Database schema comparison.
- SQLAlchemy connection pool diagnostics.
- Threshold-based alerting and historical metric storage.
- Automated testing and Git-based development workflows.

## License

No license has been specified yet. If you intend to make DB-Pulse open source, add an appropriate `LICENSE` file and update this section.

---

**DB-Pulse — Making MySQL monitoring and database operations easier to inspect through a single API.**
