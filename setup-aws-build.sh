#!/bin/bash

# Setup AWS CodeBuild for Marketplace Deployment
# Creates ECR repositories and CodeBuild project to build all 6 images

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AWS CodeBuild Setup for Marketplace${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
GITHUB_REPO=${GITHUB_REPO:-"your-username/romanian-personas-agent"}
GITHUB_BRANCH=${GITHUB_BRANCH:-"main"}
CODEBUILD_PROJECT_NAME="personas-marketplace-builder"

# Get AWS account details
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS Account:${NC} $ACCOUNT_ID"
echo -e "${GREEN}✓ Region:${NC} $AWS_REGION"
echo ""

# Step 1: Create ECR repositories
echo -e "${YELLOW}Step 1/3: Creating ECR repositories...${NC}"

REPOS=("marketplace-api" "marketplace-mcp" "marketplace-worker" "marketplace-debate-ui" "marketplace-admin-ui" "marketplace-redis")

for repo in "${REPOS[@]}"; do
    if aws ecr describe-repositories --repository-names $repo --region $AWS_REGION &>/dev/null; then
        echo -e "  ✓ ${GREEN}$repo${NC} (already exists)"
    else
        aws ecr create-repository \
            --repository-name $repo \
            --region $AWS_REGION \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256 \
            --tags Key=Project,Value=PersonasMarketplace &>/dev/null
        echo -e "  ✓ ${GREEN}Created $repo${NC}"
    fi
done

echo ""

# Step 2: Create IAM role for CodeBuild (if doesn't exist)
echo -e "${YELLOW}Step 2/3: Setting up CodeBuild IAM role...${NC}"

CODEBUILD_ROLE_NAME="PersonasCodeBuildRole"
ROLE_ARN=""

if aws iam get-role --role-name $CODEBUILD_ROLE_NAME --region $AWS_REGION &>/dev/null; then
    echo -e "  ✓ ${GREEN}IAM role exists${NC}"
    ROLE_ARN=$(aws iam get-role --role-name $CODEBUILD_ROLE_NAME --query 'Role.Arn' --output text)
else
    # Create trust policy
    cat > /tmp/codebuild-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create role
    ROLE_ARN=$(aws iam create-role \
        --role-name $CODEBUILD_ROLE_NAME \
        --assume-role-policy-document file:///tmp/codebuild-trust-policy.json \
        --query 'Role.Arn' \
        --output text)

    # Attach managed policies
    aws iam attach-role-policy \
        --role-name $CODEBUILD_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AWSCodeBuildDeveloperAccess

    aws iam attach-role-policy \
        --role-name $CODEBUILD_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

    # Create inline policy for CloudWatch Logs
    cat > /tmp/codebuild-logs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:$AWS_REGION:$ACCOUNT_ID:log-group:/aws/codebuild/*"
    }
  ]
}
EOF

    aws iam put-role-policy \
        --role-name $CODEBUILD_ROLE_NAME \
        --policy-name CodeBuildLogsPolicy \
        --policy-document file:///tmp/codebuild-logs-policy.json

    echo -e "  ✓ ${GREEN}Created IAM role${NC}"
    echo "  Waiting 10 seconds for IAM propagation..."
    sleep 10
fi

echo ""

# Step 3: Create or update CodeBuild project
echo -e "${YELLOW}Step 3/3: Setting up CodeBuild project...${NC}"

# Check if project exists
if aws codebuild batch-get-projects --names $CODEBUILD_PROJECT_NAME --region $AWS_REGION --query 'projects[0].name' --output text 2>/dev/null | grep -q "$CODEBUILD_PROJECT_NAME"; then
    echo -e "  ${YELLOW}CodeBuild project already exists. Updating...${NC}"
    ACTION="update"
else
    echo -e "  ${GREEN}Creating new CodeBuild project...${NC}"
    ACTION="create"
fi

# Create project configuration
cat > /tmp/codebuild-project.json <<EOF
{
  "name": "$CODEBUILD_PROJECT_NAME",
  "description": "Builds all 6 Docker images for Romanian Personas Marketplace",
  "source": {
    "type": "GITHUB",
    "location": "https://github.com/$GITHUB_REPO",
    "buildspec": "buildspec.yml",
    "gitCloneDepth": 1,
    "reportBuildStatus": true
  },
  "artifacts": {
    "type": "NO_ARTIFACTS"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_LARGE",
    "privilegedMode": true,
    "environmentVariables": [
      {
        "name": "AWS_DEFAULT_REGION",
        "value": "$AWS_REGION",
        "type": "PLAINTEXT"
      },
      {
        "name": "AWS_ACCOUNT_ID",
        "value": "$ACCOUNT_ID",
        "type": "PLAINTEXT"
      }
    ]
  },
  "serviceRole": "$ROLE_ARN",
  "timeoutInMinutes": 60,
  "queuedTimeoutInMinutes": 480,
  "tags": [
    {
      "key": "Project",
      "value": "PersonasMarketplace"
    }
  ],
  "logsConfig": {
    "cloudWatchLogs": {
      "status": "ENABLED",
      "groupName": "/aws/codebuild/personas-marketplace"
    }
  },
  "buildBatchConfig": {
    "serviceRole": "$ROLE_ARN",
    "timeoutInMins": 60
  }
}
EOF

if [ "$ACTION" = "create" ]; then
    aws codebuild create-project --cli-input-json file:///tmp/codebuild-project.json --region $AWS_REGION &>/dev/null
    echo -e "  ✓ ${GREEN}CodeBuild project created${NC}"
else
    # For update, use update-project (slightly different JSON structure)
    aws codebuild update-project \
        --name $CODEBUILD_PROJECT_NAME \
        --source type=GITHUB,location=https://github.com/$GITHUB_REPO,buildspec=buildspec.yml \
        --environment type=LINUX_CONTAINER,image=aws/codebuild/standard:7.0,computeType=BUILD_GENERAL1_LARGE,privilegedMode=true \
        --service-role $ROLE_ARN \
        --region $AWS_REGION &>/dev/null
    echo -e "  ✓ ${GREEN}CodeBuild project updated${NC}"
fi

# Clean up temp files
rm -f /tmp/codebuild-*.json

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. If using GitHub, connect CodeBuild to your GitHub account:"
echo "   - Go to AWS Console > CodeBuild > $CODEBUILD_PROJECT_NAME"
echo "   - Click 'Edit' > 'Source' > Connect to GitHub"
echo "   - Or set up GitHub webhook manually"
echo ""
echo "2. Trigger a build:"
echo "   aws codebuild start-build --project-name $CODEBUILD_PROJECT_NAME --region $AWS_REGION"
echo ""
echo "3. Monitor build progress:"
echo "   aws codebuild batch-get-builds --ids \$(aws codebuild list-builds-for-project --project-name $CODEBUILD_PROJECT_NAME --region $AWS_REGION --query 'ids[0]' --output text) --region $AWS_REGION"
echo ""
echo "4. Or use AWS Console:"
echo "   https://console.aws.amazon.com/codesuite/codebuild/projects/$CODEBUILD_PROJECT_NAME?region=$AWS_REGION"
echo ""
echo "ECR Repositories created:"
for repo in "${REPOS[@]}"; do
    echo "  - $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$repo"
done
echo ""
