# services/storage/file_handler.py
from __future__ import annotations
from typing import Optional, Dict, Any, Iterable, Tuple
from dataclasses import dataclass
import os
import io
import gzip
import json
import shutil
import uuid
import hashlib
import logging
import tempfile
import asyncio
from datetime import datetime, timedelta, timezone


import aiofiles # type: ignore


try:
    import magic # type: ignore
except Exception: # pragma: no cover
    magic = None


from api.validators.file_validator import validate_uploaded_file


logger = logging.getLogger(__name__)


# Custom Exceptions
class ProjectNotFoundError(Exception):
    """Raised when a project is not found."""
    pass


class FileNotFoundError(Exception):
    """Raised when a file is not found."""
    pass


class FileUploadError(Exception):
    """Raised when file upload fails."""
    pass


BASE_STORAGE_DIR = os.getenv("FILE_STORAGE_DIR", os.path.join(os.getcwd(), "storage"))
TMP_DIR = os.getenv("FILE_TMP_DIR", os.path.join(BASE_STORAGE_DIR, "tmp"))
COMPRESS_THRESHOLD = int(os.getenv("FILE_COMPRESS_THRESHOLD_BYTES", str(5 * 1024 * 1024))) # 5MB
CHUNK_SIZE = int(os.getenv("FILE_CHUNK_BYTES", str(4 * 1024 * 1024))) # 4MB
RETENTION_DAYS = int(os.getenv("FILE_RETENTION_DAYS", "0")) # 0 disables auto-delete


