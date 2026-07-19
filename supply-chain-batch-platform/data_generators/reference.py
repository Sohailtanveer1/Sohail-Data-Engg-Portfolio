"""Shared, deterministic reference data used by every generator.

Seeded so runs are reproducible and business keys are stable across sources.
Build once with ``ReferenceData(seed=42)`` and pass it to each generator.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

CATEGORIES = ["RAW", "PACKAGING", "COMPONENT", "FINISHED", "MRO"]
UOMS = ["EA", "CS", "PLT", "KG", "LB"]
REGIONS = ["NORTHEAST", "SOUTHEAST", "MIDWEST", "SOUTHWEST", "WEST"]
SEGMENTS = ["ENTERPRISE", "MIDMARKET", "SMB"]
PAYMENT_TERMS = ["NET30", "NET45", "NET60", "COD"]
CARRIER_MODES = ["LTL", "FTL", "PARCEL", "INTERMODAL"]
CURRENCIES = ["USD", "CAD"]


@dataclass
class ReferenceData:
    seed: int = 42
    n_warehouses: int = 12
    n_materials: int = 400
    n_vendors: int = 60
    n_carriers: int = 8
    n_customers: int = 150
    n_reps: int = 20

    warehouses: list[dict] = field(default_factory=list)
    materials: list[dict] = field(default_factory=list)
    vendors: list[dict] = field(default_factory=list)
    carriers: list[dict] = field(default_factory=list)
    customers: list[dict] = field(default_factory=list)
    reps: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._build()

    # -- ids ---------------------------------------------------------------
    @staticmethod
    def material_id(i: int) -> str:
        # SAP-style leading-zero material numbers -> MUST stay strings.
        return f"{100000 + i:08d}"

    @staticmethod
    def warehouse_id(i: int) -> str:
        return f"WH{i:03d}"

    @staticmethod
    def vendor_id(i: int) -> str:
        return f"V{i:05d}"

    @staticmethod
    def customer_id(i: int) -> str:
        return f"C{i:06d}"

    @staticmethod
    def rep_id(i: int) -> str:
        return f"R{i:04d}"

    @staticmethod
    def carrier_scac(i: int) -> str:
        return f"SCAC{i:02d}"

    # -- build -------------------------------------------------------------
    def _build(self) -> None:
        r = self._rng
        self.warehouses = [
            {
                "warehouse_id": self.warehouse_id(i),
                "warehouse_name": f"DC {r.choice(REGIONS).title()} {i}",
                "region": r.choice(REGIONS),
                "state": r.choice(["NY", "TX", "IL", "CA", "GA", "OH", "AZ", "PA"]),
            }
            for i in range(1, self.n_warehouses + 1)
        ]
        self.materials = [
            {
                "material_id": self.material_id(i),
                "description": f"Material {i}",
                "category": r.choice(CATEGORIES),
                "uom": r.choice(UOMS),
                "hazmat": r.random() < 0.08,
                "std_cost": round(r.uniform(1.0, 500.0), 2),
            }
            for i in range(self.n_materials)
        ]
        self.vendors = [
            {
                "vendor_id": self.vendor_id(i),
                "vendor_name": f"Vendor {i} Inc",
                "country": r.choice(["US", "CA", "MX"]),
                "payment_terms": r.choice(PAYMENT_TERMS),
            }
            for i in range(1, self.n_vendors + 1)
        ]
        self.carriers = [
            {
                "carrier_scac": self.carrier_scac(i),
                "carrier_name": f"Carrier {i} Logistics",
                "mode": r.choice(CARRIER_MODES),
            }
            for i in range(1, self.n_carriers + 1)
        ]
        self.reps = [
            {
                "rep_id": self.rep_id(i),
                "rep_name": f"Rep {i}",
                "region": r.choice(REGIONS),
            }
            for i in range(1, self.n_reps + 1)
        ]
        self.customers = [
            {
                "customer_id": self.customer_id(i),
                "customer_name": f"Customer {i} LLC",
                "segment": r.choice(SEGMENTS),
                "credit_limit": r.choice([50_000, 100_000, 250_000, 500_000, 1_000_000]),
                "rep_id": self.rep_id(r.randint(1, self.n_reps)),
            }
            for i in range(1, self.n_customers + 1)
        ]

    # -- convenience samplers ---------------------------------------------
    def sample_material(self) -> dict:
        return self._rng.choice(self.materials)

    def sample_warehouse(self) -> dict:
        return self._rng.choice(self.warehouses)

    def sample_vendor(self) -> dict:
        return self._rng.choice(self.vendors)

    def sample_carrier(self) -> dict:
        return self._rng.choice(self.carriers)

    def sample_customer(self) -> dict:
        return self._rng.choice(self.customers)

    @property
    def rng(self) -> random.Random:
        return self._rng
