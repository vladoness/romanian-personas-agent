#!/bin/bash

# AWS Marketplace Deployment Script
# Automates deployment of Romanian Personas Marketplace to ECS Fargate

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Romanian Personas Marketplace Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
CLUSTER_NAME="personas-marketplace"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS Account:${NC} $ACCOUNT_ID"
echo -e "${GREEN}✓ Region:${NC} $AWS_REGION"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found. Please install Docker.${NC}"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ AWS CLI not found. Please install AWS CLI.${NC}"
    exit 1
fi

if [ ! -d "chroma_db" ]; then
    echo -e "${RED}✗ chroma_db/ not found. Run ingestion pipeline first:${NC}"
    echo "   python -m ingest.scraper"
    echo "   python -m ingest.extract_quotes"
    echo "   python -m ingest.run_ingestion"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites satisfied${NC}"
echo ""

# Menu
echo "What would you like to do?"
echo "1. Full deployment (infrastructure + build + deploy)"
echo "2. Build and push Docker images only"
echo "3. Create ECS services only (assumes images exist)"
echo "4. Initialize EFS with data"
echo "5. Migrate legacy personas"
echo "6. Show deployment status"
read -p "Enter choice [1-6]: " CHOICE

case $CHOICE in
    1)
        echo -e "${GREEN}Starting full deployment...${NC}"

        # Step 1: Create ECR repositories
        echo -e "${YELLOW}Step 1/7: Creating ECR repositories...${NC}"
        for repo in personas-api personas-mcp personas-worker personas-debate-ui personas-admin-ui personas-redis; do
            if aws ecr describe-repositories --repository-names $repo --region $AWS_REGION &>/dev/null; then
                echo "  ✓ $repo already exists"
            else
                aws ecr create-repository \
                    --repository-name $repo \
                    --region $AWS_REGION \
                    --image-scanning-configuration scanOnPush=true &>/dev/null
                echo "  ✓ Created $repo"
            fi
        done

        # Step 2: Build and push images
        echo -e "${YELLOW}Step 2/7: Building and pushing Docker images...${NC}"
        aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

        ECR_PREFIX="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

        echo "  Building API..."
        docker build -f Dockerfile.api -t $ECR_PREFIX/personas-api:latest . &>/dev/null
        docker push $ECR_PREFIX/personas-api:latest &>/dev/null

        echo "  Building MCP Server..."
        docker build -t $ECR_PREFIX/personas-mcp:latest . &>/dev/null
        docker push $ECR_PREFIX/personas-mcp:latest &>/dev/null

        echo "  Building Worker..."
        docker build -f Dockerfile.worker -t $ECR_PREFIX/personas-worker:latest . &>/dev/null
        docker push $ECR_PREFIX/personas-worker:latest &>/dev/null

        echo "  Building Debate UI..."
        docker build -f persona-debate-ui/Dockerfile -t $ECR_PREFIX/personas-debate-ui:latest ./persona-debate-ui &>/dev/null
        docker push $ECR_PREFIX/personas-debate-ui:latest &>/dev/null

        echo "  Building Admin UI..."
        docker build -f admin-ui/Dockerfile -t $ECR_PREFIX/personas-admin-ui:latest ./admin-ui &>/dev/null
        docker push $ECR_PREFIX/personas-admin-ui:latest &>/dev/null

        echo "  Pulling and pushing Redis..."
        docker pull redis:7-alpine &>/dev/null
        docker tag redis:7-alpine $ECR_PREFIX/personas-redis:latest
        docker push $ECR_PREFIX/personas-redis:latest &>/dev/null

        echo -e "${GREEN}  ✓ All images pushed to ECR${NC}"

        # Step 3: Create ECS cluster
        echo -e "${YELLOW}Step 3/7: Creating ECS cluster...${NC}"
        if aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
            echo "  ✓ Cluster $CLUSTER_NAME already exists"
        else
            aws ecs create-cluster \
                --cluster-name $CLUSTER_NAME \
                --region $AWS_REGION \
                --capacity-providers FARGATE FARGATE_SPOT \
                --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 &>/dev/null
            echo "  ✓ Cluster created: $CLUSTER_NAME"
        fi

        # Step 4: Create EFS (if needed)
        echo -e "${YELLOW}Step 4/7: Setting up EFS...${NC}"
        echo "  Note: EFS setup requires manual configuration."
        echo "  Please follow AWS_MARKETPLACE_DEPLOYMENT.md section: Infrastructure Setup"
        echo "  Press Enter when EFS is ready..."
        read

        # Step 5: Register task definitions
        echo -e "${YELLOW}Step 5/7: Registering ECS task definitions...${NC}"
        echo "  Note: Task definitions require manual configuration."
        echo "  Please follow AWS_MARKETPLACE_DEPLOYMENT.md section: ECS Configuration"
        echo "  Press Enter when task definitions are registered..."
        read

        # Step 6: Create services
        echo -e "${YELLOW}Step 6/7: Creating ECS services...${NC}"
        echo "  Note: Service creation requires manual configuration."
        echo "  Please follow AWS_MARKETPLACE_DEPLOYMENT.md section: Deployment Steps"
        echo "  Press Enter when services are created..."
        read

        # Step 7: Verify
        echo -e "${YELLOW}Step 7/7: Verifying deployment...${NC}"
        echo "  Checking services..."
        aws ecs list-services --cluster $CLUSTER_NAME --region $AWS_REGION

        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}Deployment Complete!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo "Next steps:"
        echo "1. Get ALB DNS name from AWS Console"
        echo "2. Test health endpoints:"
        echo "   curl http://<ALB_DNS>/api/health"
        echo "   curl http://<ALB_DNS>/mcp/health"
        echo "3. Run migration: ./deploy-to-aws.sh (choose option 5)"
        echo "4. Access UIs:"
        echo "   Debate: http://<ALB_DNS>/"
        echo "   Admin: http://<ALB_DNS>/admin"
        ;;

    2)
        echo -e "${GREEN}Building and pushing Docker images...${NC}"

        aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

        ECR_PREFIX="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

        echo "Building API..."
        docker build -f Dockerfile.api -t $ECR_PREFIX/personas-api:latest .
        docker push $ECR_PREFIX/personas-api:latest

        echo "Building MCP Server..."
        docker build -t $ECR_PREFIX/personas-mcp:latest .
        docker push $ECR_PREFIX/personas-mcp:latest

        echo "Building Worker..."
        docker build -f Dockerfile.worker -t $ECR_PREFIX/personas-worker:latest .
        docker push $ECR_PREFIX/personas-worker:latest

        echo "Building Debate UI..."
        docker build -f persona-debate-ui/Dockerfile -t $ECR_PREFIX/personas-debate-ui:latest ./persona-debate-ui
        docker push $ECR_PREFIX/personas-debate-ui:latest

        echo "Building Admin UI..."
        docker build -f admin-ui/Dockerfile -t $ECR_PREFIX/personas-admin-ui:latest ./admin-ui
        docker push $ECR_PREFIX/personas-admin-ui:latest

        echo "Pulling and pushing Redis..."
        docker pull redis:7-alpine
        docker tag redis:7-alpine $ECR_PREFIX/personas-redis:latest
        docker push $ECR_PREFIX/personas-redis:latest

        echo -e "${GREEN}✓ All images pushed to ECR${NC}"
        ;;

    3)
        echo -e "${GREEN}Creating ECS services...${NC}"
        echo "This option is not yet fully automated."
        echo "Please follow AWS_MARKETPLACE_DEPLOYMENT.md section: Deployment Steps"
        ;;

    4)
        echo -e "${GREEN}Initializing EFS with data...${NC}"
        echo "This requires:"
        echo "1. EFS already created"
        echo "2. An EC2 instance or ECS task with EFS mounted"
        echo "Please follow AWS_MARKETPLACE_DEPLOYMENT.md section: Initialize EFS"
        ;;

    5)
        echo -e "${GREEN}Migrating legacy personas...${NC}"
        read -p "Enter API task ID: " TASK_ID

        aws ecs execute-command \
            --cluster $CLUSTER_NAME \
            --task $TASK_ID \
            --container api \
            --command "python migrate_legacy_personas.py" \
            --interactive \
            --region $AWS_REGION
        ;;

    6)
        echo -e "${GREEN}Deployment Status${NC}"
        echo ""
        echo "ECS Cluster:"
        aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION --query 'clusters[0].{Name:clusterName,Status:status,Tasks:registeredContainerInstancesCount}'
        echo ""
        echo "Services:"
        aws ecs list-services --cluster $CLUSTER_NAME --region $AWS_REGION
        echo ""
        echo "Recent tasks:"
        aws ecs list-tasks --cluster $CLUSTER_NAME --region $AWS_REGION
        ;;

    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Done!${NC}"
