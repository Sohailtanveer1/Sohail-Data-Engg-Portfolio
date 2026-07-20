"""Unit-test the BigQuery metadata store with a fake backend (no cloud/deps)."""

from scb_common.metadata import BatchAudit, DQResultRecord, FileAudit
from scb_common.stores.bigquery import BigQueryMetadataStore


class FakeBackend:
    """Captures inserts and serves canned query results."""

    def __init__(self):
        self.inserts: list[tuple[str, list[dict]]] = []
        self.queries: list[tuple[str, dict]] = []
        self.query_result: list[dict] = []
        self.fail = False

    def insert_rows(self, table_id, rows):
        self.inserts.append((table_id, rows))
        return [{"index": 0, "errors": ["boom"]}] if self.fail else []

    def run_query(self, sql, params):
        self.queries.append((sql, params))
        return self.query_result


def _store():
    be = FakeBackend()
    return BigQueryMetadataStore("proj", "scb_metadata_dev", backend=be), be


def test_write_batch_targets_correct_table():
    store, be = _store()
    store.write_batch(BatchAudit(batch_id="b1", pipeline="p", source="s", destination="d"))
    table, rows = be.inserts[0]
    assert table == "proj.scb_metadata_dev.batch_audit"
    assert rows[0]["batch_id"] == "b1"


def test_write_dq_batches_rows_and_skips_empty():
    store, be = _store()
    store.write_dq([])
    assert be.inserts == []
    store.write_dq([
        DQResultRecord(batch_id="b1", entity="po", rule="NotNull(x)", severity="error",
                       passed=9, failed=1, threshold=0.0, breached=True, sample_keys=["k"]),
    ])
    table, rows = be.inserts[0]
    assert table == "proj.scb_metadata_dev.dq_results"
    assert rows[0]["failed"] == 1


def test_insert_error_raises():
    store, be = _store()
    be.fail = True
    try:
        store.write_file(FileAudit(batch_id="b1", source="sap", filename="f.csv",
                                   checksum="c", size_bytes=1))
        raised = False
    except RuntimeError:
        raised = True
    assert raised


def test_get_watermark_returns_value_or_none():
    store, be = _store()
    assert store.get_watermark("po") is None
    be.query_result = [{"watermark_value": "2026-07-19"}]
    assert store.get_watermark("po") == "2026-07-19"
    assert be.queries[-1][1] == {"entity": "po"}


def test_set_watermark_issues_merge_with_params():
    store, be = _store()
    store.set_watermark("po", "2026-07-20")
    sql, params = be.queries[-1]
    assert "MERGE" in sql
    assert params == {"entity": "po", "value": "2026-07-20"}


def test_is_file_seen_true_when_rows_returned():
    store, be = _store()
    assert store.is_file_seen("sap", "c") is False
    be.query_result = [{"hit": 1}]
    assert store.is_file_seen("sap", "c") is True
    assert be.queries[-1][1] == {"source": "sap", "checksum": "c"}
