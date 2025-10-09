# database/schema.sql
-- PostgreSQL schema for BETH anomaly detection platform
-- Run with psql or in migration as needed.

-- Enums
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_status') THEN
    CREATE TYPE project_status AS ENUM ('active', 'archived', 'deleted');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'file_processing_status') THEN
    CREATE TYPE file_processing_status AS ENUM ('uploaded','processing','completed','failed');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'analysis_status') THEN
    CREATE TYPE analysis_status AS ENUM ('pending','processing','completed','failed');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'report_format') THEN
    CREATE TYPE report_format AS ENUM ('pdf','html','json');
  END IF;
END $$;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Core tables
CREATE TABLE IF NOT EXISTS project (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  created_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  status project_status NOT NULL DEFAULT 'active',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT project_name_chk CHECK (char_length(name) > 0)
);
CREATE INDEX IF NOT EXISTS ix_project_name ON project(name);
CREATE INDEX IF NOT EXISTS ix_project_active_name ON project(name) WHERE status <> 'deleted';

CREATE TABLE IF NOT EXISTS file (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  filename VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_size BIGINT NOT NULL CHECK (file_size >= 0),
  file_type VARCHAR(50),
  mime_type VARCHAR(100),
  checksum VARCHAR(64),
  uploaded_by UUID NOT NULL,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processing_status file_processing_status NOT NULL DEFAULT 'uploaded',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_file_project_time ON file(project_id, uploaded_at DESC);
CREATE INDEX IF NOT EXISTS ix_file_checksum ON file(checksum);

CREATE TABLE IF NOT EXISTS analysisresult (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  file_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  status analysis_status NOT NULL DEFAULT 'pending',
  ai_endpoint VARCHAR(255),
  llm_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  anomaly_count INT DEFAULT 0,
  results JSONB NOT NULL DEFAULT '{}'::jsonb,
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_message TEXT
);
CREATE INDEX IF NOT EXISTS ix_analysis_project_status ON analysisresult(project_id, status);

CREATE TABLE IF NOT EXISTS report (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  analysis_id UUID NOT NULL REFERENCES analysisresult(id) ON DELETE CASCADE,
  format report_format NOT NULL,
  file_path VARCHAR(500),
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  generated_by UUID NOT NULL,
  is_flagged BOOLEAN NOT NULL DEFAULT FALSE,
  flag_reason TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_report_analysis ON report(analysis_id);

CREATE TABLE IF NOT EXISTS webhook (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  url VARCHAR(500) NOT NULL,
  events JSONB NOT NULL DEFAULT '[]'::jsonb,
  secret VARCHAR(255),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_triggered TIMESTAMPTZ,
  failure_count INT NOT NULL DEFAULT 0,
  CONSTRAINT url_chk CHECK (char_length(url) > 0)
);
CREATE INDEX IF NOT EXISTS ix_webhook_project ON webhook(project_id);

-- Audit table + trigger
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  table_name TEXT NOT NULL,
  action TEXT NOT NULL,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor UUID,
  row_pk UUID,
  before JSONB,
  after JSONB
);

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
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  PERFORM 1 FROM pg_trigger WHERE tgname = 'project_audit_trg';
  IF NOT FOUND THEN
    CREATE TRIGGER project_audit_trg AFTER INSERT OR UPDATE OR DELETE ON project
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_fn();
  END IF;
END $$;

-- Views for reporting
CREATE OR REPLACE VIEW v_project_activity AS
SELECT p.id AS project_id,
       p.name,
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

-- Row-Level Security (example: restrict by created_by unless elevated)
ALTER TABLE project ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_owner_access ON project
  USING (created_by = current_setting('app.user', true)::uuid OR current_setting('app.role', true) = 'admin');

ALTER TABLE file ENABLE ROW LEVEL SECURITY;
CREATE POLICY file_project_access ON file
  USING (project_id IN (SELECT id FROM project WHERE created_by = current_setting('app.user', true)::uuid) OR current_setting('app.role', true) = 'admin');

-- Stored procedure: archive project (set status, soft delete timestamp)
CREATE OR REPLACE FUNCTION sp_archive_project(pid UUID) RETURNS VOID AS $$
BEGIN
  UPDATE project SET status='archived', deleted_at=now() WHERE id=pid;
END; $$ LANGUAGE plpgsql;