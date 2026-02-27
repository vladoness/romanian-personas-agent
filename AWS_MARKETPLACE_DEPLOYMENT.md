# AWS Marketplace Deployment Guide

Complete guide to deploying the Romanian Personas Marketplace to AWS ECS Fargate.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Infrastructure Setup](#infrastructure-setup)
- [Build and Push Images](#build-and-push-images)
- [ECS Configuration](#ecs-configuration)
- [ALB Configuration](#alb-configuration)
- [Environment Variables](#environment-variables)
- [Deployment Steps](#deployment-steps)
- [Verification](#verification)
- [Cost Estimate](#cost-estimate)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Current State (2 services)
- **MCP Server** - http://3.83.102.160:8080 (ECS cluster: vlad-persona-agents-tests)
- **Debate UI** - http://44.201.32.22:3000 (separate service)

### Target State (6 services)

```
┌─────────────────────────────────────────────────────────┐
│                 Application Load Balancer                │
│  (/api → api, /mcp → mcp, /admin → admin, / → debate)   │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────┐
│          ECS Cluster: personas-marketplace               │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Redis  │  │   API   │  │   MCP    │  │  Celery  │ │
│  │ (512MB) │  │ (2GB)   │  │  Server  │  │  Worker  │ │
│  │         │  │         │  │  (4GB)   │  │  (2GB)   │ │
│  └────┬────┘  └────┬────┘  └────┬─────┘  └────┬─────┘ │
│       │            │            │              │        │
│       └────────────┴────────────┴──────────────┘        │
│                                                          │
│  ┌──────────┐  ┌──────────┐                            │
│  │  Debate  │  │  Admin   │                            │
│  │  UI      │  │  UI      │                            │
│  │ (512MB)  │  │ (512MB)  │                            │
│  └──────────┘  └──────────┘                            │
│                                                          │
│  Shared EFS Volume: /efs                                │
│  ├── personas.db (SQLite)                               │
│  ├── chroma_db/ (123MB, pre-built)                      │
│  └── data/ (uploaded files)                             │
└──────────────────────────────────────────────────────────┘
```

**Key Design Decisions:**
- **EFS for shared storage** - SQLite database and ChromaDB accessible by all services
- **Redis in ECS** - Simple deployment, no ElastiCache needed for MVP
- **Baked ChromaDB** - Pre-built vector DB copied to EFS once
- **Single ALB** - Path-based routing to all services
- **Public subnet** - Simpler networking for MVP (use private subnet + NAT Gateway for production)

---

## Prerequisites

### Local Requirements
- Docker installed and running
- AWS CLI configured: `aws configure`
- AWS account with ECS/ECR permissions
- Existing: Pre-built `chroma_db/` and `data/` directories (from ingestion)

### AWS Resources (to be created)
- ECR repositories (6 total)
- ECS cluster
- EFS file system
- ALB + Target Groups
- Security Groups
- IAM roles for ECS tasks

---

## Infrastructure Setup

### Step 1: Create ECR Repositories

```bash
# Create 6 ECR repositories
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

for repo in personas-api personas-mcp personas-worker personas-debate-ui personas-admin-ui personas-redis; do
  aws ecr create-repository \
    --repository-name $repo \
    --region $AWS_REGION \
    --image-scanning-configuration scanOnPush=true
done

echo "ECR repositories created:"
aws ecr describe-repositories --region $AWS_REGION --query 'repositories[].repositoryName'
```

### Step 2: Create EFS File System

```bash
# Create EFS for shared storage (SQLite + ChromaDB)
EFS_ID=$(aws efs create-file-system \
  --performance-mode generalPurpose \
  --throughput-mode bursting \
  --encrypted \
  --tags Key=Name,Value=personas-marketplace-storage \
  --region $AWS_REGION \
  --query 'FileSystemId' \
  --output text)

echo "EFS created: $EFS_ID"

# Get VPC ID from existing ECS cluster
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --region $AWS_REGION)

# Get subnet IDs
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].SubnetId' \
  --output text \
  --region $AWS_REGION)

# Create mount targets (one per subnet for HA)
for SUBNET_ID in $SUBNET_IDS; do
  aws efs create-mount-target \
    --file-system-id $EFS_ID \
    --subnet-id $SUBNET_ID \
    --security-groups <efs-security-group-id> \
    --region $AWS_REGION
done

# Wait for mount targets to become available
aws efs describe-mount-targets \
  --file-system-id $EFS_ID \
  --region $AWS_REGION

echo "EFS mount targets created"
```

**Note:** You'll need to create a security group for EFS that allows NFS (port 2049) from ECS tasks.

### Step 3: Create Security Groups

```bash
# ECS tasks security group (allows ALB traffic + EFS)
ECS_SG=$(aws ec2 create-security-group \
  --group-name personas-ecs-tasks \
  --description "Security group for Personas ECS tasks" \
  --vpc-id $VPC_ID \
  --region $AWS_REGION \
  --query 'GroupId' \
  --output text)

# Allow ALB traffic (ports 3000, 3001, 8000, 8080, 6379)
aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp \
  --port 3000 \
  --source-group <alb-security-group-id> \
  --region $AWS_REGION

aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp \
  --port 3001 \
  --source-group <alb-security-group-id> \
  --region $AWS_REGION

aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp \
  --port 8000 \
  --source-group <alb-security-group-id> \
  --region $AWS_REGION

aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp \
  --port 8080 \
  --source-group <alb-security-group-id> \
  --region $AWS_REGION

# Allow inter-task communication (Redis)
aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp \
  --port 6379 \
  --source-group $ECS_SG \
  --region $AWS_REGION

# EFS security group
EFS_SG=$(aws ec2 create-security-group \
  --group-name personas-efs \
  --description "Security group for Personas EFS" \
  --vpc-id $VPC_ID \
  --region $AWS_REGION \
  --query 'GroupId' \
  --output text)

# Allow NFS from ECS tasks
aws ec2 authorize-security-group-ingress \
  --group-id $EFS_SG \
  --protocol tcp \
  --port 2049 \
  --source-group $ECS_SG \
  --region $AWS_REGION

echo "Security groups created: ECS=$ECS_SG, EFS=$EFS_SG"
```

---

## Build and Push Images

### Option A: Automated Build with CodeBuild

**Update buildspec.yml** to build all 6 images:

```yaml
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI
      - ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
      - REGION=${AWS_DEFAULT_REGION}

  build:
    commands:
      - echo Build started on `date`

      # Build API
      - docker build -f Dockerfile.api -t $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-api:latest .

      # Build MCP Server (existing)
      - docker build -t $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-mcp:latest .

      # Build Celery Worker
      - docker build -f Dockerfile.worker -t $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-worker:latest .

      # Build Debate UI
      - docker build -f persona-debate-ui/Dockerfile -t $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-debate-ui:latest ./persona-debate-ui

      # Build Admin UI
      - docker build -f admin-ui/Dockerfile -t $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-admin-ui:latest ./admin-ui

      # Redis (pull from Docker Hub)
      - docker pull redis:7-alpine
      - docker tag redis:7-alpine $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-redis:latest

  post_build:
    commands:
      - echo Pushing Docker images...
      - docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-api:latest
      - docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-mcp:latest
      - docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-worker:latest
      - docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-debate-ui:latest
      - docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-admin-ui:latest
      - docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/personas-redis:latest
      - echo Build completed on `date`
```

### Option B: Manual Build and Push

```bash
AWS_REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_PREFIX="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_PREFIX

# Build images
echo "Building images..."
docker build -f Dockerfile.api -t $ECR_PREFIX/personas-api:latest .
docker build -t $ECR_PREFIX/personas-mcp:latest .
docker build -f Dockerfile.worker -t $ECR_PREFIX/personas-worker:latest .
docker build -f persona-debate-ui/Dockerfile -t $ECR_PREFIX/personas-debate-ui:latest ./persona-debate-ui
docker build -f admin-ui/Dockerfile -t $ECR_PREFIX/personas-admin-ui:latest ./admin-ui
docker pull redis:7-alpine
docker tag redis:7-alpine $ECR_PREFIX/personas-redis:latest

# Push images
echo "Pushing images to ECR..."
docker push $ECR_PREFIX/personas-api:latest
docker push $ECR_PREFIX/personas-mcp:latest
docker push $ECR_PREFIX/personas-worker:latest
docker push $ECR_PREFIX/personas-debate-ui:latest
docker push $ECR_PREFIX/personas-admin-ui:latest
docker push $ECR_PREFIX/personas-redis:latest

echo "All images pushed successfully"
```

---

## ECS Configuration

### Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name personas-marketplace \
  --region $AWS_REGION \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1
```

### ECS Task Definitions

I'll create individual task definition JSON files for each service.

#### 1. Redis Task Definition

Save as `ecs-task-redis.json`:

```json
{
  "family": "personas-redis",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "redis",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/personas-redis:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 6379,
          "protocol": "tcp"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/personas-marketplace",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "redis"
        }
      }
    }
  ]
}
```

#### 2. API Task Definition

Save as `ecs-task-api.json`:

```json
{
  "family": "personas-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/personas-api:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "REDIS_URL", "value": "redis://redis.personas-marketplace:6379/0"},
        {"name": "DATABASE_URL", "value": "sqlite:////efs/personas.db"},
        {"name": "CHROMA_PERSIST_DIR", "value": "/efs/chroma_db"},
        {"name": "DATA_DIR", "value": "/efs/data"}
      ],
      "secrets": [
        {"name": "ANTHROPIC_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/anthropic_key"},
        {"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/openai_key"},
        {"name": "ADMIN_PASSWORD", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/admin_password"}
      ],
      "mountPoints": [
        {
          "sourceVolume": "efs-storage",
          "containerPath": "/efs",
          "readOnly": false
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/personas-marketplace",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "api"
        }
      }
    }
  ],
  "volumes": [
    {
      "name": "efs-storage",
      "efsVolumeConfiguration": {
        "fileSystemId": "<EFS_ID>",
        "transitEncryption": "ENABLED"
      }
    }
  ]
}
```

#### 3. MCP Server Task Definition

Save as `ecs-task-mcp.json`:

```json
{
  "family": "personas-mcp",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "mcp-server",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/personas-mcp:latest",
      "essential": true,
      "command": ["python", "-m", "agent.mcp_server", "--transport", "streamable-http"],
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "CHROMA_PERSIST_DIR", "value": "/efs/chroma_db"},
        {"name": "DATA_DIR", "value": "/efs/data"}
      ],
      "secrets": [
        {"name": "ANTHROPIC_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/anthropic_key"},
        {"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/openai_key"},
        {"name": "MCP_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/mcp_api_key"}
      ],
      "mountPoints": [
        {
          "sourceVolume": "efs-storage",
          "containerPath": "/efs",
          "readOnly": true
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/personas-marketplace",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "mcp"
        }
      }
    }
  ],
  "volumes": [
    {
      "name": "efs-storage",
      "efsVolumeConfiguration": {
        "fileSystemId": "<EFS_ID>",
        "transitEncryption": "ENABLED"
      }
    }
  ]
}
```

#### 4. Celery Worker Task Definition

Save as `ecs-task-worker.json`:

```json
{
  "family": "personas-worker",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "celery-worker",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/personas-worker:latest",
      "essential": true,
      "command": ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info"],
      "environment": [
        {"name": "REDIS_URL", "value": "redis://redis.personas-marketplace:6379/0"},
        {"name": "DATABASE_URL", "value": "sqlite:////efs/personas.db"},
        {"name": "CHROMA_PERSIST_DIR", "value": "/efs/chroma_db"},
        {"name": "DATA_DIR", "value": "/efs/data"}
      ],
      "secrets": [
        {"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/openai_key"}
      ],
      "mountPoints": [
        {
          "sourceVolume": "efs-storage",
          "containerPath": "/efs",
          "readOnly": false
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/personas-marketplace",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "worker"
        }
      }
    }
  ],
  "volumes": [
    {
      "name": "efs-storage",
      "efsVolumeConfiguration": {
        "fileSystemId": "<EFS_ID>",
        "transitEncryption": "ENABLED"
      }
    }
  ]
}
```

#### 5. Debate UI Task Definition

Save as `ecs-task-debate-ui.json`:

```json
{
  "family": "personas-debate-ui",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "debate-ui",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/personas-debate-ui:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 3000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "MCP_SERVER_URL", "value": "http://mcp.personas-marketplace:8080"},
        {"name": "FASTAPI_URL", "value": "http://api.personas-marketplace:8000"}
      ],
      "secrets": [
        {"name": "ACCESS_PASSWORD", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/debate_password"},
        {"name": "TAVILY_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:personas/tavily_key"}
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:3000/api/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/personas-marketplace",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "debate-ui"
        }
      }
    }
  ]
}
```

#### 6. Admin UI Task Definition

Save as `ecs-task-admin-ui.json`:

```json
{
  "family": "personas-admin-ui",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "admin-ui",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/personas-admin-ui:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 3001,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "VITE_API_URL", "value": "http://<ALB_DNS>/api"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/personas-marketplace",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "admin-ui"
        }
      }
    }
  ]
}
```

### Register Task Definitions

```bash
# Replace placeholders
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
EFS_ID=<your-efs-id>

