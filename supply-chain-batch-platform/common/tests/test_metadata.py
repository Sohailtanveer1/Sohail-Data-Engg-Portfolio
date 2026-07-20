from scb_common.metadata import (
    BatchAudit,
    DQResultRecord,
    FileAudit,
    InMemoryMetadataStore,
    JsonlMetadataStore,
    finalize,
)


def test_inmemory_batch_and_watermark_roundtrip():
    store = InMemoryMetadataStore()
    store.write_batch(BatchAudit(batch_id="b1", pipeline="p", source="s", destination="d"))
    store.set_watermark("material", "2026-07-19T00:00:00")
    assert store.get_watermark("material") == "2026-07-19T00:00:00"
    assert len(store.batches) == 1


def test_inmemory_file_dedup():
    store = InMemoryMetadataStore()
    store.write_file(
        FileAudit(batch_id="b1", source="sap", filename="po.csv", checksum="abc", size_bytes=10)
    )
    assert store.is_file_seen("sap", "abc")
    assert not store.is_file_seen("sap", "def")


def test_finalize_stamps_duration_and_status():
    audit = BatchAudit(batch_id="b1", pipeline="p", source="s", destination="d")
    finalize(audit, status="success")
    assert audit.status == "success"
    assert audit.ended_at is not None
    assert audit.duration_s is not None and audit.duration_s >= 0


def test_jsonl_store_persists_and_dedups(tmp_path):
    store = JsonlMetadataStore(tmp_path)
    store.write_file(
        FileAudit(
            batch_id="b1", source="tms", filename="ship.parquet", checksum="xyz", size_bytes=99
        )
    )
    store.write_dq(
        [
            DQResultRecord(
                batch_id="b1",
                entity="shipment",
                rule="NotNull(id)",
                severity="error",
                passed=9,
                failed=1,
                threshold=0.0,
                breached=True,
                sample_keys=["S9"],
            )
        ]
    )
    store.set_watermark("shipment", "2026-07-19")

    assert (tmp_path / "file_audit.jsonl").is_file()
    assert (tmp_path / "dq_results.jsonl").is_file()
    assert store.is_file_seen("tms", "xyz")
    assert store.get_watermark("shipment") == "2026-07-19"

    # A fresh store over the same dir still sees the file (persistence).
    reopened = JsonlMetadataStore(tmp_path)
    assert reopened.is_file_seen("tms", "xyz")
    assert reopened.get_watermark("shipment") == "2026-07-19"
