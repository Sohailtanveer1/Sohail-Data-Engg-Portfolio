"""CLI: generate one day of data for one or all source systems, in native formats.

    python -m data_generators.generate --source all --date 2026-07-19 --out data/landing
    python -m data_generators.generate --source sap_erp --date 2026-07-19

Output layout (mirrors what each real source drops):
    <out>/sap_erp/<date>/<entity>.csv          + _SUCCESS
    <out>/salesforce/<date>/<entity>.json
    <out>/wms/<date>/<entity>.csv
    <out>/tms/ship_date=<date>/shipment.parquet
    <out>/supplier_portal/<date>/supplier_portal.xlsx  + _SUCCESS
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from data_generators import salesforce, sap_erp, supplier_portal, tms, wms
from data_generators.reference import ReferenceData

GENERATORS = {
    sap_erp.SOURCE: sap_erp,
    salesforce.SOURCE: salesforce,
    wms.SOURCE: wms,
    tms.SOURCE: tms,
    supplier_portal.SOURCE: supplier_portal,
}


def _write_csv(rows: list[dict], path: Path, sep: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # dtype=object + keep_default_na False-ish: preserve leading-zero ids as strings.
    pd.DataFrame(rows).to_csv(path, index=False, sep=sep)


def _write_json(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"totalSize": len(rows), "done": True, "records": rows},
                               indent=2, default=str), encoding="utf-8")


def _write_parquet(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_messy_xlsx(entities: dict[str, list[dict]], path: Path) -> None:
    """Write one sheet per entity with human-authored quirks (title row, blanks)."""
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in entities.items():
        ws = wb.create_sheet(title=name[:31])
        # a merged-looking title row above the real header (classic mess)
        ws.append([f"Supplier Portal Export - {name} - generated"])
        headers = list(rows[0].keys()) if rows else []
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
        # a couple of blank trailing rows
        ws.append([])
        ws.append([None] * len(headers))
    wb.save(path)


def generate_source(source: str, ref: ReferenceData, gen_date: date, out: Path,
                    dirty: float) -> dict[str, int]:
    mod = GENERATORS[source]
    entities = mod.generate(ref, gen_date, dirty_fraction=dirty)
    ds = gen_date.isoformat()
    counts = {k: len(v) for k, v in entities.items()}

    if source == "sap_erp":
        base = out / source / ds
        for entity, rows in entities.items():
            _write_csv(rows, base / f"{entity}.csv", sep="|")  # SAP-style pipe delimiter
        (base / "_SUCCESS").write_text("", encoding="utf-8")
    elif source == "salesforce":
        base = out / source / ds
        for entity, rows in entities.items():
            _write_json(rows, base / f"{entity}.json")
    elif source == "wms":
        base = out / source / ds
        for entity, rows in entities.items():
            _write_csv(rows, base / f"{entity}.csv")
    elif source == "tms":
        for entity, rows in entities.items():
            _write_parquet(rows, out / source / f"ship_date={ds}" / f"{entity}.parquet")
    elif source == "supplier_portal":
        base = out / source / ds
        _write_messy_xlsx(entities, base / "supplier_portal.xlsx")
        (base / "_SUCCESS").write_text("", encoding="utf-8")

    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate local source-system data.")
    ap.add_argument("--source", default="all",
                    choices=["all", *GENERATORS.keys()])
    ap.add_argument("--date", default=date.today().isoformat(),
                    help="generation date YYYY-MM-DD")
    ap.add_argument("--out", default="data/landing", help="output root directory")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dirty", type=float, default=0.03,
                    help="fraction of deliberately bad rows [0..1]")
    args = ap.parse_args(argv)

    gen_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    out = Path(args.out)
    ref = ReferenceData(seed=args.seed)
    sources = list(GENERATORS) if args.source == "all" else [args.source]

    for source in sources:
        counts = generate_source(source, ref, gen_date, out, args.dirty)
        total = sum(counts.values())
        print(f"[{source}] {args.date} -> {total} rows across {len(counts)} entities: {counts}")

    print(f"Done. Output under: {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
