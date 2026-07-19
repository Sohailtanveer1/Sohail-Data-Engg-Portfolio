# ADR-0003 — Orchestration: Cloud Composer (managed Airflow)

**Status:** Proposed · **Date:** 2026-07-19

## Context
The platform needs orchestration (scheduling, sensors, retries, SLAs,
dependencies). We want the portfolio to demonstrate **Cloud Composer** — the
managed-Airflow service a Fortune 500 team actually runs — end to end, not just a
local simulation. The tension is cost: Composer has **no free tier and no
scale-to-zero** (a small env runs GKE + Cloud SQL 24/7 at ~$10–15/day).

## Options
1. **Local Airflow only.** Free, fast, but never shows managed Composer.
2. **Local default + 1-day guarded Composer demo.** Cheap, but Composer is only
   briefly exercised.
3. **Full Cloud Composer environment.** ✅ Real managed Airflow running the daily
   batch DAGs on GCP — the most realistic, most demonstrable, and most
   interview-credible option. Accepts a meaningful (but budgeted) share of the
   $300 trial credit.

## Decision
**Option 3 — a real Cloud Composer 2 environment** (smallest viable size) is the
primary orchestrator, provisioned by Terraform. DAGs are still authored to be
**environment-portable** (no Composer-only assumptions) and are runnable on local
Airflow for fast dev iteration, but the platform's orchestration story is
Composer. Composer is created in **Phase 8** and kept only for the phases that
need it (8–11).

## Cost management (mandatory, because this is the biggest spend)
- Provisioned via Terraform behind `enable_composer` (set **true** deliberately
  in Phase 8), so it is always visible in state and destroyable.
- **Smallest environment** (Composer 2, minimal workers, small scheduler).
- **`terraform destroy` the Composer module during any multi-day break**, then
  re-`apply` when resuming — the DAGs live in git/GCS and redeploy in minutes.
- $50 **billing budget** with 50/90/100% alerts as a backstop.
- Budgeted at roughly **$10–15/day while it exists**; the plan keeps its
  lifetime to the days actually spent on Phases 8–11 (target: well under 2 weeks
  of runtime → ~$100–200 worst case, less if torn down between sessions).

## Consequences
- ➕ Genuine managed-Airflow experience: Composer UI, GCS-synced DAGs, Cloud
    Logging integration, KubernetesExecutor behavior, IAM — all real.
- ➕ Strongest interview story ("I ran it on Composer, here's the environment").
- ➖ **Largest single cost in the project** — must be actively managed
    (destroy between breaks); this is the #1 thing to watch on the trial.
- ➖ Slower iteration than local Airflow → we still develop DAGs locally first.

## Enterprise vs Portfolio
- **Enterprise:** multiple HA Composer environments per tier, autoscaling
  workers, CI-deployed DAGs, private-IP Composer.
- **Portfolio:** one small Composer 2 env, created in Phase 8, torn down between
  sessions to control cost; DAGs developed locally, deployed to Composer's GCS
  bucket.
