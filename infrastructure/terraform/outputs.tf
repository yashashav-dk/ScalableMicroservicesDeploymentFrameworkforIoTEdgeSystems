output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority" {
  description = "Base64 encoded cluster CA certificate"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "vpc_id" {
  description = "VPC ID where the cluster is deployed"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs used by worker nodes"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs used by load balancers"
  value       = module.vpc.public_subnets
}

output "node_group_arn" {
  description = "ARN of the EKS managed node group"
  value       = module.eks.eks_managed_node_groups["iot_edge_workers"].node_group_arn
}

output "kubeconfig_command" {
  description = "Command to update kubeconfig for cluster access"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
