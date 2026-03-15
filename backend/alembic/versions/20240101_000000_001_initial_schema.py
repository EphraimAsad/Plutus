"""Initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

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
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'operations_analyst', 'operations_manager', 'read_only', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # Source systems table
    op.create_table(
        'source_systems',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('source_type', sa.Enum('csv', 'xlsx', 'api', 'database', name='sourcetype'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('config_json', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'])
    )

    # Source schema mappings table
    op.create_table(
        'source_schema_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_system_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('mapping_json', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_system_id'], ['source_systems.id'])
    )
    op.create_index('ix_source_schema_mappings_source_system_id', 'source_schema_mappings', ['source_system_id'])

    # Ingestion jobs table
    op.create_table(
        'ingestion_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_system_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_type', sa.Enum('manual_upload', 'scheduled', 'api_import', name='ingestionjobtype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'validating', 'completed', 'failed', 'cancelled', name='ingestionjobstatus'), nullable=False),
        sa.Column('file_name', sa.String(500), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('storage_path', sa.String(1000), nullable=True),
        sa.Column('rows_received', sa.Integer(), nullable=False, default=0),
        sa.Column('rows_valid', sa.Integer(), nullable=False, default=0),
        sa.Column('rows_invalid', sa.Integer(), nullable=False, default=0),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('triggered_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_system_id'], ['source_systems.id']),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'])
    )
    op.create_index('ix_ingestion_jobs_source_system_id', 'ingestion_jobs', ['source_system_id'])
    op.create_index('ix_ingestion_jobs_status', 'ingestion_jobs', ['status'])
    op.create_index('ix_ingestion_jobs_file_hash', 'ingestion_jobs', ['file_hash'])

    # Raw records table
    op.create_table(
        'raw_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ingestion_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_system_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_row_number', sa.Integer(), nullable=False),
        sa.Column('source_record_hash', sa.String(64), nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['ingestion_job_id'], ['ingestion_jobs.id']),
        sa.ForeignKeyConstraint(['source_system_id'], ['source_systems.id'])
    )
    op.create_index('ix_raw_records_ingestion_job_id', 'raw_records', ['ingestion_job_id'])
    op.create_index('ix_raw_records_source_system_id', 'raw_records', ['source_system_id'])
    op.create_index('ix_raw_records_source_record_hash', 'raw_records', ['source_record_hash'])

    # Validation results table
    op.create_table(
        'validation_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('raw_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False),
        sa.Column('error_codes', postgresql.JSONB(), nullable=False, default=[]),
        sa.Column('warning_codes', postgresql.JSONB(), nullable=False, default=[]),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['raw_record_id'], ['raw_records.id']),
        sa.UniqueConstraint('raw_record_id')
    )
    op.create_index('ix_validation_results_raw_record_id', 'validation_results', ['raw_record_id'])
    op.create_index('ix_validation_results_is_valid', 'validation_results', ['is_valid'])

    # Canonical records table
    op.create_table(
        'canonical_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('raw_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_system_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_type', sa.String(100), nullable=True),
        sa.Column('external_record_id', sa.String(255), nullable=True),
        sa.Column('account_id', sa.String(255), nullable=True),
        sa.Column('entity_id', sa.String(255), nullable=True),
        sa.Column('record_date', sa.Date(), nullable=True),
        sa.Column('settlement_date', sa.Date(), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('amount', sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column('reference_code', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('counterparty', sa.String(500), nullable=True),
        sa.Column('record_hash', sa.String(64), nullable=False),
        sa.Column('normalized_payload', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['raw_record_id'], ['raw_records.id']),
        sa.ForeignKeyConstraint(['source_system_id'], ['source_systems.id']),
        sa.UniqueConstraint('raw_record_id')
    )
    op.create_index('ix_canonical_records_raw_record_id', 'canonical_records', ['raw_record_id'])
    op.create_index('ix_canonical_records_source_system_id', 'canonical_records', ['source_system_id'])
    op.create_index('ix_canonical_records_record_type', 'canonical_records', ['record_type'])
    op.create_index('ix_canonical_records_external_record_id', 'canonical_records', ['external_record_id'])
    op.create_index('ix_canonical_records_account_id', 'canonical_records', ['account_id'])
    op.create_index('ix_canonical_records_entity_id', 'canonical_records', ['entity_id'])
    op.create_index('ix_canonical_records_record_date', 'canonical_records', ['record_date'])
    op.create_index('ix_canonical_records_amount', 'canonical_records', ['amount'])
    op.create_index('ix_canonical_records_reference_code', 'canonical_records', ['reference_code'])
    op.create_index('ix_canonical_records_record_hash', 'canonical_records', ['record_hash'])
    op.create_index('ix_canonical_records_date_amount', 'canonical_records', ['record_date', 'amount'])
    op.create_index('ix_canonical_records_source_date', 'canonical_records', ['source_system_id', 'record_date'])

    # Reconciliation runs table
    op.create_table(
        'reconciliation_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'matching', 'reviewing', 'completed', 'failed', 'cancelled', name='reconciliationstatus'), nullable=False),
        sa.Column('parameters_json', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('triggered_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_left_records', sa.Integer(), default=0),
        sa.Column('total_right_records', sa.Integer(), default=0),
        sa.Column('total_matched', sa.Integer(), default=0),
        sa.Column('total_unmatched', sa.Integer(), default=0),
        sa.Column('total_exceptions', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'])
    )
    op.create_index('ix_reconciliation_runs_status', 'reconciliation_runs', ['status'])

    # Match candidates table
    op.create_table(
        'match_candidates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reconciliation_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('left_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('right_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('match_type', sa.Enum('exact', 'tolerance', 'fuzzy', 'scored', 'manual', name='matchtype'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('feature_payload', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('decision_status', sa.Enum('pending', 'auto_matched', 'auto_rejected', 'requires_review', 'manually_matched', 'manually_rejected', name='matchdecisionstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reconciliation_run_id'], ['reconciliation_runs.id']),
        sa.ForeignKeyConstraint(['left_record_id'], ['canonical_records.id']),
        sa.ForeignKeyConstraint(['right_record_id'], ['canonical_records.id'])
    )
    op.create_index('ix_match_candidates_reconciliation_run_id', 'match_candidates', ['reconciliation_run_id'])
    op.create_index('ix_match_candidates_left_record_id', 'match_candidates', ['left_record_id'])
    op.create_index('ix_match_candidates_right_record_id', 'match_candidates', ['right_record_id'])
    op.create_index('ix_match_candidates_score', 'match_candidates', ['score'])
    op.create_index('ix_match_candidates_decision_status', 'match_candidates', ['decision_status'])
    op.create_index('ix_match_candidates_records', 'match_candidates', ['left_record_id', 'right_record_id'])
    op.create_index('ix_match_candidates_run_status', 'match_candidates', ['reconciliation_run_id', 'decision_status'])

    # Reconciled matches table
    op.create_table(
        'reconciled_matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reconciliation_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('match_group_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resolution_type', sa.Enum('one_to_one', 'one_to_many', 'many_to_one', 'many_to_many', name='resolutiontype'), nullable=False),
        sa.Column('status', sa.Enum('matched', 'partial', 'unmatched', 'duplicate_candidate', 'anomaly_flagged', 'requires_review', 'resolved_manually', name='matchstatus'), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reconciliation_run_id'], ['reconciliation_runs.id']),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'])
    )
    op.create_index('ix_reconciled_matches_reconciliation_run_id', 'reconciled_matches', ['reconciliation_run_id'])
    op.create_index('ix_reconciled_matches_match_group_id', 'reconciled_matches', ['match_group_id'])
    op.create_index('ix_reconciled_matches_status', 'reconciled_matches', ['status'])

    # Reconciled match items table
    op.create_table(
        'reconciled_match_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reconciled_match_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('canonical_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('amount_contribution', sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reconciled_match_id'], ['reconciled_matches.id']),
        sa.ForeignKeyConstraint(['canonical_record_id'], ['canonical_records.id'])
    )
    op.create_index('ix_reconciled_match_items_reconciled_match_id', 'reconciled_match_items', ['reconciled_match_id'])
    op.create_index('ix_reconciled_match_items_canonical_record_id', 'reconciled_match_items', ['canonical_record_id'])

    # Unmatched records table
    op.create_table(
        'unmatched_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reconciliation_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('canonical_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reason_code', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reconciliation_run_id'], ['reconciliation_runs.id']),
        sa.ForeignKeyConstraint(['canonical_record_id'], ['canonical_records.id'])
    )
    op.create_index('ix_unmatched_records_reconciliation_run_id', 'unmatched_records', ['reconciliation_run_id'])
    op.create_index('ix_unmatched_records_canonical_record_id', 'unmatched_records', ['canonical_record_id'])

    # Anomalies table
    op.create_table(
        'anomalies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reconciliation_run_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('canonical_record_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('anomaly_type', sa.Enum('duplicate_pattern', 'unusually_large_amount', 'abnormal_date_lag', 'repeated_unmatched_counterparty', 'suspicious_clustering', 'volume_spike', 'amount_pattern', 'reference_anomaly', 'statistical_outlier', name='anomalytype'), nullable=False),
        sa.Column('severity', sa.Enum('low', 'medium', 'high', 'critical', name='anomalyseverity'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False, default=0.0),
        sa.Column('details_json', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reconciliation_run_id'], ['reconciliation_runs.id']),
        sa.ForeignKeyConstraint(['canonical_record_id'], ['canonical_records.id'])
    )
    op.create_index('ix_anomalies_reconciliation_run_id', 'anomalies', ['reconciliation_run_id'])
    op.create_index('ix_anomalies_canonical_record_id', 'anomalies', ['canonical_record_id'])
    op.create_index('ix_anomalies_anomaly_type', 'anomalies', ['anomaly_type'])
    op.create_index('ix_anomalies_severity', 'anomalies', ['severity'])
    op.create_index('ix_anomalies_run_severity', 'anomalies', ['reconciliation_run_id', 'severity'])

    # Exceptions table
    op.create_table(
        'exceptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reconciliation_run_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('exception_type', sa.Enum('amount_mismatch', 'date_mismatch', 'description_mismatch', 'low_confidence_candidate', 'duplicate_suspected', 'missing_counter_entry', 'invalid_row', 'ambiguous_multi_match', 'anomaly_detected', 'validation_error', 'reference_mismatch', name='exceptiontype'), nullable=False),
        sa.Column('severity', sa.Enum('low', 'medium', 'high', 'critical', name='exceptionseverity'), nullable=False),
        sa.Column('status', sa.Enum('open', 'in_review', 'resolved', 'dismissed', 'escalated', name='exceptionstatus'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('related_record_ids', postgresql.JSONB(), nullable=False, default=[]),
        sa.Column('related_match_candidate_ids', postgresql.JSONB(), nullable=False, default=[]),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['reconciliation_run_id'], ['reconciliation_runs.id']),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id']),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'])
    )
    op.create_index('ix_exceptions_reconciliation_run_id', 'exceptions', ['reconciliation_run_id'])
    op.create_index('ix_exceptions_exception_type', 'exceptions', ['exception_type'])
    op.create_index('ix_exceptions_severity', 'exceptions', ['severity'])
    op.create_index('ix_exceptions_status', 'exceptions', ['status'])
    op.create_index('ix_exceptions_assigned_to', 'exceptions', ['assigned_to'])
    op.create_index('ix_exceptions_status_severity', 'exceptions', ['status', 'severity'])
    op.create_index('ix_exceptions_status_assigned', 'exceptions', ['status', 'assigned_to'])

    # Exception notes table
    op.create_table(
        'exception_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exception_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['exception_id'], ['exceptions.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )
    op.create_index('ix_exception_notes_exception_id', 'exception_notes', ['exception_id'])

    # Reports table
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_type', sa.Enum('reconciliation_summary', 'unmatched_items', 'exception_backlog', 'anomaly_report', 'ingestion_health', 'operational_summary', 'match_analysis', 'trend_analysis', name='reporttype'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('filters_json', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('status', sa.Enum('pending', 'generating', 'completed', 'failed', name='reportstatus'), nullable=False),
        sa.Column('file_path', sa.String(1000), nullable=True),
        sa.Column('file_format', sa.Enum('json', 'csv', 'excel', 'pdf', name='reportformat'), nullable=True),
        sa.Column('generated_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.String(2000), nullable=True),
        sa.Column('parameters_json', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['generated_by'], ['users.id'])
    )
    op.create_index('ix_reports_report_type', 'reports', ['report_type'])
    op.create_index('ix_reports_status', 'reports', ['status'])
    op.create_index('ix_reports_type_generated', 'reports', ['report_type', 'generated_at'])

    # Report snapshots table
    op.create_table(
        'report_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('snapshot_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'])
    )
    op.create_index('ix_report_snapshots_report_id', 'report_snapshots', ['report_id'])

    # AI explanations table
    op.create_table(
        'ai_explanations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parent_type', sa.Enum('exception', 'anomaly', 'report', 'match_candidate', 'reconciliation_run', name='parenttype'), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exception_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('input_json', postgresql.JSONB(), nullable=False),
        sa.Column('prompt_version', sa.String(50), nullable=False, default='v1'),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, default='ollama'),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'rejected', name='aiexplanationstatus'), nullable=False),
        sa.Column('output_text', sa.Text(), nullable=True),
        sa.Column('safety_flags', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('requested_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['exception_id'], ['exceptions.id']),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id']),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'])
    )
    op.create_index('ix_ai_explanations_parent_type', 'ai_explanations', ['parent_type'])
    op.create_index('ix_ai_explanations_parent_id', 'ai_explanations', ['parent_id'])
    op.create_index('ix_ai_explanations_exception_id', 'ai_explanations', ['exception_id'])
    op.create_index('ix_ai_explanations_report_id', 'ai_explanations', ['report_id'])
    op.create_index('ix_ai_explanations_status', 'ai_explanations', ['status'])
    op.create_index('ix_ai_explanations_parent', 'ai_explanations', ['parent_type', 'parent_id'])

    # Audit logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('before_json', postgresql.JSONB(), nullable=True),
        sa.Column('after_json', postgresql.JSONB(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'])
    )
    op.create_index('ix_audit_logs_actor_user_id', 'audit_logs', ['actor_user_id'])
    op.create_index('ix_audit_logs_action_type', 'audit_logs', ['action_type'])
    op.create_index('ix_audit_logs_entity_type', 'audit_logs', ['entity_type'])
    op.create_index('ix_audit_logs_entity_id', 'audit_logs', ['entity_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_entity', 'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_logs_action_time', 'audit_logs', ['action_type', 'created_at'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('ai_explanations')
    op.drop_table('report_snapshots')
    op.drop_table('reports')
    op.drop_table('exception_notes')
    op.drop_table('exceptions')
    op.drop_table('anomalies')
    op.drop_table('unmatched_records')
    op.drop_table('reconciled_match_items')
    op.drop_table('reconciled_matches')
    op.drop_table('match_candidates')
    op.drop_table('reconciliation_runs')
    op.drop_table('canonical_records')
    op.drop_table('validation_results')
    op.drop_table('raw_records')
    op.drop_table('ingestion_jobs')
    op.drop_table('source_schema_mappings')
    op.drop_table('source_systems')
    op.drop_table('users')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS userrole')
    op.execute('DROP TYPE IF EXISTS sourcetype')
    op.execute('DROP TYPE IF EXISTS ingestionjobtype')
    op.execute('DROP TYPE IF EXISTS ingestionjobstatus')
    op.execute('DROP TYPE IF EXISTS reconciliationstatus')
    op.execute('DROP TYPE IF EXISTS matchtype')
    op.execute('DROP TYPE IF EXISTS matchdecisionstatus')
    op.execute('DROP TYPE IF EXISTS resolutiontype')
    op.execute('DROP TYPE IF EXISTS matchstatus')
    op.execute('DROP TYPE IF EXISTS anomalytype')
    op.execute('DROP TYPE IF EXISTS anomalyseverity')
    op.execute('DROP TYPE IF EXISTS exceptiontype')
    op.execute('DROP TYPE IF EXISTS exceptionseverity')
    op.execute('DROP TYPE IF EXISTS exceptionstatus')
    op.execute('DROP TYPE IF EXISTS reporttype')
    op.execute('DROP TYPE IF EXISTS reportstatus')
    op.execute('DROP TYPE IF EXISTS reportformat')
    op.execute('DROP TYPE IF EXISTS parenttype')
    op.execute('DROP TYPE IF EXISTS aiexplanationstatus')
