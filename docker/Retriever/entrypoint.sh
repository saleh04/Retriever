#!/bin/bash
set -e

echo "Running database migrations..."
cd /app/models/db_schemes/Retriever/
alembic upgrade head
cd /app
exec "$@"