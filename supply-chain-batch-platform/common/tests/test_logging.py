import json
import logging

from scb_common.context import BatchContext
from scb_common.logging import get_logger


def _last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    return json.loads(out[-1])


def test_logger_emits_json_with_envelope(capsys):
    ctx = BatchContext(pipeline="scb_sap_daily", source="sap", destination="bronze")
    log = get_logger("test.sap", ctx=ctx)
    log.info("read_complete", rows_read=100)
    rec = _last_json(capsys)
    assert rec["message"] == "read_complete"
    assert rec["pipeline"] == "scb_sap_daily"
    assert rec["batch_id"] == ctx.batch_id
    assert rec["rows_read"] == 100
    assert rec["level"] == "INFO"


def test_metrics_line_has_canonical_fields(capsys):
    log = get_logger("test.metrics")
    log.metrics(status="success", rows_read=10, rows_written=9, rows_rejected=1, duration_s=1.234)
    rec = _last_json(capsys)
    assert rec["message"] == "pipeline_metrics"
    assert rec["status"] == "success"
    assert rec["rows_rejected"] == 1
    assert rec["duration_s"] == 1.234


def test_bind_attaches_persistent_fields(capsys):
    log = get_logger("test.bind").bind(entity="material")
    log.warning("slow")
    rec = _last_json(capsys)
    assert rec["entity"] == "material"
    assert rec["level"] == "WARNING"


def test_error_includes_exception(capsys):
    log = get_logger("test.err")
    try:
        raise ValueError("boom")
    except ValueError:
        log.error("failed", exc_info=True)
    rec = _last_json(capsys)
    assert "boom" in rec["error"]


def teardown_module(module):
    logging.getLogger().handlers.clear()
