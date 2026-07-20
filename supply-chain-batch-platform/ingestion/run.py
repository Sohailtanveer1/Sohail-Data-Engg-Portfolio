"""CLI: run metadata-driven ingestion (land -> Bronze) for one or all sources.

    python -m ingestion.run --source all --date 2026-07-19
    python -m ingestion.run --source sap_erp --entity purchase_order --date 2026-07-19

Sources and entities come from config/sources/*.yaml. Audit goes to a JSONL store
locally (or BigQuery when --bq-project/--bq-dataset are given).
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from scb_common.config import load_config
from scb_common.metadata import JsonlMetadataStore, MetadataStore

from ingestion.extractor import Extractor
from ingestion.landing import LocalLandingStore

CONFIG_DIR = Path("config/sources")


def _metastore(args) -> MetadataStore:
    if args.bq_project and args.bq_dataset:
        from scb_common.stores.bigquery import BigQueryMetadataStore
        return BigQueryMetadataStore(project=args.bq_project, dataset=args.bq_dataset)
    return JsonlMetadataStore(args.audit_dir)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Land source data to Bronze.")
    ap.add_argument("--source", default="all")
    ap.add_argument("--entity", default=None, help="single entity (optional)")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--config-dir", default=str(CONFIG_DIR))
    ap.add_argument("--bronze-root", default="data/bronze")
    ap.add_argument("--audit-dir", default="data/_audit")
    ap.add_argument("--bq-project", default=None)
    ap.add_argument("--bq-dataset", default=None)
    args = ap.parse_args(argv)

    cfg_dir = Path(args.config_dir)
    if args.source == "all":
        sources = sorted(p.stem for p in cfg_dir.glob("*.yaml"))
    else:
        sources = [args.source]

    metastore = _metastore(args)
    extractor = Extractor(landing=LocalLandingStore(), metastore=metastore,
                          bronze_root=args.bronze_root, env="local")

    for source in sources:
        cfg = load_config(cfg_dir / f"{source}.yaml")
        entities = [args.entity] if args.entity else None
        result = extractor.run_source(cfg, args.date, entities=entities)
        print(f"[{source}] {args.date} -> read={result.rows_read} written={result.rows_written} "
              f"processed={result.files_processed} skipped={result.files_skipped} "
              f"status={result.status} batch={result.batch_id}")

    print(f"Bronze under: {Path(args.bronze_root).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
