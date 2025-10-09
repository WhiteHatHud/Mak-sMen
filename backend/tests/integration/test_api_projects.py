# tests/integration/test_api_projects.py
from __future__ import annotations
import pytest

def test_create_and_list_projects(client):
    # create
    resp = client.post("/api/projects", json={"name": "P1", "description": "d"})
    assert resp.status_code == 201, resp.text
    # list
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
