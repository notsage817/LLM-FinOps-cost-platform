terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0"}
    local ={ source = "hashicorp/local", version = "~> 2.4"}
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "dataflow.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "bigquery.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

