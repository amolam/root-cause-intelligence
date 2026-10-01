"""Initial schema matching the Dhaga return/fit MVP data schema.

Revision ID: 0001_initial
Revises:
"""
from alembic import op

from app.db.base import Base
from app.db import models  # noqa: F401 - registers all models

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
