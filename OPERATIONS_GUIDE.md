# Romanian Personas Agent - Operations Guide

**Last Updated**: March 5, 2026
**Purpose**: Prevent common deployment issues and ensure smooth operations

## Table of Contents

1. [Critical Rules](#critical-rules)
2. [Architecture Overview](#architecture-overview)
3. [Deployment Checklist](#deployment-checklist)
4. [Common Issues & Solutions](#common-issues--solutions)
5. [Testing Procedures](#testing-procedures)
6. [Troubleshooting Guide](#troubleshooting-guide)

---

## Critical Rules

### 🚨 ALWAYS Follow These Rules

#### 1. **Test Changes Locally Before Committing**
- **Why**: AWS builds take 5-10 minutes; local testing takes seconds
- **How**:
  ```bash
  # For Docker changes
  docker build -t test-image -f Dockerfile .
  docker run -p 8080:8080 test-image

  # For code changes
  python -m pytest tests/
  ```

#### 2. **Verify AWS Resource Mappings Before Deployment**
- **Why**: Mismatched ports, paths, or environment variables cause silent failures
- **Critical Mappings to Check**:
  - ALB listener rules → target group ports → container ports
  - Environment variable names in: `.env` ↔ `config.py` ↔ task definitions
  - Image tags in: `buildspec.yml` → ECR → task definitions
  - Service discovery names: Code expects `api.us-east-1.compute.internal` format

#### 3. **Always Check ECS Task Health After Deployment**
- **Why**: Tasks can fail health checks silently; ALB shows "healthy" but uses stale task
- **How**:
  ```bash
  aws ecs describe-services --cluster personas-marketplace --services SERVICE_NAME \
    --query 'services[0].[runningCount,desiredCount,deployments[0].rolloutState]'
  ```

#### 4. **Docker Alpine Images Need Explicit Dependencies**
- **Why**: Alpine is minimal; missing `curl`, `bash`, etc. cause health check failures
- **Common Additions Needed**:
  ```dockerfile
  RUN apk add --no-cache curl bash
  ```

#### 5. **Image Caching Issues: Use Specific Tags for Updates**
- **Why**: ECS may pull cached `:latest` even after new push
- **Solution**:
  - Build with both `:latest` and `:$GIT_SHA` tags
  - Force redeploy: `--force-new-deployment`
  - Wait for old tasks to drain (check `runningCount`)

#### 6. **Never Deploy Without Checking Build Logs**
- **Why**: Build can "succeed" but produce broken images
- **How**:
  ```bash
  aws codebuild batch-get-builds --ids BUILD_ID \
    --query 'builds[0].phases[?phaseStatus==`FAILED`]'
  ```

#### 7. **Backend API Response Format Must Match UI Expectations**
- **Why**: UI breaks silently with undefined values
- **Example Issue**: API returns `display_name`, UI expects `name`
- **Solution**: Define strict contracts; use Pydantic schemas

#### 8. **Health Check Commands Must Match Container Runtime**
- **Why**: Wrong command = failed health checks = task restart loop
- **Examples**:
  - FastAPI: `curl -f http://localhost:8000/health`
  - Node.js: `curl -f http://localhost:3000/api/health`
  - http-server (static): `wget -q -O /dev/null http://localhost:3001`

#### 9. **ALB Path Routing Requires Base Path Configuration**
- **Why**: `/admin` route won't work if app serves from `/`
- **Solutions**:
  - **Vite/React**: Set `base: '/admin/'` in `vite.config.js`
  - **Next.js**: Set `basePath: '/admin'` in `next.config.js`
  - **Express**: Mount router at `/admin`: `app.use('/admin', router)`

#### 10. **Database and Volume Mounts Must Be Consistent**
- **Why**: API expects DB at one path, task mounts at another → 500 errors
- **Critical Checks**:
  ```python
  # config.py
  DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////mnt/efs/personas.db")

  # Task definition
  "mountPoints": [{"sourceVolume": "efs", "containerPath": "/mnt/efs"}]

  # Startup script
  ln -sf /mnt/efs/personas.db /app/personas.db
  ```

---

## Architecture Overview

### Services and Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Load Balancer               │
│  marketplace-alb-978685696.us-east-1.elb.amazonaws.com      │
└─────────────────────────────────────────────────────────────┘
                             │
       ┌─────────────────────┼────────────────────────┐
       │                     │                        │
       ▼                     ▼                        ▼
   /api/*                /mcp*                   /admin*
       │                     │                        │
       ▼                     ▼                        ▼
┌──────────┐          ┌──────────┐            ┌──────────┐
│   API    │          │   MCP    │            │  Admin   │
│  :8000   │◄─────────│  :8080   │            │   UI     │
└──────────┘          └──────────┘            │  :3001   │
     │                      │                  └──────────┘
     │                      │
     ▼                      ▼
┌──────────────────────────────────┐
│      EFS Persistent Storage      │
│  /mnt/efs/personas.db            │
│  /mnt/efs/chroma_db/             │
│  /mnt/efs/data/                  │
└──────────────────────────────────┘
```

### Port Mappings

| Service        | Container Port | Target Group Port | ALB Path     |
|----------------|----------------|-------------------|--------------|
| API            | 8000           | 8000              | `/api/*`     |
| MCP Server     | 8080           | 8080              | `/mcp*`      |
| Debate UI      | 3000           | 3000              | `/` (default)|
| Admin UI       | 3001           | 3001              | `/admin*`    |

### Environment Variables Matrix

| Variable              | API | MCP | Worker | Debate UI | Admin UI |
|----------------------|-----|-----|--------|-----------|----------|
| `DATABASE_URL`       | ✓   | ✗   | ✓      | ✗         | ✗        |
| `CHROMA_PERSIST_DIR` | ✓   | ✓   | ✓      | ✗         | ✗        |
| `ANTHROPIC_API_KEY`  | ✓   | ✓   | ✓      | ✗         | ✗        |
| `OPENAI_API_KEY`     | ✓   | ✓   | ✓      | ✗         | ✗        |
| `ADMIN_PASSWORD`     | ✓   | ✗   | ✗      | ✗         | ✗        |
| `MCP_SERVER_URL`     | ✗   | ✗   | ✗      | ✓         | ✗        |
| `FASTAPI_URL`        | ✗   | ✗   | ✗      | ✓         | ✓        |

### Service Discovery Names

- **API**: `api.us-east-1.compute.internal:8000`
- **MCP**: `mcp.us-east-1.compute.internal:8080`
- **Redis** (removed): Previously `redis.us-east-1.compute.internal:6379`

---

## Deployment Checklist

### Pre-Deployment (Local)

- [ ] All tests pass: `pytest tests/`
- [ ] Docker images build successfully: `docker build -f Dockerfile .`
- [ ] Health check commands work in container:
  ```bash
  docker run -d --name test IMAGE
  docker exec test curl -f http://localhost:PORT/health
  docker rm -f test
  ```
- [ ] Environment variables match across:
  - [ ] `.env` file
  - [ ] `config.py`
  - [ ] `aws/task-definitions/*.json`
- [ ] Image tags in `buildspec.yml` match repository names in ECR

### Deployment

1. **Commit and Push**
   ```bash
   git add .
   git commit -m "Clear description of changes"
   git push origin main
   ```

2. **Trigger Build**
   ```bash
   aws codebuild start-build --project-name romanian-personas-agent \
     --region us-east-1
   ```

3. **Monitor Build** (~5-10 min)
   ```bash
   # Get build ID from previous command
   aws codebuild batch-get-builds --ids BUILD_ID \
     --query 'builds[0].buildStatus'
   ```

4. **Verify Image Push**
   ```bash
   aws ecr describe-images --repository-name marketplace-SERVICE \
     --query 'sort_by(imageDetails, &imagePushedAt)[-1].imagePushedAt'
   ```

5. **Force Service Update**
   ```bash
   aws ecs update-service \
     --cluster personas-marketplace \
     --service marketplace-SERVICE \
     --force-new-deployment \
     --region us-east-1
   ```

6. **Wait for Health Checks** (~2-3 min)
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn TARGET_GROUP_ARN \
     --query 'TargetHealthDescriptions[0].TargetHealth.State'
   ```

### Post-Deployment Validation

- [ ] All services show `runningCount == desiredCount`
- [ ] Target groups show `healthy` status
- [ ] Smoke test each endpoint:
  ```bash
  curl http://ALB_DNS/api/health  # Should return 200
  curl http://ALB_DNS/mcp/health   # Should return 200
  curl http://ALB_DNS/            # Should return debate UI HTML
  curl http://ALB_DNS/admin       # Should return admin UI HTML
  ```
- [ ] Check logs for errors:
  ```bash
  aws logs tail /ecs/personas-marketplace --since 5m
  ```

---

## Common Issues & Solutions

### Issue 1: ECS Task Fails Health Checks (Exit Code 137)

**Symptoms**:
- Service shows `runningCount: 0`, `desiredCount: 1`
- Task events: "Task failed container health checks"
- Container exit code: 137 (SIGKILL)

**Root Causes**:
1. Health check command not found (e.g., `curl` missing in alpine)
2. Health check URL incorrect
3. Application not starting within `startPeriod`

**Solution**:
```dockerfile
# Add health check dependencies
RUN apk add --no-cache curl
```

```json
// Verify health check matches app
{
  "healthCheck": {
    "command": ["CMD-SHELL", "curl -f http://localhost:PORT/health || exit 1"],
    "startPeriod": 60  // Increase if app takes longer to start
  }
}
```

### Issue 2: ALB Returns 404 for Correct Path

**Symptoms**:
- `curl http://ALB/admin` returns 404
- Target group shows healthy
- Service is running

**Root Causes**:
1. App serves from `/` but ALB forwards `/admin` → app receives `/admin` but has no route
2. Static assets use absolute paths (`/assets/`) instead of relative (`./assets/`)

**Solution**:
```javascript
// vite.config.js
export default defineConfig({
  base: '/admin/',  // Must match ALB path
  // ...
})
```

### Issue 3: API Returns Data, But UI Shows "undefined"

**Symptoms**:
- API endpoint returns 200 with data
- Browser console shows `undefined` for persona names

**Root Causes**:
- Field name mismatch: API returns `display_name`, UI expects `name`
- Format mismatch: API returns array `{personas: [...]}`, UI expects dict `{id: {...}}`

**Solution**:
```python
# Define explicit transformation in API
return {
    p.persona_id: {
        "name": p.display_name,  # Transform field name
        "title": f"{p.birth_year}-{p.death_year}",
        "color": p.color
    }
    for p in personas
}
```

### Issue 4: Build Succeeds But Breaks Functionality

**Symptoms**:
- CodeBuild shows `SUCCEEDED`
- New features don't work
- Old features broken

**Root Causes**:
- `buildspec.yml` out of sync with actual services (e.g., still building Redis)
- Missing dependencies in Dockerfile
- Environment variables not propagated

**Solution**:
1. Review `buildspec.yml` against actual architecture
2. Test each Dockerfile locally before committing
3. Use `docker-compose` for integration testing

### Issue 5: Secrets Manager Secret Doesn't Exist

**Symptoms**:
- Task fails to start
- Error: "Error retrieving secret: ResourceNotFoundException"

**Root Causes**:
- Task definition references secret that wasn't created
- Secret ARN typo

**Solution**:
```bash
# Create missing secret
aws secretsmanager create-secret \
  --name marketplace/SECRET_NAME \
  --secret-string "SECRET_VALUE" \
  --region us-east-1

# Update task definition to use correct ARN
```

### Issue 6: ECS Image Caching - New Build Not Deploying

**Symptoms**:
- Build succeeds, push succeeds
- Service updated, but behavior unchanged
- Image digest hasn't changed

**Root Causes**:
- ECS pulled `:latest` and cached it
- New `:latest` pushed but not pulled

**Solution**:
```bash
# Force service to pull new image
aws ecs update-service \
  --cluster personas-marketplace \
  --service SERVICE_NAME \
  --force-new-deployment \
  --region us-east-1

# Wait for old task to drain
aws ecs describe-services --cluster personas-marketplace --services SERVICE_NAME \
  --query 'services[0].deployments' --output table
```

---

## Testing Procedures

### Local Testing (Before Git Push)

#### 1. Test Individual Docker Images
```bash
# Build image
docker build -f Dockerfile.api -t test-api .

# Run with environment
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="sqlite:////tmp/test.db" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  test-api

# Test health endpoint
curl http://localhost:8000/health

# Test actual functionality
curl -X POST http://localhost:8000/api/personas \
  -H "Authorization: Basic $(echo -n admin:password | base64)" \
  -H "Content-Type: application/json" \
  -d '{"persona_id":"test","display_name":"Test",...}'
```

#### 2. Test Multi-Service Interactions
```bash
# Use docker-compose for local testing
docker-compose up

# Test cross-service communication
curl http://localhost:3000/api/personas  # Debate UI → API
```

#### 3. Test Health Check Commands
```bash
# Start container
docker run -d --name health-test IMAGE

# Run health check command manually
docker exec health-test curl -f http://localhost:PORT/health

# Check exit code (0 = success)
echo $?

# Clean up
docker rm -f health-test
```

### AWS Testing (After Deployment)

#### 1. Service Health Checks
```bash
# Check all services
for svc in marketplace-api marketplace-mcp marketplace-debate-ui marketplace-admin-ui; do
  echo "=== $svc ==="
  aws ecs describe-services --cluster personas-marketplace --services $svc \
    --query 'services[0].[runningCount,desiredCount,deployments[0].rolloutState]' \
    --output table
done
```

#### 2. Target Group Health
```bash
# Get all target groups
aws elbv2 describe-target-groups \
  --names marketplace-api-tg marketplace-mcp-tg marketplace-debate-tg marketplace-admin-tg \
  --query 'TargetGroups[*].[TargetGroupName,HealthCheckPath,HealthCheckPort]' \
  --output table

# Check health of each
for tg in marketplace-api-tg marketplace-mcp-tg marketplace-debate-tg marketplace-admin-tg; do
  echo "=== $tg ==="
  aws elbv2 describe-target-health \
    --target-group-arn $(aws elbv2 describe-target-groups --names $tg \
      --query 'TargetGroups[0].TargetGroupArn' --output text) \
    --query 'TargetHealthDescriptions[0].TargetHealth' --output json
done
```

#### 3. End-to-End Functionality Tests
```bash
ALB_DNS="marketplace-alb-978685696.us-east-1.elb.amazonaws.com"

# Test 1: List personas (no auth)
curl -s http://$ALB_DNS/api/personas | jq 'keys'

# Test 2: Create persona (with auth)
curl -s -u admin:Romanian2026! \
  -X POST http://$ALB_DNS/api/personas \
  -H "Content-Type: application/json" \
  -d '{...}' | jq '.status'

# Test 3: MCP ask_persona
curl -s -X POST http://$ALB_DNS/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ask_persona","arguments":{"query":"Test","persona":"eminescu"}}}' \
  | jq '.result.content[0].text[:100]'

# Test 4: Debate UI
curl -s http://$ALB_DNS/ | grep -o "<title>.*</title>"

# Test 5: Admin UI
curl -s http://$ALB_DNS/admin | grep -o "<title>.*</title>"
```

#### 4. Log Analysis
```bash
# Tail logs for errors
aws logs tail /ecs/personas-marketplace --since 5m --format short \
  | grep -i error

# Check specific service
aws logs tail /ecs/personas-marketplace --since 5m --format short \
  | grep "debate-ui" | tail -20
```

---

## Troubleshooting Guide

### Debugging Methodology

1. **Check Service Status**
   ```bash
   aws ecs describe-services --cluster personas-marketplace \
     --services SERVICE_NAME
   ```

2. **Check Task Status**
   ```bash
   # Get running tasks
   aws ecs list-tasks --cluster personas-marketplace \
     --service-name SERVICE_NAME

   # Describe task
   aws ecs describe-tasks --cluster personas-marketplace \
     --tasks TASK_ARN
   ```

3. **Check Stopped Tasks**
   ```bash
   # Get recently stopped tasks
   aws ecs list-tasks --cluster personas-marketplace \
     --service-name SERVICE_NAME --desired-status STOPPED

   # Get stop reason
   aws ecs describe-tasks --cluster personas-marketplace --tasks TASK_ARN \
     --query 'tasks[0].[stoppedReason,containers[0].exitCode]'
   ```

4. **Check Logs**
   ```bash
   aws logs tail /ecs/personas-marketplace --since 10m --format short \
     --filter-pattern "SERVICE_NAME"
   ```

5. **Check Target Health**
   ```bash
   aws elbv2 describe-target-health --target-group-arn TG_ARN
   ```

### Quick Fixes

**Service stuck in "draining":**
```bash
# Drain timeout is 300s by default
# Check deployment progress
aws ecs describe-services --cluster personas-marketplace --services SERVICE_NAME \
  --query 'services[0].deployments[*].[status,runningCount,desiredCount]'
```

**Task immediately stops after starting:**
```bash
# Check task definition
aws ecs describe-task-definition --task-definition TASK_DEF_NAME \
  --query 'taskDefinition.containerDefinitions[0].[image,environment,healthCheck]'

# Check execution role permissions
aws iam get-role --role-name ROLE_NAME
```

**502/503 from ALB:**
```bash
# Check if targets are healthy
aws elbv2 describe-target-health --target-group-arn TG_ARN

# If unhealthy, check health check config
aws elbv2 describe-target-groups --target-group-arns TG_ARN \
  --query 'TargetGroups[0].[HealthCheckPath,HealthCheckPort,HealthCheckProtocol]'
```

---

## Admin Credentials

### Access

- **Admin UI**: `http://marketplace-alb-978685696.us-east-1.elb.amazonaws.com/admin`
- **Username**: `admin`
- **Password**: `Romanian2026!` (stored in AWS Secrets Manager: `marketplace/admin_password`)

### Retrieving Password

```bash
aws secretsmanager get-secret-value \
  --secret-id marketplace/admin_password \
  --query 'SecretString' --output text
```

---

## Maintenance Tasks

### Updating Admin Password

```bash
NEW_PASS=$(openssl rand -base64 16 | tr -d '=+/' | cut -c1-20)

aws secretsmanager update-secret \
  --secret-id marketplace/admin_password \
  --secret-string "$NEW_PASS"

# Restart API service to pick up new password
aws ecs update-service --cluster personas-marketplace \
  --service marketplace-api --force-new-deployment
```

### Cleaning Up Stopped Tasks

```bash
# ECS automatically cleans up after ~1 hour
# Manual cleanup not usually needed

# If needed, describe and note task IDs, then they'll auto-cleanup
aws ecs list-tasks --cluster personas-marketplace --desired-status STOPPED
```

### Rotating API Keys

```bash
# Update Secrets Manager
aws secretsmanager update-secret \
  --secret-id marketplace/anthropic_key \
  --secret-string "NEW_KEY"

# Restart services that use it
for svc in marketplace-api marketplace-mcp marketplace-worker; do
  aws ecs update-service --cluster personas-marketplace \
    --service $svc --force-new-deployment
done
```

---

## Key Lessons Learned

1. **Docker Alpine is minimal** - Always explicitly install health check tools (`curl`, `wget`)
2. **ECS caches `:latest` aggressively** - Use `--force-new-deployment` or git SHA tags
3. **Health checks must match container capabilities** - Test commands in running container first
4. **Base paths matter for ALB routing** - Configure app base path to match ALB rule
5. **API response format must match UI expectations** - Define strict contracts, transform as needed
6. **Field name mismatches cause silent failures** - Use consistent naming or explicit transformation
7. **Secrets Manager secrets must exist** - Create secrets before referencing in task definitions
8. **Environment variables must match everywhere** - Keep `.env`, `config.py`, and task defs in sync
9. **Build success ≠ functional deployment** - Always test after deployment
10. **Redis was removed** - Don't forget to update `buildspec.yml` when removing services

---

## Contact / Support

For issues or questions:
- Review this guide first
- Check AWS CloudWatch logs: `/ecs/personas-marketplace`
- Check ECS service events
- Check CodeBuild build logs

---

**End of Operations Guide**
