from datetime import date

import pytest

from data_generators import salesforce, sap_erp, supplier_portal, tms, wms
from data_generators.reference import ReferenceData

GEN_DATE = date(2026, 7, 19)


@pytest.fixture
def ref():
    return ReferenceData(seed=7)


def test_reference_is_deterministic():
    a = ReferenceData(seed=7)
    b = ReferenceData(seed=7)
    assert a.materials[0]["material_id"] == b.materials[0]["material_id"]
    assert a.materials[0]["material_id"] == "00100000"  # leading zeros preserved


def test_sap_generates_all_entities(ref):
    out = sap_erp.generate(ref, GEN_DATE, n_pos=50, dirty_fraction=0.0)
    assert set(out) == set(sap_erp.ENTITIES)
    assert out["purchase_order"], "expected PO lines"
    # clean run: every PO has a non-null material_id
    assert all(po["material_id"] is not None for po in out["purchase_order"])


def test_sap_dirt_injects_problems(ref):
    out = sap_erp.generate(ref, GEN_DATE, n_pos=400, dirty_fraction=0.5)
    pos = out["purchase_order"]
    has_null = any(po["material_id"] is None for po in pos)
    has_neg = any((po["order_qty"] or 0) < 0 for po in pos)
    has_bad_ccy = any(po["currency"] == "XXX" for po in pos)
    assert has_null and has_neg and has_bad_ccy


def test_wms_stock_movement_signing(ref):
    out = wms.generate(ref, GEN_DATE, n_movements=300, dirty_fraction=0.0)
    assert set(out) == set(wms.ENTITIES)
    moves = out["stock_movement"]
    # PICK/ADJUSTMENT may be negative; others must be positive
    for mv in moves:
        if mv["movement_type"] not in ("PICK", "ADJUSTMENT"):
            assert mv["move_qty"] > 0


def test_salesforce_incremental_carries_modstamp(ref):
    out = salesforce.generate(ref, GEN_DATE, changed_fraction=0.5)
    assert set(out) == set(salesforce.ENTITIES)
    assert all("SystemModstamp" in c for c in out["customer"])


def test_tms_shipment_shape(ref):
    out = tms.generate(ref, GEN_DATE, n_shipments=100, dirty_fraction=0.0)
    ship = out["shipment"]
    assert ship and {"shipment_id", "carrier_scac", "freight_cost", "ship_date"} <= set(ship[0])


def test_supplier_referential_to_vendors(ref):
    out = supplier_portal.generate(ref, GEN_DATE, dirty_fraction=0.0)
    assert set(out) == set(supplier_portal.ENTITIES)
    vendor_ids = {v["vendor_id"] for v in ref.vendors}
    assert all(row["supplier_id"] in vendor_ids for row in out["price_list"])
