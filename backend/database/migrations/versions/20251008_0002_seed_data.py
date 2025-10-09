# database/migrations/versions/20251008_0002_seed_data.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = '20251008_0002'
down_revision = '20251008_0001'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Minimal validation: ensure names not null
    conn.execute(sa.text("UPDATE project SET name = 'Untitled' WHERE name IS NULL"))

    # Seed a demo project
    pid = str(uuid.uuid4())
    conn.execute(sa.text("""
        INSERT INTO project(id, name, description, created_by)
        VALUES(:id, 'BETH Demo', 'Seed project for smoke tests', '00000000-0000-0000-0000-000000000000')
    """), {"id": pid})


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM project WHERE name = 'BETH Demo'"))
