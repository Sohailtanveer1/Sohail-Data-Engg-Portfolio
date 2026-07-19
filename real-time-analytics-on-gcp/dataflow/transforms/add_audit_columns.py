"""Turns a validated ParsedRecord into a BigQuery row dict.

The event's own fields map 1:1 onto the Bronze table's business columns
(the JSON Schema's `additionalProperties: false` guarantees there's nothing
extra to strip), so this transform's only real job is appending the audit
columns every Bronze table shares — see the `local.audit_columns` block in
infra/terraform/modules/bigquery/main.tf for where those columns are
defined on the table side.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import apache_beam as beam


class AddAuditColumns(beam.DoFn):
    def __init__(self, pipeline_version: str):
        self.pipeline_version = pipeline_version

    def process(self, record):
        row = dict(record.event)
        row["raw_payload"] = json.dumps(record.event)
        row["_ingested_at"] = datetime.now(UTC).isoformat()
        row["_pubsub_message_id"] = record.message_id
        row["_pubsub_publish_time"] = (
            record.publish_time.isoformat() if hasattr(record.publish_time, "isoformat") else str(record.publish_time)
        )
        row["_pipeline_version"] = self.pipeline_version
        yield row
