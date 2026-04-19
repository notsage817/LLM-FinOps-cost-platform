output "redpanda_internal_ip" {
  value       = google_compute_address.redpanda_internal.address
  description = "Internal IP of the Redpanda VM"
}

output "redpanda_bootstrap" {
  value       = "${google_compute_address.redpanda_internal.address}:9092"
  description = "Kafka bootstrap string — pass to Dataflow job"
}

output "datalake_bucket" {
  value       = google_storage_bucket.datalake.name
  description = "GCS data lake bucket name"
}

output "staging_bucket" {
  value       = google_storage_bucket.dataflow_staging.name
  description = "GCS Dataflow staging bucket name"
}

output "dataflow_sa_email" {
  value       = google_service_account.dataflow_worker.email
  description = "Dataflow worker service account email"
}

output "subnet_self_link" {
  value       = google_compute_subnetwork.subnet.self_link
  description = "Subnet self-link for Dataflow --subnetwork flag"
}