os.makedirs(BASE_STORAGE_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

@dataclass
class FileVersion:
    version_id: str
    path: str
    size_bytes: int
    compressed: bool
    checksum_sha256: str
    created_at: str




@dataclass
class StoredFile:
    file_id: str
    project_id: int
    filename: str
    content_type: Optional[str]
    size_bytes: int
    versions: list[FileVersion]
    meta: Dict[str, Any]

# ---------------- Utility helpers ----------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def _guess_mime(path: str, default: str = "application/octet-stream") -> str:
    if magic is not None:
        try:
            ms = magic.Magic(mime=True)
            return ms.from_file(path)
        except Exception:
            pass
    # Fallback by extension
    _, ext = os.path.splitext(path.lower())
    return {
        ".csv": "text/csv",
        ".json": "application/json",
        ".parquet": "application/octet-stream",
        ".pdf": "application/pdf",
        ".gz": "application/gzip",
    }.get(ext, default)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

async def _async_write_stream(dst_path: str, stream, *, chunk_size: int = CHUNK_SIZE) -> int:
    size = 0
    async with aiofiles.open(dst_path, "wb") as f:
        while True:
            chunk = await stream.read(chunk_size)
            if not chunk:
                break
            await f.write(chunk)
            size += len(chunk)
    return size

def _compress_if_needed(path: str) -> Tuple[str, bool]:
    if os.path.getsize(path) < COMPRESS_THRESHOLD:
        return path, False
    gz_path = f"{path}.gz"
    with open(path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    os.replace(gz_path, path + ".gz.final")
    final = path + ".gz.final"
    os.replace(final, path + ".gz")
    return path + ".gz", True




def _extract_metadata(path: str, filename: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "size_bytes": os.path.getsize(path),
        "mime": _guess_mime(path),
        "sha256": _sha256_file(path),
    }
    # Lightweight content-aware metadata
    ext = (filename.rsplit(".", 1)[-1] or "").lower()
    try:
        if ext == "csv":
            import csv
            with open(path, "rt", encoding="utf-8", errors="ignore") as f:
                r = csv.reader(f)
                headers = next(r, [])
                rows = sum(1 for _ in r)
                meta.update({"csv_headers": headers, "csv_rows": rows})
        elif ext == "json":
            with open(path, "rt", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    meta.update({"json_keys": list(data[0].keys()), "json_len": len(data)})
                elif isinstance(data, dict):
                    meta.update({"json_keys": list(data.keys())})
        elif ext == "parquet":
            import pyarrow.parquet as pq # type: ignore
            pf = pq.ParquetFile(path)
            meta.update({"parquet_rows": pf.metadata.num_rows, "parquet_cols": pf.metadata.num_columns})
        elif ext == "pdf":
            try:
                from PyPDF2 import PdfReader # type: ignore
                reader = PdfReader(path)
                meta.update({"pdf_pages": len(reader.pages)})
            except Exception:
                pass
    except Exception as e:
        logger.debug("metadata-extract-failed", exc_info=e)
    return meta




# ---------------- Public API ----------------


async def save_project_files(*, project_id: int, files: Iterable, user_id: int) -> list[Dict[str, Any]]:
    """Save uploaded files locally with UUID naming, validate, compress, and version.
    `files` are FastAPI UploadFile-like objects.
    """
    project_dir = os.path.join(BASE_STORAGE_DIR, f"project_{project_id}")
    os.makedirs(project_dir, exist_ok=True)

    saved_meta: list[Dict[str, Any]] = []
    for up in files:
        original = up.filename
        file_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        tmp_path = os.path.join(TMP_DIR, f"{file_id}.part")
        size = await _async_write_stream(tmp_path, up)

        # validation (reads small head internally)
        with open(tmp_path, "rb") as rf:
            head = rf.read(min(size, 1_000_000))
            try:
                validate_uploaded_file(original, size_bytes=size, file_bytes=head)
            except Exception:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                raise

        # finalize move + optional compression
        final_dir = os.path.join(project_dir, file_id)
        os.makedirs(final_dir, exist_ok=True)
        final_path = os.path.join(final_dir, original)
        os.replace(tmp_path, final_path)
        comp_path, compressed = _compress_if_needed(final_path)

        # metadata & version manifest
        md = _extract_metadata(comp_path if compressed else final_path, original)
        checksum = md.get("sha256") or _sha256_file(comp_path if compressed else final_path)
        ver = FileVersion(
            version_id=version_id,
            path=os.path.abspath(comp_path if compressed else final_path),
            size_bytes=os.path.getsize(comp_path if compressed else final_path),
            compressed=compressed,
            checksum_sha256=checksum,
            created_at=_now_iso(),
        )
        manifest_path = os.path.join(final_dir, "manifest.json")
        manifest: Dict[str, Any] = {
            "file_id": file_id,
            "project_id": project_id,
            "filename": original,
            "versions": [],
            "created_at": _now_iso(),
        }
        if os.path.exists(manifest_path):
            try:
                manifest = json.load(open(manifest_path, "rt", encoding="utf-8"))
            except Exception:
                pass
        manifest.setdefault("versions", []).append(ver.__dict__)
        json.dump(manifest, open(manifest_path, "wt", encoding="utf-8"), indent=2)

        saved_meta.append({
            "id": len(saved_meta) + 1, # placeholder; real ID comes from DB layer
            "project_id": project_id,
            "filename": original,
            "content_type": _guess_mime(final_path),
            "size_bytes": size,
            "created_at": _now_iso(),
            "file_id": file_id,
            "version_id": version_id,
            "meta": md,
        })

        if RETENTION_DAYS > 0:
            schedule_deletion(file_id, days=RETENTION_DAYS)

    return saved_meta


async def list_project_files(*, project_id: int, user_id: int) -> list[Dict[str, Any]]:
    project_dir = os.path.join(BASE_STORAGE_DIR, f"project_{project_id}")
    items: list[Dict[str, Any]] = []
    if not os.path.isdir(project_dir):
        return items
    for file_id in os.listdir(project_dir):
        fdir = os.path.join(project_dir, file_id)
        if not os.path.isdir(fdir):
            continue
        manifest_path = os.path.join(fdir, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                man = json.load(open(manifest_path, "rt", encoding="utf-8"))
                latest = man["versions"][-1]
                items.append({
                    "id": len(items) + 1,
                    "project_id": project_id,
                    "filename": man.get("filename"),
                    "content_type": _guess_mime(latest.get("path", "")),
                    "size_bytes": latest.get("size_bytes", 0),
                    "created_at": latest.get("created_at"),
                    "file_id": file_id,
                    "version_id": latest.get("version_id"),
                })
            except Exception:
                logger.debug("manifest-read-failed", exc_info=True)
    return items

async def get_file_meta(*, file_id: str | int, user_id: int) -> Optional[Dict[str, Any]]:
    # note: routes pass numeric file_id; here we accept uuid as well
    for project_folder in os.listdir(BASE_STORAGE_DIR):
        fdir = os.path.join(BASE_STORAGE_DIR, project_folder, str(file_id))
        manifest_path = os.path.join(fdir, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                man = json.load(open(manifest_path, "rt", encoding="utf-8"))
                latest = man["versions"][-1]
                return {
                    "id": 0,
                    "project_id": man.get("project_id"),
                    "filename": man.get("filename"),
                    "content_type": _guess_mime(latest.get("path", "")),
                    "size_bytes": latest.get("size_bytes", 0),
                    "created_at": latest.get("created_at"),
                    "file_id": man.get("file_id", file_id),
                    "version_id": latest.get("version_id"),
                }
            except Exception:
                pass
    return None

async def delete_file(*, file_id: str | int, user_id: int) -> bool:
    removed = False
    for project_folder in os.listdir(BASE_STORAGE_DIR):
        fdir = os.path.join(BASE_STORAGE_DIR, project_folder, str(file_id))
        if os.path.isdir(fdir):
            shutil.rmtree(fdir, ignore_errors=True)
            removed = True
    return removed

async def stream_file_preview(*, file_id: str | int, user_id: int, limit: int = 100) -> Dict[str, Any]:
    # Find latest version path
    path = None
    for project_folder in os.listdir(BASE_STORAGE_DIR):
        fdir = os.path.join(BASE_STORAGE_DIR, project_folder, str(file_id))
        manifest_path = os.path.join(fdir, "manifest.json")
        if os.path.exists(manifest_path):
            man = json.load(open(manifest_path, "rt", encoding="utf-8"))
            latest = man["versions"][-1]
            path = latest.get("path")
            break
    if not path or not os.path.exists(path):
        raise FileNotFoundError("file not found")

    _, ext = os.path.splitext(path)
    ext = ext.lower().lstrip(".")
    preview = {"type": ext, "rows": []}

    if ext.endswith("gz"):
        # try to open compressed CSV/JSON
        with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as f:
            head = f.read(20000)
            validate_uploaded_file(os.path.basename(path).replace(".gz", ""), size_bytes=len(head), file_bytes=head.encode())
            # keep preview simple: return first lines
            preview["text_head"] = head[:5000]
            return preview

    if ext == "csv":
        import csv
        with open(path, "rt", encoding="utf-8", errors="ignore") as f:
            r = csv.reader(f)
            headers = next(r, [])
            for i, row in enumerate(r):
                if i >= limit:
                    break
                preview["rows"].append(row)
            preview["headers"] = headers
    elif ext == "json":
        with open(path, "rt", encoding="utf-8", errors="ignore") as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
            if isinstance(data, list):
                preview["rows"] = data[:limit]
            else:
                preview["object"] = data
    elif ext == "parquet":
        import pyarrow.parquet as pq # type: ignore
        import pandas as pd # type: ignore
        tbl = pq.read_table(path).to_pandas().head(limit)
        preview["rows"] = tbl.to_dict(orient="records")
    elif ext == "pdf":
        preview["text_head"] = "PDF file preview not supported; download to view"
    else:
        with open(path, "rb") as f:
            preview["bytes_head_hex"] = f.read(256).hex()
    return preview

# -------------- Deletion scheduling (lightweight) --------------


SCHEDULE_FILE = os.path.join(BASE_STORAGE_DIR, "deletion_schedule.jsonl")


def schedule_deletion(file_id: str, *, days: int) -> None:
    if days <= 0:
        return
    due = datetime.now(timezone.utc) + timedelta(days=days)
    rec = {"file_id": file_id, "delete_after": due.isoformat()}
    with open(SCHEDULE_FILE, "at", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")




def run_deletion_sweeper(now: Optional[datetime] = None) -> int:
    """Sweep scheduled deletions. Call from a cron/Celery beat."""
    now = now or datetime.now(timezone.utc)
    kept: list[str] = []
    removed = 0
    if not os.path.exists(SCHEDULE_FILE):
        return 0
    with open(SCHEDULE_FILE, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                due = datetime.fromisoformat(rec["delete_after"]) # tz-aware
                if due <= now:
                    _ = asyncio.run(delete_file(file_id=rec["file_id"], user_id=0)) # best-effort
                    removed += 1
                else:
                    kept.append(line)
            except Exception:
                kept.append(line)
    with open(SCHEDULE_FILE, "wt", encoding="utf-8") as f:
        f.writelines(kept)
    return removed