# Deployment Guide

Step-by-step instructions for deploying the IoT Edge Microservices platform to AWS EKS.

## Prerequisites

- **AWS CLI** v2+ configured with appropriate IAM credentials
- **kubectl** v1.28+
- **Docker** v24+
- **Terraform** v1.5+ (if using Terraform) or AWS CloudFormation access
- **Python** 3.11+ (for local development and testing)
- AWS account with permissions for EKS, EC2, VPC, IAM, and ECR

## 1. Local Development Setup

### Quick Start with Docker Compose

```bash
# Clone the repository
git clone <repository-url>
cd iot-microservices-deployment

# Start all services locally
docker-compose up -d --build

# Verify all services are running
curl http://localhost:8001/health  # sensor-ingestion
curl http://localhost:8002/health  # data-processor
curl http://localhost:8003/health  # device-registry
curl http://localhost:8004/health  # alert-manager
curl http://localhost:8005/health  # edge-gateway
```

### Running Tests Locally

```bash
# Install dependencies for each service
for svc in sensor-ingestion data-processor device-registry alert-manager edge-gateway; do
    cd microservices/$svc
    pip install -r requirements.txt
    python -m pytest tests/ -v
    cd ../..
done

# Or use the test script
chmod +x ci-cd/scripts/test.sh
./ci-cd/scripts/test.sh
```

## 2. Provision AWS Infrastructure

### Option A: CloudFormation

```bash
aws cloudformation deploy \
    --template-file infrastructure/cloudformation/eks-cluster.yaml \
    --stack-name iot-edge-cluster-stack \
    --parameter-overrides ClusterName=iot-edge-cluster \
    --capabilities CAPABILITY_NAMED_IAM \
    --region us-east-1
```

### Option B: Terraform

```bash
cd infrastructure/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### Configure kubectl

```bash
aws eks update-kubeconfig --region us-east-1 --name iot-edge-cluster
kubectl cluster-info
```

## 3. Build and Push Docker Images

```bash
# Authenticate with ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build all images
chmod +x ci-cd/scripts/build.sh
export DOCKER_REGISTRY=<account-id>.dkr.ecr.us-east-1.amazonaws.com
./ci-cd/scripts/build.sh

# Push images
for svc in sensor-ingestion data-processor device-registry alert-manager edge-gateway; do
    docker push ${DOCKER_REGISTRY}/${svc}:$(git rev-parse --short HEAD)
    docker push ${DOCKER_REGISTRY}/${svc}:latest
done
```

## 4. Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f kubernetes/namespace.yaml

# Deploy all services
for svc in sensor-ingestion data-processor device-registry alert-manager edge-gateway; do
    kubectl apply -f kubernetes/${svc}/
done

# Verify deployment
kubectl get pods -n iot-edge
kubectl get services -n iot-edge
kubectl get hpa -n iot-edge
```

### Or use the deploy script

```bash
chmod +x ci-cd/scripts/deploy.sh
export DOCKER_REGISTRY=<account-id>.dkr.ecr.us-east-1.amazonaws.com
./ci-cd/scripts/deploy.sh $(git rev-parse --short HEAD)
```

## 5. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n iot-edge -o wide

# Check services have ClusterIP
kubectl get svc -n iot-edge

# Port-forward to test locally
kubectl port-forward svc/edge-gateway 8005:8005 -n iot-edge

# Test through gateway
curl http://localhost:8005/health
curl http://localhost:8005/api/v1/device-registry/devices
```

## 6. Monitoring and Troubleshooting

```bash
# View pod logs
kubectl logs -f deployment/sensor-ingestion -n iot-edge

# Check HPA status
kubectl get hpa -n iot-edge

# Describe a deployment for events
kubectl describe deployment edge-gateway -n iot-edge

# Rolling restart
kubectl rollout restart deployment/sensor-ingestion -n iot-edge
```

## Teardown

```bash
# Remove Kubernetes resources
kubectl delete namespace iot-edge

# Destroy infrastructure (Terraform)
cd infrastructure/terraform && terraform destroy

# Or delete CloudFormation stack
aws cloudformation delete-stack --stack-name iot-edge-cluster-stack
```
