"""team workbench baseline

Revision ID: 0001_team_workbench_baseline
Revises:
Create Date: 2026-06-12
"""

revision = "0001_team_workbench_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Baseline marker for the current SQLAlchemy models.
    # Existing local development uses create_all; future schema changes should
    # be generated as Alembic revisions from this point forward.
    pass


def downgrade() -> None:
    pass
