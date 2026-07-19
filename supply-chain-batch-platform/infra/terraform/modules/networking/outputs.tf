output "network_id" {
  description = "Self-link/id of the VPC."
  value       = google_compute_network.vpc.id
}

output "network_name" {
  value = google_compute_network.vpc.name
}

output "subnet_id" {
  description = "Self-link/id of the private subnet."
  value       = google_compute_subnetwork.private.id
}

output "subnet_name" {
  value = google_compute_subnetwork.private.name
}

output "subnet_self_link" {
  value = google_compute_subnetwork.private.self_link
}
