resource "google_bigquery_dataset" "raw" {
  dataset_id  = "llm_finops_raw"
  location    = var.region
  description = "Raw Parquet loads from GCS — append-only, immutable"

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset" "staging" {
  dataset_id  = "llm_finops_staging"
  location    = var.region
  description = "dbt staging layer — cleaned types, views only"

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset" "mart" {
  dataset_id  = "llm_finops_mart"
  location    = var.region
  description = "dbt mart layer — aggregated, dashboard-ready incremental tables"

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_table" "raw_llm_usage_events" {
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = "llm_usage_events"
  deletion_protection = false

  time_partitioning {
    type = "DAY"
  }

  clustering = ["team", "model", "provider"]

  schema = jsonencode([
    { name = "event_id",               type = "STRING",  mode = "NULLABLE" },
    { name = "timestamp_utc",          type = "TIMESTAMP",  mode = "NULLABLE" },
    { name = "provider",               type = "STRING",  mode = "NULLABLE" },
    { name = "model",                  type = "STRING",  mode = "NULLABLE" },
    { name = "prompt_tokens",          type = "INTEGER", mode = "NULLABLE" },
    { name = "completion_tokens",      type = "INTEGER", mode = "NULLABLE" },
    { name = "cached_tokens",          type = "INTEGER", mode = "NULLABLE" },
    { name = "prompt_cost_usd",        type = "FLOAT",   mode = "NULLABLE" },
    { name = "completion_cost_usd",    type = "FLOAT",   mode = "NULLABLE" },
    { name = "total_cost_usd",         type = "FLOAT",   mode = "NULLABLE" },
    { name = "latency_ms",             type = "INTEGER", mode = "NULLABLE" },
    { name = "time_to_first_token_ms", type = "INTEGER", mode = "NULLABLE" },
    { name = "team",                   type = "STRING",  mode = "NULLABLE" },
    { name = "feature",                type = "STRING",  mode = "NULLABLE" },
    { name = "experiment_id",          type = "STRING",  mode = "NULLABLE" },
    { name = "environment",            type = "STRING",  mode = "NULLABLE" },
    { name = "status",                 type = "STRING",  mode = "NULLABLE" },
    { name = "error_code",             type = "STRING",  mode = "NULLABLE" },
    { name = "finish_reason",          type = "STRING",  mode = "NULLABLE" }
  ])
}
