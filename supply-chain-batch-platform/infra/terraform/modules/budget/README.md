# Module: budget

A billing budget with threshold alerts — the Free-Trial safety net (risks C1/C5).
A budget **alerts**, it does not cap spend.

**Inputs:** `billing_account`, `project_number`, `amount` (default 50),
`currency`, `thresholds` (default 0.5/0.9/1.0), `notification_channels`,
`pubsub_topic`.
**Outputs:** `budget_id`.

With no channels/topic, default IAM recipients (billing admins) receive email at
each threshold. Set `pubsub_topic` to enable the enterprise pattern of a Cloud
Function that disables billing at 100% (documented; off by default).

> Requires the `cloudbilling.googleapis.com` API and that the Terraform identity
> has `roles/billing.admin` (or budget-specific) on the billing account.
