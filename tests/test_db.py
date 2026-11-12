"""Pruebas de la capa de almacenamiento (SQLite local y selección de motor)."""

from __future__ import annotations

from api import db


def _resultado(**extra) -> dict:
    base = {
        "es_ataque": True,
        "clase": "dos",
        "probabilidad_ataque": 0.97,
        "probabilidad_clase": 0.88,
        "modelo": "RandomForest",
        "version_modelo": "1.0.0",
        "origen": "prueba",
    }
    base.update(extra)
    return base


def test_init_idempotente():
    db.init_db()
    db.init_db()


def test_guardar_y_listar():
    db.init_db()
    ident = db.guardar_resultado(features={"service": "http"}, **_resultado())
    assert ident > 0
    filas = db.listar_historial(10)
    assert any(f["id"] == ident for f in filas)
    fila = next(f for f in filas if f["id"] == ident)
    assert fila["clase"] == "dos"
    assert fila["probabilidad_ataque"] == 0.97
    assert fila["features"]["service"] == "http"
    assert fila["es_ataque"] is True


def test_orden_descendente_y_limite():
    db.init_db()
    ids = [db.guardar_resultado(features={"n": i}, **_resultado()) for i in range(5)]
    filas = db.listar_historial(3)
    assert len(filas) == 3
    assert [f["id"] for f in filas] == sorted(ids, reverse=True)[:3]


def test_limite_se_acota():
    db.init_db()
    assert len(db.listar_historial(0)) == 1
    assert len(db.listar_historial(10_000)) <= 500


def test_ts_del_servidor_si_no_se_indica():
    db.init_db()
    ident = db.guardar_resultado(features={}, **_resultado())
    fila = next(f for f in db.listar_historial(50) if f["id"] == ident)
    assert "T" in fila["ts"]


def test_resumen_cuadra():
    db.init_db()
    antes = db.resumen()
    db.guardar_resultado(features={}, **_resultado(es_ataque=True, clase="probe"))
    db.guardar_resultado(features={}, **_resultado(es_ataque=False, clase="normal",
                                                  probabilidad_ataque=0.01))
    despues = db.resumen()
    assert despues["total"] == antes["total"] + 2
    assert despues["ataques"] == antes["ataques"] + 1
    assert despues["normales"] == despues["total"] - despues["ataques"]
    assert despues["por_clase"].get("probe", 0) >= 1


def test_resumen_separa_los_ataques_sin_familia():
    """Un ataque que el multiclase deja en "normal" suma en ataques, no en por_clase.

    Es el caso real de R2L y U2R: el binario los detecta y la cabeza multiclase no
    los reconoce. El resumen debe poder explicar la diferencia en vez de mostrar
    totales que no cuadran.
    """
    db.init_db()
    antes = db.resumen()
    db.guardar_resultado(features={}, **_resultado(es_ataque=True, clase="normal"))
    despues = db.resumen()
    assert despues["ataques"] == antes["ataques"] + 1
    assert despues["sin_familia"] == antes["sin_familia"] + 1
    assert despues["con_familia"] == despues["ataques"] - despues["sin_familia"]
    assert sum(despues["por_clase"].values()) == despues["total"]


def test_marcar_alerta_no_falla_con_id_inexistente():
    db.init_db()
    db.marcar_alerta(999_999, True)  # no debe lanzar


def test_almacen_local_es_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert db.motor() == "sqlite"
    info = db.descripcion()
    assert info["motor"] == "sqlite"
    assert info["persistente"] is False


def test_almacen_postgres_cuando_hay_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://usuario:clave@host/db")
    assert db.motor() == "postgres"
    info = db.descripcion()
    assert info["persistente"] is True
    assert "clave" not in str(info)


def test_descripcion_no_filtra_credenciales(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:secreto123@host/db")
    assert "secreto123" not in str(db.descripcion())


# --------------------------------------------------------------------------
# Migración del esquema viejo (v0.3.0: probabilidad en vez de
# probabilidad_ataque, sin clase ni origen)
# --------------------------------------------------------------------------
_ESQUEMA_VIEJO = """
CREATE TABLE predicciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT    NOT NULL,
    modelo       TEXT    NOT NULL,
    es_ataque    INTEGER NOT NULL,
    probabilidad REAL    NOT NULL,
    features     TEXT    NOT NULL
);
"""


def test_migra_esquema_viejo_sin_perder_filas(tmp_path, monkeypatch):
    import sqlite3

    ruta = tmp_path / "historial.db"
    con = sqlite3.connect(ruta)
    con.executescript(_ESQUEMA_VIEJO)
    con.execute(
        "INSERT INTO predicciones (ts, modelo, es_ataque, probabilidad, features)"
        " VALUES ('2026-10-06T09:00:44+00:00', 'ensamble(rf+knn+svm)', 1, 0.93, '{}')"
    )
    con.commit()
    con.close()

    monkeypatch.setattr(db, "SQLITE_PATH", ruta)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db.init_db()

    con = sqlite3.connect(ruta)
    tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "predicciones" in tablas
    assert "predicciones_legacy" in tablas
    assert con.execute("SELECT COUNT(*) FROM predicciones_legacy").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM predicciones").fetchone()[0] == 0
    columnas = {r[1] for r in con.execute("PRAGMA table_info(predicciones)")}
    con.close()
    assert columnas == set(db._COLUMNAS_ESPERADAS)
    assert list(tmp_path.glob("historial_legacy_*.db")), "falta la copia del archivo"


def test_migracion_es_idempotente(tmp_path, monkeypatch):
    import sqlite3

    ruta = tmp_path / "historial.db"
    monkeypatch.setattr(db, "SQLITE_PATH", ruta)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db.init_db()
    db.init_db()
    con = sqlite3.connect(ruta)
    tablas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    con.close()
    assert tablas.count("predicciones_legacy") == 0
    assert list(tmp_path.glob("*_legacy_*.db")) == []


def test_migracion_no_toca_el_esquema_actual(tmp_path, monkeypatch):
    ruta = tmp_path / "historial.db"
    monkeypatch.setattr(db, "SQLITE_PATH", ruta)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db.init_db()
    ident = db.guardar_resultado(features={"n": 1}, **_resultado())
    db.init_db()
    assert any(f["id"] == ident for f in db.listar_historial(10))

