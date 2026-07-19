"""Warehouse Management System emulator -> CSV (loaded into local Postgres, every 4h).

Entities: inventory, warehouse_location, stock_movement, cycle_count. These CSVs
are loaded into the ``wms`` Postgres schema by ``scripts/seed_wms.py`` so Phase 5
can extract them over JDBC exactly like the real source. ``updated_at`` supports
incremental extraction.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from data_generators.reference import ReferenceData

SOURCE = "wms"
ENTITIES = ["inventory", "warehouse_location", "stock_movement", "cycle_count"]

MOVEMENT_TYPES = ["RECEIPT", "PUTAWAY", "PICK", "TRANSFER", "ADJUSTMENT", "RETURN"]


def _ts(gen_date: date, rng) -> str:
    midnight = datetime.combine(gen_date, time.min, tzinfo=timezone.utc)
    return (midnight + timedelta(seconds=rng.randint(0, 86_399))).isoformat()


def generate(ref: ReferenceData, gen_date: date, *, n_movements: int = 800,
             dirty_fraction: float = 0.02) -> dict[str, list[dict]]:
    r = ref.rng

    warehouse_location = []
    for wh in ref.warehouses:
        for aisle in range(1, 4):
            for bin_no in range(1, 6):
                warehouse_location.append({
                    "location_id": f"{wh['warehouse_id']}-A{aisle}-B{bin_no:02d}",
                    "warehouse_id": wh["warehouse_id"],
                    "aisle": aisle,
                    "bin": bin_no,
                    "location_type": r.choice(["BULK", "PICK", "RESERVE"]),
                })

    inventory = []
    for wh in ref.warehouses:
        for m in r.sample(ref.materials, k=min(len(ref.materials), 120)):
            qty = r.randint(0, 8000)
            inventory.append({
                "warehouse_id": wh["warehouse_id"],
                "material_id": m["material_id"],
                "on_hand_qty": qty,
                "allocated_qty": min(qty, r.randint(0, 500)),
                "location_id": f"{wh['warehouse_id']}-A{r.randint(1,3)}-B{r.randint(1,5):02d}",
                "updated_at": _ts(gen_date, r),
            })

    stock_movement = []
    for i in range(n_movements):
        mat = ref.sample_material()
        wh = ref.sample_warehouse()
        mtype = r.choice(MOVEMENT_TYPES)
        qty = r.randint(1, 300)
        # PICK/ADJUSTMENT can legitimately be negative; others positive
        signed = -qty if mtype in ("PICK", "ADJUSTMENT") and r.random() < 0.7 else qty
        stock_movement.append({
            "movement_id": f"MV{gen_date.strftime('%Y%m%d')}{i:07d}",
            "material_id": mat["material_id"],
            "warehouse_id": wh["warehouse_id"],
            "movement_type": mtype,
            "move_qty": signed,
            "movement_ts": _ts(gen_date, r),
            "updated_at": _ts(gen_date, r),
        })

    cycle_count = []
    for i in range(150):
        mat = ref.sample_material()
        wh = ref.sample_warehouse()
        system_qty = r.randint(0, 5000)
        counted = system_qty + r.randint(-50, 50)
        cycle_count.append({
            "count_id": f"CC{gen_date.strftime('%Y%m%d')}{i:05d}",
            "material_id": mat["material_id"],
            "warehouse_id": wh["warehouse_id"],
            "system_qty": system_qty,
            "counted_qty": counted,
            "variance": counted - system_qty,
            "count_date": gen_date.isoformat(),
        })

    return {"inventory": inventory, "warehouse_location": warehouse_location,
            "stock_movement": stock_movement, "cycle_count": cycle_count}
