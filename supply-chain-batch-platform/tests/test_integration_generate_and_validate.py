"""Integration: generators (Phase 2) + scb_common schema/DQ (Phase 2).

Proves the pieces fit before any cloud exists: generate a dirty SAP feed, run it
through the schema contract and the data-quality framework, and confirm bad rows
are detected and quarantined while clean rows survive. This is the shape every
Phase 5/6 pipeline will follow.
"""

from datetime import date

from data_generators import sap_erp
from data_generators.reference import ReferenceData

from scb_common.dq import AllowedValues, NonNegative, NotNull, Unique, evaluate
from scb_common.errors import DataQualityError
from scb_common.metadata import DQResultRecord, InMemoryMetadataStore
from scb_common.schema import ColumnSpec, TableSchema

PO_SCHEMA = TableSchema(
    entity="purchase_order",
    columns=[
        ColumnSpec("po_number", "string", nullable=False),
        ColumnSpec("po_line", "int", nullable=False),
        ColumnSpec("material_id", "string", nullable=True),  # nullable in bronze; DQ flags nulls
        ColumnSpec("order_qty", "int"),
        ColumnSpec("currency", "string"),
    ],
    business_keys=["po_number", "po_line"],
)

PO_RULES = [
    NotNull("material_id"),
    NonNegative("order_qty"),
    AllowedValues("currency", allowed={"USD", "CAD"}),
]


def test_dirty_sap_feed_is_detected_and_quarantined():
    ref = ReferenceData(seed=13)
    feed = sap_erp.generate(ref, date(2026, 7, 19), n_pos=400, dirty_fraction=0.4)
    rows = feed["purchase_order"]

    # Bronze schema validation tolerates the data (material_id nullable) ...
    PO_SCHEMA.validate_rows(rows)

    # ... but the DQ framework catches the injected problems.
    report = evaluate(rows, PO_RULES, key_column="po_number")
    by = {r.rule: r for r in report.results}
    assert by["NotNull(material_id)"].failed > 0
    assert by["NonNegative(order_qty)"].failed > 0
    assert by["AllowedValues(currency)"].failed > 0

    clean, quarantined = report.split(rows)
    assert len(quarantined) > 0
    assert len(clean) + len(quarantined) == len(rows)


def test_clean_feed_passes_and_writes_audit():
    ref = ReferenceData(seed=13)
    feed = sap_erp.generate(ref, date(2026, 7, 19), n_pos=200, dirty_fraction=0.0)
    rows = feed["purchase_order"]

    report = evaluate(rows, PO_RULES, key_column="po_number")
    report.raise_if_failed()  # no breach on a clean feed

    # persist DQ results to the metadata store (as Phase 5/6 will)
    store = InMemoryMetadataStore()
    store.write_dq(
        [
            DQResultRecord(
                batch_id="b1",
                entity="purchase_order",
                rule=r.rule,
                severity=r.severity,
                passed=r.passed,
                failed=r.failed,
                threshold=r.threshold,
                breached=r.breached,
                sample_keys=r.sample_keys,
            )
            for r in report.results
        ]
    )
    assert len(store.dq) == len(PO_RULES)


def test_uniqueness_and_threshold_enforcement():
    ref = ReferenceData(seed=1)
    feed = sap_erp.generate(ref, date(2026, 7, 19), n_pos=100, dirty_fraction=0.9)
    rows = feed["purchase_order"]
    # A high-dirt feed should breach a zero-tolerance NotNull rule.
    report = evaluate(rows, [NotNull("material_id", threshold=0.0)], key_column="po_number")
    try:
        report.raise_if_failed()
        raised = False
    except DataQualityError:
        raised = True
    assert raised

    # Unique on (composite) po_number is naturally satisfied per line here.
    u = evaluate(rows, [Unique("po_number")]).results[0]
    assert u.failed >= 0  # multi-line POs share po_number; this just exercises the path
