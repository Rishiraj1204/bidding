"""Initial Database Schema for BIDVERIFY

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-27 17:42:00.000000

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
    # 1. permissions
    op.create_table(
        'permissions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_permissions_name'), 'permissions', ['name'], unique=True)

    # 2. roles
    op.create_table(
        'roles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)

    # 3. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('organization_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 4. role_permissions
    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.String(length=36), nullable=False),
        sa.Column('permission_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )

    # 5. user_roles
    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('role_id', sa.String(length=36), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )

    # 6. compliance_rules
    op.create_table(
        'compliance_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('rule_name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('rule_type', sa.String(length=50), nullable=False, default='DETERMINISTIC'),
        sa.Column('rule_definition', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_compliance_rules_category'), 'compliance_rules', ['category'], unique=False)
    op.create_index(op.f('ix_compliance_rules_rule_name'), 'compliance_rules', ['rule_name'], unique=True)

    # 7. tenders
    op.create_table(
        'tenders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tender_number', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('submission_deadline', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='DRAFT'),
        sa.Column('created_by_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenders_created_by_id'), 'tenders', ['created_by_id'], unique=False)
    op.create_index(op.f('ix_tenders_status'), 'tenders', ['status'], unique=False)
    op.create_index(op.f('ix_tenders_tender_number'), 'tenders', ['tender_number'], unique=True)

    # 8. tender_documents
    op.create_table(
        'tender_documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tender_id', sa.String(length=36), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='UPLOADED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tender_documents_file_hash'), 'tender_documents', ['file_hash'], unique=False)
    op.create_index(op.f('ix_tender_documents_tender_id'), 'tender_documents', ['tender_id'], unique=False)

    # 9. tender_requirements
    op.create_table(
        'tender_requirements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tender_id', sa.String(length=36), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('requirement_text', sa.Text(), nullable=False),
        sa.Column('parameter', sa.String(length=100), nullable=True),
        sa.Column('operator', sa.String(length=20), nullable=True),
        sa.Column('threshold_value', sa.String(length=255), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('mandatory', sa.Boolean(), nullable=False, default=True),
        sa.Column('source_document_id', sa.String(length=36), nullable=True),
        sa.Column('source_page', sa.Integer(), nullable=True),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['source_document_id'], ['tender_documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tender_requirements_category'), 'tender_requirements', ['category'], unique=False)
    op.create_index(op.f('ix_tender_requirements_tender_id'), 'tender_requirements', ['tender_id'], unique=False)

    # 10. bids
    op.create_table(
        'bids',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tender_id', sa.String(length=36), nullable=False),
        sa.Column('bidder_id', sa.String(length=36), nullable=False),
        sa.Column('bid_number', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='DRAFT'),
        sa.Column('submission_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['bidder_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bids_bid_number'), 'bids', ['bid_number'], unique=True)
    op.create_index(op.f('ix_bids_bidder_id'), 'bids', ['bidder_id'], unique=False)
    op.create_index(op.f('ix_bids_status'), 'bids', ['status'], unique=False)
    op.create_index(op.f('ix_bids_tender_id'), 'bids', ['tender_id'], unique=False)

    # 11. bid_documents
    op.create_table(
        'bid_documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('bid_id', sa.String(length=36), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False, default='OTHER'),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='UPLOADED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['bid_id'], ['bids.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bid_documents_bid_id'), 'bid_documents', ['bid_id'], unique=False)
    op.create_index(op.f('ix_bid_documents_document_type'), 'bid_documents', ['document_type'], unique=False)
    op.create_index(op.f('ix_bid_documents_file_hash'), 'bid_documents', ['file_hash'], unique=False)

    # 12. document_extractions
    op.create_table(
        'document_extractions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('total_pages', sa.Integer(), nullable=False, default=1),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('extracted_data', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='COMPLETED'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['bid_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_extractions_document_id'), 'document_extractions', ['document_id'], unique=False)

    # 13. extracted_entities
    op.create_table(
        'extracted_entities',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('extraction_id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('raw_value', sa.Text(), nullable=False),
        sa.Column('normalized_value', sa.Text(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source_snippet', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['extraction_id'], ['document_extractions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_extracted_entities_entity_type'), 'extracted_entities', ['entity_type'], unique=False)
    op.create_index(op.f('ix_extracted_entities_extraction_id'), 'extracted_entities', ['extraction_id'], unique=False)

    # 14. evidence
    op.create_table(
        'evidence',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('bid_document_id', sa.String(length=36), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('extracted_value', sa.Text(), nullable=False),
        sa.Column('normalized_value', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, default=1.0),
        sa.Column('snippet_text', sa.Text(), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False, default='DOCUMENT_OCR'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['bid_document_id'], ['bid_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['entity_id'], ['extracted_entities.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evidence_bid_document_id'), 'evidence', ['bid_document_id'], unique=False)
    op.create_index(op.f('ix_evidence_entity_id'), 'evidence', ['entity_id'], unique=False)
    op.create_index(op.f('ix_evidence_field_name'), 'evidence', ['field_name'], unique=False)

    # 15. compliance_results
    op.create_table(
        'compliance_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('bid_id', sa.String(length=36), nullable=False),
        sa.Column('requirement_id', sa.String(length=36), nullable=False),
        sa.Column('evidence_id', sa.String(length=36), nullable=True),
        sa.Column('rule_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='NEEDS_REVIEW'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evaluated_by', sa.String(length=50), nullable=False, default='RULE_ENGINE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['bid_id'], ['bids.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requirement_id'], ['tender_requirements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['compliance_rules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_compliance_results_bid_id'), 'compliance_results', ['bid_id'], unique=False)
    op.create_index(op.f('ix_compliance_results_evidence_id'), 'compliance_results', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_compliance_results_requirement_id'), 'compliance_results', ['requirement_id'], unique=False)
    op.create_index(op.f('ix_compliance_results_rule_id'), 'compliance_results', ['rule_id'], unique=False)
    op.create_index(op.f('ix_compliance_results_status'), 'compliance_results', ['status'], unique=False)

    # 16. verification_records
    op.create_table(
        'verification_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('bid_id', sa.String(length=36), nullable=False),
        sa.Column('compliance_result_id', sa.String(length=36), nullable=True),
        sa.Column('verification_type', sa.String(length=100), nullable=False),
        sa.Column('provider_name', sa.String(length=100), nullable=False, default='MOCK'),
        sa.Column('is_mock', sa.Boolean(), nullable=False, default=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='PENDING'),
        sa.Column('reference_id', sa.String(length=255), nullable=True),
        sa.Column('response_payload', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['bid_id'], ['bids.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['compliance_result_id'], ['compliance_results.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_records_bid_id'), 'verification_records', ['bid_id'], unique=False)
    op.create_index(op.f('ix_verification_records_compliance_result_id'), 'verification_records', ['compliance_result_id'], unique=False)
    op.create_index(op.f('ix_verification_records_status'), 'verification_records', ['status'], unique=False)
    op.create_index(op.f('ix_verification_records_verification_type'), 'verification_records', ['verification_type'], unique=False)

    # 17. review_tasks
    op.create_table(
        'review_tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('bid_id', sa.String(length=36), nullable=False),
        sa.Column('compliance_result_id', sa.String(length=36), nullable=False),
        sa.Column('assigned_to_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='PENDING'),
        sa.Column('trigger_reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['bid_id'], ['bids.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['compliance_result_id'], ['compliance_results.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_tasks_assigned_to_id'), 'review_tasks', ['assigned_to_id'], unique=False)
    op.create_index(op.f('ix_review_tasks_bid_id'), 'review_tasks', ['bid_id'], unique=False)
    op.create_index(op.f('ix_review_tasks_compliance_result_id'), 'review_tasks', ['compliance_result_id'], unique=False)
    op.create_index(op.f('ix_review_tasks_status'), 'review_tasks', ['status'], unique=False)

    # 18. review_decisions
    op.create_table(
        'review_decisions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=False),
        sa.Column('reviewer_id', sa.String(length=36), nullable=False),
        sa.Column('original_decision', sa.String(length=50), nullable=False),
        sa.Column('new_decision', sa.String(length=50), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['task_id'], ['review_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_decisions_reviewer_id'), 'review_decisions', ['reviewer_id'], unique=False)
    op.create_index(op.f('ix_review_decisions_task_id'), 'review_decisions', ['task_id'], unique=False)

    # 19. reports
    op.create_table(
        'reports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('bid_id', sa.String(length=36), nullable=False),
        sa.Column('tender_id', sa.String(length=36), nullable=False),
        sa.Column('report_number', sa.String(length=100), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('generated_by_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['bid_id'], ['bids.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['generated_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_bid_id'), 'reports', ['bid_id'], unique=False)
    op.create_index(op.f('ix_reports_generated_by_id'), 'reports', ['generated_by_id'], unique=False)
    op.create_index(op.f('ix_reports_report_number'), 'reports', ['report_number'], unique=True)
    op.create_index(op.f('ix_reports_tender_id'), 'reports', ['tender_id'], unique=False)

    # 20. notifications
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('notification_type', sa.String(length=50), nullable=False, default='INFO'),
        sa.Column('is_read', sa.Boolean(), nullable=False, default=False),
        sa.Column('related_resource_type', sa.String(length=50), nullable=True),
        sa.Column('related_resource_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    # 21. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('actor_id', sa.String(length=36), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=36), nullable=True),
        sa.Column('previous_state', sa.JSON(), nullable=True),
        sa.Column('new_state', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_id'), 'audit_logs', ['resource_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)


def downgrade() -> None:
    # Drop in reverse topological order
    op.drop_table('audit_logs')
    op.drop_table('notifications')
    op.drop_table('reports')
    op.drop_table('review_decisions')
    op.drop_table('review_tasks')
    op.drop_table('verification_records')
    op.drop_table('compliance_results')
    op.drop_table('evidence')
    op.drop_table('extracted_entities')
    op.drop_table('document_extractions')
    op.drop_table('bid_documents')
    op.drop_table('bids')
    op.drop_table('tender_requirements')
    op.drop_table('tender_documents')
    op.drop_table('tenders')
    op.drop_table('compliance_rules')
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('permissions')
