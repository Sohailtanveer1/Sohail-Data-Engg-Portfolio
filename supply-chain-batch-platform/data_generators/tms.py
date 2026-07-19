"""Transportation Management System emulator -> Parquet (cloud export, daily).

Entities: shipment (with embedded carrier/route/freight/delivery attributes).
This is the cheapest source to ingest — it's already lake-ready Parquet — so the
generator writes the analytical columns directly. ``ship_date`` drives the daily
export partition.
"""

from __future__ import annotations

from datetime import date, timedelta

from data_generators.reference import ReferenceData

SOURCE = "tms"
ENTITIES = ["shipment"]

DELIVERY_STATUS = ["IN_TRANSIT", "DELIVERED", "EXCEPTION", "RETURNED"]


def generate(ref: ReferenceData, gen_date: date, *, n_shipments: int = 600,
             dirty_fraction: float = 0.02) -> dict[str, list[dict]]:
    r = ref.rng
    iso = gen_date.isoformat()

    shipment = []
    for i in range(n_shipments):
        origin = ref.sample_warehouse()
        carrier = ref.sample_carrier()
        customer = ref.sample_customer()
        weight = round(r.uniform(5, 20_000), 1)
        transit_days = r.randint(1, 8)
        status = r.choice(DELIVERY_STATUS)
        delivered = status == "DELIVERED"
        promised_days = r.randint(2, 7)
        freight = round(weight * r.uniform(0.05, 0.4) + r.uniform(20, 200), 2)
        if r.random() < dirty_fraction:
            freight = -freight  # invalid negative freight cost

        ship_dt = gen_date
        deliver_dt = (ship_dt + timedelta(days=transit_days)) if delivered else None
        shipment.append({
            "shipment_id": f"SH{gen_date.strftime('%Y%m%d')}{i:06d}",
            "carrier_scac": carrier["carrier_scac"],
            "mode": carrier["mode"],
            "origin_warehouse_id": origin["warehouse_id"],
            "customer_id": customer["customer_id"],
            "route_id": f"RT{origin['warehouse_id']}-{r.randint(1,50):03d}",
            "weight_lb": weight,
            "freight_cost": freight,
            "currency": "USD",
            "transit_days": transit_days,
            "promised_days": promised_days,
            "on_time": bool(delivered and transit_days <= promised_days),
            "delivery_status": status,
            "ship_date": iso,
            "delivery_date": deliver_dt.isoformat() if deliver_dt else None,
        })

    return {"shipment": shipment}
