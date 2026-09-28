"""Persistencia en SQLite de las predicciones (historial)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("REDCENTINELA_DB", Path(__file__).resolve().parent / "data" / "redcentinela.db"))

_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predicciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    modelo      TEXT    NOT NULL,
    es_ataque   INTEGER NOT NULL,
    probabilidad REAL   NOT NULL,
    features    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_predicciones_ts ON predicciones (ts DESC);
"""


def _conexion() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _lock, _conexion() as con:
        con.executescript(_SCHEMA)


def guardar_prediccion(*, es_ataque: bool, probabilidad: float,
                       modelo: str, features: dict) -> int:
    ts = datetime.now(UTC).isoformat(timespec="seconds")
    with _lock, _conexion() as con:
        cur = con.execute(
            "INSERT INTO predicciones (ts, modelo, es_ataque, probabilidad, features)"
            " VALUES (?, ?, ?, ?, ?)",
            (ts, modelo, int(es_ataque), float(probabilidad),
             json.dumps(features, ensure_ascii=False)),
        )
        return int(cur.lastrowid)


def historial(limit: int = 50) -> list[dict]:
    with _lock, _conexion() as con:
        filas = con.execute(
            "SELECT id, ts, modelo, es_ataque, probabilidad, features"
            " FROM predicciones ORDER BY ts DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(fila) for fila in filas]