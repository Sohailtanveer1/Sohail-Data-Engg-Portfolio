"""Metadata-driven ingestion: land the five sources to Bronze.

Flow per entity (ADR-0005, ADR-0007):
    discover source files/rows -> checksum + file dedup -> read (format-specific)
    -> write Bronze Parquet (+ audit columns) -> archive -> write file/batch audit
    -> advance watermark (incremental).

Everything is config-driven (`config/sources/*.yaml`) so onboarding a new entity
is a config change, not new code.
"""
