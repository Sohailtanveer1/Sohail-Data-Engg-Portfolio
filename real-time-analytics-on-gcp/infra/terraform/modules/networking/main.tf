# VPC + subnet + firewall rules + NAT for Dataflow workers to run without
# public IPs. This is the network Dataflow, and only Dataflow, runs in —
# it's deliberately not shared with any other workload so a firewall
# mistake here has a blast radius of exactly this pipeline.

resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = "supplychain-${var.environment}-vpc"
  auto_create_subnetworks = false
  # Custom-mode VPCs create NO implicit firewall rules (unlike default-mode),
  # which is why every rule below is explicit — nothing is allowed by accident.
}

resource "google_compute_subnetwork" "subnet" {
  project       = var.project_id
  name          = "supplychain-${var.environment}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id

  # Dataflow workers run with --no_use_public_ips (see dataflow module) and
  # still need to reach BigQuery/Pub/Sub/GCS APIs — Private Google Access is
  # what makes that possible without a public IP on every worker.
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata              = "INCLUDE_ALL_METADATA"
  }
}

# Dataflow workers in the same job talk to each other directly (shuffle,
# side inputs) on ephemeral ports — without this rule a streaming job
# hangs at startup with opaque "workers failed to start" errors.
resource "google_compute_firewall" "allow_dataflow_internal" {
  project = var.project_id
  name    = "supplychain-${var.environment}-allow-dataflow-internal"
  network = google_compute_network.vpc.id

  direction = "INGRESS"
  source_ranges = [var.subnet_cidr]
  target_tags   = ["dataflow-worker"]

  allow {
    protocol = "tcp"
    ports    = ["12345-12346"]
  }
}

# SSH access for debugging goes through Identity-Aware Proxy, never a public
# IP + open port 22. 35.235.240.0/20 is Google's fixed IAP forwarding range.
resource "google_compute_firewall" "allow_iap_ssh" {
  project = var.project_id
  name    = "supplychain-${var.environment}-allow-iap-ssh"
  network = google_compute_network.vpc.id

  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["dataflow-worker"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_router" "router" {
  project = var.project_id
  name    = "supplychain-${var.environment}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

# Workers have no public IP (see dataflow module's ipConfiguration), so
# outbound internet (e.g. calling a carrier tracking API during enrichment)
# goes through NAT rather than each worker getting its own public address.
resource "google_compute_router_nat" "nat" {
  project                            = var.project_id
  name                               = "supplychain-${var.environment}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
