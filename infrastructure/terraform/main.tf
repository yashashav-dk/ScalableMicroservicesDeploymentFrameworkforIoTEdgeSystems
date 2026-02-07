terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "iot-edge-terraform-state"
    key    = "eks/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "iot-edge-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ─── Data Sources ──────────────────────────────────────────────────────
data "aws_availability_zones" "available" {
  state = "available"
}

# ─── VPC ───────────────────────────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets  = var.public_subnet_cidrs
  private_subnets = var.private_subnet_cidrs

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/role/elb"                      = "1"
    "kubernetes.io/cluster/${var.cluster_name}"    = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"             = "1"
    "kubernetes.io/cluster/${var.cluster_name}"    = "shared"
  }
}

# ─── EKS Cluster ───────────────────────────────────────────────────────
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  eks_managed_node_groups = {
    iot_edge_workers = {
      name           = "${var.cluster_name}-nodegroup"
      instance_types = [var.node_instance_type]
      ami_type       = "AL2_x86_64"

      min_size     = var.node_group_min_size
      max_size     = var.node_group_max_size
      desired_size = var.node_group_desired_size

      disk_size = 30

      labels = {
        role        = "worker"
        environment = var.environment
      }

      tags = {
        Name = "${var.cluster_name}-worker"
      }
    }
  }

  tags = {
    Cluster = var.cluster_name
  }
}
