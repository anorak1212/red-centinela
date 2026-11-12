"""Pruebas del recorrido de la demo, el modo presentación y los textos."""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest
from tablero import guia
from tablero.ui import estilos

RAIZ = Path(__file__).resolve().parents[1]
API_MUERTA = "http://127.0.0.1:9"


def test_organico_convierte_separadores_en_frases():
    assert estilos.organico("local; en Render se pierde al reiniciar") == (
        "Local. En Render se pierde al reiniciar.")
    assert estilos.organico("a · b | c") == "A, b, c."
    assert estilos.organico("") == ""


def test_guion_tiene_siete_pasos_con_vista_existente():
    from tablero import navegacion

    assert len(guia.PASOS) == 7
    for clave, *_ in guia.PASOS:
        assert navegacion.pagina(clave) is not None


def _app():
    at = AppTest.from_file(str(RAIZ / "tablero" / "app.py"), default_timeout=120)
    at.session_state["api_url"] = API_MUERTA
    at.run()
    return at


def test_recorrido_avanza_cambia_de_vista_y_termina():
    at = _app()
    at.toggle(key="tg_guia").set_value(True).run()
    assert any("paso 1 de 7" in m.value for m in at.markdown)
    for _ in range(len(guia.PASOS) - 1):
        next(b for b in at.button if b.label == "Siguiente").click().run()
        assert not at.exception
    assert any("paso 7 de 7" in m.value for m in at.markdown)
    next(b for b in at.button if b.label == "Terminar").click().run()
    assert at.session_state["guia_activa"] is False
    assert not any("rc-guia-num" in m.value for m in at.markdown)


def test_modo_presentacion_inyecta_su_estilo():
    at = _app()
    at.toggle(key="tg_presentacion").set_value(True).run()
    assert any("font-size: 1.08rem" in m.value for m in at.markdown)


def test_textos_visibles_sin_separadores_secos():
    """Sin "·", ";" ni " | " en lo que se ve (CSS y entidades HTML aparte)."""
    at = _app()
    visibles = []
    for m in at.markdown:
        v = re.sub(r"<style>.*?</style>|<svg.*?</svg>", "", m.value, flags=re.DOTALL)
        v = re.sub(r"<[^>]+>|&[a-z]+;", " ", v)
        visibles.append(v)
    visibles += [c.value for c in at.caption] + [b.label for b in at.button]
    texto = " ".join(visibles)
    assert not re.search(r"·|;| \| ", texto), re.findall(r".{0,20}(?:·|;| \| ).{0,20}", texto)
