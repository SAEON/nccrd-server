"""allow the legacy NCCRD funding types

The legacy migration squashed funding types through a fixed map, turning the
old system's "fundingTypes" vocabulary (Government, Domestic, International
grant, International loan, Private) into NULL. Restoring them
(deploy/restore-budget-funding.sql) needs the column's check constraint, which
sa.Enum(native_enum=False) created with only the form's six values, to accept
them too. Mirrors nccrd.db.models.submission.FundingType.

Downgrading fails while any row still holds one of the legacy values.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FORM_TYPES = ["Grant", "Loan", "Own Funding", "Public-Private Partnership", "None", "Other"]
LEGACY_TYPES = ["Government", "Domestic", "International grant", "International loan", "Private"]


def _replace_constraint(values) -> None:
    op.drop_constraint("ck_submission_funding_type", "submission", schema="nccrd", type_="check")
    allowed = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
    op.create_check_constraint(
        "ck_submission_funding_type", "submission", f"funding_type IN ({allowed})", schema="nccrd",
    )


def upgrade() -> None:
    _replace_constraint(LEGACY_TYPES + FORM_TYPES)


def downgrade() -> None:
    _replace_constraint(FORM_TYPES)
