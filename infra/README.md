## 📊 LLM FinOps Platform - Infrastructure as Code

The infrastructure is built with the Terraform (IaC) to provision a secure, scalable, and highly optimized Data Engineering platform on Google Cloud (GCP). The platform is specifically designed to ingest, stream, store, and transform Large Language Model (LLM) usage events (tokens, latency, costs) for further usage.

### 🚀 Overview

The infrastructure creates an end-to-end data pipeline foundation utilizing a **Medallion Data Architecture** (Raw, Staging, Mart). It is built with a security-first approach, as no resources are exposed to the public internet
and all access is mediated through Google's Identity-Aware Proxy (IAP) and strict least-privilege IAM roles.

#### Key Technologies Used:
* **Infrastructure:** Terraform (Google Provider)
* **Compute / Streaming:** GCP Compute Engine (Debian 11), Docker, Redpanda (Kafka-compatible)
* **Networking:** VPC, Cloud Router, Cloud NAT, IAP Firewalls
* **Data Lake:** Google Cloud Storage (GCS)
* **Data Warehouse:** Google BigQuery
* **Orchestration / Processing (Target):** Apache Airflow, dbt, Apache Beam (Dataflow)



### 🧩 Component Breakdown

#### 1. Networking & Security (`network.tf`)
* **Custom VPC & Subnet:** Isolated network (`10.0.0.0/24`) with auto-creation disabled.
* **Cloud NAT:** Allows the private Redpanda VM to reach the internet to download Docker images and updates without requiring a risky public IP address.
* **IAP Firewalls:** SSH (Port `22`) and external Kafka access (Port `9093`) are only accessible via Google's Identity-Aware Proxy IPs (`35.235.240.0/20`).

#### 2. Streaming Ingestion (`redpanda.tf`)
* **Compute Instance:** A Debian 11 VM running Docker via a metadata startup script.
* **Redpanda Container:** Bootstraps a lightweight, Kafka-compatible broker.
* **Static Internal IP:** Fixed to `10.0.0.10` so downstream Dataflow consumers can reliably connect, even if the VM reboots.

#### 3. Data Lake Storage (`storage.tf`)
* **Datalake Bucket:** Stores immutable, append-only raw data (e.g., Parquet/JSON). Includes a lifecycle policy to move data older than 365 days to `NEARLINE` storage to save costs.
* **Staging Bucket:** Used by Dataflow/Beam to store temporary worker files and artifacts.

#### 4. BigQuery Data Warehouse (`bigquery.tf`)
Implements the Medallion Architecture:
* **Raw Dataset:** Contains the `llm_usage_events` table.
* **FinOps Optimizations:** The table utilizes **Event-Time Partitioning** on `timestamp_utc` (to guarantee accurate daily billing reporting regardless of ingestion delays) and **Clustering** on `team, model, provider` (to minimize query costs for dashboards).
* **Staging & Mart Datasets:** Pre-provisioned for dbt transformations.

#### 5. Identity & Access Management (`iam.tf`)
Strict Service Accounts (SAs) with decoupled responsibilities:
* **Redpanda SA:** Only allowed to write logs and metrics.
* **Dataflow SA:** Restricted to GCS Object Admin to write to the datalake.
* **Airflow SA:** Granted GCS Viewer and BigQuery Data Editor to orchestrate loads and dbt runs. Local `.json` keys are exported automatically for local development.

---

### 🛠️ Deployment Guide

#### Prerequisites
1. A Google Cloud Platform (GCP) Project.
2. The Google Cloud CLI (`gcloud`) installed.
3. Terraform installed (v1.5+).

#### Step 1: Authenticate
You need to authenticate both your personal user account and your Application Default Credentials (ADC) for Terraform:
```bash
# Log in to the CLI and set your target project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Generate the credential file for Terraform to use
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

#### Step 2: Configure Variables
Copy the example variables file and add your specific project ID.
```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```
Edit `terraform.tfvars`:
```hcl
project_id         = "your-actual-gcp-project-id"
region             = "us-west1"
redpanda_static_ip = "10.0.0.10"
```

#### Step 3: Initialize & Deploy
Terraform requires a local `secrets` directory to store the generated service account keys.
```bash
# Create the secrets directory in the root of the project
mkdir -p ../../secrets

# Initialize Terraform providers
terraform init

# Review the planned infrastructure changes
terraform plan

# Deploy the infrastructure
terraform apply
```
*Type `yes` when prompted.*

#### Step 4: Verify Deployment
Once complete, Terraform will output your resource coordinates. You can verify the buckets using the CLI:
```bash
gcloud storage ls
```

---

### ⚖️ Architecture Evaluation (Pros & Cons)

#### ✅ Pros
* **Highly Secure:** Zero public attack surface. Access to the VM and Kafka broker is tightly controlled via IAP.
* **FinOps Ready:** The BigQuery schema is highly optimized. Partitioning and clustering will keep analytical query costs incredibly low.
* **Modular & Extensible:** Clean separation of concerns (`network.tf`, `bigquery.tf`, `iam.tf`). Easy to add new environments (e.g., `prod.tfvars`).
* **Cost-Efficient Compute:** Using Redpanda via Docker on an `e2-medium` VM uses significantly less memory than a traditional JVM-based Kafka/Zookeeper cluster.

#### ⚠️ Cons & Areas for Improvement
* **Local State File (`terraform.tfstate`):** Currently, the state is stored locally. **For team collaboration, this must be migrated to a GCS Remote Backend** to prevent state conflicts and secure sensitive data (like SA keys).
* **Single Point of Failure (SPOF):** The Redpanda broker is deployed as a single node. While fine for development/testing, a production environment requires a multi-node cluster for High Availability.
* **Idle Costs:** Cloud NAT has a fixed hourly cost (~$32/month) regardless of traffic. If unused for long periods, consider running `terraform destroy` to save money.

---
*Maintained by the Data Engineering Team.*