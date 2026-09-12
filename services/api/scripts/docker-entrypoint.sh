#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding workspace..."
python scripts/seed.py

exec "$@"
