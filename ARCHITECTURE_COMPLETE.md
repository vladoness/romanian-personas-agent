# Romanian Personas Agent - Complete Architecture Reference

**Version**: 2.0
**Last Updated**: March 9, 2026
**Purpose**: Single source of truth for all architectural decisions and mappings

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Service Mappings Matrix](#service-mappings-matrix)
3. [Data Flow Diagrams](#data-flow-diagrams)
4. [Environment Variables Reference](#environment-variables-reference)
5. [ALB Routing Configuration](#alb-routing-configuration)
6. [Task Definition Standards](#task-definition-standards)
7. [Common Anti-Patterns](#common-anti-patterns)
8. [Deployment Decision Tree](#deployment-decision-tree)
9. [Testing Checklist](#testing-checklist)

---

## Architecture Overview

### High-Level Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                     Internet (Users)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│            Application Load Balancer (ALB)                       │
│  marketplace-alb-978685696.us-east-1.elb.amazonaws.com          │
│                                                                   │
│  Priority-based routing:                                         │
│  1. /api/debate* → Debate UI                                     │
│  2. /mcp*        → MCP Server                                    │
│  3. /admin*      → Admin UI                                      │
│  5. /api/*       → API                                           │
│  default: /*     → Debate UI                                     │
└────────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┬───────────────┐
        ▼                    ▼                    ▼               ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐  ┌──────────────┐
│  Debate UI   │    │     API      │    │     MCP      │  │  Admin UI    │
│  Port 3000   │    │  Port 8000   │    │  Port 8080   │  │  Port 3001   │
│              │    │              │    │              │  │              │
│ Node.js      │    │ FastAPI      │    │ FastMCP      │  │ Node.js      │
│ Express      │    │ Python       │    │ Python       │  │ (static)     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘  └──────────────┘
       │                   │                   │
       │ calls ALB /mcp    │ reads/writes     │ queries
       │ calls ALB /api    │                  │
       └───────────────────┼──────────────────┘
                           ▼
              ┌────────────────────────┐
              │  EFS Persistent Data   │
              │  /mnt/efs/             │
              │                        │
              │  ├─ personas.db        │ ← SQLite
              │  ├─ chroma_db/         │ ← Vector DB
              │  └─ data/              │ ← Source files
              └────────────────────────┘
```

### Key Architectural Decisions

1. **No Service Discovery**: Services communicate via ALB, not AWS Cloud Map
   - **Why**: Simpler to debug, ALB handles load balancing
   - **Trade-off**: Slight latency increase, but more visibility

2. **Centralized Routing**: ALB handles all routing decisions
   - **Why**: Single configuration point, easier to audit
   - **Pattern**: Path-based routing with priority ordering

3. **Shared EFS**: All services access same persistent storage
   - **Why**: Simplified data sharing, no S3 sync needed
   - **Mount**: `/mnt/efs` in all containers

4. **Secrets Manager**: All sensitive data in AWS Secrets Manager
   - **Why**: Auditable, rotatable, encrypted
   - **Access**: Via task execution role

---

## Service Mappings Matrix

### Complete Service Reference

| Service | Container Port | Target Group Port | ALB Path Pattern | Priority | Health Check Path | Image Repo |
|---------|---------------|-------------------|------------------|----------|-------------------|------------|
| API | 8000 | 8000 | `/api/*` | 5 | `/health` | `marketplace-api` |
| MCP Server | 8080 | 8080 | `/mcp*` | 2 | `/health` | `marketplace-mcp` |
| Debate UI | 3000 | 3000 | `/api/debate*` <br> `/` (default) | 1 <br> default | `/api/health` | `marketplace-debate-ui` |
| Admin UI | 3001 | 3001 | `/admin*` | 3 | `/health` | `marketplace-admin-ui` |

### Service Dependencies

```
Debate UI depends on:
  → MCP Server (via ALB /mcp)
  → API (via ALB /api/personas)
  → TAVILY_API_KEY (for web search)
  → MCP_API_KEY (for authentication)

Admin UI depends on:
  → API (via ALB /api)

API depends on:
  → EFS (personas.db at /mnt/efs/personas.db)
  → ANTHROPIC_API_KEY
  → OPENAI_API_KEY
  → ADMIN_PASSWORD

MCP Server depends on:
  → EFS (chroma_db at /mnt/efs/chroma_db)
  → ANTHROPIC_API_KEY
  → OPENAI_API_KEY
  → MCP_API_KEY (optional)
```

---

## Data Flow Diagrams

### Debate Request Flow

```
User Browser
  │
  │ POST /api/debate
  │ { question, personas: ["cioran"] }
  │
  ▼
ALB (marketplace-alb-978685696...)
  │
  │ Route: /api/debate* → debate-ui target group (priority 1)
  │
  ▼
Debate UI (Node.js server on port 3000)
  │
  ├─ 1. Fetch personas from API
  │    │ GET http://ALB/api/personas?format=array
  │    │
  │    ▼ (routes to API via priority 5)
  │    API returns: { personas: [...], count: 5 }
  │
  ├─ 2. Optional: Search web with Tavily
  │    │ Uses TAVILY_API_KEY env var
  │    │
  │    ▼
  │    External API call (if TAVILY_API_KEY set)
  │
  ├─ 3. Call MCP for each persona
  │    │ POST http://ALB/mcp
  │    │ Headers:
  │    │   - Content-Type: application/json
  │    │   - Accept: application/json, text/event-stream
  │    │   - Authorization: Bearer ${MCP_API_KEY}
  │    │ Body:
  │    │   {
  │    │     "jsonrpc": "2.0",
  │    │     "method": "tools/call",
  │    │     "params": {
  │    │       "name": "ask_persona",
  │    │       "arguments": {
  │    │         "query": "...",
  │    │         "persona": "cioran"
  │    │       }
  │    │     }
  │    │   }
  │    │
  │    ▼ (routes to MCP via priority 2)
  │    MCP Server
  │      │
  │      ├─ Auth check (if MCP_API_KEY set)
  │      ├─ Query ChromaDB at /mnt/efs/chroma_db
  │      ├─ Call Claude Opus 4.6 for synthesis
  │      └─ Return response
  │
  └─ 4. Stream responses to browser
       │ Server-Sent Events (SSE)
       │
       ▼
     User receives responses in real-time
```

### Admin Persona Creation Flow

```
User → http://ALB/admin (routes to Admin UI)
  │
  │ 1. Login (admin / Romanian2026!)
  │    Browser sends Basic Auth
  │
  ▼
Admin UI (static files served from Node.js on port 3001)
  │
  │ 2. Submit persona form
  │    POST /api/personas
  │    Headers: Authorization: Basic base64(admin:password)
  │    Body: { persona_id, display_name, ... }
  │
  ▼
ALB routes to API (priority 5: /api/*)
  │
  ▼
API (FastAPI)
  │
  ├─ Verify admin credentials
  │  └─ Check ADMIN_PASSWORD from Secrets Manager
  │
  ├─ Create persona in SQLite
  │  └─ Write to /mnt/efs/personas.db
  │
  ├─ Create data directories
  │  └─ mkdir /mnt/efs/data/{persona_id}/{works,quotes,profile}
  │
  └─ Return success
     │
     ▼
Admin UI → File upload step
  │
  │ 3. Upload files
  │    POST /api/personas/{id}/upload
  │    multipart/form-data
  │
  ▼
API saves files to EFS
  │
  │ 4. Trigger ingestion
  │    POST /api/personas/{id}/ingest
  │
  ▼
Celery Worker (async)
  │
  ├─ Read files from /mnt/efs/data/{persona_id}/
  ├─ Chunk documents
  ├─ Generate embeddings (OpenAI API)
  ├─ Store in ChromaDB at /mnt/efs/chroma_db/
  └─ Update persona status: "active"
     │
     ▼
Admin UI polls status every 3s
  └─ Shows progress bars until complete
```

---

## Environment Variables Reference

### Complete Environment Matrix

| Variable | API | MCP | Debate UI | Admin UI | Worker | Source | Notes |
|----------|-----|-----|-----------|----------|--------|--------|-------|
| **ANTHROPIC_API_KEY** | ✓ | ✓ | ✗ | ✗ | ✓ | Secrets Manager | For Claude synthesis |
| **OPENAI_API_KEY** | ✓ | ✓ | ✗ | ✗ | ✓ | Secrets Manager | For embeddings |
| **ADMIN_PASSWORD** | ✓ | ✗ | ✗ | ✗ | ✗ | Secrets Manager | For admin endpoints |
| **MCP_API_KEY** | ✗ | ✓ | ✓ | ✗ | ✗ | Secrets Manager | For MCP auth (optional) |
| **TAVILY_API_KEY** | ✗ | ✗ | ✓ | ✗ | ✗ | Secrets Manager | For web search (optional) |
| **DATABASE_URL** | ✓ | ✗ | ✗ | ✗ | ✓ | ENV | `sqlite:////mnt/efs/personas.db` |
| **CHROMA_PERSIST_DIR** | ✓ | ✓ | ✗ | ✗ | ✓ | ENV | `/mnt/efs/chroma_db` |
| **DATA_DIR** | ✓ | ✗ | ✗ | ✗ | ✓ | ENV | `/mnt/efs/data` |
| **MCP_SERVER_URL** | ✗ | ✗ | ✓ | ✗ | ✗ | ENV | `http://ALB_DNS` (NO /mcp suffix!) |
| **FASTAPI_URL** | ✗ | ✗ | ✓ | ✗ | ✗ | ENV | `http://ALB_DNS/api` |
| **SYNTHESIS_MODEL** | ✓ | ✓ | ✗ | ✗ | ✓ | ENV | `claude-opus-4-6` |
| **EMBEDDING_MODEL** | ✓ | ✓ | ✗ | ✗ | ✓ | ENV | `text-embedding-3-small` |
| **REDIS_URL** | ✓ | ✗ | ✗ | ✗ | ✓ | ENV | **REMOVED** (no longer used) |

### Critical Environment Variable Rules

1. **MCP_SERVER_URL must NOT include /mcp**
   - ✅ Correct: `http://marketplace-alb-978685696.us-east-1.elb.amazonaws.com`
   - ❌ Wrong: `http://marketplace-alb-978685696.us-east-1.elb.amazonaws.com/mcp`
   - **Why**: Code appends `/mcp`, so full URL becomes `${MCP_SERVER_URL}/mcp`

2. **FASTAPI_URL must include /api**
   - ✅ Correct: `http://marketplace-alb-978685696.us-east-1.elb.amazonaws.com/api`
   - ❌ Wrong: `http://marketplace-alb-978685696.us-east-1.elb.amazonaws.com`
   - **Why**: Code uses it directly without appending path

3. **DATABASE_URL must use 4 slashes for absolute paths**
   - ✅ Correct: `sqlite:////mnt/efs/personas.db`
   - ❌ Wrong: `sqlite:///mnt/efs/personas.db`
   - **Why**: `sqlite:///` = relative, `sqlite:////` = absolute

4. **Secrets vs Environment Variables**
   - **Secrets Manager**: API keys, passwords (rotatable, auditable)
   - **Environment Variables**: Paths, URLs, model names (static config)

---

## ALB Routing Configuration

### Current Routing Rules (MUST MAINTAIN ORDER)

```
Priority 1: /api/debate* → marketplace-debate-tg
  │ Why first: More specific than /api/*
  │ Handles: Debate streaming endpoint
  │ ARN: ...afb900308df60e6a

Priority 2: /mcp* → marketplace-mcp-tg
  │ Handles: MCP server requests
  │ ARN: ...de2ed3a8891b79df

Priority 3: /admin* → marketplace-admin-tg
  │ Handles: Admin UI (static files)
  │ ARN: ...af8fcb922bbb7999

Priority 5: /api/* → marketplace-api-tg
  │ Why after /api/debate: Less specific catch-all
  │ Handles: All other API endpoints
  │ ARN: ...afb900308df60e6a

Default: /* → marketplace-debate-tg
  │ Handles: Debate UI frontend
  │ ARN: ...b984de971dc6d093
```

### Common ALB Routing Mistakes

❌ **Mistake 1**: Making `/api/*` priority 1
- **Problem**: Catches `/api/debate` before it reaches debate UI
- **Fix**: Specific paths must have lower priority numbers

❌ **Mistake 2**: Forgetting to add new specific paths
- **Problem**: `/api/new-endpoint` gets caught by wrong service
- **Fix**: Always add specific routes with appropriate priority

❌ **Mistake 3**: Using overlapping patterns
- **Problem**: `/api*` and `/api/*` both match
- **Fix**: Use consistent patterns with trailing `*`

### ALB Rule Management Commands

```bash
# List current rules
aws elbv2 describe-rules \
  --listener-arn arn:aws:elasticloadbalancing:us-east-1:914357406961:listener/app/marketplace-alb/b0e5a3f6461be8bf/78c2a67fdd357eaf \
  --region us-east-1 \
  --query 'Rules[?Priority!=`default`].[Priority,Conditions[0].Values[0],Actions[0].TargetGroupArn]' \
  --output table

# Add new rule
aws elbv2 create-rule \
  --listener-arn LISTENER_ARN \
  --priority N \
  --conditions Field=path-pattern,Values='/new/path*' \
  --actions Type=forward,TargetGroupArn=TARGET_GROUP_ARN

# Modify priorities
aws elbv2 set-rule-priorities \
  --rule-priorities \
    "RuleArn=RULE1_ARN,Priority=1" \
    "RuleArn=RULE2_ARN,Priority=2"
```

---

## Task Definition Standards

### Required Task Definition Elements

Every task definition MUST include:

1. **Image Tag Strategy**: Use `:latest` for auto-updates
   ```json
   {
     "image": "914357406961.dkr.ecr.us-east-1.amazonaws.com/SERVICE:latest"
   }
   ```
   ❌ Don't use: Git SHA tags (prevents auto-updates on force-new-deployment)

2. **Health Check**: Must match container capabilities
   ```json
   {
     "healthCheck": {
       "command": ["CMD-SHELL", "curl -f http://localhost:PORT/health || exit 1"],
       "interval": 30,
       "timeout": 5,
       "retries": 3,
       "startPeriod": 60
     }
   }
   ```
   ⚠️ Alpine images need: `RUN apk add --no-cache curl`

3. **EFS Mount**: For services needing persistent data
   ```json
   {
     "mountPoints": [
       {
         "sourceVolume": "efs",
         "containerPath": "/mnt/efs",
         "readOnly": false
       }
     ]
   }
   ```

4. **Logging**: CloudWatch Logs configuration
   ```json
   {
     "logConfiguration": {
       "logDriver": "awslogs",
       "options": {
         "awslogs-group": "/ecs/personas-marketplace",
         "awslogs-region": "us-east-1",
         "awslogs-stream-prefix": "service-name"
       }
     }
   }
   ```

### Environment vs Secrets Decision Matrix

| Data Type | Use Environment | Use Secrets |
|-----------|----------------|-------------|
| API Keys | ✗ | ✓ |
| Passwords | ✗ | ✓ |
| URLs | ✓ | ✗ |
| Paths | ✓ | ✗ |
| Model names | ✓ | ✗ |
| Port numbers | ✓ | ✗ |

---

## Common Anti-Patterns

### Anti-Pattern 1: Service Discovery Without Services

**Symptom**: `getaddrinfo ENOTFOUND service.us-east-1.compute.internal`

**Root Cause**: Code expects AWS Cloud Map service discovery, but services don't exist

**Fix**: Use ALB URLs instead
```javascript
// ❌ Wrong
const MCP_URL = "http://mcp.us-east-1.compute.internal:8080";

// ✅ Correct
const MCP_URL = "http://marketplace-alb-978685696.us-east-1.elb.amazonaws.com";
```

---

### Anti-Pattern 2: Path Concatenation Errors

**Symptom**: 404 errors when calling services

**Root Cause**: URL + path results in double paths

**Examples**:
```javascript
// ❌ Wrong
MCP_SERVER_URL = "http://alb/mcp"
code: axios.post(`${MCP_SERVER_URL}/mcp`, ...)
result: http://alb/mcp/mcp → 404!

// ✅ Correct
MCP_SERVER_URL = "http://alb"  // No /mcp!
code: axios.post(`${MCP_SERVER_URL}/mcp`, ...)
result: http://alb/mcp → ✓
```

**Rule**: Base URLs should NOT include the path that code will append

---

### Anti-Pattern 3: Missing Authorization Headers

**Symptom**: 401 Unauthorized errors

**Root Cause**: Environment variable exists but code doesn't use it

**Fix**: Always check AND use the env var
```javascript
// ✗ Wrong - has env var but doesn't use it
const headers = {
  'Content-Type': 'application/json'
};

// ✓ Correct
const headers = {
  'Content-Type': 'application/json'
};
if (process.env.MCP_API_KEY) {
  headers['Authorization'] = `Bearer ${process.env.MCP_API_KEY}`;
}
```

---

### Anti-Pattern 4: Image Tag Doesn't Update

**Symptom**: Code changes don't appear after deployment

**Root Cause**: Task definition uses specific git SHA, not `:latest`

**Fix**: Always use `:latest` in task definitions
```json
// ❌ Wrong - locks to specific build
{
  "image": "914357406961.dkr.ecr.us-east-1.amazonaws.com/service:1352742d322fa..."
}

// ✅ Correct - auto-updates
{
  "image": "914357406961.dkr.ecr.us-east-1.amazonaws.com/service:latest"
}
```

---

### Anti-Pattern 5: Health Check Command Not Found

**Symptom**: Tasks fail health checks, exit code 137

**Root Cause**: Alpine images don't include `curl`/`wget`/`bash`

**Fix**: Install dependencies in Dockerfile
```dockerfile
# ✗ Wrong
FROM node:18-alpine
# Health check will fail - curl not found

# ✓ Correct
FROM node:18-alpine
RUN apk add --no-cache curl bash
```

---

## Deployment Decision Tree

### Before Making Changes

```
START: I need to change...

├─ Code (src/, agent/, api/, etc.)
│  ├─ Test locally first ✓
│  │  └─ docker build && docker run
│  │     └─ curl health endpoint
│  │        └─ Test functionality
│  │           └─ Passes? → Commit
│  │              └─ Fails? → Fix and retry
│  │
│  ├─ Commit changes
│  ├─ Trigger CodeBuild
│  ├─ Wait for build (8-10 min)
│  ├─ Force service deployment
│  ├─ Wait for health checks (2-3 min)
│  └─ Test endpoints
│
├─ Task Definition (environment, secrets, resources)
│  ├─ Is it environment variables only?
│  │  └─ Update directly in AWS Console → faster
│  ├─ Is it code + environment?
│  │  └─ Update task def template → trigger build
│  └─ Register new revision → Update service
│
├─ ALB Routing
│  ├─ Adding NEW path?
│  │  └─ Create rule with correct priority
│  │     └─ Specific paths BEFORE generic
│  ├─ Modifying priorities?
│  │  └─ Use set-rule-priorities (atomic operation)
│  └─ Test with curl immediately
│
└─ Infrastructure (EFS, Secrets, VPC)
   └─ Use AWS Console (careful!)
      └─ Document changes in ARCHITECTURE.md
```

---

## Testing Checklist

### Pre-Deployment Testing (LOCAL)

- [ ] Docker build succeeds
  ```bash
  docker build -f Dockerfile.SERVICE -t test .
  ```

- [ ] Container starts successfully
  ```bash
  docker run -p PORT:PORT test
  ```

- [ ] Health check works
  ```bash
  docker exec CONTAINER curl -f http://localhost:PORT/health
  ```

- [ ] Environment variables load correctly
  ```bash
  docker run --env-file .env test
  docker exec CONTAINER env | grep KEY_NAME
  ```

- [ ] Functionality works end-to-end
  ```bash
  curl http://localhost:PORT/endpoint
  ```

### Post-Deployment Testing (AWS)

- [ ] Build completed successfully
  ```bash
  aws codebuild batch-get-builds --ids BUILD_ID \
    --query 'builds[0].buildStatus'
  ```

- [ ] Image pushed to ECR
  ```bash
  aws ecr describe-images --repository-name REPO \
    --query 'sort_by(imageDetails, &imagePushedAt)[-1]'
  ```

- [ ] Service deployment completed
  ```bash
  aws ecs describe-services --cluster CLUSTER --services SERVICE \
    --query 'services[0].[runningCount,desiredCount,deployments[0].rolloutState]'
  ```

- [ ] Task using correct revision
  ```bash
  TASK=$(aws ecs list-tasks --cluster CLUSTER --service SERVICE --query 'taskArns[0]' --output text)
  aws ecs describe-tasks --cluster CLUSTER --tasks $TASK \
    --query 'tasks[0].taskDefinitionArn'
  ```

- [ ] Target group healthy
  ```bash
  aws elbv2 describe-target-health --target-group-arn TG_ARN
  ```

- [ ] Endpoint responds correctly
  ```bash
  curl http://ALB_DNS/path
  ```

- [ ] Check CloudWatch logs for errors
  ```bash
  aws logs tail /ecs/personas-marketplace --since 5m --format short
  ```

---

## Quick Reference

### Service URLs

- **ALB**: `http://marketplace-alb-978685696.us-east-1.elb.amazonaws.com`
- **Debate UI**: `http://ALB/`
- **Admin UI**: `http://ALB/admin`
- **API Personas**: `http://ALB/api/personas`
- **Debate Endpoint**: `POST http://ALB/api/debate`
- **MCP Server**: `POST http://ALB/mcp`

### AWS Resource ARNs

- **Cluster**: `arn:aws:ecs:us-east-1:914357406961:cluster/personas-marketplace`
- **ALB**: `arn:aws:elasticloadbalancing:us-east-1:914357406961:loadbalancer/app/marketplace-alb/b0e5a3f6461be8bf`
- **Listener**: `...listener/app/marketplace-alb/.../78c2a67fdd357eaf`

### Admin Credentials

- **Username**: `admin`
- **Password**: `Romanian2026!` (from `marketplace/admin_password` secret)

---

**End of Complete Architecture Reference**