for file in ecs-task-*.json; do
  sed -i "s/<ACCOUNT_ID>/$ACCOUNT_ID/g" $file
  sed -i "s/<EFS_ID>/$EFS_ID/g" $file

  aws ecs register-task-definition \
    --cli-input-json file://$file \
    --region $AWS_REGION
done

echo "All task definitions registered"
```

---

## Environment Variables

### Store Secrets in AWS Secrets Manager

```bash
# Create secrets
aws secretsmanager create-secret \
  --name personas/anthropic_key \
  --secret-string "sk-ant-..." \
  --region $AWS_REGION

aws secretsmanager create-secret \
  --name personas/openai_key \
  --secret-string "sk-..." \
  --region $AWS_REGION

aws secretsmanager create-secret \
  --name personas/admin_password \
  --secret-string "Romanian2026!" \
  --region $AWS_REGION

aws secretsmanager create-secret \
  --name personas/mcp_api_key \
  --secret-string "your-mcp-key" \
  --region $AWS_REGION

aws secretsmanager create-secret \
  --name personas/debate_password \
  --secret-string "Romanian2026!" \
  --region $AWS_REGION

aws secretsmanager create-secret \
  --name personas/tavily_key \
  --secret-string "tvly-..." \
  --region $AWS_REGION
```

---

## ALB Configuration

### Create Target Groups

```bash
# API target group
aws elbv2 create-target-group \
  --name personas-api-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --region $AWS_REGION

