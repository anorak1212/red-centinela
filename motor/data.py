"""Carga del dataset NSL-KDD y mapeo de familias de ataque."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "datasets" / "raw"
PROC_DIR = RAW_DIR.parent / "processed"
MODEL_DIR = Path(__file__).resolve().parent / "models"

LABEL = "label"
TARGET = "y_binary"  # 1 = ataque, 0 = normal

CATEGORICAL = ["protocol_type", "service", "flag"]

# Las 4 categorías de ataque del NSL-KDD. Las firmas de KDDTest+ que no
# aparecen en KDDTrain+ (apache2, mailbomb, xterm, etc.) entran en su
# familia según la literatura; si alguna no está mapeada cae en "unknown".
FAMILY: dict[str, str] = {
    "normal": "normal",
    # DoS
    "back": "dos", "land": "dos", "neptune": "dos", "pod": "dos",
    "smurf": "dos", "teardrop": "dos", "apache2": "dos", "mailbomb": "dos",
    "processtable": "dos", "udpstorm": "dos", "worm": "dos",
    # Probe
    "ipsweep": "probe", "nmap": "probe", "portsweep": "probe",
    "satan": "probe", "saint": "probe", "mscan": "probe",
    # R2L
    "guess_passwd": "r2l", "ftp_write": "r2l", "imap": "r2l", "phf": "r2l",
    "multihop": "r2l", "warezmaster": "r2l", "warezclient": "r2l",
    "spy": "r2l", "snmpgetattack": "r2l", "snmpguess": "r2l",
    "xlock": "r2l", "xsnoop": "r2l", "httptunnel": "r2l",
    # U2R
    "buffer_overflow": "u2r", "loadmodule": "u2r", "perl": "u2r",
    "rootkit": "u2r", "ps": "u2r", "sqlattack": "u2r", "xterm": "u2r",
}

# 41 características en el orden oficial del KDD Cup 1999.
FEATURE_NAMES = [
    "duration", "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent", "hot",
    "num_failed_logins", "logged_in", "num_compromised", "root_shell",
    "su_attempted", "num_root", "num_file_creations", "num_shells",
    "num_access_files", "num_outbound_cmds", "is_host_login", "is_guest_login",
    "count", "srv_count", "serror_rate", "srv_serror_rate", "rerror_rate",
    "srv_rerror_rate", "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]

# NSL-KDD definitivo: 41 características + etiqueta + nivel de dificultad.
COLUMNS = FEATURE_NAMES + [LABEL, "difficulty"]

FEATURE_COLUMNS = FEATURE_NAMES
NUMERIC_COLUMNS = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL]


def load_raw(name: str = "KDDTrain+.txt") -> pd.DataFrame:
    """Lee un archivo NSL-KDD (43 columnas) y agrega familia e y binaria."""
    path = RAW_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}.\nDescarga NSL-KDD y colócalo en datasets/raw/."
        )
    df = pd.read_csv(path, header=None, names=COLUMNS)
    df["family"] = df[LABEL].map(FAMILY).fillna("unknown")
    df[TARGET] = (df["family"] != "normal").astype(int)
    if df.shape[1] != len(COLUMNS) + 2:
        raise ValueError(
            f"Estructura inesperada en {name}: {df.shape[1]} columnas "
            f"(se esperaba {len(COLUMNS) + 2})."
        )
    return df


def ensure_processed(nombre: str = "train") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (X, y) en formato NumPy desde la caché o la genera."""
    import numpy as np

    base = PROC_DIR / nombre
    x_path, y_path = base.with_suffix(".X.npy"), base.with_suffix(".y.npy")
    if x_path.exists() and y_path.exists():
        return np.load(x_path), np.load(y_path)
    raise FileNotFoundError(
        f"Caché {x_path} no existe. Ejecuta primero: python -m motor.train"
    )