#!/bin/bash

# Trigger AWS CodeBuild and monitor progress

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AWS_REGION=${AWS_REGION:-us-east-1}
CODEBUILD_PROJECT_NAME="personas-marketplace-builder"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Triggering CodeBuild${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if project exists
if ! aws codebuild batch-get-projects --names $CODEBUILD_PROJECT_NAME --region $AWS_REGION &>/dev/null; then
    echo -e "${RED}✗ CodeBuild project not found: $CODEBUILD_PROJECT_NAME${NC}"
    echo "Run ./setup-aws-build.sh first"
    exit 1
fi

# Start build
echo -e "${YELLOW}Starting build...${NC}"
BUILD_ID=$(aws codebuild start-build \
    --project-name $CODEBUILD_PROJECT_NAME \
    --region $AWS_REGION \
    --query 'build.id' \
    --output text)

echo -e "${GREEN}✓ Build started${NC}"
echo -e "  Build ID: ${BLUE}$BUILD_ID${NC}"
echo ""

# Extract short build ID for display
SHORT_BUILD_ID=$(echo $BUILD_ID | cut -d':' -f2)

# Monitor build progress
echo -e "${YELLOW}Monitoring build progress...${NC}"
echo "(Press Ctrl+C to stop monitoring, build will continue)"
echo ""

LAST_STATUS=""
START_TIME=$(date +%s)

while true; do
    # Get build info
    BUILD_INFO=$(aws codebuild batch-get-builds \
        --ids $BUILD_ID \
        --region $AWS_REGION \
        --query 'builds[0]')

    STATUS=$(echo $BUILD_INFO | jq -r '.buildStatus')
    PHASE=$(echo $BUILD_INFO | jq -r '.currentPhase // "STARTING"')

    # Show status if changed
    if [ "$STATUS" != "$LAST_STATUS" ]; then
        ELAPSED=$(($(date +%s) - $START_TIME))
        case $STATUS in
            "IN_PROGRESS")
                echo -e "[${ELAPSED}s] ${YELLOW}Status: $STATUS - Phase: $PHASE${NC}"
                ;;
            "SUCCEEDED")
                echo -e "[${ELAPSED}s] ${GREEN}✓ BUILD SUCCEEDED${NC}"
                break
                ;;
            "FAILED"|"FAULT"|"STOPPED"|"TIMED_OUT")
                echo -e "[${ELAPSED}s] ${RED}✗ BUILD FAILED: $STATUS${NC}"
                break
                ;;
        esac
        LAST_STATUS=$STATUS
    fi

    # Wait before next check
    sleep 10
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get final build details
FINAL_INFO=$(aws codebuild batch-get-builds \
    --ids $BUILD_ID \
    --region $AWS_REGION \
    --query 'builds[0]' \
    --output json)

FINAL_STATUS=$(echo $FINAL_INFO | jq -r '.buildStatus')
END_TIME=$(echo $FINAL_INFO | jq -r '.endTime // empty')
DURATION=$(echo $FINAL_INFO | jq -r '.phases[] | select(.phaseStatus != null) | .durationInSeconds' | awk '{s+=$1} END {print s}')

echo "Build ID: $SHORT_BUILD_ID"
echo "Status: $FINAL_STATUS"
echo "Duration: ${DURATION}s (~$((DURATION / 60)) minutes)"
echo ""

if [ "$FINAL_STATUS" = "SUCCEEDED" ]; then
    echo -e "${GREEN}✓ All 6 marketplace images built and pushed to ECR successfully${NC}"
    echo ""
    echo "Images available:"
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo "  1. $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketplace-api:latest"
    echo "  2. $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketplace-mcp:latest"
    echo "  3. $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketplace-worker:latest"
    echo "  4. $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketplace-debate-ui:latest"
    echo "  5. $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketplace-admin-ui:latest"
    echo "  6. $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/marketplace-redis:latest"
    echo ""
    echo "Next steps:"
    echo "  1. Review AWS_MARKETPLACE_DEPLOYMENT.md for ECS setup"
    echo "  2. Create EFS file system and initialize with data"
    echo "  3. Register ECS task definitions"
    echo "  4. Deploy ECS services"
else
    echo -e "${RED}✗ Build failed${NC}"
    echo ""
    echo "View logs:"
    echo "  aws logs tail /aws/codebuild/personas-marketplace --follow --region $AWS_REGION"
    echo ""
    echo "Or in AWS Console:"
    echo "  https://console.aws.amazon.com/codesuite/codebuild/projects/$CODEBUILD_PROJECT_NAME/build/$BUILD_ID?region=$AWS_REGION"
    exit 1
fi

echo ""
