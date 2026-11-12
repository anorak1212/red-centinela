"""Pruebas de la verificación: cada estado sale de una medición, no de un texto.

Se simulan las respuestas (todo bien, API caída, métrica por debajo de la meta,
almacén que no persiste, endpoints que fallan) para comprobar que la capa
distingue "operando", "falla" y "no verificado" sin inventar nada.
"""

from __future__ import annotations

import pytest
from tablero import verificacion

API = "https://red-centinela-api.onrender.com"
TABLERO = "https://red-centinela.streamlit.app"


def _salud(**cambios) -> dict:
    base = {
        "status": "ok",
        "modelos_disponibles": True,
        "integridad_artefactos": True,
        "umbral_decision": 0.41,
        "almacen": {"motor": "postgres", "persistente": True},
        "metricas": {"binario_kddtest": {"macro_f1": 0.7995}},
    }
    base.update(cambios)
    return base


def _metricas(macro: float = 0.7995) -> dict:
    return {"binario_kddtest": {"macro_f1": macro}}


def _endpoints(codigo: int = 200) -> list[dict]:
    rutas = ["/health", "/metrics", "/history", "/history/resumen", "/alertas/estado"]
    return [{"ruta": r, "codigo": codigo, "ms": 30.0, "error": None} for r in rutas]


def _alertas(enviados: int = 1, configurado: bool = True) -> dict:
    return {
        "configurado": configurado,
        "enviados": enviados,
        "fallidos": 0,
        "ultimo_envio_exitoso": "2026-11-12T19:18:43Z",
    }


def _latencia(p95: float = 150.0, n: int = 5, error: str | None = None) -> dict:
    return {"p95_ms": p95, "mediana_ms": p95, "n": n, "fallos": 0,
            "umbral_ms": 200.0, "error": error}


def _tablero(codigo: int = 200, destino: str | None = None) -> dict:
    return {"url": TABLERO, "codigo": codigo, "ms": 80.0, "error": None,
            "destino": destino}


def _verificar(**cambios) -> dict:
    base = {
        "api_url": API,
        "tablero_url": TABLERO,
        "salud": _salud(),
        "metricas": _metricas(),
        "alertas": _alertas(),
        "endpoints": _endpoints(),
        "latencia": _latencia(),
        "tablero": _tablero(),
        "repositorio": {"ok": True, "detalle": "sample_trafico.csv 60 filas"},
    }
    base.update(cambios)
    return verificacion.verificar(**base)


def _modulo(veredicto: dict, ident: str) -> dict:
    return next(m for m in veredicto["modulos"] if m["id"] == ident)


def _criterio(veredicto: dict, ident: str) -> dict:
    return next(c for c in veredicto["criterios"] if c["id"] == ident)


# --------------------------------------------------------------------------
# Utilidades puras
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url, esperado",
    [
        ("https://red-centinela-api.onrender.com", True),
        ("https://red-centinela.streamlit.app", True),
        ("http://127.0.0.1:8000", False),
        ("http://localhost:8000", False),
        ("http://[::1]:8000", False),
        ("http://192.168.1.10:8000", False),
        ("http://10.0.0.5", False),
        ("ftp://ejemplo.com", False),
        ("", False),
        (None, False),
    ],
)
def test_es_url_publica(url, esperado):
    assert verificacion.es_url_publica(url) is esperado


def test_percentil_por_rango_mas_cercano():
    datos = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    assert verificacion.percentil(datos, 0.95) == 100.0
    assert verificacion.percentil(datos, 0.5) == 50.0
    assert verificacion.percentil([], 0.95) is None
    assert verificacion.percentil([7.0], 0.95) == 7.0


def test_medir_latencia_cuenta_muestras_y_mide(monkeypatch):
    tiempos = iter([0.0, 0.1, 0.1, 0.3, 0.3, 0.6])
    monkeypatch.setattr(verificacion.time, "perf_counter", lambda: next(tiempos))
    resultado = verificacion.medir_latencia(lambda fila: {"es_ataque": False}, muestras=3)
    assert resultado["n"] == 3
    assert resultado["p95_ms"] == pytest.approx(300.0)
    assert resultado["error"] is None


def test_medir_latencia_aborta_si_la_fila_sale_ataque():
    llamadas = []

    def predecir(fila):
        llamadas.append(fila)
        return {"es_ataque": True}

    resultado = verificacion.medir_latencia(predecir, muestras=10)
    assert len(llamadas) == 1, "debe cortar en la primera respuesta de ataque"
    assert "ataque" in resultado["error"]


def test_medir_latencia_sin_respuestas_reporta_error():
    def predecir(fila):
        raise RuntimeError("sin conexión")

    resultado = verificacion.medir_latencia(predecir, muestras=2)
    assert resultado["p95_ms"] is None
    assert resultado["fallos"] == 2
    assert "sin conexión" in resultado["error"]


def test_inspeccionar_datasets_ok(tmp_path):
    carpeta = tmp_path / "datasets"
    carpeta.mkdir()
    (carpeta / "sample_trafico.csv").write_text(
        ",".join(f"c{i}" for i in range(41)) + "\n" + ",".join("0" for _ in range(41)) + "\n",
        encoding="utf-8",
    )
    (carpeta / "sample_etiquetado.csv").write_text(
        ",".join(f"c{i}" for i in range(43)) + "\n" + ",".join("0" for _ in range(43)) + "\n",
        encoding="utf-8",
    )
    resultado = verificacion.inspeccionar_datasets(tmp_path)
    assert resultado["ok"] is True
    assert "sample_trafico.csv" in resultado["detalle"]


