from datetime import datetime, timezone

from scb_common.context import BatchContext, new_batch_id


def test_batch_id_is_sortable_and_unique():
    at = datetime(2026, 7, 19, 18, 30, 0, tzinfo=timezone.utc)
    a = new_batch_id("scb_sap_daily", at)
    b = new_batch_id("scb_sap_daily", at)
    assert a.startswith("scb_sap_daily-20260719T183000Z-")
    assert a != b  # unique suffix


def test_context_autofills_batch_id_and_log_fields():
    ctx = BatchContext(pipeline="scb_wms_4h", source="wms", destination="bronze", env="dev")
    assert ctx.batch_id.startswith("scb_wms_4h-")
    fields = ctx.log_fields()
    assert fields["pipeline"] == "scb_wms_4h"
    assert fields["source"] == "wms"
    assert fields["env"] == "dev"


def test_context_respects_explicit_batch_id():
    ctx = BatchContext(pipeline="p", source="s", batch_id="fixed-123")
    assert ctx.batch_id == "fixed-123"
