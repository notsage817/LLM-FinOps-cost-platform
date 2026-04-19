"""Builds GCS URIs and BigQuery load job configs for hourly Parquet partitions."""

import os
from datetime import datetime


def partition_gcs_uri(bucket: str, dt: datetime) -> str:
    """Returns the GCS prefix for a given hour's Hive partition."""
    return (
        f"gs://{bucket}/llm-usage-events/"
        f"year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/hour={dt.hour:02d}/*.parquet"
    )


def partition_gcs_sensor_prefix(bucket: str, dt: datetime) -> str:
    """Returns the GCS prefix for the GCSObjectsWithPrefixExistenceSensor."""
    return (
        f"llm-usage-events/"
        f"year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/hour={dt.hour:02d}/"
    )


def bq_load_job_config(project: str, raw_dataset: str, bucket: str, dt: datetime) -> dict:
    """
    Returns a BigQueryInsertJobOperator configuration dict.

    Uses WRITE_TRUNCATE targeted at the day partition ($YYYYMMDD) so that
    retrying the same hour is idempotent — it overwrites that day's partition
    rather than appending duplicates.
    """
    partition_date = dt.strftime("%Y%m%d")
    destination_table = (
        f"{project}:{raw_dataset}.llm_usage_events${partition_date}"
    )

    return {
        "configuration": {
            "load": {
                "sourceUris": [partition_gcs_uri(bucket, dt)],
                "destinationTable": {
                    "projectId": project,
                    "datasetId": raw_dataset,
                    "tableId": f"llm_usage_events${partition_date}",
                },
                "sourceFormat": "PARQUET",
                "writeDisposition": "WRITE_TRUNCATE",
                "createDisposition": "CREATE_IF_NEEDED",
                "hivePartitioningOptions": {
                    "mode": "AUTO",
                    "sourceUriPrefix": f"gs://{bucket}/llm-usage-events/",
                },
            }
        }
    }
