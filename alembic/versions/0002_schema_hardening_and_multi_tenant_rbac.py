"""schema_hardening_and_multi_tenant_rbac

Add missing tables for multi-tenant RBAC, vocabulary tree system, audit trails,
and user management. This migration introduces:

  New tables
  ──────────
  • nccrd.user                       — 257 users from legacy Submissions.createdBy
  • nccrd.role                       — 5 roles (admin, editor, etc.)
  • nccrd.permission                 — 27 permissions (read, write, approve, etc.)
  • nccrd.permission_xref_role       — 71 role-permission assignments
  • nccrd.tenant                     — 3 multi-tenant configurations
  • nccrd.tenant_xref_submission     — 5,594 submission-to-tenant links
  • nccrd.user_xref_role_xref_tenant — 493 user-role-tenant assignments
  • nccrd.tree                       — 19 vocabulary tree definitions
  • nccrd.vocabulary_xref_tree       — 751 vocabulary-to-tree links
  • nccrd.vocabulary_xref_vocabulary — 730 parent-child vocabulary hierarchies
  • nccrd.vocabulary_xref_region     — vocabulary-region links (future geoloc queries)
  • nccrd.download_log               — 148 audit entries for bulk downloads
  • nccrd.login                      — 935 login timestamps
  • nccrd.research                   — research submissions (normalized from JSON blob)

  Schema hardening
  ────────────────
  • Add NOT NULL constraints + defaults to submission (issubmitted, deleted, createdate)
  • Add submission_status_updated_by FK to track status reviewer
  • Add FK constraints on submission.createdby → user.id
  • Create indexes on frequently-queried columns
  • Fix Foreign Key references in vocabulary tables (schema prefix + type corrections)

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────────────────────
    # 1. Create nccrd.user table (required before FK references from submissions)
    # ──────────────────────────────────────────────────────────────────────────────
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("email", sa.String(length=500), nullable=False),
        sa.Column("saeon_id", sa.String(length=255), nullable=True),
        sa.Column("id_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("email"),
        schema="nccrd",
    )

    # ──────────────────────────────────────────────────────────────────────────────
    # 2. Create nccrd.role and nccrd.permission tables (RBAC foundation)
    # ──────────────────────────────────────────────────────────────────────────────
    op.create_table(
        "role",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema="nccrd",
    )

    op.create_table(
        "permission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema="nccrd",
    )

    op.create_table(
        "permission_xref_role",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["nccrd.permission.id"],
            name="fk_permission_xref_role_permission_id",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["nccrd.role.id"],
            name="fk_permission_xref_role_role_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("permission_id", "role_id"),
        schema="nccrd",
    )

    # ──────────────────────────────────────────────────────────────────────────────
    # 3. Create nccrd.tenant table (multi-tenancy)
    # ──────────────────────────────────────────────────────────────────────────────
    op.create_table(
        "tenant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("theme", sa.JSON(), nullable=True),
        sa.Column("contact_email", sa.String(length=500), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("include_unbounded_submissions", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname"),
        schema="nccrd",
    )

    # ──────────────────────────────────────────────────────────────────────────────
    # 4. Create junction tables: user-role-tenant, tenant-submission
    # ──────────────────────────────────────────────────────────────────────────────
    op.create_table(
        "user_xref_role_xref_tenant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["nccrd.role.id"],
            name="fk_user_xref_role_xref_tenant_role_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["nccrd.tenant.id"],
            name="fk_user_xref_role_xref_tenant_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["nccrd.user.id"],
            name="fk_user_xref_role_xref_tenant_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", "tenant_id"),
        schema="nccrd",
    )

    op.create_table(
        "tenant_xref_submission",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("submission_id", PG_UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["nccrd.submission.id"],
            name="fk_tenant_xref_submission_submission_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["nccrd.tenant.id"],
            name="fk_tenant_xref_submission_tenant_id",
        ),
        sa.PrimaryKeyConstraint("tenant_id", "submission_id"),
        schema="nccrd",
    )

    # ──────────────────────────────────────────────────────────────────────────────
    # 5. Create nccrd.tree and vocabulary cross-reference tables
    # ──────────────────────────────────────────────────────────────────────────────
    op.create_table(
        "tree",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema="nccrd",
    )

    op.create_table(
        "vocabulary_xref_tree",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vocabulary_id", sa.Integer(), nullable=False),
        sa.Column("tree_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["nccrd.tree.id"],
            name="fk_vocabulary_xref_tree_tree_id",
        ),
        sa.ForeignKeyConstraint(
            ["vocabulary_id"],
            ["nccrd.vocabulary.id"],
            name="fk_vocabulary_xref_tree_vocabulary_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vocabulary_id", "tree_id"),
        schema="nccrd",
    )

    op.create_table(
        "vocabulary_xref_vocabulary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("tree_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["child_id"],
            ["nccrd.vocabulary.id"],
            name="fk_vocabulary_xref_vocabulary_child_id",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["nccrd.vocabulary.id"],
            name="fk_vocabulary_xref_vocabulary_parent_id",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["nccrd.tree.id"],
            name="fk_vocabulary_xref_vocabulary_tree_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "tree_id"),
        schema="nccrd",
    )

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

    # ──────────────────────────────────────────────────────────────────────────────
    # 6. Create nccrd.download_log and nccrd.login tables (audit trail)
    # ──────────────────────────────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────────────────────────
    # 7. Create nccrd.research table (normalized from legacy research JSON blob)
    # ──────────────────────────────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────────────────────────
    # 7b. Backfill nccrd.user with placeholder records for existing createdby IDs
    # ──────────────────────────────────────────────────────────────────────────────
    op.execute("""
        INSERT INTO nccrd.user (id, uuid, name, email, deleted)
        SELECT DISTINCT s.createdby,
               gen_random_uuid(),
               'Legacy User ' || s.createdby,
               'legacy_user_' || s.createdby || '@placeholder.local',
               false
        FROM nccrd.submission s
        WHERE s.createdby IS NOT NULL
        ON CONFLICT (id) DO NOTHING
    """)

    # ──────────────────────────────────────────────────────────────────────────────
    # 8. Alter nccrd.submission table: add NOT NULL constraints and new FK column
    # ──────────────────────────────────────────────────────────────────────────────
    # Backfill NULLs before setting NOT NULL constraints
    op.execute("UPDATE nccrd.submission SET issubmitted = false WHERE issubmitted IS NULL")
    op.execute("UPDATE nccrd.submission SET deleted = false WHERE deleted IS NULL")

    op.alter_column(
        "submission",
        "issubmitted",
        existing_type=sa.Boolean(),
        nullable=False,
        existing_server_default=sa.false(),
        schema="nccrd",
    )

    op.alter_column(
        "submission",
        "deleted",
        existing_type=sa.Boolean(),
        nullable=False,
        existing_server_default=sa.false(),
        schema="nccrd",
    )

    op.alter_column(
        "submission",
        "createdate",
        existing_type=sa.DateTime(),
        nullable=False,
        schema="nccrd",
    )

    # Add the new submission_status_updated_by column
    op.add_column(
        "submission",
        sa.Column("submission_status_updated_by", sa.Integer(), nullable=True),
        schema="nccrd",
    )

    op.create_foreign_key(
        "fk_submission_submission_status_updated_by",
        "submission",
        "user",
        ["submission_status_updated_by"],
        ["id"],
        source_schema="nccrd",
        referent_schema="nccrd",
    )

    # Add FK constraint on createdby (was orphaned)
    op.create_foreign_key(
        "fk_submission_createdby",
        "submission",
        "user",
        ["createdby"],
        ["id"],
        source_schema="nccrd",
        referent_schema="nccrd",
    )

    # ──────────────────────────────────────────────────────────────────────────────
    # 9. Add indexes for performance
    # ──────────────────────────────────────────────────────────────────────────────
    op.create_index(
        "idx_submission_createdate",
        "submission",
        ["createdate"],
        schema="nccrd",
        postgresql_using="btree",
    )

    op.create_index(
        "idx_submission_createdby",
        "submission",
        ["createdby"],
        schema="nccrd",
        postgresql_using="btree",
    )

    op.create_index(
        "idx_submission_deleted",
        "submission",
        ["deleted"],
        schema="nccrd",
        postgresql_using="btree",
        postgresql_where=sa.text("deleted = FALSE"),
    )

    op.create_index(
        "idx_submission_issubmitted",
        "submission",
        ["issubmitted"],
        schema="nccrd",
        postgresql_using="btree",
        postgresql_where=sa.text("issubmitted = TRUE"),
    )

    op.create_index(
        "idx_submission_geo_location",
        "submission",
        ["geo_location"],
        schema="nccrd",
        postgresql_using="gin",
    )

    op.create_index(
        "idx_mitigation_submission_id",
        "mitigation",
        ["submission_id"],
        schema="nccrd",
        postgresql_using="btree",
    )

    op.create_index(
        "idx_adaptation_submission_id",
        "adaptation",
        ["submission_id"],
        schema="nccrd",
        postgresql_using="btree",
    )

    op.create_index(
        "idx_progress_report_submission_id",
        "progress_report",
        ["submission_id"],
        schema="nccrd",
        postgresql_using="btree",
    )

    op.create_index(
        "idx_download_log_user_id",
        "download_log",
        ["user_id"],
        schema="nccrd",
        postgresql_using="btree",
    )

    op.create_index(
        "idx_login_user_id",
        "login",
        ["user_id"],
        schema="nccrd",
        postgresql_using="btree",
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index(
        "idx_login_user_id",
        table_name="login",
        schema="nccrd",
    )
    op.drop_index(
        "idx_download_log_user_id",
        table_name="download_log",
        schema="nccrd",
    )
    op.drop_index(
        "idx_progress_report_submission_id",
        table_name="progress_report",
        schema="nccrd",
    )
    op.drop_index(
        "idx_adaptation_submission_id",
        table_name="adaptation",
        schema="nccrd",
    )
    op.drop_index(
        "idx_mitigation_submission_id",
        table_name="mitigation",
        schema="nccrd",
    )
    op.drop_index(
        "idx_submission_geo_location",
        table_name="submission",
        schema="nccrd",
    )
    op.drop_index(
        "idx_submission_issubmitted",
        table_name="submission",
        schema="nccrd",
    )
    op.drop_index(
        "idx_submission_deleted",
        table_name="submission",
        schema="nccrd",
    )
    op.drop_index(
        "idx_submission_createdby",
        table_name="submission",
        schema="nccrd",
    )
    op.drop_index(
        "idx_submission_createdate",
        table_name="submission",
        schema="nccrd",
    )

    # Drop FKs from submission
    op.drop_constraint(
        "fk_submission_createdby",
        "submission",
        schema="nccrd",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_submission_submission_status_updated_by",
        "submission",
        schema="nccrd",
        type_="foreignkey",
    )

    # Drop submission column
    op.drop_column("submission", "submission_status_updated_by", schema="nccrd")

    # Revert NOT NULL constraints
    op.alter_column(
        "submission",
        "createdate",
        existing_type=sa.DateTime(),
        nullable=True,
        schema="nccrd",
    )

    op.alter_column(
        "submission",
        "deleted",
        existing_type=sa.Boolean(),
        nullable=True,
        existing_server_default=sa.false(),
        schema="nccrd",
    )

    op.alter_column(
        "submission",
        "issubmitted",
        existing_type=sa.Boolean(),
        nullable=True,
        existing_server_default=sa.false(),
        schema="nccrd",
    )

    # Drop tables in reverse creation order
    op.drop_table("research", schema="nccrd")
    op.drop_table("login", schema="nccrd")
    op.drop_table("download_log", schema="nccrd")
    op.drop_table("vocabulary_xref_region", schema="nccrd")
    op.drop_table("vocabulary_xref_vocabulary", schema="nccrd")
    op.drop_table("vocabulary_xref_tree", schema="nccrd")
    op.drop_table("tree", schema="nccrd")
    op.drop_table("tenant_xref_submission", schema="nccrd")
    op.drop_table("user_xref_role_xref_tenant", schema="nccrd")
    op.drop_table("permission_xref_role", schema="nccrd")
    op.drop_table("permission", schema="nccrd")
    op.drop_table("role", schema="nccrd")
    op.drop_table("tenant", schema="nccrd")
    op.drop_table("user", schema="nccrd")
