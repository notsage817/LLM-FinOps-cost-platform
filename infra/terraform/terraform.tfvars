project_id = "llm-finops-plf"

environment = "dev"
region      = "us-west1"
zone        = "us-west1-a"

bucket_name = "llm-finops-datalake"
vpc_name    = "llm-finops-vpc"

redpanda_machine_type = "e2-medium" # Upgrade for heavier workloads
subnet_cidr           = "10.0.0.0/24"
redpanda_static_ip    = "10.0.0.10"