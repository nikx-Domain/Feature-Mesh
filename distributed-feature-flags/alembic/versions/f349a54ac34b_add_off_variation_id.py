"""add_off_variation_id

Revision ID: f349a54ac34b
Revises: a63b788db6ea
Create Date: 2026-06-05 13:14:35.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f349a54ac34b'
down_revision: str | None = 'fbd3d84ac4a0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('feature_flag_environments', sa.Column('off_variation_id', sa.Uuid(), nullable=True))
    with op.batch_alter_table('feature_flag_environments', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_feature_flag_env_off_var', 'flag_variations', ['off_variation_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('feature_flag_environments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_feature_flag_env_off_var', type_='foreignkey')
        batch_op.drop_column('off_variation_id')
