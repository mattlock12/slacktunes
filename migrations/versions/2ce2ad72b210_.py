"""empty message

Revision ID: 2ce2ad72b210
Revises: 
Create Date: 2019-07-18 15:34:25.301049

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2ce2ad72b210'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('slack_id', sa.String(length=100), nullable=True),
    sa.Column('last_posted_auth_error', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_slack_id'), 'user', ['slack_id'], unique=True)
    op.create_table('credential',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('platform', sa.Enum('YOUTUBE', 'SPOTIFY', name='platform'), nullable=True),
    sa.Column('credentials', sa.String(length=5000), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'platform', name='_user_platform_constraint')
    )
    op.create_index(op.f('ix_credential_user_id'), 'credential', ['user_id'], unique=False)
    op.create_table('playlist',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('channel_id', sa.String(length=100), nullable=True),
    sa.Column('platform', sa.Enum('YOUTUBE', 'SPOTIFY', name='platform'), nullable=True),
    sa.Column('platform_id', sa.String(length=100), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('platform', 'platform_id', name='_platform_platformid_constraint')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('playlist')
    op.drop_index(op.f('ix_credential_user_id'), table_name='credential')
    op.drop_table('credential')
    op.drop_index(op.f('ix_user_slack_id'), table_name='user')
    op.drop_table('user')
    # ### end Alembic commands ###