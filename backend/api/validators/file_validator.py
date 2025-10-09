"""
File validation utilities for uploads.
- Extension & size checks
- UTF-8 encoding check
- CSV structure validation with dialect detection
- JSON validation (optional jsonschema)
- Parquet integrity via pyarrow
- Malicious content pattern scan
- Virus scanning stub
"""
from __future__ import annotations
from typing import Optional, Dict, Any
import io
import csv
import json
import re

MAX_BYTES = 500 * 1024 * 1024  # 500MB
ALLOWED_EXT = {"pdf", "csv", "json", "parquet"}

MALICIOUS_PATTERNS = [
    re.compile(r"<\s*script[\s>]", re.I),
    re.compile(r"javascript:\s*", re.I),
    re.compile(r"onerror\s*=", re.I),
    re.compile(r"drop\s+table", re.I),
    re.compile(r"union\s+select", re.I),
]

def validate_extension(filename: str) -> None:
    ext = (filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Unsupported file extension: {ext}")

def validate_size(size_bytes: int) -> None:
    if size_bytes > MAX_BYTES:
        raise ValueError("File exceeds 500MB limit")

def validate_utf8(data: bytes) -> None:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError("File is not valid UTF-8 encoding") from e

def scan_malicious_text(sample_text: str) -> None:
    for pat in MALICIOUS_PATTERNS:
        if pat.search(sample_text):
            raise ValueError("Malicious content pattern detected")

# -------- CSV --------
def validate_csv(file_bytes: bytes, require_header: bool = True) -> Dict[str, Any]:
    head = file_bytes[:20000]
    validate_utf8(head)
    text = head.decode("utf-8", errors="ignore")
    scan_malicious_text(text)

    try:
        dialect = csv.Sniffer().sniff(text, delimiters=",;\t|")
    except Exception:
        dialect = csv.get_dialect("excel")

    reader = csv.reader(io.StringIO(file_bytes.decode("utf-8", errors="ignore")), dialect)
    try:
        first = next(reader)
    except StopIteration:
        raise ValueError("CSV is empty")

    if require_header:
        if not any(any(c.isalpha() for c in cell) for cell in first):
            raise ValueError("CSV appears to be missing a header row")

    row_count = 1
    for _ in range(10):
        try:
            _ = next(reader)
            row_count += 1
        except StopIteration:
            break
        except Exception as e:
            raise ValueError("CSV parsing error") from e

    return {"delimiter": getattr(dialect, "delimiter", ","), "rows_sampled": row_count}

# -------- JSON --------
def validate_json(file_bytes: bytes, schema: Optional[dict] = None) -> Dict[str, Any]:
    validate_utf8(file_bytes[:20000])
    try:
        data = json.loads(file_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON") from e

    if schema:
        try:
            import jsonschema  # type: ignore
            jsonschema.validate(instance=data, schema=schema)
        except Exception as e:
            raise ValueError(f"JSON does not match schema: {e}")

    scan_malicious_text(json.dumps(data)[:20000])
    keys = []
    if isinstance(data, list) and data and isinstance(data[0], dict):
        keys = list(data[0].keys())
    elif isinstance(data, dict):
        keys = list(data.keys())

    return {"valid": True, "keys": keys}

# -------- Parquet --------
def validate_parquet(file_bytes: bytes) -> Dict[str, Any]:
    try:
        import pyarrow.parquet as pq  # type: ignore
        buf = io.BytesIO(file_bytes)
        pf = pq.ParquetFile(buf)
        meta = pf.metadata
        return {"rows": meta.num_rows, "columns": meta.num_columns}
    except Exception as e:
        raise ValueError("Invalid or corrupt Parquet file") from e

# -------- PDF (basic) --------
def validate_pdf(file_bytes: bytes) -> Dict[str, Any]:
    if not file_bytes.startswith(b"%PDF"):
        raise ValueError("Not a valid PDF header")
    scan_malicious_text(file_bytes[:4096].decode("latin-1", errors="ignore"))
    return {"valid": True}

# -------- Virus scanning stub --------
def virus_scan_stub(file_bytes: bytes) -> None:
    """Placeholder for AV integration (e.g., ClamAV, vendor API)."""
    return None

# -------- Unified entry --------
def validate_uploaded_file(
    filename: str,
    size_bytes: int,
    file_bytes: bytes,
    json_schema: Optional[dict] = None,
) -> Dict[str, Any]:
    validate_extension(filename)
    validate_size(size_bytes)
    virus_scan_stub(file_bytes)

    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        return validate_csv(file_bytes)
    if ext == "json":
        return validate_json(file_bytes, schema=json_schema)
    if ext == "parquet":
        return validate_parquet(file_bytes)
    if ext == "pdf":
        return validate_pdf(file_bytes)
    raise ValueError("Unsupported file type")