# MCP target group
aws elbv2 create-target-group \
  --name personas-mcp-tg \
  --protocol HTTP \
  --port 8080 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --region $AWS_REGION

# Debate UI target group
aws elbv2 create-target-group \
  --name personas-debate-tg \
  --protocol HTTP \
  --port 3000 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /api/health \
  --region $AWS_REGION

# Admin UI target group
aws elbv2 create-target-group \
  --name personas-admin-tg \
  --protocol HTTP \
  --port 3001 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --region $AWS_REGION
```

### Create Application Load Balancer

```bash
# Create ALB
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name personas-marketplace-alb \
  --subnets $SUBNET_IDS \
  --security-groups <alb-security-group-id> \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4 \
  --region $AWS_REGION \
  --query 'LoadBalancers[0].LoadBalancerArn' \
  --output text)

# Get ALB DNS
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

echo "ALB created: $ALB_DNS"
```

### Configure Listener Rules

```bash
# Create HTTP listener
LISTENER_ARN=$(aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=<debate-ui-target-group-arn> \
  --region $AWS_REGION \
  --query 'Listeners[0].ListenerArn' \
  --output text)

# Add rules for path-based routing
# /api/* → API
aws elbv2 create-rule \
  --listener-arn $LISTENER_ARN \
  --priority 1 \
  --conditions Field=path-pattern,Values='/api/*' \
  --actions Type=forward,TargetGroupArn=<api-target-group-arn> \
  --region $AWS_REGION

