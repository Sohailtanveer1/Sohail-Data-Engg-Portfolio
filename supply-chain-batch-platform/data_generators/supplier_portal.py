"""Supplier Portal emulator -> Excel .xlsx (SFTP daily, deliberately messy).

Entities (one worksheet each): supplier_catalog, price_list, lead_time, moq.
Suppliers reuse the SAP vendor ids (supplier ⊇ vendor). Row-building is pure
Python; ``generate.py``'s Excel writer adds the classic human-authored quirks
(a title row above the header, numbers stored as text, blank trailing rows) so
the Phase 6 data-quality framework has realistic problems to catch.
"""

from __future__ import annotations

from datetime import date

from data_generators.reference import CURRENCIES, ReferenceData

SOURCE = "supplier_portal"
ENTITIES = ["supplier_catalog", "price_list", "lead_time", "moq"]


def generate(
    ref: ReferenceData, gen_date: date, *, dirty_fraction: float = 0.05
) -> dict[str, list[dict]]:
    r = ref.rng
    iso = gen_date.isoformat()

    supplier_catalog = []
    price_list = []
    lead_time = []
    moq = []

    for ven in ref.vendors:
        # each supplier lists a handful of materials
        for m in r.sample(ref.materials, k=r.randint(3, 8)):
            price = round(m["std_cost"] * r.uniform(0.8, 1.4), 2)
            ccy = r.choice(CURRENCIES)
            days = r.randint(2, 60)
            min_qty = r.choice([1, 5, 10, 25, 50, 100])

            # inject dirt
            if r.random() < dirty_fraction:
                choice = r.choice(["text_num", "null_lead", "zero_moq", "bad_ccy"])
                if choice == "text_num":
                    price = f" {price} "  # number stored as text w/ spaces
                elif choice == "null_lead":
                    days = None
                elif choice == "zero_moq":
                    min_qty = 0
                elif choice == "bad_ccy":
                    ccy = "US$"  # invalid currency token

            supplier_catalog.append(
                {
                    "supplier_id": ven["vendor_id"],
                    "supplier_name": ven["vendor_name"],
                    "material_id": m["material_id"],
                    "catalog_desc": f"{ven['vendor_name']} :: {m['description']}",
                    "as_of_date": iso,
                }
            )
            price_list.append(
                {
                    "supplier_id": ven["vendor_id"],
                    "material_id": m["material_id"],
                    "unit_price": price,
                    "currency": ccy,
                    "as_of_date": iso,
                }
            )
            lead_time.append(
                {
                    "supplier_id": ven["vendor_id"],
                    "material_id": m["material_id"],
                    "lead_time_days": days,
                    "as_of_date": iso,
                }
            )
            moq.append(
                {
                    "supplier_id": ven["vendor_id"],
                    "material_id": m["material_id"],
                    "min_order_qty": min_qty,
                    "as_of_date": iso,
                }
            )

    return {
        "supplier_catalog": supplier_catalog,
        "price_list": price_list,
        "lead_time": lead_time,
        "moq": moq,
    }
