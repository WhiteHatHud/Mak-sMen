
# tests/fixtures/sample_files.py
from __future__ import annotations
import os
import json
import pandas as pd

def make_csv(tmp_path, rows: int = 10) -> str:
    df = pd.DataFrame({"amount": range(rows), "category": ["A"]*rows})
    p = tmp_path / "sample.csv"
    df.to_csv(p, index=False)
    return str(p)


def make_json(tmp_path, rows: int = 10) -> str:
    data = [{"amount": i, "flag": i % 2 == 0} for i in range(rows)]
    p = tmp_path / "sample.json"
    p.write_text(json.dumps(data))
    return str(p)