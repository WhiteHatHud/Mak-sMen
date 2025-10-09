# services/anomaly_detection/feature_engineering.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging
import numpy as np
import pandas as pd
from itertools import combinations
from sklearn.decomposition import PCA
from sklearn.feature_selection import VarianceThreshold

logger = logging.getLogger(__name__)

def add_statistical_features(df: pd.DataFrame, cols: Optional[List[str]] = None) -> pd.DataFrame:
	X = df.copy()
	cols = cols or list(X.select_dtypes(include=[np.number]).columns)
	if not cols:
		return X
	X["feat_mean"] = X[cols].mean(axis=1)
	X["feat_std"] = X[cols].std(axis=1).fillna(0)
	X["feat_skew"] = X[cols].skew(axis=1)
	X["feat_kurt"] = X[cols].kurt(axis=1)
	return X




def add_interaction_features(df: pd.DataFrame, max_pairs: int = 20) -> pd.DataFrame:
	X = df.copy()
	num_cols = list(X.select_dtypes(include=[np.number]).columns)
	pairs = list(combinations(num_cols, 2))[:max_pairs]
	for a, b in pairs:
		X[f"{a}__x__{b}"] = X[a] * X[b]
	return X



def add_rolling_features(
	df: pd.DataFrame,
	timestamp_col: Optional[str] = None,
	entity_keys: Optional[List[str]] = None,
	windows: List[int] = [3, 5, 10],
) -> pd.DataFrame:
	X = df.copy()
	if not timestamp_col or timestamp_col not in X.columns or not entity_keys:
		return X
	X = X.sort_values(entity_keys + [timestamp_col])
	num_cols = list(X.select_dtypes(include=[np.number]).columns)
	for w in windows:
		grp = X.groupby(entity_keys)
		for c in num_cols:
			X[f"{c}_rollmean_{w}"] = grp[c].transform(lambda s: s.rolling(w, min_periods=1).mean())
			X[f"{c}_rollstd_{w}"] = grp[c].transform(lambda s: s.rolling(w, min_periods=2).std()).fillna(0)
	return X





def pca_reduce(df: pd.DataFrame, n_components: int = 10) -> Dict[str, Any]:
	num = df.select_dtypes(include=[np.number])
	if num.empty:
		return {"X": df, "meta": {"pca": None}}
	k = min(n_components, num.shape[1])
	pca = PCA(n_components=k, random_state=42)
	comps = pca.fit_transform(num.values)
	cols = [f"pca_{i+1}" for i in range(comps.shape[1])]
	Xp = pd.DataFrame(comps, columns=cols, index=df.index)
	meta = {"explained_variance_ratio": pca.explained_variance_ratio_.tolist()}
	return {"X": Xp, "meta": meta}





def variance_filter(df: pd.DataFrame, thresh: float = 1e-6) -> pd.DataFrame:
	if df.empty:
		return df
	sel = VarianceThreshold(threshold=thresh)
	num = df.select_dtypes(include=[np.number])
	kept = sel.fit_transform(num.values)
	cols = [c for c, k in zip(num.columns, sel.get_support()) if k]
	X = pd.DataFrame(kept, columns=cols, index=df.index)
	# keep non-numeric as-is if any (rare for modeling matrix)
	others = df.drop(columns=num.columns, errors='ignore')
	return pd.concat([X, others], axis=1)





def add_domain_specific_beth(df: pd.DataFrame) -> pd.DataFrame:
	"""
	Placeholder for BETH-specific features. Examples (adjust to dataset semantics):
	- ratios between key numeric columns (e.g., amount_per_event = amount / events)
	- z-scores against group baselines by entity or category
	"""
	X = df.copy()
	num_cols = list(X.select_dtypes(include=[np.number]).columns)
	if len(num_cols) >= 2:
		a, b = num_cols[0], num_cols[1]
		with np.errstate(divide='ignore', invalid='ignore'):
			X[f"{a}_per_{b}"] = np.where(X[b]!=0, X[a] / X[b], 0.0)
	# group z-score example if entity key present
	for key in [c for c in X.columns if c.endswith('_id')][:1]:
		for c in num_cols[:3]:
			grp = X.groupby(key)[c]
			mu = grp.transform('mean')
			sd = grp.transform('std').replace(0, np.nan)
			X[f"{c}_z_by_{key}"] = ((X[c] - mu) / sd).fillna(0)
	return X





def build_feature_pipeline(
	df: pd.DataFrame,
	timestamp_col: Optional[str] = None,
	entity_keys: Optional[List[str]] = None,
	do_pca: bool = False,
	pca_components: int = 10,
	apply_variance_filter: bool = True,
) -> Dict[str, Any]:
	X = df.copy()
	X = add_statistical_features(X)
	X = add_interaction_features(X)
	X = add_domain_specific_beth(X)
	X = add_rolling_features(X, timestamp_col=timestamp_col, entity_keys=entity_keys)
	if apply_variance_filter:
		X = variance_filter(X)
	meta: Dict[str, Any] = {"features": list(X.columns)}
	if do_pca:
		pr = pca_reduce(X, n_components=pca_components)
		X = pr["X"]
		meta["pca"] = pr["meta"]
	return {"X": X, "meta": meta}