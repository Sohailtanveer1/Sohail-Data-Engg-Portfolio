# spark/

PySpark for the medallion transforms. `jobs/` = entry points (Bronze/Silver/Gold
per entity), `transforms/` = reusable pure logic (SCD, DQ, schema), `tests/` =
Spark unit tests. Runs on local Spark (dev) and Dataproc Serverless (scale).
**Populated in Phase 6–7.**