def test_inspeccionar_datasets_detecta_faltantes(tmp_path):
    resultado = verificacion.inspeccionar_datasets(tmp_path)
    assert resultado["ok"] is False
    assert "falta datasets/sample_trafico.csv" in resultado["detalle"]


# --------------------------------------------------------------------------
# Veredicto completo
# --------------------------------------------------------------------------
def test_todo_bien_deja_los_seis_modulos_operando():
    veredicto = _verificar(metricas=_metricas(0.95), latencia=_latencia(120.0))
    assert veredicto["operando"] == veredicto["total_modulos"] == 6
    assert all(m["estado"] == verificacion.OPERANDO for m in veredicto["modulos"])
    assert all(c["estado"] == verificacion.CUMPLIDO for c in veredicto["criterios"])


def test_api_caida_no_marca_falla_sino_no_verificado():
    veredicto = _verificar(salud=None, metricas=None, alertas=None, endpoints=None,
                           latencia=None, tablero=None)
    assert _modulo(veredicto, "M1")["estado"] == verificacion.OPERANDO
    for ident in ("M2", "M3", "M4", "M5", "M6"):
        assert _modulo(veredicto, ident)["estado"] == verificacion.NO_VERIFICADO
    assert _criterio(veredicto, "PERF-003")["estado"] == verificacion.NO_VERIFICADO
    assert _criterio(veredicto, "DEPLOY-013")["estado"] == verificacion.NO_VERIFICADO


def test_macro_f1_por_debajo_de_la_meta_sigue_no_cumplido():
    veredicto = _verificar(metricas=_metricas(0.7995))
    perf = _criterio(veredicto, "PERF-003")
    assert perf["estado"] == verificacion.NO_CUMPLIDO
    assert perf["medido"] == "0.7995"
    assert _modulo(veredicto, "M2")["estado"] == verificacion.OPERANDO, (
        "el motor opera aunque el criterio de calidad no se cumpla"
    )


def test_almacen_sqlite_no_persistente_es_falla_en_m3_y_m6():
    veredicto = _verificar(salud=_salud(almacen={"motor": "sqlite", "persistente": False}))
    assert _modulo(veredicto, "M3")["estado"] == verificacion.FALLA
    assert "no persistente" in _modulo(veredicto, "M3")["motivo"]
    assert _modulo(veredicto, "M6")["estado"] == verificacion.FALLA


def test_endpoint_de_lectura_caido_es_falla_en_m3():
    endpoints = _endpoints()
    endpoints[2]["codigo"] = 500
    veredicto = _verificar(endpoints=endpoints)
    m3 = _modulo(veredicto, "M3")
    assert m3["estado"] == verificacion.FALLA
    assert "/history" in m3["motivo"]


def test_api_en_modo_degradado_es_falla_en_m2_y_m3():
    veredicto = _verificar(salud=_salud(status="degradado", modelos_disponibles=False))
    assert _modulo(veredicto, "M2")["estado"] == verificacion.FALLA
    assert _modulo(veredicto, "M3")["estado"] == verificacion.FALLA


def test_alertas_sin_envios_quedan_no_verificadas_y_criterio_no_cumplido():
    veredicto = _verificar(alertas=_alertas(enviados=0))
    assert _modulo(veredicto, "M5")["estado"] == verificacion.NO_VERIFICADO
    assert _criterio(veredicto, "ALERT-010")["estado"] == verificacion.NO_CUMPLIDO


def test_alertas_sin_configurar_es_falla():
    veredicto = _verificar(alertas=_alertas(enviados=0, configurado=False))
    assert _modulo(veredicto, "M5")["estado"] == verificacion.FALLA


def test_tablero_que_pide_login_no_cumple_deploy_013():
    veredicto = _verificar(
        tablero=_tablero(303, "https://share.streamlit.io/-/auth/app")
    )
    assert _modulo(veredicto, "M4")["estado"] == verificacion.OPERANDO
    deploy = _criterio(veredicto, "DEPLOY-013")
    assert deploy["estado"] == verificacion.NO_CUMPLIDO
    assert "303" in deploy["motivo"]


def test_url_local_no_cumple_deploy_013():
    veredicto = _verificar(api_url="http://127.0.0.1:8000", tablero=None)
    assert _modulo(veredicto, "M6")["estado"] == verificacion.FALLA
    assert _criterio(veredicto, "DEPLOY-013")["estado"] == verificacion.NO_VERIFICADO


def test_latencia_sobre_la_meta_no_cumple():
    veredicto = _verificar(latencia=_latencia(254.0))
    perf = _criterio(veredicto, "PERF-006")
    assert perf["estado"] == verificacion.NO_CUMPLIDO
    assert "254" in perf["medido"]


def test_repositorio_incompleto_es_falla_en_m1():
    veredicto = _verificar(repositorio={"ok": False, "detalle": "falta datasets/x.csv"})
    assert _modulo(veredicto, "M1")["estado"] == verificacion.FALLA
