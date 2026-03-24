#!/bin/bash
set -e

# Auto-stamp existing databases that predate Alembic.
# If tables exist but alembic_version does not, the DB was created by the old
# Base.metadata.create_all() path. We stamp it at the initial migration so
# Alembic only runs migrations that add new columns / tables.
python - <<'PYEOF'
from sqlalchemy import inspect, text
from app.database import engine

insp = inspect(engine)
tables = insp.get_table_names()

if tables and 'alembic_version' not in tables:
    print("[entrypoint] Existing database detected without Alembic version table.")
    print("[entrypoint] Stamping at initial migration (1da8d3d765ce)...")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        ))
        conn.execute(text("INSERT INTO alembic_version VALUES ('1da8d3d765ce')"))
        conn.commit()
    print("[entrypoint] Stamp done.")
PYEOF

echo "[entrypoint] Running database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete. Starting server..."

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
