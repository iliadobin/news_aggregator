"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2024-12-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('target_chat_id', sa.BigInteger(), nullable=True),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)

    # Create sources table
    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('type', sa.Enum('CHANNEL', 'GROUP', 'PRIVATE', name='sourcetype'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sources_telegram_chat_id'), 'sources', ['telegram_chat_id'], unique=True)

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'source_id', name='uq_user_source')
    )
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_source_id'), 'subscriptions', ['source_id'], unique=False)

    # Create filters table
    op.create_table(
        'filters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('mode', sa.Enum('KEYWORD_ONLY', 'SEMANTIC_ONLY', 'COMBINED', name='filtermode'), nullable=False, server_default='COMBINED'),
        sa.Column('keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('topics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('semantic_threshold', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_filters_user_id'), 'filters', ['user_id'], unique=False)

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_message_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_message_id', 'chat_id', name='uq_telegram_message_chat')
    )
    op.create_index(op.f('ix_messages_telegram_message_id'), 'messages', ['telegram_message_id'], unique=False)
    op.create_index(op.f('ix_messages_chat_id'), 'messages', ['chat_id'], unique=False)
    op.create_index(op.f('ix_messages_source_id'), 'messages', ['source_id'], unique=False)
    op.create_index(op.f('ix_messages_date'), 'messages', ['date'], unique=False)

    # Create filter_matches table
    op.create_table(
        'filter_matches',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('filter_id', sa.Integer(), nullable=False),
        sa.Column('match_type', sa.Enum('KEYWORD', 'SEMANTIC', 'COMBINED', name='matchtype'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['filter_id'], ['filters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id', 'filter_id', name='uq_message_filter')
    )
    op.create_index(op.f('ix_filter_matches_message_id'), 'filter_matches', ['message_id'], unique=False)
    op.create_index(op.f('ix_filter_matches_filter_id'), 'filter_matches', ['filter_id'], unique=False)

    # Create forwarded_messages table
    op.create_table(
        'forwarded_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filter_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('target_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('forwarded_telegram_message_id', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', name='forwardedstatus'), nullable=False, server_default='PENDING'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('forwarded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['filter_id'], ['filters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_forwarded_messages_user_id'), 'forwarded_messages', ['user_id'], unique=False)
    op.create_index(op.f('ix_forwarded_messages_filter_id'), 'forwarded_messages', ['filter_id'], unique=False)
    op.create_index(op.f('ix_forwarded_messages_message_id'), 'forwarded_messages', ['message_id'], unique=False)
    op.create_index(op.f('ix_forwarded_messages_target_chat_id'), 'forwarded_messages', ['target_chat_id'], unique=False)


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('forwarded_messages')
    op.drop_table('filter_matches')
    op.drop_table('messages')
    op.drop_table('filters')
    op.drop_table('subscriptions')
    op.drop_table('sources')
    op.drop_table('users')
    
    # Drop custom enums
    op.execute('DROP TYPE IF EXISTS forwardedstatus')
    op.execute('DROP TYPE IF EXISTS matchtype')
    op.execute('DROP TYPE IF EXISTS filtermode')
    op.execute('DROP TYPE IF EXISTS sourcetype')
