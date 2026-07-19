# ADR-0009 — Networking topology

**Status:** Proposed · **Date:** 2026-07-19

## Context
Dataproc (Serverless and clusters) and Composer need a network. Requirements:
private-by-default (no public IPs on workers), reachable Google APIs
(GCS/BigQuery), controlled egress for package installs, and least-exposure
firewalling — all cheap on the Free Trial.

## Options
1. **Default VPC.** Zero effort, but auto-created broad firewall rules and public
   IPs — not a defensible production story.
2. **Custom VPC, private subnet, PGA + Cloud NAT, deny-by-default firewall.** ✅
   The standard secure pattern.
3. **Shared VPC / PSC / Cloud Armor.** Enterprise-grade, overkill and costly for a
   portfolio.

## Decision
**Option 2.** A **custom VPC** with a single **private subnet** per region.
Workers have **no external IPs**. **Private Google Access (PGA)** lets them reach
GCS/BigQuery over Google's network. **Cloud NAT** (via Cloud Router) provides
controlled outbound internet (e.g. pip/Iceberg jars) without inbound exposure.
Firewall is **deny-by-default**, allowing only internal subnet traffic and the
specific ports Dataproc/Composer require.

## Consequences
- ➕ No public attack surface on compute; a clean security narrative.
- ➕ PGA keeps GCS/BigQuery traffic on Google's backbone (no NAT cost for those).
- ➕ NAT only matters while clusters run — negligible cost.
- ➖ Slightly more Terraform; NAT/router are extra resources to destroy.
- ➖ Must open the correct internal ports or Dataproc/Composer fail to start.

## Enterprise vs Portfolio
- **Enterprise:** Shared VPC across projects, Private Service Connect, Cloud Armor,
  hierarchical firewall policies, VPC-SC perimeter.
- **Portfolio:** custom VPC + private subnet + PGA + NAT + minimal firewall —
  demonstrates the same principles at zero/low cost.
