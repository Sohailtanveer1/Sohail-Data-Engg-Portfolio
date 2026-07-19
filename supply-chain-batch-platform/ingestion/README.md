# ingestion/

Land-to-Bronze extractors — one connector per source protocol (SFTP, REST API,
JDBC, GCS). Metadata-driven (reads `config/`), with file tracking, checksums,
idempotent landing, and archive strategy. **Populated in Phase 5.**
