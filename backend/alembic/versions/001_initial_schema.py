"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-01-24 12:00:00.000000

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
    # Create domains table
    op.create_table(
        'domains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraping_status', sa.String(length=50), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_domains_id'), 'domains', ['id'], unique=False)
    op.create_index(op.f('ix_domains_domain'), 'domains', ['domain'], unique=True)

    # Create scraping_sessions table
    op.create_table(
        'scraping_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_domains', sa.Integer(), nullable=True),
        sa.Column('processed_domains', sa.Integer(), nullable=True),
        sa.Column('successful_domains', sa.Integer(), nullable=True),
        sa.Column('failed_domains', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scraping_sessions_id'), 'scraping_sessions', ['id'], unique=False)

    # Create scraped_deals table
    op.create_table(
        'scraped_deals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('deal_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('webhook_sent', sa.Boolean(), nullable=True),
        sa.Column('webhook_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['scraping_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scraped_deals_id'), 'scraped_deals', ['id'], unique=False)
    op.create_index(op.f('ix_scraped_deals_session_id'), 'scraped_deals', ['session_id'], unique=False)
    op.create_index(op.f('ix_scraped_deals_domain'), 'scraped_deals', ['domain'], unique=False)

    # Create config table
    op.create_table(
        'config',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

    # Create cron_jobs table
    op.create_table(
        'cron_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('cron_expression', sa.String(length=100), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('batch_size', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cron_jobs_id'), 'cron_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_cron_jobs_name'), 'cron_jobs', ['name'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_cron_jobs_name'), table_name='cron_jobs')
    op.drop_index(op.f('ix_cron_jobs_id'), table_name='cron_jobs')
    op.drop_table('cron_jobs')
    
    op.drop_table('config')
    
    op.drop_index(op.f('ix_scraped_deals_domain'), table_name='scraped_deals')
    op.drop_index(op.f('ix_scraped_deals_session_id'), table_name='scraped_deals')
    op.drop_index(op.f('ix_scraped_deals_id'), table_name='scraped_deals')
    op.drop_table('scraped_deals')
    
    op.drop_index(op.f('ix_scraping_sessions_id'), table_name='scraping_sessions')
    op.drop_table('scraping_sessions')
    
    op.drop_index(op.f('ix_domains_domain'), table_name='domains')
    op.drop_index(op.f('ix_domains_id'), table_name='domains')
    op.drop_table('domains')
