# workers/analysis_worker.py
from __future__ import annotations
from typing import List, Dict, Any, Optional, Iterable, Tuple
from dataclasses import dataclass
import os
import io
import gc
import json
import time
import uuid
import gzip
import logging
from datetime import datetime, timezone


from celery import Celery, group, chord, states
from celery.exceptions import SoftTimeLimitExceeded


import numpy as np
import pandas as pd


# Local services
from services.anomaly_detection.preprocessor import preprocess
from services.anomaly_detection.feature_engineering import build_feature_pipeline
from services.anomaly_detection.detector import AnomalyDetector, DetectionResult
from services.llm.explainer import ExplainerService


# Storage helpers (manifest path lookup)
from services.storage.file_handler import _extract_metadata # reuse metadata extractor


# Monitoring hooks (stubs; wire to your metrics backend)
from utils.metrics import observe_latency_ms


logger = logging.getLogger(__name__)

# ---------------- Celery App ----------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    import redis as redis_sync # type: ignore
    rds = redis_sync.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception: # pragma: no cover
    rds = None


celery_app = Celery(
"beth_workers",
broker=CELERY_BROKER_URL,
backend=CELERY_BACKEND_URL,
)


celery_app.conf.update(
task_time_limit=int(os.getenv("CELERY_TASK_HARD_LIMIT", "3600")), # hard time limit
task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_LIMIT", "3300")),
worker_max_tasks_per_child=int(os.getenv("CELERY_MAX_TASKS_PER_CHILD", "20")),
worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "4")),
task_acks_late=True,
task_reject_on_worker_lost=True,
)


CHUNK_ROWS = int(os.getenv("ANALYSIS_CHUNK_ROWS", "200000"))
TOP_N = int(os.getenv("ANALYSIS_TOP_N", "100"))
P_THRESHOLD = float(os.getenv("ANALYSIS_PROB_THRESHOLD", "0.98"))

# --------------- Progress helpers ---------------


def _status_key(aid: str) -> str:
    return f"analysis:{aid}:status"


def _ckpt_key(aid: str) -> str:
    return f"analysis:{aid}:ckpt"


def _result_key(aid: str) -> str:
    return f"analysis:{aid}:result"


def set_status(aid: str, **kwargs: Any) -> None:
    if rds is None:
        return
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(), **kwargs}
    rds.set(_status_key(aid), json.dumps(payload), ex=60 * 60 * 24)


def get_status(aid: str) -> Optional[Dict[str, Any]]:
    if rds is None:
        return None
    v = rds.get(_status_key(aid))
    return json.loads(v) if v else None


def save_ckpt(aid: str, ckpt: Dict[str, Any]) -> None:
    if rds is None:
        return
    rds.set(_ckpt_key(aid), json.dumps(ckpt), ex=60 * 60 * 24)


def load_ckpt(aid: str) -> Dict[str, Any]:
    if rds is None:
        return {}
    v = rds.get(_ckpt_key(aid))
    return json.loads(v) if v else {}

def cache_results(aid: str, result: Dict[str, Any]) -> None:
    if rds is None:
        return
    rds.set(_result_key(aid), json.dumps(result), ex=60 * 60 * 24 * 7)


def get_cached_results(aid: str) -> Optional[Dict[str, Any]]:
    if rds is None:
        return None
    v = rds.get(_result_key(aid))
    return json.loads(v) if v else None

# --------------- File path lookup ---------------
BASE_STORAGE_DIR = os.getenv("FILE_STORAGE_DIR", os.path.join(os.getcwd(), "storage"))


def _find_file_path_by_id(file_id: int | str) -> Optional[str]:
    for project_folder in os.listdir(BASE_STORAGE_DIR):
        fdir = os.path.join(BASE_STORAGE_DIR, project_folder, str(file_id))
        manifest = os.path.join(fdir, "manifest.json")
        if os.path.exists(manifest):
            try:
                man = json.load(open(manifest, "rt", encoding="utf-8"))
                latest = man["versions"][-1]
                return latest.get("path")
            except Exception:
                continue
    return None

# --------------- Chunked readers ---------------


def iter_csv(path: str, chunksize: int) -> Iterable[pd.DataFrame]:
    for chunk in pd.read_csv(path, chunksize=chunksize, low_memory=False):
        yield chunk


def iter_parquet(path: str, chunksize: int) -> Iterable[pd.DataFrame]:
    try:
        import pyarrow.parquet as pq # type: ignore
        pf = pq.ParquetFile(path)
        for rg in range(pf.num_row_groups):
            tbl = pf.read_row_group(rg)
            df = tbl.to_pandas()
            # If row group too big, split within
            if chunksize and len(df) > chunksize:
                for i in range(0, len(df), chunksize):
                    yield df.iloc[i:i+chunksize]
            else:
                yield df
    except Exception: # fallback
        yield pd.read_parquet(path)


def iter_json(path: str, chunksize: int) -> Iterable[pd.DataFrame]:
    # Support NDJSON (json lines). If not NDJSON, load fully.
    try:
        return pd.read_json(path, lines=True, chunksize=chunksize)
    except ValueError:
        df = pd.read_json(path)
        for i in range(0, len(df), chunksize):
            yield df.iloc[i:i+chunksize]


def iter_pdf(path: str, chunksize: int) -> Iterable[pd.DataFrame]:
    # PDFs are not tabular; return empty frames (skip)
    yield pd.DataFrame()

