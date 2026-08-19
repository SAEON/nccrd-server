"""refactor_submission_schema_v2

Applies schema changes introduced in the v2 backend consolidation:

  submission table
  ────────────────
  • Rename column  platfrom            → platform
  • Rename column  project_manager_phone → project_manager_contact_number
  • Drop   column  project_manager_position
  • Drop   column  project_manager_mobile
  • Add CHECK constraint on intervention_measurement (enum values)
  • Add CHECK constraint on implementation_status     (enum values)
  • Add CHECK constraint on funding_type              (enum values)

  adaptaion table   →   adaptation table  (table rename + FK fix)
  ────────────────────────────────────────────────────────────────
  • Rename table adaptaion → adaptation

  mitigation table
  ────────────────
  • Rename column  enviromental_co_benefit             → environmental_co_benefit
  • Rename column  enviromental_co_benefit_description → environmental_co_benefit_description

  progress_report table  (new)
  ────────────────────────────
  • Create nccrd.progress_report with FK → nccrd.submission.id

Revision ID: 0001
Revises:
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Allowed enum values — must stay in sync with Python enums in models/submission.py
_INTERVENTION_VALUES = ("Mitigation", "Adaptation", "Cross Cutting")
_STATUS_VALUES = (
    "Planned",
    "Under Implementation",
    "Completed",
    "Cancelled",
    "On Hold",
)
_FUNDING_VALUES = (
    "Grant",
    "Loan",
    "Own Funding",
    "Public-Private Partnership",
    "None",
    "Other",
)


def _in_clause(values: tuple) -> str:
    """Build a SQL IN(...) literal for a CHECK constraint."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"({quoted})"


