"""Preprocesamiento: one-hot de categóricas + estandarización de numéricas.

El Preprocessor se ajusta SOLO con el conjunto de entrenamiento y luego se
reutiliza idéntico en la API y en el conjunto de prueba. Se serializa con
joblib junto a los modelos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .data import CATEGORICAL, NUMERIC_COLUMNS


class Preprocessor:
    """Codifica NSL-KDD en una matriz densa de 122 características."""

    def __init__(self) -> None:
        self.scaler_ = StandardScaler()
        self.cat_categories_: dict[str, list[str]] = {}
        self._fitted = False

    def fit(self, df: pd.DataFrame) -> Preprocessor:
        num = df[NUMERIC_COLUMNS].to_numpy(dtype=float)
        self.scaler_.fit(num)
        for c in CATEGORICAL:
            cats = list(dict.fromkeys(df[c].astype(str).tolist()))
            self.cat_categories_[c] = cats
        self._fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Preprocessor.fit() debe ejecutarse antes.")
        n = len(df)
        partes: list[np.ndarray] = []
        for c in CATEGORICAL:
            cats = self.cat_categories_[c]
            codes = pd.Categorical(df[c].astype(str), categories=cats).codes
            mat = np.zeros((n, len(cats)), dtype=np.float32)
            valid = codes >= 0
            mat[np.arange(n)[valid], codes[valid]] = 1.0
            partes.append(mat)
        num = self.scaler_.transform(df[NUMERIC_COLUMNS].to_numpy(dtype=float))
        partes.append(num.astype(np.float32))
        return np.hstack(partes)

    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        return self.fit(df).transform(df)

    def n_features(self) -> int:
        return sum(len(v) for v in self.cat_categories_.values()) + len(NUMERIC_COLUMNS)

    def feature_names(self) -> list[str]:
        names: list[str] = []
        prefijos = {"protocol_type": "proto_", "service": "srv_", "flag": "flg_"}
        for c in CATEGORICAL:
            names += [prefijos[c] + v for v in self.cat_categories_[c]]
        names += [f"num_{c}" for c in NUMERIC_COLUMNS]
        return names