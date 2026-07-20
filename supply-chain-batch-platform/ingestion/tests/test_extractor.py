"""End-to-end (offline) ingestion: land a CSV source to Bronze, prove audit +
idempotency (checksum dedup) + watermark advance."""

import pandas as pd
from ingestion.extractor import Extractor
from ingestion.landing import LocalLandingStore

from scb_common.metadata import JsonlMetadataStore

DS = "2026-07-19"


def _make_source(tmp_path):
    landing = tmp_path / "landing" / "testsrc" / DS
    landing.mkdir(parents=True)
    (landing / "widget.csv").write_text(
        "id,updated\n" "A1,2026-07-19T01:00:00\n" "A2,2026-07-19T05:00:00\n",
        encoding="utf-8",
    )
    return {
        "source": "testsrc",
        "source_type": "sftp",
        "format": "csv",
        "delimiter": ",",
        "landing_path": str(tmp_path / "landing" / "testsrc"),
        "archive_path": str(tmp_path / "archive"),
        "entities": {
            "widget": {
                "load_type": "incremental",
                "watermark_column": "updated",
                "business_keys": ["id"],
            }
        },
    }


def _extractor(tmp_path):
    return Extractor(
        landing=LocalLandingStore(),
        metastore=JsonlMetadataStore(tmp_path / "audit"),
        bronze_root=str(tmp_path / "bronze"),
    )


def test_land_to_bronze_with_audit_and_watermark(tmp_path):
    cfg = _make_source(tmp_path)
    ext = _extractor(tmp_path)
    res = ext.run_source(cfg, DS)

    assert res.status == "success"
    assert res.rows_read == 2 and res.rows_written == 2
    assert res.files_processed == 1 and res.files_skipped == 0

    # Bronze parquet exists with audit columns
    parquet = list((tmp_path / "bronze" / "testsrc" / "widget").rglob("*.parquet"))
    assert len(parquet) == 1
    df = pd.read_parquet(parquet[0])
    assert df["_source"].unique().tolist() == ["testsrc"]

    # watermark advanced to the max updated value
    assert ext.metastore.get_watermark("testsrc.widget") == "2026-07-19T05:00:00"

    # archive copy made
    assert (tmp_path / "archive" / "testsrc" / DS / "widget.csv").exists()


def test_rerun_is_idempotent_via_checksum_dedup(tmp_path):
    cfg = _make_source(tmp_path)
    ext = _extractor(tmp_path)
    ext.run_source(cfg, DS)  # first run processes
    res2 = ext.run_source(cfg, DS)  # second run should skip the unchanged file

    assert res2.files_processed == 0
    assert res2.files_skipped == 1
    assert res2.rows_written == 0


def test_missing_file_is_warned_not_fatal(tmp_path):
    cfg = _make_source(tmp_path)
    cfg["entities"]["ghost"] = {"load_type": "full", "business_keys": ["id"]}
    ext = _extractor(tmp_path)
    res = ext.run_source(cfg, DS)  # 'ghost' has no file; should not crash
    assert res.status == "success"
    assert res.files_processed == 1  # only widget
