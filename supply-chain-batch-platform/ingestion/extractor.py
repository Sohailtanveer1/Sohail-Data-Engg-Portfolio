"""The ingestion orchestrator: config-driven land-to-Bronze with audit + dedup.

One ``BatchContext`` per source run; per-file ``file_audit`` with checksum dedup;
per-entity watermark advance for incremental loads; one ``batch_audit`` row with
the rows read/written/rejected envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple

from scb_common.context import BatchContext
from scb_common.logging import get_logger
from scb_common.metadata import BatchAudit, FileAudit, MetadataStore, finalize

from ingestion.bronze import write_bronze
from ingestion.landing import LandingStore
from ingestion.readers import read_entity


class FileRef(NamedTuple):
    path: str
    sheet: str | None


@dataclass
class SourceResult:
    source: str
    batch_id: str
    rows_read: int
    rows_written: int
    files_processed: int
    files_skipped: int
    status: str


class Extractor:
    def __init__(self, *, landing: LandingStore, metastore: MetadataStore,
                 bronze_root: str, env: str = "local") -> None:
        self.landing = landing
        self.metastore = metastore
        self.bronze_root = bronze_root
        self.env = env

    # -- file discovery ----------------------------------------------------
    def _resolve_files(self, cfg: dict, entity: str, ds: str) -> list[FileRef]:
        base = cfg["landing_path"]
        fmt = cfg["format"]
        if fmt in ("csv", "json"):
            ext = "csv" if fmt == "csv" else "json"
            return [FileRef(f"{base}/{ds}/{entity}.{ext}", None)]
        if fmt == "parquet":
            part = cfg.get("partition_pattern", "ship_date={ds}").format(ds=ds)
            return [FileRef(p, None) for p in self.landing.list(f"{base}/{part}/*.parquet")]
        if fmt == "xlsx":
            wb = cfg.get("workbook", "{source}.xlsx").format(source=cfg["source"])
            return [FileRef(f"{base}/{ds}/{wb}", entity)]
        raise ValueError(f"Unsupported format: {fmt}")

    # -- per-entity --------------------------------------------------------
    def _process_file_entity(self, cfg: dict, entity: str, entity_cfg: dict, ds: str,
                             ctx: BatchContext, log) -> tuple[int, int, int, int]:
        source = cfg["source"]
        fmt = cfg["format"]
        read = written = processed = skipped = 0

        for ref in self._resolve_files(cfg, entity, ds):
            if not self.landing.exists(ref.path):
                log.warning("source_file_missing", entity=entity, file=ref.path)
                continue

            checksum = self.landing.checksum(ref.path)
            dedup_key = f"{checksum}:{entity}" if ref.sheet else checksum
            if self.metastore.is_file_seen(source, dedup_key):
                skipped += 1
                log.info("skip_duplicate", entity=entity, file=ref.path)
                self.metastore.write_file(FileAudit(
                    batch_id=ctx.batch_id, source=source, filename=ref.path,
                    checksum=dedup_key, size_bytes=0, status="skipped_duplicate"))
                continue

            data = self.landing.read_bytes(ref.path)
            rows = read_entity(data, fmt=fmt, delimiter=cfg.get("delimiter", ","),
                               sheet=ref.sheet)
            path, n = write_bronze(rows, bronze_root=self.bronze_root, source=source,
                                   entity=entity, batch_id=ctx.batch_id,
                                   source_file=ref.path, ingest_date=ds)
            read += len(rows)
            written += n
            processed += 1

            self.metastore.write_file(FileAudit(
                batch_id=ctx.batch_id, source=source, filename=ref.path,
                checksum=dedup_key, size_bytes=len(data), status="processed"))

            if cfg.get("archive_path"):
                self.landing.archive(ref.path, cfg["archive_path"], f"{source}/{ds}")

            self._advance_watermark(source, entity, entity_cfg, rows)
            log.info("entity_landed", entity=entity, rows=n, bronze=path)

        return read, written, processed, skipped

    def _process_jdbc_entity(self, cfg: dict, entity: str, entity_cfg: dict, ds: str,
                             ctx: BatchContext, log) -> tuple[int, int, int, int]:
        from ingestion.jdbc import read_table

        source = cfg["source"]
        wm_col = entity_cfg.get("watermark_column")
        wm = self.metastore.get_watermark(f"{source}.{entity}") if wm_col else None
        rows = read_table(cfg.get("schema", source), entity,
                          watermark_column=wm_col, watermark=wm)
        path, n = write_bronze(rows, bronze_root=self.bronze_root, source=source,
                               entity=entity, batch_id=ctx.batch_id,
                               source_file=f"jdbc://{source}/{entity}", ingest_date=ds)
        self._advance_watermark(source, entity, entity_cfg, rows)
        log.info("entity_landed", entity=entity, rows=n, bronze=path)
        return len(rows), n, 1, 0

    def _advance_watermark(self, source: str, entity: str, entity_cfg: dict,
                           rows: list[dict[str, Any]]) -> None:
        if entity_cfg.get("load_type") != "incremental":
            return
        col = entity_cfg.get("watermark_column")
        if not col:
            return
        values = [r[col] for r in rows if r.get(col) is not None]
        if values:
            self.metastore.set_watermark(f"{source}.{entity}", str(max(values)))

    # -- source run --------------------------------------------------------
    def run_source(self, cfg: dict, ds: str, entities: list[str] | None = None) -> SourceResult:
        source = cfg["source"]
        ctx = BatchContext(pipeline=f"scb_{source}_ingest", source=source,
                           destination="bronze", env=self.env)
        log = get_logger(f"ingest.{source}", ctx=ctx)
        audit = BatchAudit(batch_id=ctx.batch_id, pipeline=ctx.pipeline,
                           source=source, destination="bronze")

        entity_names = entities or list(cfg["entities"].keys())
        rows_read = rows_written = files_processed = files_skipped = 0
        is_jdbc = cfg["source_type"] == "jdbc"

        try:
            for entity in entity_names:
                entity_cfg = cfg["entities"][entity]
                handler = self._process_jdbc_entity if is_jdbc else self._process_file_entity
                r, w, p, s = handler(cfg, entity, entity_cfg, ds, ctx, log)
                rows_read += r
                rows_written += w
                files_processed += p
                files_skipped += s

            audit.rows_read = rows_read
            audit.rows_written = rows_written
            audit.rows_rejected = rows_read - rows_written
            finalize(audit, status="success")
            self.metastore.write_batch(audit)
            log.metrics(status="success", rows_read=rows_read, rows_written=rows_written,
                        rows_rejected=audit.rows_rejected, duration_s=audit.duration_s,
                        files_processed=files_processed, files_skipped=files_skipped)
            return SourceResult(source, ctx.batch_id, rows_read, rows_written,
                                files_processed, files_skipped, "success")
        except Exception as exc:  # noqa: BLE001 - audited + re-raised
            finalize(audit, status="failed", error=str(exc))
            self.metastore.write_batch(audit)
            log.error("ingestion_failed", exc_info=True, error=str(exc))
            raise
