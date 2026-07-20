"""Data-freshness monitoring from the batch audit trail.

Answers "did each pipeline succeed recently enough?" by reading `batch_audit`
(the same records the pipelines write). The core computation is pure/testable;
`freshness_report` reads the local JSONL store, and the Terraform `monitoring`
module provides the cloud-side freshness alert.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scb_common.context import utcnow


@dataclass
class FreshnessRow:
    pipeline: str
    last_success: str | None
    age_hours: float | None
    stale: bool


def freshness_from_audit(
    rows: Iterable[dict[str, Any]],
    *,
    now: datetime,
    max_age_hours: float,
    pipelines: list[str] | None = None,
) -> list[FreshnessRow]:
    """Per pipeline: latest successful `ended_at`, its age, and staleness.

    A pipeline with no successful run is stale. Explicitly-listed pipelines that
    never appear are reported stale with age None (missing = stale).
    """
    rows = list(rows)
    latest: dict[str, str] = {}
    seen: set[str] = set()
    for r in rows:
        p = r.get("pipeline", "")
        if p:
            seen.add(p)
        if r.get("status") != "success" or not r.get("ended_at"):
            continue
        if p not in latest or r["ended_at"] > latest[p]:
            latest[p] = r["ended_at"]

    # Report every pipeline we've seen (a failed-only one is stale), plus any
    # explicitly-expected pipelines (a missing one is stale).
    names = set(pipelines or []) | seen | set(latest)
    out: list[FreshnessRow] = []
    for p in sorted(names):
        ended = latest.get(p)
        if ended is None:
            out.append(FreshnessRow(p, None, None, True))
            continue
        age = (now - datetime.fromisoformat(ended)).total_seconds() / 3600.0
        out.append(FreshnessRow(p, ended, round(age, 2), age > max_age_hours))
    return out


def load_batch_audit_jsonl(audit_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(audit_dir) / "batch_audit.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def freshness_report(
    audit_dir: str | Path,
    *,
    now: datetime | None = None,
    max_age_hours: float = 26,
    pipelines: list[str] | None = None,
) -> list[FreshnessRow]:
    return freshness_from_audit(
        load_batch_audit_jsonl(audit_dir),
        now=now or utcnow(),
        max_age_hours=max_age_hours,
        pipelines=pipelines,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Report pipeline data freshness.")
    ap.add_argument("--audit-dir", default="data/_audit")
    ap.add_argument("--max-age-hours", type=float, default=26)
    args = ap.parse_args(argv)

    stale_found = False
    for row in freshness_report(args.audit_dir, max_age_hours=args.max_age_hours):
        flag = "STALE" if row.stale else "ok"
        age = f"{row.age_hours}h" if row.age_hours is not None else "never"
        print(f"[{flag:5s}] {row.pipeline:32s} last_success={row.last_success} age={age}")
        stale_found = stale_found or row.stale
    return 1 if stale_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
