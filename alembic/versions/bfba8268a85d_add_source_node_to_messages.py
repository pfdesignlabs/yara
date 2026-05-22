"""add source node to messages

Revision ID: bfba8268a85d
Revises: 1fccab4b892a
Create Date: 2026-05-22 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bfba8268a85d'
down_revision = '1fccab4b892a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('source_node', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'source_node')
