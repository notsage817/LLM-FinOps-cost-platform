variable "project_id" {
    description = "The GCP project ID"
    type        = string
}

variable "region" { 
    type       = string
    default    = "us-west2"
    description = "The GCP region for all resources"
}

variable "zone" {
    type       = string
    default    = "us-west2-a"
    description = "GCP zone for the Redpanda VM"
}

variable "environment" {
    type        = string
    default     = "dev"
    description = "Environment tag (dev/prod)"
}

variable "bucket_name" {
    type        = string
    default     = "llm-finops-datalake"
    description = "Prefix for GCS bucket names"
}

variable "redpanda_machine_type" {
    type        = string
    default     = "e2-medium"
    description = "The machine type for the Redpanda VM(2 vCPU, 4GB RAM)"    
}

variable "vpc_name" {
    type       = string
    default     = "llm-finops-vpc"
    description = "Name of the VPC network"
}

variable "subnet_cidr" {
    type       = string
    default     = "10.0.0.0/24"
    description = "CIDR range for the subnet"
}

variable "redpanda_static_ip" {
    type       = string
    default    = "10.0.0.10"
    description = "Static internal IP served for the Redpanda VM"
}