"""Salesforce CRM emulator -> JSON (served by the mock REST API, hourly incremental).

Entities: customer, account, sales_rep, credit. Each record carries a
``SystemModstamp`` so the mock API and the extractor can do watermark-based
incremental pulls. ``IsDeleted`` models soft deletes.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from data_generators.reference import ReferenceData

SOURCE = "salesforce"
ENTITIES = ["customer", "account", "sales_rep", "credit"]


def _modstamp(gen_date: date, rng) -> str:
    """A UTC ISO timestamp at a random second within the generation day."""
    midnight = datetime.combine(gen_date, time.min, tzinfo=timezone.utc)
    return (midnight + timedelta(seconds=rng.randint(0, 86_399))).isoformat()


def generate(ref: ReferenceData, gen_date: date, *, changed_fraction: float = 0.3,
             dirty_fraction: float = 0.02) -> dict[str, list[dict]]:
    r = ref.rng
    # Only a fraction of customers "change" on a given day (incremental feed).
    changed = r.sample(ref.customers, k=max(1, int(len(ref.customers) * changed_fraction)))

    customer = []
    credit = []
    for c in changed:
        credit_limit = c["credit_limit"]
        if r.random() < dirty_fraction:
            credit_limit = -abs(credit_limit)  # invalid negative credit
        customer.append({
            "Id": c["customer_id"],
            "Name": c["customer_name"],
            "Segment__c": c["segment"],
            "OwnerRepId__c": c["rep_id"],
            "IsDeleted": r.random() < 0.02,
            "SystemModstamp": _modstamp(gen_date, r),
        })
        credit.append({
            "Id": f"CR{c['customer_id']}",
            "CustomerId__c": c["customer_id"],
            "CreditLimit__c": credit_limit,
            "Currency__c": "USD",
            "RiskRating__c": r.choice(["LOW", "MEDIUM", "HIGH"]),
            "SystemModstamp": _modstamp(gen_date, r),
        })

    account = [
        {
            "Id": f"A{c['customer_id']}",
            "CustomerId__c": c["customer_id"],
            "AccountType": r.choice(["BILL_TO", "SHIP_TO", "SOLD_TO"]),
            "SystemModstamp": _modstamp(gen_date, r),
        }
        for c in changed
    ]

    sales_rep = [
        {
            "Id": rep["rep_id"],
            "Name": rep["rep_name"],
            "Region__c": rep["region"],
            "SystemModstamp": _modstamp(gen_date, r),
        }
        for rep in ref.reps
    ]

    return {"customer": customer, "account": account, "sales_rep": sales_rep,
            "credit": credit}
