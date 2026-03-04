#!/bin/bash
set -e

# Create symlink from EFS database to expected location
if [ -f "/mnt/efs/personas.db" ]; then
    echo "Creating symlink: /app/personas.db -> /mnt/efs/personas.db"
    ln -sf /mnt/efs/personas.db /app/personas.db
else
    echo "WARNING: /mnt/efs/personas.db not found"
fi

# Start the API server
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
