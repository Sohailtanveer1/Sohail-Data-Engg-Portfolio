"""Pluggable metadata-store backends.

The in-memory and JSONL stores live in ``scb_common.metadata``; the BigQuery
store lives here because it carries an optional heavy dependency
(``google-cloud-bigquery``, the ``bigquery`` extra).
"""
