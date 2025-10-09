# tests/unit/test_anomaly_detector.py
from __future__ import annotations
import pandas as pd
from services.anomaly_detection.detector import AnomalyDetector


def test_detector_fit_predict():
    X = pd.DataFrame({"x": [0,0,0,10]})
    det = AnomalyDetector()
    det.fit(X)
    res = det.predict(X)
    assert len(res.anomaly_score) == 4
