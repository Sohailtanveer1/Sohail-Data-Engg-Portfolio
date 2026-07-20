"""SAP ERP emulator -> CSV drops (SFTP daily).

Entities: material_master, vendor, purchase_order, goods_receipt,
inventory_valuation. Row-building is pure Python (list[dict]) so it is testable
without pandas; ``generate.py`` handles CSV serialization.

Deliberate messiness (controlled by ``dirty_fraction``) mirrors real SAP feeds:
null business keys, negative quantities, invalid currency codes, malformed SKUs.
"""

from __future__ import annotations

from datetime import date, timedelta

from data_generators.reference import CURRENCIES, ReferenceData

SOURCE = "sap_erp"
ENTITIES = ["material_master", "vendor", "purchase_order", "goods_receipt", "inventory_valuation"]


def generate(
    ref: ReferenceData, gen_date: date, *, n_pos: int = 500, dirty_fraction: float = 0.03
) -> dict[str, list[dict]]:
    r = ref.rng
    iso = gen_date.isoformat()

    material_master = [
        {**m, "hazmat": "Y" if m["hazmat"] else "N", "updated_date": iso} for m in ref.materials
    ]
    vendor = [{**v, "updated_date": iso} for v in ref.vendors]

    purchase_order: list[dict] = []
    for i in range(n_pos):
        mat = ref.sample_material()
        ven = ref.sample_vendor()
        wh = ref.sample_warehouse()
        n_lines = r.randint(1, 4)
        for line in range(1, n_lines + 1):
            qty = r.randint(1, 500)
            currency = r.choice(CURRENCIES)
            material_id = mat["material_id"]
            # inject dirt
            if r.random() < dirty_fraction:
                choice = r.choice(["null_key", "neg_qty", "bad_ccy", "bad_sku"])
                if choice == "null_key":
                    material_id = None
                elif choice == "neg_qty":
                    qty = -qty
                elif choice == "bad_ccy":
                    currency = "XXX"
                elif choice == "bad_sku":
                    material_id = "??" + material_id[2:]
            purchase_order.append(
                {
                    "po_number": f"PO{gen_date.strftime('%Y%m%d')}{i:05d}",
                    "po_line": line,
                    "material_id": material_id,
                    "vendor_id": ven["vendor_id"],
                    "warehouse_id": wh["warehouse_id"],
                    "order_qty": qty,
                    "unit_price": round(mat["std_cost"] * r.uniform(0.9, 1.3), 2),
                    "currency": currency,
                    "order_date": iso,
                    "expected_date": (gen_date + timedelta(days=r.randint(3, 30))).isoformat(),
                }
            )

    goods_receipt: list[dict] = []
    for po in purchase_order:
        if po["material_id"] is None or r.random() > 0.6:
            continue
        received = max(0, int((po["order_qty"] or 0) * r.uniform(0.5, 1.0)))
        goods_receipt.append(
            {
                "receipt_id": f"GR{gen_date.strftime('%Y%m%d')}{len(goods_receipt):06d}",
                "po_number": po["po_number"],
                "po_line": po["po_line"],
                "material_id": po["material_id"],
                "warehouse_id": po["warehouse_id"],
                "received_qty": received,
                "receipt_date": iso,
            }
        )

    inventory_valuation: list[dict] = []
    for m in r.sample(ref.materials, k=min(len(ref.materials), 250)):
        wh = ref.sample_warehouse()
        qty = r.randint(0, 5000)
        inventory_valuation.append(
            {
                "material_id": m["material_id"],
                "warehouse_id": wh["warehouse_id"],
                "valuation_date": iso,
                "qty_on_hand": qty,
                "std_cost": m["std_cost"],
                "valuation_amount": round(qty * m["std_cost"], 2),
                "currency": "USD",
            }
        )

    return {
        "material_master": material_master,
        "vendor": vendor,
        "purchase_order": purchase_order,
        "goods_receipt": goods_receipt,
        "inventory_valuation": inventory_valuation,
    }
