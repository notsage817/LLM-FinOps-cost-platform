# Redpanda VM — logs and metrics only, nothing else
resource "google_project_iam_member" "redpanda_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.redpanda_vm.email}"
}

resource "google_project_iam_member" "redpanda_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.redpanda_vm.email}"
}

# Dataflow worker SA
resource "google_service_account" "dataflow_worker" {
  account_id   = "dataflow-worker"
  display_name = "Dataflow Worker — LLM FinOps"
}

resource "google_project_iam_member" "dataflow_worker_role" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow_worker.email}"
}

# Required by Dataflow — workers must be able to impersonate their own SA
resource "google_project_iam_member" "dataflow_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.dataflow_worker.email}"
}

resource "google_storage_bucket_iam_member" "datalake_access" {
  bucket = google_storage_bucket.datalake.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow_worker.email}"
}

resource "google_storage_bucket_iam_member" "staging_access" {
  bucket = google_storage_bucket.dataflow_staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow_worker.email}"
}

# SA key written locally — used to submit Dataflow jobs from your machine
resource "google_service_account_key" "dataflow_worker" {
  service_account_id = google_service_account.dataflow_worker.name
}

resource "local_sensitive_file" "dataflow_sa_key" {
  content  = base64decode(google_service_account_key.dataflow_worker.private_key)
  filename = "${path.module}/../../secrets/dataflow-sa-key.json"
}

# Airflow worker SA — orchestrates BQ load jobs and dbt runs
resource "google_service_account" "airflow_worker" {
  account_id   = "airflow-worker"
  display_name = "Airflow Worker — LLM FinOps"
}

resource "google_bigquery_dataset_iam_member" "airflow_raw_editor" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.airflow_worker.email}"
}

resource "google_bigquery_dataset_iam_member" "airflow_staging_editor" {
  dataset_id = google_bigquery_dataset.staging.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.airflow_worker.email}"
}

resource "google_bigquery_dataset_iam_member" "airflow_mart_editor" {
  dataset_id = google_bigquery_dataset.mart.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.airflow_worker.email}"
}

resource "google_project_iam_member" "airflow_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.airflow_worker.email}"
}

resource "google_storage_bucket_iam_member" "airflow_datalake_viewer" {
  bucket = google_storage_bucket.datalake.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.airflow_worker.email}"
}

resource "google_service_account_key" "airflow_worker" {
  service_account_id = google_service_account.airflow_worker.name
}

resource "local_sensitive_file" "airflow_sa_key" {
  content  = base64decode(google_service_account_key.airflow_worker.private_key)
  filename = "${path.module}/../../secrets/airflow-sa-key.json"
}