def upgrade() -> None:
    # ── submission: column renames ────────────────────────────────────────────
    op.alter_column(
        "submission",
        "platfrom",
        new_column_name="platform",
        schema="nccrd",
    )
    op.alter_column(
        "submission",
        "project_manager_phone",
        new_column_name="project_manager_contact_number",
        schema="nccrd",
    )

    # ── submission: drop obsolete columns ─────────────────────────────────────
    op.drop_column("submission", "project_manager_position", schema="nccrd")
    op.drop_column("submission", "project_manager_mobile",   schema="nccrd")

    # ── submission: coerce legacy values to canonical enum values ─────────────
    # Historical rows used uppercase or non-standard strings that pre-date the
    # enum definition.  We normalise known aliases; anything truly unrecognised
    # is set to NULL (all three enum columns are nullable) so the CHECK
    # constraint can be added without rejecting the row.

    # funding_type normalisation
    op.execute("""
        UPDATE nccrd.submission
        SET funding_type = CASE UPPER(TRIM(funding_type))
            WHEN 'NONE'                     THEN 'None'
            WHEN 'GRANT'                    THEN 'Grant'
            WHEN 'LOAN'                     THEN 'Loan'
            WHEN 'OWN FUNDING'              THEN 'Own Funding'
            WHEN 'PUBLIC-PRIVATE PARTNERSHIP' THEN 'Public-Private Partnership'
            WHEN 'OTHER'                    THEN 'Other'
            ELSE NULL   -- unrecognised → NULL (column is nullable)
        END
        WHERE funding_type IS NOT NULL
          AND funding_type NOT IN (
              'Grant','Loan','Own Funding','Public-Private Partnership','None','Other'
          )
    """)

    # implementation_status normalisation
    op.execute("""
        UPDATE nccrd.submission
        SET implementation_status = CASE TRIM(implementation_status)
            WHEN 'planned'                THEN 'Planned'
            WHEN 'under implementation'   THEN 'Under Implementation'
            WHEN 'completed'              THEN 'Completed'
            WHEN 'cancelled'              THEN 'Cancelled'
            WHEN 'on hold'                THEN 'On Hold'
            ELSE NULL   -- unrecognised → NULL
        END
        WHERE implementation_status IS NOT NULL
          AND implementation_status NOT IN (
              'Planned','Under Implementation','Completed','Cancelled','On Hold'
          )
    """)

    # intervention_measurement normalisation
    op.execute("""
        UPDATE nccrd.submission
        SET intervention_measurement = CASE LOWER(TRIM(intervention_measurement))
            WHEN 'mitigation'    THEN 'Mitigation'
            WHEN 'adaptation'    THEN 'Adaptation'
            WHEN 'cross cutting' THEN 'Cross Cutting'
            ELSE NULL
        END
        WHERE intervention_measurement IS NOT NULL
          AND intervention_measurement NOT IN ('Mitigation','Adaptation','Cross Cutting')
    """)

    # ── submission: add CHECK constraints for enum fields ─────────────────────
    # Using native CHECK constraints (native_enum=False in the model means
    # SQLAlchemy does not create a PG ENUM type, so we add the constraint here).
    op.create_check_constraint(
        "ck_submission_intervention_measurement",
        "submission",
        f"intervention_measurement IN {_in_clause(_INTERVENTION_VALUES)}",
        schema="nccrd",
    )
    op.create_check_constraint(
        "ck_submission_implementation_status",
        "submission",
        f"implementation_status IN {_in_clause(_STATUS_VALUES)}",
        schema="nccrd",
    )
    op.create_check_constraint(
        "ck_submission_funding_type",
        "submission",
        f"funding_type IN {_in_clause(_FUNDING_VALUES)}",
        schema="nccrd",
    )

    # ── adaptaion → adaptation: table rename ──────────────────────────────────
    op.rename_table("adaptaion", "adaptation", schema="nccrd")

    # ── mitigation: column renames ────────────────────────────────────────────
    op.alter_column(
        "mitigation",
        "enviromental_co_benefit",
        new_column_name="environmental_co_benefit",
        schema="nccrd",
    )
    op.alter_column(
        "mitigation",
        "enviromental_co_benefit_description",
        new_column_name="environmental_co_benefit_description",
        schema="nccrd",
    )

    # ── progress_report: create new table ────────────────────────────────────
    op.create_table(
        "progress_report",
        sa.Column("id",            sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("submission_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("file_url",      sa.String(),   nullable=False),
        sa.Column("file_name",     sa.String(),   nullable=False),
        sa.Column("upload_date",   sa.DateTime(), nullable=True),
        sa.Column("notes",         sa.Text(),     nullable=True),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["nccrd.submission.id"],
            name="fk_progress_report_submission_id",
            ondelete="CASCADE",
        ),
        schema="nccrd",
    )


def downgrade() -> None:
    # ── Drop progress_report ──────────────────────────────────────────────────
    op.drop_table("progress_report", schema="nccrd")

    # ── mitigation: revert column renames ─────────────────────────────────────
    op.alter_column(
        "mitigation",
        "environmental_co_benefit",
        new_column_name="enviromental_co_benefit",
        schema="nccrd",
    )
    op.alter_column(
        "mitigation",
        "environmental_co_benefit_description",
        new_column_name="enviromental_co_benefit_description",
        schema="nccrd",
    )

    # ── adaptation → adaptaion: table rename ──────────────────────────────────
    op.rename_table("adaptation", "adaptaion", schema="nccrd")

    # ── submission: drop CHECK constraints ────────────────────────────────────
    op.drop_constraint(
        "ck_submission_funding_type", "submission", schema="nccrd", type_="check"
    )
    op.drop_constraint(
        "ck_submission_implementation_status", "submission", schema="nccrd", type_="check"
    )
    op.drop_constraint(
        "ck_submission_intervention_measurement", "submission", schema="nccrd", type_="check"
    )

    # ── submission: restore dropped columns ───────────────────────────────────
    op.add_column(
        "submission",
        sa.Column("project_manager_mobile",   sa.String(), nullable=True),
        schema="nccrd",
    )
    op.add_column(
        "submission",
        sa.Column("project_manager_position", sa.String(), nullable=True),
        schema="nccrd",
    )

    # ── submission: revert column renames ─────────────────────────────────────
    op.alter_column(
        "submission",
        "project_manager_contact_number",
        new_column_name="project_manager_phone",
        schema="nccrd",
    )
    op.alter_column(
        "submission",
        "platform",
        new_column_name="platfrom",
        schema="nccrd",
    )
