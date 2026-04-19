resource "google_compute_network" "vpc" {
  name                    = var.vpc_name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.vpc_name}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id
}

# Kafka port — only reachable from within the subnet
resource "google_compute_firewall" "allow_kafka" {
  name    = "allow-kafka-internal"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["9092"]
  }

  source_ranges = [var.subnet_cidr]
  target_tags   = ["redpanda"]
}

# SSH via IAP — no port 22 open to the internet
resource "google_compute_firewall" "allow_iap_ssh" {
  name    = "allow-iap-ssh"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["redpanda"]
}

# Dataflow worker-to-worker coordination
resource "google_compute_firewall" "allow_dataflow_internal" {
  name    = "allow-dataflow-internal"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["12345-12346"]
  }

  source_ranges = [var.subnet_cidr]
}

resource "google_compute_firewall" "allow_iap_kafka" {
  name    = "allow-iap-kafka-external"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["9093"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["redpanda"]
}


# Cloud Router + NAT — outbound internet for VM (Docker image pull), no public IP needed
resource "google_compute_router" "router" {
  name    = "${var.vpc_name}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.vpc_name}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}