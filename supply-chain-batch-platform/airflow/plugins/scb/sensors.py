"""FileArrivalSensor — wait for a source's daily drop to be complete.

A source is "ready" when its `_SUCCESS`/marker (or the dated prefix) exists. Use
`mode="reschedule"` so the sensor frees the worker slot while waiting (no idle
occupancy) — important on a small Composer environment.

Works on local filesystem or GCS depending on the path scheme.
"""

from __future__ import annotations

import os

from airflow.sensors.base import BaseSensorOperator


class FileArrivalSensor(BaseSensorOperator):
    template_fields = ("path",)

    def __init__(self, *, path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.path = path

    def poke(self, context) -> bool:  # noqa: D401
        self.log.info("Checking for source readiness at %s", self.path)
        if self.path.startswith("gs://"):
            from google.cloud import storage

            bucket_name, _, key = self.path[5:].partition("/")
            client = storage.Client()
            return client.bucket(bucket_name).blob(key).exists()
        return os.path.exists(self.path)
