# Billing budget with threshold alerts — the Free-Trial safety net (risk C1/C5).
# A budget does not cap spend; it *alerts*. The optional pubsub_topic enables the
# enterprise "auto-disable billing at 100%" Cloud Function pattern (documented,
# off by default for the portfolio).

resource "google_billing_budget" "this" {
  billing_account = var.billing_account
  display_name    = var.display_name

  budget_filter {
    projects = ["projects/${var.project_number}"]
  }

  amount {
    specified_amount {
      currency_code = var.currency
      units         = tostring(var.amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = var.thresholds
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  all_updates_rule {
    monitoring_notification_channels = var.notification_channels
    pubsub_topic                     = var.pubsub_topic
    disable_default_iam_recipients   = false
  }
}
