"""initial_schema

The true from-scratch baseline for the nccrd schema, replacing the old
0001-0006 chain. That chain was never a complete schema definition: its
former 0001 (refactor_submission_schema_v2) started with
`ALTER TABLE nccrd.submission RENAME platfrom TO platform`, which presumes
nccrd.submission — and evidently not every table the chain went on to
create — already existed from an undocumented pre-Alembic bootstrap step.
Confirmed directly: running `alembic upgrade head` against a genuinely
empty database on the old chain failed immediately on that first migration
with `relation "nccrd.submission" does not exist`. Different environments
had evidently been bootstrapped from different baseline snapshots before
migration tracking began, so "alembic_version = head" never actually
guaranteed two environments had identical schemas — which is exactly how
this project ended up with a deployed server missing nccrd.research (see
the old 0006_ensure_research_table for that specific incident) despite
every migration reporting successfully applied.

This migration is the complete current schema, generated in two parts and
merged:
  1. `alembic revision --autogenerate` against a genuinely empty database,
     with the old 0001-0006 files temporarily removed so Alembic had
     nothing to assume already existed — this captured every table/column
     that has a SQLAlchemy model (nccrd/db/models/).
  2. Four tables that are real, already-deployed parts of the schema but
     have no ORM model, so autogenerate can't see them — added by hand
     from the old 0002 migration's original definitions, verified against
     the actual running schema: vocabulary_xref_region, download_log,
     login, research.
  Plus every non-PK/non-unique index confirmed present in the real schema
  via `pg_indexes` but not re-derived by autogenerate (SQLAlchemy models
  here don't declare secondary indexes, so autogenerate never sees them
  either — same blind spot as the four tables above).

Verified by generating this file against a byte-for-byte replica of the
actual deployed server's schema (pg_dump --schema-only, restored locally)
and confirming zero remaining differences beyond the four model-less
tables already accounted for above.

Revision ID: 0001
Revises:
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tables with a SQLAlchemy model (from `alembic revision --autogenerate`) ──
    op.create_table('country',
    sa.Column('gid', sa.Integer(), nullable=False),
    sa.Column('shape0', sa.String(), nullable=True),
    sa.Column('shapeiso', sa.String(), nullable=True),
    sa.Column('shapeid', sa.String(), nullable=True),
    sa.Column('shapegroup', sa.String(), nullable=True),
    sa.Column('shapetype', sa.String(), nullable=True),
    sa.Column('geometry', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('gid'),
    schema='nccrd'
    )
    op.create_table('district',
    sa.Column('FID', sa.Integer(), nullable=False),
    sa.Column('PROVINCE', sa.String(), nullable=True),
    sa.Column('DISTRICT', sa.String(), nullable=True),
    sa.Column('DISTRICT_N', sa.String(), nullable=True),
    sa.Column('DATE', sa.Integer(), nullable=True),
    sa.Column('CATEGORY', sa.String(), nullable=True),
    sa.Column('geometry', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('FID'),
    schema='nccrd'
    )
    op.create_table('local_district',
    sa.Column('FID', sa.Integer(), nullable=False),
    sa.Column('OBJECTID', sa.Integer(), nullable=True),
    sa.Column('PROVINCE', sa.String(), nullable=True),
    sa.Column('CATEGORY', sa.String(), nullable=True),
    sa.Column('CAT2', sa.String(), nullable=True),
    sa.Column('CAT_B', sa.String(), nullable=True),
    sa.Column('MUNICNAME', sa.String(), nullable=True),
    sa.Column('NAMECODE', sa.String(), nullable=True),
    sa.Column('MAP_TITLE', sa.String(), nullable=True),
    sa.Column('DISTRICT', sa.String(), nullable=True),
    sa.Column('DISTRICT_N', sa.String(), nullable=True),
    sa.Column('DATE', sa.Integer(), nullable=True),
    sa.Column('geometry', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('FID'),
    schema='nccrd'
    )
    op.create_table('permission',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    schema='nccrd'
    )
    op.create_table('province',
    sa.Column('FID', sa.Integer(), nullable=False),
    sa.Column('PR_MDB_C', sa.String(), nullable=True),
    sa.Column('PR_CODE', sa.Integer(), nullable=True),
    sa.Column('PR_CODE_st', sa.Integer(), nullable=True),
    sa.Column('PR_NAME', sa.String(), nullable=True),
    sa.Column('ALBERS_ARE', sa.Float(), nullable=True),
    sa.Column('SHAPE_Leng', sa.Float(), nullable=True),
    sa.Column('X', sa.Float(), nullable=True),
    sa.Column('Y', sa.Float(), nullable=True),
    sa.Column('Shape__Area', sa.Float(), nullable=True),
    sa.Column('Shape__Length', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('FID'),
    schema='nccrd'
    )
    op.create_table('role',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    schema='nccrd'
    )
    op.create_table('tenant',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('hostname', sa.String(length=500), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=True),
    sa.Column('theme', sa.JSON(), nullable=True),
    sa.Column('contact_email', sa.String(length=500), nullable=True),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('include_unbounded_submissions', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hostname'),
    schema='nccrd'
    )
    op.create_table('tree',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('description', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('user',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('uuid', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=500), nullable=False),
    sa.Column('email', sa.String(length=500), nullable=False),
    sa.Column('saeon_id', sa.String(length=255), nullable=True),
    sa.Column('id_token', sa.Text(), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('password_set_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('uuid'),
    schema='nccrd'
    )
    op.create_table('vocabulary',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('term', sa.String(), nullable=True),
    sa.Column('properties', sa.String(), nullable=True),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('code', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('permission_xref_role',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('permission_id', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['nccrd.permission.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['nccrd.role.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('submission',
    sa.Column('_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('intervention_measurement', sa.Enum('Mitigation', 'Adaptation', 'Cross Cutting', name='intervention_measurement_enum', native_enum=False), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('implementation_status', sa.Enum('Planned', 'Under Implementation', 'Completed', 'Cancelled', 'On Hold', name='implementation_status_enum', native_enum=False), nullable=True),
    sa.Column('implementation_organization', sa.String(), nullable=True),
    sa.Column('implementation_partners_other', sa.String(), nullable=True),
    sa.Column('start_date', sa.DateTime(), nullable=True),
    sa.Column('end_date', sa.DateTime(), nullable=True),
    sa.Column('link', sa.String(), nullable=True),
    sa.Column('funding_organization', sa.String(), nullable=True),
    sa.Column('funding_type', sa.Enum('Grant', 'Loan', 'Own Funding', 'Public-Private Partnership', 'None', 'Other', name='funding_type_enum', native_enum=False), nullable=True),
    sa.Column('funding_amount', sa.Float(), nullable=True),
    sa.Column('estimated_budget_cost', sa.String(), nullable=True),
    sa.Column('geo_location', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('project_manager_name', sa.String(), nullable=True),
    sa.Column('project_manager_organization', sa.String(), nullable=True),
    sa.Column('project_manager_email', sa.String(), nullable=True),
    sa.Column('project_manager_contact_number', sa.String(), nullable=True),
    sa.Column('submission_status', sa.String(), nullable=True),
    sa.Column('submission_status_updated_by', sa.Integer(), nullable=True),
    sa.Column('submission_comments', sa.String(), nullable=True),
    sa.Column('issubmitted', sa.Boolean(), nullable=True),
    sa.Column('research', sa.String(), nullable=True),
    sa.Column('platform', sa.String(), nullable=True),
    sa.Column('data_source', sa.String(), nullable=True),
    sa.Column('createdby', sa.Integer(), nullable=True),
    sa.Column('createdate', sa.DateTime(), nullable=True),
    sa.Column('updatedate', sa.DateTime(), nullable=True),
    sa.Column('updatedby', sa.Integer(), nullable=True),
    sa.Column('deletedby', sa.Integer(), nullable=True),
    sa.Column('deletedate', sa.DateTime(), nullable=True),
    sa.Column('deleted', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['createdby'], ['nccrd.user.id'], ),
    sa.ForeignKeyConstraint(['deletedby'], ['nccrd.user.id'], ),
    sa.ForeignKeyConstraint(['submission_status_updated_by'], ['nccrd.user.id'], ),
    sa.ForeignKeyConstraint(['updatedby'], ['nccrd.user.id'], ),
    sa.PrimaryKeyConstraint('_id'),
    sa.UniqueConstraint('id'),
    schema='nccrd'
    )
    op.create_table('user_xref_role_xref_tenant',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['nccrd.role.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['nccrd.tenant.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['nccrd.user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('vocabulary_xref_tree',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vocabulary_id', sa.Integer(), nullable=True),
    sa.Column('tree_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['tree_id'], ['nccrd.tree.id'], ),
    sa.ForeignKeyConstraint(['vocabulary_id'], ['nccrd.vocabulary.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('vocabulary_xref_vocabulary',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('child_id', sa.Integer(), nullable=True),
    sa.Column('tree_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['child_id'], ['nccrd.vocabulary.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['nccrd.vocabulary.id'], ),
    sa.ForeignKeyConstraint(['tree_id'], ['nccrd.tree.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('adaptation',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('sector', sa.String(), nullable=True),
    sa.Column('national_policy', sa.String(), nullable=True),
    sa.Column('intervention_goal', sa.String(), nullable=True),
    sa.Column('provincial_municipal', sa.String(), nullable=True),
    sa.Column('hazard', sa.String(), nullable=True),
    sa.Column('progress_calculator', sa.String(), nullable=True),
    sa.Column('climate_impact', sa.String(), nullable=True),
    sa.Column('address_climate_impact', sa.String(), nullable=True),
    sa.Column('impact_response', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['submission_id'], ['nccrd.submission.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('mitigation',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('sector', sa.String(), nullable=True),
    sa.Column('subsector', sa.String(), nullable=True),
    sa.Column('secondary', sa.String(), nullable=True),
    sa.Column('project_type', sa.String(), nullable=True),
    sa.Column('project_subtype', sa.String(), nullable=True),
    sa.Column('mitigation_program', sa.String(), nullable=True),
    sa.Column('national_policy', sa.String(), nullable=True),
    sa.Column('provincial_municipal', sa.String(), nullable=True),
    sa.Column('primary_intended_outcome', sa.String(), nullable=True),
    sa.Column('progress_calculator', sa.String(), nullable=True),
    sa.Column('environmental_co_benefit', sa.String(), nullable=True),
    sa.Column('environmental_co_benefit_description', sa.String(), nullable=True),
    sa.Column('social_co_benefit', sa.String(), nullable=True),
    sa.Column('social_co_benefit_description', sa.String(), nullable=True),
    sa.Column('economic_co_benefit', sa.String(), nullable=True),
    sa.Column('economic_co_benefit_description', sa.String(), nullable=True),
    sa.Column('carbon_credit', sa.String(), nullable=True),
    sa.Column('cdm_voluntary', sa.String(), nullable=True),
    sa.Column('cdm_executive_board_status', sa.String(), nullable=True),
    sa.Column('cdm_methodology', sa.String(), nullable=True),
    sa.Column('organization_issuing_credits', sa.String(), nullable=True),
    sa.Column('voluntary_methodology', sa.String(), nullable=True),
    sa.Column('cdm_project_number', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['submission_id'], ['nccrd.submission.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('progress_report',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('file_url', sa.String(), nullable=False),
    sa.Column('file_name', sa.String(), nullable=False),
    sa.Column('upload_date', sa.DateTime(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['submission_id'], ['nccrd.submission.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='nccrd'
    )
    op.create_table('tenant_xref_submission',
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['submission_id'], ['nccrd.submission.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['nccrd.tenant.id'], ),
    sa.PrimaryKeyConstraint('tenant_id', 'submission_id'),
    schema='nccrd'
    )

    # ── Tables with no SQLAlchemy model — real, deployed, but invisible to
    # autogenerate; added by hand from the old 0002 migration's original
    # definitions (see this file's docstring) ──
    op.create_table(
        "vocabulary_xref_region",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vocabulary_id", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["vocabulary_id"],
            ["nccrd.vocabulary.id"],
            name="fk_vocabulary_xref_region_vocabulary_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="nccrd",
    )
    op.create_table(
        "download_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("submission_ids", sa.JSON(), nullable=True),
        sa.Column("submission_search", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["nccrd.user.id"],
            name="fk_download_log_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="nccrd",
    )
    op.create_table(
        "login",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["nccrd.user.id"],
            name="fk_login_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="nccrd",
    )
    op.create_table(
        "research",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["nccrd.submission.id"],
            name="fk_research_submission_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="nccrd",
    )

    # ── Secondary indexes — not declared on any model, so autogenerate
    # misses these too; confirmed present in the real schema via pg_indexes ──
    op.create_index("idx_adaptation_submission_id", "adaptation", ["submission_id"], schema="nccrd", postgresql_using="btree")
    op.create_index("idx_mitigation_submission_id", "mitigation", ["submission_id"], schema="nccrd", postgresql_using="btree")
    op.create_index("idx_progress_report_submission_id", "progress_report", ["submission_id"], schema="nccrd", postgresql_using="btree")
    op.create_index("idx_submission_createdate", "submission", ["createdate"], schema="nccrd", postgresql_using="btree")
    op.create_index("idx_submission_createdby", "submission", ["createdby"], schema="nccrd", postgresql_using="btree")
    op.create_index("idx_submission_deleted", "submission", ["deleted"], schema="nccrd", postgresql_using="btree", postgresql_where=sa.text("deleted = FALSE"))
    op.create_index("idx_submission_geo_location", "submission", ["geo_location"], schema="nccrd", postgresql_using="gin")
    op.create_index("idx_submission_issubmitted", "submission", ["issubmitted"], schema="nccrd", postgresql_using="btree", postgresql_where=sa.text("issubmitted = TRUE"))
    op.create_index("idx_download_log_user_id", "download_log", ["user_id"], schema="nccrd", postgresql_using="btree")
    op.create_index("idx_login_user_id", "login", ["user_id"], schema="nccrd", postgresql_using="btree")


def downgrade() -> None:
    op.drop_index("idx_login_user_id", table_name="login", schema="nccrd")
    op.drop_index("idx_download_log_user_id", table_name="download_log", schema="nccrd")
    op.drop_index("idx_submission_issubmitted", table_name="submission", schema="nccrd")
    op.drop_index("idx_submission_geo_location", table_name="submission", schema="nccrd")
    op.drop_index("idx_submission_deleted", table_name="submission", schema="nccrd")
    op.drop_index("idx_submission_createdby", table_name="submission", schema="nccrd")
    op.drop_index("idx_submission_createdate", table_name="submission", schema="nccrd")
    op.drop_index("idx_progress_report_submission_id", table_name="progress_report", schema="nccrd")
    op.drop_index("idx_mitigation_submission_id", table_name="mitigation", schema="nccrd")
    op.drop_index("idx_adaptation_submission_id", table_name="adaptation", schema="nccrd")

    op.drop_table("research", schema="nccrd")
    op.drop_table("login", schema="nccrd")
    op.drop_table("download_log", schema="nccrd")
    op.drop_table("vocabulary_xref_region", schema="nccrd")

    op.drop_table('tenant_xref_submission', schema='nccrd')
    op.drop_table('progress_report', schema='nccrd')
    op.drop_table('mitigation', schema='nccrd')
    op.drop_table('adaptation', schema='nccrd')
    op.drop_table('vocabulary_xref_vocabulary', schema='nccrd')
    op.drop_table('vocabulary_xref_tree', schema='nccrd')
    op.drop_table('user_xref_role_xref_tenant', schema='nccrd')
    op.drop_table('submission', schema='nccrd')
    op.drop_table('permission_xref_role', schema='nccrd')
    op.drop_table('vocabulary', schema='nccrd')
    op.drop_table('user', schema='nccrd')
    op.drop_table('tree', schema='nccrd')
    op.drop_table('tenant', schema='nccrd')
    op.drop_table('role', schema='nccrd')
    op.drop_table('province', schema='nccrd')
    op.drop_table('permission', schema='nccrd')
    op.drop_table('local_district', schema='nccrd')
    op.drop_table('district', schema='nccrd')
    op.drop_table('country', schema='nccrd')
