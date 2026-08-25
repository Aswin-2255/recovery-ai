"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-25 14:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. merchants table
    op.create_table(
        'merchants',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('api_key', sa.String(length=255), nullable=False),
        sa.Column('webhook_endpoint', sa.String(length=512), nullable=True),
        sa.Column('auto_recovery_enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('api_key'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_merchants_email'), 'merchants', ['email'], unique=True)

    # 2. customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('historical_success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('historical_failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_spend_inr', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('trust_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_email'), 'customers', ['email'], unique=False)
    op.create_index(op.f('ix_customers_merchant_id'), 'customers', ['merchant_id'], unique=False)

    # 3. transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('customer_id', sa.String(length=64), nullable=False),
        sa.Column('order_id', sa.String(length=64), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='INR'),
        sa.Column('payment_method', sa.String(length=32), nullable=False),
        sa.Column('transaction_type', sa.String(length=32), nullable=False, server_default='one_time'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('failure_category', sa.String(length=32), nullable=False, server_default='none'),
        sa.Column('failure_code', sa.String(length=64), nullable=True),
        sa.Column('failure_reason', sa.String(length=512), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries_allowed', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('gateway_reference', sa.String(length=128), nullable=True),
        sa.Column('is_synthetic', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('is_degradation_incident', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_customer_id'), 'transactions', ['customer_id'], unique=False)
    op.create_index(op.f('ix_transactions_failure_code'), 'transactions', ['failure_code'], unique=False)
    op.create_index(op.f('ix_transactions_is_degradation_incident'), 'transactions', ['is_degradation_incident'], unique=False)
    op.create_index(op.f('ix_transactions_mcht_status_ts'), 'transactions', ['merchant_id', 'status', 'timestamp'], unique=False)
    op.create_index(op.f('ix_transactions_merchant_id'), 'transactions', ['merchant_id'], unique=False)
    op.create_index(op.f('ix_transactions_method_status'), 'transactions', ['payment_method', 'status'], unique=False)
    op.create_index(op.f('ix_transactions_order_id'), 'transactions', ['order_id'], unique=False)
    op.create_index(op.f('ix_transactions_payment_method'), 'transactions', ['payment_method'], unique=False)
    op.create_index(op.f('ix_transactions_status'), 'transactions', ['status'], unique=False)
    op.create_index(op.f('ix_transactions_timestamp'), 'transactions', ['timestamp'], unique=False)

    # 4. recovery_cases table
    op.create_table(
        'recovery_cases',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('transaction_id', sa.String(length=64), nullable=False),
        sa.Column('merchant_id', sa.String(length=64), nullable=False),
        sa.Column('revenue_at_risk', sa.Float(), nullable=False),
        sa.Column('recovery_probability', sa.Float(), nullable=True),
        sa.Column('priority', sa.String(length=32), nullable=False, server_default='medium'),
        sa.Column('classification', sa.String(length=32), nullable=False, server_default='uncertain'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('reason', sa.String(length=512), nullable=True),
        sa.Column('root_cause_summary', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id')
    )
    op.create_index(op.f('ix_recovery_cases_classification'), 'recovery_cases', ['classification'], unique=False)
    op.create_index(op.f('ix_recovery_cases_created_at'), 'recovery_cases', ['created_at'], unique=False)
    op.create_index(op.f('ix_recovery_cases_mcht_status'), 'recovery_cases', ['merchant_id', 'status'], unique=False)
    op.create_index(op.f('ix_recovery_cases_merchant_id'), 'recovery_cases', ['merchant_id'], unique=False)
    op.create_index(op.f('ix_recovery_cases_priority'), 'recovery_cases', ['priority'], unique=False)
    op.create_index(op.f('ix_recovery_cases_status'), 'recovery_cases', ['status'], unique=False)
    op.create_index(op.f('ix_recovery_cases_transaction_id'), 'recovery_cases', ['transaction_id'], unique=True)

    # 5. recovery_actions table
    op.create_table(
        'recovery_actions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=64), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('amount_recovered', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('result', sa.String(length=512), nullable=True),
        sa.Column('execution_details_json', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_actions_case_status'), 'recovery_actions', ['recovery_case_id', 'status'], unique=False)
    op.create_index(op.f('ix_recovery_actions_created_at'), 'recovery_actions', ['created_at'], unique=False)
    op.create_index(op.f('ix_recovery_actions_recovery_case_id'), 'recovery_actions', ['recovery_case_id'], unique=False)
    op.create_index(op.f('ix_recovery_actions_status'), 'recovery_actions', ['status'], unique=False)

    # 6. agent_decisions table
    op.create_table(
        'agent_decisions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('recovery_case_id', sa.String(length=64), nullable=False),
        sa.Column('decision', sa.String(length=64), nullable=False),
        sa.Column('recommended_action', sa.String(length=64), nullable=True),
        sa.Column('reasoning_summary', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('policy_approved', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('policy_rejection_reason', sa.String(length=512), nullable=True),
        sa.Column('execution_payload_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_decisions_created_at'), 'agent_decisions', ['created_at'], unique=False)
    op.create_index(op.f('ix_agent_decisions_recovery_case_id'), 'agent_decisions', ['recovery_case_id'], unique=False)

    # 7. audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=False),
        sa.Column('actor', sa.String(length=64), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('what_happened', sa.Text(), nullable=False),
        sa.Column('what_caused_it', sa.Text(), nullable=True),
        sa.Column('action_taken', sa.Text(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_action'), 'audit_logs', ['actor', 'action'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity'), 'audit_logs', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_type'), 'audit_logs', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('agent_decisions')
    op.drop_table('recovery_actions')
    op.drop_table('recovery_cases')
    op.drop_table('transactions')
    op.drop_table('customers')
    op.drop_table('merchants')
