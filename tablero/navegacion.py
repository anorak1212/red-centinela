"""Páginas del tablero en un solo lugar.

Las usan `app.py` (menú) y el recorrido guiado (`guia.py`), que salta de una
vista a otra con `st.switch_page`.
"""

from __future__ import annotations

import streamlit as st

from tablero.vistas import (
    analizar,
    ayuda,
    configuracion,
    historial,
    modelo,
    resumen,
    sistema,
)


def paginas() -> dict[str, list[st.Page]]:
    """Construye las páginas en cada ejecución.

    Crear los `st.Page` una sola vez al importar el módulo los deja ligados a la
    primera ejecución (o a ninguna, en las pruebas); por eso se arman de nuevo
    en cada pasada, como recomienda Streamlit.
    """
    return {
        "Operación": [
            st.Page(resumen.render, title="Resumen", icon=":material/dashboard:",
                    url_path="resumen", default=True),
            st.Page(analizar.render, title="Analizar", icon=":material/radar:",
                    url_path="analizar"),
            st.Page(historial.render, title="Historial", icon=":material/history:",
                    url_path="historial"),
        ],
        "Modelo": [
            st.Page(modelo.render, title="Modelo y métricas", icon=":material/insights:",
                    url_path="modelo"),
        ],
        "Proyecto": [
            st.Page(sistema.render, title="Sistema", icon=":material/hub:",
                    url_path="sistema"),
            st.Page(ayuda.render, title="Ayuda", icon=":material/help:",
                    url_path="ayuda"),
        ],
        "Ajustes": [
            st.Page(configuracion.render, title="Configuración", icon=":material/settings:",
                    url_path="configuracion"),
        ],
    }


_UBICACION = {
    "resumen": ("Operación", 0), "analizar": ("Operación", 1), "historial": ("Operación", 2),
    "modelo": ("Modelo", 0), "sistema": ("Proyecto", 0), "ayuda": ("Proyecto", 1),
    "configuracion": ("Ajustes", 0),
}


def pagina(clave: str) -> st.Page:
    """Página por clave propia (la página por omisión expone url_path vacío)."""
    seccion, indice = _UBICACION[clave]
    return paginas()[seccion][indice]


def misma(a: st.Page, b: st.Page) -> bool:
    """Compara páginas por su título, que es único en el tablero."""
    return a.title == b.title