# /mcp → MCP Server
aws elbv2 create-rule \
  --listener-arn $LISTENER_ARN \
  --priority 2 \
  --conditions Field=path-pattern,Values='/mcp*' \
  --actions Type=forward,TargetGroupArn=<mcp-target-group-arn> \
  --region $AWS_REGION

# /admin → Admin UI
aws elbv2 create-rule \
  --listener-arn $LISTENER_ARN \
  --priority 3 \
  --conditions Field=path-pattern,Values='/admin*' \
  --actions Type=forward,TargetGroupArn=<admin-target-group-arn> \
  --region $AWS_REGION

# Default: Debate UI (already set in listener)
```

---

## Deployment Steps

### Step 1: Initialize EFS with Pre-built Data

**Important:** Copy pre-built ChromaDB and SQLite database to EFS before starting services.

```bash
# Launch a temporary EC2 instance with EFS mounted
# Or use ECS Fargate task with EFS volume

# Create an init task definition with EFS mounted
# Run these commands inside the container:

# Copy pre-built ChromaDB
aws s3 cp s3://your-bucket/chroma_db.tar.gz /tmp/
tar -xzf /tmp/chroma_db.tar.gz -C /efs/

# Copy data directory
aws s3 cp s3://your-bucket/data.tar.gz /tmp/
tar -xzf /tmp/data.tar.gz -C /efs/

