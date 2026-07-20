import pandas as pd
from ingestion.bronze import AUDIT_COLS, add_audit_columns, row_hash, write_bronze


def test_row_hash_ignores_audit_columns_and_is_stable():
    r1 = {"material_id": "001", "qty": "5"}
    r2 = {"material_id": "001", "qty": "5", "_batch_id": "b1", "_ingest_ts": "now"}
    assert row_hash(r1) == row_hash(r2)  # audit cols excluded
    assert row_hash({"material_id": "002"}) != row_hash(r1)


def test_add_audit_columns_present():
    rows = add_audit_columns(
        [{"x": "1"}],
        batch_id="b1",
        source="sap",
        entity="po",
        source_file="f.csv",
        ingest_date="2026-07-19",
    )
    for col in AUDIT_COLS:
        assert col in rows[0]
    assert rows[0]["_source"] == "sap"
    assert rows[0]["_ingest_date"] == "2026-07-19"


def test_write_bronze_creates_parquet_with_audit(tmp_path):
    rows = [{"id": "A1", "v": "10"}, {"id": "A2", "v": "20"}]
    path, n = write_bronze(
        rows,
        bronze_root=str(tmp_path),
        source="src",
        entity="ent",
        batch_id="b1",
        source_file="f.csv",
        ingest_date="2026-07-19",
    )
    assert n == 2
    assert "ingest_date=2026-07-19" in path
    df = pd.read_parquet(path)
    assert len(df) == 2
    assert set(AUDIT_COLS).issubset(df.columns)
    assert df["_batch_id"].unique().tolist() == ["b1"]


def test_write_bronze_empty_is_noop(tmp_path):
    path, n = write_bronze(
        [],
        bronze_root=str(tmp_path),
        source="s",
        entity="e",
        batch_id="b1",
        source_file="f",
        ingest_date="2026-07-19",
    )
    assert path is None and n == 0
