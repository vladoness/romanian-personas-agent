# Build stage
FROM public.ecr.aws/docker/library/node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the app (if using build script in package.json)
RUN npm run build 2>/dev/null || echo "No build script found, using src as-is"

# Production stage
FROM public.ecr.aws/docker/library/node:18-alpine

WORKDIR /app

# Install curl and wget for health checks
RUN apk add --no-cache curl wget

# Copy built files from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server.js ./server.js

EXPOSE 3001

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD wget --quiet --tries=1 --spider http://localhost:3001/health || exit 1

# Start custom server that handles /admin routing
CMD ["node", "server.js"]
