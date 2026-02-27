#!/bin/bash

# Start script for Admin UI
# Usage: ./start.sh

echo "Starting Persona Admin UI..."
echo "Available at: http://localhost:3001"
echo ""
echo "Make sure FastAPI backend is running on http://localhost:8000"
echo ""

npm run dev