# Create empty SQLite database (will be initialized by API)
touch /efs/personas.db

# Verify
ls -lh /efs/
# Should show: chroma_db/ (123MB), data/, personas.db
```

**Alternative:** Use an init container in the API task definition to copy data from image to EFS on first run.

### Step 2: Deploy Services in Order

```bash
# 1. Deploy Redis (no dependencies)
aws ecs create-service \
  --cluster personas-marketplace \
  --service-name redis \
  --task-definition personas-redis \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --service-registries "registryArn=<service-discovery-arn>" \
  --region $AWS_REGION

# Wait for Redis to be healthy
aws ecs wait services-stable \
  --cluster personas-marketplace \
  --services redis \
  --region $AWS_REGION

# 2. Deploy API (depends on Redis + EFS)
aws ecs create-service \
  --cluster personas-marketplace \
  --service-name api \
  --task-definition personas-api \
  --desired-count 1 \
  --launch-type FARGATE \
  --load-balancers "targetGroupArn=<api-tg-arn>,containerName=api,containerPort=8000" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --region $AWS_REGION

# 3. Deploy MCP Server (depends on EFS)
aws ecs create-service \
  --cluster personas-marketplace \
  --service-name mcp-server \
  --task-definition personas-mcp \
  --desired-count 1 \
  --launch-type FARGATE \
  --load-balancers "targetGroupArn=<mcp-tg-arn>,containerName=mcp-server,containerPort=8080" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --region $AWS_REGION

# 4. Deploy Celery Worker (depends on Redis + EFS)
aws ecs create-service \
  --cluster personas-marketplace \
  --service-name celery-worker \
  --task-definition personas-worker \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --region $AWS_REGION

# 5. Deploy Debate UI (depends on API + MCP)
aws ecs create-service \
  --cluster personas-marketplace \
  --service-name debate-ui \
  --task-definition personas-debate-ui \
  --desired-count 1 \
  --launch-type FARGATE \
  --load-balancers "targetGroupArn=<debate-tg-arn>,containerName=debate-ui,containerPort=3000" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --region $AWS_REGION

