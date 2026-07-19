# local/

Local development stack via Docker Compose. **Implemented in Phase 2:**
PostgreSQL (WMS source), a mock Salesforce REST API (`mock_salesforce/`, Flask
with pagination + `?since=` incremental), and an SFTP server (SAP/Supplier drops).
Runs the whole data plane on your laptop at **$0 GCP cost**.

```
cp .env.example .env
docker compose up -d --build      # start
docker compose ps                 # status
docker compose down -v            # stop + wipe Postgres volume
```

Local **Airflow** and **Spark** join this stack in Phase 8 / Phase 6, when there
are DAGs/jobs to run. `postgres/init.sql` creates the WMS schema; seed it with
`scripts/seed_wms.py`.
