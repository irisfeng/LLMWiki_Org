#!/bin/sh
set -e

cd /app
PYTHONPATH=/app alembic upgrade head

exec "$@"
