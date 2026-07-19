# Business Context

## The problem

A mid-size supply chain operator (the scenario this project models:
warehouses, carriers, suppliers, a returns process — deliberately close to
a real US supply chain business) runs its Order, Inventory, Shipment,
Return, and Supplier systems as largely disconnected applications. Data
reaches a warehouse or reporting layer via nightly batch ETL. Three
concrete failure modes result:

1. **Overselling / stockouts.** Inventory decrements from one warehouse
   system reach the central reporting layer up to 24 hours late. A
   storefront or B2B ordering system can sell against stock that's already
   gone, generating a cancellation and a frustrated customer.
2. **Missed shipment SLAs discovered too late.** A shipment delay is only
   visible to ops the next business day, by which point the customer
   already knows before the company does.
3. **Slow supplier accountability.** A supplier's pattern of late PO
   acknowledgments is only visible in a quarterly report, long after it
   would have been useful to shift volume to a more reliable supplier.

## The platform's value proposition

Convert "discovered next business day in a batch report" into "alertable
within seconds of the event occurring," for the handful of metrics that
actually change an operational decision:
- Is a SKU about to stock out at a specific warehouse? (`inventory_snapshot`)
- Is an order at risk of missing its fulfillment SLA? (`order_fulfillment_sla`)
- Is a specific carrier's on-time rate degrading? (`shipment_performance`)
- Is a specific supplier's reliability degrading? (`supplier_scorecard`)
- Is a specific warehouse seeing a spike in a specific return reason (a
  quality signal)? (`return_rate_by_reason`)

Every Gold view (see [docs/api/README.md](../api/README.md)) exists
because it answers one of these five questions directly — not because it
was easy to compute from Silver.

## Stakeholders

| Stakeholder | Uses | Primary concern |
|---|---|---|
| Warehouse operations | `order_fulfillment_sla`, `inventory_snapshot` | Are we going to miss SLAs or stock out today? |
| Logistics / carrier management | `shipment_performance` | Which carriers are actually reliable, with data, not anecdote? |
| Procurement | `supplier_scorecard` | Which suppliers should get more/less volume next quarter? |
| Quality / returns team | `return_rate_by_reason` | Is a quality issue emerging at a specific warehouse? |
| Data platform team (you) | Everything upstream of Gold | Is the pipeline healthy, current, and trustworthy? |

## Why real-time, not just "faster batch"

A batch job that runs every 15 minutes instead of nightly captures most of
the freshness benefit at a fraction of this platform's complexity — worth
stating plainly, since "just run batch more often" is a fair question an
interviewer or a skeptical stakeholder should ask.

The honest answer: this project intentionally builds the real-time
architecture because (a) it's the more valuable skill set to demonstrate,
and (b) at genuine production scale, streaming ingestion avoids the
resource-contention problem of a batch job re-scanning a growing source
table every 15 minutes — a problem that gets worse, not better, as volume
grows, where streaming's cost scales with actual event volume instead. For
a business at QXO's scale specifically, the stockout/SLA-miss cost of even
a 15-minute batch delay is real money, which is the concrete business case
that justifies the added operational complexity here.
