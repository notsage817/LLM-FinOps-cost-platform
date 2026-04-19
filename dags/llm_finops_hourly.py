"""
Hourly ELT pipeline: GCS Parquet → BigQuery raw → dbt staging → dbt mart

Schedule: top of every hour, processes the previous hour's Hive partition.

Task graph:
  check_gcs_partition → bq_load_raw → dbt_run_staging → dbt_run_mart → dbt_test_mart
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectsWithPrefixExistenceSensor

from utils.gcs_bq_loader import bq_load_job_config, partition_gcs_sensor_prefix

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
BUCKET = os.environ["GCS_DATALAKE_BUCKET"]
RAW_DATASET = os.environ.get("BQ_RAW_DATASET", "llm_finops_raw")
DBT_DIR = "/opt/airflow/dbt"

default_args = {
    "owner": "llm-finops",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _check_partition_prefix(**context):
    """Pushes the GCS sensor prefix into XCom so the sensor can use it."""
    dt = context["data_interval_start"]
    return partition_gcs_sensor_prefix(BUCKET, dt)


def _run_bq_load(**context):
    """Submits a BigQuery load job for the previous hour's Parquet partition."""
    from google.cloud import bigquery

    dt = context["data_interval_start"]
    config = bq_load_job_config(PROJECT_ID, RAW_DATASET, BUCKET, dt)
    client = bigquery.Client(project=PROJECT_ID)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        hive_partitioning=bigquery.HivePartitioningOptions(
            mode="AUTO",
            source_uri_prefix=f"gs://{BUCKET}/llm-usage-events/",
        ),
    )

    partition_date = dt.strftime("%Y%m%d")
    destination = f"{PROJECT_ID}.{RAW_DATASET}.llm_usage_events${partition_date}"
    source_uri = config["configuration"]["load"]["sourceUris"][0]

    load_job = client.load_table_from_uri(source_uri, destination, job_config=job_config)
    load_job.result()  # blocks until complete, raises on failure

    context["ti"].log.info(
        "Loaded %d rows into %s", load_job.output_rows, destination
    )


with DAG(
    dag_id="llm_finops_hourly_pipeline",
    description="GCS Parquet → BigQuery → dbt (hourly)",
    schedule_interval="0 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["llm-finops", "elt"],
) as dag:

    check_gcs_partition = GCSObjectsWithPrefixExistenceSensor(
        task_id="check_gcs_partition_exists",
        bucket=BUCKET,
        # Jinja-rendered prefix: year=YYYY/month=MM/day=DD/hour=HH/
        prefix=(
            "llm-usage-events/"
            "year={{ data_interval_start.year }}/"
            "month={{ '%02d' % data_interval_start.month }}/"
            "day={{ '%02d' % data_interval_start.day }}/"
            "hour={{ '%02d' % data_interval_start.hour }}/"
        ),
        google_cloud_conn_id="google_cloud_default",
        timeout=1800,
        poke_interval=120,
        mode="reschedule",
    )

    bq_load_raw = PythonOperator(
        task_id="bq_load_raw_parquet",
        python_callable=_run_bq_load,
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=(
            f"cd {DBT_DIR} && "
            "dbt run --select staging "
            "--vars '{\"run_hour\": \"{{ data_interval_start }}\"}'"
        ),
    )

    dbt_run_mart = BashOperator(
        task_id="dbt_run_mart",
        bash_command=(
            f"cd {DBT_DIR} && "
            "dbt run --select mart "
            "--vars '{\"run_hour\": \"{{ data_interval_start }}\"}'"
        ),
    )

    dbt_test_mart = BashOperator(
        task_id="dbt_test_mart",
        bash_command=f"cd {DBT_DIR} && dbt test --select mart",
    )

    check_gcs_partition >> bq_load_raw >> dbt_run_staging >> dbt_run_mart >> dbt_test_mart
