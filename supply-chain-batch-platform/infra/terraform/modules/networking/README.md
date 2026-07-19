# Module: networking

Custom VPC + private subnet + Private Google Access + Cloud NAT + deny-by-default
firewall (ADR-0009). Compute (Dataproc/Composer) runs here with **no external IPs**.

**Inputs:** `project_id`, `region`, `name_prefix`, `subnet_cidr`,
`secondary_ranges` (Composer/GKE), `enable_iap_ssh`.
**Outputs:** `network_id/name`, `subnet_id/name/self_link`.

**Why each piece:**
- *Custom VPC (no auto subnets)* — avoids the default VPC's broad firewall rules.
- *Private Google Access* — GCS/BigQuery reachable without public IPs (no NAT cost
  for Google APIs).
- *Cloud NAT* — outbound-only internet (pip, Iceberg jars); no inbound exposure.
- *Firewall* — allow intra-subnet only; optional IAP-SSH; explicit deny of all
  other ingress on top of the implicit deny.
