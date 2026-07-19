"""Enriches SHIPMENT_DISPATCHED / SHIPMENT_IN_TRANSIT events with live
carrier tracking data via an external API call — the one place in this
pipeline that leaves GCP's network boundary (hence NAT in the networking
module, and why this is the transform docs/security-guide.md points to
when explaining the Secret Manager grant on the Dataflow worker SA).

Design choices:
- The API key is fetched from Secret Manager ONCE per worker (in setup(),
  not per-element) — fetching a secret on every element would be needless
  latency and load on Secret Manager for no benefit, since the key doesn't
  rotate mid-job.
- A failed enrichment call degrades gracefully: the shipment event still
  gets written to Bronze with carrier_live_status/carrier_eta left null,
  logged as a warning. Enrichment is an enhancement, not a correctness
  requirement — a shipment event is still valid and worth having without it,
  so this deliberately does NOT route to the DLQ on enrichment failure.
- Swap CARRIER_API_BASE_URL for a real or sandbox carrier tracking
  endpoint before running against real traffic; this ships pointed at a
  placeholder so the pipeline is runnable without a live third-party
  contract.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import apache_beam as beam
import requests
from google.cloud import secretmanager

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from supplychain_common.retry import RetriesExhausted, call_with_backoff  # noqa: E402

logger = logging.getLogger(__name__)

ENRICHABLE_EVENT_TYPES = {"SHIPMENT_DISPATCHED", "SHIPMENT_IN_TRANSIT"}
CARRIER_API_BASE_URL = "https://api.example-carrier-sandbox.com/v1/track"


class EnrichShipment(beam.DoFn):
    def __init__(self, project_id: str, secret_id: str):
        self.project_id = project_id
        self.secret_id = secret_id
        self._api_key = None

    def setup(self):
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{self.project_id}/secrets/{self.secret_id}/versions/latest"
        self._api_key = client.access_secret_version(name=name).payload.data.decode("utf-8")

    def process(self, record):
        event = record.event
        if event.get("event_type") not in ENRICHABLE_EVENT_TYPES:
            yield record
            return

        try:
            status, eta = call_with_backoff(
                lambda: self._call_carrier_api(event["carrier"], event["tracking_number"]),
                max_attempts=3,
                base_delay_seconds=0.5,
                retry_on=(requests.RequestException,),
            )
            record.event["carrier_live_status"] = status
            record.event["carrier_eta"] = eta
        except RetriesExhausted as exc:
            logger.warning(
                "carrier enrichment failed for shipment_id=%s after retries: %s — writing without enrichment",
                event.get("shipment_id"),
                exc,
            )
            record.event["carrier_live_status"] = None
            record.event["carrier_eta"] = None

        yield record

    def _call_carrier_api(self, carrier: str, tracking_number: str) -> tuple[str, str]:
        if not tracking_number:
            return None, None
        response = requests.get(
            CARRIER_API_BASE_URL,
            params={"carrier": carrier, "tracking_number": tracking_number},
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=5,
        )
        response.raise_for_status()
        body = response.json()
        return body.get("status"), body.get("eta")
