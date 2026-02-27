# Build stage
FROM node:18-alpine AS builder

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
FROM node:18-alpine

WORKDIR /app

# Install a simple HTTP server to serve the static files
RUN npm install -g http-server

# Copy built files from builder or source files
COPY --from=builder /app . .

# Create necessary directories
RUN mkdir -p dist public

EXPOSE 3001

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD wget --quiet --tries=1 --spider http://localhost:3001 || exit 1

# Serve with http-server (serves public/ or src/ as static files)
CMD ["sh", "-c", "test -d dist && http-server dist -p 3001 --cors || http-server src -p 3001 --cors"]
