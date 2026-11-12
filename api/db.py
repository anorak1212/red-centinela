"""Persistencia del historial de predicciones (DATA-011).

Hay dos implementaciones detrás de la misma interfaz mínima:

    guardar_resultado(...)  -> int          (id de la fila insertada)
    listar_historial(limit) -> list[dict]
    resumen()               -> dict         (conteos para el tablero)
    init_db()               -> None

El destino se elige con la variable de entorno DATABASE_URL:

- Sin DATABASE_URL: SQLite en api/data/redcentinela.db (desarrollo local y
  arranque de un solo comando).
- Con DATABASE_URL: PostgreSQL. Es obligatorio en Render, porque el sistema de
  archivos del plan gratuito se borra en cada reinicio y SQLite no persiste.

Todas las consultas son parametrizadas. Nunca se interpola texto del cliente en
el SQL (mitiga la inyección en AM-08 y AM-09).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

SQLITE_PATH = Path(
    os.environ.get("REDCENTINELA_DB", Path(__file__).resolve().parent / "data" / "redcentinela.db")
)

_COLUMNAS = (
    "id, ts, modelo, version_modelo, origen, es_ataque, clase, "
    "probabilidad_ataque, probabilidad_clase, alerta_enviada, features"
)

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS predicciones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                  TEXT    NOT NULL,
    modelo              TEXT    NOT NULL,
    version_modelo      TEXT    NOT NULL,
    origen              TEXT    NOT NULL,
    es_ataque           INTEGER NOT NULL,
    clase               TEXT    NOT NULL,
    probabilidad_ataque REAL    NOT NULL,
    probabilidad_clase  REAL    NOT NULL,
    alerta_enviada      INTEGER NOT NULL DEFAULT 0,
    features            TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_predicciones_ts ON predicciones (ts DESC);
"""

