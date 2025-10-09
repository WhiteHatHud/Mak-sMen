# services/anomaly_detection/preprocessor.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
import logging
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, RobustScaler

logger = logging.getLogger(__name__)

def data_quality_checks(df: pd.DataFrame) -> Dict[str, Any]:
	return {
		"rows": int(df.shape[0]),
		"cols": int(df.shape[1]),
		"null_counts": df.isna().sum().to_dict(),
		"dtypes": {c: str(t) for c, t in df.dtypes.items()},
		"dup_rows": int(df.duplicated().sum()),
	}


def profile_stats(df: pd.DataFrame) -> Dict[str, Any]:
	desc = df.describe(include='all', datetime_is_numeric=True).to_dict()
	return {"describe": desc}


def cap_outliers(df_num: pd.DataFrame, lower_q: float = 0.01, upper_q: float = 0.99) -> pd.DataFrame:
	capped = df_num.copy()
	q_low = df_num.quantile(lower_q)
	q_hi = df_num.quantile(upper_q)
	return df_num.clip(lower=q_low, upper=q_hi, axis=1)

def preprocess(
	df: pd.DataFrame,
	categorical: Optional[List[str]] = None,
	timestamp_col: Optional[str] = None,
	entity_keys: Optional[List[str]] = None,
	scale: str = 'standard',  # 'standard' | 'robust' | 'none'
	impute_strategy: str = 'median',
	outlier_cap: bool = True,
) -> Dict[str, Any]:
	"""
	Preprocess DataFrame -> numeric feature matrix ready for modeling.
	- impute numeric/categorical
	- optional outlier capping
	- scale numeric
	- one-hot encode categoricals
	- add basic time features if timestamp_col present
	Returns dict with 'X' (DataFrame), 'meta' (dict)
	"""
	df = df.copy()
	meta: Dict[str, Any] = {"quality": data_quality_checks(df)}

	# Time features
	if timestamp_col and timestamp_col in df.columns:
		ts = pd.to_datetime(df[timestamp_col], errors='coerce')
		df["ts_hour"] = ts.dt.hour
		df["ts_day"] = ts.dt.day
		df["ts_dow"] = ts.dt.dayofweek
		df["ts_month"] = ts.dt.month
		meta["time_features"] = True

	# Split
	if categorical is None:
		categorical = list(df.select_dtypes(include=["object", "category"]).columns)
	numeric_cols = list(df.select_dtypes(include=[np.number]).columns)

	# Impute
	num_imputer = SimpleImputer(strategy=impute_strategy)
	cat_imputer = SimpleImputer(strategy='most_frequent')

	df_num = pd.DataFrame(num_imputer.fit_transform(df[numeric_cols]), columns=numeric_cols, index=df.index) if numeric_cols else pd.DataFrame(index=df.index)
	df_cat = pd.DataFrame(cat_imputer.fit_transform(df[categorical]), columns=categorical, index=df.index) if categorical else pd.DataFrame(index=df.index)

	# Outlier capping
	if outlier_cap and not df_num.empty:
		df_num = cap_outliers(df_num)

	# Scale
	if scale == 'standard' and not df_num.empty:
		scaler = StandardScaler()
		df_num[:] = scaler.fit_transform(df_num)
	elif scale == 'robust' and not df_num.empty:
		scaler = RobustScaler()
		df_num[:] = scaler.fit_transform(df_num)

	# Encode categoricals
	if not df_cat.empty:
		ohe = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
		enc = ohe.fit_transform(df_cat)
		cat_cols = ohe.get_feature_names_out(df_cat.columns)
		df_enc = pd.DataFrame(enc, columns=cat_cols, index=df.index)
		X = pd.concat([df_num, df_enc], axis=1)
	else:
		X = df_num

	meta["profile"] = profile_stats(X.select_dtypes(include=[np.number]))
	meta["features"] = list(X.columns)
	return {"X": X, "meta": meta}