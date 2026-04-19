# Static internal IP — Dataflow connects here every time, survives VM reboots
resource "google_compute_address" "redpanda_internal" {
  name         = "redpanda-internal-ip"
  subnetwork   = google_compute_subnetwork.subnet.id
  address_type = "INTERNAL"
  address      = var.redpanda_static_ip
  region       = var.region
}

resource "google_service_account" "redpanda_vm" {
  account_id   = "redpanda-vm"
  display_name = "Redpanda VM Service Account"
}

resource "google_compute_instance" "redpanda" {
  name         = "redpanda-vm"
  machine_type = var.redpanda_machine_type
  zone         = var.zone
  tags         = ["redpanda"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 50
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
    network_ip = google_compute_address.redpanda_internal.address
    # No access_config block = no external/public IP
  }

  service_account {
    email  = google_service_account.redpanda_vm.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    set -e
    apt-get update -y
    apt-get install -y docker.io
    systemctl enable --now docker

    docker run -d \
      --name redpanda \
      --restart always \
      --net host \
      docker.redpanda.com/redpandadata/redpanda:latest \
      redpanda start \
        --overprovisioned \
        --smp 1 \
        --memory 1G \
        --reserve-memory 0M \
        --node-id 0 \
        --check=false \
        --kafka-addr INTERNAL://0.0.0.0:9092,EXTERNAL://0.0.0.0:9093 \
        --advertise-kafka-addr INTERNAL://${var.redpanda_static_ip}:9092,EXTERNAL://localhost:9093
  EOT

  depends_on = [google_compute_router_nat.nat]
}