_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS predicciones (
    id                  BIGSERIAL PRIMARY KEY,
    ts                  TEXT    NOT NULL,
    modelo              TEXT    NOT NULL,
    version_modelo      TEXT    NOT NULL,
    origen              TEXT    NOT NULL,
    es_ataque           INTEGER NOT NULL,
    clase               TEXT    NOT NULL,
    probabilidad_ataque DOUBLE PRECISION NOT NULL,
    probabilidad_clase  DOUBLE PRECISION NOT NULL,
    alerta_enviada      INTEGER NOT NULL DEFAULT 0,
    features            TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_predicciones_ts ON predicciones (ts DESC);
"""

_COLUMNAS_ESPERADAS = (
    "id", "ts", "modelo", "version_modelo", "origen", "es_ataque", "clase",
    "probabilidad_ataque", "probabilidad_clase", "alerta_enviada", "features",
)

_lock = threading.Lock()


def url_datos() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def motor() -> str:
    """Devuelve 'postgres' o 'sqlite' según la configuración presente."""
    return "postgres" if url_datos() else "sqlite"


def descripcion() -> dict:
    """Describe el almacén sin revelar la cadena de conexión."""
    if motor() == "postgres":
        return {"motor": "postgres", "persistente": True,
                "nota": "Neon; sobrevive a reinicios del servicio"}
    return {"motor": "sqlite", "persistente": False,
            "ruta": SQLITE_PATH.name,
            "nota": "local; en Render se pierde al reiniciar"}


# --------------------------------------------------------------------------
# Conexiones
# --------------------------------------------------------------------------
def _conexion_sqlite() -> sqlite3.Connection:
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(SQLITE_PATH, check_same_thread=False, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def _conexion_postgres():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(url_datos(), row_factory=dict_row, connect_timeout=10)


def _marcadores(sql: str) -> str:
    """Traduce los marcadores ? de SQLite a %s de psycopg."""
    return sql.replace("?", "%s")


def init_db() -> None:
    """Crea la tabla si no existe y migra el esquema viejo de SQLite.

    El esquema anterior (hasta la versión 0.3.0) guardaba `probabilidad` en vez
    de `probabilidad_ataque`, y no tenía `clase`, `origen`, `version_modelo` ni
    `probabilidad_clase`. Las 73 filas de ese historial no se pueden rellenar sin
    inventar datos: el modelo viejo no clasificaba en cinco familias. Por eso se
    conserva la tabla completa como `predicciones_legacy` y se deja una copia del
    archivo junto a la base. El historial nuevo arranca con el esquema actual.

    Idempotente: con el esquema al día no hace nada.
    """
    with _lock:
        if motor() == "postgres":
            con = _conexion_postgres()
            try:
                with con.cursor() as cur:
                    cur.execute(_SCHEMA_POSTGRES)
                con.commit()
            finally:
                con.close()
            return

        con = _conexion_sqlite()
        try:
            _migrar_sqlite(con)
            con.executescript(_SCHEMA_SQLITE)
            con.commit()
        finally:
            con.close()


def _columnas_sqlite(con: sqlite3.Connection) -> list[str]:
    return [r["name"] for r in con.execute("PRAGMA table_info(predicciones)")]


def _migrar_sqlite(con: sqlite3.Connection) -> None:
    """Renombra la tabla vieja y respalda el archivo antes de migrar."""
    existentes = _columnas_sqlite(con)
    if not existentes or tuple(existentes) == _COLUMNAS_ESPERADAS:
        return
    if "predicciones_legacy" in {
        r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }:
        # Ya se migró en un arranque anterior.
        return

    respaldo = SQLITE_PATH.with_name(
        f"{SQLITE_PATH.stem}_legacy_{datetime.now(UTC):%Y%m%d%H%M%S}.db"
    )
    respaldo.write_bytes(SQLITE_PATH.read_bytes())
    con.execute("ALTER TABLE predicciones RENAME TO predicciones_legacy")
    con.commit()

    from logging import getLogger

    getLogger(__name__).warning(
        "Esquema de SQLite migrado. Historial anterior conservado en "
        "predicciones_legacy y en %s", respaldo.name
    )


# --------------------------------------------------------------------------
# Escritura
# --------------------------------------------------------------------------
def guardar_resultado(
    *,
    es_ataque: bool,
    clase: str,
    probabilidad_ataque: float,
    probabilidad_clase: float,
    modelo: str,
    version_modelo: str,
    origen: str,
    features: dict,
    alerta_enviada: bool = False,
    ts: str | None = None,
) -> int:
    """Inserta una predicción y devuelve su id.

    La marca de tiempo la pone el servidor, no el cliente (AM-08).
    """
    ts = ts or datetime.now(UTC).isoformat(timespec="seconds")
    valores = (
        ts, modelo, version_modelo, origen, int(bool(es_ataque)), clase,
        float(probabilidad_ataque), float(probabilidad_clase),
        int(bool(alerta_enviada)), json.dumps(features, ensure_ascii=False),
    )
    sql = (
        "INSERT INTO predicciones"
        " (ts, modelo, version_modelo, origen, es_ataque, clase,"
        "  probabilidad_ataque, probabilidad_clase, alerta_enviada, features)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    with _lock:
        if motor() == "postgres":
            con = _conexion_postgres()
            try:
                with con.cursor() as cur:
                    cur.execute(_marcadores(sql) + " RETURNING id", valores)
                    nuevo = cur.fetchone()["id"]
                con.commit()
                return int(nuevo)
            finally:
                con.close()
        con = _conexion_sqlite()
        try:
            cur = con.execute(sql, valores)
            con.commit()
            return int(cur.lastrowid)
        finally:
            con.close()


def marcar_alerta(id_prediccion: int, enviada: bool) -> None:
    """Actualiza la bandera de alerta una vez que la tarea en segundo plano
    conoce el resultado real del envío. Si falla, se deja como estaba."""
    valor = int(bool(enviada))
    sql = "UPDATE predicciones SET alerta_enviada = ? WHERE id = ?"
    try:
        with _lock:
            if motor() == "postgres":
                con = _conexion_postgres()
                try:
                    with con.cursor() as cur:
                        cur.execute(_marcadores(sql), (valor, int(id_prediccion)))
                    con.commit()
                finally:
                    con.close()
            else:
                con = _conexion_sqlite()
                try:
                    con.execute(sql, (valor, int(id_prediccion)))
                    con.commit()
                finally:
                    con.close()
    except Exception:  # noqa: BLE001, S110 - no debe tumbar la respuesta
        pass


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------
def _normalizar(fila: dict) -> dict:
    return {
        "id": int(fila["id"]),
        "ts": fila["ts"],
        "modelo": fila["modelo"],
        "version_modelo": fila["version_modelo"],
        "origen": fila["origen"],
        "es_ataque": bool(fila["es_ataque"]),
        "clase": fila["clase"],
        "probabilidad_ataque": round(float(fila["probabilidad_ataque"]), 4),
        "probabilidad_clase": round(float(fila["probabilidad_clase"]), 4),
        "alerta_enviada": bool(fila["alerta_enviada"]),
        "features": json.loads(fila["features"]),
    }


def listar_historial(limit: int = 50) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    sql = f"SELECT {_COLUMNAS} FROM predicciones ORDER BY id DESC LIMIT ?"
    with _lock:
        if motor() == "postgres":
            con = _conexion_postgres()
            try:
                with con.cursor() as cur:
                    cur.execute(_marcadores(sql), (limit,))
                    filas = cur.fetchall()
            finally:
                con.close()
        else:
            con = _conexion_sqlite()
            try:
                filas = [dict(r) for r in con.execute(sql, (limit,)).fetchall()]
            finally:
                con.close()
    return [_normalizar(f) for f in filas]


def resumen() -> dict:
    """Conteos agregados que alimenta el tablero (DASH-009)."""
    sql = (
        "SELECT COUNT(*) AS total,"
        " COALESCE(SUM(es_ataque), 0) AS ataques,"
        " MIN(ts) AS primero, MAX(ts) AS ultimo"
        " FROM predicciones"
    )
    sql_clases = "SELECT clase, COUNT(*) AS n FROM predicciones GROUP BY clase"
    # Las dos cabezas deciden por separado: el binario puede marcar ataque y el
    # multiclase no reconocer ninguna de las cuatro familias. Esas filas suman en
    # "ataques" pero no en "por_clase", y sin contarlas aparte el tablero muestra
    # totales que no cuadran. No se reescribe el historial: se cuenta y se explica.
    sql_sin_familia = (
        "SELECT COUNT(*) AS n FROM predicciones"
        " WHERE es_ataque = 1 AND clase = 'normal'"
    )
    with _lock:
        if motor() == "postgres":
            con = _conexion_postgres()
            try:
                with con.cursor() as cur:
                    cur.execute(sql)
                    base = cur.fetchone()
                    cur.execute(sql_clases)
                    por_clase = {r["clase"]: int(r["n"]) for r in cur.fetchall()}
                    cur.execute(sql_sin_familia)
                    sin_familia = int(cur.fetchone()["n"] or 0)
            finally:
                con.close()
        else:
            con = _conexion_sqlite()
            try:
                base = dict(con.execute(sql).fetchone())
                por_clase = {
                    r["clase"]: int(r["n"]) for r in con.execute(sql_clases).fetchall()
                }
                sin_familia = int(con.execute(sql_sin_familia).fetchone()["n"] or 0)
            finally:
                con.close()
    total = int(base["total"] or 0)
    ataques = int(base["ataques"] or 0)
    return {
        "total": total,
        "ataques": ataques,
        "normales": total - ataques,
        "por_clase": por_clase,
        "sin_familia": sin_familia,
        "con_familia": max(0, ataques - sin_familia),
        "primero": base["primero"],
        "ultimo": base["ultimo"],
        "almacen": descripcion(),
    }
