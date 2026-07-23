"""rename games site unique constraint

Revision ID: 404f145b7ceb
Revises: 12e478a8f1cb
Create Date: 2026-07-23 23:22:59.853339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '404f145b7ceb'
down_revision: Union[str, Sequence[str], None] = '12e478a8f1cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        "ALTER TABLE games RENAME CONSTRAINT games_site_key TO uq_games_site"
    )


def downgrade():
    op.execute(
        "ALTER TABLE games RENAME CONSTRAINT uq_games_site TO games_site_key"
    )
