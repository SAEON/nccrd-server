"""
Alembic environment configuration for NCCRD.

Reads the database URL from the same nccrd_config that the application uses,
and imports all ORM models so autogenerate can diff against the live schema.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text
from alembic import context

# ── Ensure the package root is on sys.path ───────────────────────────────────
_server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _server_root)

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

# Secondary indexes created via raw DDL in migration 0001 (see its
# docstring) that have no corresponding SQLAlchemy Index() declaration on
# any model — deliberately, matching this codebase's existing style of not
# modeling every secondary index (true even for indexes on tables that do
# have a model, e.g. idx_submission_createdby). Without this filter,
# autogenerate/`alembic check` always sees them as "extra" objects to drop,
# drowning out genuine future drift.
#
# The 4 tables (download_log, vocabulary_xref_region, login, research)
# these indexes originally lived alongside now have real ORM models — see
# nccrd/db/models/rbac.py, submission.py, vocabulary.py — so only the
# index names remain excluded here, not the tables themselves.
_UNMAPPED_INDEXES = {
    "idx_download_log_user_id", "idx_login_user_id",
    "idx_adaptation_submission_id", "idx_mitigation_submission_id",
    "idx_progress_report_submission_id", "idx_submission_createdate",
    "idx_submission_createdby", "idx_submission_deleted",
    "idx_submission_geo_location", "idx_submission_issubmitted",
}


def include_object(object, name, type_, reflected, compare_to):
    return not (type_ == "index" and name in _UNMAPPED_INDEXES)


# The app owns only the `nccrd` schema. The same database also holds the data
# pipeline's `bronze`, `silver` and `pipeline` schemas (nccrd-build/pipeline,
# see PIPELINE.md); without this filter, include_schemas=True makes
# autogenerate reflect them and propose dropping every pipeline table.
def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == "nccrd"
    return True


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live connection (offline mode)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
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
        # A genuinely fresh database has no `nccrd` schema at all yet — every
        # migration (and the alembic_version table itself) lives inside it,
        # so this has to exist before `context.run_migrations()` runs, not
        # just before individual migrations that happen to create tables.
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS nccrd"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
            version_table_schema="nccrd",  # Store alembic_version table inside nccrd schema.
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
