"""Phase 9 hardening: a corrupted source file is quarantined, batch continues."""

from ingestion.extractor import Extractor
from ingestion.landing import LocalLandingStore

from scb_common.metadata import JsonlMetadataStore

DS = "2026-07-19"


def _cfg(tmp_path):
    base = tmp_path / "landing" / "src" / DS
    base.mkdir(parents=True)
    # one good JSON, one corrupted JSON
    (base / "good.json").write_text('{"records":[{"id":"A1"},{"id":"A2"}]}', encoding="utf-8")
    (base / "bad.json").write_text("{ this is not valid json ", encoding="utf-8")
    return {
        "source": "src",
        "source_type": "rest",
        "format": "json",
        "landing_path": str(tmp_path / "landing" / "src"),
        "entities": {
            "good": {"load_type": "full", "business_keys": ["id"]},
            "bad": {"load_type": "full", "business_keys": ["id"]},
        },
    }


def test_corrupted_file_quarantined_batch_succeeds(tmp_path):
    cfg = _cfg(tmp_path)
    store = JsonlMetadataStore(tmp_path / "audit")
    ext = Extractor(
        landing=LocalLandingStore(), metastore=store, bronze_root=str(tmp_path / "bronze")
    )
    res = ext.run_source(cfg, DS)

    assert res.status == "success"  # one bad file did not fail the batch
    assert res.files_processed == 1  # 'good'
    assert res.files_failed == 1  # 'bad'

    # the good entity produced Bronze; the bad one did not
    good = list((tmp_path / "bronze" / "src" / "good").rglob("*.parquet"))
    bad = list((tmp_path / "bronze" / "src" / "bad").rglob("*.parquet"))
    assert len(good) == 1 and len(bad) == 0
