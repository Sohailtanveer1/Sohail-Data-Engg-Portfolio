output "emails" {
  description = "Map of SA short name -> email."
  value       = { for k, sa in google_service_account.this : k => sa.email }
}

output "members" {
  description = "Map of SA short name -> IAM member string (serviceAccount:<email>)."
  value       = { for k, sa in google_service_account.this : k => "serviceAccount:${sa.email}" }
}

output "ids" {
  description = "Map of SA short name -> fully-qualified id."
  value       = { for k, sa in google_service_account.this : k => sa.id }
}