# 6. Deploy Admin UI (depends on API)
aws ecs create-service \
  --cluster personas-marketplace \
  --service-name admin-ui \
  --task-definition personas-admin-ui \
  --desired-count 1 \
  --launch-type FARGATE \
  --load-balancers "targetGroupArn=<admin-tg-arn>,containerName=admin-ui,containerPort=3001" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --region $AWS_REGION

# Wait for all services to stabilize
aws ecs wait services-stable \
  --cluster personas-marketplace \
  --services api mcp-server celery-worker debate-ui admin-ui \
  --region $AWS_REGION

echo "All services deployed successfully"
```

### Step 3: Migrate Legacy Personas

Once the API is running, migrate the 5 existing personas to the database:

```bash
# Run migration script via ECS exec or temporary task
aws ecs execute-command \
  --cluster personas-marketplace \
  --task <api-task-id> \
  --container api \
  --command "python migrate_legacy_personas.py" \
  --interactive

# Or run as a one-off task
aws ecs run-task \
  --cluster personas-marketplace \
  --task-definition personas-api \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"api","command":["python","migrate_legacy_personas.py"]}]}'
```

---

## Verification

### Check Service Health

```bash
# Get ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names personas-marketplace-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

# Test API health
curl http://$ALB_DNS/api/health

# Test MCP health
curl http://$ALB_DNS/mcp/health

# Test debate UI
curl http://$ALB_DNS/

# Test admin UI
curl http://$ALB_DNS/admin

# List personas
curl -u admin:Romanian2026! http://$ALB_DNS/api/personas
```

### Check ECS Services

```bash
# List all services
aws ecs list-services \
  --cluster personas-marketplace \
  --region $AWS_REGION

# Describe specific service
aws ecs describe-services \
  --cluster personas-marketplace \
  --services api mcp-server celery-worker \
  --region $AWS_REGION

# Check task logs
aws logs tail /ecs/personas-marketplace --follow
```

### Test End-to-End

```bash
# 1. List personas (should show 5 legacy personas)
curl -u admin:Romanian2026! http://$ALB_DNS/api/personas

# 2. Start a debate via UI
open http://$ALB_DNS

# 3. Access admin UI
open http://$ALB_DNS/admin
```

---

## Cost Estimate

**Monthly AWS Costs (24/7 operation):**

| Service | Specs | Monthly Cost |
|---------|-------|--------------|
| ECS Fargate - Redis | 0.25 vCPU, 0.5GB | $12 |
| ECS Fargate - API | 0.5 vCPU, 2GB | $30 |
| ECS Fargate - MCP | 1 vCPU, 4GB | $60 |
| ECS Fargate - Worker | 0.5 vCPU, 2GB | $30 |
| ECS Fargate - Debate UI | 0.25 vCPU, 0.5GB | $12 |
| ECS Fargate - Admin UI | 0.25 vCPU, 0.5GB | $12 |
| ALB | - | $20 |
| EFS | 10GB storage | $3 |
| ECR | 6 images (~2GB) | $1 |
| CloudWatch Logs | ~10GB/month | $5 |
| **Total** | | **~$185/month** |

**Cost Optimization Options:**
- Use FARGATE_SPOT for 70% discount (worker, redis)
- Scale down to 1 instance of each during off-hours
- Use reserved capacity for predictable workloads
- Estimated savings: **~$100/month** → **$85/month**

---

## Troubleshooting

### Services Not Starting

```bash
# Check task logs
aws logs tail /ecs/personas-marketplace --follow

# Describe failed tasks
aws ecs describe-tasks \
  --cluster personas-marketplace \
  --tasks <task-id> \
  --region $AWS_REGION

# Common issues:
# 1. EFS not mounted: Check security group allows NFS (port 2049)
# 2. Secrets not accessible: Check IAM task execution role has secretsmanager:GetSecretValue
# 3. Redis not reachable: Check service discovery and security groups
```

### Redis Connection Errors

```bash
# Verify Redis service is running
aws ecs describe-services \
  --cluster personas-marketplace \
  --services redis \
  --region $AWS_REGION

