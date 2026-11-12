"""Pruebas del tablero: cliente HTTP, parseo de CSV y render de cada vista.

El render se prueba con `AppTest`, el runner oficial de Streamlit. Las vistas se
montan contra una API inexistente (puerto 9, siempre cerrado): así se comprueba
lo que de verdad importa cuando algo falla, que es que el tablero explique el
problema en pantalla en vez de reventar con una traza.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from tablero import client
from tablero.client import COLUMNAS, ApiError, filas_desde_csv, leer_csv, salud

RAIZ = Path(__file__).resolve().parents[1]
SAMPLE = RAIZ / "datasets" / "sample_trafico.csv"
SAMPLE_ETIQUETADO = RAIZ / "datasets" / "sample_etiquetado.csv"
API_MUERTA = "http://127.0.0.1:9"

GUION_VISTA = """
import sys
sys.path.insert(0, r"{raiz}")
import importlib
importlib.import_module("tablero.vistas.{nombre}").render()
"""


@pytest.fixture(autouse=True)
def _restaurar_url():
    """El render de una vista cambia la URL global del cliente.

    Sin esto, la prueba que monta el tablero contra una API muerta deja el
    módulo apuntando al puerto 9 y las pruebas siguientes fallan por herencia.
    """
    original = client.API_URL
    yield
    client.configurar(original)


# --------------------------------------------------------------------------
# Contrato del cliente
# --------------------------------------------------------------------------
def test_columnas_esperadas():
    assert len(COLUMNAS) == 41
    assert set(COLUMNAS) >= {"protocol_type", "service", "flag"}


@pytest.mark.skipif(not SAMPLE.exists(), reason="falta datasets/sample_trafico.csv")
def test_filas_desde_csv_archivo_valido():
    filas = filas_desde_csv(SAMPLE)
    assert len(filas) >= 50
    assert set(filas[0].keys()) == set(COLUMNAS)
    assert isinstance(filas[0]["protocol_type"], str)
    assert isinstance(filas[0]["duration"], float)


def test_filas_desde_csv_rechaza_encabezado_invalido(tmp_path):
    malo = tmp_path / "malo.csv"
    malo.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Encabezado inválido"):
        filas_desde_csv(malo)


def test_filas_desde_csv_rechaza_numero_invalido(tmp_path):
    filas = ["duration," + ",".join(COLUMNAS[1:])]
    valores = ["abc"] + ["0"] * (len(COLUMNAS) - 1)
    for nombre in ("protocol_type", "service", "flag"):
        valores[COLUMNAS.index(nombre)] = "tcp"
    filas.append(",".join(valores))
    ruta = tmp_path / "roto.csv"
    ruta.write_text("\n".join(filas) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no es un número"):
        leer_csv(ruta)


@pytest.mark.skipif(not SAMPLE_ETIQUETADO.exists(), reason="falta la muestra etiquetada")
def test_leer_csv_acepta_etiquetas_y_las_devuelve():
    filas, familias = leer_csv(SAMPLE_ETIQUETADO)
    assert len(filas) == len(familias) == 150
    assert set(familias) == {"normal", "dos", "probe", "r2l", "u2r"}
    assert set(filas[0]) == set(COLUMNAS), "las etiquetas no deben viajar como features"


def test_leer_csv_sin_familia_devuelve_none(tmp_path):
    if not SAMPLE.exists():
        pytest.skip("falta datasets/sample_trafico.csv")
    filas, familias = leer_csv(SAMPLE)
    assert len(filas) == len(familias)
    assert all(f is None for f in familias)


def test_leer_csv_rechaza_columnas_sobrantes(tmp_path):
    ruta = tmp_path / "extra.csv"
    cabecera = ",".join([*COLUMNAS, "comentario"])
    ruta.write_text(cabecera + "\n" + ",".join(["0"] * (len(COLUMNAS) + 1)) + "\n",
                    encoding="utf-8")
    with pytest.raises(ValueError, match="sobran"):
        leer_csv(ruta)


def test_leer_csv_rechaza_archivo_sin_filas(tmp_path):
    ruta = tmp_path / "vacio.csv"
    ruta.write_text(",".join(COLUMNAS) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no tiene filas"):
        leer_csv(ruta)


def test_ejemplos_etiquetados_uno_por_familia():
    if not SAMPLE_ETIQUETADO.exists():
        pytest.skip("falta la muestra etiquetada")
    ejemplos = client.ejemplos_etiquetados(SAMPLE_ETIQUETADO)
    assert set(ejemplos) == {"normal", "dos", "probe", "r2l", "u2r"}
    assert set(ejemplos["dos"]) == set(COLUMNAS)


def test_ejemplos_etiquetados_sin_archivo():
    assert client.ejemplos_etiquetados(RAIZ / "no_existe.csv") == {}


def test_api_caida_lanza_apierror_con_la_url():
    original = client.API_URL
    client.configurar(API_MUERTA)
    try:
        with pytest.raises(ApiError, match="Sin conexión"):
            salud()
    finally:
        client.configurar(original)


# --------------------------------------------------------------------------
# Render de las vistas con la API caída
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "vista", ["resumen", "analizar", "historial", "modelo", "sistema", "ayuda"]
)
def test_vista_renderiza_sin_api(vista):
    at = AppTest.from_string(
        GUION_VISTA.format(raiz=RAIZ, nombre=vista), default_timeout=120
    )
    at.session_state["api_url"] = API_MUERTA
    at.run()
    assert not at.exception, [e.message for e in at.exception]


def test_resumen_avisa_cuando_la_api_no_responde():
    at = AppTest.from_string(
        GUION_VISTA.format(raiz=RAIZ, nombre="resumen"), default_timeout=120
    )
    at.session_state["api_url"] = API_MUERTA
    at.run()
    textos = " ".join(m.value for m in at.markdown)
    assert "API sin respuesta" in textos
    assert "no responde" in textos.lower()


def test_app_completa_arranca_y_declara_la_url():
    at = AppTest.from_file(str(RAIZ / "tablero" / "app.py"), default_timeout=120)
    at.session_state["api_url"] = API_MUERTA
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("URL de la API" in c.label for c in at.text_input)


# --------------------------------------------------------------------------
# Contrato contra una API viva (se salta si no está levantada)
# --------------------------------------------------------------------------
def _api_disponible() -> bool:
    try:
        return salud(timeout=3).get("status") == "ok"
    except ApiError:
        return False


@pytest.mark.skipif(not _api_disponible(), reason="API no disponible")
def test_health_contra_api():
    body = salud()
    assert body["status"] == "ok"
    assert body["integridad_artefactos"] is True
    assert 0.0 < float(body["umbral_decision"]) < 1.0


@pytest.mark.skipif(not _api_disponible(), reason="API no disponible")
def test_boton_reverificar_confirma_el_manifiesto():
    """El botón no es decorativo: rehashea y lo dice en pantalla."""
    at = AppTest.from_string(
        GUION_VISTA.format(raiz=RAIZ, nombre="resumen"), default_timeout=180
    )
    at.session_state["api_url"] = client.api_url()
    at.run()
    boton = next(b for b in at.button if "Reverificar" in b.label)
    boton.click().run()
    assert any("coinciden con el manifiesto" in s.value for s in at.success), [
        s.value for s in at.success
    ]


@pytest.mark.skipif(not _api_disponible(), reason="API no disponible")
def test_resumen_no_dibuja_boton_de_telegram_sin_credenciales():
    """Sin token no hay botón de prueba: se explica en su lugar."""
    at = AppTest.from_string(
        GUION_VISTA.format(raiz=RAIZ, nombre="resumen"), default_timeout=180
    )
    at.session_state["api_url"] = client.api_url()
    at.run()
    etiquetas = [b.label.lower() for b in at.button]
    assert not any("mensaje de prueba" in e for e in etiquetas)
    textos = " ".join(m.value for m in at.markdown)
    assert "Sin configurar" in textos or "sin configurar" in textos.lower()
