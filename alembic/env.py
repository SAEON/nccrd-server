"""
Alembic environment configuration for NCCRD.

Reads the database URL from the same nccrd_config that the application uses,
and imports all ORM models so autogenerate can diff against the live schema.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Ensure both package roots are on sys.path ────────────────────────────────
_server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_odp_core_root = os.path.abspath(os.path.join(_server_root, "..", "odp-core"))
sys.path.insert(0, _server_root)
sys.path.insert(0, _odp_core_root)

# ── Import project config and models ─────────────────────────────────────────
from nccrd.config import nccrd_config   # noqa: E402
from nccrd.db import Base               # noqa: E402

# Import all model modules so Base.metadata is fully populated.
import nccrd.db.models  # noqa: F401, E402

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

# Wire the DB URL from application config — overrides the placeholder in alembic.ini.
config.set_main_option("sqlalchemy.url", nccrd_config.NCCRD.DB.URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live connection (offline mode)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="nccrd",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection (online mode)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="nccrd",  # Store alembic_version table inside nccrd schema.
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
