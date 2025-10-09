# tests/integration/test_files_flow.py
from __future__ import annotations
import io

def test_file_upload_and_preview(client, tmp_path):
    csv_path = (tmp_path / "data.csv")
    csv_path.write_text("a,b\n1,2\n3,4\n")
    with open(csv_path, "rb") as f:
        resp = client.post("/api/projects/1/files", files=[("files", ("data.csv", f, "text/csv"))])
    assert resp.status_code == 200, resp.text
    file_id = resp.json()["data"]["files"][0]["file_id"]
    # preview
    resp = client.get(f"/api/files/{file_id}/preview")
    assert resp.status_code == 200
