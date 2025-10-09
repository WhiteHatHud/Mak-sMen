# services/anomaly_detection/detector.py
from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import MinMaxScaler
from sklearn.inspection import permutation_importance
from sklearn.utils.validation import check_is_fitted


logger = logging.getLogger(__name__)




@dataclass
class AnomalyScores:
	scores: np.ndarray  # raw anomaly scores (higher => more anomalous)
	prob: np.ndarray  # calibrated [0,1] anomaly probability (percentile rank)
	prob_ci_low: np.ndarray  # lower bound of CI per point
	prob_ci_high: np.ndarray  # upper bound of CI per point
	method: str  # 'iforest' | 'lof' | 'ensemble'




@dataclass
class DetectionResult:
	method: str
	index: List[Any]
	anomaly_score: List[float]
	anomaly_prob: List[float]
	ci_low: List[float]
	ci_high: List[float]
	threshold: float  # probability threshold used for anomaly labeling
	labels: List[int]  # 1 = anomaly, 0 = normal
	feature_importance: Optional[Dict[str, float]] = None
	meta: Optional[Dict[str, Any]] = None




class AnomalyDetector:
	"""
	IsolationForest + LOF ensemble with percentile calibration, Wilson CI, and permutation feature importance.
	- fit(X): trains models (IF, LOF novelty) and computes calibration reference.
	- predict(X, threshold=0.98): returns DetectionResult with probability/CI and labels.
	- batch_predict(list[pd.DataFrame]): processes multiple batches consistently (same fitted models).
	"""

	def __init__(
		self,
		random_state: int = 42,
		iforest_estimators: int = 300,
		iforest_max_samples: str | int = 'auto',
		contamination: float = 0.01,
		lof_n_neighbors: int = 20,
		ensemble_weights: Tuple[float, float] = (0.6, 0.4),
	) -> None:
		self.random_state = random_state
		self.iforest = IsolationForest(
			n_estimators=iforest_estimators,
			max_samples=iforest_max_samples,
			contamination=contamination,
			random_state=random_state,
			n_jobs=-1,
		)
		# LOF novelty allows transform/predict on new data
		self.lof = LocalOutlierFactor(
			n_neighbors=lof_n_neighbors,
			novelty=True,
			contamination=contamination,
			n_jobs=-1,
		)
		self.weights = np.array(ensemble_weights, dtype=float)
		self.weights = self.weights / self.weights.sum()
		self._calib_scores_: Optional[np.ndarray] = None
		self._feature_names_: Optional[List[str]] = None
		self._scaler = MinMaxScaler()

	# ---------------- Public API -----------------
	def fit(self, X: pd.DataFrame) -> 'AnomalyDetector':
		return {}