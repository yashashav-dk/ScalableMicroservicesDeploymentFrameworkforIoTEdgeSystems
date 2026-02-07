#!/usr/bin/env bash
# Setup script for provisioning and configuring the EKS cluster.
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-iot-edge-cluster}"
AWS_REGION="${AWS_REGION:-us-east-1}"
NAMESPACE="iot-edge"

echo "============================================"
echo "IoT Edge Platform - Cluster Setup"
echo "Cluster: ${CLUSTER_NAME}"
echo "Region:  ${AWS_REGION}"
echo "============================================"

# Step 1: Check prerequisites
echo ""
echo "--- Checking prerequisites ---"
for cmd in aws kubectl helm; do
    if command -v "${cmd}" &> /dev/null; then
        echo "  ✓ ${cmd} found"
    else
        echo "  ✗ ${cmd} not found. Please install it first."
        exit 1
    fi
done

# Step 2: Provision infrastructure (choose one)
echo ""
echo "--- Provisioning infrastructure ---"
echo "Choose method:"
echo "  1) CloudFormation"
echo "  2) Terraform"
read -rp "Enter choice [1/2]: " CHOICE

if [ "${CHOICE}" = "1" ]; then
    echo "Deploying CloudFormation stack..."
    aws cloudformation deploy \
        --template-file infrastructure/cloudformation/eks-cluster.yaml \
        --stack-name "${CLUSTER_NAME}-stack" \
        --parameter-overrides ClusterName="${CLUSTER_NAME}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${AWS_REGION}"
elif [ "${CHOICE}" = "2" ]; then
    echo "Applying Terraform configuration..."
    cd infrastructure/terraform
    terraform init
    terraform plan -out=tfplan
    terraform apply tfplan
    cd ../..
else
    echo "Invalid choice. Exiting."
    exit 1
fi

# Step 3: Configure kubectl
echo ""
echo "--- Configuring kubectl ---"
aws eks update-kubeconfig --region "${AWS_REGION}" --name "${CLUSTER_NAME}"
kubectl cluster-info

# Step 4: Create namespace
echo ""
echo "--- Creating namespace ---"
kubectl apply -f kubernetes/namespace.yaml

# Step 5: Deploy services
echo ""
echo "--- Deploying microservices ---"
SERVICES=("sensor-ingestion" "data-processor" "device-registry" "alert-manager" "edge-gateway")
for service in "${SERVICES[@]}"; do
    echo "Deploying ${service}..."
    kubectl apply -f "kubernetes/${service}/"
done

# Step 6: Verify deployment
echo ""
echo "--- Verifying deployment ---"
kubectl get all -n "${NAMESPACE}"

echo ""
echo "============================================"
echo "Cluster setup complete!"
echo "============================================"
echo ""
echo "Access the cluster:"
echo "  kubectl get pods -n ${NAMESPACE}"
echo "  kubectl get services -n ${NAMESPACE}"
