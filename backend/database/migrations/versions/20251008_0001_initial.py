# database/migrations/versions/20251008_0001_initial.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20251008_0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Enums
    project_status = postgresql.ENUM('active','archived','deleted', name='project_status')
    project_status.create(op.get_bind(), checkfirst=True)
    file_processing_status = postgresql.ENUM('uploaded','processing','completed','failed', name='file_processing_status')
    file_processing_status.create(op.get_bind(), checkfirst=True)
    analysis_status = postgresql.ENUM('pending','processing','completed','failed', name='analysis_status')
    analysis_status.create(op.get_bind(), checkfirst=True)
    report_format = postgresql.ENUM('pdf','html','json', name='report_format')
    report_format.create(op.get_bind(), checkfirst=True)

    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        'project',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('status', project_status, nullable=False, server_default='active'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index('ix_project_name', 'project', ['name'])
    op.create_index('ix_project_active_name', 'project', ['name'], postgresql_where=sa.text("status <> 'deleted'"))

    op.create_table(
        'file',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('project.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('file_type', sa.String(50)),
        sa.Column('mime_type', sa.String(100)),
        sa.Column('checksum', sa.String(64)),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploaded_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processing_status', file_processing_status, nullable=False, server_default='uploaded'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index('ix_file_project_time', 'file', ['project_id','uploaded_at'])
    op.create_index('ix_file_checksum', 'file', ['checksum'])

    op.create_table(
        'analysisresult',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('project.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_ids', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('status', analysis_status, nullable=False, server_default='pending'),
        sa.Column('ai_endpoint', sa.String(255)),
        sa.Column('llm_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('anomaly_count', sa.Integer(), server_default='0'),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('error_message', sa.Text()),
    )
    op.create_index('ix_analysis_project_status', 'analysisresult', ['project_id','status'])

    op.create_table(
        'report',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysisresult.id', ondelete='CASCADE'), nullable=False),
        sa.Column('format', report_format, nullable=False),
        sa.Column('file_path', sa.String(500)),
        sa.Column('generated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('generated_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_flagged', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('flag_reason', sa.Text()),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index('ix_report_analysis', 'report', ['analysis_id'])

    op.create_table(
        'webhook',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('project.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('events', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('secret', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_triggered', sa.TIMESTAMP(timezone=True)),
        sa.Column('failure_count', sa.Integer(), server_default='0', nullable=False),
    )
    op.create_index('ix_webhook_project', 'webhook', ['project_id'])

    # Audit log
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('table_name', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('changed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('actor', postgresql.UUID(as_uuid=True)),
        sa.Column('row_pk', postgresql.UUID(as_uuid=True)),
        sa.Column('before', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('after', postgresql.JSONB(astext_type=sa.Text())),
    )

    # Audit trigger function & attachment
    op.execute("""
    CREATE OR REPLACE FUNCTION audit_trigger_fn() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log(table_name, action, actor, row_pk, after)
        VALUES (TG_TABLE_NAME, TG_OP, current_setting('app.user', true)::uuid, NEW.id, to_jsonb(NEW));
        RETURN NEW;
      ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log(table_name, action, actor, row_pk, before, after)
        VALUES (TG_TABLE_NAME, TG_OP, current_setting('app.user', true)::uuid, NEW.id, to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;
      ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log(table_name, action, actor, row_pk, before)
        VALUES (TG_TABLE_NAME, TG_OP, current_setting('app.user', true)::uuid, OLD.id, to_jsonb(OLD));
        RETURN OLD;
      END IF;
      RETURN NULL;
    END; $$ LANGUAGE plpgsql;
    """)

    for t in ('project','file','analysisresult','report','webhook'):
        op.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = '{t}_audit_trg') THEN CREATE TRIGGER {t}_audit_trg AFTER INSERT OR UPDATE OR DELETE ON {t} FOR EACH ROW EXECUTE FUNCTION audit_trigger_fn(); END IF; END $$;")

    # RLS enablement
    op.execute("ALTER TABLE project ENABLE ROW LEVEL SECURITY;")
    op.execute("CREATE POLICY project_owner_access ON project USING (created_by = current_setting('app.user', true)::uuid OR current_setting('app.role', true) = 'admin');")
    op.execute("ALTER TABLE file ENABLE ROW LEVEL SECURITY;")
    op.execute("CREATE POLICY file_project_access ON file USING (project_id IN (SELECT id FROM project WHERE created_by = current_setting('app.user', true)::uuid) OR current_setting('app.role', true) = 'admin');")

    # Reporting view
    op.execute("""
    CREATE OR REPLACE VIEW v_project_activity AS
    SELECT p.id AS project_id, p.name,
           COUNT(DISTINCT f.id) AS files,
           COUNT(DISTINCT a.id) AS analyses,
           COUNT(DISTINCT r.id) AS reports,
           max(a.completed_at) AS last_analysis
    FROM project p
    LEFT JOIN file f ON f.project_id = p.id
    LEFT JOIN analysisresult a ON a.project_id = p.id
    LEFT JOIN report r ON r.analysis_id = a.id
    WHERE p.status <> 'deleted'
    GROUP BY p.id, p.name;
    """)


def downgrade():
    op.execute("DROP VIEW IF EXISTS v_project_activity")
    for t in ('project','file','analysisresult','report','webhook'):
        op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = '{t}_audit_trg') THEN DROP TRIGGER {t}_audit_trg ON {t}; END IF; END $$;")
    op.drop_table('audit_log')
    op.drop_index('ix_webhook_project', table_name='webhook')
    op.drop_table('webhook')
    op.drop_index('ix_report_analysis', table_name='report')
    op.drop_table('report')
    op.drop_index('ix_analysis_project_status', table_name='analysisresult')
    op.drop_table('analysisresult')
    op.drop_index('ix_file_checksum', table_name='file')
    op.drop_index('ix_file_project_time', table_name='file')
    op.drop_table('file')
    op.drop_index('ix_project_active_name', table_name='project')
    op.drop_index('ix_project_name', table_name='project')
    op.drop_table('project')
    for enum in ('report_format','analysis_status','file_processing_status','project_status'):
        op.execute(f'DROP TYPE IF EXISTS {enum}')