def get_iterator(path: str, chunksize: int) -> Iterable[pd.DataFrame]:
    p = path.lower()
    if p.endswith(".csv") or p.endswith(".csv.gz"):
        return iter_csv(path, chunksize)
    if p.endswith(".parquet"):
        return iter_parquet(path, chunksize)
    if p.endswith(".json") or p.endswith(".jsonl"):
        return iter_json(path, chunksize)
    if p.endswith(".pdf"):
        return iter_pdf(path, chunksize)
    # default try CSV
    return iter_csv(path, chunksize)

# --------------- Core per-file processing ---------------
@celery_app.task(bind=True, name="process_file", acks_late=True)
def process_file(self, aid: str, file_id: int) -> Dict[str, Any]:
    started = time.time()
    path = _find_file_path_by_id(file_id)
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"File {file_id} not found")
    
    ckpt = load_ckpt(aid)
    start_chunk = ckpt.get(str(file_id), 0)
    
    detector = AnomalyDetector()
    anomalies = []
    rows_total = 0
    warmup = True
    
    try:
        for i, chunk in enumerate(get_iterator(path, CHUNK_ROWS)):
            if i < start_chunk:
                continue
            
            rows_total += len(chunk)
            
            # Preprocess
            pp = preprocess(chunk)
            feats = build_feature_pipeline(pp["X"]) # type: ignore
            X = feats["X"]
            # Fit detector on first non-empty chunk
            if warmup and not X.empty:
                detector.fit(X)
                warmup = False
            if X.empty:
                save_ckpt(aid, {**ckpt, str(file_id): i + 1})
                continue
            # Predict
            dr: DetectionResult = detector.predict(X, threshold=P_THRESHOLD, method='ensemble', compute_feature_importance=(i==0))
            # Collect top-N anomalies per chunk
            df_scores = pd.DataFrame({
                "index": X.index,
                "prob": dr.anomaly_prob,
                "score": dr.anomaly_score,
                "ci_low": dr.ci_low,
                "ci_high": dr.ci_high,
                "label": dr.labels,
            })
            top = df_scores.sort_values("prob", ascending=False).head(min(TOP_N, len(df_scores)))
            # Attach feature importance once
            fi = dr.feature_importance or {}
            for rec in top.to_dict(orient="records"):
                anomalies.append({
                    "row_index": int(rec["index"]) if isinstance(rec["index"], (int, np.integer)) else str(rec["index"]),
                    "prob": float(rec["prob"]),
                    "score": float(rec["score"]),
                    "ci": [float(rec["ci_low"]), float(rec["ci_high"])],
                    "file_id": file_id,
                    "feature_importance": fi,
                })
            # Progress + checkpoint
            save_ckpt(aid, {**ckpt, str(file_id): i + 1})
            set_status(aid, status="running", progress=min(0.95, (len(anomalies) / max(1, rows_total))), message=f"file {file_id} chunk {i}")
            # Memory hygiene
            del chunk, pp, feats, X, df_scores, top
            gc.collect()
    except SoftTimeLimitExceeded:
        logger.warning("process_file soft time limit exceeded", extra={"file_id": file_id})
        raise
    except Exception:
        logger.exception("process_file failed", extra={"file_id": file_id})
        raise

    observe_latency_ms("analysis.process_file", str(file_id), "chunks", (time.time() - started) * 1000)
    return {"file_id": file_id, "path": path, "rows_seen": rows_total, "anomalies": anomalies[:TOP_N]}

# --------------- Orchestrator ---------------
@celery_app.task(bind=True, name="start_analysis", acks_late=True)
def start_analysis(self, *, user_id: int, project_id: int, file_ids: List[int], ai_endpoint: str, enable_llm_explain: bool = False) -> Dict[str, Any]:
    aid = self.request.id or str(uuid.uuid4())
    set_status(aid, status="queued", progress=0.0, started_at=datetime.now(timezone.utc).isoformat())

    # Parallel process files via group, then aggregate using callback
    g = group(process_file.s(aid, fid) for fid in file_ids)

    def _on_complete(results: List[Dict[str, Any]]):
        # Flatten anomalies, attach basic analysis summary
        all_anoms = []
        for res in results:
            all_anoms.extend(res.get("anomalies", []))
        all_anoms.sort(key=lambda x: x["prob"], reverse=True)
        summary = {
            "analysis_id": aid,
            "project_id": project_id,
            "file_ids": file_ids,
            "total_anomalies": len(all_anoms),
            "top_k": TOP_N,
            "prob_threshold": P_THRESHOLD,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        cache_results(aid, {"summary": summary, "anomalies": all_anoms[:TOP_N]})
        set_status(aid, status="completed", progress=1.0, finished_at=datetime.now(timezone.utc).isoformat())
        return {"analysis_id": aid}

    # Launch chord (group + callback executed by worker)
    ch = chord(g)(_on_complete.s()) # type: ignore
    return {"analysis_id": aid, "task_id": str(ch.id)}

@celery_app.task(name="cancel_analysis")
def cancel_analysis(analysis_id: str) -> bool:
    try:
        celery_app.control.revoke(analysis_id, terminate=True)
        set_status(analysis_id, status="cancelled")
        return True
    except Exception:
        logger.exception("cancel failed", extra={"analysis_id": analysis_id})
        return False