# Check security group allows port 6379 from ECS tasks
aws ec2 describe-security-groups --group-ids $ECS_SG
```

### EFS Mount Failures

```bash
# Verify mount targets are available
aws efs describe-mount-targets \
  --file-system-id $EFS_ID \
  --region $AWS_REGION

# Check EFS security group allows NFS from ECS
aws ec2 describe-security-groups --group-ids $EFS_SG

# Test EFS access from EC2 instance
sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576 \
  $EFS_ID.efs.$AWS_REGION.amazonaws.com:/ /mnt/efs
```

### ChromaDB Not Found

```bash
# Verify EFS has chroma_db directory
aws ecs execute-command \
  --cluster personas-marketplace \
  --task <api-task-id> \
  --container api \
  --command "ls -lh /efs" \
  --interactive

# If missing, run EFS init step again
```

### Database Locked (SQLite)

```bash
# SQLite on EFS can have locking issues with multiple writers
# Solution 1: Use WAL mode (already configured in database.py)
# Solution 2: Ensure only API writes (worker/mcp read-only)
# Solution 3: Migrate to RDS PostgreSQL for production

# Check current mode
aws ecs execute-command \
  --cluster personas-marketplace \
  --task <api-task-id> \
  --container api \
  --command "sqlite3 /efs/personas.db 'PRAGMA journal_mode;'" \
  --interactive
# Should return: wal
```

---

## Production Considerations

### Security Hardening

- [ ] Use private subnets for ECS tasks + NAT Gateway
- [ ] Enable ALB access logs to S3
- [ ] Use AWS WAF for ALB protection
- [ ] Enable container insights for monitoring
- [ ] Use secrets rotation for API keys
- [ ] Enable VPC Flow Logs
- [ ] Use IAM roles for ECS tasks (no hardcoded credentials)

### High Availability

- [ ] Deploy tasks across multiple AZs
- [ ] Set desired count > 1 for critical services (API, MCP)
- [ ] Use EFS replication for backup
- [ ] Configure auto-scaling for ECS services
- [ ] Set up Route53 health checks
- [ ] Enable cross-region failover (optional)

### Monitoring & Alerts

```bash
# Create CloudWatch alarms
aws cloudwatch put-metric-alarm \
  --alarm-name personas-api-cpu-high \
  --alarm-description "API CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=ServiceName,Value=api Name=ClusterName,Value=personas-marketplace

# Create SNS topic for alerts
aws sns create-topic --name personas-alerts
aws sns subscribe --topic-arn <topic-arn> --protocol email --notification-endpoint admin@example.com
```

### Backup Strategy

```bash
# EFS backup (automated daily)
aws backup create-backup-plan \
  --backup-plan '{
    "BackupPlanName": "personas-efs-daily",
    "Rules": [{
      "RuleName": "daily-backup",
      "TargetBackupVaultName": "Default",
      "ScheduleExpression": "cron(0 5 * * ? *)",
      "StartWindowMinutes": 60,
      "CompletionWindowMinutes": 120,
      "Lifecycle": {
        "DeleteAfterDays": 30
      }
    }]
  }'

# Database backup (export to S3 daily)
# Add to API cron job or Lambda function
aws s3 cp /efs/personas.db s3://personas-backups/$(date +%Y%m%d)-personas.db
```

---

## Next Steps

After successful deployment:

1. **Test Admin UI** - Create a test persona through the admin interface
2. **Monitor Logs** - Watch CloudWatch logs for errors
3. **Load Test** - Use `ab` or `wrk` to test concurrent queries
4. **Document URLs** - Update `.env.example` with ALB DNS
5. **Set Up CI/CD** - Configure CodeBuild webhook for auto-deploy
6. **Enable HTTPS** - Add ACM certificate to ALB listener
7. **Custom Domain** - Point Route53 domain to ALB

---

**Last Updated:** 2026-02-26
**Deployment Model:** ECS Fargate + EFS + ALB
**Total Services:** 6 (Redis, API, MCP, Worker, Debate UI, Admin UI)
