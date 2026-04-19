"""
Apache Beam streaming pipeline: Redpanda (Kafka) → GCS Parquet (hourly partitions)

Runs on GCP Dataflow. For local testing use --runner DirectRunner.

Output layout:
  gs://{output_bucket}/llm-usage-events/
    year=YYYY/month=MM/day=DD/hour=HH/data-00000-of-00001.parquet

Usage (Dataflow):
  python consumer.py \\
    --project MY_PROJECT \\
    --runner DataflowRunner \\
    --bootstrap_servers 10.0.0.10:9092

Usage (local test):
  python consumer.py --project MY_PROJECT --runner DirectRunner \\
    --bootstrap_servers localhost:9092
"""

import argparse
import io
import json
import logging
from datetime import datetime, timezone

import apache_beam as beam
import pyarrow as pa
import pyarrow.parquet as pq
from apache_beam.io.fileio import FileSink, WriteToFiles, default_file_naming
from apache_beam.io.kafka import ReadFromKafka
from apache_beam.options.pipeline_options import (
    GoogleCloudOptions,
    PipelineOptions,
    SetupOptions,
    StandardOptions,
)

# Matches the 20-field schema produced by src/producer/generate-llm-events.py
SCHEMA = pa.schema([
    pa.field("event_id",               pa.string()),
    pa.field("timestamp_utc",          pa.timestamp('s', tz='UTC')),
    pa.field("provider",               pa.string()),
    pa.field("model",                  pa.string()),
    pa.field("prompt_tokens",          pa.int64()),
    pa.field("completion_tokens",      pa.int64()),
    pa.field("cached_tokens",          pa.int64()),
    pa.field("prompt_cost_usd",        pa.float64()),
    pa.field("completion_cost_usd",    pa.float64()),
    pa.field("total_cost_usd",         pa.float64()),
    pa.field("latency_ms",             pa.int64()),
    pa.field("time_to_first_token_ms", pa.int64()),
    pa.field("team",                   pa.string()),
    pa.field("feature",                pa.string()),
    pa.field("experiment_id",          pa.string()),
    pa.field("environment",            pa.string()),
    pa.field("status",                 pa.string()),
    pa.field("error_code",             pa.string()),
    pa.field("finish_reason",          pa.string()),
])


class ParseLLMEvent(beam.DoFn):
    """Deserializes Kafka (key, value) bytes → typed dict matching SCHEMA."""

    def process(self, element):
        _, value_bytes = element
        try:
            record = json.loads(value_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logging.warning("Dropped malformed Kafka message: %s", exc)
            return

        row = {}
        for field in SCHEMA:
            val = record.get(field.name)
            if val is None:
                val = "" if pa.types.is_string(field.type) else 0
            elif pa.types.is_integer(field.type):
                val = int(val)
            elif pa.types.is_floating(field.type):
                val = float(val)
            else:
                val = str(val)
            row[field.name] = val
        yield row


class ParquetSink(FileSink):
    """Buffers records in memory then flushes a snappy-compressed Parquet file."""

    def open(self, fh):
        self._fh = fh
        self._buf = io.BytesIO()
        self._writer = pq.ParquetWriter(self._buf, SCHEMA, compression="snappy")

    def write(self, record):
        table = pa.Table.from_pydict(
            {k: [v] for k, v in record.items()}, schema=SCHEMA
        )
        self._writer.write_table(table)

    def flush(self):
        self._writer.close()
        self._fh.write(self._buf.getvalue())


def hourly_destination(record):
    """Map a record to its Hive-style hourly partition path segment."""
    ts_str = record.get("timestamp_utc", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        ts = datetime.now(timezone.utc)
    return (
        f"year={ts.year:04d}/"
        f"month={ts.month:02d}/"
        f"day={ts.day:02d}/"
        f"hour={ts.hour:02d}"
    )


def run(argv=None):
    parser = argparse.ArgumentParser(description="LLM FinOps Kafka → GCS consumer")
    parser.add_argument(
        "--bootstrap_servers", default="10.0.0.10:9092",
        help="Kafka bootstrap servers (Terraform output: redpanda_bootstrap)",
    )
    parser.add_argument("--topic", default="llm.usage.events")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--region", default="us-west2")
    parser.add_argument(
        "--output_bucket", default=None,
        help="GCS bucket name (no gs://). Defaults to llm-finops-datalake-{project}",
    )
    parser.add_argument("--staging_location", default=None)
    parser.add_argument("--temp_location", default=None)
    parser.add_argument(
        "--window_size_secs", type=int, default=3600,
        help="Fixed window duration in seconds (default: 3600 = 1 hour)",
    )
    known_args, pipeline_args = parser.parse_known_args(argv)

    output_bucket    = known_args.output_bucket or f"llm-finops-datalake-{known_args.project}"
    staging_bucket   = f"llm-finops-datalake-staging-{known_args.project}"
    staging_location = known_args.staging_location or f"gs://{staging_bucket}/staging"
    temp_location    = known_args.temp_location    or f"gs://{staging_bucket}/temp"

    options = PipelineOptions(pipeline_args)
    options.view_as(SetupOptions).save_main_session = True
    options.view_as(StandardOptions).streaming = True

    gcp = options.view_as(GoogleCloudOptions)
    gcp.project          = known_args.project
    gcp.region           = known_args.region
    gcp.staging_location = staging_location
    gcp.temp_location    = temp_location

    output_path = f"gs://{output_bucket}/llm-usage-events"

    with beam.Pipeline(options=options) as p:
        (
            p
            | "ReadFromKafka" >> ReadFromKafka(
                consumer_config={
                    "bootstrap.servers": known_args.bootstrap_servers,
                    "group.id": "llm-finops-consumer",
                    "auto.offset.reset": "earliest",
                },
                topics=[known_args.topic],
            )
            | "ParseEvent" >> beam.ParDo(ParseLLMEvent())
            | "WindowInto" >> beam.WindowInto(
                beam.window.FixedWindows(known_args.window_size_secs)
            )
            | "WriteToGCS" >> WriteToFiles(
                path=output_path,
                destination=hourly_destination,
                sink=lambda _: ParquetSink(),
                file_naming=default_file_naming(prefix="data", suffix=".parquet"),
                max_writers_per_bundle=0,
            )
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
