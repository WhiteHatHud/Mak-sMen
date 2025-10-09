# tests/unit/test_validators.py
from __future__ import annotations
import io
import json
import pytest
from api.validators.file_validator import validate_uploaded_file


def test_validate_allows_csv_small():
    content = b"a,b\n1,2\n"
    validate_uploaded_file("ok.csv", size_bytes=len(content), file_bytes=content)


def test_validate_rejects_big_file():
    content = b"0" * (600 * 1024 * 1024)  # 600MB
    with pytest.raises(Exception):
        validate_uploaded_file("big.csv", size_bytes=len(content), file_bytes=content[:1024])


def test_validate_json_schema():
    body = json.dumps({"items": [1,2,3]})
    validate_uploaded_file("file.json", size_bytes=len(body), file_bytes=body.encode())

