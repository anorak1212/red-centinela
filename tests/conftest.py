"""Utilidades compartidas de las pruebas (A32: pruebas funcionales).

Todo lo que se genera aquí es sintético y vive en tmp_path: las pruebas
entrenan con un NSL-KDD simulado y escriben SOLO en directorios temporales,
nunca en motor/models/, datasets/ ni api/data/ del repositorio. Así pueden
correr en CI (GitHub Actions) sin red y sin el dataset real descargado.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import numpy as np
import pandas as pd
from motor import train
from motor.data import NUMERIC_COLUMNS, TARGET


def frame_sintetico(n: int = 600, semilla: int = 42) -> pd.DataFrame:
    """DataFrame con las 43 columnas de NSL-KDD + family + etiqueta binaria.

    Los ataques desplazan `src_bytes` para que el problema sea resoluble:
    sin ese sesgo el entrenamiento sintético no serviría para verificar que
    el pipeline (preproceso -> calibración -> empaquetado) funciona.
    """
    rng = np.random.default_rng(semilla)
    datos: dict = {c: rng.normal(0.0, 1.0, n) for c in NUMERIC_COLUMNS}
    datos["protocol_type"] = rng.choice(["tcp", "udp", "icmp"], n)
    datos["service"] = rng.choice(["http", "ftp", "smtp", "dns"], n)
    datos["flag"] = rng.choice(["SF", "S0", "REJ"], n)
    df = pd.DataFrame(datos)

    familias = rng.choice(
        ["normal", "dos", "probe", "r2l", "u2r"], n, p=[0.40, 0.30, 0.15, 0.10, 0.05]
    )
    ataques = familias != "normal"
    df.loc[ataques, "src_bytes"] += 500.0
    df["label"] = np.where(ataques, "neptune", "normal")
    df["family"] = familias
    df["difficulty"] = rng.integers(0, 21, n)
    df[TARGET] = ataques.astype(int)
    return df


@contextmanager
def entrenar_en(directorio, train_df: pd.DataFrame, test_df: pd.DataFrame):
    """Corre motor.train.main() escribiendo SOLO en `directorio`.

    Redirige load_raw (dataset sintético), MODEL_DIR y PROC_DIR para que ni
    los modelos reales ni la caché del repositorio se toquen.
    """

    def _cargar(nombre: str) -> pd.DataFrame:
        return train_df if "Train" in nombre else test_df

    with (
        patch.object(train, "load_raw", new=_cargar),
        patch.object(train, "MODEL_DIR", directorio),
        patch.object(train, "PROC_DIR", directorio / "processed"),
    ):
        train.main()
