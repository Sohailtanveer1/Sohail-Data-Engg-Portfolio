import logging
from datetime import UTC, datetime

from scb_common.logging import attach_handler
from scb_common.monitoring import FreshnessRow, freshness_from_audit, freshness_report

NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)

AUDIT = [
    {
        "pipeline": "scb_sap_erp_ingest",
        "status": "success",
        "ended_at": "2026-07-20T06:30:00+00:00",
    },
    {
        "pipeline": "scb_sap_erp_ingest",
        "status": "success",
        "ended_at": "2026-07-19T06:30:00+00:00",
    },
    {"pipeline": "scb_tms_ingest", "status": "failed", "ended_at": "2026-07-20T06:00:00+00:00"},
    {"pipeline": "scb_wms_ingest", "status": "success", "ended_at": "2026-07-18T00:00:00+00:00"},
]


def _by_pipeline(rows):
    return {r.pipeline: r for r in rows}


def test_freshness_picks_latest_success():
    rows = _by_pipeline(freshness_from_audit(AUDIT, now=NOW, max_age_hours=26))
    assert rows["scb_sap_erp_ingest"].last_success == "2026-07-20T06:30:00+00:00"
    assert rows["scb_sap_erp_ingest"].stale is False  # ~5.5h old


def test_only_failed_runs_means_stale():
    rows = _by_pipeline(freshness_from_audit(AUDIT, now=NOW, max_age_hours=26))
    # tms only failed -> no success -> stale, age None
    assert rows["scb_tms_ingest"] == FreshnessRow("scb_tms_ingest", None, None, True)


def test_old_success_is_stale():
    rows = _by_pipeline(freshness_from_audit(AUDIT, now=NOW, max_age_hours=26))
    assert rows["scb_wms_ingest"].stale is True  # >2 days old


def test_missing_expected_pipeline_is_stale():
    rows = _by_pipeline(
        freshness_from_audit(AUDIT, now=NOW, max_age_hours=26, pipelines=["scb_salesforce_ingest"])
    )
    assert rows["scb_salesforce_ingest"].stale is True
    assert rows["scb_salesforce_ingest"].last_success is None


def test_freshness_report_reads_jsonl(tmp_path):
    import json

    (tmp_path / "batch_audit.jsonl").write_text(
        "\n".join(json.dumps(r) for r in AUDIT), encoding="utf-8"
    )
    rows = freshness_report(tmp_path, now=NOW, max_age_hours=26)
    assert any(r.pipeline == "scb_sap_erp_ingest" for r in rows)


def test_attach_handler_adds_to_root():
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    h = Capture()
    attach_handler(h)
    try:
        logging.getLogger("scb.test.attach").info("hello")
        assert "hello" in seen
    finally:
        logging.getLogger().removeHandler(h)
