output "budget_id" {
  description = "The created billing budget id."
  value       = google_billing_budget.this.id
}
