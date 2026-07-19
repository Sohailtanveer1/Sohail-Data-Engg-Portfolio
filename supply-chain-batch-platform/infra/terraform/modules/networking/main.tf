# Custom VPC with a single private subnet, Private Google Access, Cloud NAT for
# controlled egress, and a deny-by-default firewall (ADR-0009). Dataproc and
# Composer workers run here with NO external IPs.

resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false # no default broad subnets/firewall
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "private" {
  project       = var.project_id
  name          = "${var.name_prefix}-subnet-${var.region}"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id

  # Reach GCS/BigQuery over Google's backbone without external IPs.
  private_ip_google_access = true

  # Secondary ranges for Composer 2 / GKE (pods, services).
  dynamic "secondary_ip_range" {
    for_each = var.secondary_ranges
    content {
      range_name    = secondary_ip_range.value.range_name
      ip_cidr_range = secondary_ip_range.value.ip_cidr_range
    }
  }

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Cloud Router + NAT: outbound-only internet (pip/Iceberg jars) with no inbound.
resource "google_compute_router" "router" {
  project = var.project_id
  name    = "${var.name_prefix}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  project                            = var.project_id
  name                               = "${var.name_prefix}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# --- Firewall: deny-by-default (implicit) + explicit minimal allows ---

# Allow all traffic *within* the subnet (Dataproc/Composer node-to-node).
resource "google_compute_firewall" "allow_internal" {
  project = var.project_id
  name    = "${var.name_prefix}-allow-internal"
  network = google_compute_network.vpc.id

  direction     = "INGRESS"
  source_ranges = [var.subnet_cidr]

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }
}

# Allow SSH only from Google's IAP range (no public SSH) for occasional debugging.
resource "google_compute_firewall" "allow_iap_ssh" {
  count   = var.enable_iap_ssh ? 1 : 0
  project = var.project_id
  name    = "${var.name_prefix}-allow-iap-ssh"
  network = google_compute_network.vpc.id

  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"] # IAP TCP forwarding range

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# Explicit deny of all other ingress (belt-and-suspenders over the implicit deny).
resource "google_compute_firewall" "deny_all_ingress" {
  project  = var.project_id
  name     = "${var.name_prefix}-deny-all-ingress"
  network  = google_compute_network.vpc.id
  priority = 65534

  direction     = "INGRESS"
  source_ranges = ["0.0.0.0/0"]

  deny {
    protocol = "all"
  }
}
